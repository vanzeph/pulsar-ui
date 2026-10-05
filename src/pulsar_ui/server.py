"""The FastAPI read-only query service (:mod:`pulsar_ui.server`).

One local dashboard service over run artifacts and the data lake.
The API surface is exactly the one fixed by the UI design ("只读 API
面"), every endpoint is GET, responses are pre-aggregated server-side,
and the listener is bound to 127.0.0.1 — never anything else::

    GET /api/runs                    run 清单与指标摘要
    GET /api/runs/{id}/equity        净值曲线（服务端预聚合）
    GET /api/runs/{id}/trades        逐笔明细（分页）
    GET /api/runs/{id}/manifest      RunManifest 原文
    GET /api/factors/{name}/ic       因子 IC/IR（当前为明确空态）
    GET /api/lake/coverage           数据湖覆盖与质量热图
    GET /api/lake/bars/{symbol}      个股行情（K 线）

Failure behaviour follows the design's reliability rules: a missing or
unsupported artifact is a structured empty state on a 200 response, an
unknown run id is a 404, and a malformed parameter is a 422 — never a
stack trace. The service makes no outbound connections of any kind.

The service also hosts the built web dashboard (``web/`` → committed
under ``pulsar_ui/static/``) at ``/`` with an SPA fallback for the view
routes; see :mod:`pulsar_ui.webapp`.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from .artifacts import (
    MAX_CURVE_POINTS,
    MAX_TRADES_PAGE_SIZE,
    RunRecord,
    RunStore,
    parse_iso_date,
)
from .factors import factor_ic, valid_factor_name
from .lake import MAX_BARS_POINTS, LakeStore, valid_symbol
from .settings import DEFAULT_PORT, HOST, Settings
from .webapp import mount_web_app

__all__ = ["DEFAULT_MAX_POINTS", "create_app", "main", "serve"]

#: Default/ceiling for the server-side curve downsampling knobs.
DEFAULT_MAX_POINTS = 2_000

_API_DESCRIPTION = (
    "Pulsar local read-only dashboard service. GET-only; binds 127.0.0.1; "
    "serves pre-aggregated views of run artifacts and the local data lake."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the read-only application for the given (or environment) settings."""
    resolved = settings if settings is not None else Settings.from_env()
    runs = RunStore(resolved.runs_root)
    lake = LakeStore(resolved.lake_root)

    app = FastAPI(
        title="pulsar-ui",
        description=_API_DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    def require_run(run_id: str) -> RunRecord:
        record = runs.get(run_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "run_not_found", "run_id": run_id},
            )
        return record

    def run_summary(record: RunRecord) -> dict[str, Any]:
        start, end = record.span()
        summary = record.metrics_summary()
        return {
            "run_id": record.run_id,
            "directory": record.directory.name,
            "mode": (record.manifest or {}).get("mode"),
            "seed": (record.manifest or {}).get("seed"),
            "code_version": (record.manifest or {}).get("code_version"),
            "experiment_id": record.experiment_id(),
            "sweep": record.sweep_point(),
            "start": start,
            "end": end,
            "initial_cash": (record.metrics or {}).get("initial_cash"),
            "metrics": summary,
            "final_nav": (record.metrics or {}).get("final_nav")
            or ((summary or {}).get("final_nav")),
            "artifacts": {
                "manifest": record.manifest is not None,
                "events": record.events_path is not None,
                "metrics": record.metrics is not None,
            },
            "schema_support": {
                "manifest_supported": record.manifest_supported,
                "events_supported": record.events_supported,
                "metrics_supported": record.report_supported,
                "events_schema_versions": record.events_schema_versions,
            },
        }

    # -- service index ---------------------------------------------------------
    # "/" is the dashboard (see webapp.mount_web_app); the JSON service
    # index lives there as the no-build fallback.

    # -- runs -------------------------------------------------------------------

    @app.get("/api/runs", tags=["runs"])
    def list_runs() -> dict[str, Any]:
        records = runs.scan()
        summaries = [run_summary(record) for record in records.values()]
        summaries.sort(
            key=lambda item: (item["start"] or "", item["run_id"]), reverse=True
        )
        return {"count": len(summaries), "runs": summaries}

    @app.get("/api/runs/{run_id}/equity", tags=["runs"])
    def run_equity(
        run_id: str,
        max_points: int = Query(DEFAULT_MAX_POINTS, ge=1, le=MAX_CURVE_POINTS),
    ) -> dict[str, Any]:
        record = require_run(run_id)
        payload = runs.equity_curve(record, max_points)
        return {"run_id": record.run_id, **payload}

    @app.get("/api/runs/{run_id}/trades", tags=["runs"])
    def run_trades(
        run_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=MAX_TRADES_PAGE_SIZE),
    ) -> dict[str, Any]:
        record = require_run(run_id)
        payload = runs.trades(record, page=page, page_size=page_size)
        return {"run_id": record.run_id, **payload}

    @app.get("/api/runs/{run_id}/manifest", tags=["runs"])
    def run_manifest(run_id: str) -> dict[str, Any]:
        record = require_run(run_id)
        if record.manifest is None:
            return {
                "run_id": record.run_id,
                "available": False,
                "reason": record.manifest_error,
            }
        if not record.manifest_supported:
            return {
                "run_id": record.run_id,
                "available": False,
                "reason": (
                    f"run_manifest.json schema_version {record.manifest_schema!r} "
                    "is not supported by this reader"
                ),
            }
        # The design pins this endpoint to the manifest 原文: return the
        # parsed document as-is, no reshaping.
        return record.manifest

    # -- factors ------------------------------------------------------------------

    @app.get("/api/factors/{name}/ic", tags=["factors"])
    def factor_ic_series(name: str) -> dict[str, Any]:
        if not valid_factor_name(name):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_factor_name",
                    "name": name,
                    "reason": "factor names must be identifier-shaped",
                },
            )
        return factor_ic(name)

    # -- lake ------------------------------------------------------------------------

    @app.get("/api/lake/coverage", tags=["lake"])
    def lake_coverage() -> dict[str, Any]:
        return lake.coverage()

    @app.get("/api/lake/bars/{symbol}", tags=["lake"])
    def lake_bars(
        symbol: str,
        start: str | None = Query(None, description="YYYY-MM-DD (inclusive)"),
        end: str | None = Query(None, description="YYYY-MM-DD (inclusive)"),
        max_points: int = Query(DEFAULT_MAX_POINTS, ge=1, le=MAX_BARS_POINTS),
    ) -> dict[str, Any]:
        if not valid_symbol(symbol):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_symbol",
                    "symbol": symbol,
                    "reason": (
                        "symbols must be exchange-prefixed codes like SH600519 "
                        "(path-free characters only)"
                    ),
                },
            )
        start_date = end_date = None
        if start is not None:
            start_date = parse_iso_date(start)
            if start_date is None:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "invalid_start", "value": start},
                )
        if end is not None:
            end_date = parse_iso_date(end)
            if end_date is None:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "invalid_end", "value": end},
                )
        return lake.bars(
            symbol, start=start_date, end=end_date, max_points=max_points
        )

    # -- dashboard (static SPA hosting) ---------------------------------------
    # Mounted last so the API routes above always match first; the mount
    # serves the committed build output of web/ at "/" with an SPA fallback
    # for the client-side view routes. When the build output is absent the
    # app still comes up and "/" answers an explicit "not built" JSON index.
    mount_web_app(app)

    return app


def serve(settings: Settings | None = None, *, port: int | None = None) -> None:
    """Run the dashboard service, loopback-only.

    The host is deliberately not a parameter: :data:`HOST` (127.0.0.1) is
    the security baseline. Only the port is configurable.
    """
    import uvicorn

    resolved = settings if settings is not None else Settings.from_env()
    effective_port = port if port is not None else resolved.port
    uvicorn.run(create_app(resolved), host=HOST, port=effective_port)


def main(argv: list[str] | None = None) -> None:
    """Console entry point: ``pulsar-ui [--port N] [--runs-dir D] [--lake-dir D]``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="pulsar-ui",
        description=(
            "Pulsar local read-only dashboard (binds 127.0.0.1; "
            f"default port {DEFAULT_PORT})"
        ),
    )
    parser.add_argument("--port", type=int, default=None, help="listen port")
    parser.add_argument(
        "--runs-dir", type=str, default=None, help="root containing run directories"
    )
    parser.add_argument("--lake-dir", type=str, default=None, help="data lake root")
    args = parser.parse_args(argv)

    from pathlib import Path

    settings = Settings.from_env()
    if args.runs_dir is not None:
        settings = Settings(
            runs_root=Path(args.runs_dir), lake_root=settings.lake_root, port=settings.port
        )
    if args.lake_dir is not None:
        settings = Settings(
            runs_root=settings.runs_root, lake_root=Path(args.lake_dir), port=settings.port
        )
    serve(settings, port=args.port)

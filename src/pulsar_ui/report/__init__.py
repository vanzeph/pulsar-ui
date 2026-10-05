"""Static, self-contained HTML report generator (设计基线：静态报告).

run 结束时由 pulsar-app 调用本 CLI（一行命令，见 README「静态报告」节），
读取 run 目录三工件——与看板同源：``run_manifest.json`` /
``events.parquet`` / ``metrics_report.json``——产出自包含
``report.html``：数据与图全部内嵌（纯 HTML + CSS + 内联 SVG，无脚本、
无外部 CDN、零外部请求），写入 run 目录随 RunManifest 归档，双击即看、
可离线分享。

契约语义复用 :mod:`pulsar_ui.artifacts`（schema v1，锚定 pulsar-core
31801cb）：schema_version 不匹配时输出明确错误页而非半解析数据；工件
缺失时对应章节渲染明确空态。零 pulsar 包依赖（拓扑门禁约束）。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ..artifacts import (
    EVENTS_FILENAME,
    EVENTS_SCHEMA_VERSION,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    MAX_TRADES_PAGE_SIZE,
    METRICS_FILENAME,
    REPORT_SCHEMA_VERSION,
    RunStore,
)
from .charts import Point
from .render import ReportData, render_error_page, render_report

__all__ = [
    "DEFAULT_MAX_CURVE_POINTS",
    "DEFAULT_MAX_TRADE_ROWS",
    "REPORT_FILENAME",
    "ReportInputError",
    "generate_report",
    "main",
]

#: The report artifact written into the run directory.
REPORT_FILENAME = "report.html"

#: NAV curve cap for the embedded chart (two years of daily points).
DEFAULT_MAX_CURVE_POINTS = 730

#: Fill rows embedded in the static trades table; beyond this the table
#: notes the truncation instead of silently growing the archive.
DEFAULT_MAX_TRADE_ROWS = 1_000


class ReportInputError(ValueError):
    """The report was invoked on something that is not a run directory."""


def generate_report(
    run_dir: str | Path,
    *,
    output: str | Path | None = None,
    max_curve_points: int = DEFAULT_MAX_CURVE_POINTS,
    max_trade_rows: int = DEFAULT_MAX_TRADE_ROWS,
) -> Path:
    """Generate ``report.html`` for one run directory and return its path.

    ``run_dir`` must directly contain at least one of the three contract
    files (the same qualification :class:`RunStore` applies). The report
    is written to ``run_dir / report.html`` unless ``output`` names
    another path.
    """
    directory = Path(run_dir)
    if not directory.is_dir():
        raise ReportInputError(f"run 目录不存在或不是目录：{directory}")

    record = None
    for candidate in RunStore(directory).scan().values():
        if candidate.directory == directory or candidate.directory.resolve() == directory.resolve():
            record = candidate
            break
    if record is None:
        raise ReportInputError(
            "目录中未发现 run 工件"
            f"（{MANIFEST_FILENAME} / {EVENTS_FILENAME} / {METRICS_FILENAME}）：{directory}"
        )

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    mismatches, missing, status = _contract_status(record)

    if mismatches:
        document = render_error_page(
            run_dir=directory,
            generated_at=generated_at,
            mismatches=mismatches,
            missing=missing,
        )
    else:
        document = render_report(_collect_data(record, generated_at, status, max_curve_points, max_trade_rows))

    target = Path(output) if output is not None else record.directory / REPORT_FILENAME
    if not target.parent.is_dir():
        raise ReportInputError(f"输出目录不存在：{target.parent}")
    target.write_text(document, encoding="utf-8")
    return target


def _contract_status(record: Any) -> tuple[list, list, list]:
    """Classify the three artifacts: version mismatch / missing / status text.

    Mismatches drive the error page; missing or unreadable artifacts are
    states the normal report surfaces section by section.
    """
    mismatches: list[tuple[str, object, int]] = []
    missing: list[tuple[str, str]] = []
    status: list[tuple[str, str, bool]] = []

    if record.manifest is None:
        missing.append((MANIFEST_FILENAME, record.manifest_error or "未找到"))
        status.append((MANIFEST_FILENAME, "缺失", False))
    elif record.manifest_schema != MANIFEST_SCHEMA_VERSION:
        mismatches.append((MANIFEST_FILENAME, record.manifest_schema, MANIFEST_SCHEMA_VERSION))
        status.append((MANIFEST_FILENAME, f"schema v{record.manifest_schema}", False))
    else:
        status.append((MANIFEST_FILENAME, f"schema v{record.manifest_schema}", True))

    if record.metrics is None:
        missing.append((METRICS_FILENAME, record.metrics_error or "未找到"))
        status.append((METRICS_FILENAME, "缺失", False))
    elif record.report_schema != REPORT_SCHEMA_VERSION:
        mismatches.append((METRICS_FILENAME, record.report_schema, REPORT_SCHEMA_VERSION))
        status.append((METRICS_FILENAME, f"schema v{record.report_schema}", False))
    else:
        status.append((METRICS_FILENAME, f"schema v{record.report_schema}", True))

    if record.events_path is None or record.events_error:
        reason = record.events_error or "未找到"
        missing.append((EVENTS_FILENAME, reason))
        status.append((EVENTS_FILENAME, "不可读" if record.events_path else "缺失", False))
    elif not record.events_supported:
        versions = sorted(set(record.events_schema_versions))
        mismatches.append((EVENTS_FILENAME, versions, EVENTS_SCHEMA_VERSION))
        status.append((EVENTS_FILENAME, f"schema v{'/'.join(str(v) for v in versions)}", False))
    else:
        status.append((EVENTS_FILENAME, f"schema v{record.events_schema_versions[0]}", True))

    return mismatches, missing, status


def _collect_data(
    record: Any,
    generated_at: str,
    status: list[tuple[str, str, bool]],
    max_curve_points: int,
    max_trade_rows: int,
) -> ReportData:
    store = RunStore(record.directory)

    nav_series: list[Point] = []
    curve_total = curve_shown = 0
    downsampled = False
    initial_cash = None
    span_start = span_end = None
    curve = store.equity_curve(record, max_points=max_curve_points)
    if curve.get("available"):
        initial_cash = curve.get("initial_cash")
        curve_total = int(curve.get("total_points") or 0)
        downsampled = bool(curve.get("downsampled"))
        for point in curve.get("points") or []:
            if isinstance(point, dict) and isinstance(point.get("nav"), (int, float)):
                nav_series.append((str(point.get("ts", "")), float(point["nav"])))
        curve_shown = len(nav_series)
        span_start, span_end = record.span()

    metrics_summary = record.metrics_summary()
    if metrics_summary is None and record.metrics is not None:
        metrics_note = "metrics 报告未携带 metrics 指标块"
    else:
        metrics_note = record.metrics_error
    fees = record.metrics.get("fee_attribution") if record.metrics else None
    journal = record.metrics.get("journal_digest") if record.metrics else None

    fills, fills_total, fills_note = _collect_fills(store, record, max_trade_rows)

    return ReportData(
        run_id=record.run_id,
        directory=record.directory,
        generated_at=generated_at,
        artifact_status=tuple(status),
        manifest=record.manifest,
        manifest_note=record.manifest_error,
        metrics=metrics_summary,
        metrics_note=metrics_note,
        initial_cash=initial_cash,
        span_start=span_start,
        span_end=span_end,
        nav_series=nav_series,
        dd_series=_drawdown_series(nav_series),
        curve_total=curve_total,
        curve_shown=curve_shown,
        curve_downsampled=downsampled,
        fills=fills,
        fills_total=fills_total,
        fills_note=fills_note,
        fee_attribution=fees if isinstance(fees, dict) else None,
        journal_digest=journal if isinstance(journal, str) else None,
    )


def _collect_fills(
    store: RunStore, record: Any, max_trade_rows: int
) -> tuple[list[dict[str, Any]], int | None, str | None]:
    response = store.trades(record, page=1, page_size=MAX_TRADES_PAGE_SIZE)
    if not response.get("available"):
        return [], None, str(response.get("reason") or "不可用")
    total = int(response.get("total_fills") or 0)
    fills: list[dict[str, Any]] = list(response.get("fills") or [])
    wanted = min(max_trade_rows, total)
    page = 2
    while len(fills) < wanted:
        chunk = store.trades(record, page=page, page_size=MAX_TRADES_PAGE_SIZE)
        rows = chunk.get("fills") or []
        if not rows:
            break
        fills.extend(rows[: wanted - len(fills)])
        page += 1
    note = None
    if len(fills) < total:
        note = f"共 {total} 笔成交，静态报告仅内嵌前 {len(fills)} 笔（完整明细见 events.parquet 或看板）"
    return fills, total, note


def _drawdown_series(nav_series: Sequence[Point]) -> list[Point]:
    """Drawdown from the running peak: ``nav / peak - 1`` per point."""
    series: list[Point] = []
    peak: float | None = None
    for label, value in nav_series:
        peak = value if peak is None or value > peak else peak
        depth = value / peak - 1.0 if peak else 0.0
        series.append((label, depth))
    return series


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry: ``python -m pulsar_ui.report <run_dir> [-o OUTPUT]``."""
    parser = argparse.ArgumentParser(
        prog="python -m pulsar_ui.report",
        description="为单个 run 目录生成自包含静态 HTML 报告（默认写入 <run_dir>/report.html）",
    )
    parser.add_argument("run_dir", help="包含三工件的 run 目录")
    parser.add_argument(
        "-o", "--output", default=None, help="报告输出路径（默认 <run_dir>/report.html）"
    )
    args = parser.parse_args(argv)
    try:
        target = generate_report(args.run_dir, output=args.output)
    except ReportInputError as exc:
        print(f"报告生成失败：{exc}", file=sys.stderr)
        return 2
    print(target)
    return 0

"""Read-only access to run artifacts: the three-contract run directory.

pulsar-ui never imports pulsar code; it depends on the artifact *formats*
produced by ``pulsar-core`` (the ``pulsar_core.artifacts`` module, contract
version anchored at commit 31801cb)::

    <runs root>/<run dir>/run_manifest.json    reproducibility record
    <runs root>/<run dir>/events.parquet       full event journal
    <runs root>/<run dir>/metrics_report.json  equity curve + metrics + fees

This module scans a runs root for such directories, parses the two JSON
documents, and serves trades from the event archive through the guarded
DuckDB layer. Schema versions the reader understands are pinned here;
runs carrying versions we do not implement surface as explicit
"unsupported schema" states instead of half-parsed data. Missing
artifacts are *states, not errors*: every accessor reports availability.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .db import ReadOnlyDuckDB

__all__ = [
    "EVENTS_FILENAME",
    "EVENTS_SCHEMA_VERSION",
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "METRICS_FILENAME",
    "REPORT_SCHEMA_VERSION",
    "RunRecord",
    "RunStore",
]

#: Canonical artifact file names of the run-directory contract.
MANIFEST_FILENAME = "run_manifest.json"
EVENTS_FILENAME = "events.parquet"
METRICS_FILENAME = "metrics_report.json"

#: Artifact schema versions this reader implements (events schema v1 and
#: report/manifest schema v1 as of pulsar-core 31801cb). Bump on contract
#: changes; anything else surfaces as an explicit unsupported state.
MANIFEST_SCHEMA_VERSION = 1
EVENTS_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1

#: Run ids are 16 hex chars from the manifest digest; directory names may
#: be anything filesystem-safe. Used to reject path-shaped "ids".
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

#: Maximum number of fills one trades page may return (write-side of the
#: "超大结果集一律服务端预聚合，不下发原始行" baseline: trades are the only
#: per-row endpoint, so its page is the one thing that needs a hard cap).
MAX_TRADES_PAGE_SIZE = 500

#: Ceiling for the equity-curve downsampling knob.
MAX_CURVE_POINTS = 10_000


@dataclass
class RunRecord:
    """What the store knows about one discovered run directory."""

    run_id: str
    directory: Path
    manifest: dict[str, Any] | None = None
    manifest_error: str | None = None
    metrics: dict[str, Any] | None = None
    metrics_error: str | None = None
    events_path: Path | None = None
    events_schema_versions: list[int] = field(default_factory=list)
    events_error: str | None = None

    # -- derived views --------------------------------------------------------

    @property
    def manifest_schema(self) -> int | None:
        value = (self.manifest or {}).get("schema_version")
        return value if isinstance(value, int) else None

    @property
    def report_schema(self) -> int | None:
        value = (self.metrics or {}).get("schema_version")
        return value if isinstance(value, int) else None

    @property
    def manifest_supported(self) -> bool:
        return self.manifest_schema == MANIFEST_SCHEMA_VERSION

    @property
    def report_supported(self) -> bool:
        return self.report_schema == REPORT_SCHEMA_VERSION

    @property
    def events_supported(self) -> bool:
        return bool(self.events_schema_versions) and all(
            version == EVENTS_SCHEMA_VERSION for version in self.events_schema_versions
        )

    def experiment_id(self) -> str | None:
        """Experiment grouping key, when the manifest config carries one.

        Sweep families share ``config.experiment.id`` while each run keeps
        its own ``run_id`` — that is the run-group contract the backtest
        comparison view groups by.
        """
        config = (self.manifest or {}).get("config")
        if isinstance(config, dict):
            experiment = config.get("experiment")
            if isinstance(experiment, dict):
                value = experiment.get("id")
                if isinstance(value, str) and value:
                    return value
        return None

    def sweep_point(self) -> dict[str, Any] | None:
        """The run's sweep assignment (``config.sweep``), when present."""
        config = (self.manifest or {}).get("config")
        if isinstance(config, dict):
            sweep = config.get("sweep")
            if isinstance(sweep, dict):
                return sweep
        return None

    def metrics_summary(self) -> dict[str, Any] | None:
        """Headline metrics block, passed through from the report."""
        metrics = (self.metrics or {}).get("metrics")
        return metrics if isinstance(metrics, dict) else None

    def span(self) -> tuple[str | None, str | None]:
        start = (self.metrics or {}).get("start")
        end = (self.metrics or {}).get("end")
        return (
            start if isinstance(start, str) else None,
            end if isinstance(end, str) else None,
        )


def _parse_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{path.name} not found in run directory"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path.name} is unreadable: {exc}"
    if not isinstance(document, dict):
        return None, f"{path.name} is not a JSON object"
    return document, None


def _events_schema_versions(path: Path) -> tuple[list[int], str | None]:
    try:
        with ReadOnlyDuckDB() as db:
            rows = db.query(
                "SELECT DISTINCT schema_version AS v FROM read_parquet(?) "
                "ORDER BY v",
                [str(path)],
            )
        return [int(row["v"]) for row in rows], None
    except Exception as exc:  # noqa: BLE001 - duckdb surfaces unreadable parquet as many exception types; the UI must answer with an availability state, never a crash
        return [], f"events.parquet unreadable: {exc}"


class RunStore:
    """Scans one runs root and serves artifact reads for its run dirs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    # -- discovery ------------------------------------------------------------

    def scan(self) -> dict[str, RunRecord]:
        """Discover run directories keyed by run id.

        A directory qualifies when it directly contains at least one of the
        three contract files. The run id comes from the manifest when it is
        readable (the manifest is the identity of a run); directories whose
        manifest is missing or broken fall back to the directory name so
        they still surface in the list with explicit availability states.
        """
        records: dict[str, RunRecord] = {}
        if not self.root.is_dir():
            return records
        candidates = [self.root] + sorted(
            child for child in self.root.iterdir() if child.is_dir()
        )
        for directory in candidates:
            if not any(
                (directory / name).is_file()
                for name in (MANIFEST_FILENAME, EVENTS_FILENAME, METRICS_FILENAME)
            ):
                continue
            record = self._load_record(directory)
            key = record.run_id
            if key in records:  # duplicate id: keep scanning deterministically
                key = f"{key}::{directory.name}"
            record.run_id = key
            records[key] = record
        return records

    def _load_record(self, directory: Path) -> RunRecord:
        manifest, manifest_error = _parse_json_file(directory / MANIFEST_FILENAME)
        metrics, metrics_error = _parse_json_file(directory / METRICS_FILENAME)

        run_id = ""
        if manifest is not None:
            value = manifest.get("run_id")
            if isinstance(value, str) and _SAFE_ID.match(value):
                run_id = value
        if not run_id and _SAFE_ID.match(directory.name):
            run_id = directory.name
        if not run_id:
            run_id = directory.name

        events_path: Path | None = None
        events_versions: list[int] = []
        events_error: str | None = None
        candidate = directory / EVENTS_FILENAME
        if candidate.is_file():
            events_path = candidate
            events_versions, events_error = _events_schema_versions(candidate)
        else:
            events_error = "events.parquet not found in run directory"

        return RunRecord(
            run_id=run_id,
            directory=directory,
            manifest=manifest,
            manifest_error=manifest_error,
            metrics=metrics,
            metrics_error=metrics_error,
            events_path=events_path,
            events_schema_versions=events_versions,
            events_error=events_error,
        )

    # -- lookups --------------------------------------------------------------

    def get(self, run_id: str) -> RunRecord | None:
        """The record for ``run_id`` under this root, or ``None``."""
        if not _SAFE_ID.match(run_id):
            return None
        for key, record in self.scan().items():
            if key == run_id or record.directory.name == run_id:
                return record
        return None

    # -- artifact reads -------------------------------------------------------

    def equity_curve(self, record: RunRecord, max_points: int) -> dict[str, Any]:
        """The run's NAV curve from the metrics report, downsampled.

        The report's ``equity_curve`` is already the server-friendly daily
        aggregation (one point per trading day plus the start point); the
        optional downsampling keeps the last point of each bucket, so a
        bucket's NAV is its honest close.
        """
        if record.metrics is None:
            return {"available": False, "reason": record.metrics_error}
        if not record.report_supported:
            return {
                "available": False,
                "reason": (
                    f"metrics_report.json schema_version "
                    f"{record.report_schema!r} is not supported "
                    f"(this reader implements {REPORT_SCHEMA_VERSION})"
                ),
            }
        curve = record.metrics.get("equity_curve")
        if not isinstance(curve, list):
            return {"available": False, "reason": "metrics report carries no equity_curve"}
        points, downsampled = _downsample(curve, max_points)
        return {
            "available": True,
            "source": METRICS_FILENAME,
            "initial_cash": record.metrics.get("initial_cash"),
            "total_points": len(curve),
            "returned_points": len(points),
            "downsampled": downsampled,
            "max_points": max_points,
            "points": points,
        }

    def trades(
        self, record: RunRecord, *, page: int, page_size: int
    ) -> dict[str, Any]:
        """One page of fill rows from the event archive.

        Fills are the EXECUTION rows whose denormalized ``side`` is set
        (``event_type = 'fill'`` in the v1 archive); ordering follows the
        journal sequence column ``seq``.
        """
        if record.events_path is None:
            return {"available": False, "reason": record.events_error}
        if not record.events_supported:
            versions = sorted(set(record.events_schema_versions))
            return {
                "available": False,
                "reason": (
                    f"events.parquet schema version(s) {versions} not supported "
                    f"(this reader implements {EVENTS_SCHEMA_VERSION})"
                ),
            }
        assert record.events_path is not None  # for the type checker
        with ReadOnlyDuckDB() as db:
            total_rows = db.query(
                "SELECT count(*) AS total FROM read_parquet(?) "
                "WHERE event_type = 'fill' AND side IS NOT NULL",
                [str(record.events_path)],
            )
            total = int(total_rows[0]["total"])
            offset = (page - 1) * page_size
            rows = db.query(
                "SELECT seq, ts, symbol, side, price, quantity, "
                "commission, stamp_duty, transfer_fee "
                "FROM read_parquet(?) "
                "WHERE event_type = 'fill' AND side IS NOT NULL "
                "ORDER BY seq LIMIT ? OFFSET ?",
                [str(record.events_path), page_size, offset],
            )
        fills = []
        for row in rows:
            fees = sum(
                row[name] or 0.0
                for name in ("commission", "stamp_duty", "transfer_fee")
            )
            fills.append(
                {
                    "seq": int(row["seq"]),
                    "ts": row["ts"],
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "price": row["price"],
                    "quantity": int(row["quantity"]) if row["quantity"] is not None else None,
                    "commission": row["commission"],
                    "stamp_duty": row["stamp_duty"],
                    "transfer_fee": row["transfer_fee"],
                    "fees_total": fees,
                }
            )
        pages = (total + page_size - 1) // page_size
        return {
            "available": True,
            "source": EVENTS_FILENAME,
            "total_fills": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "fills": fills,
        }


def _downsample(items: list[dict[str, Any]], max_points: int) -> tuple[list[Any], bool]:
    """Keep at most ``max_points`` items, taking each bucket's last element.

    Deterministic bucket math over positions (no timestamps needed): bucket
    boundaries are ``round(i * n / max_points)``; the last bucket always
    ends at the final element so the curve's endpoint is never dropped.
    """
    count = len(items)
    if count <= max_points:
        return items, False
    kept: list[Any] = []
    for bucket in range(max_points):
        low = round(bucket * count / max_points)
        high = max(low + 1, round((bucket + 1) * count / max_points))
        high = min(high, count)
        kept.append(items[high - 1])
    return kept, True


def parse_iso_date(value: str) -> date | None:
    """Parse ``YYYY-MM-DD`` (or a full timestamp prefix) to a date."""
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError:
        return None

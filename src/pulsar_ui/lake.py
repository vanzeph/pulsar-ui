"""Read-only access to the local market-data lake.

pulsar-ui depends only on the lake *layout* (owned by pulsar-data)::

    lake/
      bars_1d/symbol=SH600519/year=2024/part.parquet   OHLCV + quality
      _meta/watermarks.parquet                          sync positions

``bars_1d`` files carry the canonical bar columns (``symbol, ts, open,
high, low, close, volume, amount, adjust_factor, quality``) with ``ts``
a timezone-aware Asia/Shanghai daily timestamp and ``quality`` one of
``ok / backfilled / suspect``. Everything here reads through the guarded
DuckDB layer; partition globs only ever match ``part.parquet`` so the
hidden ``.tmp-*`` siblings of an in-flight atomic write can never leak
into a result. A missing or empty lake is an explicit empty state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .db import ReadOnlyDuckDB

__all__ = ["MAX_BARS_POINTS", "LakeStore"]

#: Ceiling for the K-line endpoint's ``max_points`` parameter.
MAX_BARS_POINTS = 10_000

#: Lake symbols are exchange-prefixed codes (``SH600519``); partition keys
#: must stay path-free, so anything outside this shape is rejected before
#: it can touch a filesystem path or a glob.
_SAFE_SYMBOL = re.compile(r"^[A-Za-z]{2}[0-9]{4,6}[A-Za-z0-9]{0,4}$")

#: Quality marker values the coverage aggregation distinguishes.
QUALITY_LEVELS = ("ok", "backfilled", "suspect")


@dataclass(frozen=True)
class LakeStore:
    """Read-only views over one lake directory."""

    root: Path

    # -- helpers ---------------------------------------------------------------

    def _bars_files(self, symbol: str) -> list[Path]:
        base = self.root / "bars_1d" / f"symbol={symbol}"
        return sorted(base.glob("year=*/part.parquet"))

    def _glob_sql(self, files: list[Path]) -> str:
        quoted = ", ".join(f"'{path.as_posix().replace(chr(39), chr(39) * 2)}'" for path in files)
        return f"[{quoted}]"

    # -- datasets ---------------------------------------------------------------

    def coverage(self) -> dict[str, Any]:
        """Per symbol x year coverage, quality mix and watermark positions.

        This is the server-side pre-aggregation behind the coverage
        heatmap: the client receives group-by rows, never raw bars.
        """
        files = sorted(self.root.glob("bars_1d/symbol=*/year=*/part.parquet"))
        if not files:
            return {
                "available": False,
                "reason": (
                    "no bars_1d partitions found under the configured lake root"
                    if self.root.is_dir()
                    else "configured lake root does not exist"
                ),
                "symbols": [],
                "watermarks": {"available": False, "reason": "lake unavailable"},
            }
        with ReadOnlyDuckDB() as db:
            rows = db.query(
                "SELECT symbol, year(ts) AS yr, count(*) AS rows, "
                "min(ts) AS first_ts, max(ts) AS last_ts, "
                "count(*) FILTER (WHERE quality = 'ok') AS ok, "
                "count(*) FILTER (WHERE quality = 'backfilled') AS backfilled, "
                "count(*) FILTER (WHERE quality = 'suspect') AS suspect, "
                "count(*) FILTER ("
                "  WHERE quality IS NULL"
                "     OR quality NOT IN ('ok', 'backfilled', 'suspect')"
                ") AS other "
                f"FROM read_parquet({self._glob_sql(files)}, hive_partitioning=false) "
                "GROUP BY symbol, year(ts) ORDER BY symbol, yr"
            )
            watermarks = self._watermarks(db)
        by_symbol: dict[str, dict[str, Any]] = {}
        totals = {"rows": 0, "ok": 0, "backfilled": 0, "suspect": 0, "other": 0}
        for row in rows:
            year_block = {
                "year": int(row["yr"]),
                "rows": int(row["rows"]),
                "first_ts": row["first_ts"],
                "last_ts": row["last_ts"],
                "quality": {
                    "ok": int(row["ok"]),
                    "backfilled": int(row["backfilled"]),
                    "suspect": int(row["suspect"]),
                    "other": int(row["other"]),
                },
            }
            entry = by_symbol.setdefault(row["symbol"], {"symbol": row["symbol"], "years": []})
            entry["years"].append(year_block)
            totals["rows"] += year_block["rows"]
            for level in QUALITY_LEVELS + ("other",):
                totals[level] += year_block["quality"][level]
        symbols = [by_symbol[key] for key in sorted(by_symbol)]
        return {
            "available": True,
            "symbols": symbols,
            "totals": {**totals, "symbols": len(symbols)},
            "watermarks": watermarks,
        }

    def _watermarks(self, db: ReadOnlyDuckDB) -> dict[str, Any]:
        path = self.root / "_meta" / "watermarks.parquet"
        if not path.is_file():
            return {"available": False, "reason": "_meta/watermarks.parquet not found"}
        try:
            rows = db.query(
                "SELECT source, dataset, partition, rows, synced_through, updated_at "
                f"FROM read_parquet('{path.as_posix()}') "
                "ORDER BY dataset, partition"
            )
        except Exception as exc:  # noqa: BLE001 - a broken watermarks file is an availability state, not a crash
            return {"available": False, "reason": f"_meta/watermarks.parquet unreadable: {exc}"}
        return {"available": True, "entries": rows}

    def bars(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        max_points: int,
    ) -> dict[str, Any]:
        """OHLCV bars for one symbol, optionally windowed and downsampled.

        Downsampling aggregates into at most ``max_points`` time buckets
        (first-open / max-high / min-low / last-close / summed volume),
        computed in DuckDB — the client never receives raw rows beyond the
        cap.
        """
        files = self._bars_files(symbol)
        if not files:
            return {
                "available": False,
                "reason": (
                    f"no bars_1d partitions for symbol {symbol!r} in the lake"
                ),
                "symbol": symbol,
                "bars": [],
            }
        clauses: list[str] = []
        params: list[Any] = []
        if start is not None:
            clauses.append("CAST(ts AS DATE) >= ?")
            params.append(start)
        if end is not None:
            clauses.append("CAST(ts AS DATE) <= ?")
            params.append(end)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with ReadOnlyDuckDB() as db:
            total_rows = db.query(
                f"SELECT count(*) AS total FROM read_parquet("
                f"{self._glob_sql(files)}, hive_partitioning=false){where}",
                params,
            )
            total = int(total_rows[0]["total"])
            if total == 0:
                return {
                    "available": True,
                    "symbol": symbol,
                    "total_bars": 0,
                    "returned_bars": 0,
                    "downsampled": False,
                    "bars": [],
                }
            if total <= max_points:
                rows = db.query(
                    "SELECT ts, open, high, low, close, volume, amount, "
                    "adjust_factor, quality "
                    f"FROM read_parquet({self._glob_sql(files)}, hive_partitioning=false)"
                    f"{where} ORDER BY ts",
                    params,
                )
                downsampled = False
            else:
                rows = db.query(
                    "WITH ordered AS ("
                    "  SELECT *, row_number() OVER (ORDER BY ts) - 1 AS rn,"
                    "         count(*) OVER () AS n"
                    f"  FROM read_parquet({self._glob_sql(files)}, hive_partitioning=false)"
                    f"{where}"
                    "), bucketed AS ("
                    "  SELECT *, (rn * ?) // n AS bucket FROM ordered"
                    ") "
                    "SELECT first(ts ORDER BY ts) AS ts, "
                    "first(open ORDER BY ts) AS open, "
                    "max(high) AS high, min(low) AS low, "
                    "last(close ORDER BY ts) AS close, "
                    "sum(volume) AS volume, sum(amount) AS amount, "
                    "last(adjust_factor ORDER BY ts) AS adjust_factor, "
                    "last(quality ORDER BY ts) AS quality "
                    "FROM bucketed GROUP BY bucket ORDER BY bucket",
                    [*params, max_points],
                )
                downsampled = True
        return {
            "available": True,
            "symbol": symbol,
            "total_bars": total,
            "returned_bars": len(rows),
            "downsampled": downsampled,
            "max_points": max_points,
            "bars": rows,
        }


def valid_symbol(symbol: str) -> bool:
    """Whether ``symbol`` is a path-free lake symbol shape."""
    return bool(_SAFE_SYMBOL.match(symbol))

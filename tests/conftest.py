"""Shared fixtures: real run artifacts plus a lake synthesized per contract.

The run fixtures under ``fixtures/runs/`` were produced by pulsar-core's
``write_run_artifacts`` (commit 31801cb — the artifact contract this
service reads); see ``tests/test_artifacts_fixture.py`` for the local
round-trip check against the real reader when pulsar-core is installed.

The lake fixture is synthesized here from the *layout* contract only
(``bars_1d/symbol=.../year=.../part.parquet`` + ``_meta/watermarks.parquet``
with the canonical bar columns) — no pulsar package involved.
"""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from pulsar_ui.server import create_app
from pulsar_ui.settings import Settings

FIXTURE_RUNS = Path(__file__).parent / "fixtures" / "runs"

SHANGHAI = timezone(timedelta(hours=8))


def trading_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def bar_table(rows: list[dict]) -> pa.Table:
    schema = pa.schema(
        [
            pa.field("symbol", pa.string()),
            pa.field("ts", pa.timestamp("ns", tz="Asia/Shanghai")),
            pa.field("open", pa.float64()),
            pa.field("high", pa.float64()),
            pa.field("low", pa.float64()),
            pa.field("close", pa.float64()),
            pa.field("volume", pa.float64()),
            pa.field("amount", pa.float64()),
            pa.field("adjust_factor", pa.float64()),
            pa.field("quality", pa.string()),
        ]
    )
    return pa.table(
        {field.name: pa.array([row[field.name] for row in rows], type=field.type) for field in schema},
        schema=schema,
    )


def write_symbol_partitions(root: Path, symbol: str, per_year: dict[int, list[dict]]) -> None:
    for year, rows in per_year.items():
        target = root / "bars_1d" / f"symbol={symbol}" / f"year={year}" / "part.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(bar_table(rows), target)


def make_bars(
    symbol: str, days: list[date], *, start_price: float = 10.0, quality_plan: dict[int, str] | None = None
) -> list[dict]:
    rows: list[dict] = []
    price = start_price
    for index, day in enumerate(days):
        drift = 0.004 if index % 3 else -0.002
        open_ = round(price, 4)
        close = round(price * (1 + drift), 4)
        high = round(max(open_, close) * 1.002, 4)
        low = round(min(open_, close) * 0.998, 4)
        volume = 100_000.0 + 1_000.0 * (index % 17)
        quality = (quality_plan or {}).get(index, "ok")
        rows.append(
            {
                "symbol": symbol,
                "ts": datetime(day.year, day.month, day.day, tzinfo=SHANGHAI),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": round(close * volume, 2),
                "adjust_factor": 1.0,
                "quality": quality,
            }
        )
        price = close
    return rows


def build_lake(root: Path) -> None:
    """A small lake with two symbols, mixed quality and two watermarks."""
    sh_2024 = make_bars("SH600000", trading_days(date(2024, 1, 1), date(2024, 6, 30)))
    sh_2025 = make_bars("SH600000", trading_days(date(2025, 1, 1), date(2025, 3, 31)))
    sz_days = trading_days(date(2024, 1, 1), date(2024, 3, 31))
    sz_plan = {10: "backfilled", 20: "suspect", 21: "backfilled"}
    sz_2024 = make_bars("SZ000001", sz_days, start_price=8.0, quality_plan=sz_plan)
    write_symbol_partitions(
        root, "SH600000", {2024: sh_2024, 2025: sh_2025}
    )
    write_symbol_partitions(root, "SZ000001", {2024: sz_2024})

    meta = root / "_meta"
    meta.mkdir(parents=True, exist_ok=True)
    watermark_schema = pa.schema(
        [
            pa.field("source", pa.string()),
            pa.field("dataset", pa.string()),
            pa.field("partition", pa.string()),
            pa.field("rows", pa.int64()),
            pa.field("synced_through", pa.timestamp("ns", tz="Asia/Shanghai")),
            pa.field("updated_at", pa.timestamp("ns", tz="Asia/Shanghai")),
        ]
    )
    watermark_rows = [
        {
            "source": "fixture",
            "dataset": "bars_1d",
            "partition": f"symbol={symbol}/year={year}",
            "rows": rows,
            "synced_through": datetime(day.year, day.month, day.day, tzinfo=SHANGHAI),
            "updated_at": datetime(day.year, day.month, day.day, tzinfo=SHANGHAI),
        }
        for symbol, year, rows, day in (
            ("SH600000", 2024, len(sh_2024), date(2024, 7, 1)),
            ("SH600000", 2025, len(sh_2025), date(2025, 4, 1)),
            ("SZ000001", 2024, len(sz_2024), date(2024, 4, 1)),
        )
    ]
    pq.write_table(
        pa.table(
            {
                field.name: pa.array([row[field.name] for row in watermark_rows], type=field.type)
                for field in watermark_schema
            },
            schema=watermark_schema,
        ),
        meta / "watermarks.parquet",
    )


@pytest.fixture(scope="session")
def fixture_run_ids() -> list[str]:
    return sorted(path.name for path in FIXTURE_RUNS.iterdir() if path.is_dir())


@pytest.fixture(scope="session")
def runs_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("runs")
    shutil.copytree(FIXTURE_RUNS, target, dirs_exist_ok=True)
    return target


@pytest.fixture(scope="session")
def lake_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("lake")
    build_lake(target)
    return target


@pytest.fixture(scope="session")
def settings(runs_dir: Path, lake_dir: Path) -> Settings:
    return Settings(runs_root=runs_dir, lake_root=lake_dir, port=7800)


@pytest.fixture(scope="session")
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture(scope="session")
def client(app) -> TestClient:
    return TestClient(app)

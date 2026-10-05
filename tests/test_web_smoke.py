"""Acceptance (U2): four-view smoke over the U1 fixtures via TestClient.

End-to-end per view, at the API+hosting level the browser exercises:

* 回测对比 — ≥2 fixture runs (same experiment family) with equity curves
  and manifests for overlay/diff;
* 因子分析 — the IC endpoint's explicit empty state;
* 交易分析 — K-line bars for the traded symbol aligned with the run's
  fill dates (lake extended to cover the run session), plus fees;
* 数据可视化 — coverage heatmap rows and watermark entries.

The lake here reuses conftest's contract-based generators plus one extra
2026 partition for SH600000 so the run session has bars — exactly how a
real lake would look for that period.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import make_bars, trading_days, write_symbol_partitions

from pulsar_ui.server import create_app
from pulsar_ui.settings import Settings

RUN_A = "56659226cb264ae5"
RUN_B = "fe2ce6b1a85f1260"


@pytest.fixture(scope="module")
def smoke_client(
    tmp_path_factory: pytest.TempPathFactory, runs_dir: Path, lake_dir: Path
) -> TestClient:
    """Client over the fixture runs and a lake aligned to the run session."""
    lake = tmp_path_factory.mktemp("lake_smoke")
    shutil.copytree(lake_dir, lake, dirs_exist_ok=True)
    # bars for the traded symbol over the run session (June 2026)
    write_symbol_partitions(
        lake,
        "SH600000",
        {2026: make_bars("SH600000", trading_days(date(2026, 6, 1), date(2026, 6, 30)), start_price=99.2)},
    )
    return TestClient(
        create_app(Settings(runs_root=runs_dir, lake_root=lake, port=7800))
    )


def test_backtest_view_two_runs_compare(smoke_client: TestClient) -> None:
    listing = smoke_client.get("/api/runs").json()
    assert listing["count"] >= 2
    runs = {run["run_id"]: run for run in listing["runs"]}
    assert RUN_A in runs and RUN_B in runs
    # same experiment family -> the comparison view's grouping dimension
    assert runs[RUN_A]["experiment_id"] == runs[RUN_B]["experiment_id"]
    assert runs[RUN_A]["seed"] != runs[RUN_B]["seed"]

    curves = []
    for run_id in (RUN_A, RUN_B):
        payload = smoke_client.get(f"/api/runs/{run_id}/equity").json()
        assert payload["available"] is True
        assert len(payload["points"]) >= 10
        curves.append(payload)
    # NAV series overlap on dates and differ in content (seed differs)
    dates_a = {point["ts"] for point in curves[0]["points"]}
    dates_b = {point["ts"] for point in curves[1]["points"]}
    assert dates_a & dates_b

    manifests = [
        smoke_client.get(f"/api/runs/{run_id}/manifest").json() for run_id in (RUN_A, RUN_B)
    ]
    assert all(doc["schema_version"] == 1 for doc in manifests)
    # seed differs -> the manifest diff view has at least one changed field
    assert manifests[0]["seed"] != manifests[1]["seed"]

    # the dashboard page hosting this view is served
    page = smoke_client.get("/")
    assert page.status_code == 200 and 'id="root"' in page.text


def test_factor_view_renders_explicit_empty_state(smoke_client: TestClient) -> None:
    payload = smoke_client.get("/api/factors/momentum_20/ic").json()
    assert payload["available"] is False
    assert payload["reason"]
    assert payload["ic_series"] == []
    page = smoke_client.get("/factors")
    assert page.status_code == 200 and 'id="root"' in page.text


def test_trades_view_kline_with_buy_sell_markers(smoke_client: TestClient) -> None:
    fills = smoke_client.get(f"/api/runs/{RUN_A}/trades").json()
    assert fills["available"] is True and fills["total_fills"] >= 2
    traded_symbols = {fill["symbol"] for fill in fills["fills"]}
    assert traded_symbols == {"600000"}

    bars = smoke_client.get("/api/lake/bars/SH600000").json()
    assert bars["available"] is True
    assert bars["total_bars"] >= 20

    bar_dates = {bar["ts"][:10] for bar in bars["bars"]}
    for fill in fills["fills"]:
        assert fill["ts"][:10] in bar_dates, (
            f"fill on {fill['ts']} has no bar to anchor its buy/sell marker"
        )
    # every fill row carries the fee breakdown the table renders
    for fill in fills["fills"]:
        for key in ("commission", "stamp_duty", "transfer_fee", "fees_total"):
            assert key in fill

    page = smoke_client.get("/trades")
    assert page.status_code == 200 and 'id="root"' in page.text


def test_lake_view_coverage_and_watermarks(smoke_client: TestClient) -> None:
    payload = smoke_client.get("/api/lake/coverage").json()
    assert payload["available"] is True
    symbols = {entry["symbol"]: entry for entry in payload["symbols"]}
    assert "SH600000" in symbols and "SZ000001" in symbols
    years = {block["year"] for block in symbols["SH600000"]["years"]}
    assert {2024, 2025, 2026} <= years
    # quality mix is part of every heatmap cell
    for entry in payload["symbols"]:
        for block in entry["years"]:
            assert set(block["quality"]) == {"ok", "backfilled", "suspect", "other"}
    watermarks = payload["watermarks"]
    assert watermarks["available"] is True and len(watermarks["entries"]) >= 3
    page = smoke_client.get("/lake")
    assert page.status_code == 200 and 'id="root"' in page.text

"""Lake endpoints: coverage heatmap aggregation and K-line serving."""

from __future__ import annotations

import time
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from pulsar_ui.server import create_app
from pulsar_ui.settings import Settings

SECONDS_BUDGET = 1.0


class TestCoverage:
    def test_aggregates_rows_quality_and_watermarks(
        self, client: TestClient, lake_dir: Path
    ) -> None:
        started = time.perf_counter()
        response = client.get("/api/lake/coverage")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < SECONDS_BUDGET
        payload = response.json()
        assert payload["available"] is True

        symbols = {entry["symbol"]: entry for entry in payload["symbols"]}
        assert set(symbols) == {"SH600000", "SZ000001"}
        sh = symbols["SH600000"]
        assert [year["year"] for year in sh["years"]] == [2024, 2025]

        # per-partition row counts come from the parquet files themselves
        file_rows = pq.read_table(
            lake_dir / "bars_1d" / "symbol=SH600000" / "year=2024" / "part.parquet"
        ).num_rows
        year_2024 = next(y for y in sh["years"] if y["year"] == 2024)
        assert year_2024["rows"] == file_rows
        assert year_2024["first_ts"] <= year_2024["last_ts"]

        sz = next(year for year in symbols["SZ000001"]["years"] if year["year"] == 2024)
        quality = sz["quality"]
        assert quality["ok"] + quality["backfilled"] + quality["suspect"] == sz["rows"]
        assert quality["backfilled"] == 2
        assert quality["suspect"] == 1

        totals = payload["totals"]
        assert totals["symbols"] == 2
        assert totals["rows"] == sum(
            year["rows"] for symbol in payload["symbols"] for year in symbol["years"]
        )
        watermarks = payload["watermarks"]
        assert watermarks["available"] is True
        assert len(watermarks["entries"]) == 3
        partitions = {entry["partition"] for entry in watermarks["entries"]}
        assert "symbol=SZ000001/year=2024" in partitions

    def test_missing_lake_is_an_explicit_empty_state(self, tmp_path: Path) -> None:
        app = create_app(Settings(runs_root=tmp_path / "runs", lake_root=tmp_path / "nope"))
        with TestClient(app) as client:
            response = client.get("/api/lake/coverage")
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert payload["symbols"] == []
        assert "lake" in payload["reason"]


class TestBars:
    def test_serves_ohlcv_in_order_without_downsampling(
        self, client: TestClient, lake_dir: Path
    ) -> None:
        started = time.perf_counter()
        response = client.get("/api/lake/bars/SH600000")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < SECONDS_BUDGET
        payload = response.json()
        assert payload["available"] is True
        assert payload["symbol"] == "SH600000"
        assert payload["downsampled"] is False

        files = sorted(
            (lake_dir / "bars_1d" / "symbol=SH600000").glob("year=*/part.parquet")
        )
        expected_rows = sum(pq.read_table(path).num_rows for path in files)
        assert payload["total_bars"] == expected_rows
        assert payload["returned_bars"] == expected_rows

        bars = payload["bars"]
        ts_sequence = [bar["ts"] for bar in bars]
        assert ts_sequence == sorted(ts_sequence)
        for bar in bars:
            assert bar["low"] <= bar["open"] <= bar["high"]
            assert bar["low"] <= bar["close"] <= bar["high"]
            assert bar["quality"] in ("ok", "backfilled", "suspect")
        first = pq.read_table(files[0]).slice(0, 1).to_pylist()[0]
        assert bars[0]["close"] == pytest.approx(first["close"])

    def test_downsampling_aggregates_into_bounded_buckets(
        self, client: TestClient
    ) -> None:
        payload = client.get(
            "/api/lake/bars/SH600000", params={"max_points": 10}
        ).json()
        assert payload["available"] is True
        assert payload["downsampled"] is True
        bars = payload["bars"]
        assert len(bars) <= 10
        ts_sequence = [bar["ts"] for bar in bars]
        assert ts_sequence == sorted(ts_sequence)
        for bar in bars:
            assert bar["low"] <= bar["open"] <= bar["high"]
            assert bar["low"] <= bar["close"] <= bar["high"]

    def test_window_filtering_by_date(self, client: TestClient) -> None:
        payload = client.get(
            "/api/lake/bars/SH600000",
            params={"start": "2024-02-01", "end": "2024-02-28"},
        ).json()
        assert payload["available"] is True
        assert payload["total_bars"] == len(payload["bars"])
        assert payload["bars"], "February 2024 has weekday bars"
        for bar in payload["bars"]:
            stamp = bar["ts"][:10]
            assert "2024-02-01" <= stamp <= "2024-02-28"

    def test_unknown_symbol_is_an_explicit_empty_state(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/lake/bars/SH999999")
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert "no bars_1d partitions" in payload["reason"]
        assert payload["bars"] == []

    def test_malformed_symbol_and_dates_are_rejected(self, client: TestClient) -> None:
        traversal = client.get("/api/lake/bars/..%2F..%2Fetc")
        assert traversal.status_code in (404, 422)
        bad_shape = client.get("/api/lake/bars/not%20a%20symbol")
        assert bad_shape.status_code == 422
        assert bad_shape.json()["detail"]["error"] == "invalid_symbol"
        bad_date = client.get("/api/lake/bars/SH600000", params={"start": "yesterday"})
        assert bad_date.status_code == 422

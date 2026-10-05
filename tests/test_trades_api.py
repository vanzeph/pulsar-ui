"""Trades endpoint: pagination, fee columns, and unsupported-schema states."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from pulsar_ui.server import create_app
from pulsar_ui.settings import Settings

SECONDS_BUDGET = 1.0


@pytest.fixture()
def known_run(fixture_run_ids: list[str]) -> str:
    return fixture_run_ids[0]


class TestTrades:
    def test_serves_fill_rows_with_fees_within_seconds(
        self, client: TestClient, known_run: str, runs_dir: Path
    ) -> None:
        started = time.perf_counter()
        response = client.get(f"/api/runs/{known_run}/trades")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < SECONDS_BUDGET
        payload = response.json()
        assert payload["available"] is True
        assert payload["source"] == "events.parquet"
        assert payload["page"] == 1
        assert payload["page_size"] == 50

        fills = payload["fills"]
        assert len(fills) == payload["total_fills"]
        assert fills, "the fixture run must have traded"
        for fill in fills:
            assert fill["side"] in ("buy", "sell")
            assert fill["price"] > 0
            assert fill["quantity"] > 0
            for fee_column in ("commission", "stamp_duty", "transfer_fee", "fees_total"):
                assert fee_column in fill
        seqs = [fill["seq"] for fill in fills]
        assert seqs == sorted(seqs)
        # every fill appears exactly once in the denormalized archive view
        table = pq.read_table(runs_dir / known_run / "events.parquet")
        event_types = table.column("event_type").to_pylist()
        sides = table.column("side").to_pylist()
        archive_fills = sum(
            1 for event_type, side in zip(event_types, sides)
            if event_type == "fill" and side is not None
        )
        assert payload["total_fills"] == archive_fills

    def test_pagination_windows_and_reports_totals(
        self, client: TestClient, known_run: str
    ) -> None:
        everything = client.get(f"/api/runs/{known_run}/trades").json()
        if everything["total_fills"] < 2:
            pytest.skip("fixture run has fewer than two fills")
        first = client.get(
            f"/api/runs/{known_run}/trades", params={"page": 1, "page_size": 1}
        ).json()
        second = client.get(
            f"/api/runs/{known_run}/trades", params={"page": 2, "page_size": 1}
        ).json()
        assert first["total_fills"] == everything["total_fills"]
        assert first["pages"] == everything["total_fills"]
        assert len(first["fills"]) == 1
        assert second["fills"][0]["seq"] > first["fills"][0]["seq"]
        beyond = client.get(
            f"/api/runs/{known_run}/trades", params={"page": 999, "page_size": 10}
        ).json()
        assert beyond["fills"] == []
        assert beyond["total_fills"] == everything["total_fills"]

    def test_page_bounds_are_validated(self, client: TestClient, known_run: str) -> None:
        assert (
            client.get(f"/api/runs/{known_run}/trades", params={"page": 0}).status_code
            == 422
        )
        assert (
            client.get(
                f"/api/runs/{known_run}/trades", params={"page_size": 10_000}
            ).status_code
            == 422
        )

    def test_missing_events_is_an_explicit_empty_state(
        self, fixture_run_ids: list[str], runs_dir: Path, tmp_path: Path
    ) -> None:
        broken_root = tmp_path / "runs"
        shutil.copytree(runs_dir, broken_root)
        run_id = fixture_run_ids[0]
        (broken_root / run_id / "events.parquet").unlink()
        app = create_app(Settings(runs_root=broken_root, lake_root=tmp_path / "lake"))
        with TestClient(app) as client:
            response = client.get(f"/api/runs/{run_id}/trades")
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert "events.parquet" in payload["reason"]

    def test_unsupported_events_schema_is_rejected_with_a_reason(
        self, fixture_run_ids: list[str], runs_dir: Path, tmp_path: Path
    ) -> None:
        future_root = tmp_path / "runs"
        shutil.copytree(runs_dir, future_root)
        run_id = fixture_run_ids[0]
        target = future_root / run_id / "events.parquet"
        table = pq.read_table(target)
        bumped = table.set_column(
            table.schema.get_field_index("schema_version"),
            "schema_version",
            pa.array([99] * table.num_rows, type=pa.int64()),
        )
        pq.write_table(bumped, target)
        app = create_app(Settings(runs_root=future_root, lake_root=tmp_path / "lake"))
        with TestClient(app) as client:
            response = client.get(f"/api/runs/{run_id}/trades")
            listing = client.get("/api/runs").json()
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert "not supported" in payload["reason"]
        assert "[99]" in payload["reason"]
        listed = {run["run_id"]: run for run in listing["runs"]}[run_id]
        assert listed["schema_support"]["events_supported"] is False
        assert listed["schema_support"]["events_schema_versions"] == [99]

    def test_unknown_run_is_404(self, client: TestClient) -> None:
        assert client.get("/api/runs/does-not-exist/trades").status_code == 404

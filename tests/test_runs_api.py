"""Run endpoints over the real pulsar-core fixtures: list, equity, manifest.

Covers the runs side of the API plus the two reliability behaviours the
design fixes: missing artifacts are explicit empty states (never errors),
and responses over real artifacts return within seconds.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulsar_ui.server import create_app
from pulsar_ui.settings import Settings

SECONDS_BUDGET = 1.0  # "日线级全市场回测的 events 在预聚合后应秒级响应"


@pytest.fixture()
def known_run(fixture_run_ids: list[str]) -> str:
    assert fixture_run_ids, "committed run fixtures are missing"
    return fixture_run_ids[0]


class TestRunsList:
    def test_lists_every_fixture_run_with_metrics_summary(
        self, client: TestClient, fixture_run_ids: list[str]
    ) -> None:
        started = time.perf_counter()
        response = client.get("/api/runs")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < SECONDS_BUDGET, f"/api/runs took {elapsed:.3f}s"
        payload = response.json()
        assert payload["count"] == len(fixture_run_ids)
        assert [run["run_id"] for run in payload["runs"]] == sorted(
            fixture_run_ids, reverse=True
        )

        by_id = {run["run_id"]: run for run in payload["runs"]}
        for run_id in fixture_run_ids:
            run = by_id[run_id]
            assert run["mode"] == "research"
            assert run["start"] and run["end"]
            assert run["artifacts"] == {
                "manifest": True,
                "events": True,
                "metrics": True,
            }
            assert run["schema_support"]["manifest_supported"] is True
            assert run["schema_support"]["events_supported"] is True
            assert run["schema_support"]["metrics_supported"] is True
            metrics = run["metrics"]
            for key in (
                "trading_days",
                "total_return",
                "annual_return",
                "annual_volatility",
                "sharpe",
                "max_drawdown",
                "fills",
                "final_nav",
            ):
                assert key in metrics, f"metrics summary misses {key}"

    def test_fixture_runs_group_under_one_experiment(
        self, client: TestClient, fixture_run_ids: list[str]
    ) -> None:
        payload = client.get("/api/runs").json()
        experiment_ids = {run["experiment_id"] for run in payload["runs"]}
        assert experiment_ids == {"fixture-momentum"}
        assert len(payload["runs"]) == len(fixture_run_ids)

    def test_empty_runs_root_is_an_empty_list(self, tmp_path: Path) -> None:
        app = create_app(Settings(runs_root=tmp_path / "runs", lake_root=tmp_path / "lake"))
        with TestClient(app) as client:
            payload = client.get("/api/runs").json()
        assert payload == {"count": 0, "runs": []}


class TestEquity:
    def test_serves_the_report_curve_within_seconds(
        self, client: TestClient, known_run: str, runs_dir: Path
    ) -> None:
        started = time.perf_counter()
        response = client.get(f"/api/runs/{known_run}/equity")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < SECONDS_BUDGET
        payload = response.json()
        assert payload["available"] is True
        assert payload["source"] == "metrics_report.json"
        assert payload["downsampled"] is False

        report = json.loads((runs_dir / known_run / "metrics_report.json").read_text())
        assert payload["total_points"] == len(report["equity_curve"])
        assert payload["returned_points"] == payload["total_points"]
        assert payload["initial_cash"] == report["initial_cash"]
        first, last = payload["points"][0], payload["points"][-1]
        assert first["nav"] == pytest.approx(1.0)
        assert last["nav"] == pytest.approx(report["metrics"]["final_nav"])
        ts_sequence = [point["ts"] for point in payload["points"]]
        assert ts_sequence == sorted(ts_sequence)

    def test_downsamples_when_max_points_is_tight(
        self, client: TestClient, known_run: str
    ) -> None:
        payload = client.get(
            f"/api/runs/{known_run}/equity", params={"max_points": 5}
        ).json()
        assert payload["available"] is True
        assert payload["downsampled"] is True
        assert payload["returned_points"] <= 5
        # the curve's endpoint survives downsampling
        assert payload["points"][-1]["nav"] == pytest.approx(
            payload["points"][-1]["equity"] / payload["initial_cash"]
        )

    def test_missing_metrics_is_an_explicit_empty_state(
        self, client: TestClient, fixture_run_ids: list[str], runs_dir: Path, tmp_path: Path
    ) -> None:
        broken_root = tmp_path / "runs"
        shutil.copytree(runs_dir, broken_root)
        run_id = fixture_run_ids[0]
        (broken_root / run_id / "metrics_report.json").unlink()
        app = create_app(Settings(runs_root=broken_root, lake_root=tmp_path / "lake"))
        with TestClient(app) as client_broken:
            response = client_broken.get(f"/api/runs/{run_id}/equity")
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert "metrics_report.json" in payload["reason"]

    def test_unknown_run_is_404(self, client: TestClient) -> None:
        response = client.get("/api/runs/deadbeef00000000/equity")
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "run_not_found"


class TestManifest:
    def test_returns_the_manifest_verbatim(
        self, client: TestClient, known_run: str, runs_dir: Path
    ) -> None:
        raw = (runs_dir / known_run / "run_manifest.json").read_text(encoding="utf-8")
        document = json.loads(raw)
        started = time.perf_counter()
        response = client.get(f"/api/runs/{known_run}/manifest")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < SECONDS_BUDGET
        assert response.json() == document

    def test_unknown_run_is_404(self, client: TestClient) -> None:
        assert client.get("/api/runs/nope/manifest").status_code == 404

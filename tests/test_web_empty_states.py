"""Acceptance (U2): missing artifacts surface as explicit empty states.

The UI design's failure rule — "工件缺失显示明确空态而非报错" — is a
contract between the service and the frontend: this module constructs
degenerate run roots and asserts the payload shape each dashboard view
renders its empty state from (available=false + a human-readable reason),
never an error page or fabricated data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from pulsar_ui.server import create_app
from pulsar_ui.settings import Settings


def _client(runs_root: Path, lake_root: Path) -> TestClient:
    return TestClient(
        create_app(Settings(runs_root=runs_root, lake_root=lake_root, port=7800))
    )


def test_empty_runs_root_is_an_explicit_zero_run_state(tmp_path: Path) -> None:
    client = _client(tmp_path / "runs", tmp_path / "lake")
    payload = client.get("/api/runs").json()
    assert payload == {"count": 0, "runs": []}
    # the dashboard itself still loads over the empty workspace
    assert 'id="root"' in client.get("/trades").text


def test_run_directory_with_only_a_manifest_reports_missing_artifacts(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs"
    run_dir = runs / "bare-run"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "bare000000000001",
                "mode": "research",
                "seed": 1,
                "code_version": "test",
                "config": {},
            }
        ),
        encoding="utf-8",
    )
    client = _client(runs, tmp_path / "lake")

    payload = client.get("/api/runs").json()
    assert payload["count"] == 1
    run = payload["runs"][0]
    assert run["artifacts"] == {"manifest": True, "events": False, "metrics": False}

    equity = client.get("/api/runs/bare000000000001/equity").json()
    assert equity["available"] is False
    assert equity["reason"]

    trades = client.get("/api/runs/bare000000000001/trades").json()
    assert trades["available"] is False
    assert trades["reason"]

    manifest = client.get("/api/runs/bare000000000001/manifest").json()
    assert manifest["run_id"] == "bare000000000001"
    assert manifest["schema_version"] == 1


def test_run_with_unreadable_metrics_reports_reason_not_error(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run_dir = runs / "broken-run"
    run_dir.mkdir(parents=True)
    (run_dir / "metrics_report.json").write_text("{not json", encoding="utf-8")
    client = _client(runs, tmp_path / "lake")

    payload = client.get("/api/runs").json()
    assert payload["count"] == 1
    assert payload["runs"][0]["artifacts"]["metrics"] is False

    equity = client.get("/api/runs/broken-run/equity").json()
    assert equity["available"] is False
    assert "unreadable" in equity["reason"]


def test_factor_ic_empty_state_is_explicit_and_unfabricated(client: Any) -> None:
    payload = client.get("/api/factors/momentum_20/ic").json()
    assert payload["available"] is False
    assert payload["reason"]
    assert payload["ic_series"] == []
    assert payload["quantile_returns"] == []
    assert payload["ir"] is None
    # the frontend renders exactly these fields in its empty-state panel
    assert payload["checked_sources"]
    assert payload["pending"]


def test_missing_lake_is_an_explicit_unavailable_state(tmp_path: Path) -> None:
    client = _client(tmp_path / "runs", tmp_path / "nowhere-lake")
    payload = client.get("/api/lake/coverage").json()
    assert payload["available"] is False
    assert payload["reason"]
    assert payload["symbols"] == []
    assert payload["watermarks"]["available"] is False

    bars = client.get("/api/lake/bars/SH600000").json()
    assert bars["available"] is False
    assert bars["reason"]
    assert bars["bars"] == []

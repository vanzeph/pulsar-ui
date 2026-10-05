"""Factor IC endpoint: the honest empty state — no fabricated series.

Until the C3 artifacts extension publishes factor IC data, the endpoint
must answer with a clear unavailable state that names the missing source.
These tests pin that contract so it cannot silently regress into made-up
numbers.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def test_factor_ic_returns_explicit_empty_state(client: TestClient) -> None:
    response = client.get("/api/factors/momentum_20/ic")
    assert response.status_code == 200
    payload = response.json()
    assert payload["factor"] == "momentum_20"
    assert payload["available"] is False
    assert payload["ic_series"] == []
    assert payload["ir"] is None
    assert payload["quantile_returns"] == []
    # the state must point at the missing data source, not hide it
    reason = payload["reason"]
    assert "no factor IC data" in reason
    assert "C3" in reason
    assert any("events.parquet" in source for source in payload["checked_sources"])


def test_factor_ic_names_the_pending_extension(client: TestClient) -> None:
    payload = client.get("/api/factors/volatility_20/ic").json()
    assert "C3 artifacts extension" in payload["pending"]


def test_factor_name_is_validated(client: TestClient) -> None:
    response = client.get("/api/factors/..%2Fetc/ic")
    assert response.status_code in (404, 422)
    malformed = client.get("/api/factors/bad name/ic")
    assert malformed.status_code == 422
    assert malformed.json()["detail"]["error"] == "invalid_factor_name"


def test_any_factor_answers_consistently(client: TestClient, app: Any) -> None:
    from pulsar_ui.factors import factor_ic

    payload = factor_ic("range_20")
    assert payload["available"] is False
    assert payload == client.get("/api/factors/range_20/ic").json()

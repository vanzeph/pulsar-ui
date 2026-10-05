"""Acceptance: the API surface is GET-only — no write paths exist.

The UI design's read-only acceptance: "路由测试断言全部端点为 GET 且无写
路径；服务仅绑定 127.0.0.1". This module walks ``app.routes`` and asserts
the method set of every single route, then double-checks the wire by
sending write verbs to every /api path and expecting 405.
"""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
#: Starlette pairs HEAD with GET automatically; HEAD is the safe twin.
SAFE_METHODS = {"GET", "HEAD"}


def test_every_route_is_get_only(app: Any) -> None:
    routes = [route for route in app.routes if hasattr(route, "methods")]
    assert routes, "expected routes to inspect"
    for route in routes:
        methods = set(route.methods or ())
        assert methods <= SAFE_METHODS, (
            f"route {route.path} declares non-GET methods: {sorted(methods)}"
        )
        assert "GET" in methods, f"route {route.path} is not a GET route"
        assert not methods & WRITE_METHODS, (
            f"route {route.path} exposes write methods: {sorted(methods)}"
        )


def test_api_routes_are_the_designed_seven(app: Any) -> None:
    api_paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api")
    }
    assert api_paths == {
        "/api/runs",
        "/api/runs/{run_id}/equity",
        "/api/runs/{run_id}/trades",
        "/api/runs/{run_id}/manifest",
        "/api/factors/{name}/ic",
        "/api/lake/coverage",
        "/api/lake/bars/{symbol}",
    }


def test_write_verbs_are_rejected_on_every_api_path(app: Any, client: Any) -> None:
    api_paths = sorted(
        {
            route.path
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/api")
        }
    )
    concrete = [
        "/api/runs",
        "/api/runs/fe2ce6b1a85f1260/equity",
        "/api/runs/fe2ce6b1a85f1260/trades",
        "/api/runs/fe2ce6b1a85f1260/manifest",
        "/api/factors/momentum_20/ic",
        "/api/lake/coverage",
        "/api/lake/bars/SH600000",
    ]
    for path in concrete:
        assert any(path_template_covers(candidate, path) for candidate in api_paths), (
            f"probe path {path} is not covered by the declared routes"
        )
        for verb in sorted(WRITE_METHODS):
            response = getattr(client, verb.lower())(path)
            assert response.status_code == 405, (
                f"{verb} {path} -> {response.status_code}; write paths must not exist"
            )


def path_template_covers(template: str, path: str) -> bool:
    """Whether a FastAPI path template matches a concrete path (simple case)."""
    template_parts = template.strip("/").split("/")
    path_parts = path.strip("/").split("/")
    if len(template_parts) != len(path_parts):
        return False
    return all(
        part.startswith("{") or part == concrete
        for part, concrete in zip(template_parts, path_parts)
    )

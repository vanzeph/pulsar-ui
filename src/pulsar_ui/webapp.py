"""Static hosting of the built web dashboard (:mod:`pulsar_ui.webapp`).

The React+ECharts frontend lives in ``web/`` (source); its build output
is committed as package resources under ``pulsar_ui/static/`` and this
module mounts them at ``/`` so the service hosts the dashboard itself —
"前端源码构建后内嵌为包资源，服务启动即托管，无需独立前端部署".

The mount plays two rules from the UI design:

* SPA fallback — client-side routes (``/``, ``/trades``, ``/factors``,
  ``/lake``) answer ``index.html`` on direct navigation and refresh;
* reserved prefixes — anything under ``/api`` (and the docs endpoints)
  keeps its JSON 404 instead of an HTML page.

When the build output is absent (a source checkout without a web build)
the service still starts and ``/`` answers a JSON service index whose
``web`` block says exactly that: a missing UI is an explicit state, never
a crash. Rebuild with ``tools/build_web.sh``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

__all__ = ["SPAStaticFiles", "STATIC_DIR", "mount_web_app"]

#: Build output of ``web/`` (see ``tools/build_web.sh`` / ``web/vite.config.ts``).
STATIC_DIR = Path(__file__).parent / "static"

#: Paths that must never receive the SPA fallback.
_RESERVED_PREFIXES = ("/api",)

#: Path prefixes that belong to the service itself, not the dashboard.
_SERVICE_PREFIXES = ("/docs", "/openapi.json", "/redoc")


class SPAStaticFiles(StaticFiles):
    """Static files that fall back to ``index.html`` for client routes.

    A missing file surfaces either as a 404 response or as a raised
    ``HTTPException(404)`` depending on the Starlette version; both paths
    are intercepted here. Reserved prefixes keep their 404.
    """

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or self._should_keep_404(scope):
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and not self._should_keep_404(scope):
            response = await super().get_response("index.html", scope)
        return response

    @staticmethod
    def _should_keep_404(scope: dict[str, Any]) -> bool:
        request_path = scope.get("path", "")
        reserved = _RESERVED_PREFIXES + _SERVICE_PREFIXES
        return any(
            request_path == prefix or request_path.startswith(f"{prefix}/")
            for prefix in reserved
        )


def _service_index(web_available: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "service": "pulsar-ui",
        "read_only": True,
        "host": "127.0.0.1",
        "endpoints": [
            "/api/runs",
            "/api/runs/{run_id}/equity",
            "/api/runs/{run_id}/trades",
            "/api/runs/{run_id}/manifest",
            "/api/factors/{name}/ic",
            "/api/lake/coverage",
            "/api/lake/bars/{symbol}",
        ],
    }
    if web_available:
        payload["web"] = {
            "available": True,
            "mounted_at": "/",
            "routes": ["/", "/factors", "/trades", "/lake"],
        }
    else:
        payload["web"] = {
            "available": False,
            "reason": (
                "web dashboard build output not found under pulsar_ui/static; "
                "rebuild with tools/build_web.sh (npm ci && npm run build in web/)"
            ),
        }
    return payload


def mount_web_app(app: FastAPI) -> dict[str, Any]:
    """Host the built dashboard at ``/``, or the explicit no-build state.

    Returns the ``web`` block of the service index (for tests/logging).
    """
    index = STATIC_DIR / "index.html"
    if index.is_file():
        app.mount(
            "/",
            SPAStaticFiles(directory=str(STATIC_DIR), html=True),
            name="web",
        )
        return _service_index(True)["web"]

    @app.get("/", tags=["service"], include_in_schema=False)
    def service_index() -> dict[str, Any]:
        return _service_index(False)

    return _service_index(False)["web"]


def web_mount_note() -> str:
    """One-line status for logs/tests: is the dashboard mounted?"""
    mounted = (STATIC_DIR / "index.html").is_file()
    return "web: mounted at /" if mounted else "web: build output missing (API-only)"

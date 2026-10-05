"""Acceptance (U2): the built web dashboard is hosted by the service.

The UI design pins "web 目录：React+ECharts 源码，构建产物内嵌包资源"
and "服务启动即托管" — these tests assert the committed build output is
served at ``/``, the SPA fallback covers the four view routes, unknown
``/api`` paths keep their JSON 404, and the served bundle really contains
the four views with no external resource references (no CDN at runtime).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

VIEW_ROUTES = ("/", "/trades", "/factors", "/lake")

#: Chinese view titles shipped in the bundle; minification preserves
#: string literals, so each must appear in the built JS.
VIEW_MARKERS = ("回测对比", "因子分析", "交易分析", "数据可视化")


def _index_html(client: Any) -> str:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_web_assets_are_committed() -> None:
    from pulsar_ui.webapp import STATIC_DIR

    assert (STATIC_DIR / "index.html").is_file(), (
        "committed dashboard build output missing under pulsar_ui/static; "
        "run tools/build_web.sh and commit the result"
    )


def test_root_serves_the_spa_mount_point(client: Any) -> None:
    html = _index_html(client)
    assert 'id="root"' in html, "index.html must carry the React mount point #root"
    assert "Pulsar Dashboard" in html


def test_spa_fallback_serves_index_for_all_four_view_routes(client: Any) -> None:
    for route in VIEW_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.headers["content-type"].startswith("text/html"), route
        assert 'id="root"' in response.text, route


def test_unknown_api_path_keeps_json_404_not_html(client: Any) -> None:
    response = client.get("/api/definitely-not-an-endpoint")
    assert response.status_code == 404
    assert 'id="root"' not in response.text
    assert "Not Found" in response.text


def test_deep_unknown_page_falls_back_to_spa(client: Any) -> None:
    response = client.get("/some/deep/unknown/page")
    assert response.status_code == 200
    assert 'id="root"' in response.text


def test_write_verbs_on_spa_routes_are_rejected(client: Any) -> None:
    for verb in ("post", "put", "patch", "delete"):
        response = getattr(client, verb)("/trades")
        assert response.status_code == 405, (verb, response.status_code)


def test_index_references_only_local_assets(client: Any) -> None:
    html = _index_html(client)
    urls = re.findall(r'(?:src|href)="([^"]+)"', html)
    assert urls, "index.html references no assets?"
    for url in urls:
        assert url.startswith("/"), f"non-local asset reference: {url}"
        assert "://" not in url and not url.startswith("//"), (
            f"external asset reference violates the no-CDN baseline: {url}"
        )


def test_bundle_contains_all_four_views(client: Any) -> None:
    html = _index_html(client)
    scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    assert scripts, "index.html references no built JS bundle"
    bundle = "".join(client.get(script).text for script in scripts)
    for marker in VIEW_MARKERS:
        assert marker in bundle, f"view marker {marker!r} missing from built bundle"


def test_static_assets_served_with_content_types(client: Any) -> None:
    html = _index_html(client)
    for script in re.findall(r'src="(/assets/[^"]+)"', html):
        response = client.get(script)
        assert response.status_code == 200, script
        assert "javascript" in response.headers["content-type"], script
    for stylesheet in re.findall(r'href="(/assets/[^"]+\.css)"', html):
        response = client.get(stylesheet)
        assert response.status_code == 200, stylesheet
        assert "css" in response.headers["content-type"], stylesheet


def test_docs_still_served_alongside_the_dashboard(client: Any) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("route", VIEW_ROUTES)
def test_view_routes_survive_trailing_slash(client: Any, route: str) -> None:
    target = route if route == "/" else f"{route}/"
    response = client.get(target)
    assert response.status_code == 200
    assert 'id="root"' in response.text

"""Acceptance: the service binds 127.0.0.1 — and only 127.0.0.1.

The UI design makes the loopback boundary a hard constraint ("服务只监听
127.0.0.1，无公网暴露…此边界为硬约束"). These tests pin the boundary from
three sides: the module constant, the absence of any host parameter on the
serve path, and a real uvicorn bind that answers on the loopback interface.
"""

from __future__ import annotations

import inspect
import json
import threading
import time
import urllib.request
from typing import Any

import pytest
import uvicorn

from pulsar_ui import server as server_module
from pulsar_ui.settings import HOST, Settings


def test_host_constant_is_loopback() -> None:
    assert HOST == "127.0.0.1"


def test_serve_has_no_host_parameter() -> None:
    signature = inspect.signature(server_module.serve)
    assert "host" not in signature.parameters, (
        "serve() must not expose a host parameter — the loopback bind is a "
        "hard security baseline, not a knob"
    )


def test_main_has_no_host_argument() -> None:
    with pytest.raises(SystemExit) as excinfo:
        server_module.main(["--help"])
    assert excinfo.value.code == 0
    source = inspect.getsource(server_module.main)
    assert "--host" not in source


def test_serve_passes_loopback_host_to_uvicron(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    captured: dict[str, object] = {}

    def fake_uvicorn_run(app: Any, *, host: str, port: int) -> None:
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(uvicorn, "run", fake_uvicorn_run)
    server_module.serve(settings, port=7901)
    assert captured == {"host": "127.0.0.1", "port": 7901}


def test_real_bind_answers_on_loopback_only(app: Any, settings: Settings) -> None:
    """Start a live uvicorn server and confirm it serves on 127.0.0.1."""
    config = uvicorn.Config(app, host=HOST, port=0, log_level="warning")
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10.0
    port = None
    while time.monotonic() < deadline:
        if uvicorn_server.started:
            sockets = getattr(uvicorn_server, "servers", [])
            if sockets:
                port = sockets[0].sockets[0].getsockname()[1]
                break
        time.sleep(0.05)
    assert port is not None, "uvicorn did not start within 10s"

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/runs", timeout=5) as response:
        assert response.status == 200
        payload = json.loads(response.read().decode("utf-8"))
    assert payload["count"] >= 1

    # the listening socket must be bound to the loopback address, nothing wider
    for server_socket in uvicorn_server.servers:
        for sock in server_socket.sockets:
            assert sock.getsockname()[0] == "127.0.0.1"

    uvicorn_server.should_exit = True
    thread.join(timeout=10.0)

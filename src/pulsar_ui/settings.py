"""Service settings: where to read, where to listen — and nothing else.

Two environment variables steer discovery (no config files, no database):

* ``PULSAR_UI_RUNS_DIR`` — root containing one sub-directory per run
  (each holding the three contract artifacts ``run_manifest.json``,
  ``events.parquet``, ``metrics_report.json``). Default: ``./runs``.
* ``PULSAR_UI_LAKE_DIR`` — root of the local data lake
  (``bars_1d/symbol=.../year=.../part.parquet`` + ``_meta/watermarks.parquet``).
  Default: ``./lake``.
* ``PULSAR_UI_PORT`` — the port to listen on. Default: ``7800``.

The listen host is **not** configurable: the service binds 127.0.0.1 only
(:data:`HOST`, a hard security baseline from the UI design — "服务只监听
127.0.0.1，无公网暴露；本机单用户前提下不做鉴权，此边界为硬约束").
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = ["DEFAULT_PORT", "HOST", "Settings"]

#: The only address this service may ever listen on. A module constant on
#: purpose: there is no code path that could widen it to 0.0.0.0.
HOST = "127.0.0.1"

#: Default listen port (the dashboard's documented local address).
DEFAULT_PORT = 7800


@dataclass(frozen=True)
class Settings:
    """Resolved read locations plus the (port-only) listen configuration."""

    runs_root: Path
    lake_root: Path
    port: int = DEFAULT_PORT

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        """Build settings from the environment (``os.environ`` by default)."""
        source = os.environ if env is None else env
        runs = Path(source.get("PULSAR_UI_RUNS_DIR", "runs"))
        lake = Path(source.get("PULSAR_UI_LAKE_DIR", "lake"))
        raw_port = source.get("PULSAR_UI_PORT", str(DEFAULT_PORT))
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError(f"PULSAR_UI_PORT must be an integer, got {raw_port!r}") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"PULSAR_UI_PORT must be within 1..65535, got {port}")
        return cls(runs_root=runs, lake_root=lake, port=port)

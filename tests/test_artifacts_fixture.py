"""Authenticity of the committed fixtures against the real pulsar-core reader.

Skipped wherever pulsar-core is not importable (CI, fresh checkouts): the
committed artifacts are the contract samples, and this cross-check only
runs in workspaces that have the producer installed. It asserts the
fixture events.parquet parses through ``pulsar_core.read_event_archive``
— i.e. what the UI reads is exactly what the engine wrote.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pulsar_core = pytest.importorskip("pulsar_core")

from pulsar_core import (
    MANIFEST_FILENAME,
    METRICS_FILENAME,
    load_manifest,
    load_metrics_report,
    read_event_archive,
)

FIXTURE_RUNS = Path(__file__).parent / "fixtures" / "runs"


def test_every_fixture_run_round_trips_through_the_real_reader() -> None:
    run_dirs = sorted(path for path in FIXTURE_RUNS.iterdir() if path.is_dir())
    assert run_dirs, "committed run fixtures are missing"
    for directory in run_dirs:
        manifest = load_manifest(directory / MANIFEST_FILENAME)
        assert manifest.run_id == directory.name

        report = load_metrics_report(directory / METRICS_FILENAME)
        assert report.run_id == manifest.run_id

        events = read_event_archive(directory / "events.parquet")
        assert len(events) == pq_rows(directory / "events.parquet")
        assert any(event.execution is not None for event in events)


def pq_rows(path: Path) -> int:
    import pyarrow.parquet as pq

    return pq.read_table(path).num_rows


def test_metrics_json_matches_the_report_model(tmp_path: Path) -> None:
    """The committed JSON stays parseable by the producer's model loader."""
    for directory in sorted(path for path in FIXTURE_RUNS.iterdir() if path.is_dir()):
        report = load_metrics_report(directory / METRICS_FILENAME)
        raw = json.loads((directory / METRICS_FILENAME).read_text(encoding="utf-8"))
        assert raw == json.loads(report.to_json())

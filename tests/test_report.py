"""Static report generator tests (U3).

Coverage required by the task:
- fixture-artifact reports assert key content (metric values, chart
  elements, manifest summary, trades rows);
- self-containment (no external URLs, no script/link tags, offline-open
  simulation via parsing);
- schema_version mismatch produces an explicit error page;
- the ``python -m pulsar_ui.report`` CLI works end to end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from pulsar_ui.report import REPORT_FILENAME, ReportInputError, generate_report

FIXTURES = Path(__file__).parent / "fixtures" / "runs"
RUN_ID = "56659226cb264ae5"
JOURNAL_DIGEST = "82996b79abbcdabf0261652436f3f49c2f183de6de7efd9911d3c64e90ea52fc"
SRC_ROOT = Path(__import__("pulsar_ui").__file__).resolve().parent.parent


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    target = tmp_path / "run"
    shutil.copytree(FIXTURES / RUN_ID, target)
    return target


def generate(run: Path) -> str:
    target = generate_report(run)
    assert target == run / REPORT_FILENAME
    return target.read_text(encoding="utf-8")


# -- key content from the U1/C5-semantics fixture artifacts ------------------


def test_report_key_metrics_table(run_dir: Path) -> None:
    page = generate(run_dir)
    assert RUN_ID in page
    # headline metric values as formatted by the report
    assert "3.21%" in page  # total_return 0.0320985
    assert "48.90%" in page  # annual_return 0.4889717
    assert "5.01%" in page  # annual_volatility 0.0500878
    assert "0.60%" in page  # max_drawdown 0.0060101
    assert "7.98" in page  # sharpe 7.977797
    assert "1.0321" in page  # final_nav 1.0320985
    assert "103,209.85" in page  # final_equity
    # fee attribution block
    assert "费用合计" in page
    assert "佣金" in page


def test_report_embeds_inline_svg_charts(run_dir: Path) -> None:
    page = generate(run_dir)
    assert 'id="nav-chart"' in page
    assert 'id="drawdown-chart"' in page
    assert page.count("<polyline") == 2  # one per chart, both inline
    assert "<title>净值曲线" in page
    assert "<title>回撤曲线" in page


def test_report_manifest_summary(run_dir: Path) -> None:
    page = generate(run_dir)
    assert "RunManifest 摘要" in page
    assert "fixture-momentum" in page  # experiment id
    assert "round_trip" in page  # strategy name
    assert "31801cb" in page  # code_version
    assert "bar_replay" in page  # session kind
    assert ">23<" in page  # seed as its own cell
    assert "600000" in page  # symbol
    assert "2026-06-01" in page and "2026-06-26" in page  # session span
    assert "bars/1d/600000" in page  # data watermark row


def test_report_trades_table(run_dir: Path) -> None:
    page = generate(run_dir)
    assert "逐笔成交" in page
    assert "96.3431" in page  # buy fill price
    assert "102.7628" in page  # sell fill price
    assert "买入" in page and "卖出" in page
    assert JOURNAL_DIGEST in page  # events archive digest


# -- self-containment / offline-open simulation ------------------------------


class _ExternalRefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.external_refs: list[tuple[str, str, str]] = []
        self.tags: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        for name, value in attrs:
            if name in ("src", "href", "xlink:href") and value:
                self.external_refs.append((tag, name, value))


def test_report_is_self_contained(run_dir: Path) -> None:
    page = generate(run_dir)
    # no fetchable URL text anywhere (including no xmlns namespace URIs)
    assert "http://" not in page
    assert "https://" not in page
    assert "xmlns" not in page
    # no script or stylesheet machinery at all
    assert "<script" not in page
    assert "<link" not in page
    # offline-open simulation: parse and confirm nothing references outside
    collector = _ExternalRefCollector()
    collector.feed(page)
    assert collector.external_refs == []
    assert "script" not in collector.tags
    assert "link" not in collector.tags
    assert "svg" in collector.tags


def test_all_fixture_runs_generate_self_contained_reports(tmp_path: Path) -> None:
    for source in sorted(path for path in FIXTURES.iterdir() if path.is_dir()):
        run = tmp_path / source.name
        shutil.copytree(source, run)
        page = generate(run)
        assert "http://" not in page and "https://" not in page
        assert 'id="nav-chart"' in page
        assert 'id="drawdown-chart"' in page


# -- schema_version mismatch → explicit error page ----------------------------


def _patch_json(path: Path, mutate) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def test_schema_mismatch_metrics_produces_error_page(run_dir: Path) -> None:
    _patch_json(run_dir / "metrics_report.json", lambda doc: doc.update(schema_version=2))
    page = generate(run_dir)
    assert "Schema 版本不匹配" in page
    assert "metrics_report.json" in page
    assert "v2" in page
    assert "v1" in page  # supported version stated
    # no half-parsed data on the error page
    assert 'id="nav-chart"' not in page
    assert "<polyline" not in page
    assert "7.98" not in page
    assert "fixture-momentum" not in page


def test_schema_mismatch_manifest_produces_error_page(run_dir: Path) -> None:
    _patch_json(run_dir / "run_manifest.json", lambda doc: doc.update(schema_version=99))
    page = generate(run_dir)
    assert "Schema 版本不匹配" in page
    assert "run_manifest.json" in page
    assert "v99" in page
    assert "<polyline" not in page


def test_schema_mismatch_events_produces_error_page(run_dir: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    target = run_dir / "events.parquet"
    table = pq.read_table(target)
    index = table.schema.get_field_index("schema_version")
    table = table.set_column(index, "schema_version", pa.array([2] * table.num_rows, pa.int64()))
    pq.write_table(table, target)
    page = generate(run_dir)
    assert "Schema 版本不匹配" in page
    assert "events.parquet" in page
    assert "v2" in page
    assert "<polyline" not in page
    assert "96.3431" not in page


# -- missing artifacts render explicit empty states, not errors ---------------


def test_missing_events_renders_explicit_empty_state(run_dir: Path) -> None:
    (run_dir / "events.parquet").unlink()
    page = generate(run_dir)
    assert "逐笔成交不可用" in page
    assert "7.98" in page  # metrics still rendered
    assert 'id="nav-chart"' in page  # curves still rendered


def test_missing_metrics_renders_explicit_empty_state(run_dir: Path) -> None:
    (run_dir / "metrics_report.json").unlink()
    page = generate(run_dir)
    assert "关键指标不可用" in page
    assert "净值曲线不可用" in page
    assert "RunManifest 摘要" in page
    assert "600000" in page  # manifest section intact


# -- input errors -------------------------------------------------------------


def test_generate_report_requires_real_run_dir(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ReportInputError):
        generate_report(empty)
    with pytest.raises(ReportInputError):
        generate_report(tmp_path / "does-not-exist")


# -- CLI: python -m pulsar_ui.report <run_dir> --------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(SRC_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "pulsar_ui.report", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_generates_report(tmp_path: Path) -> None:
    run = tmp_path / "run"
    shutil.copytree(FIXTURES / RUN_ID, run)
    proc = _run_cli(str(run))
    assert proc.returncode == 0, proc.stderr
    target = run / REPORT_FILENAME
    assert target.is_file()
    assert str(target) in proc.stdout
    page = target.read_text(encoding="utf-8")
    assert "7.98" in page
    assert "http://" not in page and "https://" not in page


def test_cli_custom_output_path(tmp_path: Path) -> None:
    run = tmp_path / "run"
    shutil.copytree(FIXTURES / RUN_ID, run)
    out = tmp_path / "elsewhere" / "report.html"
    out.parent.mkdir()
    proc = _run_cli(str(run), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    assert not (run / REPORT_FILENAME).exists()


def test_cli_rejects_directory_without_artifacts(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = _run_cli(str(empty))
    assert proc.returncode == 2
    assert "报告生成失败" in proc.stderr

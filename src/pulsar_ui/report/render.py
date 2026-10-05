"""HTML document assembly for the static report.

Pure string templating: styles live in one inline ``<style`` block, charts
are inline SVG, and the whole document references no external resource —
no ``<script``/``<link`` tags, no external URLs, no XML namespace URIs —
so it opens offline with a double-click. Every dynamic text fragment is
HTML-escaped exactly once on its way into the document.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .charts import Point, line_chart

__all__ = ["ReportData", "render_error_page", "render_report"]

_CSS = """
:root{--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#1d4ed8;
--bad:#b91c1c;--ok:#047857;--card:#fff;--bg:#f5f6f8}
*{box-sizing:border-box}
body{margin:0;padding:32px 16px 48px;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
"Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:980px;margin:0 auto}
header.page h1{margin:0 0 4px;font-size:24px}
.page-meta{color:var(--muted);font-size:13px;margin:0}
section.card{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:18px 20px;margin:18px 0}
section.card>h2{margin:0 0 12px;font-size:17px;border-bottom:1px solid var(--line);
padding-bottom:8px}
h3.sub{font-size:13.5px;color:var(--muted);margin:16px 0 6px;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tbody tr:nth-child(even) td{background:#fafafa}
.badges{display:flex;flex-wrap:wrap;gap:8px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12.5px;
border:1px solid var(--line);background:#fff}
.badge.ok{color:var(--ok);border-color:#a7f3d0;background:#ecfdf5}
.badge.miss{color:#92400e;border-color:#fde68a;background:#fffbeb}
.empty{color:var(--muted);font-size:14px;margin:6px 0}
.chart{width:100%;height:auto;display:block;margin-top:6px}
.chart-meta{color:var(--muted);font-size:13px;margin:0 0 4px}
.chart .grid{stroke:var(--line);stroke-width:1}
.chart .axis{stroke:#9ca3af;stroke-width:1}
.chart .zero{stroke:#9ca3af;stroke-width:1;stroke-dasharray:4 4}
.chart .tick{fill:var(--muted);font-size:12px}
.chart .tick.last{fill:var(--ink);font-weight:600}
td.side-buy{color:var(--bad);font-weight:600}
td.side-sell{color:var(--ok);font-weight:600}
code{background:#f3f4f6;padding:1px 5px;border-radius:4px;font-size:13px}
footer{color:var(--muted);font-size:12.5px;margin-top:28px;line-height:1.7}
section.error-card{border-color:#fecaca;background:#fef2f2}
section.error-card h2{color:var(--bad);border-bottom-color:#fecaca}
@media print{body{background:#fff;padding:0}section.card{border:none}}
"""

#: Curated headline metrics (label order for the key-metrics table).
_METRIC_ORDER: tuple[tuple[str, str], ...] = (
    ("total_return", "总收益"),
    ("annual_return", "年化收益"),
    ("annual_volatility", "年化波动"),
    ("max_drawdown", "最大回撤"),
    ("sharpe", "Sharpe"),
    ("final_nav", "期末净值"),
    ("final_equity", "期末权益（元）"),
    ("fills", "成交笔数"),
    ("trading_days", "交易天数"),
    ("turnover_ratio", "换手率"),
    ("turnover_annualized", "年化换手"),
    ("turnover_value", "成交额（元）"),
    ("buy_value", "买入金额（元）"),
    ("sell_value", "卖出金额（元）"),
)

#: Ratio-valued metric keys rendered as percentages.
_PCT_KEYS = {"total_return", "annual_return", "annual_volatility", "max_drawdown", "turnover_ratio"}
_NAV_KEYS = {"final_nav"}

#: Fee attribution labels (metrics_report.json ``fee_attribution`` block).
_FEE_ORDER: tuple[tuple[str, str], ...] = (
    ("total", "费用合计（元）"),
    ("commission", "佣金（元）"),
    ("stamp_duty", "印花税（元）"),
    ("transfer_fee", "过户费（元）"),
    ("slippage", "滑点成本（元）"),
    ("drag_total", "费用总拖累（元）"),
    ("drag_commission", "佣金拖累（元）"),
    ("drag_stamp_duty", "印花税拖累（元）"),
    ("drag_transfer_fee", "过户费拖累（元）"),
    ("drag_slippage", "滑点拖累（元）"),
    ("fills", "计费成交笔数"),
)

_SIDE_LABELS = {"buy": ("买入", "side-buy"), "sell": ("卖出", "side-sell")}


@dataclass(frozen=True)
class ReportData:
    """Everything the renderer needs for one run's report page."""

    run_id: str
    directory: Path
    generated_at: str
    artifact_status: tuple[tuple[str, str, bool], ...]
    manifest: dict[str, Any] | None = None
    manifest_note: str | None = None
    metrics: dict[str, Any] | None = None
    metrics_note: str | None = None
    initial_cash: float | None = None
    span_start: str | None = None
    span_end: str | None = None
    nav_series: list[Point] = field(default_factory=list)
    dd_series: list[Point] = field(default_factory=list)
    curve_total: int = 0
    curve_shown: int = 0
    curve_downsampled: bool = False
    fills: list[dict[str, Any]] = field(default_factory=list)
    fills_total: int | None = None
    fills_note: str | None = None
    fee_attribution: dict[str, Any] | None = None
    journal_digest: str | None = None


# -- small formatting helpers ------------------------------------------------


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_metric(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        if key in _PCT_KEYS:
            return f"{value * 100:.2f}%"
        if key in _NAV_KEYS:
            return f"{value:.4f}"
        if isinstance(value, int):
            return f"{value:,}"
        return f"{value:,.2f}"
    return str(value)


def _generic_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(_generic_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _pair_table(rows: list[tuple[str, str]]) -> str:
    """Two label/value pairs per row (four cells) — compact key tables."""
    if not rows:
        return '<p class="empty">无数据</p>'
    body = []
    for start in range(0, len(rows), 2):
        cells = "".join(
            f"<th>{_esc(label)}</th><td class=\"num\">{_esc(value)}</td>"
            for label, value in rows[start : start + 2]
        )
        body.append(f"<tr>{cells}</tr>")
    return f"<table><tbody>{''.join(body)}</tbody></table>"


def _section(section_id: str, heading: str, body: str, *, error: bool = False) -> str:
    cls = "card error-card" if error else "card"
    return (
        f'<section class="{cls}" id="{section_id}">\n<h2>{_esc(heading)}</h2>\n'
        f"{body}\n</section>\n"
    )


def _document(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        '<meta name="generator" content="pulsar-ui static report">\n'
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n"
        f'<div class="wrap">\n{body}</div>\n</body>\n</html>\n'
    )


# -- section builders --------------------------------------------------------


def _badge(filename: str, text: str, ok: bool) -> str:
    state = "ok" if ok else "miss"
    return f'<span class="badge {state}">{_esc(filename)} · {_esc(text)}</span>'


def _manifest_section(data: ReportData) -> str:
    if data.manifest is None:
        body = (
            '<p class="empty">RunManifest 不可用：'
            f"{_esc(data.manifest_note or 'run_manifest.json 缺失')}</p>"
        )
        return _section("manifest-summary", "RunManifest 摘要", body)
    manifest = data.manifest
    config = manifest.get("config") if isinstance(manifest.get("config"), dict) else {}
    experiment = config.get("experiment") if isinstance(config.get("experiment"), dict) else {}
    session = config.get("session") if isinstance(config.get("session"), dict) else {}
    strategy = config.get("strategy") if isinstance(config.get("strategy"), dict) else {}

    rows = [
        ("运行 ID", str(manifest.get("run_id", data.run_id))),
        ("清单 schema", f"v{manifest.get('schema_version')}" if "schema_version" in manifest else "—"),
        ("模式", _generic_value(manifest.get("mode")) if "mode" in manifest else "—"),
        ("随机种子", _generic_value(manifest.get("seed")) if "seed" in manifest else "—"),
        ("代码版本", _generic_value(manifest.get("code_version")) if "code_version" in manifest else "—"),
    ]
    if "created_at" in manifest:
        rows.append(("生成时间", _generic_value(manifest["created_at"])))
    if "experiment" in config and experiment:
        rows.append(("实验 ID", _generic_value(experiment.get("id"))))
        if "name" in experiment:
            rows.append(("实验名称", _generic_value(experiment["name"])))
    if "session" in config and session:
        rows.append(("会话类型", _generic_value(session.get("kind"))))
        rows.append(("频率", _generic_value(session.get("freq"))))
        rows.append(("回放起点", _generic_value(session.get("start"))))
        rows.append(("回放终点", _generic_value(session.get("end"))))
        if "adjust" in session:
            rows.append(("复权", _generic_value(session["adjust"])))
        if "symbols" in session:
            rows.append(("标的", _generic_value(session["symbols"])))
    if "name" in strategy:
        rows.append(("策略", _generic_value(strategy["name"])))

    handled = {"run_id", "schema_version", "mode", "seed", "code_version", "created_at", "config", "data_watermarks"}
    for key in sorted(set(manifest) - handled):
        rows.append((key, _generic_value(manifest[key])))

    body = _pair_table(rows)
    watermarks = manifest.get("data_watermarks")
    if isinstance(watermarks, dict) and watermarks:
        wm_rows = "".join(
            f"<tr><td>{_esc(name)}</td><td>{_esc(when)}</td></tr>"
            for name, when in sorted(watermarks.items())
        )
        body += (
            '<h3 class="sub">数据水位（data_watermarks）</h3>'
            "<table><thead><tr><th>数据集</th><th>水位时间</th></tr></thead>"
            f"<tbody>{wm_rows}</tbody></table>"
        )
    return _section("manifest-summary", "RunManifest 摘要", body)


def _metrics_section(data: ReportData) -> str:
    if data.metrics is None:
        body = (
            '<p class="empty">关键指标不可用：'
            f"{_esc(data.metrics_note or 'metrics_report.json 缺失')}</p>"
        )
        return _section("metrics", "关键指标", body)
    metrics = data.metrics
    known = dict(_METRIC_ORDER)
    rows = [(label, _fmt_metric(key, metrics[key])) for key, label in _METRIC_ORDER if key in metrics]
    rows += [
        (key, _fmt_metric(key, metrics[key])) for key in sorted(set(metrics) - set(known))
    ]
    return _section("metrics", "关键指标", _pair_table(rows))


def _nav_section(data: ReportData, span: str) -> str:
    if len(data.nav_series) < 2:
        body = '<p class="empty">净值曲线不可用：metrics 报告未携带可用的 equity_curve</p>'
        return _section("nav-chart-section", "净值曲线", body)
    meta = [f"共 {data.curve_total} 个净值点（含起点）"]
    if data.curve_downsampled:
        meta.append(f"已降采样至 {data.curve_shown} 点（每桶保留末值）")
    if data.initial_cash is not None:
        meta.append(f"期初资金 {_money(data.initial_cash)} 元")
    chart = line_chart(
        data.nav_series,
        chart_id="nav-chart",
        title=f"净值曲线（{span or data.run_id}）",
        value_kind="nav",
        color="#1d4ed8",
    )
    body = f'<p class="chart-meta">{_esc("；".join(meta))}</p>\n{chart}'
    return _section("nav-chart-section", "净值曲线", body)


def _dd_section(data: ReportData, span: str) -> str:
    if len(data.dd_series) < 2:
        body = '<p class="empty">回撤曲线不可用：metrics 报告未携带可用的 equity_curve</p>'
        return _section("drawdown-chart-section", "回撤曲线", body)
    chart = line_chart(
        data.dd_series,
        chart_id="drawdown-chart",
        title=f"回撤曲线（{span or data.run_id}）",
        value_kind="pct",
        color="#b91c1c",
        area=True,
    )
    body = (
        '<p class="chart-meta">按净值运行峰值计算：回撤 = 净值 ÷ 峰值 − 1，负值越深回撤越大</p>\n'
        + chart
    )
    return _section("drawdown-chart-section", "回撤曲线", body)


def _fees_section(data: ReportData) -> str:
    if not data.fee_attribution:
        body = '<p class="empty">费用归因不可用：metrics 报告未携带 fee_attribution</p>'
        return _section("fees", "费用归因", body)
    fees = data.fee_attribution
    known = dict(_FEE_ORDER)
    rows = [(label, _fmt_metric(key, fees[key])) for key, label in _FEE_ORDER if key in fees]
    rows += [(key, _fmt_metric(key, fees[key])) for key in sorted(set(fees) - set(known))]
    return _section("fees", "费用归因", _pair_table(rows))


def _trades_section(data: ReportData) -> str:
    if data.fills_total is None:
        body = f'<p class="empty">逐笔成交不可用：{_esc(data.fills_note or "events.parquet 缺失")}</p>'
        return _section("trades", "逐笔成交", body)
    if not data.fills:
        body = '<p class="empty">该 run 没有成交记录</p>'
    else:
        head = (
            "<table><thead><tr><th>seq</th><th>时间</th><th>标的</th><th>方向</th>"
            '<th class="num">价格</th><th class="num">数量</th><th class="num">佣金</th>'
            '<th class="num">印花税</th><th class="num">过户费</th>'
            '<th class="num">费用合计</th></tr></thead><tbody>'
        )
        rows = []
        for fill in data.fills:
            label, side_cls = _SIDE_LABELS.get(str(fill.get("side")), (str(fill.get("side")), ""))
            price = fill.get("price")
            quantity = fill.get("quantity")
            fee_cells = []
            for name in ("commission", "stamp_duty", "transfer_fee", "fees_total"):
                value = fill.get(name)
                fee_cells.append("—" if value is None else f"{value:,.2f}")
            rows.append(
                "<tr>"
                f"<td>{_esc(fill.get('seq'))}</td>"
                f"<td>{_esc(fill.get('ts'))}</td>"
                f"<td>{_esc(fill.get('symbol'))}</td>"
                f'<td class="{side_cls}">{_esc(label)}</td>'
                f'<td class="num">{"—" if price is None else f"{price:,.4f}"}</td>'
                f'<td class="num">{"—" if quantity is None else f"{quantity:,}"}</td>'
                + "".join(f'<td class="num">{_esc(cell)}</td>' for cell in fee_cells)
                + "</tr>"
            )
        body = head + "".join(rows) + "</tbody></table>"
    if data.fills_note:
        body += f'<p class="empty">{_esc(data.fills_note)}</p>'
    if data.journal_digest:
        body += (
            '<p class="empty">事件存档摘要（journal_digest）：'
            f"<code>{_esc(data.journal_digest)}</code></p>"
        )
    return _section("trades", "逐笔成交", body)


_FOOTER = (
    "<footer>\n"
    "<p>自包含静态报告：数据与图全部内嵌，无脚本、无外部依赖，双击即看、可离线分享。</p>\n"
    "<p>由 pulsar-ui 静态报告生成器产出，与看板读取同一套 run 工件；重新生成："
    "<code>python -m pulsar_ui.report &lt;run_dir&gt;</code></p>\n"
    "</footer>\n"
)


# -- public renderers --------------------------------------------------------


def render_report(data: ReportData) -> str:
    """The full self-contained HTML document for one healthy run."""
    span = ""
    if data.span_start and data.span_end:
        span = f"{data.span_start[:10]} ~ {data.span_end[:10]}"
    header = (
        '<header class="page">\n<h1>Pulsar 回测报告</h1>\n'
        f'<p class="page-meta">{_esc(data.run_id)}'
        + (f" · {_esc(span)}" if span else "")
        + f" · 生成于 {_esc(data.generated_at)} · 工件目录 {_esc(data.directory)}</p>\n"
        "</header>\n"
    )
    badges = "".join(_badge(name, text, ok) for name, text, ok in data.artifact_status)
    artifacts = _section(
        "artifact-status", "工件状态", f'<div class="badges">{badges}</div>'
    )
    body = (
        header
        + artifacts
        + _manifest_section(data)
        + _metrics_section(data)
        + _nav_section(data, span)
        + _dd_section(data, span)
        + _fees_section(data)
        + _trades_section(data)
        + _FOOTER
    )
    return _document(f"Pulsar 回测报告 · {data.run_id}", body)


def render_error_page(
    *,
    run_dir: Path,
    generated_at: str,
    mismatches: list[tuple[str, object, int]],
    missing: list[tuple[str, str]],
) -> str:
    """The explicit error page for schema_version mismatches.

    按契约语义，版本不匹配绝不输出半解析数据：本页只陈述事实（哪个
    工件、发现版本、生成器支持的版本）与恢复动作。
    """

    def found_text(found: object) -> str:
        if found is None:
            return "缺失/未知"
        if isinstance(found, list):
            return "v" + "/".join(str(item) for item in found) if found else "未知"
        return f"v{found}"

    rows = "".join(
        f"<tr><td>{_esc(name)}</td><td class=\"num\">{_esc(found_text(found))}</td>"
        f'<td class="num">v{supported}</td></tr>'
        for name, found, supported in mismatches
    )
    body = (
        "<p>该 run 工件的契约版本（schema_version）与报告生成器实现不一致，"
        "报告内容未生成——不为版本不匹配的工件输出半解析数据。</p>\n"
        "<table><thead><tr><th>工件</th><th class=\"num\">发现版本</th>"
        '<th class="num">生成器支持</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>\n"
        "<p>恢复动作：升级 pulsar-ui 至支持该 schema 版本的版本后，对该 run 目录"
        "重新执行 <code>python -m pulsar_ui.report &lt;run_dir&gt;</code>。</p>\n"
    )
    if missing:
        items = "".join(f"<li>{_esc(name)}：{_esc(reason)}</li>" for name, reason in missing)
        body += f"<p>同时缺失的工件（仅提示，非本次失败原因）：</p><ul>{items}</ul>"
    header = (
        '<header class="page">\n<h1>Pulsar 静态报告 · 生成失败</h1>\n'
        f'<p class="page-meta">Schema 版本不匹配 · 生成于 {_esc(generated_at)} · '
        f"工件目录 {_esc(run_dir)}</p>\n</header>\n"
    )
    section = _section("schema-error", "Schema 版本不匹配", body, error=True)
    return _document("Pulsar 静态报告 · 生成失败（Schema 版本不匹配）", header + section + _FOOTER)

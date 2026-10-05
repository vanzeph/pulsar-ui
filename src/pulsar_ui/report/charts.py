"""Inline-SVG chart builders for the static report.

The report's self-containment baseline (设计文档：数据与图全部内嵌、无外
部依赖、双击离线可开) lands here: every chart is deterministic
string-built SVG — no charting library, no script, no XML-namespace URI —
so the finished document contains no external URL of any kind, not even a
fetchable-looking one.
"""

from __future__ import annotations

import html
from typing import Sequence

__all__ = ["line_chart"]

#: One ``(label, value)`` point; the label is the point's timestamp.
Point = tuple[str, float]

_WIDTH = 860
_HEIGHT = 280
_LEFT = 68
_RIGHT = 24
_TOP = 34
_BOTTOM = 44

_Y_TICKS = 5
_X_TICKS = 6

#: Y tick formats per value kind: nav levels, percentages, plain money.
_FORMATS = {
    "nav": "{:.4f}".format,
    "pct": lambda value: f"{value * 100:.2f}%",
    "num": "{:,.2f}".format,
}


def _text(
    x: float, y: float, content: str, *, anchor: str = "start", cls: str = ""
) -> str:
    class_attr = f' class="{cls}"' if cls else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{class_attr}>'
        f"{html.escape(content, quote=True)}</text>"
    )


def _x_tick_indices(count: int) -> list[int]:
    if count <= 1:
        return [0]
    wanted = min(_X_TICKS, count)
    return sorted({round(i * (count - 1) / (wanted - 1)) for i in range(wanted)})


def line_chart(
    series: Sequence[Point],
    *,
    chart_id: str,
    title: str,
    value_kind: str = "num",
    color: str = "#1d4ed8",
    area: bool = False,
) -> str:
    """Render one line chart as a standalone inline ``<svg>`` element.

    ``area=True`` shades the space between the curve and the zero baseline
    (the drawdown presentation); the y domain is then clamped so zero is
    the natural top edge. The x axis is index-based (equal spacing), which
    is honest for daily equity points and keeps rendering deterministic.
    """
    count = len(series)
    if count == 0:
        return ""
    format_y = _FORMATS[value_kind]

    plot_w = _WIDTH - _LEFT - _RIGHT
    plot_h = _HEIGHT - _TOP - _BOTTOM
    values = [value for _, value in series]
    vmin, vmax = min(values), max(values)
    if area:
        vmax = max(vmax, 0.0)
    domain = vmax - vmin
    pad = domain * 0.08 if domain > 0 else max(abs(vmax) * 0.05, 0.5)
    ymin, ymax = vmin - pad, vmax + pad

    def x_at(index: int) -> float:
        return _LEFT + (plot_w * index / (count - 1) if count > 1 else plot_w / 2)

    def y_at(value: float) -> float:
        return _TOP + plot_h * (1 - (value - ymin) / (ymax - ymin))

    parts = [
        f'<svg id="{html.escape(chart_id, quote=True)}" class="chart" '
        f'viewBox="0 0 {_WIDTH} {_HEIGHT}" role="img" '
        f'aria-label="{html.escape(title, quote=True)}">',
        f"<title>{html.escape(title, quote=True)}</title>",
        # axis frame
        f'<line class="axis" x1="{_LEFT}" y1="{_TOP}" x2="{_LEFT}" y2="{_HEIGHT - _BOTTOM}"/>',
        f'<line class="axis" x1="{_LEFT}" y1="{_HEIGHT - _BOTTOM}" '
        f'x2="{_WIDTH - _RIGHT}" y2="{_HEIGHT - _BOTTOM}"/>',
    ]

    # horizontal grid lines with y tick labels
    for tick in range(_Y_TICKS):
        value = ymin + (ymax - ymin) * tick / (_Y_TICKS - 1)
        y = y_at(value)
        parts.append(
            f'<line class="grid" x1="{_LEFT}" y1="{y:.1f}" '
            f'x2="{_WIDTH - _RIGHT}" y2="{y:.1f}"/>'
        )
        parts.append(_text(_LEFT - 8, y + 4, format_y(value), anchor="end", cls="tick"))

    # zero baseline when the domain strictly crosses it
    if ymin < 0.0 < ymax:
        zero_y = y_at(0.0)
        parts.append(
            f'<line class="zero" x1="{_LEFT}" y1="{zero_y:.1f}" '
            f'x2="{_WIDTH - _RIGHT}" y2="{zero_y:.1f}"/>'
        )

    # x tick labels (dates), anchored to avoid clipping at the edges
    for index in _x_tick_indices(count):
        anchor = "start" if index == 0 else "end" if index == count - 1 else "middle"
        label = series[index][0][:10]
        parts.append(
            _text(x_at(index), _HEIGHT - _BOTTOM + 20, label, anchor=anchor, cls="tick")
        )

    curve = " ".join(f"{x_at(i):.1f},{y_at(value):.1f}" for i, (_, value) in enumerate(series))
    if area and ymin <= 0.0 <= ymax:
        zero_y = y_at(0.0)
        polygon = (
            f"{curve} {x_at(count - 1):.1f},{zero_y:.1f} {x_at(0):.1f},{zero_y:.1f}"
        )
        parts.append(f'<polygon fill="{color}" fill-opacity="0.12" points="{polygon}"/>')
    parts.append(
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{curve}"/>'
    )

    # last-point marker with its value
    last_x, last_value = x_at(count - 1), values[-1]
    last_y = y_at(last_value)
    parts.append(f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="{color}"/>')
    parts.append(
        _text(last_x - 8, last_y - 8, format_y(last_value), anchor="end", cls="tick last")
    )

    parts.append("</svg>")
    return "".join(parts)

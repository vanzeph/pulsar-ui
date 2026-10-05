// Shared visual vocabulary: A-share color convention (red = up, green =
// down) on a dark dashboard surface, used consistently across views.

export const COLORS = {
  bg: "#0e131a",
  card: "#161d27",
  border: "#232d3a",
  text: "#d7e0ea",
  muted: "#8b98a8",
  accent: "#4da3ff",
  up: "#e0564f", // 红涨
  down: "#2f9e77", // 绿跌
  ok: "#2f9e77",
  warn: "#d9a441",
  bad: "#c4514a",
};

export const RUN_PALETTE = [
  "#4da3ff",
  "#e0a54f",
  "#b184e0",
  "#54c8b5",
  "#e07ab5",
  "#8bc24a",
];

/** Axis/tooltip text styling defaults for chart options. */
export const AXIS_STYLE = {
  axisLabel: { color: COLORS.muted, fontSize: 11 },
  axisLine: { lineStyle: { color: COLORS.border } },
  splitLine: { lineStyle: { color: COLORS.border, opacity: 0.5 } },
};

export function tooltipStyle(extra: object = {}): object {
  return {
    backgroundColor: "#10161e",
    borderColor: COLORS.border,
    textStyle: { color: COLORS.text, fontSize: 12 },
    ...extra,
  };
}

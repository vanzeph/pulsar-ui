"""Factor IC queries — an explicit empty state until C3 extends artifacts.

The factor-analysis view needs per-factor IC/IR time series and quantile
returns. Neither of today's data sources carries that data:

* run artifacts (``events.parquet`` / ``metrics_report.json``, schema v1
  as of pulsar-core 31801cb) record fills, equity and headline metrics —
  no factor values, no factor IC series;
* the lake's ``bars_1d`` canonical columns are OHLCV + ``adjust_factor``
  + ``quality`` — no factor columns.

So the endpoint answers with a well-formed empty result that says exactly
that, and names the seam (:func:`factor_ic`) where the aggregation will
land once the C3 artifacts extension publishes factor IC data. The server
never fabricates series to fill the gap.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["FACTOR_NAME_PATTERN", "factor_ic", "valid_factor_name"]

#: Factor names are registered identifiers (``momentum_20``, ...): keep
#: them identifier-shaped and path-free.
FACTOR_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")

#: Data sources the IC aggregation is specified to read from, in order.
IC_DATA_SOURCES = (
    "run artifacts (events.parquet / metrics_report.json)",
    "lake bars_1d factor columns",
)

_EMPTY_STATE_REASON = (
    "no factor IC data is present in the current artifact contracts: "
    "events.parquet and metrics_report.json (schema v1, pulsar-core 31801cb) "
    "carry no factor series, and lake bars_1d has no factor columns; "
    "this endpoint returns real series once the C3 artifacts extension "
    "publishes factor IC data"
)


def valid_factor_name(name: str) -> bool:
    """Whether ``name`` is an identifier-shaped, path-free factor name."""
    return bool(FACTOR_NAME_PATTERN.match(name))


def factor_ic(name: str) -> dict[str, Any]:
    """The IC/IR query for factor ``name``.

    Today this is the documented empty state; when C3 lands factor IC in
    the artifacts, this function becomes the aggregation (and only it —
    the endpoint shape stays stable).
    """
    return {
        "factor": name,
        "available": False,
        "reason": _EMPTY_STATE_REASON,
        "checked_sources": list(IC_DATA_SOURCES),
        "pending": "C3 artifacts extension (factor IC series)",
        "ic_series": [],
        "ir": None,
        "quantile_returns": [],
    }

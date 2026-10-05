"""pulsar-ui: the Pulsar local read-only visualization service.

The package is a pure consumer of Pulsar's stable data contracts — the
run artifacts (``run_manifest.json`` / ``events.parquet`` /
``metrics_report.json``) and the local Parquet data lake — and never
imports any pulsar code. :mod:`pulsar_ui.server` serves the GET-only
dashboard API bound to 127.0.0.1; the web front-end (U2) and the static
report generator (U3) live elsewhere in this repository.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]

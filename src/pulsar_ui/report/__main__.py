"""``python -m pulsar_ui.report <run_dir>`` — generate the static report."""

from __future__ import annotations

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())

"""``python3 -m agentic_loop.gate`` CLI entry.

The merge gate moved from a single ``gate.py`` module into a ``gate/`` package
(WP-03). This module preserves the historical ``-m`` entry point verbatim so the
in-service ``codex_merge_gate.sh`` thin shell keeps working without changes: it
simply delegates to ``agentic_loop.gate.main``, exactly as ``gate.py``'s
``__main__`` block used to.
"""
from __future__ import annotations

import sys

from agentic_loop.gate import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

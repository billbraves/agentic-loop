"""Bundled orchestration wrapper scripts (package data).

These are byte-for-byte copies of the main repo's ``scripts/agentic/*.sh``
wrappers, shipped so that ``pip install agentic-loop`` works in a project that
does not carry ``scripts/agentic/`` itself. ``agentic_loop.cli`` resolves the
main-repo copy first (dogfood) and falls back to these via
``importlib.resources``.
"""

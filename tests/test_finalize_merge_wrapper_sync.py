"""Guard the dual finalize_merge.sh copies stay byte-for-byte identical.

``cli.resolve_wrapper`` prefers the live main-repo ``scripts/agentic/`` copy
(dogfood) but falls back to the wheel-bundled
``agentic_loop/wrappers/finalize_merge.sh`` for external pip consumers. Those
two files are documented as byte-for-byte copies and must evolve together;
otherwise the external fallback silently drifts from the canonical triple-sign
gate. This test pins that contract in the framework repo where both files are
present. In the standalone extracted repo only the bundled wrapper exists (no
top-level ``scripts/agentic/``), so the drift assertion is skipped there.
"""
from pathlib import Path

import pytest

# Bundled wrapper lives inside THIS package (parents[1] = package root), so it
# resolves both inside the monorepo and in the standalone extracted repo.
PKG_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = PKG_ROOT / "src" / "agentic_loop" / "wrappers" / "finalize_merge.sh"
# Canonical main-repo copy only exists in the monorepo dogfood layout
# (parents[3] = monorepo root). Absent in the standalone repo.
CANONICAL = Path(__file__).resolve().parents[3] / "scripts" / "agentic" / "finalize_merge.sh"


def test_finalize_merge_wrapper_is_byte_for_byte_identical():
    assert WRAPPER.is_file(), f"missing bundled wrapper copy: {WRAPPER}"
    if not CANONICAL.is_file():
        pytest.skip("canonical main-repo copy absent in standalone layout")
    assert CANONICAL.read_bytes() == WRAPPER.read_bytes(), (
        f"finalize_merge.sh drifted between canonical ({CANONICAL}) and "
        f"bundled wrapper ({WRAPPER}); keep them byte-for-byte identical"
    )

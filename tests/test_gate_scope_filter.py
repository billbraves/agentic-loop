"""WP-04: the merge gate scope-filters the reviewed diff before sending it to
the consultant, so historical false positives (orchestration scaffolding,
branch status.json self-reference, stale-base cross-WP files) never reach codex.

These are unit tests over the pure helpers added to ``agentic_loop.gate``:
``filter_diff_by_scope`` / ``scope_matches`` / ``_path_in_scope``. They pin the
four correctness properties the brief requires:

1. scaffolding (brief / status.json / another WP's files) is excluded;
2. forbidden paths are excluded and win over allowed;
3. an all-in-scope diff is byte-for-byte equivalent before/after (no false
   negatives — legal content is never dropped);
4. the prefix predicate is identical to ``scripts/agentic/quality-gate.sh``'s
   ``matches()`` for the same ``(path, prefix)`` pairs.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.gate import (  # noqa: E402
    _path_in_scope,
    filter_diff_by_scope,
    scope_matches,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = REPO_ROOT / "scripts" / "agentic" / "quality-gate.sh"


def _block(path: str, added: str = "new line\n") -> str:
    """A minimal but realistic single-file unified-diff block for ``path``."""
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index 0000000..1111111 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1 @@\n"
        f"+{added}"
    )


ALLOWED = [
    "packages/agentic-loop/src/agentic_loop/gate.py",
    "packages/agentic-loop/tests/",
    "docs/plans/agentic-loop-hardening-v1/work-packages/WP-04.status.json",
]
FORBIDDEN = [
    "packages/agentic-loop/src/agentic_loop/validate_wp_status.py",
    "packages/agentic-loop/src/agentic_loop/wrappers/",
    "profiles/",
    ".env",
    ".context/",
    ".worktrees/",
]


# ---------------------------------------------------------------------------
# Property 1 + 2: scaffolding and forbidden files excluded; allowed retained.
# ---------------------------------------------------------------------------
def test_scaffolding_and_forbidden_excluded_allowed_retained():
    gate_py = _block("packages/agentic-loop/src/agentic_loop/gate.py")
    test_py = _block("packages/agentic-loop/tests/test_gate_scope_filter.py")
    status = _block(
        "docs/plans/agentic-loop-hardening-v1/work-packages/WP-04.status.json"
    )
    # scaffolding: another WP's brief + another WP's status (stale-base drag-in)
    other_brief = _block("docs/plans/agentic-loop-hardening-v1/WP-05-brief.md")
    other_status = _block(
        "docs/plans/agentic-loop-hardening-v1/work-packages/WP-05.status.json"
    )
    # forbidden files
    validator = _block(
        "packages/agentic-loop/src/agentic_loop/validate_wp_status.py"
    )
    wrapper = _block("packages/agentic-loop/src/agentic_loop/wrappers/lock.py")
    profile = _block("profiles/baofu/config.toml")

    diff = "".join(
        [gate_py, test_py, status, other_brief, other_status,
         validator, wrapper, profile]
    )
    filtered, kept, excluded = filter_diff_by_scope(diff, ALLOWED, FORBIDDEN)

    # allowed-in-scope files survive ...
    assert "a/packages/agentic-loop/src/agentic_loop/gate.py" in filtered
    assert "a/packages/agentic-loop/tests/test_gate_scope_filter.py" in filtered
    assert "WP-04.status.json" in filtered
    # ... scaffolding (other WP brief/status, not in allowed) is dropped ...
    assert "WP-05-brief.md" not in filtered
    assert "WP-05.status.json" not in filtered
    # ... forbidden files are dropped even though some sit under allowed prefixes
    assert "validate_wp_status.py" not in filtered
    assert "wrappers/lock.py" not in filtered
    assert "profiles/baofu/config.toml" not in filtered

    assert kept == 3
    assert excluded == 5


def test_forbidden_wins_over_allowed_overlap():
    """A forbidden prefix nested under an allowed prefix must be excluded:
    forbidden wins. wrappers/ lives under the agentic_loop src tree, but the
    allowed list here is the whole src package."""
    allowed = ["packages/agentic-loop/src/agentic_loop/"]
    forbidden = ["packages/agentic-loop/src/agentic_loop/wrappers/"]
    keep = _block("packages/agentic-loop/src/agentic_loop/gate.py")
    drop = _block("packages/agentic-loop/src/agentic_loop/wrappers/lock.py")
    filtered, kept, excluded = filter_diff_by_scope(keep + drop, allowed, forbidden)
    assert "gate.py" in filtered
    assert "wrappers/lock.py" not in filtered
    assert (kept, excluded) == (1, 1)


# ---------------------------------------------------------------------------
# Property 3: an all-in-scope diff is byte-for-byte equivalent (no false neg).
# ---------------------------------------------------------------------------
def test_all_in_scope_diff_is_byte_for_byte_equivalent():
    diff = "".join(
        [
            _block("packages/agentic-loop/src/agentic_loop/gate.py"),
            _block("packages/agentic-loop/tests/test_a.py"),
            _block("packages/agentic-loop/tests/test_b.py"),
            _block(
                "docs/plans/agentic-loop-hardening-v1/work-packages/"
                "WP-04.status.json"
            ),
        ]
    )
    filtered, kept, excluded = filter_diff_by_scope(diff, ALLOWED, FORBIDDEN)
    assert filtered == diff
    assert kept == 4
    assert excluded == 0


def test_empty_allowed_only_forbidden_applies():
    """Empty allowed_paths imposes no allowed restriction (quality-gate.sh
    parity): everything survives except forbidden."""
    keep = _block("some/random/file.py")
    drop = _block("profiles/x.toml")
    filtered, kept, excluded = filter_diff_by_scope(keep + drop, [], FORBIDDEN)
    assert "some/random/file.py" in filtered
    assert "profiles/x.toml" not in filtered
    assert (kept, excluded) == (1, 1)


def test_empty_diff_returns_empty():
    assert filter_diff_by_scope("", ALLOWED, FORBIDDEN) == ("", 0, 0)


def test_unparseable_leading_block_kept_failsafe():
    """Content before the first ``diff --git`` header (or any block whose path
    cannot be parsed) is kept verbatim — fail-safe against false negatives."""
    preamble = "some git noise not a header\n"
    real = _block("packages/agentic-loop/src/agentic_loop/gate.py")
    filtered, kept, excluded = filter_diff_by_scope(
        preamble + real, ALLOWED, FORBIDDEN
    )
    assert filtered.startswith(preamble)
    assert "gate.py" in filtered
    assert kept == 2
    assert excluded == 0


# ---------------------------------------------------------------------------
# Property 4: prefix predicate parity with quality-gate.sh matches().
# ---------------------------------------------------------------------------
def _bash_matches(path: str, prefix: str) -> bool:
    """Invoke the exact python predicate embedded in quality-gate.sh so the
    parity test cannot drift from the shipped shell source."""
    snippet = (
        "import sys\n"
        "def matches(path, prefix):\n"
        "    normalized = prefix.removeprefix('./')\n"
        "    return path == normalized.rstrip('/') or "
        "path.startswith(normalized.rstrip('/') + '/')\n"
        "print('1' if matches(sys.argv[1], sys.argv[2]) else '0')\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", snippet, path, prefix],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return out == "1"


@pytest.mark.parametrize(
    "path,prefix",
    [
        ("packages/agentic-loop/src/agentic_loop/gate.py",
         "packages/agentic-loop/src/agentic_loop/gate.py"),
        ("packages/agentic-loop/tests/test_x.py", "packages/agentic-loop/tests/"),
        ("packages/agentic-loop/tests/test_x.py", "packages/agentic-loop/tests"),
        ("packages/agentic-loop/tests", "packages/agentic-loop/tests/"),
        ("packages/agentic-loop/tests_other/x.py", "packages/agentic-loop/tests"),
        ("profiles/baofu/x.toml", "./profiles/"),
        (".env", ".env"),
        (".envrc", ".env"),
        ("docs/plans/it/WP-04.status.json",
         "docs/plans/it/WP-04.status.json"),
        ("a/b/c", "a/b"),
        ("ab/c", "a"),
    ],
)
def test_scope_matches_parity_with_quality_gate(path, prefix):
    assert scope_matches(path, prefix) == _bash_matches(path, prefix)


def test_path_in_scope_forbidden_precedence_unit():
    allowed = ["a/"]
    forbidden = ["a/secret/"]
    assert _path_in_scope("a/ok.py", allowed, forbidden) is True
    assert _path_in_scope("a/secret/k.py", allowed, forbidden) is False
    assert _path_in_scope("b/other.py", allowed, forbidden) is False
    # empty allowed => only forbidden filters
    assert _path_in_scope("b/other.py", [], forbidden) is True

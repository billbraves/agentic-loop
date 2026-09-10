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
BUNDLED_QUALITY_GATE = (
    Path(__file__).resolve().parents[1]
    / "src" / "agentic_loop" / "wrappers" / "quality-gate.sh"
)


def _shell_matches_source() -> str:
    """Extract the real ``matches()`` definition from the shipped shell script.

    Previously this test inlined a hand-copied snippet, which meant it kept
    passing while the shell source drifted — exactly the drift it exists to
    catch. Read the shipped file instead, so parity is asserted against what
    actually runs.
    """
    text = BUNDLED_QUALITY_GATE.read_text(encoding="utf-8")
    start = text.index("def matches(")
    # The definition ends at the first line that is neither blank nor indented.
    lines = text[start:].splitlines()
    body = [lines[0]]
    for line in lines[1:]:
        if line and not line[0].isspace():
            break
        body.append(line)
    return "\n".join(body)


def _bash_matches(path: str, prefix: str) -> bool:
    """Invoke the exact python predicate embedded in quality-gate.sh so the
    parity test cannot drift from the shipped shell source."""
    snippet = (
        "import sys\n"
        + _shell_matches_source()
        + "\nprint('1' if matches(sys.argv[1], sys.argv[2]) else '0')\n"
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
        # glob spellings must behave identically on both sides
        ("skills/prod/run.py", "skills/**"),
        ("skills/prod/run.py", "skills/*"),
        ("skills", "skills/**"),
        ("skills_other/x.py", "skills/**"),
        ("docs/plans/ha/a.md", "docs/plans/ha/**"),
        ("a/b.py", "a/*"),
        # degenerate entries match nothing on both sides
        ("anything/at/all", "**"),
        ("anything/at/all", "/"),
        ("anything/at/all", "./"),
    ],
)
def test_scope_matches_parity_with_quality_gate(path, prefix):
    assert scope_matches(path, prefix) == _bash_matches(path, prefix)


# ---------------------------------------------------------------------------
# Regression: glob-suffixed entries used to enforce nothing.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "pattern", ["skills/**", "skills/*", "skills/", "skills", "./skills/**"]
)
def test_forbidden_glob_suffix_actually_forbids(pattern):
    """``forbidden_paths: ['skills/**']`` must forbid ``skills/...``.

    Before the fix ``scope_matches`` was a literal ``startswith``, so no real
    path could ever match an entry containing ``**``: the entry forbade nothing
    while looking active in the status JSON. All five spellings of "the skills
    directory" must now agree.
    """
    assert scope_matches("skills/prod/run.py", pattern) is True
    assert _path_in_scope("skills/prod/run.py", [], [pattern]) is False
    filtered, kept, excluded = filter_diff_by_scope(
        _block("skills/prod/run.py"), [], [pattern]
    )
    assert "skills/prod/run.py" not in filtered
    assert (kept, excluded) == (0, 1)


def test_glob_suffix_does_not_over_match_sibling_dirs():
    """Stripping ``/**`` must not turn ``skills`` into a bare substring match:
    ``skills_other/`` is a different directory."""
    assert scope_matches("skills_other/x.py", "skills/**") is False
    assert scope_matches("skills", "skills/**") is True


def test_allowed_glob_suffix_keeps_in_scope_files():
    """The same bug hit allowed_paths from the other side: an allowed entry of
    ``dir/**`` matched nothing, so every real file fell outside scope."""
    allowed = ["qoder_agent/harness/**"]
    keep = _block("qoder_agent/harness/loader/core.py")
    drop = _block("qoder_agent/other/thing.py")
    filtered, kept, excluded = filter_diff_by_scope(keep + drop, allowed, [])
    assert "qoder_agent/harness/loader/core.py" in filtered
    assert "qoder_agent/other/thing.py" not in filtered
    assert (kept, excluded) == (1, 1)


@pytest.mark.parametrize("pattern", ["**", "/", "./", "   ", ""])
def test_degenerate_entry_matches_nothing(pattern):
    """An entry reducing to empty must not become "match everything": under
    forbidden that would block the whole WP, under allowed it would silently
    disable scope enforcement. The validator rejects these; the matcher stays
    fail-closed if one arrives anyway."""
    assert scope_matches("any/path.py", pattern) is False


def test_path_in_scope_forbidden_precedence_unit():
    allowed = ["a/"]
    forbidden = ["a/secret/"]
    assert _path_in_scope("a/ok.py", allowed, forbidden) is True
    assert _path_in_scope("a/secret/k.py", allowed, forbidden) is False
    assert _path_in_scope("b/other.py", allowed, forbidden) is False
    # empty allowed => only forbidden filters
    assert _path_in_scope("b/other.py", [], forbidden) is True

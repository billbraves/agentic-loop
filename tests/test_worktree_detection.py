"""WP-19 / A13 and WP-01: the status-source predicate is a git fact, not a path
literal and not a positional guess.

``agentic_loop.gate.path_is_in_worktree`` is the single authoritative definition,
referenced by all five call sites (``gate/__init__.py``, ``gate/qoder_security.py``,
``wrappers/preflight.sh``, ``wrappers/merge.sh``, ``wrappers/finalize_merge.sh``).
This suite pins:

WP-19 / A22 / A27 / A28 / A29 hardening (unchanged guarantees, rewritten call
form and premises — INV-4):

- an unresolvable path fails closed (refused) without raising;
- the verdict does not depend on the directory NAME (a literal ``/.worktrees/``
  directory is not by itself a refusal reason);
- the predicate does not inherit the caller's repository-selection environment
  (``GIT_DIR`` et al.) — those are stripped so the verdict reads the filesystem;
- the sanitized env keeps ``PATH`` usable;
- blank git output, symlink loops, overlong paths and NUL bytes all fail closed
  and never raise;
- ``finalize_merge.sh`` end-to-end rejects a non-authoritative status path.

WP-01 (2026-10-15-status-source-topology) retargets the predicate from "is this
path inside a LINKED worktree?" to "is this path in the checkout that HOLDS THE
AUTHORITATIVE BRANCH?", where the authoritative branch is PLAN status's
``git.base_branch`` (the plan's integration branch). The acceptance nodes E1-E12
below pin that contract:

- E1 a linked worktree holding the authoritative branch is ACCEPTED (the whole
  point: on this machine the integration branch lives in a linked worktree, so
  the old rule refused the one checkout that held the truth);
- E2 the physical primary repo holding the authoritative branch is still
  ACCEPTED (backwards compatible);
- E3 another worktree on a different branch is still REFUSED;
- E4 no checkout holds the authoritative branch -> REFUSED;
- E5 a prunable (stale) ghost holder -> REFUSED, with its own witness;
- E6 the authoritative branch NAME is validated by git's own ref syntax;
- E8 the 17 WP-19 hardening nodes above stay green (the hardening guard);
- E9 every degradation of the PLAN status -> REFUSED (``unresolved``);
- E10 the judged WP status cannot declare its own basis (PLAN wins);
- E12 one predicate across all five call sites.

WP-01 claims NO security property: a local actor who can write the repository or
set the caller's environment can edit the predicate itself, so ``git.base_branch``
is configuration, not a trust boundary. No anchor, policy file, environment
variable, or bypass flag exists or is tested for.
"""
from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
PKG_SRC = PKG_ROOT / "src"
if str(PKG_SRC) not in sys.path:
    sys.path.insert(0, str(PKG_SRC))

from agentic_loop.gate import path_is_in_worktree
from agentic_loop.gate import refusal_reason

FINALIZE_SH = PKG_SRC / "agentic_loop" / "wrappers" / "finalize_merge.sh"

# Witness strings (WP-01). Kept as literals here on purpose: the acceptance
# tests must fail if the predicate changes the wording, rather than tracking it.
W_UNRESOLVED = "authoritative branch unresolved"
W_NO_HOLDER = "no checkout holds authoritative branch"
W_STALE = "authoritative branch holder is stale (prunable)"
W_NOT_HOLDER = "checkout does not hold authoritative branch"

PLAN_SCHEMA = "agentic-plan-status/v1"


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _current_branch(repo: Path) -> str:
    return _run_git(repo, "branch", "--show-current").stdout.strip()


def _write_plan_status(
    plan_dir: Path,
    base_branch: object,
    *,
    name: str = "PLAN-01.status.json",
    schema: str = PLAN_SCHEMA,
    raw: str | None = None,
) -> Path:
    """Write a PLAN status declaring ``base_branch`` and return its path.

    A legal PLAN status is the ONLY thing that declares the authoritative branch;
    nothing in this suite injects it through an environment variable or a
    file outside the repository.
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    path = plan_dir / name
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    data: dict[str, object] = {"schema_version": schema, "plan_id": "PLAN-01"}
    if base_branch is not _MISSING:
        data["git"] = {"base_branch": base_branch, "target_branch": "main"}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class _Missing:
    """Sentinel: omit the key entirely (distinct from a None value)."""


_MISSING = _Missing()


def _write_wp_status(
    plan_dir: Path,
    *,
    name: str = "WP-01.status.json",
    base_branch: object = _MISSING,
    extra: dict | None = None,
) -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    path = plan_dir / name
    data: dict[str, object] = {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-01",
    }
    if base_branch is not _MISSING:
        data["git"] = {"base_branch": base_branch}
    if extra:
        data.update(extra)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real repo on its default branch, with a plan directory present.

    The plan directory holds a WP status and (when a test wants one) a PLAN
    status. No PLAN status is written here by default, so the "unresolved"
    family is the default and tests opt into a declared authority.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "init")
    return repo


def _plan_dir(repo: Path, iteration: str = "it-1") -> Path:
    plan_dir = repo / "docs" / "plans" / iteration
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


# ---------------------------------------------------------------------------
# E1-E5: the authoritative-branch-holder contract
# ---------------------------------------------------------------------------


def test_e1_linked_worktree_holding_authoritative_branch_is_accepted(
    repo: Path, tmp_path: Path
) -> None:
    """E1 [authoritative-branch-in-linked-worktree-is-trusted].

    Physical primary repo parked on one branch; the AUTHORITATIVE branch checked
    out in a LINKED worktree, whose status path must be ACCEPTED. This is the
    whole reason WP-01 exists: under the old predicate this checkout is refused.

    Self-proving premise: the accepting checkout is asserted to be a linked
    worktree (``--git-dir != --git-common-dir``), so the node cannot pass for an
    unrelated reason (e.g. the fixture not actually being a worktree).
    """
    primary_branch = "plan/primary-parked"
    _run_git(repo, "checkout", "-q", "-b", primary_branch)

    authority = "plan/authoritative"
    wt = tmp_path / "authority-wt"
    _run_git(repo, "worktree", "add", "-q", "-b", authority, str(wt))

    # The linked worktree must REALLY be a linked worktree, or this node is void.
    git_dir = _run_git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
    common_dir = _run_git(wt, "rev-parse", "--git-common-dir").stdout.strip()
    assert git_dir != common_dir, "premise: the authority checkout is a linked worktree"
    assert _current_branch(wt) == authority

    plan_dir = _plan_dir(wt)
    _write_plan_status(plan_dir, authority)
    status = _write_wp_status(plan_dir)

    assert path_is_in_worktree(status) is False, refusal_reason()


def test_e2_primary_repo_holding_authoritative_branch_still_trusted(
    repo: Path,
) -> None:
    """E2 [primary-repo-holding-authoritative-branch-still-trusted].

    The traditional layout — the physical primary repo itself checks out the
    authoritative branch — must keep working (compatibility). This node would
    also pass under the old predicate, so it is the control that proves WP-01
    did not trade one layout for the other.
    """
    authority = _current_branch(repo)
    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, authority)
    status = _write_wp_status(plan_dir)

    assert path_is_in_worktree(status) is False, refusal_reason()


def test_e3_other_worktree_still_refused(repo: Path, tmp_path: Path) -> None:
    """E3 [other-worktree-still-refused].

    Another worktree of the SAME repository, on a different branch, must still be
    refused, with the wrong-branch witness. Pairs with E1 so that "accept the
    holder" cannot degrade into "accept every worktree" (that would be M-5).
    """
    authority = _current_branch(repo)
    wt = tmp_path / "other-wt"
    _run_git(repo, "worktree", "add", "-q", "-b", "plan/y", str(wt))

    plan_dir = _plan_dir(wt)
    _write_plan_status(plan_dir, authority)
    status = _write_wp_status(plan_dir)

    assert path_is_in_worktree(status) is True
    assert refusal_reason() == W_NOT_HOLDER


def test_e4_no_holder_fails_closed(repo: Path) -> None:
    """E4 [no-holder-fails-closed].

    The declared authoritative branch is checked out by NO worktree, so the path
    is refused with the no-holder witness (distinct from the stale witness).
    """
    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, "plan/nowhere")
    status = _write_wp_status(plan_dir)

    assert path_is_in_worktree(status) is True
    assert refusal_reason() == W_NO_HOLDER


def test_e5_stale_holder_fails_closed(repo: Path, tmp_path: Path) -> None:
    """E5 [stale-holder-fails-closed] (INV-2b).

    Register a worktree that checks out the authoritative branch, then DELETE its
    directory. git keeps the entry, marks it ``prunable``, and still lists it as
    the branch's holder — so the repository is stuck on a holder that cannot be
    used. The predicate must refuse with the STALE witness, not degrade to
    ``no checkout holds`` (the remedies differ: ``git worktree prune``).

    Self-proving premise: the ghost entry is asserted to be present in
    ``git worktree list --porcelain``, flagged ``prunable``, and its directory is
    asserted to be gone.
    """
    authority = "plan/authoritative"
    _run_git(repo, "checkout", "-q", "-b", "plan/primary-parked")
    wt = tmp_path / "stale-wt"
    _run_git(repo, "worktree", "add", "-q", "-b", authority, str(wt))

    # The PLAN status lives in the PRIMARY repo's plan dir; the judged path we
    # assert on after the deletion is a status in that same dir (so it survives
    # the ghost checkout's removal).
    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, authority)
    status_in_primary = _write_wp_status(plan_dir, name="WP-P.status.json")

    # Premise (self-proving): while the holder is alive, a status INSIDE that
    # holder is ACCEPTED, so the fixture demonstrably resolves authority. The
    # plan dir is derived from the JUDGED file's own location, so the holder's
    # copy carries its own PLAN status (this mirrors a real worktree carrying the
    # plan directory committed on the integration branch).
    holder_plan_dir = _plan_dir(wt)
    _write_plan_status(holder_plan_dir, authority)
    status_in_holder = _write_wp_status(holder_plan_dir, name="WP-H.status.json")
    assert path_is_in_worktree(status_in_holder) is False, refusal_reason()
    # ...and the same plan dir as seen from the primary repo is refused as a
    # non-holder checkout (the primary repo does not hold the authority here).
    assert path_is_in_worktree(status_in_primary) is True
    assert refusal_reason() == W_NOT_HOLDER

    shutil.rmtree(wt)
    assert not wt.exists()
    assert status_in_primary.is_file()

    listing = _run_git(repo, "worktree", "list", "--porcelain").stdout
    # Premise: the ghost is still listed, still holds the branch, prunable.
    assert str(wt) in listing
    assert "prunable" in listing
    block = _porcelain_blocks(listing)[str(wt)]
    assert f"branch refs/heads/{authority}" in block

    assert path_is_in_worktree(status_in_primary) is True
    assert refusal_reason() == W_STALE


def _porcelain_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree ") :]
            blocks[current] = []
        elif current is not None and line.strip():
            blocks[current].append(line.strip())
    return blocks


# ---------------------------------------------------------------------------
# E6: git ref-syntax name validation
# ---------------------------------------------------------------------------


E6_POSITIVE = [
    "plan/2026-10-15-status-source-topology",
    "feature/x-y",
    "a.b",
    "release/2026.10",
    "@",
]

E6_NEGATIVE = [
    "",  # empty
    "a\x00b",  # NUL
    "a..b",  # ".."
    ".",  # a single dot
    ".hidden",  # component begins with "."
    "/leading",  # leading slash => empty first component
    "trailing/",  # trailing slash => empty last component
    "a//b",  # doubled slash => empty component
    "has space",  # space
    "tilde~x",  # "~"
    "caret^x",  # "^"
    "colon:x",  # ":"
    "q?x",  # "?"
    "star*x",  # "*"
    "bracket[x",  # "["
    "trail.lock",  # ends with ".lock"
    "trail.",  # component ends with "."
]


@pytest.mark.parametrize("name", E6_POSITIVE)
def test_e6_positive_legal_branch_names_are_accepted(
    repo: Path, tmp_path: Path, name: str
) -> None:
    """E6 positive group: a legal (possibly slashed) integration branch name must
    be accepted, INCLUDING the real value. rev1-rev5 would reject these and leave
    the deadlock un-lifted (D14)."""
    authority = _current_branch(repo)
    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, name)
    status = _write_wp_status(plan_dir)

    # The oracle: git itself accepts this name as a branch.
    assert _git_accepts_branch_name(name), name
    # The holder set is empty for all but the real checkout; the point of this
    # node is that the NAME check does not refuse by itself.
    verdict = path_is_in_worktree(status)
    if name == authority:
        assert verdict is False, refusal_reason()
    else:
        assert verdict is True
        assert refusal_reason() == W_NO_HOLDER


@pytest.mark.parametrize("name", E6_NEGATIVE)
def test_e6_negative_illegal_branch_names_fail_closed(
    repo: Path, tmp_path: Path, name: str
) -> None:
    """E6 negative group: every illegal form must fail closed with the
    name-validation witness (``unresolved``), NOT for an incidental reason."""
    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, name)
    status = _write_wp_status(plan_dir)

    assert not _git_accepts_branch_name(name), name
    assert path_is_in_worktree(status) is True
    assert refusal_reason() == W_UNRESOLVED, (name, refusal_reason())


def _git_accepts_branch_name(name: str) -> bool:
    """Oracle: exactly ``git check-ref-format --branch <name>``."""
    try:
        proc = subprocess.run(
            ["git", "check-ref-format", "--branch", name],
            capture_output=True,
            text=True,
        )
    except (OSError, RuntimeError, ValueError):
        return False
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# E9: PLAN status degradation -> unresolved
# ---------------------------------------------------------------------------


def _e9_fixture(repo: Path, tmp_path: Path, *, degrade: str) -> Path:
    """A fixture with ONE LIVE ``main`` holder, plus a degraded PLAN status.

    The live ``main`` holder is the rev6 (D16) premise: without it, a mutation
    that adds a ``"main"`` fallback would merely turn ``unresolved`` into
    ``no holder`` — still fail closed — and could not go red. With it, the
    fallback would WRONGLY ACCEPT these inputs.
    """
    # A real `main` branch, checked out in a live linked worktree.
    _run_git(repo, "branch", "main")
    main_wt = tmp_path / "main-holder"
    _run_git(repo, "worktree", "add", "-q", str(main_wt), "main")
    assert _current_branch(main_wt) == "main"

    plan_dir = _plan_dir(repo)
    if degrade == "missing_file":
        pass  # no PLAN status at all
    elif degrade == "invalid_json":
        _write_plan_status(plan_dir, _MISSING, raw="{not json")
    elif degrade == "no_git_section":
        (plan_dir / "PLAN-01.status.json").write_text(
            json.dumps({"schema_version": PLAN_SCHEMA}), encoding="utf-8"
        )
    elif degrade == "no_base_branch_key":
        (plan_dir / "PLAN-01.status.json").write_text(
            json.dumps({"schema_version": PLAN_SCHEMA, "git": {}}), encoding="utf-8"
        )
    elif degrade == "non_string_value":
        _write_plan_status(plan_dir, 123)
    elif degrade == "illegal_name":
        _write_plan_status(plan_dir, "a..b")
    else:  # pragma: no cover - guards against a typo in the parametrization
        raise AssertionError(degrade)
    return _write_wp_status(plan_dir)


E9_FORMS = [
    "missing_file",
    "invalid_json",
    "no_git_section",
    "no_base_branch_key",
    "non_string_value",
    "illegal_name",
]


@pytest.mark.parametrize("degrade", E9_FORMS)
def test_e9_unresolved_plan_status_fails_closed(
    repo: Path, tmp_path: Path, degrade: str
) -> None:
    """E9 [authoritative-branch-unresolved-fails-closed] (INV-1b clauses 1-2).

    Six degradation forms; every one must fail closed with the ``unresolved``
    witness, and NONE may fall back to ``main`` and wrongly accept. The fixture
    contains a live ``main`` holder so the no-fallback half is load-bearing (D16).
    """
    status = _e9_fixture(repo, tmp_path, degrade=degrade)

    assert path_is_in_worktree(status) is True, (degrade, refusal_reason())
    assert refusal_reason() == W_UNRESOLVED, (degrade, refusal_reason())
    # Explicit no-fallback assertion: the answer must NOT be the acceptance a
    # `"main"` fallback would produce.
    assert path_is_in_worktree(status) is not False


# ---------------------------------------------------------------------------
# E10: the judged object cannot declare its own basis
# ---------------------------------------------------------------------------


def test_e10_judged_object_cannot_declare_its_own_basis(repo: Path) -> None:
    """E10 [judged-object-cannot-declare-its-own-basis].

    The authoritative branch MUST come from the PLAN status, never from the WP
    status being judged. Both use the same legal schema field name
    (``git.base_branch``), and the WP's own copy is the most likely misread.

    Construction: PLAN declares ``plan/authoritative`` (checked out here, so the
    only correct verdict is ACCEPT); the judged WP status declares
    ``plan/attacker`` (checked out nowhere). Only legal schema objects are used —
    no unknown field is injected, so this cannot go green via a validator
    rejection. A predicate that read the WP's own field would refuse.
    """
    authority = "plan/authoritative"
    _run_git(repo, "checkout", "-q", "-b", authority)

    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, authority)
    status = _write_wp_status(plan_dir, base_branch="plan/attacker")

    assert path_is_in_worktree(status) is False, refusal_reason()

    # Contrast: when the PLAN itself declares the attacker branch, the same file
    # is refused — proving the PLAN field is what the verdict follows.
    _write_plan_status(plan_dir, "plan/attacker")
    assert path_is_in_worktree(status) is True
    assert refusal_reason() == W_NO_HOLDER


# ---------------------------------------------------------------------------
# E12: one predicate across all five call sites
# ---------------------------------------------------------------------------


CALL_SITES = [
    "src/agentic_loop/wrappers/preflight.sh",
    "src/agentic_loop/wrappers/merge.sh",
    "src/agentic_loop/wrappers/finalize_merge.sh",
    "src/agentic_loop/gate/__init__.py",
    "src/agentic_loop/gate/qoder_security.py",
]


PREDICATE = "path_is_in_worktree"
# Tolerant on purpose: a parenthesised multi-line import, a trailing comma, or an
# `as` alias are all legitimate refactors and must not be reported as a second
# implementation. For .py the AST answers this exactly; this regex is only the
# shell fallback, where the import is a single line inside a Python heredoc.
SH_IMPORT_RE = re.compile(
    r"from\s+agentic_loop\.gate\s+import\b[\s\S]{0,200}?" + PREDICATE
)
SH_CALL_RE = re.compile(r"\b" + PREDICATE + r"\s*\(")


def _imports_and_calls(body: str, rel: str) -> "tuple[bool, bool]":
    """(imports the predicate from gate, actually calls it) for one call site.

    ``.py`` is parsed with ``ast`` so an alias or a multi-line import is handled
    correctly instead of being mistaken for a missing import. Shell files carry
    their Python in heredocs, so they fall back to a tolerant regex.
    """
    if rel.endswith(".py"):
        import ast

        try:
            tree = ast.parse(body)
        except SyntaxError:
            return (False, False)
        # Resolve the LOCAL name the import binds, so `... import p as _pw`
        # followed by `_pw(...)` is recognised as the same predicate rather
        # than mistaken for a second implementation.
        local = None
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module == "agentic_loop.gate":
                for a in n.names:
                    if a.name == PREDICATE:
                        local = a.asname or a.name
        if local is None:
            return (False, False)
        invoked = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == local
            for n in ast.walk(tree)
        )
        return (True, invoked)
    return (
        SH_IMPORT_RE.search(body) is not None,
        SH_CALL_RE.search(body) is not None,
    )


def _strip_comments(text: str, rel: str) -> str:
    """Remove comments so an assertion cannot be satisfied by prose.

    ``.py`` goes through ``tokenize`` so only real COMMENT spans are removed --
    a line-local ``#`` rule is fooled by ``#`` inside strings. Shell files have
    no lexer here, so only FULL-LINE comments (first non-space char ``#``) are
    stripped, which is the form every ``.sh`` call site uses. Anything that
    fails to lex is returned verbatim, so a file that cannot be read keeps the
    assertion RED rather than silently skipping it.
    """
    if rel.endswith(".py"):
        import io
        import tokenize

        try:
            # Blank out each COMMENT token's OWN span in the original text.
            # Re-joining token strings would drop the whitespace between them
            # and make `def path_is_in_worktree(` unfindable.
            lines = text.splitlines(keepends=True)
            spans = []
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.COMMENT:
                    spans.append((tok.start, tok.end))
            for (srow, scol), (erow, ecol) in spans:
                if srow == erow:
                    ln = lines[srow - 1]
                    lines[srow - 1] = ln[:scol] + ln[ecol:]
            return "".join(lines)
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return text
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )


def test_e12_one_predicate_across_all_five_call_sites() -> None:
    """E12 [one-predicate-across-all-five-call-sites] (INV-5).

    All five entry points reference the SAME predicate function, and no second,
    selectable implementation exists (that would be M-12)."""
    texts = {
        rel: (PKG_ROOT / rel).read_text(encoding="utf-8") for rel in CALL_SITES
    }

    # Assert against CODE, not raw text. A first cut of this node only checked
    # that the string appeared, and every one of these files mentions the name
    # in a comment -- so renaming the real import and call while leaving the
    # comments intact kept it green (reproduced by the consultant and again
    # here). Comments are stripped before matching.
    code = {rel: _strip_comments(text, rel) for rel, text in texts.items()}

    definition = "def path_is_in_worktree("
    home = "src/agentic_loop/gate/__init__.py"

    # The definition lives in exactly ONE place, and that file gets no import
    # assertion -- it DEFINES the predicate rather than importing it.
    definers = [rel for rel, body in code.items() if definition in body]
    assert definers == [home], definers
    assert len(code[home].split(definition)) > 1

    # Every OTHER entry point must import it exactly and then actually call it.
    for rel, body in code.items():
        if rel == home:
            continue
        imported, invoked = _imports_and_calls(body, rel)
        assert imported, (
            rel, "does not import path_is_in_worktree from agentic_loop.gate"
        )
        assert invoked, (rel, "imports the predicate but never calls it")

    # No alternate predicate definition anywhere else in product code.
    for rel, body in code.items():
        if rel == "src/agentic_loop/gate/__init__.py":
            continue
        assert definition not in body, rel


# ---------------------------------------------------------------------------
# WP-19 hardening guards (E8): attack guarantees preserved (INV-4).
#
# Each node below keeps its original attack SHAPE (env disguise, symlink
# following and loops, NUL, overlong paths, blank git output) and only adapts the
# call form / fixture to the new contract. The mapping table in the WP handoff
# records the one-by-one correspondence with the original 17 nodes and the
# reason for every adjusted expectation.
# ---------------------------------------------------------------------------


def _trust_main(repo: Path):
    """Make ``repo``'s CURRENT branch the authoritative one for its plan dir.

    Returns a callable ``accepting(path)`` that writes a WP status in the same
    plan dir as ``path``... Simpler: helper returns the plan dir after writing a
    PLAN status declaring ``repo``'s current branch.
    """
    plan_dir = _plan_dir(repo)
    _write_plan_status(plan_dir, _current_branch(repo))
    return plan_dir


def test_guard_main_repo_path_is_not_worktree(repo: Path) -> None:
    # Original node 1. The physical primary repo holding the authoritative branch
    # is trusted => False. (Under the old predicate this was True by topology;
    # the new contract keys on role, and the primary repo here HOLDS the role.)
    plan_dir = _trust_main(repo)
    status = _write_wp_status(plan_dir)
    assert path_is_in_worktree(status) is False


def test_guard_sibling_worktree_path_is_worktree(repo: Path, tmp_path: Path) -> None:
    # Original node 2. The layout this repo actually uses: `git worktree add
    # ../wpN-x` — a sibling whose name never contains ".worktrees/". The sibling
    # does NOT hold the authoritative branch, so it is still refused (True).
    plan_dir = _trust_main(repo)
    wt = tmp_path / "wp19-x"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-x", str(wt))
    assert "/.worktrees/" not in str(wt)
    status = _write_wp_status(plan_dir, name="WP-SIB.status.json")
    # Same plan dir, but reach it THROUGH the sibling checkout.
    sibling_status = wt / plan_dir.relative_to(repo) / status.name
    sibling_status.parent.mkdir(parents=True, exist_ok=True)
    sibling_status.write_text(status.read_text(encoding="utf-8"), encoding="utf-8")
    assert path_is_in_worktree(sibling_status) is True


def test_guard_verdict_does_not_depend_on_directory_name(
    repo: Path, tmp_path: Path
) -> None:
    # Original node 3. A literal ".worktrees" directory INSIDE the primary repo is
    # plain content. With the plan dir under it and the branch declared, the path
    # is NOT refused: the verdict is a git/branch fact, not the directory name.
    plan_dir = _plan_dir(repo).parent / ".worktrees" / "fake"
    _write_plan_status(plan_dir, _current_branch(repo))
    status = _write_wp_status(plan_dir)
    assert path_is_in_worktree(status) is False


def test_guard_unresolvable_path_fails_closed_without_raising(tmp_path: Path) -> None:
    # Original node 4. Outside any git repository: fail closed and never raise.
    missing = tmp_path / "no-such-dir" / "WP-X.status.json"
    assert path_is_in_worktree(missing) is True


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"])
def test_guard_caller_env_cannot_disguise_non_holder_toolpath(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, var: str
) -> None:
    # Original node 5 (A22). The caller exports a repository-selection variable
    # pointing at a FOREIGN repository whose registry does not list the
    # authoritative branch. If the probe inherited it, `git worktree list` would
    # read the foreign registry and the legitimate authoritative checkout would
    # be misjudged (refused as a non-holder). The predicate strips the variable,
    # so the holder is still ACCEPTED (False) and a non-holder is still refused.
    authority = "plan/authoritative"
    _run_git(repo, "checkout", "-q", "-b", "plan/parked")
    wt = tmp_path / "auth-wt"
    _run_git(repo, "worktree", "add", "-q", "-b", authority, str(wt))
    plan_dir = _plan_dir(wt)
    _write_plan_status(plan_dir, authority)
    status = _write_wp_status(plan_dir)

    foreign = _foreign_repo(tmp_path)
    value = str(foreign) if var == "GIT_WORK_TREE" else str(foreign / ".git")
    monkeypatch.setenv(var, value)

    # Premise: where the variable redirects the registry (GIT_DIR /
    # GIT_COMMON_DIR), the foreign registry genuinely lacks the authoritative
    # branch, so inheritance WOULD change the verdict. GIT_WORK_TREE does not
    # redirect the registry (it only declares a work tree), so it is checked for
    # the invariant verdict alone.
    listing = subprocess.run(
        ["git", "-C", str(wt), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, env={**os.environ, var: value},
    )
    if listing.returncode == 0 and var in ("GIT_DIR", "GIT_COMMON_DIR"):
        assert f"branch refs/heads/{authority}" not in listing.stdout

    assert path_is_in_worktree(status) is False, refusal_reason()


def _foreign_repo(tmp_path: Path) -> Path:
    """A separate git repo whose registry lists no authoritative branch."""
    foreign = tmp_path / "foreign-repo"
    foreign.mkdir()
    _run_git(foreign, "init", "-q")
    _run_git(foreign, "config", "user.email", "test@example.com")
    _run_git(foreign, "config", "user.name", "Test")
    (foreign / "f.txt").write_text("f\n", encoding="utf-8")
    _run_git(foreign, "add", "f.txt")
    _run_git(foreign, "commit", "-q", "-m", "foreign init")
    return foreign


def test_guard_caller_env_cannot_disguise_authoritative_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Original node 6 (A22, reverse direction). With GIT_DIR pointing at a linked
    # worktree's git dir, a path in the trustED checkout still resolves by
    # filesystem topology and is NOT refused (False) — sanitization must not
    # over-correct.
    plan_dir = _trust_main(repo)
    status = _write_wp_status(plan_dir)
    wt = tmp_path / "wp19-env-rev"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-env-rev", str(wt))
    wt_git_dir = _run_git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
    monkeypatch.setenv("GIT_DIR", wt_git_dir)
    assert path_is_in_worktree(status) is False


def test_guard_caller_env_combined_cannot_disguise_non_holder(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Original node 7 (A22 combined form). GIT_DIR + GIT_WORK_TREE +
    # GIT_COMMON_DIR all pointing at the trusted checkout must not flip a
    # non-holder worktree path to False.
    _trust_main(repo)
    wt = tmp_path / "wp19-env-all"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-env-all", str(wt))
    monkeypatch.setenv("GIT_DIR", str(repo / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(repo))
    monkeypatch.setenv("GIT_COMMON_DIR", str(repo / ".git"))
    status = _write_wp_status(_plan_dir(wt))
    assert path_is_in_worktree(status) is True


def test_guard_sanitized_env_still_preserves_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Original node 8. Distinguish "env sanitized" from "env emptied": with a PATH
    # that has NO git the probe cannot run and must fail closed (True); with the
    # inherited PATH it finds git and the trusted path is correctly NOT refused.
    plan_dir = _trust_main(repo)
    status = _write_wp_status(plan_dir)

    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    assert shutil.which("git") is None  # premise: git genuinely unfindable
    assert path_is_in_worktree(status) is True  # fail-closed
    monkeypatch.undo()  # restore the real PATH
    assert shutil.which("git") is not None
    assert path_is_in_worktree(status) is False


def test_guard_blank_common_dir_fails_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Original node 9 (A28-1). git exits 0 but an output line is blank; degenerate
    # output must fail closed. The probe under the new predicate is the git call
    # that enumerates worktrees; a blanked line there must not yield a verdict.
    wt = _run_git(repo, "worktree", "list", "--porcelain").stdout
    fake = subprocess.CompletedProcess(args=["git"], returncode=0, stdout=" \n", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    assert path_is_in_worktree(
        _write_wp_status(_plan_dir(repo))
    ) is True
    assert wt  # the real listing is non-trivially non-empty (fixture sanity)


def test_guard_blank_git_dir_fails_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Original node 10 (A28-1 symmetric). A blank probe output must fail closed.
    fake = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    assert path_is_in_worktree(_write_wp_status(_plan_dir(repo))) is True


def test_guard_symlink_loop_fails_closed_without_raising(repo: Path) -> None:
    # Original node 11 (A28-2 / A33). A symlink loop must never raise; the verdict
    # is version-dependent (3.13+ returns the path), so the cross-version CONTRACT
    # is: never raises and returns a real bool.
    loop = repo / "loop"
    loop.symlink_to("loop")  # real self-referential symlink loop
    result = path_is_in_worktree(loop)
    assert isinstance(result, bool)


def test_guard_symlink_loop_inside_non_holder_is_refused(
    repo: Path, tmp_path: Path
) -> None:
    # Original node 12 (A33 detection-power counterpart). A symlink loop INSIDE a
    # non-holder worktree must be refused (True) on every interpreter — otherwise a
    # predicate that always returned False would pass the contract node above.
    _trust_main(repo)
    wt = tmp_path / "wp21-loop"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp21-loop", str(wt))
    loop = wt / "loop"
    loop.symlink_to("loop")
    assert path_is_in_worktree(loop) is True


def test_guard_symlink_to_non_authoritative_status_is_refused(
    repo: Path, tmp_path: Path
) -> None:
    # Original node 13 (A27). The predicate must judge the file actually read, not
    # the path NAME: an alias in the trusted checkout pointing at a
    # non-authoritative status file is followed by every later consumer, so the
    # verdict must be the target's (True).
    _trust_main(repo)
    wt = tmp_path / "wp19-link"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-link", str(wt))
    status_in_wt = _write_wp_status(_plan_dir(wt))
    link = repo / "WP-L.status.json"
    link.symlink_to(status_in_wt)
    assert path_is_in_worktree(link) is True


def test_guard_finalize_merge_rejects_non_authoritative_status(
    repo: Path, tmp_path: Path
) -> None:
    # Original node 14. finalize_merge.sh end-to-end rejects a status path in a
    # non-holder worktree, with the unchanged refusal wording.
    _trust_main(repo)
    wt = tmp_path / "wp19-y"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-y", str(wt))
    status_in_wt = _write_wp_status(_plan_dir(wt), name="WP-Y.status.json")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["AGENTIC_PYTHON"] = sys.executable
    res = subprocess.run(
        ["bash", str(FINALIZE_SH), str(status_in_wt)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "resolves inside a worktree" in res.stderr, (res.stdout, res.stderr)


def test_guard_long_path_fails_closed_without_raising(repo: Path) -> None:
    # Original node 15 (A29-1 / A30). An overlong path must never raise: the
    # cross-version invariant is that the call returns a real bool.
    long_name = "a" * 300 + ".json"
    result = path_is_in_worktree(repo / long_name)
    assert isinstance(result, bool)


def test_guard_long_path_inside_non_holder_is_refused(
    repo: Path, tmp_path: Path
) -> None:
    # Original node 16 (A30 counterpart). An overlong path inside a non-holder
    # worktree must be refused (True) on every supported interpreter.
    _trust_main(repo)
    wt = tmp_path / "wp19-long"
    _run_git(repo, "worktree", "add", "-q", "-b", "feat/wp19-long", str(wt))
    long_name = "a" * 300 + ".json"
    assert path_is_in_worktree(wt / long_name) is True


def test_guard_null_byte_path_fails_closed_without_raising(repo: Path) -> None:
    # Original node 17 (A29-2). resolve() raises ValueError for NUL paths, which
    # is not an OSError; the shared guard form catches it -> fail closed (True).
    nul_path = Path(str(repo) + "/a\x00b.json")
    assert path_is_in_worktree(nul_path) is True


# ---------------------------------------------------------------------------
# E13: malformed `git worktree list --porcelain` must refuse (found in the
# WP-01 implementation second signature, verified by the orchestrator).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "listing",
    [
        # An unrecognised line inside a record. This is the fail-open that was
        # actually there: the parser skipped unknown lines, so a record it did
        # not understand was still returned as a valid holder.
        "worktree /tmp/t\nbranch refs/heads/main\nMALFORMED junk\n",
        # A second `branch` line contradicts the first; refuse rather than pick.
        "worktree /tmp/t\nbranch refs/heads/a\nbranch refs/heads/b\n",
        # Junk BETWEEN records, not just inside one.
        "worktree /tmp/a\nbranch refs/heads/x\n\nJUNK\nworktree /tmp/b\n"
        "branch refs/heads/y\n",
        # A record with no `worktree` line at all.
        "HEAD abc\nbranch refs/heads/main\n",
        # Prefix, not whole-token, matching. The first cut of this fix used
        # startswith("locked") / startswith("prunable") and these slipped
        # through -- found by the implementation second signature (r2).
        "worktree /tmp/t\nbranch refs/heads/main\nlockedevil\n",
        "worktree /tmp/t\nbranch refs/heads/main\nprunableevil\n",
        "worktree /tmp/t\nbranch refs/heads/main\nHEADEVIL x\n",
        # HEAD is single-valued; a second one is corruption, not a fact.
        "worktree /tmp/t\nHEAD a\nHEAD b\nbranch refs/heads/main\n",
        # HEAD and branch CARRY a value, so a bare one is malformed. `locked`
        # and `prunable` may stand alone, and must still parse (positive half).
        "worktree /tmp/t\nHEAD\nbranch refs/heads/main\n",
        "worktree /tmp/t\nHEAD a\nbranch\n",
        # Records must be separated by a blank line, so a second `worktree`
        # line while one is still open is malformed rather than a new record.
        "worktree /tmp/a\nbranch refs/heads/x\nworktree /tmp/b\n"
        "branch refs/heads/y\n",
    ],
)
def test_e13_malformed_porcelain_fails_closed(listing: str) -> None:
    """E13 [malformed-porcelain-fails-closed].

    `path_is_in_worktree`'s contract says malformed `git worktree list
    --porcelain` output refuses. The parser must therefore RECOGNISE every line
    it accepts and return None on anything else -- silently skipping an
    unknown line would answer "trusted" on output it did not understand, which
    inverts the whole fail-closed design.
    """
    from agentic_loop.gate import _parse_worktree_listing

    assert _parse_worktree_listing(listing) is None, listing


@pytest.mark.parametrize(
    "listing,count",
    [
        # The documented vocabulary must still parse: strictness that rejected
        # real git output would break every gate.
        ("worktree /tmp/t\nHEAD abc\nbranch refs/heads/main\n", 1),
        ("worktree /tmp/t\nHEAD abc\ndetached\nlocked reason\n", 1),
        ("worktree /tmp/t\nbare\n", 1),
        # `locked` and `prunable` may appear with no argument.
        ("worktree /tmp/t\nHEAD a\nlocked\n", 1),
        ("worktree /tmp/t\nHEAD a\nprunable\n", 1),
        ("worktree /tmp/t\nHEAD abc\nbranch refs/heads/x\nprunable gone\n", 1),
        # Real porcelain separates records with an empty line.
        ("worktree /tmp/a\nbranch refs/heads/x\n\n"
         "worktree /tmp/b\nbranch refs/heads/y\n\n", 2),
    ],
)
def test_e13_well_formed_porcelain_still_parses(listing: str, count: int) -> None:
    """E13 (positive half): the strictness must not reject real porcelain."""
    from agentic_loop.gate import _parse_worktree_listing

    records = _parse_worktree_listing(listing)
    assert records is not None, listing
    assert len(records) == count, (listing, records)

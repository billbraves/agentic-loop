"""agentic — thin CLI dispatch layer.

Each subcommand forwards verbatim to the matching ``scripts/agentic/<wrapper>.sh``
in the main repository. This layer adds no behavior of its own: argv, stdout,
stderr and exit codes pass through unchanged, so ``agentic gate <status>`` is
byte-for-byte equivalent to ``bash scripts/agentic/codex_merge_gate.sh <status>``.

The wrappers hold the real orchestration; porting their bash glue into Python is
explicitly out of scope (frozen design decision — bash stays as package-adjacent
tooling).

Wrapper resolution is dual-copy:

  (a) the main-repo ``scripts/agentic/<wrapper>.sh`` when this runs inside the
      framework's own git tree — so live edits (dogfood) take effect without a
      reinstall; else
  (b) the copy bundled in the wheel under ``agentic_loop/wrappers/`` — so a
      project that merely ``pip install``\\ ed the package, with no git repo and
      no ``scripts/agentic/``, still runs the gates.

Only when neither is present does the CLI emit its clean "wrapper not found"
error (never a traceback).
"""
import contextlib
import importlib.resources as _resources
import os
import subprocess
import sys
from pathlib import Path

# Package that holds the bundled wrapper copies (fallback for external installs).
_WRAPPER_PACKAGE = "agentic_loop.wrappers"

# agentic <subcommand> -> scripts/agentic/<file>.sh
_SUBCOMMANDS = {
    "gate": "codex_merge_gate.sh",
    "redispatch": "redispatch.sh",
    "preflight": "preflight.sh",
    "finalize": "finalize_merge.sh",
    "dispatch-lint": "dispatch_lint.sh",
    "quality-gate": "quality-gate.sh",
    "lock": "lock.sh",
    "health": "kimi-health.sh",
}

# Python-implemented subcommands (not .sh forwards): name -> one-line summary.
_PY_SUBCOMMANDS = {
    "init": "scaffold config + contracts + skeleton in a project",
    "contract": "check | diff — governance-contract drift detection",
}


def _usage() -> str:
    lines = ["usage: agentic <subcommand> [args...]", "", "subcommands:"]
    width = max(len(s) for s in list(_SUBCOMMANDS) + list(_PY_SUBCOMMANDS))
    for sub, summary in _PY_SUBCOMMANDS.items():
        lines.append("  {sub:<{w}}  {summary}".format(sub=sub, w=width, summary=summary))
    for sub, wrapper in _SUBCOMMANDS.items():
        lines.append("  {sub:<{w}}  -> scripts/agentic/{wrapper}".format(
            sub=sub, w=width, wrapper=wrapper))
    return "\n".join(lines)


def _main_root() -> Path:
    """Resolve the main repository root, independent of CWD.

    Mirrors the shell wrappers' locate pattern
    (``dirname "$(cd "$(git rev-parse --git-common-dir)" && pwd)"``): from any
    worktree, git-common-dir points at the main repo's ``.git``, whose parent is
    the main repo root that owns ``scripts/agentic/``.
    """
    out = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(
            "agentic: not inside a git repository (git rev-parse failed): "
            + out.stderr.strip()
        )
    common_dir = Path(out.stdout.strip()).resolve()
    return common_dir.parent


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        print(_usage())
        return 0

    sub = argv[0]
    rest = argv[1:]

    if sub in _PY_SUBCOMMANDS:
        if sub == "init":
            from . import init_cmd
            return init_cmd.main(rest)
        if sub == "contract":
            from . import contract_cmd
            return contract_cmd.main(rest)

    wrapper_name = _SUBCOMMANDS.get(sub)
    if wrapper_name is None:
        print("agentic: unknown subcommand '{}'\n".format(sub), file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2

    # (a) Dogfood: a main-repo scripts/agentic/<wrapper>.sh wins when present, so
    # live edits drive real WP flow with no reinstall. Absence of a git repo is
    # NOT fatal here — it just means we fall through to the bundled copy.
    main_repo_wrapper = None
    try:
        candidate = _main_root() / "scripts" / "agentic" / wrapper_name
        if candidate.is_file():
            main_repo_wrapper = candidate
    except RuntimeError:
        main_repo_wrapper = None

    if main_repo_wrapper is not None:
        # A real filesystem path — replace the process for full transparency.
        cmd = ["bash", str(main_repo_wrapper), *rest]
        return _exec_or_run(cmd)

    # (b) Fallback: the copy bundled in the wheel, located via the Python
    # 3.9-safe importlib.resources.path() context manager (NOT the 3.11+
    # files()-only idiom). The context manager may materialize a temp file for
    # zip-imported packages, so run the wrapper *inside* the `with` block via a
    # child process (exec would abandon the cleanup) and keep the resource alive
    # for the wrapper's whole lifetime.
    with contextlib.ExitStack() as stack:
        try:
            bundled = stack.enter_context(
                _resources.path(_WRAPPER_PACKAGE, wrapper_name)
            )
        except (FileNotFoundError, ModuleNotFoundError):
            bundled = None
        if bundled is None or not Path(bundled).is_file():
            # (c) Neither copy exists — clean error, never a traceback.
            print(
                "agentic: wrapper '{}' not found (no main-repo "
                "scripts/agentic/ and none bundled in the package)".format(
                    wrapper_name
                ),
                file=sys.stderr,
            )
            return 2
        completed = subprocess.run(["bash", str(bundled), *rest])
        return completed.returncode


def _exec_or_run(cmd):
    """Replace the current process with ``cmd`` for full stream/exit-code
    transparency; fall back to a child process only if exec is unavailable."""
    try:
        os.execvp("bash", cmd)
    except OSError:
        completed = subprocess.run(cmd)
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

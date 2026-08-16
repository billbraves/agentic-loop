"""agentic init — scaffold a project's agentic-loop governance layer.

Writes ``.agentic/config.toml``, renders the three governance contracts
(``AGENTS.md`` / ``CLAUDE.md`` / ``docs/agentic/OPERATING_MODEL.md``) via the
WP-20 engine with a stamp header, and creates the ``docs/plans/`` +
``.agentic/locks/`` skeleton (the latter gitignored).

Safety: never overwrites an existing ``.agentic/config.toml`` or contract file
unless ``--force`` is given — the file-existence check happens before any write.
Headless-friendly: ``--non-interactive`` uses a neutral default config so init
runs in CI/tests without a TTY.

Stdlib only (argparse/pathlib) plus the WP-20 engine.
"""
import argparse
import sys
from pathlib import Path

from . import contract_cmd, contract_render

# Neutral, tool-agnostic default config for --non-interactive / no-TTY init.
# Role values are generic placeholders a project edits after init; the render
# engine's build_values also supplies defaults, but shipping a real file makes
# the drift-checksum basis explicit and gives the user something to edit.
DEFAULT_CONFIG = """\
# .agentic/config.toml — project adaptation layer.
# Role mappings, path conventions, quality gates and safety rules specific to
# this project. Edit the values below, then run `agentic contract diff --apply`
# to re-render the governance contracts.

[project]
iterations_dir = "docs/plans"
# default_output_language = "English"

[roles]
# role -> adapter name; an array means primary/fallback candidates.
orchestrator = "claude"
developer    = ["kimi", "claude"]
reviewer     = "claude"
consultant   = "codex"

[quality_gate]
# path-prefix -> test command mapping (project-specific rules only).
# [[quality_gate.rule]]
# match = "src/**"
# run   = ["<your test command>"]

[safety]
forbidden_paths  = [".env", ".context/"]
production_paths = []

[review_policy]
min_independence = "strong"

[locks]
owner_source = "env:AGENTIC_SESSION_ID"
ttl_minutes  = 30
"""

GITIGNORE_LOCKS_LINE = ".agentic/locks/"

# Optional local-gate trigger files. These are scaffolded as packaged templates
# and are deliberately NOT part of the managed contract conflict check: a
# pre-existing hook must never block governance scaffolding, and (unlike the
# governed contracts) it must never be overwritten -- not even with --force.
GITHOOKS_REL = ".githooks/pre-push"
INSTALL_SH_REL = "install.sh"

# (template filename, project-relative target, file mode)
_HOOK_TEMPLATES = (
    ("pre-push.tmpl", GITHOOKS_REL, 0o755),
    ("install.sh.tmpl", INSTALL_SH_REL, 0o755),
)

# Per-WP reference skeletons scaffolded under docs/agentic/templates/ so the
# adopting project has a starting point for a new brief + status file. Like the
# hook assets, these are never overwritten once present.
_REFERENCE_TEMPLATES = (
    ("STATUS.json.tmpl", "docs/agentic/templates/STATUS.json", 0o644),
    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
)


def _write_asset(root, tmpl_name, rel, mode):
    """Write one packaged asset once; return ``"written"`` or ``"conflict"``.

    Hook and reference-template assets are user-customizable, so this is
    idempotent in the strict sense: an existing file is never replaced, even
    when ``--force`` was given.
    """
    target = root / rel
    if target.exists():
        return "conflict"
    text = contract_render.load_template(tmpl_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    target.chmod(mode)
    return "written"


def _ensure_gitignore_locks(root):
    """Append the locks-ignore line to ``.gitignore`` unless already present."""
    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    lines = existing.splitlines()
    if GITIGNORE_LOCKS_LINE in lines:
        return False
    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    with gitignore.open("a", encoding="utf-8") as fh:
        fh.write("{}{}\n".format(prefix, GITIGNORE_LOCKS_LINE))
    return True


def run_init(target_dir, *, force, non_interactive, config_path=None):
    root = Path(target_dir)
    pname = contract_cmd.project_name_for(root)

    if not non_interactive and config_path is None and not sys.stdin.isatty():
        print(
            "agentic init: no TTY for interactive config; pass --non-interactive "
            "or --config <path>",
            file=sys.stderr,
        )
        return 2

    # Resolve the config text to write.
    if config_path is not None:
        src = Path(config_path)
        if not src.is_file():
            print("agentic init: --config not found: {}".format(src), file=sys.stderr)
            return 2
        config_text = src.read_text(encoding="utf-8")
    else:
        config_text = DEFAULT_CONFIG

    # Data-loss guard: detect ALL existing managed files up front and refuse
    # before touching the filesystem. brief-frozen "detect existence before
    # writing"; a partial write on the refuse path would corrupt a project that
    # only looks half-initialized. --force opts out.
    cfg_rel = contract_cmd.CONFIG_RELPATH
    managed = [cfg_rel] + [rel for _tmpl, rel in contract_cmd.CONTRACT_FILES]
    if not force:
        conflicts = [rel for rel in managed if (root / rel).is_file()]
        if conflicts:
            for rel in conflicts:
                print(
                    "INIT_REFUSED: {} (exists; use --force to overwrite)".format(rel),
                    file=sys.stderr,
                )
            print(
                "\nagentic init: refused — {} existing managed file(s); this project "
                "looks initialized. Nothing was written. Use `agentic contract "
                "check`/`diff`, or --force.".format(len(conflicts)),
                file=sys.stderr,
            )
            return 1

    # No conflicts (or --force): all writes below are now safe to perform.
    root.mkdir(parents=True, exist_ok=True)
    written = []

    cfg_target = root / cfg_rel
    cfg_target.parent.mkdir(parents=True, exist_ok=True)
    cfg_target.write_text(config_text, encoding="utf-8")
    written.append(cfg_rel)

    # Parse the config just written so rendered contracts match the config the
    # project will actually check against.
    config = contract_cmd.load_config(root)

    for tmpl, rel in contract_cmd.CONTRACT_FILES:
        rendered = contract_render.render_template(tmpl, config, project_name=pname)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        written.append(rel)

    (root / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    (root / ".agentic" / "locks").mkdir(parents=True, exist_ok=True)
    gi_changed = _ensure_gitignore_locks(root)

    # Scaffold the optional local pre-push hook + its opt-in installer. These
    # are additive and never mutate git config: hooksPath is only enabled when
    # the user explicitly runs install.sh. Existing hook/install files are kept
    # untouched and reported as conflicts.
    for tmpl, rel, mode in _HOOK_TEMPLATES:
        outcome = _write_asset(root, tmpl, rel, mode)
        if outcome == "written":
            print("INIT_WROTE: {}".format(rel))
        else:
            print(
                "INIT_HOOK_CONFLICT: {} (exists; not overwritten)".format(rel),
                file=sys.stderr,
            )

    # Reference skeletons for new WPs (brief + status). Scaffolded like the hook
    # assets: written once, never overwritten, not part of the managed-contract
    # conflict check.
    for tmpl, rel, mode in _REFERENCE_TEMPLATES:
        outcome = _write_asset(root, tmpl, rel, mode)
        if outcome == "written":
            print("INIT_WROTE: {}".format(rel))
        else:
            print(
                "INIT_REF_CONFLICT: {} (exists; not overwritten)".format(rel),
                file=sys.stderr,
            )

    for label in written:
        print("INIT_WROTE: {}".format(label))
    print("INIT_SKELETON: docs/plans .agentic/locks docs/agentic/templates")
    if gi_changed:
        print("INIT_GITIGNORE: added {}".format(GITIGNORE_LOCKS_LINE))

    print(
        "\nNext steps:\n"
        "  1. Edit {}/.agentic/config.toml (roles, paths, quality gates).\n"
        "  2. Run `agentic contract diff --apply` to re-render contracts.\n"
        "  3. Run `agentic preflight <status.json>` before dispatching work.\n"
        "  4. Run `./install.sh` to opt in to the local .githooks pre-push gate.".format(
            root
        )
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="agentic init")
    parser.add_argument("--dir", default=".", help="target project directory (default: CWD)")
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite existing config/contract files",
    )
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="use the built-in default config (no TTY prompts)",
    )
    parser.add_argument(
        "--config", default=None,
        help="seed .agentic/config.toml from this file instead of the default",
    )
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    return run_init(
        args.dir,
        force=args.force,
        non_interactive=args.non_interactive,
        config_path=args.config,
    )


if __name__ == "__main__":
    raise SystemExit(main())

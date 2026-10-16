"""agentic contract check / diff — governance-contract drift detection.

Consumes the WP-20 render engine (``contract_render``) read-only. ``check`` is
pure read: it parses each project contract file's stamp header
(``<!-- agentic-contract: template_version=X config_checksum=Y -->``) and
compares it against the current package template version + a checksum recomputed
from the project's ``.agentic/config.toml``. ``diff`` re-renders each contract
from the current template + config and shows a unified diff; only ``--apply``
writes the re-rendered result back.

Stdlib only (argparse/difflib/pathlib/re) plus the WP-20 render engine; TOML
parsing is delegated to the framework's single ratified loader
(``resolve_paths._load_config``). No network, no new third-party dependency.
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

from . import contract_render

# template filename -> project-relative output path
CONTRACT_FILES = (
    ("AGENTS.md.tmpl", "AGENTS.md"),
    ("CLAUDE.md.tmpl", "CLAUDE.md"),
    ("OPERATING_MODEL.md.tmpl", "docs/agentic/OPERATING_MODEL.md"),
)

CONFIG_RELPATH = ".agentic/config.toml"

_STAMP_RE = re.compile(
    r"agentic-contract:\s*template_version=(\S+)\s+config_checksum=(\S+)"
)

# drift exit code (brief: 0=all IN_SYNC, 3=any drift; others reserved for usage)
DRIFT_RC = 3


def project_name_for(target_dir):
    """Project name is the owning repository's name (stable across CWD).

    A linked worktree must render the same contract as the main checkout. Taking
    the target directory's own name renders ``# wp-41-skeleton-gates …`` inside
    ``.worktrees/wp-41-skeleton-gates``, which then fails ``contract check`` in
    the main repo after the merge. ``.git`` is a file (not a directory) in a
    linked worktree and points at the main repo's admin dir, so resolve through
    it to recover the real project name; anything unexpected falls back to the
    directory name.
    """
    resolved = Path(target_dir).resolve()
    git_path = resolved / ".git"
    if git_path.is_file():
        try:
            text = git_path.read_text(encoding="utf-8").strip()
        except OSError:
            return resolved.name
        prefix = "gitdir:"
        if text.startswith(prefix):
            gitdir = Path(text[len(prefix):].strip())
            if not gitdir.is_absolute():
                gitdir = (resolved / gitdir).resolve()
            # .../<main>/.git/worktrees/<name> -> main repo root is 3 levels up
            for parent in gitdir.parents:
                if parent.name == ".git":
                    return parent.parent.name
    return resolved.name


def load_config(target_dir):
    """Parse ``.agentic/config.toml`` under ``target_dir`` into a dict.

    Delegates to the framework's single ratified config loader
    (:func:`resolve_paths._load_config`) rather than opening a second TOML parse
    path, so init/check/diff inherit the framework's established parser behavior
    (a P2 user-ratified decision) instead of making an independent dependency
    choice. Callers guard file existence; a missing file yields ``{}``.
    """
    from . import resolve_paths

    config = resolve_paths._load_config(Path(target_dir))
    return config if config is not None else {}


def expected_checksum(config, *, project_name):
    """Checksum the current config would stamp — same basis as the engine."""
    values = contract_render.build_values(config, project_name=project_name)
    return contract_render.canonical_checksum(values)


def parse_stamp(text):
    """Return ``(template_version, config_checksum)`` from a contract's header.

    Returns ``None`` if no well-formed stamp header is present.
    """
    match = _STAMP_RE.search(text)
    if not match:
        return None
    return match.group(1), match.group(2)


def classify(path, *, cur_version, cur_checksum):
    """Classify one contract file's drift state (pure read)."""
    if not path.is_file():
        return "MISSING"
    stamp = parse_stamp(path.read_text(encoding="utf-8"))
    if stamp is None:
        return "MALFORMED"
    hv, hc = stamp
    if hv != cur_version:
        return "TEMPLATE_OUTDATED"
    if hc != cur_checksum:
        return "CONFIG_DRIFT"
    return "IN_SYNC"


def _resolve_context(target_dir):
    """Shared setup: (config, project_name, cur_version, cur_checksum)."""
    config = load_config(target_dir)
    pname = project_name_for(target_dir)
    cur_version = contract_render.CONTRACT_TEMPLATE_VERSION
    cur_checksum = expected_checksum(config, project_name=pname)
    return config, pname, cur_version, cur_checksum


def cmd_check(target_dir):
    root = Path(target_dir)
    cfg_path = root / CONFIG_RELPATH
    if not cfg_path.is_file():
        print(
            "agentic contract check: no {} under {} (run `agentic init` first)".format(
                CONFIG_RELPATH, root
            ),
            file=sys.stderr,
        )
        return 2

    _, _, cur_version, cur_checksum = _resolve_context(target_dir)

    drift = False
    for _tmpl, rel in CONTRACT_FILES:
        state = classify(
            root / rel, cur_version=cur_version, cur_checksum=cur_checksum
        )
        print("CONTRACT_CHECK: {} {}".format(rel, state))
        if state != "IN_SYNC":
            drift = True
    return DRIFT_RC if drift else 0


def cmd_diff(target_dir, *, apply):
    root = Path(target_dir)
    cfg_path = root / CONFIG_RELPATH
    if not cfg_path.is_file():
        print(
            "agentic contract diff: no {} under {} (run `agentic init` first)".format(
                CONFIG_RELPATH, root
            ),
            file=sys.stderr,
        )
        return 2

    config, pname, _, _ = _resolve_context(target_dir)

    any_changed = False
    for tmpl, rel in CONTRACT_FILES:
        target = root / rel
        rendered = contract_render.render_template(
            tmpl, config, project_name=pname
        )
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if rendered == current:
            print("CONTRACT_DIFF: {} unchanged".format(rel))
            continue

        any_changed = True
        diff_lines = difflib.unified_diff(
            current.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile="a/{}".format(rel),
            tofile="b/{}".format(rel),
        )
        sys.stdout.writelines(diff_lines)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
        print("CONTRACT_DIFF: {} changed".format(rel))

        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            print("CONTRACT_APPLIED: {}".format(rel))

    if not any_changed and not apply:
        return 0
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="agentic contract")
    sub = parser.add_subparsers(dest="action")

    p_check = sub.add_parser("check", help="report contract drift (read-only)")
    p_check.add_argument("--dir", default=".", help="project directory (default: CWD)")

    p_diff = sub.add_parser("diff", help="show re-render diff; --apply to write back")
    p_diff.add_argument("--dir", default=".", help="project directory (default: CWD)")
    p_diff.add_argument(
        "--apply", action="store_true",
        help="write the re-rendered contracts back (updates stamp header)",
    )
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.action == "check":
        return cmd_check(args.dir)
    if args.action == "diff":
        return cmd_diff(args.dir, apply=args.apply)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

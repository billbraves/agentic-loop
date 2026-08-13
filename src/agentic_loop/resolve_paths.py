#!/usr/bin/env python3
"""INV-4 root resolver + optional .agentic/config.toml reader.

Provides the four roots the agentic framework must distinguish (main_repo,
current_worktree, package, iterations_dir). Bash scripts call this instead of
open-coding `git rev-parse` incantations, so INV-4 is enforced in one place.

Config is OPTIONAL: when .agentic/config.toml is absent, iterations_dir falls
back to the built-in default (docs/plans) and no TOML library is imported (keeps
the no-config path working on the bare python3, which may be <3.11).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ITERATIONS_DIR = "docs/plans"

DEFAULT_ROLES = {
    "orchestrator": "claude",
    "developer": ["kimi", "claude"],
    "reviewer": "claude",
    "consultant": "codex",
}

DEFAULT_QUALITY_GATE = {
    "rule": [
        {"match": "packages/engine/**", "run": ["uv run pytest packages/engine/tests -q"]},
        {"match": "packages/data-app/**", "run": ["uv run pytest packages/data-app/tests -q"]},
    ]
}

DEFAULT_SAFETY = {
    "forbidden_paths": ["profiles/", ".env", ".context/"],
    "production_paths": ["~/.hermes/profiles/baofu-data"],
}

DEFAULT_REVIEW_POLICY = {
    "hard_rules": [
        "禁止为通过测试而偷改信号语义、阈值、估值规则或自动交易行为。",
    ],
    "min_independence": "strong",
}

DEFAULT_LOCKS = {
    "owner_source": "env:CLAUDE_CODE_SESSION_ID",
    "ttl_minutes": 30,
}

DEFAULT_ADAPTERS = {
    "names": ["claude", "codex", "kimi", "hermes"],
}

DEFAULT_PROJECT = {
    "iterations_dir": DEFAULT_ITERATIONS_DIR,
}

# Exposed config sections and their built-in safe defaults (fail-closed).
CONFIG_SECTIONS: dict[str, dict[str, Any]] = {
    "project": DEFAULT_PROJECT,
    "roles": DEFAULT_ROLES,
    "quality_gate": DEFAULT_QUALITY_GATE,
    "safety": DEFAULT_SAFETY,
    "review_policy": DEFAULT_REVIEW_POLICY,
    "locks": DEFAULT_LOCKS,
    "adapters": DEFAULT_ADAPTERS,
}


def _fail(reason: str) -> "NoReturn":
    print(f"RESOLVE_FAIL: {reason}", file=sys.stderr)
    raise SystemExit(2)


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        _fail(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def main_repo() -> Path:
    common = _git("rev-parse", "--git-common-dir")
    return Path(common).resolve().parent


def current_worktree() -> Path:
    return Path(_git("rev-parse", "--show-toplevel")).resolve()


def package_root() -> Path:
    return Path(__file__).resolve().parent


def _tomllib() -> Any:
    """Lazy-import a TOML parser. tomllib is py3.11+; fall back to tomli."""
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    return tomllib


def _load_config(repo: Path) -> dict[str, Any] | None:
    """Read .agentic/config.toml if it exists; otherwise return None.

    Import of any TOML library only happens when the file exists, preserving the
    no-config compatibility guarantee for bare python3 <3.11.
    """
    config_path = repo / ".agentic" / "config.toml"
    if not config_path.is_file():
        return None
    tomllib = _tomllib()
    with open(config_path, "rb") as fh:
        return tomllib.load(fh)  # type: ignore[attr-defined]


def _is_valid_config_value(key: str, value: Any, default: Any) -> bool:
    """Reject values that would silently relax a built-in safe default.

    Missing, None, empty string, empty collection, or type-mismatched values are
    all treated as invalid so that fail-closed defaults are preserved.
    """
    if value is None:
        return False
    if isinstance(default, str):
        return isinstance(value, str) and value != ""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        # bool is a subclass of int in Python; disallow it for int defaults.
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, (list, tuple)):
        return isinstance(value, (list, tuple)) and len(value) > 0
    if isinstance(default, dict):
        return isinstance(value, dict) and len(value) > 0
    # For any other default shape, accept the raw value as-is.
    return True


def _read_config_section(repo: Path, section: str) -> dict[str, Any]:
    """Return a config section merged over its built-in safe defaults.

    Missing config, missing section, malformed section value, or a key present
    but with an empty/None/type-mismatched value all fall back to the built-in
    safe defaults (fail-closed). The reader never silently returns an empty or
    relaxed value as a legitimate configuration.
    """
    defaults = CONFIG_SECTIONS.get(section, {})
    data = _load_config(repo) or {}
    if not isinstance(data, dict):
        return dict(defaults)
    raw_section = data.get(section)
    if not isinstance(raw_section, dict):
        return dict(defaults)

    merged: dict[str, Any] = {}
    # Preserve unknown keys (forward compatibility); validate known keys.
    for key, value in raw_section.items():
        if key in defaults:
            merged[key] = (
                defaults[key]
                if not _is_valid_config_value(key, value, defaults[key])
                else value
            )
        else:
            merged[key] = value
    # Fill any missing keys from defaults.
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = value
    return merged


def get_config_section(repo: Path, section: str) -> dict[str, Any]:
    """Read-only public accessor for a config section."""
    return _read_config_section(repo, section)


def get_roles(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "roles")


def get_quality_gate(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "quality_gate")


def get_safety(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "safety")


def get_review_policy(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "review_policy")


def get_locks(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "locks")


def get_adapters(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "adapters")


def _read_iterations_dir_rel(repo: Path) -> str:
    """Return the iterations_dir relative path, from config if present else default."""
    project = _read_config_section(repo, "project")
    value = project.get("iterations_dir")
    return value if value else DEFAULT_ITERATIONS_DIR


def iterations_dir() -> Path:
    repo = main_repo()
    rel = _read_iterations_dir_rel(repo)
    p = Path(rel)
    return p.resolve() if p.is_absolute() else (repo / rel).resolve()


ROOTS = {
    "main_repo": main_repo,
    "current_worktree": current_worktree,
    "package": package_root,
    "iterations_dir": iterations_dir,
}


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--root" and argv[1] in ROOTS:
        print(ROOTS[argv[1]]())
        return 0
    if len(argv) == 2 and argv[0] == "--config-section" and argv[1] in CONFIG_SECTIONS:
        print(json.dumps(_read_config_section(main_repo(), argv[1]), ensure_ascii=False))
        return 0
    # 任何其它 argv(含非法 --config-section 形态)一律回落 base 冻结 root usage(WP-04)。
    print(f"usage: {Path(sys.argv[0]).name} --root <{'|'.join(ROOTS)}>", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

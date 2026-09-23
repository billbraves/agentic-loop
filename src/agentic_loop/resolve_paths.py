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

DEFAULT_GATE = {
    "blocking": True,
    "enabled": True,
    "apply": "first_match",
}

# Frozen enum domains for the unified ``[[gate]]`` schema (brief Required 1).
# ``kind``/``stage`` have no built-in safe default; an illegal value is dropped
# by ``get_gates`` (see ``_gate_has_valid_enums``) rather than guessed. ``apply``
# has a safe default (first_match), so an illegal value falls back to it.
VALID_GATE_KINDS = {"command", "codex", "qoder_security", "qoder_judge"}
VALID_GATE_STAGES = {"pre_review", "merge"}
VALID_GATE_APPLY = {"first_match", "overlay"}

DEFAULT_QODER_SECURITY_LEVEL = "L3"

DEFAULT_AUTONOMY = {
    "default_mode": "ask",
    "ultra_auto": [
        "local_edit", "test_run", "worktree_lifecycle",
        "dispatch_developer", "review", "merge_gate",
        "local_merge_no_ff", "finalize_merge",
    ],
    "always_stop": [
        "push", "feishu_send", "production_write",
        "cron_change", "release_deploy", "credential_rw",
        "irreversible_git",
    ],
    "soft_limit_signals": ["frozen_hard", "rework_twice", "circuit_breaker"],
}

DEFAULT_SAFETY = {
    "forbidden_paths": [".env", ".context/"],
    "production_paths": [],
}

DEFAULT_REVIEW_POLICY = {
    "hard_rules": [],
    "min_independence": "strong",
}

DEFAULT_LOCKS = {
    "owner_source": "env:CLAUDE_CODE_SESSION_ID",
    "ttl_minutes": 30,
}

DEFAULT_ADAPTERS = {
    "names": ["claude", "codex", "kimi"],
}

DEFAULT_PROJECT = {
    "iterations_dir": DEFAULT_ITERATIONS_DIR,
}

# Exposed config sections and their built-in safe defaults (fail-closed).
CONFIG_SECTIONS: dict[str, dict[str, Any]] = {
    "project": DEFAULT_PROJECT,
    "roles": DEFAULT_ROLES,
    "autonomy": DEFAULT_AUTONOMY,
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


def get_autonomy(repo: Path | None = None) -> dict[str, Any]:
    return get_config_section(repo or main_repo(), "autonomy")


def _normalize_gate(gate: dict[str, Any]) -> dict[str, Any]:
    """Apply per-gate defaults (blocking/enabled/apply) and kind defaults.

    The reader only reads; it enforces the enum constraint only for ``apply``,
    the one gate field with a built-in safe default: a value outside
    ``{first_match, overlay}`` falls back to ``first_match`` (fail-closed), just
    like a missing/empty/type-mismatched value. ``kind``/``stage`` have no safe
    default here, so their enum validation lives in ``get_gates`` (see
    ``_gate_has_valid_enums``), which drops an illegal entry instead of guessing
    a legal enum. ``rule`` (kind=command) is preserved verbatim.
    """
    out = dict(gate)
    for key, default in DEFAULT_GATE.items():
        if not _is_valid_config_value(key, out.get(key), default):
            out[key] = default
    # fail-closed: an illegal apply value must never silently relax the built-in
    # safe default by being read through verbatim.
    if out.get("apply") not in VALID_GATE_APPLY:
        out["apply"] = DEFAULT_GATE["apply"]
    if out.get("kind") == "qoder_security":
        level = out.get("level")
        if not _is_valid_config_value("level", level, DEFAULT_QODER_SECURITY_LEVEL):
            out["level"] = DEFAULT_QODER_SECURITY_LEVEL
    return out


def _gate_has_valid_enums(gate: dict[str, Any]) -> bool:
    """True when a gate entry's ``kind`` and ``stage`` are both valid enums.

    Fail-closed semantics (chosen): an entry whose ``kind`` is not one of the
    four frozen kinds, or whose ``stage`` is not one of ``{pre_review, merge}``,
    is DROPPED from ``get_gates()``. Dropping (rather than marking unavailable)
    keeps the normalized result a plain list of usable gates, so any caller that
    filters on kind/stage — ``get_command_gate`` today, a future runner tomorrow
    — can never mis-select an illegal entry. We never guess an illegal value into
    a legal enum; an illegal entry simply does not exist in the normalized view.
    """
    return gate.get("kind") in VALID_GATE_KINDS and gate.get("stage") in VALID_GATE_STAGES


def get_gates(repo: Path | None = None) -> list[dict[str, Any]]:
    """Return the unified ``[[gate]]`` array (defaults + enum validation applied).

    Entries whose ``kind`` or ``stage`` is not a valid enum value are dropped
    (fail-closed), so an illegal gate can never reach ``get_command_gate`` or any
    downstream runner. Returns ``[]`` when there is no config, no ``gate`` array,
    or no usable entry.
    """
    data = _load_config(repo or main_repo()) or {}
    if not isinstance(data, dict):
        return []
    raw = data.get("gate")
    if not isinstance(raw, list):
        return []
    return [
        _normalize_gate(g)
        for g in raw
        if isinstance(g, dict) and _gate_has_valid_enums(g)
    ]


def get_command_gate(repo: Path | None = None) -> dict[str, Any] | None:
    """Return the first command-kind gate for the pre_review stage, if any."""
    for gate in get_gates(repo):
        if gate.get("kind") == "command" and gate.get("stage") == "pre_review":
            return gate
    return None


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


def get_providers(repo: Path | None = None) -> dict[str, Any]:
    """Return the raw ``[providers]`` table (empty dict when absent)."""
    data = _load_config(repo or main_repo()) or {}
    if not isinstance(data, dict):
        return {}
    providers = data.get("providers")
    return providers if isinstance(providers, dict) else {}


def get_roles_raw(repo: Path | None = None) -> dict[str, Any]:
    """Return the RAW ``[roles]`` table without safe-default merging.

    Unlike ``get_roles()``, this preserves table-form role values (dict), which
    the safe-default validator would otherwise reject and revert to a default.
    """
    data = _load_config(repo or main_repo()) or {}
    if not isinstance(data, dict):
        return {}
    roles = data.get("roles")
    return roles if isinstance(roles, dict) else {}


def _first_candidate(value: Any) -> str | None:
    """Extract the adapter name from a role value (str / list / table)."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item:
                return item
        return None
    if isinstance(value, dict):
        adapter = value.get("adapter")
        return adapter if isinstance(adapter, str) and adapter else None
    return None


def resolve_role_binding(
    role: str, repo: Path | None = None
) -> tuple[str, "Any"]:
    """Resolve a role to ``(adapter_name, ProviderBinding | None)``.

    Falls back to DEFAULT_ROLES when the role is absent. Returns binding=None
    (zero-regression) when the role value is legacy str/list, carries no
    ``provider``, or the ``[providers]`` section is missing.
    """
    from agentic_loop.provider_binding import build_binding

    repo = repo or main_repo()
    raw_roles = get_roles_raw(repo)
    value: Any = raw_roles.get(role, DEFAULT_ROLES.get(role))

    adapter = _first_candidate(value)
    if adapter is None:
        # Nothing usable; degrade to the built-in default for this role.
        adapter = _first_candidate(DEFAULT_ROLES.get(role)) or "claude"

    provider_name: str | None = None
    if isinstance(value, dict):
        pn = value.get("provider")
        provider_name = pn if isinstance(pn, str) and pn else None

    if provider_name is None:
        return adapter, None

    providers = get_providers(repo)
    provider_cfg = providers.get(provider_name)
    if not isinstance(provider_cfg, dict):
        return adapter, None

    provider_cfg = dict(provider_cfg)
    provider_cfg["_name"] = provider_name
    binding = build_binding(adapter=adapter, provider_cfg=provider_cfg)
    return adapter, binding


def resolve_role_fallback_binding(
    role: str, repo: Path | None = None
) -> "Any":
    """Resolve the OPTIONAL quota-fallback binding for ``role``.

    Reads ``roles.<role>`` dict's optional ``fallback_provider`` key and builds a
    ProviderBinding from that provider's config. Returns ``None`` (zero-regression)
    when the role is not a dict, carries no ``fallback_provider``, or the provider
    section is missing/invalid. Never raises for provider-config shape errors;
    a malformed config FILE is a pre-existing failure shared with
    ``resolve_role_binding`` (escapes from ``get_roles_raw`` outside the try),
    out of scope for this resolver.
    """
    from agentic_loop.provider_binding import build_binding

    repo = repo or main_repo()
    raw_roles = get_roles_raw(repo)
    value: Any = raw_roles.get(role, DEFAULT_ROLES.get(role))
    if not isinstance(value, dict):
        return None
    fp = value.get("fallback_provider")
    if not isinstance(fp, str) or not fp:
        return None
    adapter = _first_candidate(value)
    if adapter is None:
        return None
    providers = get_providers(repo)
    provider_cfg = providers.get(fp)
    if not isinstance(provider_cfg, dict):
        return None
    provider_cfg = dict(provider_cfg)
    provider_cfg["_name"] = fp
    try:
        return build_binding(adapter=adapter, provider_cfg=provider_cfg)
    except Exception as exc:
        # INV-3 强化（codex impl-rev1 #1 / brief rev7 §R1）：fallback 路径对任意
        # provider 配置形状（selectors 为字符串/列表等触发 build_binding 内任意
        # 异常）一律回落 None，绝不抛进派发主链。窄作用域：仅包 build_binding 调用；
        # 一行脱敏诊断（固定文案 + 异常类名），绝不含 config 原文/路径/密钥。
        print(
            "resolve_role_fallback_binding: provider config invalid "
            f"({type(exc).__name__}); falling back to no quota fallback",
            file=sys.stderr,
        )
        return None


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
    if len(argv) == 2 and argv[0] == "--config-section":
        section = argv[1]
        if section == "gate":
            print(json.dumps(get_command_gate() or {"rule": []}, ensure_ascii=False))
            return 0
        if section in CONFIG_SECTIONS:
            print(json.dumps(_read_config_section(main_repo(), section), ensure_ascii=False))
            return 0
    # 任何其它 argv(含非法 --config-section 形态)一律回落 base 冻结 root usage(WP-04)。
    print(f"usage: {Path(sys.argv[0]).name} --root <{'|'.join(ROOTS)}>", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

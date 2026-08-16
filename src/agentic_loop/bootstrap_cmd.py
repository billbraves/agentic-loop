"""agentic bootstrap — 探测/安装三签 CLI、校验 key、真实注入探针。

本轮只覆盖 claude/kimi/codex（无 qoder，注入通道未闭合）。安装来源写死；
key 只校验在场，绝不代填/落盘；已装 CLI 不升级但必须过真实注入探针，
过不了则 fail-closed。dry-run 只打印，不安装、不发 sentinel。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from agentic_loop.adapters.claude import ClaudeAdapter
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.adapters.kimi import KimiAdapter
from agentic_loop.provider_binding import ProviderBinding
from agentic_loop.resolve_paths import main_repo, resolve_role_binding

# 安装来源写死，不接受运行时变量拼接（供应链风险，spec §3.3 安装契约）。
INSTALL_COMMANDS: dict[str, list[str]] = {
    "codex": ["brew", "install", "--cask", "codex"],
    "kimi": ["uv", "tool", "install", "kimi-cli"],
    "claude": ["npm", "install", "-g", "@anthropic-ai/claude-code"],
}

ADAPTER_CLASSES: dict[str, type] = {
    "claude": ClaudeAdapter,
    "kimi": KimiAdapter,
    "codex": CodexAdapter,
}

_BIN_ENV = {"claude": "CLAUDE_BIN", "kimi": "KIMI_BIN", "codex": "CODEX_BIN"}

# role -> 该角色的 adapter（本轮固定三签映射的反查用不到，直接遍历 roles）。
_ROLES = ("developer", "reviewer", "consultant")


@dataclass
class BootstrapPlan:
    to_install: list[str] = field(default_factory=list)
    to_probe: list[tuple[str, ProviderBinding | None]] = field(default_factory=list)
    missing_key: list[str] = field(default_factory=list)


def _adapter_bindings(repo: Path) -> dict[str, ProviderBinding | None]:
    """从三个角色解析出 {adapter_name: binding}（去重，本轮三签各一）。"""
    out: dict[str, ProviderBinding | None] = {}
    for role in _ROLES:
        adapter, binding = resolve_role_binding(role, repo=repo)
        # 后出现的 binding 不覆盖已解析的（同一 adapter 名只需一份 binding）。
        out.setdefault(adapter, binding)
    return out


def plan_bootstrap(repo: Path, *, adapter_names: list[str]) -> BootstrapPlan:
    """纯函数：探测每个 CLI 是否已装 + 收集 binding + 缺失 key。"""
    plan = BootstrapPlan()
    bindings = _adapter_bindings(repo)
    seen_key_env: set[str] = set()
    for name in adapter_names:
        binding = bindings.get(name)
        if shutil.which(_bin_name(name)) is None:
            plan.to_install.append(name)
        else:
            plan.to_probe.append((name, binding))
        if binding is not None and binding.api_key_env not in seen_key_env:
            seen_key_env.add(binding.api_key_env)
            if not os.environ.get(binding.api_key_env):
                plan.missing_key.append(binding.api_key_env)
    return plan


def _bin_name(adapter: str) -> str:
    return os.environ.get(_BIN_ENV[adapter], adapter)


def _run_install(adapter: str) -> int:
    cmd = INSTALL_COMMANDS[adapter]
    print(f"BOOTSTRAP_INSTALL: {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    return proc.returncode


def _probe_one(adapter: str, binding: ProviderBinding | None) -> bool:
    cls = ADAPTER_CLASSES[adapter]
    kwargs = {f"{adapter}_bin": _bin_name(adapter), "binding": binding}
    inst = cls(**kwargs)
    return inst.probe_injection()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentic bootstrap")
    p.add_argument("--dry-run", action="store_true",
                   help="只打印将执行的安装命令 + 将探针的 CLI，不安装、不发请求")
    p.add_argument("--yes", action="store_true",
                   help="免除安装动作的逐个确认（不豁免真实注入探针）")
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)

    repo = main_repo()
    adapter_names = ["claude", "kimi", "codex"]     # 本轮固定三签
    plan = plan_bootstrap(repo, adapter_names=adapter_names)

    if args.dry_run:
        for name in plan.to_install:
            print(f"BOOTSTRAP_WOULD_INSTALL: {' '.join(INSTALL_COMMANDS[name])}")
        for name, _b in plan.to_probe:
            print(f"BOOTSTRAP_WOULD_PROBE: {name}")
        if plan.missing_key:
            print(f"BOOTSTRAP_MISSING_KEY: {', '.join(plan.missing_key)}")
        return 0

    # key 不在场 → 报错停下，绝不代填/落盘。
    if plan.missing_key:
        for env in plan.missing_key:
            print(
                f"BOOTSTRAP_ERROR: required env {env} not set. "
                f"Set it once in your shell (e.g. `export {env}=sk-...`) and "
                "re-run. The key is read from the env var named in "
                ".agentic/config.toml [providers.<name>].api_key_env — it is "
                "never written to disk or argv.",
                file=sys.stderr,
            )
        return 2

    # 安装缺失（逐个确认，除非 --yes）。信任确认任何档位保留。
    for name in plan.to_install:
        cmd = INSTALL_COMMANDS[name]
        if not args.yes:
            print(f"BOOTSTRAP_CONFIRM: will run `{' '.join(cmd)}` to install {name}. "
                  "Re-run with --yes to proceed.", file=sys.stderr)
            return 3
        rc = _run_install(name)
        if rc != 0:
            print(f"BOOTSTRAP_ERROR: install of {name} failed (rc={rc}); "
                  "no half-installed state.", file=sys.stderr)
            return 2
        # 装完后纳入探针集合（binding 与已装同名一致）。
        _, binding = resolve_role_binding_for_adapter(repo, name)
        plan.to_probe.append((name, binding))

    # 逐个真实注入探针（已装 + 刚装的都跑；fail-closed）。
    ok = True
    for name, binding in plan.to_probe:
        passed = _probe_one(name, binding)
        if passed:
            print(f"BOOTSTRAP_PROBE_OK: {name}")
        else:
            ok = False
            print(f"BOOTSTRAP_ERROR: CLI_INSTALLED_BUT_INCOMPATIBLE: {name} "
                  "failed real-injection probe; will NOT auto-upgrade. "
                  "Upgrade it manually and re-run bootstrap.", file=sys.stderr)
    if not ok:
        return 2

    print("BOOTSTRAP_OK: all three signatures pass real-injection probe.")
    return 0


def resolve_role_binding_for_adapter(repo: Path, adapter: str):
    """反查某 adapter 名对应的 binding（遍历角色取首个匹配）。"""
    for role in _ROLES:
        a, b = resolve_role_binding(role, repo=repo)
        if a == adapter:
            return a, b
    return adapter, None


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""agentic provider — switch codex/kimi/claude default provider (official ↔ DeepSeek).

Background: agentic's DeepSeek is a runtime injection (only when agentic dispatches
gate/redispatch/review); it does not touch each CLI's global config. This command
switches what the *manually-run* codex/kimi/claude use, so when an official key hits
its quota (codex 5h / kimi weekly) you can flip to DeepSeek in one step.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

CODEX_CFG = Path(os.environ.get("CODEX_CFG", os.path.expanduser("~/.codex/config.toml")))
KIMI_CFG = Path(os.environ.get("KIMI_CFG", os.path.expanduser("~/.kimi/config.toml")))
CLAUDE_CFG = Path(os.environ.get("CLAUDE_CFG", os.path.expanduser("~/.claude/settings.json")))
CLAUDE_BAK = Path(str(CLAUDE_CFG) + ".official.bak")


def _deepseek_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    zshrc = Path(os.path.expanduser("~/.zshrc"))
    if zshrc.is_file():
        for line in zshrc.read_text(encoding="utf-8").splitlines():
            if line.startswith("export DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1]
    return ""


def _replace(path: Path, pattern: str, repl: str) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    path.write_text(
        re.sub(pattern, repl, text, count=1, flags=re.MULTILINE),
        encoding="utf-8",
    )


def _switch_codex_deepseek():
    _replace(CODEX_CFG, r'^model = "gpt-5.5"', 'model = "deepseek-v4-pro"')


def _switch_codex_official():
    _replace(CODEX_CFG, r'^model = "deepseek-v4-pro"', 'model = "gpt-5.5"')


def _switch_kimi_deepseek():
    _replace(KIMI_CFG, r'^default_model = "kimi-code/kimi-for-coding"',
             'default_model = "deepseek/v4-pro"')


def _switch_kimi_official():
    _replace(KIMI_CFG, r'^default_model = "deepseek/v4-pro"',
             'default_model = "kimi-code/kimi-for-coding"')


def _switch_claude_deepseek():
    if not CLAUDE_CFG.is_file():
        return
    if not CLAUDE_BAK.exists():
        shutil.copy(CLAUDE_CFG, CLAUDE_BAK)  # 备份官方/中转配置，供切回
    data = json.loads(CLAUDE_CFG.read_text(encoding="utf-8"))
    env = data.setdefault("env", {})
    env["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
    env["ANTHROPIC_AUTH_TOKEN"] = _deepseek_key()
    env["ANTHROPIC_MODEL"] = "deepseek-v4-pro"
    env.pop("ANTHROPIC_API_KEY", None)  # DeepSeek 走 AUTH_TOKEN
    CLAUDE_CFG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _switch_claude_official():
    if CLAUDE_BAK.exists():
        shutil.copy(CLAUDE_BAK, CLAUDE_CFG)


def _grep_line(path: Path, prefix: str) -> str:
    if not path.is_file():
        return "(无)"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.strip()
    return "(未找到)"


def _claude_status() -> str:
    if not CLAUDE_CFG.is_file():
        return "(无)"
    try:
        data = json.loads(CLAUDE_CFG.read_text(encoding="utf-8"))
        env = data.get("env", {})
        return "ANTHROPIC_MODEL={} BASE_URL={}".format(
            env.get("ANTHROPIC_MODEL", "?"), env.get("ANTHROPIC_BASE_URL", "?")
        )
    except Exception:
        return "(解析失败)"


def _status() -> str:
    return "\n".join(
        [
            "codex:  " + _grep_line(CODEX_CFG, "model"),
            "kimi:   " + _grep_line(KIMI_CFG, "default_model"),
            "claude: " + _claude_status(),
        ]
    )


# target -> (callables, message)
_SWITCHES = {
    "deepseek": (
        (_switch_codex_deepseek, _switch_kimi_deepseek, _switch_claude_deepseek),
        "codex+kimi+claude 已切 DeepSeek",
    ),
    "official": (
        (_switch_codex_official, _switch_kimi_official, _switch_claude_official),
        "codex+kimi+claude 已切回官方",
    ),
    "codex-deepseek": ((_switch_codex_deepseek,), "codex → DeepSeek"),
    "codex-official": ((_switch_codex_official,), "codex → 官方"),
    "kimi-deepseek": ((_switch_kimi_deepseek,), "kimi → DeepSeek"),
    "kimi-official": ((_switch_kimi_official,), "kimi → 官方"),
    "claude-deepseek": ((_switch_claude_deepseek,), "claude → DeepSeek"),
    "claude-official": ((_switch_claude_official,), "claude → 官方"),
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    target = argv[0] if argv else "status"

    if target in ("status", "show"):
        print(_status())
        return 0

    if target in _SWITCHES:
        callables, msg = _SWITCHES[target]
        for fn in callables:
            fn()
        print(msg)
        return 0

    print(
        "usage: agentic provider [deepseek|official|codex-deepseek|kimi-deepseek|claude-deepseek|…|status]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

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
import subprocess
import sys
from pathlib import Path

CODEX_CFG = Path(os.environ.get("CODEX_CFG", os.path.expanduser("~/.codex/config.toml")))
KIMI_CFG = Path(os.environ.get("KIMI_CFG", os.path.expanduser("~/.kimi/config.toml")))
CLAUDE_CFG = Path(os.environ.get("CLAUDE_CFG", os.path.expanduser("~/.claude/settings.json")))
CLAUDE_BAK = Path(str(CLAUDE_CFG) + ".official.bak")
CODEX_BAK = Path(str(CODEX_CFG) + ".official.bak")
KIMI_BAK = Path(str(KIMI_CFG) + ".official.bak")


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


def _replace(path: Path, pattern: str, repl: str) -> bool:
    """替换首个匹配；返回是否真正发生了改动（文件不存在返回 False）。"""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE)
    if n == 0:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def _find_model(path: Path, key: str) -> str:
    """返回 config 里 `key = "..."` 的当前值；找不到返回空串。"""
    if not path.is_file():
        return ""
    pattern = re.compile(r'^{} = "([^"]*)"'.format(re.escape(key)))
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            return m.group(1)
    return ""


# Codex/Kimi 的官方 model 名会随上游升级而变（如 gpt-5.5 -> gpt-5.6-sol），
# 因此不硬编码：切 DeepSeek 时把当前 model 备份到 .official.bak，切回时从备份还原。

def _switch_codex_deepseek() -> bool:
    cur = _find_model(CODEX_CFG, "model")
    if not cur or cur == "deepseek-v4-pro":
        return False
    CODEX_BAK.write_text(cur + "\n", encoding="utf-8")
    return _replace(CODEX_CFG, r'^model = ".*"', 'model = "deepseek-v4-pro"')


def _switch_codex_official() -> bool:
    if not CODEX_BAK.exists():
        return False
    official = CODEX_BAK.read_text(encoding="utf-8").strip()
    if not official:
        return False
    return _replace(CODEX_CFG, r'^model = ".*"', 'model = "{}"'.format(official))


def _switch_kimi_deepseek() -> bool:
    cur = _find_model(KIMI_CFG, "default_model")
    if not cur or cur == "deepseek/v4-pro":
        return False
    KIMI_BAK.write_text(cur + "\n", encoding="utf-8")
    return _replace(KIMI_CFG, r'^default_model = ".*"',
                    'default_model = "deepseek/v4-pro"')


def _switch_kimi_official() -> bool:
    if not KIMI_BAK.exists():
        return False
    official = KIMI_BAK.read_text(encoding="utf-8").strip()
    if not official:
        return False
    return _replace(KIMI_CFG, r'^default_model = ".*"',
                    'default_model = "{}"'.format(official))


def _switch_claude_deepseek() -> bool:
    if not CLAUDE_CFG.is_file():
        return False
    if not CLAUDE_BAK.exists():
        shutil.copy(CLAUDE_CFG, CLAUDE_BAK)  # 备份官方/中转配置，供切回
    data = json.loads(CLAUDE_CFG.read_text(encoding="utf-8"))
    env = data.setdefault("env", {})
    env["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
    env["ANTHROPIC_AUTH_TOKEN"] = _deepseek_key()
    env["ANTHROPIC_MODEL"] = "deepseek-v4-pro"
    env.pop("ANTHROPIC_API_KEY", None)  # DeepSeek 走 AUTH_TOKEN
    CLAUDE_CFG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def _switch_claude_official() -> bool:
    if CLAUDE_BAK.exists():
        shutil.copy(CLAUDE_BAK, CLAUDE_CFG)
        return True
    return False


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


def _running_kimi_processes() -> list[str]:
    """Best-effort 检测运行中的 kimi 进程（ps 不可用时返回空）。

    用 ``ps`` 而非 ``pgrep``：macOS 的 pgrep 匹配不到 comm 带空格的进程
    （如 kimi CLI 的 ``Kimi Code``）。命令行里带 "agentic" 的（即本命令自身）
    会被排除。
    """
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,args="],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
    except OSError:
        return []
    hits = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        low = line.lower()
        if "kimi" in low and "agentic" not in low:
            hits.append(line)
    return hits


def _warn_if_kimi_running() -> None:
    """运行中的 kimi 会话持有启动时的内存配置，/model、登录刷新等时机会整盘
    回写 ~/.kimi/config.toml，覆盖刚才的切换；且其本身也不会读到新配置。"""
    hits = _running_kimi_processes()
    if not hits:
        return
    print(
        "⚠️ 检测到正在运行的 kimi 进程：\n  " + "\n  ".join(hits) + "\n"
        "运行中的 kimi 会话会在 /model、登录刷新等时机用内存配置整盘回写 "
        f"{KIMI_CFG}，可能覆盖刚才的切换；该会话本身也不会读到新配置。\n"
        "请先退出所有 kimi 会话再执行本命令，或在每个会话里用 /model 切换。",
        file=sys.stderr,
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
        # 必须全部执行完再汇总：any(fn() for fn in ...) 会在首个 True 处短路，
        # 跳过排在后面的切换（曾导致 codex 成功后 kimi/claude 从未执行）。
        results = [fn() for fn in callables]
        failed = [fn for fn, ok in zip(callables, results) if not ok]
        if not failed:
            print(msg)
        else:
            if any(results):
                print(msg)  # 部分成功：仍提示，但下面逐项列出未切换的
            else:
                print(msg, file=sys.stderr)
                print("provider: 未修改（已处于目标状态，或未找到匹配的 model 行）", file=sys.stderr)
            for fn in failed:
                tool = fn.__name__.split("_")[2]  # _switch_<tool>_<direction>
                print(
                    f"provider: {tool} 未切换；若 DeepSeek 是被旧版本（≤0.8.11）硬编码切过去的，\n"
                    "  则没有 .official.bak 备份，请手动恢复官方配置\n"
                    "  （kimi 在会话里 /model 选官方模型；codex 编辑 ~/.codex/config.toml；\n"
                    "  claude 检查 ~/.claude/settings.json）",
                    file=sys.stderr,
                )
        if any("kimi" in fn.__name__ for fn in callables):
            _warn_if_kimi_running()
        return 0

    print(
        "usage: agentic provider [deepseek|official|codex-deepseek|kimi-deepseek|claude-deepseek|…|status]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

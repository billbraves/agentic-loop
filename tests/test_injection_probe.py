from __future__ import annotations

import os
import stat
import sys
import textwrap
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.claude import ClaudeAdapter
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.adapters.kimi import KimiAdapter
from agentic_loop.provider_binding import ProviderBinding


def mk_binding():
    return ProviderBinding(
        provider="deepseek",
        anthropic_base_url="https://api.deepseek.com/anthropic",
        openai_base_url="https://api.deepseek.com/v1",
        identity_model="deepseek-v4-pro",
        cli_selector="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
    )


def _fake_bin(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body), encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_probe_injection_passes_when_sentinel_echoed(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    # A compatible fake: only emits the sentinel when the injected base_url env is set.
    fake = _fake_bin(tmp_path, "claude", """
        if [ -n "$ANTHROPIC_BASE_URL" ]; then
          echo "DEEPSEEK_PROBE_OK"
          exit 0
        fi
        echo "no injection"; exit 0
    """)
    a = ClaudeAdapter(claude_bin=fake, binding=mk_binding())
    assert a.probe_injection() is True


def test_probe_injection_fails_when_binary_ignores_injection(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    # An outdated/incompatible fake: alive (which-hit) but ignores injection env,
    # never emits the sentinel. `which`-style probe would wrongly pass; ours must fail.
    fake = _fake_bin(tmp_path, "claude", """
        echo "hello from legacy claude"; exit 0
    """)
    a = ClaudeAdapter(claude_bin=fake, binding=mk_binding())
    assert a.probe_injection() is False


def test_probe_injection_fails_on_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    fake = _fake_bin(tmp_path, "claude", """
        echo "DEEPSEEK_PROBE_OK"; exit 3
    """)
    a = ClaudeAdapter(claude_bin=fake, binding=mk_binding())
    assert a.probe_injection() is False


def test_probe_injection_without_binding_falls_back_to_which(tmp_path):
    fake = _fake_bin(tmp_path, "claude", "exit 0\n")
    a = ClaudeAdapter(claude_bin=fake, binding=None)
    # No binding: probe_injection degrades to liveness probe (which-hit true).
    assert a.probe_injection() is True


def test_kimi_probe_injection_passes_when_sentinel_echoed(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    # A compatible fake: only emits the sentinel when the --config-file argv flag is present.
    fake = _fake_bin(tmp_path, "kimi", """
        for a in "$@"; do
          if [ "$a" = "--config-file" ]; then
            echo "DEEPSEEK_PROBE_OK"
            exit 0
          fi
        done
        echo "no injection"; exit 0
    """)
    a = KimiAdapter(kimi_bin=fake, binding=mk_binding())
    assert a.probe_injection() is True


def test_kimi_probe_injection_fails_when_binary_ignores_injection(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    # Alive (which-hit) but ignores the --config-file injection flag; never emits sentinel.
    fake = _fake_bin(tmp_path, "kimi", """
        echo "hello from legacy kimi"; exit 0
    """)
    a = KimiAdapter(kimi_bin=fake, binding=mk_binding())
    assert a.probe_injection() is False


def test_kimi_probe_injection_without_binding_falls_back_to_probe(tmp_path):
    # Kimi.probe() actually runs `kimi -p "reply PROBE_OK"` and checks stdout.
    fake = _fake_bin(tmp_path, "kimi", """
        echo "PROBE_OK"; exit 0
    """)
    a = KimiAdapter(kimi_bin=fake, binding=None)
    assert a.probe_injection() is True


def test_codex_probe_injection_passes_when_sentinel_echoed(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    # A compatible fake: only emits the sentinel when a model_provider inline flag is present.
    fake = _fake_bin(tmp_path, "codex", """
        for a in "$@"; do
          case "$a" in
            *model_provider*) echo "DEEPSEEK_PROBE_OK"; exit 0 ;;
          esac
        done
        echo "no injection"; exit 0
    """)
    a = CodexAdapter(codex_bin=fake, binding=mk_binding())
    assert a.probe_injection() is True


def test_codex_probe_injection_fails_when_binary_ignores_injection(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    # Alive (which-hit) but ignores the model_provider injection flags; never emits sentinel.
    fake = _fake_bin(tmp_path, "codex", """
        echo "hello from legacy codex"; exit 0
    """)
    a = CodexAdapter(codex_bin=fake, binding=mk_binding())
    assert a.probe_injection() is False


def test_codex_probe_injection_without_binding_falls_back_to_which(tmp_path):
    # Codex.probe() is a which-hit check.
    fake = _fake_bin(tmp_path, "codex", "exit 0\n")
    a = CodexAdapter(codex_bin=fake, binding=None)
    assert a.probe_injection() is True


# ---- D1: base 默认 bool 契约零回归 ----
# 只继承 Adapter、不覆写 probe_injection / probe_injection_detail 的最小子类，
# 实现四个抽象方法 capabilities / identity / probe / review，_binding 为 None。
class _BaseDefaultAdapter(Adapter):
    name = "base-default"

    def __init__(self, probe_result: bool) -> None:
        self._probe_result = probe_result

    def identity(self):
        return None

    def capabilities(self):
        return None

    def review(self, *, diff, brief, contract, effort):
        return None

    def probe(self) -> bool:
        return self._probe_result


def test_base_default_probe_injection_returns_exact_bool():
    # probe() 返回 True / False，probe_injection() 必须用 `is` 精确等于该布尔。
    # 若 base 变异为 `return self.probe_injection_detail()`（返回元组），
    # 此处 `is True` / `is False` 必红（元组不是 bool）。
    assert _BaseDefaultAdapter(True).probe_injection() is True
    assert _BaseDefaultAdapter(False).probe_injection() is False

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.provider_binding import (
    ProviderBinding,
    ProviderConfigError,
    build_binding,
)

DEEPSEEK_CFG = {
    "anthropic_base_url": "https://api.deepseek.com/anthropic",
    "openai_base_url": "https://api.deepseek.com/v1",
    "api_key_env": "DEEPSEEK_API_KEY",
    "identity_model": "deepseek-v4-pro",
    "selectors": {
        "kimi": "deepseek/v4-pro",
        "codex": "deepseek-v4-pro",
        "claude": "deepseek-v4-pro",
    },
}


def test_binding_is_frozen():
    b = build_binding(adapter="claude", provider_cfg=DEEPSEEK_CFG)
    with pytest.raises(FrozenInstanceError):
        b.identity_model = "x"  # type: ignore[misc]


def test_claude_binding_uses_anthropic_and_canonical_identity():
    b = build_binding(adapter="claude", provider_cfg=DEEPSEEK_CFG)
    assert b.anthropic_base_url == "https://api.deepseek.com/anthropic"
    assert b.identity_model == "deepseek-v4-pro"          # canonical
    assert b.cli_selector == "deepseek-v4-pro"            # claude selector
    assert b.api_key_env == "DEEPSEEK_API_KEY"


def test_kimi_selector_differs_from_identity():
    b = build_binding(adapter="kimi", provider_cfg=DEEPSEEK_CFG)
    assert b.cli_selector == "deepseek/v4-pro"            # per-adapter
    assert b.identity_model == "deepseek-v4-pro"          # canonical, NOT selector


def test_codex_binding_uses_openai_base_url():
    b = build_binding(adapter="codex", provider_cfg=DEEPSEEK_CFG)
    assert b.openai_base_url == "https://api.deepseek.com/v1"
    assert b.cli_selector == "deepseek-v4-pro"


def test_claude_missing_anthropic_base_url_fail_closed():
    bad = dict(DEEPSEEK_CFG, anthropic_base_url=None)
    with pytest.raises(ProviderConfigError):
        build_binding(adapter="claude", provider_cfg=bad)


def test_codex_missing_openai_base_url_fail_closed():
    bad = dict(DEEPSEEK_CFG, openai_base_url=None)
    with pytest.raises(ProviderConfigError):
        build_binding(adapter="codex", provider_cfg=bad)


def test_error_message_does_not_leak_key_value(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-SECRET-LEAK-CANARY")
    bad = dict(DEEPSEEK_CFG, anthropic_base_url=None)
    with pytest.raises(ProviderConfigError) as ei:
        build_binding(adapter="claude", provider_cfg=bad)
    assert "sk-SECRET-LEAK-CANARY" not in str(ei.value)

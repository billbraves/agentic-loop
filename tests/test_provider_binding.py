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


# --------------------------------------------------------------------------
# The validated field must be the field the adapter actually injects.
#
# kimi's injected provider block is ``type = "openai_legacy"``, so the adapter
# reads ``openai_base_url``. While kimi sat in the anthropic set, a config with
# only ``anthropic_base_url`` (this repo's own providers.deepseekflash was in
# exactly that shape) passed validation and then wrote the /anthropic endpoint
# into an openai_legacy block -- a valid-looking file that could only fail later
# as an opaque remote error.
# --------------------------------------------------------------------------

def test_kimi_missing_openai_base_url_fail_closed():
    """kimi injects an openai_legacy provider, so it requires openai_base_url."""
    bad = dict(DEEPSEEK_CFG, openai_base_url=None)
    with pytest.raises(ProviderConfigError):
        build_binding(adapter="kimi", provider_cfg=bad)


def test_kimi_missing_field_message_names_the_field_and_no_key(monkeypatch):
    """The kimi failure must be self-diagnosing and must never echo the key.

    Asserting only the exception TYPE is vacuous: an error raised for an
    unrelated cause, or one that prints the key, passes such a test. Pinning the
    field name in the message makes a wrong-cause failure red, and pinning the
    absence of the canary keeps a future message from leaking the credential it
    was handed the env-var name for.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-SECRET-LEAK-CANARY")
    bad = dict(DEEPSEEK_CFG, openai_base_url=None)
    with pytest.raises(ProviderConfigError) as ei:
        build_binding(adapter="kimi", provider_cfg=bad)
    message = str(ei.value)
    assert "openai_base_url" in message, message
    assert "kimi" in message, message
    assert "sk-SECRET-LEAK-CANARY" not in message, message


def test_kimi_anthropic_only_config_message_names_openai_base_url():
    """Same contract for the exact historical shape: name the missing field."""
    bad = {
        "anthropic_base_url": "https://api.deepseek.com/anthropic",
        "api_key_env": "DEEPSEEK_API_KEY",
        "identity_model": "deepseek-v4-flash",
        "selectors": {"kimi": "deepseek/v4-flash"},
    }
    with pytest.raises(ProviderConfigError) as ei:
        build_binding(adapter="kimi", provider_cfg=bad)
    assert "openai_base_url" in str(ei.value), ei.value


def test_kimi_with_openai_base_url_builds():
    """Positive reachability: the same call succeeds once the field is declared."""
    b = build_binding(adapter="kimi", provider_cfg=DEEPSEEK_CFG)
    assert b.openai_base_url == "https://api.deepseek.com/v1"


def test_error_message_does_not_leak_key_value(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-SECRET-LEAK-CANARY")
    bad = dict(DEEPSEEK_CFG, anthropic_base_url=None)
    with pytest.raises(ProviderConfigError) as ei:
        build_binding(adapter="claude", provider_cfg=bad)
    assert "sk-SECRET-LEAK-CANARY" not in str(ei.value)

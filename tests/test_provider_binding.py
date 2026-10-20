from __future__ import annotations

import sys
import tomllib
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


# Three input shapes reach the same guard and must be pinned separately. All
# three are indistinguishable to the production code -- `.get()` yields a falsy
# value for each -- but NOT to a mutation, which can branch on
# `"openai_base_url" in provider_cfg` or on `value is None`:
#   * declared_none  -- the key is present and None;
#   * declared_empty -- the key is present and "", which is what an operator
#                       actually writes in TOML (openai_base_url = ""). Omitting
#                       this shape let `not value` -> `value is None` admit the
#                       empty string with the whole module still green;
#   * absent         -- the key is missing entirely (the historical shape, a
#                       provider block that only declared anthropic_base_url).
#
# declared_empty is parsed from real TOML rather than hand-written as "" so the
# test pins the shape an actual config file produces, not our assumption about
# how tomllib represents it.
_EMPTY_URL_CFG = tomllib.loads(
    """
    anthropic_base_url = "https://api.deepseek.com/anthropic"
    openai_base_url    = ""
    api_key_env        = "DEEPSEEK_API_KEY"
    identity_model     = "deepseek-v4-flash"
    [selectors]
    kimi = "deepseek/v4-flash"
    """
)

_MISSING_OPENAI_URL_SHAPES = {
    "declared_none": dict(DEEPSEEK_CFG, openai_base_url=None),
    "declared_empty": _EMPTY_URL_CFG,
    "absent_anthropic_only": {
        "anthropic_base_url": "https://api.deepseek.com/anthropic",
        "api_key_env": "DEEPSEEK_API_KEY",
        "identity_model": "deepseek-v4-flash",
        "selectors": {"kimi": "deepseek/v4-flash"},
    },
}


def test_empty_url_shape_is_really_an_empty_string():
    """Guard the fixture itself: the shape must be "" and present, not None.

    If tomllib ever produced something else here, the parametrized cases above
    would still pass while no longer covering the empty-string shape at all --
    the silent-coverage-loss failure mode this whole block exists to prevent.
    """
    assert "openai_base_url" in _EMPTY_URL_CFG
    assert _EMPTY_URL_CFG["openai_base_url"] == ""

# The exact diagnostic this one cause must produce. Pinned as full equality, not
# as a substring: `"openai_base_url" in message` cannot tell "this field is
# missing" apart from "this field is fine, a DIFFERENT one is missing", so a
# message like "openai_base_url is valid; missing identity_model" satisfies a
# substring check while being the wrong diagnosis. Equality also makes a
# rewording a conscious edit here rather than a silent loss of the contract.
_EXPECTED_MISSING_OPENAI_URL = "adapter 'kimi' requires openai_base_url"


@pytest.mark.parametrize("shape", sorted(_MISSING_OPENAI_URL_SHAPES))
def test_kimi_missing_openai_base_url_names_that_exact_cause(shape):
    """The failure must say which field is missing, for both input shapes."""
    with pytest.raises(ProviderConfigError) as ei:
        build_binding(adapter="kimi", provider_cfg=_MISSING_OPENAI_URL_SHAPES[shape])
    assert str(ei.value) == _EXPECTED_MISSING_OPENAI_URL, str(ei.value)


@pytest.mark.parametrize("shape", sorted(_MISSING_OPENAI_URL_SHAPES))
def test_kimi_missing_openai_base_url_never_echoes_the_key(monkeypatch, shape):
    """No input shape may leak the credential whose env-var name it was given.

    Both shapes need the canary. Covering only one leaves a mutation free to
    leak exactly in the uncovered shape, which is how an earlier round of this
    test stayed green while printing a key.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-SECRET-LEAK-CANARY")
    with pytest.raises(ProviderConfigError) as ei:
        build_binding(adapter="kimi", provider_cfg=_MISSING_OPENAI_URL_SHAPES[shape])
    assert "sk-SECRET-LEAK-CANARY" not in str(ei.value), str(ei.value)


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

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.claude import ClaudeAdapter
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.adapters.kimi import KimiAdapter
from agentic_loop.provider_binding import ProviderBinding


def mk_binding(provider="deepseek", selector="deepseek-v4-pro"):
    return ProviderBinding(
        provider=provider,
        anthropic_base_url="https://api.deepseek.com/anthropic",
        openai_base_url="https://api.deepseek.com/v1",
        identity_model="deepseek-v4-pro",
        cli_selector=selector,
        api_key_env="DEEPSEEK_API_KEY",
    )


# ---- identity: canonical, never selector -----------------------------------

def test_claude_identity_none_without_binding():
    assert ClaudeAdapter().identity().model is None


def test_claude_identity_reports_canonical_with_binding():
    a = ClaudeAdapter(binding=mk_binding(selector="deepseek-v4-pro"))
    assert a.identity().model == "deepseek-v4-pro"


def test_kimi_identity_uses_canonical_not_selector():
    # kimi selector differs (deepseek/v4-pro) but identity must stay canonical.
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    assert a.identity().model == "deepseek-v4-pro"       # NOT "deepseek/v4-pro"


def test_codex_identity_reports_canonical_with_binding():
    a = CodexAdapter(binding=mk_binding())
    assert a.identity().model == "deepseek-v4-pro"


# ---- claude env injection (dry_run exposes command, env checked via build) --

def test_claude_dry_run_command_has_no_key_in_argv(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = ClaudeAdapter(binding=mk_binding())
    res = a.implement(worktree="/tmp", brief="", prompt="hi", dry_run=True)
    assert "sk-CANARY" not in " ".join(res.command)     # key never in argv


def test_claude_build_env_injects_anthropic(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = ClaudeAdapter(binding=mk_binding())
    env = a._build_env()                                  # helper under test
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-CANARY"
    assert env["ANTHROPIC_MODEL"] == "deepseek-v4-pro"


# ---- codex review subprocess output redaction (WP-02 REWORK) ---------------

def test_codex_review_nonzero_exit_redacts_key_from_stderr(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    fake = tmp_path / "fake-codex"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "echo \"boom $DEEPSEEK_API_KEY\" >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    adapter = CodexAdapter(codex_bin=str(fake), binding=mk_binding())
    contract = ReviewContract(
        role="consultant",
        output_schema={
            "type": "object",
            "properties": {"decision": {"type": "string"}},
        },
    )

    with pytest.raises(RuntimeError) as excinfo:
        adapter.review(
            diff="diff",
            brief="brief",
            contract=contract,
            effort="medium",
        )

    message = str(excinfo.value)
    assert "sk-CANARY" not in message
    assert "***REDACTED***" in message


# ---- codex -c inline injection ---------------------------------------------

def test_codex_review_cmd_has_provider_flags_no_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = CodexAdapter(binding=mk_binding())
    cmd = a._build_injection_flags()                      # helper under test
    joined = " ".join(cmd)
    assert "model_provider=deepseek" in joined
    assert "model_providers.deepseek.base_url=https://api.deepseek.com/v1" in joined
    assert "model_providers.deepseek.env_key=DEEPSEEK_API_KEY" in joined
    assert "model_providers.deepseek.wire_api=responses" in joined
    assert "-m" in cmd and "deepseek-v4-pro" in cmd
    assert "sk-CANARY" not in joined                      # env_key name only


# ---- kimi 0600 temp config, key not in argv --------------------------------

def test_kimi_temp_config_contains_key_and_is_0600(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    with a._temp_config() as cfg_path:                    # context mgr under test
        import os, stat
        mode = stat.S_IMODE(os.stat(cfg_path).st_mode)
        assert mode == 0o600
        text = Path(cfg_path).read_text()
        # kimi 1.50 only resolves these selectors through an openai_legacy
        # provider; an anthropic-typed block yields "LLM not set" despite a
        # valid key, so the injected config targets the OpenAI-compatible URL.
        assert 'type     = "openai_legacy"' in text
        assert "https://api.deepseek.com/v1" in text
        assert "sk-CANARY" in text                        # key in temp file only
    assert not Path(cfg_path).exists()                    # cleaned up after ctx


def test_kimi_temp_config_never_writes_anthropic_endpoint(monkeypatch):
    """The openai_legacy block must never carry the /anthropic endpoint.

    When kimi fell back to ``anthropic_base_url``, a provider section declaring
    only that field produced ``base_url = ".../anthropic"`` inside a
    ``type = "openai_legacy"`` block: syntactically valid, semantically wrong,
    and observable only as an opaque remote failure at dispatch time.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    with a._temp_config() as cfg_path:
        text = Path(cfg_path).read_text()
    assert "openai_legacy" in text
    assert "/anthropic" not in text, text


# The adapter's own guard is the SECOND place this cause can be reported, and
# the more dangerous one: by the time it runs, _temp_config has already read the
# real credential out of the environment into a local. A substring match on
# "openai_base_url" admits both a wrong diagnosis and a message that appends the
# key -- the exact pair of defects codex rejected in provider_binding. Pinning
# the message by equality covers both, in the one place that holds the secret.
_EXPECTED_ADAPTER_GUARD = (
    "kimi adapter requires openai_base_url "
    "(the injected provider uses type=openai_legacy)"
)


def test_kimi_temp_config_refuses_binding_without_openai_base_url(monkeypatch):
    """A hand-built binding must fail loudly, not silently reuse the other URL.

    The message is pinned exactly, and the canary asserted absent: this guard
    runs with the real key already in hand, so "fails loudly" must not mean
    "fails loudly, with the credential in the exception text".
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-SECRET-LEAK-CANARY")
    b = mk_binding(selector="deepseek/v4-pro")
    object.__setattr__(b, "openai_base_url", None)        # frozen dataclass
    a = KimiAdapter(binding=b)
    with pytest.raises(ValueError) as ei:
        with a._temp_config() as _cfg:
            pass
    message = str(ei.value)
    assert message == _EXPECTED_ADAPTER_GUARD, message
    assert "sk-SECRET-LEAK-CANARY" not in message, message



def test_kimi_temp_mcp_config_declares_no_servers(monkeypatch):
    """Dispatch must not inherit the operator's ~/.kimi/mcp.json.

    An unreachable server there aborts the whole run with MCPRuntimeError,
    which is how a WP-41 dispatch died before this isolation existed.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    with a._temp_mcp_config() as mcp_path:
        import json

        assert json.loads(Path(mcp_path).read_text()) == {"mcpServers": {}}
    assert not Path(mcp_path).exists()


def test_kimi_implement_isolates_mcp_config(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    res = a.implement(worktree="/tmp", brief="", prompt="hi", dry_run=True)
    assert "--mcp-config-file" in res.command


def test_kimi_implement_cmd_has_no_key_in_argv(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    res = a.implement(worktree="/tmp", brief="", prompt="hi", dry_run=True)
    joined = " ".join(res.command)
    assert "sk-CANARY" not in joined
    assert "--config-file" in res.command
    assert "--model" in res.command and "deepseek/v4-pro" in res.command

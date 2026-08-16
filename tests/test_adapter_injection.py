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
        assert "https://api.deepseek.com/anthropic" in text
        assert "sk-CANARY" in text                        # key in temp file only
    assert not Path(cfg_path).exists()                    # cleaned up after ctx


def test_kimi_implement_cmd_has_no_key_in_argv(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-CANARY")
    a = KimiAdapter(binding=mk_binding(selector="deepseek/v4-pro"))
    res = a.implement(worktree="/tmp", brief="", prompt="hi", dry_run=True)
    joined = " ".join(res.command)
    assert "sk-CANARY" not in joined
    assert "--config-file" in res.command
    assert "--model" in res.command and "deepseek/v4-pro" in res.command

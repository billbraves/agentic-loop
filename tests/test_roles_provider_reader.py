from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import resolve_paths as rp
from agentic_loop.provider_binding import ProviderBinding

PROVIDERS_CONFIG = """\
[providers.deepseek]
anthropic_base_url = "https://api.deepseek.com/anthropic"
openai_base_url    = "https://api.deepseek.com/v1"
api_key_env        = "DEEPSEEK_API_KEY"
identity_model     = "deepseek-v4-pro"
[providers.deepseek.selectors]
kimi   = "deepseek/v4-pro"
codex  = "deepseek-v4-pro"
claude = "deepseek-v4-pro"

[roles]
developer  = { adapter = "kimi",   provider = "deepseek" }
reviewer   = { adapter = "claude", provider = "deepseek" }
consultant = { adapter = "codex",  provider = "deepseek" }
"""

LEGACY_CONFIG = """\
[roles]
orchestrator = "claude"
developer    = ["kimi", "claude"]
reviewer     = "claude"
consultant   = "codex"
"""


def _mk_repo(tmp_path: Path, config_text: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    agentic = tmp_path / ".agentic"
    agentic.mkdir()
    (agentic / "config.toml").write_text(config_text, encoding="utf-8")
    return tmp_path


def test_table_role_resolves_to_binding(tmp_path):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    adapter, binding = rp.resolve_role_binding("reviewer", repo=repo)
    assert adapter == "claude"
    assert isinstance(binding, ProviderBinding)
    assert binding.identity_model == "deepseek-v4-pro"
    assert binding.cli_selector == "deepseek-v4-pro"
    assert binding.anthropic_base_url == "https://api.deepseek.com/anthropic"


def test_kimi_developer_table_role_selector(tmp_path):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    adapter, binding = rp.resolve_role_binding("developer", repo=repo)
    assert adapter == "kimi"
    assert binding.cli_selector == "deepseek/v4-pro"      # per-adapter
    assert binding.identity_model == "deepseek-v4-pro"    # canonical


def test_legacy_string_role_no_binding(tmp_path):
    repo = _mk_repo(tmp_path, LEGACY_CONFIG)
    adapter, binding = rp.resolve_role_binding("reviewer", repo=repo)
    assert adapter == "claude"
    assert binding is None                                # 零回归


def test_legacy_array_role_first_candidate_no_binding(tmp_path):
    repo = _mk_repo(tmp_path, LEGACY_CONFIG)
    adapter, binding = rp.resolve_role_binding("developer", repo=repo)
    assert adapter == "kimi"                              # 主候选
    assert binding is None


def test_no_config_no_binding(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    adapter, binding = rp.resolve_role_binding("reviewer", repo=tmp_path)
    assert adapter == "claude"                            # DEFAULT_ROLES 兜底
    assert binding is None


def test_get_roles_raw_preserves_table(tmp_path):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    raw = rp.get_roles_raw(repo=repo)
    assert raw["reviewer"] == {"adapter": "claude", "provider": "deepseek"}

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.resolve_paths import resolve_role_fallback_binding

FLASH_CFG = """\
[providers.deepseekflash]
anthropic_base_url = "https://api.deepseek.com/anthropic"
api_key_env        = "DEEPSEEK_API_KEY"
identity_model     = "deepseek-v4-flash"
[providers.deepseekflash.selectors]
kimi = "deepseek/v4-flash"

[roles]
developer = { adapter = "kimi", fallback_provider = "deepseekflash" }
"""


def _repo(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / ".agentic" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body, encoding="utf-8")
    return tmp_path


def test_resolves_flash_binding(tmp_path):
    repo = _repo(tmp_path, FLASH_CFG)
    b = resolve_role_fallback_binding("developer", repo=repo)
    assert b is not None
    assert b.identity_model == "deepseek-v4-flash"
    assert b.cli_selector == "deepseek/v4-flash"
    assert b.anthropic_base_url == "https://api.deepseek.com/anthropic"
    assert b.api_key_env == "DEEPSEEK_API_KEY"


def test_none_when_no_fallback_provider(tmp_path):
    repo = _repo(tmp_path, '[roles]\ndeveloper = "kimi"\n')
    assert resolve_role_fallback_binding("developer", repo=repo) is None


def test_none_when_role_is_dict_without_fallback(tmp_path):
    repo = _repo(tmp_path, '[roles]\ndeveloper = { adapter = "kimi" }\n')
    assert resolve_role_fallback_binding("developer", repo=repo) is None


def test_none_when_provider_section_missing(tmp_path):
    repo = _repo(tmp_path, '[roles]\ndeveloper = { adapter = "kimi", fallback_provider = "nope" }\n')
    assert resolve_role_fallback_binding("developer", repo=repo) is None


def test_none_when_provider_cfg_invalid_no_raise(tmp_path):
    # 缺 anthropic_base_url（kimi 必需）→ build_binding 会抛；解析器须吞掉返回 None。
    bad = (
        '[providers.deepseekflash]\n'
        'api_key_env = "DEEPSEEK_API_KEY"\n'
        'identity_model = "deepseek-v4-flash"\n'
        '[providers.deepseekflash.selectors]\nkimi = "deepseek/v4-flash"\n'
        '[roles]\ndeveloper = { adapter = "kimi", fallback_provider = "deepseekflash" }\n'
    )
    repo = _repo(tmp_path, bad)
    assert resolve_role_fallback_binding("developer", repo=repo) is None

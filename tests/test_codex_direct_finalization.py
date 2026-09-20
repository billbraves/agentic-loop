"""禁工具收尾改走直连 Responses API 的契约测试。

背景（WP-34 取第二签实测）：codex CLI **客户端**会把 web_search 注入请求，且没有
任何开关能关掉（--disable web_search / web_search_request / standalone_web_search /
search_tool / -c tools.web_search=false / omit_tools_from 全部无效；
supports_standalone_web_search=false 会让 turn 直接失败）。于是禁工具收尾 turn 必然
出现 web_search 项，_validated_final_message(tools_forbidden=True) 只能 fail-closed
拒签，第二签永远取不到。

注入方是 CLI 而非 provider：以 tools=[] 直连 DeepSeek /v1/responses 时，即使提示明确
要求联网搜索，输出也只有 reasoning + message。直连因此真正兑现禁工具契约。

本测试锁住：请求里 tools 恒为空、默认不启用（避免劫持既有 CLI 打桩用例）、
以及直连路径自身对任何工具项/截断同样 fail-closed。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters import codex as codex_mod
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.provider_binding import ProviderBinding

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"decision": {"type": "string"}},
    "required": ["decision"],
}


def mk_binding():
    return ProviderBinding(
        provider="deepseek",
        anthropic_base_url="https://api.deepseek.com/anthropic",
        openai_base_url="https://api.deepseek.com/v1",
        identity_model="deepseek-v4-pro",
        cli_selector="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
    )


def fake_urlopen(payload, captured):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    def _open(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["url"] = req.full_url
        return _Resp()

    return _open


def ok_payload(text='{"decision": "ACCEPT"}'):
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning"},
            {"type": "message", "content": [{"type": "output_text", "text": text}]},
        ],
    }


# ---- 默认关闭：不得劫持既有 CLI 打桩用例 -----------------------------------

def test_direct_disabled_by_default_even_with_binding(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    adapter = CodexAdapter(binding=mk_binding())
    assert adapter._direct_finalization_enabled() is False, (
        "默认必须关闭：否则开发机配了真密钥就会把打桩 CLI 协议的单测劫持成真实 HTTP"
    )


def test_direct_requires_binding(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert CodexAdapter(direct_finalization=True)._direct_finalization_enabled() is False


def test_direct_enabled_when_opted_in(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    assert adapter._direct_finalization_enabled() is True


# ---- 核心契约：请求里 tools 恒为空 ------------------------------------------

def test_request_always_sends_empty_tools(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    captured: dict = {}
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen", fake_urlopen(ok_payload(), captured)
    )
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    out = adapter._direct_tool_free_verdict(prompt="p", schema=SCHEMA)
    assert json.loads(out)["decision"] == "ACCEPT"
    assert captured["body"]["tools"] == [], (
        "禁工具契约的核心：请求里工具面必须是空数组，而不是事后校验被污染的流"
    )
    assert captured["body"]["stream"] is False
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["url"].endswith("/responses")


def test_api_key_not_in_url(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret-value")
    captured: dict = {}
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen", fake_urlopen(ok_payload(), captured)
    )
    CodexAdapter(
        binding=mk_binding(), direct_finalization=True
    )._direct_tool_free_verdict(prompt="p", schema=SCHEMA)
    assert "sk-secret-value" not in captured["url"]
    assert "sk-secret-value" not in json.dumps(captured["body"])


# ---- fail-closed：直连路径同样不得放宽 -------------------------------------

def test_tool_item_rejected(monkeypatch):
    """直连流里出现工具项必须拒绝 —— 与 CLI 路径同等严格。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    payload = {
        "status": "completed",
        "output": [
            {"type": "web_search"},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"decision":"ACCEPT"}'}],
            },
        ],
    }
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen", fake_urlopen(payload, {})
    )
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    with pytest.raises(RuntimeError, match="tool-free turn emitted item type"):
        adapter._direct_tool_free_verdict(prompt="p", schema=SCHEMA)


def test_incomplete_status_rejected(monkeypatch):
    """截断（max_output_tokens）的裁决绝不采信。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    payload = {"status": "incomplete", "output": [], "incomplete_details": {}}
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen", fake_urlopen(payload, {})
    )
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    with pytest.raises(RuntimeError, match="did not complete"):
        adapter._direct_tool_free_verdict(prompt="p", schema=SCHEMA)


def test_multiple_output_texts_rejected(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    payload = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "{}"},
                    {"type": "output_text", "text": "{}"},
                ],
            }
        ],
    }
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen", fake_urlopen(payload, {})
    )
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    with pytest.raises(RuntimeError, match="exactly one output_text"):
        adapter._direct_tool_free_verdict(prompt="p", schema=SCHEMA)


def test_missing_api_key_fails_closed(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    with pytest.raises(RuntimeError, match="requires \\$DEEPSEEK_API_KEY"):
        adapter._direct_tool_free_verdict(prompt="p", schema=SCHEMA)


def test_http_error_does_not_leak_body(monkeypatch):
    """HTTP 错误不得把响应体外抛（可能含密钥或账号信息）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def _raise(req, timeout=None):
        raise codex_mod.urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"error":"sk-leaked-secret"}'),
        )

    monkeypatch.setattr(codex_mod.urllib.request, "urlopen", _raise)
    adapter = CodexAdapter(binding=mk_binding(), direct_finalization=True)
    with pytest.raises(RuntimeError) as ei:
        adapter._direct_tool_free_verdict(prompt="p", schema=SCHEMA)
    assert "sk-leaked-secret" not in str(ei.value)
    assert "401" in str(ei.value)

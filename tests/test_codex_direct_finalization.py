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

import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters import codex as codex_mod
from agentic_loop.adapters.base import ReviewContract
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


# =====================================================================
# WP-21：直连禁工具链路的正确性修复
#   (1) 归一化 prompt = nonce 定界明文引号块（无任何解码/变换要求）；
#   (2) 空终态直连 = 有界全量重试（内联 brief+diff；超界不发起调用）。
# =====================================================================

DIFF = "diff --git a/x.py b/x.py\n+print('wp21 diff body')\n"
BRIEF = "WP-21 brief body: bounded direct retry"
CHUNK_CTX = "## Chunk context\nYou are now judging chunk 1/3, which contains: x.py."


def mk_contract(review_policy: str = "") -> ReviewContract:
    return ReviewContract(
        role="consultant", output_schema=SCHEMA, review_policy=review_policy
    )


def mk_direct_adapter(monkeypatch) -> CodexAdapter:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    return CodexAdapter(binding=mk_binding(), direct_finalization=True)


def extract_norm_block(prompt: str) -> tuple[str, str]:
    """取出 (nonce, 明文 payload)；开/闭标记共享同一 nonce。"""
    m = re.search(
        r"<<<<PRIOR_OUTPUT_([0-9a-f]{16})\n(.*?)\nPRIOR_OUTPUT_\1>>>>",
        prompt,
        re.DOTALL,
    )
    assert m, "nonce-delimited PRIOR_OUTPUT block not found"
    return m.group(1), m.group(2)


def _fake_proc():
    return subprocess.CompletedProcess(
        args=["codex"], returncode=0, stdout=b"", stderr=b""
    )


def _patch_first_attempt(monkeypatch, adapter, *, verdict):
    """把 CLI 首轮与输出读取打桩掉，只留直连恢复调用走真实构建路径。"""
    monkeypatch.setattr(adapter, "_exec_attempt", lambda **kw: _fake_proc())
    monkeypatch.setattr(adapter, "_read_verdict_output", lambda *a, **k: verdict)


# ---- 归一化 prompt：nonce 明文、无解码要求 ----------------------------------

def test_normalization_prompt_nonce_plaintext_without_decode_requirement(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    prompt = adapter._build_normalization_prompt(
        prior_output="free text verdict body", contract=mk_contract()
    )
    nonce, payload = extract_norm_block(prompt)
    assert payload == "free text verdict body"
    assert prompt.count(f"PRIOR_OUTPUT_{nonce}") == 2
    # P0 根因（解码要求触发无界手工解码）的载体必须不复存在。
    assert "base64" not in prompt.lower()
    assert "decode" not in prompt.lower()


def test_normalization_prompt_nonce_fresh_each_call(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    p1 = adapter._build_normalization_prompt(prior_output="x", contract=mk_contract())
    p2 = adapter._build_normalization_prompt(prior_output="x", contract=mk_contract())
    assert extract_norm_block(p1)[0] != extract_norm_block(p2)[0], (
        "nonce 必须每次调用新生成，否则可被跨调用重放的伪造标记截断"
    )


# ---- 重试 prompt：结构绑定 + 上界 -------------------------------------------

def test_retry_prompt_structure_binding(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    prompt = adapter._build_direct_retry_prompt(
        diff=DIFF, brief=BRIEF, contract=mk_contract(), chunk_context=CHUNK_CTX
    )
    # 不再是伪签装置（无上下文收尾文案）。
    assert not prompt.startswith("FINALIZATION")
    assert "FINALIZATION for the review you just completed" not in prompt
    # 与 _build_prompt 同源的评审指令段（标准载体与首轮一致）。
    assert (
        "You are Codex acting as the independent Architecture & Incident Consultant"
        in prompt
    )
    assert "Return a structured verdict:" in prompt
    # 材料双 nonce 块：开/闭共享同一 nonce、各自恰好一对；块内 = 原文。
    brief_nonce = re.search(r"<<<<UNTRUSTED_BRIEF_([0-9a-f]{16})", prompt).group(1)
    diff_nonce = re.search(r"<<<<UNTRUSTED_DIFF_([0-9a-f]{16})", prompt).group(1)
    assert brief_nonce == diff_nonce
    assert prompt.count(f"UNTRUSTED_BRIEF_{brief_nonce}") == 2
    assert prompt.count(f"UNTRUSTED_DIFF_{brief_nonce}") == 2
    assert (
        f"<<<<UNTRUSTED_BRIEF_{brief_nonce}\n{BRIEF}\n"
        f"UNTRUSTED_BRIEF_{brief_nonce}>>>>"
    ) in prompt
    assert (
        f"<<<<UNTRUSTED_DIFF_{brief_nonce}\n{DIFF}\n"
        f"UNTRUSTED_DIFF_{brief_nonce}>>>>"
    ) in prompt
    # 字节数 + SHA-256 绑定。
    assert f"Brief UTF-8 bytes: {len(BRIEF.encode())}" in prompt
    assert f"Brief SHA-256: {hashlib.sha256(BRIEF.encode()).hexdigest()}" in prompt
    assert f"Diff UTF-8 bytes: {len(DIFF.encode())}" in prompt
    assert f"Diff SHA-256: {hashlib.sha256(DIFF.encode()).hexdigest()}" in prompt
    # chunk_context 保留（分块场景的全局方位）。
    assert CHUNK_CTX in prompt


def test_retry_prompt_includes_review_policy(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    prompt = adapter._build_direct_retry_prompt(
        diff=DIFF, brief=BRIEF, contract=mk_contract(review_policy="HARD RULE: X")
    )
    assert "HARD RULE: X" in prompt
    prompt2 = adapter._build_direct_retry_prompt(
        diff=DIFF, brief=BRIEF, contract=mk_contract()
    )
    assert "HARD RULE" not in prompt2


def test_retry_prompt_over_input_bound_fails_closed(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    huge = "diff --git a/x b/x\n+" + "x" * CodexAdapter._DIRECT_RETRY_MAX_INPUT_BYTES
    with pytest.raises(RuntimeError, match="exceeds input bound"):
        adapter._build_direct_retry_prompt(diff=huge, brief=BRIEF, contract=mk_contract())


# ---- site A（空终态）直连接线 ------------------------------------------------

def test_empty_final_state_direct_uses_bounded_retry_not_finalization(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    captured: dict = {}
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen",
        fake_urlopen(
            ok_payload(
                '{"decision": "ACCEPT", "rationale": "r", "findings": []}'
            ),
            captured,
        ),
    )
    _patch_first_attempt(monkeypatch, adapter, verdict=None)

    verdict = adapter._review_single(
        diff=DIFF, brief=BRIEF, contract=mk_contract(), effort="high",
        chunk_context=CHUNK_CTX,
    )

    assert verdict.decision == "ACCEPT"
    sent = captured["body"]["input"]
    # 直连空终态：发的是有界全量重试（材料内联），不是无上下文收尾文案。
    assert "FINALIZATION for the review you just completed" not in sent
    assert "<<<<UNTRUSTED_BRIEF_" in sent and "<<<<UNTRUSTED_DIFF_" in sent
    assert BRIEF in sent and "wp21 diff body" in sent
    assert CHUNK_CTX in sent
    assert captured["body"]["tools"] == []


def test_empty_final_state_over_bound_fails_closed_without_http(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    calls = {"n": 0}

    def _forbidden_open(req, timeout=None):
        calls["n"] += 1
        raise AssertionError("HTTP must not be issued when retry exceeds bound")

    monkeypatch.setattr(codex_mod.urllib.request, "urlopen", _forbidden_open)
    _patch_first_attempt(monkeypatch, adapter, verdict=None)
    huge = "diff --git a/x b/x\n+" + "x" * CodexAdapter._DIRECT_RETRY_MAX_INPUT_BYTES

    with pytest.raises(RuntimeError, match="exceeds input bound"):
        adapter._review_single(
            diff=huge, brief=BRIEF, contract=mk_contract(), effort="high"
        )
    assert calls["n"] == 0


def test_empty_final_state_retry_incomplete_fails_closed(monkeypatch):
    """重试被截断（incomplete）→ 抛错取不到签，绝不产伪签。"""
    adapter = mk_direct_adapter(monkeypatch)
    payload = {"status": "incomplete", "output": [], "incomplete_details": {}}
    monkeypatch.setattr(codex_mod.urllib.request, "urlopen", fake_urlopen(payload, {}))
    _patch_first_attempt(monkeypatch, adapter, verdict=None)

    with pytest.raises(RuntimeError, match="did not complete"):
        adapter._review_single(
            diff=DIFF, brief=BRIEF, contract=mk_contract(), effort="high"
        )


# ---- site B（非法 JSON）归一化直连接线 ---------------------------------------

def test_normalization_site_direct_prompt_no_finalization_text(monkeypatch):
    adapter = mk_direct_adapter(monkeypatch)
    captured: dict = {}
    monkeypatch.setattr(
        codex_mod.urllib.request, "urlopen",
        fake_urlopen(
            ok_payload(
                '{"decision": "REWORK", "rationale": "r", "findings": []}'
            ),
            captured,
        ),
    )
    _patch_first_attempt(monkeypatch, adapter, verdict="plain free text, not json")

    verdict = adapter._review_single(
        diff=DIFF, brief=BRIEF, contract=mk_contract(), effort="high"
    )

    assert verdict.decision == "REWORK"
    sent = captured["body"]["input"]
    assert "plain free text, not json" in sent
    assert "<<<<PRIOR_OUTPUT_" in sent
    assert "base64" not in sent.lower()
    assert "FINALIZATION for the review you just completed" not in sent

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import ImplementResult
from agentic_loop.provider_binding import ProviderBinding
from agentic_loop.redispatch import _dispatch_with_quota_fallback


def _result(dispatched, output, exit_code=0):
    return ImplementResult(dispatched=dispatched, exit_code=exit_code,
                           output=output, command=("kimi",), dry_run=False)


class _StubAdapter:
    name = "stub"

    def __init__(self, result):
        self._result = result
        self.calls = 0

    def implement(self, *, worktree, brief, prompt, dry_run=False):
        self.calls += 1
        return self._result


def _flash_binding():
    return ProviderBinding(
        provider="deepseekflash",
        anthropic_base_url="https://api.deepseek.com/anthropic",
        openai_base_url=None,
        identity_model="deepseek-v4-flash",
        cli_selector="deepseek/v4-flash",
        api_key_env="DEEPSEEK_API_KEY",
    )


WT = Path("/tmp/kqff-wt")


def test_success_no_fallback():
    primary = _StubAdapter(_result(True, "done"))
    built = []
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", False,
        fallback_binding=_flash_binding(),
        fallback_factory=lambda b: built.append(b) or _StubAdapter(_result(True, "ok")))
    assert res.dispatched is True
    assert prov is None
    assert built == []           # 成功不构造回退 adapter


def test_non_quota_failure_no_fallback():
    primary = _StubAdapter(_result(False, "AssertionError: expected 3 got 4", exit_code=1))
    built = []
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", False,
        fallback_binding=_flash_binding(),
        fallback_factory=lambda b: built.append(b) or _StubAdapter(_result(True, "ok")))
    assert res.dispatched is False
    assert prov is None
    assert built == []           # 非额度失败不回退（不掩盖真实错误）


def test_quota_failure_retries_with_flash_success():
    primary = _StubAdapter(_result(False, "错误：账户额度不足", exit_code=1))
    fb = _StubAdapter(_result(True, "flash done"))
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", False,
        fallback_binding=_flash_binding(), fallback_factory=lambda b: fb)
    assert res.dispatched is True
    assert prov == "deepseekflash"
    assert fb.calls == 1         # 恰好重派一次


def test_quota_failure_no_fallback_configured():
    primary = _StubAdapter(_result(False, "quota exceeded", exit_code=1))
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", False,
        fallback_binding=None, fallback_factory=lambda b: _StubAdapter(_result(True, "x")))
    assert res.dispatched is False
    assert prov is None          # 未配回退 → 原样返回失败，交 main() STOP


def test_single_hop_flash_also_quota_fails():
    primary = _StubAdapter(_result(False, "额度不足", exit_code=1))
    fb = _StubAdapter(_result(False, "insufficient balance", exit_code=1))
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", False,
        fallback_binding=_flash_binding(), fallback_factory=lambda b: fb)
    assert res.dispatched is False
    assert prov == "deepseekflash"
    assert fb.calls == 1         # 单跳：不再三跳、不无限重试


def test_dry_run_does_not_fallback_even_on_quota_output():
    primary = _StubAdapter(_result(False, "quota exceeded", exit_code=None))
    built = []
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", True,
        fallback_binding=_flash_binding(),
        fallback_factory=lambda b: built.append(b) or _StubAdapter(_result(True, "x")))
    assert prov is None
    assert built == []           # dry_run 直通，不触发回退

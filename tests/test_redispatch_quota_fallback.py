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


def test_success_with_quota_like_output_no_fallback():
    """brief rev7 §R3（findings #4/#5 erratum）：success 腿独立承重。primary
    dispatched=True 但 output 含额度词（weekly quota reset）→ 短路守卫
    ``if dry_run or result.dispatched: return`` 必须优先于 is_quota_error，
    绝不构造回退。删短路 → is_quota_error 命中额度词 → 误构造回退 → 本用例转红。
    （test_success_no_fallback 的 output "done" 非额度串，只是等价 witness，非承重。）
    """
    primary = _StubAdapter(_result(True, "build ok; note: weekly quota reset scheduled"))
    built = []
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", False,
        fallback_binding=_flash_binding(),
        fallback_factory=lambda b: built.append(b) or _StubAdapter(_result(True, "ok")))
    assert res.dispatched is True
    assert built == []           # success 腿：含额度词也绝不回退
    assert prov is None


def test_dry_run_does_not_fallback_even_on_quota_output():
    primary = _StubAdapter(_result(False, "quota exceeded", exit_code=None))
    built = []
    res, prov = _dispatch_with_quota_fallback(
        primary, WT, "b", "p", True,
        fallback_binding=_flash_binding(),
        fallback_factory=lambda b: built.append(b) or _StubAdapter(_result(True, "x")))
    assert prov is None
    assert built == []           # dry_run 直通，不触发回退


# ---- 项目 config 断言（B5 Step 3）----
from agentic_loop.resolve_paths import resolve_role_binding, resolve_role_fallback_binding

REPO = Path(__file__).resolve().parents[1]   # 被测 checkout（派发时即 WP worktree）


def test_project_config_primary_developer_stays_native():
    # 主档零回归：developer 主 binding 仍为 None（原生 kimi），评级语义不变。
    adapter_name, binding = resolve_role_binding("developer", repo=REPO)
    assert adapter_name == "kimi"
    assert binding is None


def test_project_config_resolves_flash_fallback():
    b = resolve_role_fallback_binding("developer", repo=REPO)
    assert b is not None
    assert b.provider == "deepseekflash"
    assert b.identity_model == "deepseek-v4-flash"
    assert b.cli_selector == "deepseek/v4-flash"
    assert b.api_key_env == "DEEPSEEK_API_KEY"


# ---- main() 接线级测试（codex rev1 finding #2）----
# 承重两条不变式，各绑定一个"必须转红"的 source mutation：
#   INV-W1「回退成功只 +1」：primary 额度失败 -> flash 成功后 executor.redispatch_count 恰为 N+1。
#     M1：main() 里 `new_count = count + 1` 改成 `count + 2`（或成功后再 +1 一次）-> 本测试转红。
#   INV-W2「circuit-breaker 先于派发」：count>=REDISPATCH_MAX 时 primary/fallback 都不调、flash 不构造。
#     M2：把 `_dispatch_with_quota_fallback` 调用移到 circuit-breaker（count>=max return 0）之前 -> 本测试转红。
import json
from agentic_loop.redispatch import main as _redispatch_main


def _write_status(tmp_path, *, count, state="REWORK"):
    itdir = tmp_path / "iters" / "2026-09-22-kimi-quota-flash-fallback"
    itdir.mkdir(parents=True, exist_ok=True)
    sf = itdir / "WP-01.status.json"
    sf.write_text(json.dumps({
        "schema_version": "agentic-wp-status/v2",
        "wp_id": "WP-01", "work_package_id": "WP-01",
        "iteration_id": "2026-09-22-kimi-quota-flash-fallback",
        "state": state,
        "git": {"worktree": str(tmp_path / "wt"), "base_branch": "plan/x",
                "base_commit": "0" * 40, "work_branch": "", "dispatch_commit": "", "merged_commit": ""},
        "executor": {"tool": "kimi", "session_id": "s", "redispatch_count": count,
                     "log_path": "", "started_at": "", "finished_at": ""},
        "review": {"decision": "N/A", "notes": "", "evidence_commit": "", "reviewed_at": ""},
        "consult": {"decision": "N/A", "consulted_tool": "codex", "session_id": "",
                    "evidence_commit": "", "consulted_at": ""},
        "evidence": {"remaining_risks": [], "brief": {"path": "x", "sha256": "", "rev": 2},
                     "attestation_commit": ""},
        "timestamps": {"created_at": "", "updated_at": "", "dispatched_at": ""},
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "wt").mkdir(exist_ok=True)
    return sf


class _StubDev:           # primary developer adapter（_resolve_developer 返回它）
    name = "kimi"
    def probe_injection(self): return True


class _StubFlash:         # fallback adapter（KimiAdapter 被 mock 成它）
    name = "kimi"
    def __init__(self, *a, **k): pass
    def implement(self, **k):
        return ImplementResult(dispatched=True, exit_code=0, output="flash ok",
                               command=("kimi",), dry_run=False)


def _stub_io(monkeypatch, tmp_path):
    """把 main() 的 IO 依赖全部导向 tmp_path / stub，使接线逻辑可离线断言。"""
    monkeypatch.setattr("agentic_loop.redispatch.main_repo", lambda: tmp_path)
    monkeypatch.setattr("agentic_loop.redispatch.iterations_dir", lambda: tmp_path / "iters")
    monkeypatch.setattr("agentic_loop.redispatch._run_validator", lambda v, s: None)
    monkeypatch.setattr("agentic_loop.redispatch._build_prompt", lambda *a, **k: "stub prompt")
    monkeypatch.setattr("agentic_loop.redispatch._git_output", lambda *a, **k: "")

    def fake_read_field(validator, status_file, dotted):
        cur = json.loads(Path(status_file).read_text(encoding="utf-8"))
        for part in dotted.split("."):
            cur = cur.get(part, "") if isinstance(cur, dict) else ""
        if cur is None:
            return ""
        return cur if isinstance(cur, str) else json.dumps(cur, ensure_ascii=False)
    monkeypatch.setattr("agentic_loop.redispatch._read_field", fake_read_field)

    stub_lock = tmp_path / "lock.sh"
    stub_lock.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    stub_lock.chmod(0o755)
    class _Res:
        path = stub_lock
        stack = None
    monkeypatch.setattr("agentic_loop.redispatch.resolve_wrapper", lambda name: _Res())

    def fake_run(cmd, *a, **k):
        joined = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        class _P:
            returncode = 0
            stderr = ""
        _P.stdout = "HEARTBEAT_OK\n" if "heartbeat" in joined else "PROBE_OK\n"
        return _P()
    monkeypatch.setattr("subprocess.run", fake_run)

    monkeypatch.setattr("agentic_loop.redispatch.get_roles", lambda repo=None: {"developer": "kimi"})
    monkeypatch.setattr("agentic_loop.redispatch._resolve_developer", lambda roles, probe=True: (_StubDev(), []))
    monkeypatch.setattr("agentic_loop.redispatch.resolve_role_fallback_binding", lambda role, repo=None: _flash_binding())
    monkeypatch.setattr("agentic_loop.redispatch.load_quota_patterns", lambda repo=None: ("额度", "quota"))


def test_wiring_fallback_success_increments_count_by_one(tmp_path, monkeypatch):
    """INV-W1 / M1：primary 额度失败 -> flash 成功，最终 redispatch_count 恰为 1（不是 2）。"""
    sf = _write_status(tmp_path, count=0)
    _stub_io(monkeypatch, tmp_path)

    def fake_dispatch(adapter, wt, brief, prompt, dry):
        if isinstance(adapter, _StubFlash):     # fallback 成功
            return ImplementResult(dispatched=True, exit_code=0, output="flash ok",
                                   command=("kimi",), dry_run=dry)
        return ImplementResult(dispatched=False, exit_code=1, output="错误：账户额度不足",
                               command=("kimi",), dry_run=dry)   # primary 额度失败
    monkeypatch.setattr("agentic_loop.redispatch._dispatch", fake_dispatch)
    monkeypatch.setattr("agentic_loop.redispatch.KimiAdapter", _StubFlash)

    assert _redispatch_main([str(sf)]) == 0
    final = json.loads(sf.read_text(encoding="utf-8"))
    assert final["executor"]["redispatch_count"] == 1, \
        "回退成功只 +1；=2 说明重复计数或 wrapper 内另写了 status"


def test_wiring_circuit_breaker_precedes_dispatch(tmp_path, monkeypatch):
    """INV-W2 / M2：count>=REDISPATCH_MAX 时 circuit-breaker 先 return，primary/fallback 都不调、flash 不构造。"""
    sf = _write_status(tmp_path, count=1)
    _stub_io(monkeypatch, tmp_path)
    monkeypatch.setenv("REDISPATCH_MAX", "1")

    calls = {"primary": 0, "wrapper": 0, "flash": 0}
    def spy_dispatch(*a, **k):
        calls["primary"] += 1
        return ImplementResult(dispatched=True, exit_code=0, output="", command=("kimi",), dry_run=False)
    monkeypatch.setattr("agentic_loop.redispatch._dispatch", spy_dispatch)
    orig_wrapper = _dispatch_with_quota_fallback
    def spy_wrapper(*a, **k):
        calls["wrapper"] += 1
        return orig_wrapper(*a, **k)
    monkeypatch.setattr("agentic_loop.redispatch._dispatch_with_quota_fallback", spy_wrapper)
    class _SpyFlash:
        def __init__(self, *a, **k):
            calls["flash"] += 1
    monkeypatch.setattr("agentic_loop.redispatch.KimiAdapter", _SpyFlash)

    assert _redispatch_main([str(sf)]) == 0
    assert calls == {"primary": 0, "wrapper": 0, "flash": 0}, \
        "circuit-breaker 必须先于任何派发/构造；非零说明派发被移到 breaker 前"
    final = json.loads(sf.read_text(encoding="utf-8"))
    assert final["executor"]["redispatch_count"] == 1, "circuit-breaker 不改写 count"

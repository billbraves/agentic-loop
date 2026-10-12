from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import inspect

from agentic_loop.adapters.base import ImplementResult
from agentic_loop.provider_binding import ProviderBinding
from agentic_loop.redispatch import _dispatch_with_quota_fallback
import agentic_loop.redispatch as redispatch


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


def _stub_io(monkeypatch, tmp_path, *, stub_resolver: bool = True):
    """把 main() 的 IO 依赖全部导向 tmp_path / stub，使接线逻辑可离线断言。

    ``stub_resolver=False`` 时不 patch ``_resolve_developer``，让测试能用真实
    resolver（B6/D6 需要真实 resolver 命中未知 adapter / 校验 probe 契约）。
    """
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

    if stub_resolver:
        monkeypatch.setattr("agentic_loop.redispatch._resolve_developer", lambda *, repo, registry=None, probe=True: (_StubDev(), [], False))
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


# ======================================================================
# A/B 族承重测试（WP-01 brief §A/§B）——resolver 层 stub adapter + monkeypatch
# 公共约定：registry 注入 kimi/claude/codex 三工厂与探针均带计数的 stub；
# 「所有非首选工厂计数 0」= 除首选键外每个工厂的工厂计数与探针计数均为 0。
# ======================================================================
import pytest

from agentic_loop.quota_fallback import DEFAULT_QUOTA_PATTERNS
from agentic_loop.redispatch import ProbeFailedError
from agentic_loop.redispatch import _resolve_developer


class _CountingProbeAdapter:
    """探针结果可配置、探针调用带计数的 stub adapter（非 Adapter 子类）。"""

    def __init__(self, name, *, probe_ok, probe_output):
        self.name = name
        self._probe_ok = probe_ok
        self._probe_output = probe_output
        self.probe_calls = 0

    def probe_injection_detail(self):
        self.probe_calls += 1
        return (self._probe_ok, self._probe_output)


def _counting_registry(*, probe_ok=False, probe_output=""):
    """kimi/claude/codex 三工厂 + 探针均带计数的 stub registry。

    返回 ``(registry, counters)``；``counters[key] = {"factory": int,
    "bindings": [..], "adapters": [_CountingProbeAdapter, ...]}``。
    """
    keys = ("kimi", "claude", "codex")
    counters = {key: {"factory": 0, "bindings": [], "adapters": []} for key in keys}

    def make_factory(key):
        def factory(binding):
            c = counters[key]
            c["factory"] += 1
            c["bindings"].append(binding)
            adapter = _CountingProbeAdapter(
                key, probe_ok=probe_ok, probe_output=probe_output)
            c["adapters"].append(adapter)
            return adapter
        return factory

    registry = {key: make_factory(key) for key in keys}
    return registry, counters


def _patch_resolver(monkeypatch, *, primary, binding, fallback_binding):
    """monkeypatch resolve_role_binding / resolve_role_fallback_binding /
    load_quota_patterns，注入纯内存场景（不触网、不真发子进程）。"""
    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_binding",
        lambda role, repo=None: (primary, binding),
    )
    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_fallback_binding",
        lambda role, repo=None: fallback_binding,
    )
    monkeypatch.setattr(
        "agentic_loop.redispatch.load_quota_patterns",
        lambda repo=None: DEFAULT_QUOTA_PATTERNS,
    )


def _assert_non_primary_untouched(counters, primary):
    """非首选工厂的工厂计数与探针计数均为 0（brief 公共约定）。"""
    for key in counters:
        if key != primary:
            assert counters[key]["factory"] == 0, f"{key} 工厂不应被构造"
            assert counters[key]["adapters"] == [], f"{key} 探针不应被调用"


# ---- A 族：不换 adapter（本 WP 唯一目标的直接承重）----

@pytest.mark.parametrize("primary", ["kimi", "codex"])
def test_no_adapter_switch_on_nonquota_stop(primary, monkeypatch, tmp_path):
    registry, counters = _counting_registry(
        probe_ok=False, probe_output="compile error")
    _patch_resolver(monkeypatch, primary=primary, binding=object(), fallback_binding=None)

    with pytest.raises(ProbeFailedError) as exc:
        _resolve_developer(repo=tmp_path, registry=registry)

    assert str(exc.value) == "probe failed: other"
    assert counters[primary]["factory"] == 1
    _assert_non_primary_untouched(counters, primary)


@pytest.mark.parametrize("primary", ["kimi", "codex"])
def test_no_adapter_switch_on_quota_stop(primary, monkeypatch, tmp_path):
    registry, counters = _counting_registry(
        probe_ok=False, probe_output="insufficient balance")
    _patch_resolver(monkeypatch, primary=primary, binding=object(), fallback_binding=None)

    with pytest.raises(ProbeFailedError) as exc:
        _resolve_developer(repo=tmp_path, registry=registry)

    assert str(exc.value) == "probe failed: quota, no fallback"
    assert counters[primary]["factory"] == 1
    _assert_non_primary_untouched(counters, primary)


def test_unknown_adapter_builds_nothing(monkeypatch, tmp_path, capsys):
    registry, counters = _counting_registry()
    sentinel = "no-such-adapter-SENTINEL4"
    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_binding",
        lambda role, repo=None: (sentinel, None),
    )
    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_fallback_binding",
        lambda role, repo=None: None,
    )
    monkeypatch.setattr(
        "agentic_loop.redispatch.load_quota_patterns",
        lambda repo=None: DEFAULT_QUOTA_PATTERNS,
    )

    with pytest.raises(ProbeFailedError) as exc:
        _resolve_developer(repo=tmp_path, registry=registry)

    assert str(exc.value) == "unknown developer adapter"
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    for key in ("kimi", "claude", "codex"):
        assert counters[key]["factory"] == 0
        assert counters[key]["adapters"] == []


# ---- B 族：结局与状态贯通 ----

@pytest.mark.parametrize("primary", ["kimi", "codex"])
def test_quota_flash_returns_same_registry_key(primary, monkeypatch, tmp_path):
    registry, counters = _counting_registry(
        probe_ok=False, probe_output="insufficient balance")
    fallback_binding = object()
    _patch_resolver(monkeypatch, primary=primary, binding=object(),
                    fallback_binding=fallback_binding)

    adapter, reasons, fallback_applied = _resolve_developer(
        repo=tmp_path, registry=registry)

    assert fallback_applied is True
    # 返回 adapter 由首选工厂构造（S9 flash 构造的那一个）
    assert adapter is counters[primary]["adapters"][-1]
    assert counters[primary]["factory"] == 2          # S5 探针构造 + S9 flash 构造
    assert counters[primary]["bindings"][-1] is fallback_binding  # 最后一次实参
    if primary == "codex":
        assert counters["kimi"]["factory"] == 0


def test_probe_output_is_read_by_consumer(monkeypatch, tmp_path):
    fallback_binding = object()
    _patch_resolver(monkeypatch, primary="kimi", binding=object(),
                    fallback_binding=fallback_binding)

    # 额度输出 → flash 返回
    reg_q, _ = _counting_registry(
        probe_ok=False, probe_output="insufficient balance")
    adapter_q, reasons_q, fallback_q = _resolve_developer(
        repo=tmp_path, registry=reg_q)
    assert fallback_q is True

    # 非额度输出 → 抛 ProbeFailedError
    reg_n, _ = _counting_registry(probe_ok=False, probe_output="compile error")
    with pytest.raises(ProbeFailedError) as exc:
        _resolve_developer(repo=tmp_path, registry=reg_n)
    assert str(exc.value) == "probe failed: other"


def test_probe_stage_flash_disables_dispatch_flash(tmp_path, monkeypatch):
    sf = _write_status(tmp_path, count=0)
    _stub_io(monkeypatch, tmp_path)
    monkeypatch.setenv("REDISPATCH_DRY_RUN", "1")
    # 探针阶段已 flash（fb=True）→ dispatch 阶段不得再带 fallback_binding
    monkeypatch.setattr(
        "agentic_loop.redispatch._resolve_developer",
        lambda *, repo, registry=None, probe=True: (_StubDev(), [], True),
    )
    captured = {}
    orig = _dispatch_with_quota_fallback
    def spy_dispatch(*a, **k):
        captured["fallback_binding"] = k.get("fallback_binding")
        return orig(*a, **k)
    monkeypatch.setattr("agentic_loop.redispatch._dispatch_with_quota_fallback",
                        spy_dispatch)

    assert _redispatch_main([str(sf)]) == 0
    assert captured["fallback_binding"] is None


def test_fallback_flag_false_on_pass(monkeypatch, tmp_path):
    registry, counters = _counting_registry(probe_ok=True, probe_output="")
    _patch_resolver(monkeypatch, primary="kimi", binding=object(), fallback_binding=None)

    adapter, reasons, fallback_applied = _resolve_developer(
        repo=tmp_path, registry=registry)

    assert fallback_applied is False


def test_probe_false_returns_primary_without_probing(monkeypatch, tmp_path):
    registry, counters = _counting_registry(probe_ok=False, probe_output="")
    _patch_resolver(monkeypatch, primary="kimi", binding=object(), fallback_binding=None)

    adapter, reasons, fallback_applied = _resolve_developer(
        repo=tmp_path, registry=registry, probe=False)

    assert fallback_applied is False
    assert adapter is counters["kimi"]["adapters"][0]
    assert counters["kimi"]["adapters"][0].probe_calls == 0  # 首选工厂探针计数 0
    _assert_non_primary_untouched(counters, "kimi")


# ======================================================================
# C 族：零外流（resolver 层 stub adapter + monkeypatch）
# 哨兵经 stub 的 probe_injection_detail() 返回值注入（不真发子进程）；
# native 实例用 NATIVE_EGRESS_SENTINEL，bound 实例用 BOUND_EGRESS_SENTINEL。
# ======================================================================
from agentic_loop.adapters.kimi import KimiAdapter

NATIVE_EGRESS_SENTINEL = "NATIVE_EGRESS_SENTINEL_7f9a"
BOUND_EGRESS_SENTINEL = "BOUND_EGRESS_SENTINEL_3c8e"


class _StubProviderBinding:
    """bound 实例的 binding stub；resolver 仅透传该对象给工厂，不读字段。"""

    pass


def _egress_binding(binding_kind):
    """binding_kind -> (binding, sentinel)。native -> (None, NATIVE 哨兵)；bound -> (stub, BOUND 哨兵)。"""
    if binding_kind == "native":
        return None, NATIVE_EGRESS_SENTINEL
    return _StubProviderBinding(), BOUND_EGRESS_SENTINEL


@pytest.mark.parametrize("binding_kind", ["native", "bound"])
def test_zero_egress_on_probe_pass(binding_kind, monkeypatch, tmp_path, capsys):
    # C0 通过支零外流：首选探针通过（ok=True），probe_output 含哨兵也不外吐。
    binding, sentinel = _egress_binding(binding_kind)
    registry, counters = _counting_registry(probe_ok=True, probe_output=sentinel)
    _patch_resolver(monkeypatch, primary="kimi", binding=binding, fallback_binding=None)

    adapter, reasons, fallback_applied = _resolve_developer(repo=tmp_path, registry=registry)

    assert fallback_applied is False
    assert adapter is counters["kimi"]["adapters"][0]   # 正常返回首选 adapter
    for item in reasons:
        assert sentinel not in item
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err


@pytest.mark.parametrize("binding_kind", ["native", "bound"])
def test_zero_egress_on_quota_flash_return(binding_kind, monkeypatch, tmp_path, capsys):
    # C1 可返回支（额度 + 有 fallback）零外流：探针输出含哨兵也不外吐。
    binding, sentinel = _egress_binding(binding_kind)
    registry, counters = _counting_registry(
        probe_ok=False, probe_output=f"insufficient balance {sentinel}")
    _patch_resolver(monkeypatch, primary="kimi", binding=binding,
                    fallback_binding=_StubProviderBinding())

    adapter, reasons, fallback_applied = _resolve_developer(repo=tmp_path, registry=registry)

    assert fallback_applied is True   # 确实走了可返回支，防空路径假过
    for item in reasons:
        assert sentinel not in item
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err


@pytest.mark.parametrize("binding_kind", ["native", "bound"])
def test_zero_egress_on_quota_stop(binding_kind, monkeypatch, tmp_path, capsys):
    # C2 额度 + 无 fallback STOP 支零外流。
    binding, sentinel = _egress_binding(binding_kind)
    registry, counters = _counting_registry(
        probe_ok=False, probe_output=f"insufficient balance {sentinel}")
    _patch_resolver(monkeypatch, primary="kimi", binding=binding, fallback_binding=None)

    with pytest.raises(ProbeFailedError) as exc:
        _resolve_developer(repo=tmp_path, registry=registry)

    assert str(exc.value) == "probe failed: quota, no fallback"
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err


@pytest.mark.parametrize("binding_kind", ["native", "bound"])
def test_zero_egress_on_nonquota_stop(binding_kind, monkeypatch, tmp_path, capsys):
    # C3 非额度 STOP 支零外流。
    binding, sentinel = _egress_binding(binding_kind)
    registry, counters = _counting_registry(
        probe_ok=False, probe_output=f"compile error {sentinel}")
    _patch_resolver(monkeypatch, primary="kimi", binding=binding, fallback_binding=None)

    with pytest.raises(ProbeFailedError) as exc:
        _resolve_developer(repo=tmp_path, registry=registry)

    assert str(exc.value) == "probe failed: other"
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err


def test_kimi_bound_detail_redacts_api_key(monkeypatch):
    # C4 adapter 层 oracle：bound 支 probe_injection_detail 的 detail 串
    # 不含 api_key_env 指向的密钥值，且仍含 stdout 里另一段非密钥文本。
    binding = _flash_binding()
    secret = "sk-secret-api-key-1a2b3c4d5e6f"
    non_key_text = "deepseek probe body text"
    monkeypatch.setenv(binding.api_key_env, secret)

    class _FakeProc:
        returncode = 0
        stdout = f"prefix {secret} suffix {non_key_text}"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeProc())

    adapter = KimiAdapter(binding=binding)
    ok, detail = adapter.probe_injection_detail()

    assert secret not in detail
    assert non_key_text in detail


# ======================================================================
# Stage 2 余项：D2/D3/D4/D5 + CHAR-1（adapter 层 detail 承重、签名与语义承重、
# repo 透传承重、dispatch fallback 接线承重、退化配置承重）
# ======================================================================


@pytest.mark.parametrize("binding_kind", ["native", "bound"])
def test_probe_injection_binding_modes(binding_kind, monkeypatch):
    # D2 adapter 层承重：probe_injection_detail() 的 ok 为精确 bool，detail 串
    # 承载真实 stdout（非空、含对应分支哨兵），而非被清空或替换为固定占位。
    if binding_kind == "native":
        adapter = KimiAdapter(binding=None)
        sentinel = NATIVE_EGRESS_SENTINEL
        fake_stdout = f"PROBE_OK {sentinel}"
    else:
        binding = _flash_binding()
        monkeypatch.setenv(binding.api_key_env, "sk-d2")
        adapter = KimiAdapter(binding=binding)
        sentinel = BOUND_EGRESS_SENTINEL
        fake_stdout = f"DEEPSEEK_PROBE_OK {sentinel}"

    class _FakeProc:
        returncode = 0
        stdout = fake_stdout

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeProc())

    ok, detail = adapter.probe_injection_detail()

    assert ok is True
    assert detail != ""
    assert sentinel in detail


def test_flattened_roles_cannot_select_adapter(monkeypatch, tmp_path):
    # D3 签名+语义承重：_resolve_developer 不读取任何 get_roles（redispatch 模块
    # 里根本没有该属性）；即便强行塞一个返回 ["claude"] 的 get_roles，也不会改变
    # 首选 adapter 的工厂/探针调用（首选仍由 resolve_role_binding 决定）。
    registry, counters = _counting_registry(probe_ok=True, probe_output="")
    _patch_resolver(monkeypatch, primary="kimi", binding=object(), fallback_binding=None)

    # redispatch 模块无 get_roles；用 raising=False 兜住不存在的 setattr。
    monkeypatch.setattr(
        "agentic_loop.redispatch.get_roles",
        lambda repo=None: {"developer": ["claude"]},
        raising=False,
    )

    adapter, reasons, fallback_applied = _resolve_developer(repo=tmp_path, registry=registry)

    assert fallback_applied is False
    assert counters["kimi"]["factory"] == 1
    assert counters["claude"]["factory"] == 0
    assert isinstance(adapter, _CountingProbeAdapter)
    assert adapter.name == "kimi"
    assert adapter is counters["kimi"]["adapters"][0]

    sig = inspect.signature(_resolve_developer)
    for name, kind in [
        ("repo", inspect.Parameter.KEYWORD_ONLY),
        ("registry", inspect.Parameter.KEYWORD_ONLY),
        ("probe", inspect.Parameter.KEYWORD_ONLY),
    ]:
        assert sig.parameters[name].kind == kind


def test_all_config_reads_share_one_repo(monkeypatch, tmp_path):
    # D4 repo 透传承重：_resolve_developer 的三处 config 读取
    # （resolve_role_binding / resolve_role_fallback_binding / load_quota_patterns）
    # 都必须把调用方传入的同一个 repo 透传下去，不得各自回退到 main_repo()/None
    # 产生漂移。
    registry, _ = _counting_registry(probe_ok=True, probe_output="")

    recorded = {
        "resolve_role_binding": [],
        "resolve_role_fallback_binding": [],
        "load_quota_patterns": [],
    }

    def spy_for(key, original):
        def spy(*args, **kwargs):
            if "repo" in kwargs:
                repo = kwargs["repo"]
            elif len(args) >= 2:
                repo = args[1]
            else:
                repo = args[0]
            recorded[key].append(repo)
            return original(*args, **kwargs)
        return spy

    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_binding",
        spy_for("resolve_role_binding", redispatch.resolve_role_binding),
    )
    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_fallback_binding",
        spy_for("resolve_role_fallback_binding", redispatch.resolve_role_fallback_binding),
    )
    monkeypatch.setattr(
        "agentic_loop.redispatch.load_quota_patterns",
        spy_for("load_quota_patterns", redispatch.load_quota_patterns),
    )

    adapter, reasons, fallback_applied = _resolve_developer(repo=tmp_path, registry=registry)

    assert fallback_applied is False
    for key in recorded:
        assert recorded[key], f"{key} 未被调用"
        assert all(r == tmp_path for r in recorded[key]), \
            f"{key} 的 repo 透传漂移: {recorded[key]}"
    # 三处 config 读取恰好各一次，不多不少（防重复读取/遗漏读取）。
    assert sum(len(recorded[key]) for key in recorded) == 3


def test_main_dispatch_fallback_binding_uses_repo_root(tmp_path, monkeypatch):
    # D5 接线承重：main() 在 dispatch 阶段读取 fallback binding 时，必须把
    # repo_root（main_repo() 的返回值）透传给 resolve_role_fallback_binding，
    # 不得改传 None 或 status 文件所在目录等其它值。
    sf = _write_status(tmp_path, count=0)
    _stub_io(monkeypatch, tmp_path)
    monkeypatch.setenv("REDISPATCH_DRY_RUN", "1")

    recorded = []
    def spy(*args, **kwargs):
        if "repo" in kwargs:
            repo = kwargs["repo"]
        elif len(args) >= 2:
            repo = args[1]
        else:
            repo = args[0]
        recorded.append(repo)
        return _flash_binding()

    monkeypatch.setattr("agentic_loop.redispatch.resolve_role_fallback_binding", spy)

    assert _redispatch_main([str(sf)]) == 0

    assert len(recorded) >= 1
    expected = redispatch.main_repo()
    assert all(r == expected for r in recorded)


@pytest.mark.parametrize(
    "case",
    ["no_config", "empty_roles", "dev_empty_list", "dev_empty_str", "dev_missing"],
)
def test_degenerate_config_resolves_native_kimi_no_fallback(case, tmp_path):
    # CHAR-1 退化配置承重：任何使 developer 角色解析为空的退化 config，
    # 都必须稳定落到 (kimi, None) 首选 + None fallback，不抛异常、不漂移。
    if case != "no_config":
        cfgdir = tmp_path / ".agentic"
        cfgdir.mkdir(parents=True, exist_ok=True)
        body = {
            "empty_roles": "[roles]\n",
            "dev_empty_list": "[roles]\ndeveloper = []\n",
            "dev_empty_str": '[roles]\ndeveloper = ""\n',
            "dev_missing": '[roles]\nreviewer = "claude"\n',
        }[case]
        (cfgdir / "config.toml").write_text(body, encoding="utf-8")

    assert resolve_role_binding("developer", repo=tmp_path) == ("kimi", None)
    assert resolve_role_fallback_binding("developer", repo=tmp_path) is None


# ======================================================================
# Stage 3 余项：B6（legacy 交人出口承重）+ D6（resolver 调用契约承重）+
# D7（默认 registry 透传 binding 承重）
# ======================================================================


def test_legacy_path_unknown_adapter_stops_not_crashes(tmp_path, monkeypatch, capsys):
    # B6 F8 legacy 交人出口承重：legacy bash 探针通过后，dispatch 阶段用
    # probe=False 的真实 resolver 命中未知 adapter → 必须打印 STOP 并 return 0
    # （不崩溃、不派发），且未知 adapter 名（哨兵）绝不外吐。
    sf = _write_status(tmp_path, count=0)
    _stub_io(monkeypatch, tmp_path, stub_resolver=False)
    sentinel = "no-such-adapter-SENTINEL6"
    monkeypatch.setattr(
        "agentic_loop.redispatch.resolve_role_binding",
        lambda role, repo=None: (sentinel, None),
    )
    monkeypatch.setenv("PROBE_CMD", "true")
    monkeypatch.setenv("REDISPATCH_DRY_RUN", "1")

    dispatch_calls = []
    monkeypatch.setattr(
        "agentic_loop.redispatch._dispatch_with_quota_fallback",
        lambda *a, **k: dispatch_calls.append(1),
    )

    assert _redispatch_main([str(sf)]) == 0
    assert dispatch_calls == []
    captured = capsys.readouterr()
    assert captured.out.strip() == "REDISPATCH_STOP: probe failed — 不重派,查根因"
    assert sentinel not in captured.out
    assert sentinel not in captured.err


@pytest.mark.parametrize("path", ["main", "legacy"])
def test_main_resolver_call_contract(tmp_path, monkeypatch, path):
    # D6 调用契约承重：main() 调用 _resolve_developer 时，repo 必须透传
    # main_repo() 返回值；probe 必须按分支取 True（无 PROBE_CMD，非 legacy）
    # 或 False（legacy bash 探针已通过，dispatch 阶段补解析），且恰好一次。
    sf = _write_status(tmp_path, count=0)
    _stub_io(monkeypatch, tmp_path, stub_resolver=False)

    recorded = []
    def spy_resolver(*, repo, registry=None, probe=True):
        recorded.append((repo, probe))
        return (_StubDev(), [], False)
    monkeypatch.setattr("agentic_loop.redispatch._resolve_developer", spy_resolver)

    if path == "legacy":
        monkeypatch.setenv("PROBE_CMD", "echo PROBE_OK")
    else:
        monkeypatch.delenv("PROBE_CMD", raising=False)
    monkeypatch.setenv("REDISPATCH_DRY_RUN", "1")

    assert _redispatch_main([str(sf)]) == 0
    assert len(recorded) == 1
    repo, probe = recorded[0]
    assert repo == redispatch.main_repo()
    assert probe is (path == "main")


@pytest.mark.parametrize("primary", ["kimi", "claude"])
def test_default_registry_preserves_adapter_and_binding(primary, monkeypatch, tmp_path):
    # D7 默认 registry 承重：不注入 registry 时，_resolve_developer 必须用默认
    # registry 里对应首选键的工厂构造 adapter，并把 resolve_role_binding 返回的
    # binding 原样（同一对象）透传给工厂；非首选工厂绝不构造。
    sentinel_binding = object()
    _patch_resolver(monkeypatch, primary=primary, binding=sentinel_binding,
                    fallback_binding=None)

    constructed = {"kimi": [], "claude": []}
    def spy_kimi(*, kimi_bin="kimi", binding=None):
        constructed["kimi"].append(binding)
        return _StubDev()
    def spy_claude(*, claude_bin="claude", binding=None):
        constructed["claude"].append(binding)
        return _StubDev()
    monkeypatch.setattr("agentic_loop.redispatch.KimiAdapter", spy_kimi)
    monkeypatch.setattr("agentic_loop.redispatch.ClaudeAdapter", spy_claude)

    adapter, reasons, fallback_applied = _resolve_developer(repo=tmp_path, probe=False)

    assert fallback_applied is False
    assert isinstance(adapter, _StubDev)
    assert constructed[primary] == [sentinel_binding]
    other = "claude" if primary == "kimi" else "kimi"
    assert constructed[other] == []

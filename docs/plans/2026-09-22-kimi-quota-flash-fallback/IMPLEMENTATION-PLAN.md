# kimi 额度不足自动回退 deepseek-flash — Implementation Plan

> **For agentic workers:** 本仓有强治理（AGENTS.md）。用户已选定「新 WP / 新 plan 完整流程」交付，
> 因此**代码实现（Phase B）经 WP 生命周期由 kimi 执行**（本计划的 TDD 任务即 brief 验收标的与派发
> prompt 依据），Phase A/C 的治理步骤由编排者执行。步骤用 checkbox（`- [ ]`）跟踪。
> 设计依据见同目录 `DESIGN.md`（已与用户逐节确认）。

**Goal:** 让 `agentic redispatch` 在 kimi 套餐额度不足导致派发失败时，自动改用 deepseek-v4-flash 重派一次（单跳），无需人工。

**Architecture:** 三层——纯函数额度检测（`quota_fallback.py`）+ 配置驱动的回退 binding 解析（`resolve_paths.resolve_role_fallback_binding`）+ 派发层重试编排（`redispatch._dispatch_with_quota_fallback`）。复用既有 `KimiAdapter` 的 DeepSeek 临时 config 注入机制，不改 adapter。对现有裸 kimi 配置零回归。

**Tech Stack:** Python 3.11（tomllib/tomli）、pytest、dataclass、既有 `ProviderBinding`/`build_binding`/`ImplementResult`。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `src/agentic_loop/quota_fallback.py` | 纯函数额度检测 + 模式清单加载（无 I/O 副作用） | Create |
| `src/agentic_loop/resolve_paths.py` | 新增 `resolve_role_fallback_binding`（读可选 `fallback_provider`） | Modify |
| `src/agentic_loop/redispatch.py` | 新增 `_dispatch_with_quota_fallback` + 接入 `main()` 派发点 | Modify |
| `.agentic/config.toml` | 追加 `[providers.deepseekflash]` + `roles.developer` 加 `fallback_provider` | Modify |
| `tests/test_quota_fallback.py` | 检测纯函数 + 模式加载单测 | Create |
| `tests/test_resolve_fallback_binding.py` | 回退 binding 解析单测（含零回归负例） | Create |
| `tests/test_redispatch_quota_fallback.py` | 派发回退编排单测（stub adapter 注入，无真实 kimi/网络） | Create |

**禁改（forbidden）**：`src/agentic_loop/independence.py`、`src/agentic_loop/gate/**`、`src/agentic_loop/adapters/kimi.py`、`uv.lock`、其它 WP 所有权文件。本改动**不碰** #38 边界与信任根评级。

---

## Phase A — 治理 setup（编排者执行）

### Task A1: 切集成分支 + 独立 worktree（off 最新 main）

- [ ] **Step 1: 确认 main tip 与占用**

Run: `git -C /Users/admin/vibe/agentic_loop worktree list | /usr/bin/grep -E '\[main\]'`
Expected: 输出含 `7c318f4 [main]`（main 被 sibling worktree `agentic-loop-main-codex-merge` 占用，故新分支必须用独立 worktree，不能 checkout main）。

- [ ] **Step 2: 创建集成分支 worktree（从 main 切出）**

Run:
```bash
git -C /Users/admin/vibe/agentic_loop worktree add -b plan/2026-09-22-kimi-quota-flash-fallback \
  /Users/admin/vibe/.worktrees/kqff main
```
Expected: `Preparing worktree (new branch 'plan/2026-09-22-kimi-quota-flash-fallback')`；HEAD=7c318f4。

### Task A2: 落盘设计/计划文档到新 iteration 目录

- [ ] **Step 1: 复制 spec 与 plan 到新 worktree 的 iteration 目录**

Run:
```bash
mkdir -p /Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback
cp /Users/admin/vibe/agentic_loop/docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md \
   /Users/admin/vibe/agentic_loop/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md \
   /Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/
```
Expected: 两文件就位（原主仓工作树里的 untracked 副本随后可删，避免游离）。

- [ ] **Step 2: 显式路径提交文档（先查 MM，排除 uv.lock）**

Run:
```bash
cd /Users/admin/vibe/.worktrees/kqff && git status --short
git add docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md \
        docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md
git commit -m "docs(kqff): 设计 spec + 实现计划（kimi 额度回退 deepseek-flash）" -- \
  docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md \
  docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md
```
Expected: 1 commit；`git status --short` 提交前无 `MM`（无并发 session）。

### Task A3: 建 plan status + WP-01 brief + WP-01 status（从模板）

- [ ] **Step 1: 从模板生成三份产物**

以 `docs/agentic/templates/PLAN.json`、`WORK_PACKAGE.md`、`STATUS.json` 为基，在
`docs/plans/2026-09-22-kimi-quota-flash-fallback/` 下创建：
- `PLAN-01.status.json`：schema `agentic-plan-status/v1`；`git.base_branch=plan/2026-09-22-kimi-quota-flash-fallback`、`git.target_branch=main`、`work_packages=["WP-01"]`、`state=DRAFT`。
- `WP-01-brief.md`：scope/allowed_paths/forbidden_paths/验收不变式直接引自本计划 §File Structure 与 `DESIGN.md` §4-§8；交付物 = 3 源改动 + 3 测试文件 + config。
- `WP-01.status.json`：`state=DRAFT`、`phase` 视 plan 定义（建议非 architecture 档 → gate effort=medium）、`git.base_branch/base_commit` 指向集成分支 tip、`role=developer`、`executor.tool=kimi`。

- [ ] **Step 2: 校验 status 合法**

Run: `cd /Users/admin/vibe/.worktrees/kqff && PYTHONPATH=src python3.11 -m agentic_loop.validate_wp_status docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`
Expected: `STATUS_VALID`（无 PYTHONPATH=src 会 ModuleNotFoundError，见 KNOWN-ISSUE-bare-python3）。

### Task A4: codex consult（冻结前第二签名，DESIGN §10.3 建议）

- [ ] **Step 1: 就 WP-01 brief 跑 codex consult，结论须 ACCEPT 才可冻结**

按章程 §3.2/§0.1，非信任根 WP 不强制 consult，但派发路径较敏感，建议过一次低成本 codex consult。
Run（编排者，主仓或 worktree 内，按既有 consult 制品约定）：产出 `WP-01-consult-codex.md` + verdict。
Expected: verdict=ACCEPT → 进 A5 冻结；若 REWORK → 修 brief 再 consult，不冻结。

### Task A5: 冻结 WP-01（DRAFT→APPROVED）+ freeze 提交

- [ ] **Step 1: 冻结并显式路径提交 brief+status（freeze commit，签名留空）**

按 §4.3 commit discipline：status 文件在集成分支上只提交两次（freeze 与 finalize）。
Run:
```bash
cd /Users/admin/vibe/.worktrees/kqff
git add docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md \
        docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json \
        docs/plans/2026-09-22-kimi-quota-flash-fallback/PLAN-01.status.json
git commit -m "freeze(kqff/WP-01): DRAFT→APPROVED（codex consult ACCEPT）" -- <上述三路径>
```
Expected: freeze commit 落地；PLAN state DRAFT→ACTIVE（如需 `agentic plan` 激活按 CLI 约定）。

---

## Phase B — 实现（TDD；kimi 执行，编排者独立复核）

> 测试统一前置：`SRC = Path(__file__).resolve().parents[1] / "src"` 插入 `sys.path`（本仓约定，见 test_provider_binding.py）。
> 运行测试命令统一：`env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest <path> -q`
> （**必须 `env -u AGENTIC_PYTHON`**，否则泄漏进 test_gate_runner_shell 子进程绕过 python3 stub → 假失败）。

### Task B1: `quota_fallback.is_quota_error`（纯检测）

**Files:**
- Create: `src/agentic_loop/quota_fallback.py`
- Test: `tests/test_quota_fallback.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_quota_fallback.py
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.quota_fallback import is_quota_error


def test_matches_chinese_quota_terms():
    assert is_quota_error("错误：账户额度不足，请充值") is True
    assert is_quota_error("套餐已用尽") is True
    assert is_quota_error("配额超限") is True


def test_matches_english_quota_terms():
    assert is_quota_error("Error: insufficient balance") is True
    assert is_quota_error("quota exceeded for this key") is True
    assert is_quota_error("HTTP 429 Too Many Requests") is True
    assert is_quota_error("payment required (402)") is True


def test_case_insensitive():
    assert is_quota_error("QUOTA EXCEEDED") is True
    assert is_quota_error("Insufficient Balance") is True


def test_negative_cases_return_false():
    assert is_quota_error("ModuleNotFoundError: no module named foo") is False
    assert is_quota_error("AssertionError: expected 3 got 4") is False
    assert is_quota_error("PROBE_OK") is False
    assert is_quota_error("") is False


def test_custom_patterns_override_defaults():
    # 自定义清单生效时，默认清单不再参与匹配。
    assert is_quota_error("quota exceeded", patterns=["credit"]) is False
    assert is_quota_error("out of credit", patterns=["credit"]) is True
```

- [ ] **Step 2: 运行验证失败**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_quota_fallback.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentic_loop.quota_fallback'`。

- [ ] **Step 3: 写最小实现**

```python
# src/agentic_loop/quota_fallback.py
#!/usr/bin/env python3
"""Pure quota-exhaustion detection for developer-dispatch fallback.

`is_quota_error` is a pure string predicate (no I/O). `load_quota_patterns`
reads an optional project-config override and fails safe to built-in defaults.
Neither imports git/subprocess nor touches status; the dispatch layer
(redispatch) owns all side effects.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

# 大小写不敏感；覆盖中英常见额度措辞 + HTTP 429/402。正向命中才触发回退，
# 避免把普通失败（编译/测试错误）误判为额度问题而掩盖真实错误（AGENTS.md §7）。
DEFAULT_QUOTA_PATTERNS: tuple[str, ...] = (
    r"额度", r"配额", r"套餐", r"用量", r"余额",
    r"quota", r"insufficient", r"balance", r"credit",
    r"exceeded", r"rate.?limit", r"too many requests",
    r"billing", r"\b429\b", r"\b402\b",
)


def is_quota_error(output: str, patterns: Sequence[str] | None = None) -> bool:
    """True iff ``output`` matches any quota pattern (case-insensitive). Pure.

    空输出 → False。坏的正则（来自 config 覆盖）跳过而非崩溃（fail-safe）。
    """
    if not output:
        return False
    pats = DEFAULT_QUOTA_PATTERNS if patterns is None else tuple(patterns)
    for p in pats:
        try:
            if re.search(p, output, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False
```

- [ ] **Step 4: 运行验证通过**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_quota_fallback.py -q`
Expected: PASS（6 passed）。

- [ ] **Step 5: 提交**

```bash
git add src/agentic_loop/quota_fallback.py tests/test_quota_fallback.py
git commit -m "feat(kqff): quota_fallback.is_quota_error 纯函数额度检测" -- \
  src/agentic_loop/quota_fallback.py tests/test_quota_fallback.py
```

### Task B2: `quota_fallback.load_quota_patterns`（config 覆盖 + fail-safe）

**Files:**
- Modify: `src/agentic_loop/quota_fallback.py`
- Test: `tests/test_quota_fallback.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 tests/test_quota_fallback.py
from agentic_loop.quota_fallback import DEFAULT_QUOTA_PATTERNS, load_quota_patterns


def _write_cfg(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / ".agentic" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body, encoding="utf-8")
    return tmp_path


def test_load_patterns_returns_defaults_when_no_config(tmp_path):
    assert load_quota_patterns(repo=tmp_path) == DEFAULT_QUOTA_PATTERNS


def test_load_patterns_reads_override(tmp_path):
    repo = _write_cfg(tmp_path, '[quota_fallback]\npatterns = ["额度", "quota", "429"]\n')
    assert load_quota_patterns(repo=repo) == ("额度", "quota", "429")


def test_load_patterns_fails_safe_on_bad_override(tmp_path):
    # patterns 非字符串列表 / 空列表 → 回落默认，绝不抛到派发主链。
    repo = _write_cfg(tmp_path, '[quota_fallback]\npatterns = []\n')
    assert load_quota_patterns(repo=repo) == DEFAULT_QUOTA_PATTERNS
    repo2 = _write_cfg(tmp_path / "b", '[quota_fallback]\npatterns = "额度"\n')
    assert load_quota_patterns(repo=repo2) == DEFAULT_QUOTA_PATTERNS
```

- [ ] **Step 2: 运行验证失败**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_quota_fallback.py -q`
Expected: FAIL — `ImportError: cannot import name 'load_quota_patterns'`。

- [ ] **Step 3: 追加实现**

```python
# 追加到 src/agentic_loop/quota_fallback.py
def load_quota_patterns(repo: Path | None = None) -> tuple[str, ...]:
    """读可选 ``[quota_fallback] patterns``；缺省/坏配置回落 DEFAULT（fail-safe）。

    直读 ``_load_config``（避开 CONFIG_SECTIONS 白名单过滤）；任何异常都回落默认，
    绝不把解析失败抛进派发主链。
    """
    try:
        from agentic_loop.resolve_paths import _load_config, main_repo

        repo = repo or main_repo()
        data: Any = _load_config(repo) or {}
        section = data.get("quota_fallback") if isinstance(data, dict) else None
        if isinstance(section, dict):
            pats = section.get("patterns")
            if (isinstance(pats, (list, tuple)) and pats
                    and all(isinstance(x, str) and x for x in pats)):
                return tuple(pats)
    except Exception:
        pass
    return DEFAULT_QUOTA_PATTERNS
```

- [ ] **Step 4: 运行验证通过**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_quota_fallback.py -q`
Expected: PASS（9 passed）。

- [ ] **Step 5: 提交**

```bash
git add src/agentic_loop/quota_fallback.py tests/test_quota_fallback.py
git commit -m "feat(kqff): load_quota_patterns 读 config 覆盖 + fail-safe 回落默认" -- \
  src/agentic_loop/quota_fallback.py tests/test_quota_fallback.py
```

### Task B3: `resolve_paths.resolve_role_fallback_binding`

**Files:**
- Modify: `src/agentic_loop/resolve_paths.py`（在 `resolve_role_binding` 之后新增）
- Test: `tests/test_resolve_fallback_binding.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_resolve_fallback_binding.py
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
```

- [ ] **Step 2: 运行验证失败**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_resolve_fallback_binding.py -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_role_fallback_binding'`。

- [ ] **Step 3: 写实现（紧跟 `resolve_role_binding` 之后）**

```python
# 追加到 src/agentic_loop/resolve_paths.py（resolve_role_binding 之后）
def resolve_role_fallback_binding(
    role: str, repo: Path | None = None
) -> "Any":
    """Resolve the OPTIONAL quota-fallback binding for ``role``.

    Reads ``roles.<role>`` dict's optional ``fallback_provider`` key and builds a
    ProviderBinding from that provider's config. Returns ``None`` (zero-regression)
    when the role is not a dict, carries no ``fallback_provider``, or the provider
    section is missing/invalid. NEVER raises into the dispatch path.
    """
    from agentic_loop.provider_binding import ProviderConfigError, build_binding

    repo = repo or main_repo()
    raw_roles = get_roles_raw(repo)
    value: Any = raw_roles.get(role, DEFAULT_ROLES.get(role))
    if not isinstance(value, dict):
        return None
    fp = value.get("fallback_provider")
    if not isinstance(fp, str) or not fp:
        return None
    adapter = _first_candidate(value)
    if adapter is None:
        return None
    providers = get_providers(repo)
    provider_cfg = providers.get(fp)
    if not isinstance(provider_cfg, dict):
        return None
    provider_cfg = dict(provider_cfg)
    provider_cfg["_name"] = fp
    try:
        return build_binding(adapter=adapter, provider_cfg=provider_cfg)
    except ProviderConfigError:
        return None
```

- [ ] **Step 4: 运行验证通过**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_resolve_fallback_binding.py -q`
Expected: PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
git add src/agentic_loop/resolve_paths.py tests/test_resolve_fallback_binding.py
git commit -m "feat(kqff): resolve_role_fallback_binding 读可选 fallback_provider（零回归）" -- \
  src/agentic_loop/resolve_paths.py tests/test_resolve_fallback_binding.py
```


> **派发与执行约定（编排者，在 B1 之前）**：A5 冻结后，编排者从集成分支切 WP feature 分支
> `feature/kqff-wp01-quota-fallback` + 独立 worktree（`/Users/admin/vibe/.worktrees/kqff-wp01`），
> 跑 `agentic preflight`（含 dispatch-lint），probe kimi（`PROBE_OK` 才派），**全脱离**派发
> （Python `Popen(..., start_new_session=True, stdin=DEVNULL)`，env 剥离 `AGENTIC_PYTHON`，避免 tty-stop）。
> kimi 在该 worktree 内执行 B1–B6；编排者 `agentic health` 监控至 DONE 后独立复核（Phase C）。
> 若派发时 kimi 原生套餐已耗尽，本 WP 自身尚未合入回退能力，故按 DESIGN §10.1 用
> `deepseek-v4-flash` 的手动 `--config-file` 派发（用户已授权 flash 优先）。

### Task B4: `redispatch._dispatch_with_quota_fallback`（回退编排）

**Files:**
- Modify: `src/agentic_loop/redispatch.py`（新增函数 + 顶部 import）
- Test: `tests/test_redispatch_quota_fallback.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_redispatch_quota_fallback.py
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
```

- [ ] **Step 2: 运行验证失败**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_redispatch_quota_fallback.py -q`
Expected: FAIL — `ImportError: cannot import name '_dispatch_with_quota_fallback'`。

- [ ] **Step 3: 加顶部 import**

在 `src/agentic_loop/redispatch.py` 既有 import 区加入：
```python
from agentic_loop.quota_fallback import is_quota_error, load_quota_patterns
```
并把既有 `from agentic_loop.resolve_paths import (...)` 扩为含 `resolve_role_fallback_binding`：
```python
from agentic_loop.resolve_paths import get_roles
from agentic_loop.resolve_paths import iterations_dir
from agentic_loop.resolve_paths import main_repo
from agentic_loop.resolve_paths import resolve_role_binding
from agentic_loop.resolve_paths import resolve_role_fallback_binding
```

- [ ] **Step 4: 写实现（紧跟既有 `_dispatch` 之后）**

```python
# 追加到 src/agentic_loop/redispatch.py（_dispatch 之后）
def _dispatch_with_quota_fallback(
    adapter: Adapter,
    worktree: Path,
    brief: str,
    prompt: str,
    dry_run: bool,
    *,
    fallback_binding: ProviderBinding | None = None,
    fallback_factory=None,
    quota_patterns=None,
) -> tuple[ImplementResult, str | None]:
    """派发；若失败且命中额度模式，用 fallback binding 重派一次（单跳）。

    返回 ``(最终 result, 实际生效的 fallback provider 名 or None)``。
    - 成功 / dry_run / 非额度失败 / 未配回退 → 不触发回退（provider=None）。
    - 额度失败且配了回退 → 构造 flash adapter 重派一次；flash 也额度失败则单跳到底
      （原样返回失败 result，由 main() 打 REDISPATCH_STOP），绝不三跳/无限重试。
    本函数不写 status、不动锁、不计 redispatch_count（计数仍由 main() 在成功后 +1）。
    """
    result = _dispatch(adapter, worktree, brief, prompt, dry_run)
    if dry_run or result.dispatched:
        return result, None
    if not is_quota_error(result.output, quota_patterns):
        return result, None
    if fallback_binding is None:
        _log("quota detected but no fallback_provider configured; not retrying")
        return result, None
    if fallback_factory is None:
        def fallback_factory(b):  # noqa: E306
            return KimiAdapter(kimi_bin=os.environ.get("KIMI_BIN", "kimi"), binding=b)
    fb_adapter = fallback_factory(fallback_binding)
    _log(f"quota detected on primary dispatch; retrying with fallback "
         f"provider={fallback_binding.provider}")
    fb_result = _dispatch(fb_adapter, worktree, brief, prompt, dry_run)
    if not fb_result.dispatched and is_quota_error(fb_result.output, quota_patterns):
        _log(f"fallback provider={fallback_binding.provider} ALSO hit quota; "
             f"single-hop exhausted -> STOP (hand to human)")
    return fb_result, fallback_binding.provider
```

- [ ] **Step 5: 运行验证通过**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_redispatch_quota_fallback.py -q`
Expected: PASS（6 passed）。

- [ ] **Step 6: 提交**

```bash
git add src/agentic_loop/redispatch.py tests/test_redispatch_quota_fallback.py
git commit -m "feat(kqff): _dispatch_with_quota_fallback 额度失败单跳回退 flash" -- \
  src/agentic_loop/redispatch.py tests/test_redispatch_quota_fallback.py
```

### Task B5: 接入 `main()` 派发点 + 项目 config

**Files:**
- Modify: `src/agentic_loop/redispatch.py`（`main()` 派发点）
- Modify: `.agentic/config.toml`
- Test: `tests/test_redispatch_quota_fallback.py`（追加 config/wiring 断言）

- [ ] **Step 1: 改 `.agentic/config.toml`（追加 provider；developer 改 dict 形态）**

把 `[roles]` 段的：
```toml
developer    = "kimi"
```
改为：
```toml
developer    = { adapter = "kimi", fallback_provider = "deepseekflash" }
```
并在 `[providers.kirogpt]` 段之后追加：
```toml
# kimi 套餐额度不足时的自动回退目标（仅 developer 派发用；主档仍是原生 kimi）。
# 单跳：kimi 原生 → deepseek-v4-flash；flash 也额度失败则 REDISPATCH_STOP 交人工。
[providers.deepseekflash]
anthropic_base_url = "https://api.deepseek.com/anthropic"   # kimi 走 anthropic 兼容端
api_key_env        = "DEEPSEEK_API_KEY"                      # 只存 env 名，绝不落盘明文
identity_model     = "deepseek-v4-flash"                     # DESIGN §10.1：实现前须核实精确 id
[providers.deepseekflash.selectors]
kimi = "deepseek/v4-flash"                                   # DESIGN §10.1：实现前须核实精确 selector
```
> 注意：`developer` 由裸 string 改 dict 后，`resolve_role_binding("developer")` 仍返回
> `("kimi", None)`（无 `provider` 键 → 主档零注入，原生 kimi 不变）；只有新增的
> `resolve_role_fallback_binding` 会读 `fallback_provider`。**主派发路径与评级语义零回归**。

- [ ] **Step 2: 改 `main()` 派发点**

把 `src/agentic_loop/redispatch.py` `main()` 中的：
```python
    result = _dispatch(adapter, worktree, brief, prompt_text, dry_run)
```
替换为：
```python
    fallback_binding = resolve_role_fallback_binding("developer")
    result, used_fallback = _dispatch_with_quota_fallback(
        adapter, worktree, brief, prompt_text, dry_run,
        fallback_binding=fallback_binding,
        quota_patterns=load_quota_patterns(repo_root),
    )
    if used_fallback:
        print(f"REDISPATCH_QUOTA_FALLBACK: provider={used_fallback}", file=sys.stderr)
```
（`repo_root` 已在 `main()` 开头由 `main_repo()` 解析；其余计数/日志逻辑不变。）

- [ ] **Step 3: 追加 config/wiring 断言测试**

```python
# 追加到 tests/test_redispatch_quota_fallback.py
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
```

- [ ] **Step 4: 运行验证通过**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests/test_redispatch_quota_fallback.py -q`
Expected: PASS（8 passed）。

- [ ] **Step 5: 提交**

```bash
git add src/agentic_loop/redispatch.py .agentic/config.toml tests/test_redispatch_quota_fallback.py
git commit -m "feat(kqff): redispatch.main 接入额度回退 + 项目配置 deepseekflash fallback" -- \
  src/agentic_loop/redispatch.py .agentic/config.toml tests/test_redispatch_quota_fallback.py
```

### Task B6: 全量回归 + 范围守卫

- [ ] **Step 1: 全量测试**

Run: `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests -q`
Expected: 仅 4 个**预存** `test_finalize_merge_triple_sign.py` 失败（根因：main 被 sibling worktree `agentic-loop-main-codex-merge` 占用，`git checkout -q main` 非零）；其余全绿，新增 ~19 个用例通过。任何**新增**失败都视为回归，必须修复。

- [ ] **Step 2: 范围守卫（确认未越界）**

Run:
```bash
git -C /Users/admin/vibe/.worktrees/kqff-wp01 diff --stat main...HEAD
git -C /Users/admin/vibe/.worktrees/kqff-wp01 diff main...HEAD -- \
  src/agentic_loop/independence.py src/agentic_loop/gate/ src/agentic_loop/adapters/kimi.py uv.lock
```
Expected: 第一条只列出 6 个允许文件（quota_fallback.py / resolve_paths.py / redispatch.py / config.toml / 3 测试）；第二条**空输出**（independence/gate/kimi.py/uv.lock 零改动 → #38 边界与信任根评级未触）。

- [ ] **Step 3: 质量门**

Run: `cd /Users/admin/vibe/.worktrees/kqff-wp01 && bash src/agentic_loop/wrappers/quality-gate.sh docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`（或 `agentic quality-gate <status>`）
Expected: 命中 `src/agentic_loop/**` 规则 → 跑全量 pytest；结果与 Step 1 一致（仅 4 预存失败）。

- [ ] **Step 4: 提交（如 quality-gate 产物需入库则显式路径；否则跳过）**

无新增源码改动则不提交；status 的工作树累积**不单独提交**（§4.3：freeze 与 finalize 之间只累积）。

---

## Phase C — 评审 / gate / 合并 / 收敛（编排者执行）

### Task C1: 独立复核 + review（不轻信 kimi 报告）

- [ ] 读 kimi handoff；`git show <commit> --stat` 核对改动面 == 6 允许文件。
- [ ] **亲自重跑**：focused（3 新测试文件）+ 全量（仅 4 预存失败）+ 范围守卫（B6 Step 2）。
- [ ] **revert-probe**：临时还原 `_dispatch_with_quota_fallback` 的额度判定（令其恒不回退）→ 断言 `test_quota_failure_retries_with_flash_success` 等转红，证明新用例承重；probe 后 worktree 须 clean。
- [ ] 验证零回归断言：`resolve_role_binding("developer")` 主 binding 仍 None（评级语义未变）。
- [ ] 记录 `review.decision=ACCEPT` + attestation（fresh_session/adversarial_prompt）；刷 WP 锁 heartbeat。

### Task C2: 双签门 `agentic gate`（consult 第二签名）

- [ ] Run（主仓，env `CLAUDE_CODE_SESSION_ID=<session>` + `AGENTIC_PYTHON=python3.11`）：
  `agentic gate docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json </dev/null`
- [ ] gate effort 按 phase tier（建议 medium：非信任根、加性引擎改动）。
- [ ] Expected: `GATE_DECISION=ACCEPT` → 置 `APPROVED_FOR_MERGE`；若 REWORK → 独立复现 finding，成立则记录 CHANGES_REQUESTED 并按 circuit-breaker 规则处理（不自主无限重派）。

### Task C3: 合并 WP → 集成分支 → finalize

- [ ] 人工批准后 `git merge --no-ff feature/kqff-wp01-quota-fallback` 进集成分支（`agentic merge` 走 autonomy `local_merge_no_ff`）。
- [ ] `agentic finalize <WP-01.status.json>` 盖 `state=MERGED` + `merged_commit`（仅写 status，不动 git；双签 ACCEPT 才放行；释放 WP 锁）。
- [ ] finalize 提交（status 第二次也是最后一次提交，折叠全部签名）。

### Task C4: plan 收敛（单 WP → 单一合并到 main）

- [ ] `agentic plan check PLAN-01.status.json`（所有声明 WP=MERGED；集成分支是否已并入 target）。
- [ ] `agentic plan lint PLAN-01.status.json`（commit discipline：每 WP status 恰好 freeze+finalize 两次提交，无中间 sync 提交）。
- [ ] 置 plan `READY_TO_MERGE` → `agentic plan merge PLAN-01.status.json`（唯一 `git merge --no-ff` 集成分支→main，autonomy `local_merge_no_ff`，fail-closed）。
- [ ] `agentic plan finalize PLAN-01.status.json`（盖 `state=MERGED` + `git.merged_commit`，幂等）。
- [ ] **push 保留人工批准**（`push` 是 always_stop，无 `agentic plan push`）。

---

## Self-Review（写计划后自检，对照 DESIGN.md）

**1. Spec 覆盖**：
- DESIGN §4.1 quota_fallback（is_quota_error/load_quota_patterns）→ B1/B2 ✓
- DESIGN §4.2 resolve_role_fallback_binding → B3 ✓
- DESIGN §4.3 + §5 数据流（派发失败后单跳回退）→ B4/B5 ✓
- DESIGN §6 安全（正向命中、单跳、脱敏、评级不变、probe 门不变）→ B4 负例 + B5 主档零回归断言 + B6 范围守卫 ✓
- DESIGN §7 config → B5 Step 1 ✓
- DESIGN §8 测试计划 → B1-B6 全覆盖（含零回归负例、单跳 STOP、计数不双计由 main() 逻辑保证 + C1 复核）✓
- DESIGN §9 交付路径（新 iteration/plan/WP、独立 worktree、冻结→派发→评审→gate→merge→收敛、push always_stop）→ Phase A/C ✓
- DESIGN §10 待确认（flash 精确 id/selector、额度原文锚定、是否强制 consult）→ A4 consult + B5 config 注释标注「实现前核实」✓
- DESIGN §11 范围外 → 计划未引入多档链/probe 预切/持久改写/泛化到 claude-codex/改 init 模板 ✓

**2. 占位符扫描**：无 TBD/TODO；每个代码步骤含完整代码；每个命令含预期输出。Phase A3/C 的治理步骤引用 AGENTS.md 既有流程与模板（非占位，是既定过程）。

**3. 类型/命名一致性**：`is_quota_error(output, patterns=None)`、`load_quota_patterns(repo=None)`、`resolve_role_fallback_binding(role, repo=None)`、`_dispatch_with_quota_fallback(adapter, worktree, brief, prompt, dry_run, *, fallback_binding=None, fallback_factory=None, quota_patterns=None) -> (ImplementResult, str|None)` 在 B1-B5 定义与调用处签名一致；`ProviderBinding`/`ImplementResult`/`build_binding`/`_first_candidate`/`get_roles_raw`/`get_providers`/`_load_config`/`main_repo` 均为既有符号，已核实存在。

**已知测试边界（诚实标注）**：`redispatch.main()` 无既有单测harness（本仓无 test_redispatch.py），故 main() 的 3 行接线 glue 由 B4 wrapper 单测 + B5 config 解析断言 + C1 独立复核 + 全量回归共同覆盖，不为 main() 单独 stub git/validator/lock 子进程（与本仓现有测试深度一致）。

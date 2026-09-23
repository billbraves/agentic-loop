# WP-01 C1' 独立复核（rework / impl rev2）— review.decision = ACCEPT

- **复核者**：claude-code（orchestrator，session=kqff-b，lock owner claude-kqff-b）
- **对象**：kqff WP-01 rev7 rework（impl rev2），base `42e6d85` → HEAD `4035f06`
- **执行者**：kimi（developer，rework session `6f806b78-4269-42d2-9635-bdd2a0c7b368`，2026-09-22 退出，[STATUS] DONE / [CONCERNS] 无）
- **冻结基线**：brief rev7（sha256 `a5b72c39…`，codex rev7 复签 ACCEPT）
- **独立性**：reviewer=orchestrator，独立性由 codex consult 第二签名承载（weak-attested，WP-17 先例），与 rev1 同。

## 复核方法（verification-before-completion：全部自跑，未只信 kimi 报告）

1. **真实 diff** `git diff --stat 42e6d85...HEAD` = **恰好 5 文件 +99/-5**（`quota_fallback.py` +13/-2、`resolve_paths.py` +15/-3、`test_quota_fallback.py` +20、`test_redispatch_quota_fallback.py` +18、`test_resolve_fallback_binding.py` +33）；**无** `redispatch.py`/`config.toml`（§R 明确本轮不改）、**无** forbidden、**无** docs/plans/。
2. **逐条读 diff** 对齐 rev7 §R spec（见下）。
3. **focused 复跑**：`test_quota_fallback.py`+`test_resolve_fallback_binding.py`+`test_redispatch_quota_fallback.py` = **30 passed**；collect-only 计数 **12/7/11** 精确匹配 §R4。
4. **全量复跑**：`pytest tests -q` = **803 passed / 4 failed / 4 skipped（177.88s）**；4 失败**全部**预存 `test_finalize_merge_triple_sign.py`（根因 `git checkout -q main` 非零退出 = main 被 sibling worktree 占用的环境基线，非本 WP），**零新增失败**；803 = 799(rev1)+4(rework 新测试)。
5. **C1' probe**（`.kqff-wp01-c1prime-probe.py`，临时 repo，只读）：见下「不变式实证」。
6. **git 纪律**：一次 feat 提交 `4035f06`（message `rework(r1): close codex impl-rev1 REWORK #1/#8 + brief #4/#5 erratum`，显式路径）；编排者制品（`M WP-01-brief.md`/`M WP-01.status.json` + 8 个 `?? WP-01-*.md`）**仍未提交、未被 kimi 触碰**（§4.3 守住）。

## rev7 §R 逐条核验

- **§R1（finding #1，实现阻断）— 闭环 ✅** `resolve_paths.py` 的 `build_binding(...)` 调用点 `except ProviderConfigError` → **`except Exception as exc`**（**窄作用域**：try 块仅包 `build_binding`；`get_roles_raw(repo)`（L401）仍在 try **外**未动 → 畸形 TOML 按设计仍逃逸，属范围外、与 primary 共享的既有失败）；回落 None 前打**一行脱敏诊断**（固定文案 + `type(exc).__name__`）；docstring 精确收窄为「never raises for provider-config shape errors; a malformed config FILE is a pre-existing failure shared with resolve_role_binding … out of scope」；删除不再使用的 `ProviderConfigError` import（干净）。新增 2 承重测试 `test_none_when_selectors_is_{string,list}_no_raise`。**未加畸形 TOML 用例**（NARROW 范围外，符合 rev7）。
- **§R2a（rev7 已删除）— 确未实现 ✅** `git grep -nE '_MAX_SCAN_CHARS|tail.?window|65536'` 于 `quota_fallback.py` = **空**；`is_quota_error` 全文 `re.search` 未改；仅模块 docstring 加 operator-trusted 信任边界注记（无行为变更、无检测回归）。
- **§R2b（finding #8 硬化）— 闭环 ✅** `load_quota_patterns` 的 `except Exception: pass` → `except Exception as exc: print("load_quota_patterns: quota_fallback config unreadable ({type(exc).__name__}); falling back to built-in defaults", file=sys.stderr)`；新增 `test_load_patterns_emits_redacted_diagnostic_on_fault`（capsys + 哨兵 `SECRET_SENTINEL_DO_NOT_LEAK` 不在 stderr + 恰一行 + 固定前缀 + 路径不泄）。
- **§R3（findings #4/#5 台账勘误）— 承重 ✅** #4/#5 台账更正已在 brief rev7 完成（kimi 未改 brief，正确）；新增 `test_success_with_quota_like_output_no_fallback`（primary dispatched=True + output 含额度词 → 短路优先、`built==[]`、`prov is None`）。

## 不变式实证（C1' probe，OVERALL PASS）

- **INV-3（#1 闭环）**：`selectors="SECRET_SENTINEL_DO_NOT_LEAK"`（字符串）→ `resolve_role_fallback_binding("developer")` = **None，raised=None**（`build_binding` 内 `selectors.get` 的 AttributeError 被 except Exception 吞、回落 None，**不抛进派发主链**）。
- **INV-4（primary 未削弱）**：同一 config 下 `resolve_role_binding("developer")` = **`('kimi', None)`** 不变（NARROW 未触碰 primary，主档零回归）。
- **§R1 脱敏**：stderr 诊断 = `resolve_role_fallback_binding: provider config invalid (AttributeError); falling back to no quota fallback` → 哨兵 **absent**、固定前缀 **PASS**（config 原文/路径/密钥不泄）。
- **§R3 承前提实证**：`is_quota_error("build ok; note: weekly quota reset scheduled")` = **True** → 删短路则 success 腿误触发回退 → 本用例转红 = **真承重**（非伪 witness）。
- **NameError 排雷**：`resolve_paths.py:16 import sys` 存在 → except 块 `print(file=sys.stderr)` 不会自身 NameError 击穿 fail-safe。

## 非阻断 nit（记录，不拦 ACCEPT）

- `test_load_patterns_emits_redacted_diagnostic_on_fault` 末行断言 `"api_key" not in err.lower() or "api_key_env" not in err` 是弱 **OR**（任一不含即过）；但同用例的哨兵串 + config 路径 + 恰一行 + 固定前缀断言已充分覆盖脱敏，诊断串本身亦不含任何密钥字段，故**非阻断**。可在 C2'/未来收紧为 AND，不影响本轮裁定。

## 裁定

**review.decision = ACCEPT**（findings=[]）。rev7 rework 正确闭环 codex impl-rev1 的 #1（实现阻断）+ #8（硬化）+ #4/#5（§R3 承重），零回归（全量仅 4 预存失败）、范围守卫干净（5 allowed 文件）、git 纪律守住。**双签待 C2'（codex impl 复签）**：当前 review=ACCEPT(rev2) / consult=REWORK(rev1，stale，pending C2') → double_sign NOT_SATISFIED。C2' ACCEPT 后凑齐双签，停在 C2 gate 前汇报（standing 用户边界）。

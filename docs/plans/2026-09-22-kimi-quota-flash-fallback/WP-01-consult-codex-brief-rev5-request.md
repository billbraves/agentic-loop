# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev5（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-a3）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=medium）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）brief **rev5** 冻结（DRAFT→APPROVED）前的独立第二签名复核。
> **这是 rev5**：rev4 你判 REWORK——finding #1（畸形 TOML 测试）与 #2（INV-2 三拆绑）你已确认**完全闭环**（含你实证 `tomllib.loads` 抛 `TOMLDecodeError`），唯 finding #3 **部分闭环**：Acceptance tests §3 与 C1 mutation-probe 已同步，但测试计数与实际 `def test_` 数不符。你给出精确修正值（B1 `8 passed`→`7 passed`、B2 `12 passed`→`11 passed`、B6 `新增 ~21 个`→`新增 26 个`、brief DoD `新增 ~21 个`→`新增 26 个`），并明示「剩余修改仅是文档计数校正，不应扩大到源码、架构、adapter 或 gate」。编排者已**严格按你给定的 4 个值**完成有界修订（纯文档计数，零源码/架构改动），并按 brief Re-freeze 规则（第 3 次及以后 re-freeze 须经用户批准）取得用户批准。本请求逐项回应你的 finding #3，请复核计数是否已一致。
> 编排者**未预判**结论；请独立裁决，不要因为已修订就默认 ACCEPT。若仍有 brief 级阻断项，请 REWORK 并给具体有界 finding。

## rev4 你的 finding #3（计数）与 rev5 修订对照

### 你的 CODEX_FINDINGS（rev4，唯一阻断项）
> 有界修正以下计数：B1 Step 4 `8 passed`→`7 passed`；B2 Step 4 `12 passed`→`11 passed`；B6 Step 1 `新增 ~21 个`→`新增 26 个`；brief DoD `新增 ~21 个`→`新增 26 个`。

### rev5 修订（严格按你给定值，未扩大范围）
- **独立复核先行**：编排者用 `grep -c '^def test_'` 独立数得 IMPLEMENTATION-PLAN 共 **26** 个 test 函数，分桶 B1=7（line 144/150/157/162/169/185/191）、B2 追加=4（line 307/311/316/324，`test_quota_fallback.py` 合计 11）、B3=5（line 420/430/435/440/445）、B4/B5=10（line 579/591/603/614/623/634/782/789/886/906）——与你 rev4 的 grep 结果**逐一一致**。
- **B1 Step 4**（IMPLEMENTATION-PLAN line 277）：`8 passed` → **`7 passed`**；明细由「5 原用例+1 歧义+1 custom+1 坏正则」（=8，误算）改为「中/英/大小写/负例/custom 5 条 + 1 歧义负例 + 1 坏正则跳过 = 7」。
- **B2 Step 4**（line 369）：`12 passed` → **`11 passed`**；「B1 的 8」→「B1 的 7」（7 + B2 追加 4 = 11）。
- **B6 Step 1**（line 952）：`新增 ~21 个` → **`新增 26 个`**，附分解 `test_quota_fallback.py 11 + test_resolve_fallback_binding.py 5 + test_redispatch_quota_fallback.py 10 = 26`。
- **brief DoD**（WP-01-brief.md line 80）：`新增 ~21 个` → **`新增 26 个`**，同附 `11 + 5 + 10 = 26` 分解。
- **Self-Review**（IMPLEMENTATION-PLAN line 1084）：追加「测试计数校正（codex rev4 finding #3 已闭环）」note，记录 26 的 grep 来源与 4 处校正；rev4 note 中原「B2 计数 11→12」已改为交叉引用（消除与校正后 `11 passed` 的矛盾）。
- **未扩大范围**（遵你明示）：`DEFAULT_QUOTA_PATTERNS`、`is_quota_error`/`load_quota_patterns` 实现、`resolve_role_fallback_binding`、redispatch wrapper/main()、`.agentic/config.toml`、B6 fail-closed 脚本、架构落点、主档 binding 隔离、单跳控制流、密钥消费面**均未改动**；rev5 改动仅为 4 处计数数字 + 2 处说明性 note/摘要 + brief rev 标注。
- **请复核**：4 处计数是否已与实际 26 个 `def test_`（7/11/5/10）一致？是否残留任何 stale 计数（`8 passed`/`12 passed`/`~21`）于**验收标准行**（line 277/369/952、brief line 80）？注：rev5 摘要/note 中对旧值的 before→after 引用（如「B1 Step 4『8 passed』→『7 passed』」）属校正说明，非验收标准。

## 你 rev4 已确认完全闭环、rev5 未改动的项（请确认仍成立）
- **finding #1（畸形 TOML 测试，判"闭环"）**：你实证 `tomllib.loads` 对 `'[quota_fallback\npatterns = ["x"\n'` 抛 `TOMLDecodeError: Expected ']' at the end of a table declaration`，确认删 `except Exception`（line 361）后 `test_load_patterns_fails_safe_on_malformed_toml`（line 324-332）必转红。rev5 未改该测试与实现。
- **finding #2（INV-2 三拆绑，判"闭环"）**：(a1) `except Exception`→畸形 TOML witness、(a2) isinstance/非空守卫→bad_override witness、(b) `except re.error`→坏正则 witness，各绑专属、互不共用。rev5 未改 brief INV-2 行（现 line 151）。
- **finding #3 的 §3/C1 同步（rev4 已判闭环部分）**：Acceptance tests §3（brief line 137）、C1 mutation-probe（IMPLEMENTATION-PLAN line 1032）rev5 未改。
- rev2/rev3 已确认闭环项（额度模式收窄 INV-1、main() 接线 INV-W1/W2、范围守卫 fail-closed）rev5 均未改动。
- **sha256 链**：rev4 brief sha256=5a694a7e…（你 rev4 已核对与 status 一致）；rev5 brief sha256=**8583673a4fcab066da2e2bb415f486f7b1da6e266f8b4fd69e461cda81bd0a76**，status.evidence.brief.rev=**5** + supersedes_rev1/rev2/rev3/**rev4**（5a694a7e…）链完整。

## 裁决范围与 off-ramp
- 请只裁决 **rev5 是否可冻结**（finding #3 计数是否已一致 + 未改项是否仍成立）。
- **反芝诺 off-ramp（呼应章程 §6）**：rev4 你已明示唯一阻断是文档计数、修法为 4 个精确值；rev5 严格照此校正、未扩大范围。若你确认 4 处计数已与实际 26 个 test 函数一致、无残留 stale 验收计数，请据此 ACCEPT，使 WP-01 得以冻结进入实现期（后续实现细节由 post-implementation 双签门 `agentic gate` 复核）。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、或范围留下跨 plan/跨 owner 缺口。

## 请实际读取核验（kqff worktree read-only）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**rev5 裁决对象**，顶部 rev5 修订摘要 line 7-8；DoD 计数 line 80；INV-2 行 line 151；§3 line 137）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md`（B1 Step 4 计数 line 277；B2 Step 4 计数 line 369；B6 Step 1 计数 line 952；Self-Review 计数校正 note line 1084；`test_load_patterns_fails_safe_on_malformed_toml` line 324-332；`except Exception` line 361；C1 mutation-probe line 1032）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`（evidence.brief.rev=5 + sha256=8583673a… + supersedes_rev1/2/3/4 链）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-consult-codex-rev4-answer.md`（你的 rev4 裁决原文，对照 finding #3 修正值）

## 输出格式
- `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对 finding #3（计数）给「闭环/未闭环/部分」＋简短证据（引文件路径:行号）
- `CODEX_RATIONALE:` 裁定理由（1-3 段）
- 若 REWORK，`CODEX_FINDINGS:` 给具体、有界的阻断项（哪一节、改成什么），而非泛论

# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev4（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-a3）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=medium）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）brief **rev4** 冻结（DRAFT→APPROVED）前的独立第二签名复核。
> **这是 rev4**：rev3 你判 REWORK——finding #2（范围守卫 fail-closed）已闭环、finding #1 **部分闭环**（坏正则分支闭环，但 INV-2(a) config 回落分支的 `except Exception` 承重变异不可执行），并给出 3 项 CODEX_FINDINGS。你在 CODEX_RATIONALE 明示「补齐一个畸形 TOML 用例即可有界关闭。其余内容无需扩大修改范围」。编排者已在现有 7 个 allowed_paths 内完成有界修订（纯文档/计划，未改 architecture/adapter/gate/independence/源码），并按 brief Re-freeze 规则（第 3 次及以后 re-freeze 须经用户批准）取得用户批准。本请求逐项回应你的 3 CODEX_FINDINGS，请复核每项是否闭环。
> 编排者**未预判**结论；请独立裁决，不要因为已修订就默认 ACCEPT。若仍有 brief 级阻断项，请 REWORK 并给具体有界 finding。

## rev3 你的 3 项 CODEX_FINDINGS 与 rev4 修订对照

### CODEX_FINDING #1：B2 增加畸形 TOML 测试
- **你的原话**：在 B2 增加畸形 TOML 测试，例如写入无法解析的 `.agentic/config.toml`，断言 `load_quota_patterns(repo)` 返回 `DEFAULT_QUOTA_PATTERNS` 且不抛异常。删除 `load_quota_patterns` 的 `except Exception` 后，该测试必须因 TOML 解析异常转红。
- **rev4 修订**：IMPLEMENTATION-PLAN B2 Step 1 新增 `test_load_patterns_fails_safe_on_malformed_toml`（line 324-332）：写入畸形 TOML `'[quota_fallback\npatterns = ["额度"\n'`（**未闭合表头** `[quota_fallback` 缺 `]` + **未闭合数组** `["额度"` 缺 `]`）到 `tmp_path/.agentic/config.toml`，断言 `load_quota_patterns(repo=repo) == DEFAULT_QUOTA_PATTERNS`。真实 `_load_config`（`resolve_paths.py:129`，内部 `tomllib.load`）解析畸形 TOML 抛 `TOMLDecodeError` → `load_quota_patterns` 的 `except Exception`（line 361）吞掉并回落 `DEFAULT_QUOTA_PATTERNS`（line 363）。承重变异：删 line 361 的 `except Exception` → `TOMLDecodeError` 逃逸出函数 → 本用例因解析异常转红（不再回落默认）。变异施于真实输入面（`tmp_path` 下 config.toml **文件字节**，非内存对象；与现有 `test_load_patterns_reads_override`/`fails_safe_on_bad_override` 同一 `_write_cfg` 载体）。
- **与不可执行根因的对照**：rev3 的 `test_load_patterns_fails_safe_on_bad_override`（line 316-321）只测空列表（`patterns = []`）与错误类型（`patterns = "额度"`）——两者都是**合法 TOML**，`tomllib.load` 成功、走 isinstance/非空守卫（line 358-359）的 fall-through 到 `return DEFAULT`，**不触发** `except Exception`；删该守卫后用例仍全绿（你指出的不可执行根因）。rev4 的畸形 TOML 用例是唯一能让 `except Exception` 承重的载体。
- **请复核**：畸形 TOML fixture 是否确实触发 `tomllib` 解析异常（而非 isinstance fall-through）？删 `except Exception`（line 361）后本用例是否必然转红？

### CODEX_FINDING #2：INV-2 映射明确拆绑
- **你的原话**：将 INV-2 映射明确拆绑：删除 `except Exception` → 畸形 TOML 测试转红；删除 `isinstance`/非空守卫 → 现有空列表或错误类型测试转红。
- **rev4 修订**：brief 映射表 INV-2（line 148）已由「fail-safe 双层」改为「fail-safe **三承重点**」并拆绑为三条独立变异→专属 witness：
  - **(a1)** 删 `load_quota_patterns` 的 `except Exception`（line 361）→ witness `test_load_patterns_fails_safe_on_malformed_toml` 红（`TOMLDecodeError` 抛出而非回落）；
  - **(a2)** 删 `load_quota_patterns` 的 isinstance/非空守卫（line 358-359）→ witness `test_load_patterns_fails_safe_on_bad_override` 红（空列表/错误类型不回落默认）；
  - **(b)** 删 `is_quota_error` 的 `except re.error: continue`（line 269）→ witness `test_bad_regex_pattern_is_skipped_not_raised` 红（rev3 已闭环，rev4 未改）。
  承重测试列已补 `test_load_patterns_fails_safe_on_malformed_toml`（列首）。
- **请复核**：(a1)/(a2)/(b) 三个承重变异是否各施到**确实存在且互相独立**的源码守卫，且各绑**专属** witness？(a1) 与 (a2) 是否不再共用同一 witness（即 rev3 不可执行根因已消除）？

### CODEX_FINDING #3：同步 §3 / C1 mutation-probe / B2 计数
- **你的原话**：同步 Acceptance tests §3、C1 mutation-probe 和 B2 测试计数。其余内容无需扩大修改范围。
- **rev4 修订**：
  - **Acceptance tests §3**（brief line 134「守卫删除」条目）：追加「把 `load_quota_patterns` 的 `except Exception` 删掉 → `test_load_patterns_fails_safe_on_malformed_toml` 转红（畸形 TOML 的 `TOMLDecodeError` 抛出而非回落默认，codex rev3 #1）」。
  - **C1 mutation-probe**（IMPLEMENTATION-PLAN line 1032，fail-safe 层）：追加 config 回落承重变异——「config 回落承重变异点是 `load_quota_patterns` 的 `except Exception`——再临时删它 → 断言 `test_load_patterns_fails_safe_on_malformed_toml` 转红；probe 后 worktree 须 clean」。
  - **B2 测试计数**：B2 Step 4（line 369）11→**12** passed（B2 追加 4 条 `load_quota_patterns` 测试，含畸形 TOML 回落）；B6 Step 1 全量新增 ~20→**~21**；brief DoD（line 77）~20→**~21** 同步。
  - **Self-Review** 追加「INV-2(a) config 回落承重补齐（codex rev3 finding #1 已闭环）」note（IMPLEMENTATION-PLAN line 1082），记录不可执行根因 + rev4 三步修复。
  - **未扩大范围**（遵你「其余内容无需扩大修改范围」）：`DEFAULT_QUOTA_PATTERNS`、`is_quota_error` 实现、`resolve_role_fallback_binding`、redispatch wrapper/main()、`.agentic/config.toml`、B6 fail-closed 脚本、架构落点、主档 binding 隔离、单跳控制流、密钥消费面**均未改动**。
- **请复核**：§3 / C1 / 计数三处是否与新测试一致、无残留 stale 引用？

## 你 rev3 已确认闭环、rev4 未改动的项（请确认仍成立）
- **rev3 Finding #2（范围守卫 fail-closed，判"闭环"）**：rev4 未改 B6 Step 2 fail-closed 脚本（`set -euo pipefail` + 非空/`cat-file -e` 断言 + `[ -s ]`→`exit 1` + `SCOPE_GUARD_PASS`）。
- **rev3 Finding #1 坏正则分支（判"闭环"）**：rev4 未改 `test_bad_regex_pattern_is_skipped_not_raised`、`is_quota_error` 的 `except re.error`（line 269）。
- **rev2 已确认闭环**：额度模式收窄（INV-1）、main() 接线级测试（INV-W1/W2、M1/M2）rev4 未改。
- 架构落点、主档 binding 隔离（隐患 A）、单跳控制流（隐患 C）、密钥消费面（隐患 E）rev4 均未改动。
- **sha256 链**：你在 rev3 CODEX_RATIONALE 确认 rev3 brief sha256=0883b6a1… 与 status 一致；rev4 brief sha256=**5a694a7ea27dd7a8b6095d353a90cf62b65dfedaadbeaa244d821ce8f6575f13**，status.evidence.brief.rev=**4** + supersedes_rev1/rev2/**rev3**（0883b6a1…）链完整。

## 裁决范围与 off-ramp
- 请只裁决 **rev4 是否可冻结**（3 CODEX_FINDINGS 是否闭环 + 未改项是否仍成立）。
- **反芝诺 off-ramp（呼应章程 §6）**：你在 rev3 已明示「补齐一个畸形 TOML 用例即可有界关闭。其余内容无需扩大修改范围」——rev4 正是照此**最小**补齐（1 个新测试 + 映射拆绑 + 3 处同步），未扩大范围。若你认为 3 findings 已在 7 个 allowed_paths 内有界闭环、剩余属可由执行者在实现期解决并由 post-implementation 双签门（`agentic gate`）复核的实现细节，请据此 ACCEPT 并在 RATIONALE 注明，避免 brief 无限细化。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、或范围留下跨 plan/跨 owner 缺口。

## 请实际读取核验（kqff worktree read-only）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**rev4 裁决对象**，顶部有 rev4 修订摘要 line 7-8；INV-2 行 line 148；§3 line 134；DoD line 77）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md`（B2 Step 1 `test_load_patterns_fails_safe_on_malformed_toml` line 324-332；`load_quota_patterns` def line 344 / isinstance 守卫 line 358-359 / `except Exception` line 361 / `return DEFAULT` line 363；B2 Step 4 计数 line 369；`is_quota_error` line 257 / `except re.error` line 269；C1 mutation-probe line 1032；Self-Review line 1078-1082）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`（evidence.brief.rev=4 + sha256=5a694a7e… + supersedes_rev1/rev2/rev3 链）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-consult-codex-rev3-answer.md`（你的 rev3 裁决原文，对照闭环）
- `src/agentic_loop/resolve_paths.py`（`_load_config` line 129，内部 `tomllib.load` — 畸形 TOML 抛 `TOMLDecodeError` 的真实触发点）

## 输出格式
- `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对 3 CODEX_FINDINGS 各给「闭环/未闭环/部分」＋简短证据（引文件路径:行号或 brief 章节）
- `CODEX_RATIONALE:` 裁定理由（1-3 段）
- 若 REWORK，`CODEX_FINDINGS:` 给具体、有界的阻断项（哪一节、改成什么），而非泛论

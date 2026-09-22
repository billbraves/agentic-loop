# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev3（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-a3）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=medium）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）brief **rev3** 冻结（DRAFT→APPROVED）前的独立第二签名复核。
> **这是 rev3**：rev2 你判 REWORK，给出 2 项 brief 级 oracle 缺口（CODEX_FINDINGS #1=INV-2 oracle 不可执行、#2=范围守卫不 fail-closed），并已确认 rev2 的 finding #1（额度过宽）与 #2（计数接线）闭环。编排者已在现有 7 个 allowed_paths 内完成有界修订（纯文档/计划，未改 architecture/adapter/gate/independence/源码），并按你在 rev2 answer 末行的明确要求「进入 rev3 前需履行 brief 已声明的用户批准要求」取得了用户批准（brief Re-freeze 规则：第 3 次及以后 re-freeze 须经用户批准）。本请求逐项回应你的 2 findings，请复核每项是否闭环。
> 编排者**未预判**结论；请独立裁决，不要因为已修订就默认 ACCEPT。若仍有 brief 级阻断项，请 REWORK 并给具体有界 finding。

## rev2 你的 2 项 finding 与 rev3 修订对照

### Finding #1（rev2 判"部分闭环"）：INV-2 oracle 不可执行——承重变异指向不存在的源码
- **你的原话**：INV-2 映射声称"坏正则回落默认"并要求删除 `load_quota_patterns` 的坏正则 `try/except`（brief:141）；但实际 B2 的 `load_quota_patterns` 既不编译正则、也不存在该 `try/except`，测试只覆盖空列表和错误类型（IMPLEMENTATION-PLAN:301）；真正的 `re.error` 防线在 `is_quota_error`（line 242）。你的修法：拆分 malformed TOML/空列表/错误类型（`load_quota_patterns` 回落）vs 语法非法正则（`is_quota_error` 跳过不抛）；增加含坏正则的真实配置/模式测试（如 `["[", r"\bquota\b"]`）；承重变异改为删 `is_quota_error` 的 `except re.error`；同步 brief INV-2/B2 说明/C1 mutation-probe。
- **rev3 修订**：
  - IMPLEMENTATION-PLAN B1 Step 1 新增 `test_bad_regex_pattern_is_skipped_not_raised`（line 191-203）：`is_quota_error("quota exceeded", patterns=["[", r"\bquota\b"]) is True`（坏正则 `[` 跳过、合法 `\bquota\b` 仍命中）；`is_quota_error("unrelated output", patterns=["["]) is False`；`is_quota_error("insufficient balance", patterns=["(", r"balance\W{0,10}credit"]) is False`。变异施于 `is_quota_error` 的真实输入面（`patterns` 参数，即进程内函数边界；坏正则来自 config 覆盖的真实载体）。
  - 承重变异点更正为 `is_quota_error` 的 `except re.error: continue`（B1 Step 3 实现，`def is_quota_error` line 257、`except re.error` line 269）——删它则 `re.search("[", ...)` 抛 `re.error`，上述测试转红（error 而非返回 False）。**不再**指向 `load_quota_patterns`（B2 `def load_quota_patterns` line 333 只读 config、不编译正则，无该守卫；其 fail-safe 是 line 350 的 `except Exception`）。
  - brief 映射表 INV-2（line 145）已拆为两个真实输入面：(a) config 回落默认——承重变异删 `load_quota_patterns` 的 `try/except Exception`（line 350）或 isinstance/非空守卫，witness=`test_load_patterns_fails_safe_on_bad_override` 红（抛异常/不回落）；(b) 坏正则跳过——承重变异删 `is_quota_error` 的 `except re.error: continue`（line 269），witness=`test_bad_regex_pattern_is_skipped_not_raised` 红（`re.error` 抛出而非跳过）。
  - 同步项：brief 交付物清单（test_quota_fallback.py）、Acceptance tests §3「守卫删除」条目、C1 mutation-probe（fail-safe 层，line 1021）、Self-Review（line 1067）；B1 Step 4 计数 7→8、B2 Step 4 计数 10→11。
- **请复核**：`test_bad_regex_pattern_is_skipped_not_raised` 是否施于真实输入面、能否被"删 `is_quota_error` 的 `except re.error`"转红？INV-2 拆分后 (a)/(b) 两个承重变异是否都施到**确实存在**的源码守卫（`load_quota_patterns` 的 `except Exception` @line 350、`is_quota_error` 的 `except re.error` @line 269）？

### Finding #2（rev2 判"部分闭环"）：范围守卫不 fail-closed——comm 越界仍退出 0
- **你的原话**：`dispatch_commit` 基线和七项 allowed 已改对（IMPLEMENTATION-PLAN:930），但集合差只执行 `comm -23` 观察输出（line 941）；`comm` 即使发现越界仍退出 0；若 `dispatch_commit` 为空或 `git diff` 失败，管道还可能由 `sort` 返回成功生成空结果。你的修法：`set -euo pipefail`；断言 `dispatch_commit` 非空且 `git cat-file -e "$BASE^{commit}"` 成功；`git diff` 失败直接终止；`comm -23` 写入 unexpected 文件并用 `test ! -s` 或等价返回非零；失败前打印 unexpected 内容诊断。
- **rev3 修订**：IMPLEMENTATION-PLAN B6 Step 2（line 951-995）已改为机器化 fail-closed：
  - 首行 `set -euo pipefail`（line 951）；
  - `test -n "$BASE" || { echo "SCOPE_GUARD_FAIL: dispatch_commit 为空…"; exit 1; }`（line 956）；
  - `git -C "$WT" cat-file -e "${BASE}^{commit}" || { echo "SCOPE_GUARD_FAIL: …非有效 commit"; exit 1; }`（line 957）；
  - `git diff --name-only "${BASE}...HEAD" | sort -u > changed.txt`（git diff 失败在 pipefail+set -e 下直接终止，不静默产出空集）；
  - `comm -23 changed.txt allowed.txt > unexpected.txt`；`if [ -s unexpected.txt ]; then echo SCOPE_GUARD_FAIL; cat unexpected.txt; exit 1; fi`；
  - forbidden diff `> forbidden.diff`；`if [ -s forbidden.diff ]; then echo SCOPE_GUARD_FAIL; cat forbidden.diff; exit 1; fi`；
  - 全绿 `echo "SCOPE_GUARD_PASS"`（line 995，退出 0）。
  - brief rev3 DoD（line 75）、「Allowed and forbidden paths」范围守卫命令块（line 160-174，`SCOPE_GUARD_PASS` @174）与判据句（line 177）已同步 fail-closed 语义；Expected 改为 `SCOPE_GUARD_PASS`/`SCOPE_GUARD_FAIL` + 退出码判据；Self-Review 追加"范围守卫 fail-closed 已闭环"note（line 1069）。
- **请复核**：`set -euo pipefail` + `test -n` + `cat-file -e` + `[ -s unexpected ]`/`[ -s forbidden ]` + `exit 1` 是否构成机器化 fail-closed（越界 / 空基线 / git diff 失败都非零退出）？是否还残留"已跑但没证明"的假绿路径？

## 你 rev2 已确认闭环、rev3 未改动的项（请确认仍成立）
- **rev2 Finding #1（额度过宽，判"闭环"）**：rev3 未改 `DEFAULT_QUOTA_PATTERNS` 收窄正则、`test_ambiguous_phrases_are_not_quota_errors`、INV-1 映射。
- **rev2 Finding #2（计数接线，判"闭环"）**：rev3 未改 B5 Step 3 的 2 条 main() 接线级测试（INV-W1/W2）、M1/M2 mutation、C1 mutation-probe（main() 接线层）。
- 架构落点、主档 binding 隔离（隐患 A）、单跳控制流（隐患 C）、密钥消费面（隐患 E）rev3 均未改动。

## 裁决范围与 off-ramp
- 请只裁决 **rev3 是否可冻结**（2 findings 是否闭环 + 未改项是否仍成立）。
- **反芝诺 off-ramp（呼应章程 §6）**：若你认为 2 findings 已在 7 个 allowed_paths 内有界闭环，剩余问题属可由执行者在实现期解决、并由 post-implementation 双签门（`agentic gate`）复核的实现细节，请据此 ACCEPT 并在 RATIONALE 注明，避免 brief 无限细化。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、或范围留下跨 plan/跨 owner 缺口。

## 请实际读取核验（kqff worktree read-only）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**rev3 裁决对象**，顶部有 rev3 修订摘要；INV-2 行 line 145；DoD line 75；范围守卫命令块 line 160-174）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md`（B1 Step 1 `test_bad_regex_pattern_is_skipped_not_raised` line 191-203；`is_quota_error` line 257 / `except re.error` line 269；`load_quota_patterns` line 333 / `except Exception` line 350；B6 Step 2 fail-closed line 951-995；C1 mutation-probe line 1021；Self-Review line 1067-1069）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`（evidence.brief.rev=3 + sha256=0883b6a1… + supersedes_rev1/rev2 链）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-consult-codex-rev2-answer.md`（你的 rev2 裁决原文，对照闭环）
- `src/agentic_loop/resolve_paths.py`（`_load_config` 现状，供 `load_quota_patterns` 回落判据核验）

## 输出格式
- `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对 2 findings 各给「闭环/未闭环/部分」＋简短证据（引文件路径:行号或 brief 章节）
- `CODEX_RATIONALE:` 裁定理由（1-3 段）
- 若 REWORK，`CODEX_FINDINGS:` 给具体、有界的阻断项（哪一节、改成什么），而非泛论

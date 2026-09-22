CODEX_DECISION: REWORK

1. Finding #1：闭环  
   默认模式已从裸歧义词收窄为语境化组合，`429`/`402` 也要求限流或付费上下文，见 [DESIGN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md:64)。你点名的四类误判及扩展边界均有 False 断言，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:169)。INV-1 同时覆盖漏报与过宽误报变异，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:140)。结合 wrapper 的 `built == []` 非额度测试和构造仅位于 `is_quota_error` 真分支之后，足以组合证明 `fallback_factory` 不会被歧义负例触发。

2. Finding #2：闭环  
   wiring fixture 保留了真实 `main()` 的 circuit-breaker、wrapper 调用和成功后计数逻辑，只替换外围 validator、probe、heartbeat、文件路径与 adapter，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:820)。INV-W1 实际经过 primary 额度失败和 flash 成功后读取 status，能捕获 `count + 2`；INV-W2 对 module global wrapper、primary dispatch 和 flash 构造分别计数，能捕获 breaker 被删除、绕过或 wrapper 被前移，见同文件 [line 860](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:860) 与 [line 880](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:880)。这些 mock 没有架空被测控制流。

3. Finding #3：部分闭环  
   无效的“删除空串 guard 必转红”已正确撤销，并解释为行为等价，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:129)；五项映射表也已建立。但 INV-2 的 oracle 不可执行：映射声称“坏正则回落默认”并要求删除 `load_quota_patterns` 的坏正则 `try/except`，见同文件 [line 141](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:141)；实际 B2 既不编译正则，也不存在该 `try/except`，测试只覆盖空列表和错误类型，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:301)。真正的 `re.error` 防线位于 `is_quota_error`，见同文件 [line 242](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:242)。因此五项映射中仍有一项变异施不到所称真实输入面。

4. Finding #4：部分闭环  
   `dispatch_commit` 基线和七项完整 allowed 集合已改对，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:930)。当前 rev2 brief/计划中的 `main...HEAD` 仅为“不得使用”的说明；操作性残留只存在于历史 rev1 和咨询记录。  
   但集合差目前只是执行 `comm -23` 并观察输出，见同文件 [line 941](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:941)；`comm` 即使发现越界仍退出 0。若 `dispatch_commit` 为空或 `git diff` 失败，管道还可能由 `sort` 返回成功并生成空结果。因此尚未形成 finding 要求的机器化 fail-closed 范围守卫。

CODEX_RATIONALE:

架构落点、主档 binding 隔离、单跳控制流和密钥消费面仍成立。`resolve_role_binding()` 只读取 `provider`，不会把 `fallback_provider` 注入主 binding；现有 circuit-breaker 与成功后单次计数位置也和 rev2 测试针对的位置一致。当前 brief 的 SHA-256 与 status 中 rev2 记录一致。

本次不通过不是要求继续细化实现，而是仍有两个 brief 级 oracle 缺口：INV-2 指向一个不存在的源码变异，范围集合差则不会因违规返回失败。这两处都会允许执行报告给出“已跑”但没有真正证明不变式，符合本请求所定义的阻断条件。

CODEX_FINDINGS:

1. 修正 INV-2 的测试与变异映射。建议保持当前设计语义并明确拆分：

   - malformed TOML、空列表、错误类型由 `load_quota_patterns` 回落默认；
   - syntactically invalid regex 由 `is_quota_error` 跳过且不抛异常；
   - 增加含坏正则的真实配置/模式测试，例如 `["[", r"\bquota\b"]`；
   - 将承重变异改为删除 `is_quota_error` 的 `except re.error`，预期该测试抛异常转红，而不是删除不存在的 `load_quota_patterns` 坏正则守卫。

   同步修改 brief INV-2、B2 测试说明和 C1 mutation-probe。

2. 将范围守卫改为 fail-closed 命令：

   - 使用 `set -euo pipefail`；
   - 断言 `dispatch_commit` 非空且 `git cat-file -e "$BASE^{commit}"` 成功；
   - 让 `git diff` 失败直接终止；
   - 将 `comm -23` 写入 unexpected 文件，并用 `test ! -s` 或等价条件返回非零；
   - 可在失败前打印 unexpected 内容用于诊断。

   同步更新 brief 与 IMPLEMENTATION-PLAN。修订后须按 Re-freeze 规则更新 brief rev/hash；进入 rev3 前需履行 brief 已声明的用户批准要求。
CODEX_DECISION: REWORK

1. 主档零回归（隐患 A）：充分

`resolve_role_binding()` 对 dict 只读取 `adapter` 与 `provider`；`fallback_provider` 不会进入主 binding，无 `provider` 时明确返回 `(adapter, None)`，见 [resolve_paths.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/resolve_paths.py:334) 与 [resolve_paths.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/resolve_paths.py:369)。B5 的断言同时锁定 `adapter_name == "kimi"` 和 `binding is None`，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:722)。

补充纠正：DESIGN 所称“仅 `review.decision == N/A` 时使用 implementer identity”已经过时；当前 gate 对 `N/A` 和 `ACCEPT` 都尝试解析 developer binding，见 [gate/__init__.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/gate/__init__.py:747)。但 binding 为 `None` 时仍不会生成 implementer identity，见 [gate/__init__.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/gate/__init__.py:765)，所以结论仍是评级语义不变。

2. 正向命中才回退（隐患 B）：不充分

默认模式包含无上下文的 `insufficient`、`balance`、`credit`、`exceeded`、`billing`，以及较宽的 `rate.?limit`，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:198)。例如 `test count exceeded`、`insufficient permissions`、`billing module failed` 都会被判为额度错误。

现有负例只有 `ModuleNotFoundError`、`AssertionError`、`PROBE_OK` 和空串，完全没有携带这些歧义词的非额度失败，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:162)。因此测试只能证明部分普通错误不误判，不能证明默认模式“不掩盖真实错误”。

3. 单跳到底（隐患 C）：充分

目标、交付物和 acceptance witness 都明确规定单跳，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:14)、[WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:54) 和 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:112)。B4 测试要求 `fb.calls == 1`，实现草案在第二次 `_dispatch()` 后直接返回，没有循环或递归，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:563) 和 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:642)。DESIGN §11 也显式排除多档链。

4. 计数不双计（隐患 D）：不充分

文字不变式正确，但没有承重测试。现有 `main()` 在 circuit-breaker 后派发，并仅在最终成功后执行 `count + 1`，见 [redispatch.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/redispatch.py:393) 和 [redispatch.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/redispatch.py:515)。brief 只在附注中要求保持该语义，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:90)。

更关键的是，DESIGN 测试计划明确要求“回退成功只 +1”和“circuit-breaker 仍先于回退”，见 [DESIGN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md:167)，但 B4/B5 没有对应测试。允许修改整个 `redispatch.py` 时，仅靠注释和 post-review 不足以强制该不变式。

5. 密钥安全（隐患 E）：充分

brief 将 DESIGN §4–§8 列为权威输入，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:45)；DESIGN 明确规定检测和日志只能使用已脱敏的 `ImplementResult.output`，见 [DESIGN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md:121)。实现草案也只读取 `result.output`/`fb_result.output`，没有自行运行 subprocess。

既有 `KimiAdapter` 在 fallback binding 路径上先调用 `redact_env_value()` 再构造 `ImplementResult`，见 [kimi.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/adapters/kimi.py:107)；`adapters/kimi.py` 又被列为 forbidden。`load_quota_patterns()` 吞掉解析异常且不记录配置内容，`ProviderConfigError` 也不包含 key 值。可在 brief 附注复述该约束，但不是独立阻断项。

6. oracle 四证据：不充分

oracle 框架本身严谨：要求真实输入面变异、双向验证、config 临时副本和活树逐字节恢复，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:107)。但当前具体化存在两个承重缺口：

- 没有覆盖“计数只 +1／circuit-breaker 不绕过”。
- “删除 `if not output: return False` 后空串用例必须转红”不成立；即使删除该守卫，所有现有正则在空串上仍不匹配，函数仍返回 False，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:115) 与草案循环 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:208)。

此外，“判定恒 False”只验证漏报，不验证过宽模式导致的误报。因此四证据尚未覆盖全部五项不变式。

7. allowed/forbidden 范围：部分

brief 与 status 的 7 个 allowed 路径完全一致，status 中的 brief SHA-256 也与当前文件实际值一致。额外列出 `framework-hardening/` 或 `wrappers/` 为 forbidden 没有必要，因为 allowed whitelist 已使所有未列路径隐式禁止。`resolve_paths.py` 以文件为最小 Git 范围也可以接受，交付物已进一步限定只能新增 resolver。

但范围守卫命令不正确：[WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:127) 使用 `main...HEAD`，而该 feature branch 将从已经包含 DESIGN、HANDOFF 和 freeze 文档的 plan integration branch 切出，因此结果不会“只列 7 个允许文件”。应以派发时冻结的 integration tip/`git.dispatch_commit` 为基线，并机器校验全部 changed paths 是 allowed_paths 的子集，而不只是检查四个显式 forbidden 路径。另有文案错误：B6 写“6 个允许文件”，括号内实际列了 7 个，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:758)。

CODEX_RATIONALE:

架构落点、主档 binding 隔离和单跳控制流是正确且足够具体的；密钥路径也复用了现有脱敏边界，不要求扩大实现范围。阻断冻结的不是实现细枝末节，而是两个核心不变式尚无可承重 oracle：额度模式可能误吞真实错误，计数/circuit-breaker 接线则完全没有测试。当前 oracle 还包含一个实际不会转红的变异，无法按 brief 自己规定的标准形成证据。

这些缺口都可在现有 7 个 allowed paths 内有界修订，无需改 architecture、adapter、gate 或 independence。完成以下修订后，无需继续扩写 brief，可重新请求冻结签名。

CODEX_FINDINGS:

1. 在 brief「交付物清单 / Acceptance tests」中加入歧义边界不变式：默认模式不得把至少 `test count exceeded`、`insufficient permissions`、`billing module failed`、含 `credit` 但非账户余额语义的普通错误判为额度失败。同步要求 `is_quota_error(...) is False`，且 wrapper 的 `fallback_factory` 未调用。默认 regex 应收窄为额度/账户/API 限制语境，而不是保留无上下文单词。

2. 在 B5 和 brief Acceptance tests 增加 `main()` 接线级测试：

   - 初始 `redispatch_count=N`，primary 额度失败、fallback 成功后最终为 `N+1`，不是 `N+2`。
   - `count >= REDISPATCH_MAX` 时 primary 与 fallback 都不调用、不构造。
   - 对应 source mutation：额外增加一次计数或把 fallback 派发移到 circuit-breaker 前，测试必须转红。

3. 修正 oracle §3–§4：

   - 删除“去掉空输出 guard 必然转红”的无效变异，改为确实改变空输出结果的源码变异。
   - 增加五项不变式到“测试／真实输入面变异／预期转红 witness”的明确映射。
   - 为正向命中增加“过宽判定”变异，而不只测试恒 False 的漏报方向。

4. 修正范围守卫：用冻结的 dispatch baseline（优先 `status.git.dispatch_commit`）到 HEAD 的 changed-path 集合，与 7 项 allowed_paths 做完整集合差；不要用 `main...HEAD`。同时把 B6 的“6 个允许文件”改为“7 个”。
# Codex 独立评审 r4（WP-02 终局判决：CONSULT）

> 评审者：codex-cli（consultant 角色，独立于实现者）
> 评审对象：`5dbc0b8`（WP-02 第三次返工后）
> 范围：`fix/tool-fixes-2026-10-14..` 本轮分支尖端
> 本轮完整跑完，未因配额中断。原始会话约 6150 行，属临时产物未入库。

## 结论

| WP | r4 判决 | 提交 |
|---|---|---|
| WP-01 | ACCEPT（维持） | `71c0658` |
| WP-02 | **CONSULT**（按 §7 升级，交用户裁决） | `5dbc0b8` |
| WP-03 | ACCEPT（维持） | `3cdd101` |

**计划不可合并。本轮未授权合并。**

### 为何是 CONSULT 而非第四次 REWORK

codex 的理由：三轮修复都是「围绕上一条 mutation 局部补丁」，没有系统覆盖
「错误原因 × 输入形态 × 诊断路径」三个维度，因此每轮都还能找到同类漏检。
§7 的触发条件不是「轮数够了」，而是同一根因经两次真实修复仍存活。

归因：**(a) 测试设计问题是直接原因，(b) 编排纪律问题是促成因素
（实现者兼审核者削弱了独立的第一道检查），(c) 对抗审核确实在起作用，
但不能据此无限续跑返工。**

### r4 新增阻断发现：真实空字符串未覆盖

两个模块的测试都把「声明但为空」写成 `None`，而 TOML 的实际空值形态是
`openai_base_url = ""`。以下变异均保持 **27 passed**：

- 把 `not value` 改成 `value is None`，放行空字符串；
- 仅在空字符串时错误归因并追加环境中的 canary。

未变异代码会正确拒绝空字符串，**所以这是已证实的验收覆盖缺口，
不是当前实现已泄漏凭据**。编排者已独立复现：变异后
`build_binding` 返回 `openai_base_url=''`，27 例仍全绿。

### 历史变异全部仍被拦住

| 变异 | r4 结果 |
|---|---:|
| r1 无关原因＋假密钥 | 4 failed |
| 正确原因＋追加环境密钥 | 4 failed |
| r2 错误归因，保留 `openai_base_url` 子串 | 2 failed |
| 仅字段缺省时泄漏 | 2 failed |
| 仅字段存在但为 `None` 时泄漏 | 2 failed |
| 恢复旧 adapter 校验集合 | 5 failed |
| 删除 kimi adapter 守卫 | 1 failed |
| r3 adapter 追加密钥／错误归因 | 各 1 failed |

### 另外两项不可延期 / 可延期的区分

- 共享 helper/lint **可以延期**（它也不会自动发现遗漏的输入形态）；
- 空字符串覆盖缺口与 §7 的用户裁决**不可延期**。

### codex 调用路径的既有覆盖债务

源码中没有第三个独立的同原因 `raise`，但共享 binding 守卫的 **codex 调用
路径**仍只检查异常类型；仅对 codex 错误归因并泄漏的变异也保持 27 passed。
codex 明确指出：这是既有债务，**不能宣称全局已覆盖，也不应借此偷偷扩大
本 WP 的 kimi 范围**。

---

## 评审正文（原文）

**WP-02：CONSULT。当前计划不可合并到 `main`。** WP-01、WP-03 维持 ACCEPT。

审核范围：`5bd90b5..759b4f5`。未修改仓库文件、状态或 Git 历史；变异均在临时副本执行。[完整证据与复现脚本](/tmp/pbv-r4-evidence/README.md)。

| WP | 本轮结论 | 依据 |
|---|---|---|
| WP-01 `71c0658` | ACCEPT | 两种宿主默认分支下均 5 passed；恢复裸 `git init` 后均 4 failed |
| WP-02 `5dbc0b8` | **CONSULT** | 历史变异已拦住，但发现同类输入覆盖缺口，且触发 §7 升级条件 |
| WP-03 `3cdd101` | ACCEPT | 26 passed；恢复旧实现后 5 failed；三份契约 IN_SYNC、unchanged |

**1. WP-02：旧修复有效，仍有新漏检。**

原命令 `python3.11 -m pytest tests -q`：**924 passed、4 skipped，exit 0**。两个重点模块：**27 passed**。

| 变异 | 本轮结果 |
|---|---:|
| r1 无关原因＋假密钥 | 4 failed |
| 正确原因＋追加环境密钥 | 4 failed |
| r2 错误归因，保留 `openai_base_url` 子串 | 2 failed |
| 仅字段缺省时泄漏 | 2 failed |
| 仅字段存在但为 `None` 时泄漏 | 2 failed |
| 恢复旧 adapter 校验集合 | 5 failed |
| 删除 kimi adapter 守卫 | 1 failed |
| r3 adapter 追加密钥／错误归因 | 各 1 failed |
| 恢复两个旧 fixture | 分别 1、2 failed |

**新增阻断发现：真实空字符串没有覆盖。** [binding 测试](/Users/admin/vibe/.worktrees/pbv-plan/tests/test_provider_binding.py:95)把 `declared_but_empty` 写成 `None`；[adapter 测试](/Users/admin/vibe/.worktrees/pbv-plan/tests/test_adapter_injection.py:176)也只传 `None`。但 TOML 的实际空值形态是 `openai_base_url = ""`。

我分别进行了以下变异，两个模块均保持 **27 passed**：

- binding 或 adapter 将 `not value` 改成 `value is None`，放行空字符串。
- binding 或 adapter **仅在空字符串时**错误归因并追加环境中的 canary。

实际 TOML 解析后的空字符串，在当前未变异代码中会被正确拒绝。因此这是**已证实的验收覆盖缺口，不是发现当前实现已经泄漏凭据**。

额外全套变异得到 `923 passed、4 skipped、1 failed`；唯一失败源于临时 archive 没有 `.git`，恢复源码后该例仍同样失败，不能把它算作变异被检出。[详细日志](/tmp/pbv-r4-evidence/pbv-r4-extra.log)。

源码中没有第三个独立的同原因 `raise`。不过，共享 binding 守卫的 **codex 调用路径**仍只检查异常类型；仅对 codex 错误归因并泄漏的变异也保持 27 passed。这是既有覆盖债务，不能宣称全局已覆盖，但不应偷偷扩大本 WP 的 kimi 范围。

合法 reword 确实会令 binding 两例、adapter 一例失败。全等断言绑定了措辞，存在维护成本；对这两个短诊断可以接受。未来可考虑结构化错误字段，但不应退回无法区分原因的子串断言。

**2. §7 必须触发 CONSULT。**

[AGENTS.md §7](/Users/admin/vibe/.worktrees/pbv-plan/AGENTS.md)明确要求：同一根因经过两次真实修复仍存活时，停止并升级。这里不是仅仅“经历三轮”：修复持续围绕上一条 mutation 局部补丁，没有完整覆盖错误原因、输入形态和诊断路径，本轮仍找到同类漏检。

判断是 **(a) 测试设计问题为直接原因，(b) 编排纪律问题为促成因素；(c) 对抗审核确实发挥作用，但不能据此无限续跑返工。**

共享 helper/lint **本身可以延期**，它也不会自动发现遗漏的输入形态。当前空字符串覆盖缺口和 §7 的用户裁决不能延期。应由用户明确验收边界及继续修复方式，不能自动再开一轮 REWORK。

**3. 记录问题仅部分关闭。**

- `f4c4f5a` 已修正点名的三个旧指令。但 [WP-03 Brief:70](/Users/admin/vibe/.worktrees/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-03-brief.md:70)仍写“重渲后的契约正文”，尚不能宣称全文残留清零。
- 三个 **live status** 的 `base_commit` 都是其实现提交的祖先；WP-03 的 `9d943b8 → 3cdd101` 正确。
- 已提交冻结版 WP-03 仍是旧 `480fb80`，需按约定在 finalize 提交中折叠修正。
- “所有 status 字段均无旧历史 SHA”不成立：[WP-03 `review.evidence`](/Users/admin/vibe/.worktrees/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-03.status.json:59)仍引用 `1843f7e`。另有明确历史性引用 `480fb80`、`f2359ca`；这些可保留为历史，但须与当前有效证据区分。旧对象仍可读取，不等于属于当前分支历史。

**4. WP-01、WP-03 的 ACCEPT 继续成立。**

相关源码和测试相对各自指定提交未变，本轮已重新跑正向及反向变异。上述文档残留不推翻其代码结论，但仍需整理合并证据。

**5. kimi 环境变化应补充归因，不应改写执行者。**

保留真实的 `executor.tool=claude-code`；给“kimi 不可用”的说明补上时间范围、环境根因及恢复证据。WP-02 已追加相关说明，但旧说明不能继续作为后续代理开发的理由。

本轮未联网重跑真实 probe，因此不把 `DEEPSEEK_PROBE_OK` 冒称为独立验证结果。按用户提供的新环境事实，后续已不能沿用原不可用前提。

实现者兼审核者削弱了独立第一道检查，是连续局部修复的重要流程因素；但不能断言换成 kimi 就必然不会漏检。

**6. 签名和合并条件仍未满足。**

提示中“两个字段必须都 ACCEPT”与实际代码不完全一致：[validator](/Users/admin/vibe/.worktrees/pbv-plan/src/agentic_loop/validate_wp_status.py:56)和 [finalize](/Users/admin/vibe/.worktrees/pbv-plan/src/agentic_loop/wrappers/finalize_merge.sh:319)明确支持实现者兼审核者的 `N/A` 路径。

应如实归属：

- `review.decision=N/A`：说明 Claude 同时是实现者，不能提供独立自审。
- `consult`：记录实际 Codex 会话、报告和结论；WP-01/03 为 ACCEPT，WP-02 本轮为 CONSULT。
- r3 保留“部分发现、无正式判决”，不能补造正式 REWORK。
- 不得把同一次 Codex 审核复制成两份 ACCEPT。

实测 `plan check`、`plan lint` 均 **exit 3**；lint 仅剩三个 `finalize commit x0`，历史 status-sync 问题已关闭。WP-01/03 的 `evidence.tests` 仍为空，三份 `consult` 也为空。

此外，[PLAN:89–90](/Users/admin/vibe/.worktrees/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/PLAN.md:89)仍把 plan merge 排在 WP finalize 前，顺序错误；各 WP 必须先满足签署、证据和 finalize 提交要求。依赖 `5bd90b5` 虽已存在于远端跟踪分支，却仍不是本地 `main`／`origin/main` 的祖先，也未满足 PLAN 声明的基线前置条件。

**本轮没有授权合并；编排者应先记录 CONSULT 并交用户裁决。**
hook: Stop
hook: Stop
hook: Stop Completed
hook: Stop Completed
tokens used
115,471

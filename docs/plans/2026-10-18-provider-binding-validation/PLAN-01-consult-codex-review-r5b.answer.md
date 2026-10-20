# Codex 独立评审 r5（WP-02 终局判决：ACCEPT）

> 评审者：codex-cli（consultant 角色，独立于实现者）
> 评审对象：`b01dfd2`（按用户裁决补齐空字符串覆盖后）
> 本轮完整跑完，未因配额中断。第一次 r5 尝试于配额耗尽中止，
> 见 `PLAN-01-consult-codex-review-r5.answer.md`。

## 结论

| WP | 判决 | 提交 |
|---|---|---|
| WP-01 | ACCEPT（维持） | `71c0658` |
| WP-02 | **ACCEPT** | `b01dfd2` |
| WP-03 | ACCEPT（维持） | `3cdd101` |

三个 WP 签名齐备。**但 codex 同时指出收敛前置条件尚未满足**，其中一项
（基线 `5bd90b5` 不是 `main` 祖先）被它判为阻断，见下文第 5 节。

## 对编排者自测数据的独立核对

codex 先在 `b01dfd2^` 重跑四个 r4 变异确认**仍为 27 全绿**，再在 `b01dfd2`
重跑，由此证明检出能力确实归因于本提交，而非环境差异。

它明确确认：**我自测的 `2/2/1/1` 与 `6/3/2/2/2` 均正确**。
并纠正了一处我未察觉的差异：r4 脚本里「字段存在即泄漏」的变异现在同时覆盖
`None` 和 `""`，所以是 4 failed，与「仅 present None」不是同一个变异。

## 形态枚举的边界（codex 的裁定）

对 `str | None` 加字典字段缺省这一输入域，**三个形态已完整，没有第四个
类型内的缺值形态**。但 codex 划清了两条界：

- `0 / False / [] / {}`：当前两个 guard 都拒绝，但测试没有逐一锁定——
  它把 guard 缩窄为只拒绝 `None` 与 `""`，**仍 31 passed**。所以不能宣称
  穷尽任意输入。这些属类型错误，要求本 WP 扩展为通用类型校验
  **没有冻结范围依据**。
- `"   "`、`"   https://x  "`、裸 host：实测均被接受。本 guard 负责缺值检查，
  要求它执行 strip / scheme / URL 合法性校验会新增职责，
  **不应作为拒收理由**。

## fixture 自检：有效但有界

把 fixture 改成 `None`，自检产生 1 failed——确实关闭了它声称的漏洞。
但 codex 指出它不保证整个参数矩阵不退化：把 `declared_empty` 表项改接到
`None` fixture 仍 31 passed；删除该表项 29 passed。

结论是「不是摆设，也不是覆盖完整性的证明」。当前接线正确，
这些属未来编辑风险，不阻断本次 ACCEPT。

---

## 评审正文（原文）

**WP-02 在 `b01dfd21cc1de2ef81af0b2c416b2e0d6c66a436`：ACCEPT。** 空字符串覆盖缺口已关闭，没有依据要求再返工。**计划目前仍有收敛前置条件未满足。**

本轮未修改仓库文件、status 或 Git 历史。独立运行 `python3.11 -m pytest tests -q`：**928 passed、4 skipped，exit 0**；三份契约均 `IN_SYNC`、diff 均 `unchanged`。[完整证据与复现脚本](/tmp/pbv-r5-evidence/README.md)

**1. Mutation 结果**

在 `b01dfd2^` 重跑四个 r4 mutation，全部仍为 **27 passed**；在 `b01dfd2`：

| Mutation | 失败数 |
|---|---:|
| binding 改成只拒绝 `None` | 2 |
| binding 仅空字符串时错误归因并泄漏 | 2 |
| adapter 改成只拒绝 `None` | 1 |
| adapter 仅空字符串时错误归因并泄漏 | 1 |
| r1 无关原因＋假密钥 | 6 |
| 正确原因＋环境密钥 | 6 |
| r2 错误归因，保留字段名 | 3 |
| 仅字段缺省时泄漏 | 2 |
| 仅字段存在且为 `None` 时泄漏 | 2 |
| 恢复旧 adapter 校验集合 | 7 |
| 删除 adapter 守卫 | 2 |
| r3 adapter 追加密钥／错误归因 | 各 2 |
| 恢复两个旧 fixture | 分别 1、2 |

你的 **`2/2/1/1` 和 `6/3/2/2/2` 均正确**。原 r4 脚本中的“字段存在即泄漏”变异如今覆盖 `None` 和 `""`，所以是 **4 failed**；这与“仅 present None”不是同一变异。

**2. 形态枚举的完备性有明确边界。**

对 `str | None` 加字典字段缺省这一输入域，三个形态已经完整，没有第四个类型内的缺值形态。

- `0 / False / [] / {}`：当前两个 guard 都拒绝，符合现有 falsy 检查；但测试没有逐一锁定。我将 guard 缩窄为只拒绝 `None`、`""`，仍 **31 passed**。因此不能宣称穷尽任意 Python/TOML 输入。它们属于类型错误；要求本 WP 扩展为通用类型校验没有冻结范围依据。
- `"   "`、`"   https://x  "`、裸 host：实测均被接受。这个 guard 负责缺值检查；要求它执行 strip、scheme 或 URL 合法性校验会新增职责，**不应作为本轮拒收理由**。

**3. fixture 自检有效，但只保护 fixture 本身。**

将 `_EMPTY_URL_CFG["openai_base_url"]` 改为 `None`，自检产生 **1 failed**，确实关闭了声称的那个局部漏洞。

它不保证整个参数矩阵永不退化：

- 将 `declared_empty` 表项改接到 `None` fixture：**31 passed**；
- 删除该表项：**29 passed**。

所以它不是摆设，也不是覆盖完整性的证明。当前提交的实际接线正确，空串 mutation 确实被检出；这些未来测试编辑风险不阻断本次 ACCEPT。

**4. codex 路径债务仍可延期。**

codex-only 错误归因＋泄漏变异仍 **31 passed**。它没有因本次测试修改变成 kimi WP 的新增职责，维持 r4 的范围裁定，**不阻断收敛**。

记录有一处不准确：当前 `PLAN.md` 只有较泛的 helper/lint 债务，没有明确列出这条 codex 路径；具体债务已在 r4 报告和 live WP-02 status 中。编排者应补准登记，不能声称全局已覆盖。

**5. 收敛顺序正确，但必须包含提交与门禁步骤。**

应为：

`各 WP 证据与签署齐备 → WP finalize 并提交最终 status → plan READY_TO_MERGE → plan check/lint 全绿 → 单次 plan merge → plan finalize → 用户批准后单次 push`

实际命令是 `agentic plan merge <plan.status.json>`；它内部使用 `git merge --no-ff`，CLI 本身不接受额外的 `--no-ff` 参数。

第一次 finalize 前仍需处理：

- **更新签署与状态**：记录本轮 ACCEPT，保留 `review.decision=N/A`；WP-02 当前仍为 `BLOCKED/CONSULT`，其他两份仍为 `IMPLEMENTING`，须满足 `APPROVED_FOR_MERGE` 前置条件。
- **更新提交锚点**：三份 live `git.commit` 都是短 SHA，而 [finalize 要求 40 位 SHA](/Users/admin/vibe/.worktrees/pbv-plan/src/agentic_loop/wrappers/finalize_merge.sh:451)。WP-02 还指向旧 `5dbc0b8`，必须改为本轮审核提交。
- **完成证据落盘**：WP-01/03 的 live `evidence.tests` 已各有四项，并非仍为空；尚未提交。WP-03 live `base_commit=9d943b8` 正确，冻结版仍为 `480fb80`，须在 finalize 提交中折叠修正。本轮报告与日志也应归档。
- **准备主仓权威 status 副本及锁**：目前主仓没有本迭代这些文件；finalize 明确拒绝 linked-worktree 内的 status 路径。
- **满足基线前置条件**：`5bd90b5` 是集成分支及本地远端跟踪分支的祖先，仍不是本地 `main`／`origin/main` 的祖先。**按当前 PLAN 明文规定，这阻断计划收敛。** 推到依赖分支不等于落入 `main`；本轮用户裁决没有明确撤销该前置条件。

当前 `plan check`、`plan lint` 均 **exit 3**；lint 仅剩三个 `finalize commit x0`，没有重新出现 status-sync 违规。WP-01/03 的正向与反向验证也已重跑，维持 ACCEPT。

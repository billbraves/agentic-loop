# Codex 独立评审 r2（WP-02 复审 + WP-01/03 重新确认）

> 评审者：codex-cli（consultant 角色，独立于实现者）
> 时间：2026-10-18
> 范围：`git diff fix/tool-fixes-2026-10-14..aa15124`
> 背景：r1 判 WP-02 REWORK；返工提交 `d0f1bf6` 后请求复审。
> 分支历史在 r1 之后被重写，r1 引用的 SHA 均已失效。
> 原始完整会话（约 5600 行）属临时产物，未入库；本文件即其结论部分的完整摘录。
> 被引用的变异日志见 consult-evidence/。

## 结论摘要

| WP | r2 结论 | 对应提交 |
|---|---|---|
| WP-01 | ACCEPT（重新验证后维持） | `71c0658` |
| WP-02 | **REWORK**（第二次） | `d0f1bf6` 修好了 r1 的变异，但仍有两个漏检 |
| WP-03 | ACCEPT（重新验证后维持） | `3cdd101` |

**计划当前不可合并。**

关键数据（codex 独立复测）：

| 独立复测 | 结果 |
|---|---|
| 旧测试 + r1 原始变异 | 24 passed（r1 的漏检） |
| 当前测试，无变异 | 25 passed |
| 当前测试 + r1 原始变异 | **2 failed**（返工生效） |
| 保留正确原因，仅追加假密钥 | **1 failed** |
| 消息改为「openai_base_url 有效、缺 identity_model」 | **25 passed，漏检** |
| 仅在字段完全缺省时泄漏假密钥 | **25 passed，漏检** |

---

## 评审正文（原文）

**WP-02：REWORK。当前计划仍不可合并到 `main`。** WP-01、WP-03 经本轮重新验证，继续 **ACCEPT**，分别对应 `71c0658`、`3cdd101`。

审核范围为 `fix/tool-fixes-2026-10-14..aa15124`。未修改仓库文件及已有 status 改动；变异均在临时副本执行。

1. **WP-02 修复了原始 mutation，但验收断言仍有缺口。**

   我从 round-1 原始记录恢复了完全相同的消息变异：

   ```text
   unrelated failure sk-SECRET-LEAK-CANARY
   ```

   | 独立复测 | 结果 |
   |---|---|
   | 旧测试＋原始 mutation | 24 passed |
   | 当前测试，无变异 | 25 passed |
   | 当前测试＋原始 mutation | **2 failed / 23 passed** |
   | 保留正确原因，仅追加假密钥 | **1 failed / 24 passed** |
   | 消息改为 `adapter 'kimi': openai_base_url is valid; missing identity_model` | **25 passed，漏检** |
   | 仅在配置完全缺少 `openai_base_url` 时追加环境中的假密钥 | **25 passed，漏检** |

   两个阻塞问题：

   - [消息断言](tests/test_provider_binding.py:102)只要求包含字段名和 adapter，无法区分“缺少该字段”与“该字段有效、另一个字段缺失”。用户要求检查的“仅断言偶然出现的子串”问题仍存在。
   - [历史配置形态用例](tests/test_provider_binding.py:107)没有设置 canary，也没有密钥缺席断言。现有脱敏断言只覆盖 `openai_base_url=None`；完全缺省字段时泄漏环境中的假密钥仍全绿。`d0f1bf6` 提交说明声称历史形态也有同样断言，与代码不符。

   需要让两种输入形态都验证明确的缺字段原因及密钥不泄漏，并分别证明错误原因变异、泄漏变异转红。[原始 mutation 证据](consult-evidence/r2-exact-r1.log)、[缺省字段泄漏证据](consult-evidence/r2-absent-real-env-leak.log)。

   **没有发现其他测试被削弱。** 其余 9 个既有测试函数 AST 完全不变；被折叠的历史形态用例保留了原输入、调用及异常类型检查，没有损失原覆盖。恢复旧校验产生 **3 failed**，删除 adapter 守卫产生 **1 failed**。实现本身的正确性判断不变。

2. **英文范围锚点已修正，但不能确认冻结输入全文只剩一种口径。**

   WP-02 的英文锚点已补齐两个测试文件；WP-03 的英文锚点已禁止修改三份契约，与 status 一致。

   残留文字仍需清理：

   - [WP-02 Brief:45](docs/plans/2026-10-18-provider-binding-validation/WP-02-brief.md:45)保留“除非 contract checksum 真的变了”的黑名单例外，而英文锚点/status 无条件禁止；附注又要求变化时停止报告。
   - [WP-03 Brief:10](docs/plans/2026-10-18-provider-binding-validation/WP-03-brief.md:10)仍要求重渲三份契约，[附注:82](docs/plans/2026-10-18-provider-binding-validation/WP-03-brief.md:82)仍要求 `diff --apply`，与 re-freeze 后禁止触碰契约的范围不一致。

   这些旧文字不能作为扩大权限的依据，但“全文无第二套范围”的关闭条件尚未满足。

3. **历史中的 status-sync 违规已关闭；finalize 尚未完成。**

   指定的 `agentic plan lint …/PLAN-01.status.json` 返回 **exit 3**，仅报告：

   ```text
   WP-01: finalize commit x0 (expected 1)
   WP-02: finalize commit x0 (expected 1)
   WP-03: finalize commit x0 (expected 1)
   ```

   没有 status-sync 提交。逐提交提取并运行 `validate_wp_status`：**8 个提交、21 份本迭代 WP status 快照全部 STATUS_VALID**，包括首次 freeze；`executor.tool` 均为 `claude-code`。三份当前未提交 status 也通过 schema 校验。

   但 schema 合法不等于证据完整：[WP-03 status:23](docs/plans/2026-10-18-provider-binding-validation/WP-03.status.json:23)仍以旧历史的 `480fb80` 为 `base_commit`，它不是 `3cdd101` 的祖先。

4. **历史重写本身未发现侵入无关用户修改；旧 ACCEPT 已重新建立依据。**

   提示中的“旧 SHA 不再存在”不准确：它们已退出当前分支历史，但本地 Git 对象仍可读取。因此我能直接比较：

   - `28a7b97 → 71c0658`：WP-01 implementation diff 完全一致。
   - `f2359ca → 9d943b8`：WP-02 implementation diff 完全一致。
   - `848c359 → 3cdd101`：WP-03 implementation diff 完全一致。

   WP-01 在默认分支 `master`、`review-unusual` 下均 **5 passed**；恢复裸 `git init` 后 **4 failed / 1 passed**。WP-03 **26 passed**；恢复旧列表包裹实现后 **5 failed / 21 passed**。三份契约内容未变，`contract check` 全部 `IN_SYNC`，`contract diff` 全部 `unchanged`。

   因而 WP-01/03 的 ACCEPT 是经内容比对和重新验证后确认，不能仅靠换填 SHA 转移。按所述“本地、未推送、编排者自有提交”的前提，重写不违反禁止重写无关用户修改的规则；“从未推送”无法仅凭本地记录证明。

5. **合并仍须阻断，pre-push 缺陷可延期，但不能视为门禁已通过。**

   当前还缺：

   - WP-02 上述验收缺口修复及独立复审；
   - 冻结输入残留矛盾、旧 SHA 引用和审核证据的整理；
   - 有效签署、各 WP 在集成分支上完成并提交 finalize，以及 plan 达到 `READY_TO_MERGE`、lint 全绿。

   `agentic plan check` 当前返回 **exit 3**：读取到的三份已提交 WP 状态都是 `IMPLEMENTING`。三份 live status 的 `consult` 也均为空。

   [PLAN.md:76](docs/plans/2026-10-18-provider-binding-validation/PLAN.md:76)的恢复步骤顺序错误：不能先 plan merge，再用 plan finalize 补齐 WP finalize。实际门禁要求合并前集成分支上各 WP 已为 `MERGED`。此外，PLAN 声明的基线先落 `main` 的前置条件尚未满足：`5bd90b5` 目前不是本地 `main` 的祖先。

   pre-push 问题已在 PLAN 登记，归因正确。我再次用绝对 `PYTHONPATH` 在当前版本和 `origin/main` 复现了 `PRE_PUSH_SKIP`：**它是真实的既有门禁缺陷，不是可忽略的环境异常。** 可接受留到后续迭代处理，**不单独阻断本次本地合并**，前提是本次显式完成所需门禁，不能将 hook 的 skip 当作通过。`AGENTIC_PYTHON` 绕过 PATH stub 的既有测试隔离问题也在两版本复现。

本轮按原命令执行 `python3.11 -m pytest tests -q`：**922 passed，4 skipped，exit 0**。全套通过不消除上述 mutation 漏检和合并状态阻塞。
hook: Stop
hook: Stop
hook: Stop Completed
hook: Stop Completed
2026-10-19T01:58:25.061559Z ERROR codex_models_manager::manager: failed to refresh available models: request timed out
tokens used
102,330

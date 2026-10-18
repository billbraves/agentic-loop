# Codex 独立评审（PLAN-01 三个 WP）

> 评审者：codex-cli 0.159.3（consultant 角色，独立于实现者）
> 时间：2026-10-18
> 范围：`git diff fix/tool-fixes-2026-10-14..d1b9123`
> 触发原因：三个 WP 均由编排者代理开发，按 AGENTS.md §8 编排者不得自评。
> 原始完整会话记录见 /tmp/codex-review-out.txt（含 codex 读取的文件上下文）。

## 结论摘要

| WP | 独立结论 |
|---|---|
| WP-01 | ACCEPT |
| WP-02 | **REWORK** |
| WP-03 | ACCEPT |

合并前阻断项：提交纪律门禁失败（plan lint exit 3）；Brief 与 status 范围口径不一致；
pre-push 钩子在 linked worktree 下漏读状态（既有缺陷）。

---

## 评审正文（原文）

**当前不应合并。** 审核范围为 `fix/tool-fixes-2026-10-14..d1b9123`；未修改仓库文件或状态。

| WP | 独立结论 | 主要依据 |
|---|---|---|
| WP-01 | **ACCEPT** | 确认是默认分支依赖；断言未削弱，恢复缺陷后同四例转红 |
| WP-02 | **REWORK** | 实现方向正确，但缺少 Brief 明确要求的原因特异性、kimi 错误消息脱敏测试 |
| WP-03 | **ACCEPT** | 渲染器回归归因成立；三份契约内容正确且完全未变；禁止变异使五例转红 |

**WP-01**

[fixture:80](/tmp/pbv-plan/tests/test_finalize_merge_triple_sign.py:80) 明确固定 `git init -b main`，状态与 checkout 共用 `INIT_BRANCH`。实际 diff 没有删除、跳过或放松任何断言。

独立复现结果：

- `origin/main`，默认分支 `master`：**4 failed / 1 passed**，均在 `git checkout -q main` 抛出 `CalledProcessError`。
- 同一基线，默认分支 `main`：**5 passed**。
- 当前实现，默认分支分别为 `master`、`review-unusual`：均 **5 passed**。
- 临时副本恢复裸 `git init`：同四例再次失败。

**WP-02**

行为修复本身成立：[provider_binding.py:59](/tmp/pbv-plan/src/agentic_loop/provider_binding.py:59) 要求 `openai_base_url`；[kimi.py:66](/tmp/pbv-plan/src/agentic_loop/adapters/kimi.py:66) 拒绝缺值，随后只把该字段写进 `type="openai_legacy"` 配置。我独立解析实际生成的 TOML，确认 URL 精确匹配且不含 anthropic 端点。

既有测试修改合理：准确说是**两个 fixture 和一处注释**。恢复旧 `FLASH_CFG` 后，`test_resolves_flash_binding` 失败；恢复旧 `_flash_binding(openai_base_url=None)` 后，脱敏与 bound probe 两例失败。原断言都保留，提交说明也解释了旧前提。

**阻塞项：验收测试未覆盖明确承诺。** [Brief:116](/tmp/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-02-brief.md:116) 要求错误不泄漏 key，[Brief:126](/tmp/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-02-brief.md:126) 要求消息指向缺失字段；但 [test_provider_binding.py:84](/tmp/pbv-plan/tests/test_provider_binding.py:84) 和第 96 行只检查异常类型，现有脱敏测试只调用 `claude`。

我把 OpenAI 缺字段错误消息变异为“无关原因 + 假密钥”，两个相关模块仍 **24 passed**。因此需要补充 kimi 的字段消息断言、假密钥泄漏断言，以及相应变异转红证据。现有两项代表性变异可以复现：恢复旧校验产生 **2 failed**；删除适配器守卫产生 **1 failed**。

[status:83](/tmp/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-02.status.json:83) 确实诚实记录了兼容性变化和 contract DoD **未满足**；没有冒报完成。该项在 WP-02 提交处仍失败，由 WP-03 在集成结果中补齐。

**WP-03**

独立计算结果：

| 版本 | renderer checksum |
|---|---|
| `origin/main`、审核基线、WP-02 提交 | `c2ab3c3bb360dadc` |
| 当前实现 | `307a6503bae68e97` |

[AGENTS.md:1](/tmp/pbv-plan/AGENTS.md:1) 原本就盖有 `307a6503bae68e97`。三份治理文件在上述版本间逐字一致；当前 `contract check` 全部 `IN_SYNC`，`contract diff` 全部 `unchanged`。增删 provider 的 `openai_base_url` 不改变 checksum。

[contract_render.py:104](/tmp/pbv-plan/src/agentic_loop/contract_render.py:104) 正确提取表格式角色的 adapter；[测试:254](/tmp/pbv-plan/tests/test_contract_render.py:254) 验证实际渲染结果并保留 provider 信息。恢复旧列表包裹实现后 **5 failed**。

缩窄范围有实质依据，且缩窄后的 Brief/status 已在 `1843f7e`、实现提交之前存在；未发现事后为越界修改开脱的证据。不过 Git 中没有单独的原版→r1 冻结历史，不能进一步证明未提交阶段的时间顺序。

**跨 WP 的合并阻塞与记录问题**

1. **提交纪律门禁实际失败。** 独立运行 `plan lint`，exit **3**：WP-01/02 各有两个 status-sync 提交（`5d4554f`、`480fb80`），WP-03 有一个（`d1b9123`）。它们违反 [AGENTS.md:242](/tmp/pbv-plan/AGENTS.md:242)；即使随后正常 finalize，这些违规提交仍然存在。缺少 finalize 在当前审核阶段是正常的，中间状态提交违规则不是。

2. **实现范围通过，Brief 口径仍需统一。** 对照各实现提交当时的 status，WP-01/02/03 分别修改 **1/7/2** 个文件，全部属于白名单且无黑名单命中。其余五个提交修改的是编排文档，不能混称为“全部提交均处于实现白名单”。此外，[WP-02 Brief:135](/tmp/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-02-brief.md:135) 漏掉已追加的两个测试文件；[WP-03 Brief:114](/tmp/pbv-plan/docs/plans/2026-10-18-provider-binding-validation/WP-03-brief.md:114) 仍允许修改已被 status 禁止的三份契约。冻结输入内部不应保留两套范围。

3. **绝对 `PYTHONPATH` 暴露真实的既有门禁缺陷。** [pre-push.tmpl:53](/tmp/pbv-plan/src/agentic_loop/templates/pre-push.tmpl:53) 在包可导入时调用 `_iterations_dir()`，而 [resolve_paths.py:305](/tmp/pbv-plan/src/agentic_loop/resolve_paths.py:305) 返回主仓目录，导致遗漏当前 worktree 的状态并输出 `PRE_PUSH_SKIP`。在当前分支和 `origin/main` 均复现。它不是本次引入，但不能以“环境问题”消掉，或据此宣称门禁可靠；应明确登记并处置。
   
   `AGENTIC_PYTHON` 则确实绕过了测试的 PATH stub：测试继承该变量，而 wrapper 优先使用它。这属于既有测试隔离问题，同样在基线复现。

独立执行 `python3.11 -m pytest tests -q`：**921 passed，4 skipped，exit 0**；相关模块另跑 **103 passed**。全绿不能替代上述缺失的验收断言和失败的合并门禁。[全套日志](/tmp/pbv-review-pytest.log)、[变异证据](/tmp/pbv-review-mutations.log)、[环境对照](/tmp/pbv-review-env.log)。
hook: Stop
hook: Stop
hook: Stop Completed
hook: Stop Completed
tokens used
90,439

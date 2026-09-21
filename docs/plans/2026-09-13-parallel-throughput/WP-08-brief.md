# WP-08: 解开双签合并门的独立性死锁

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

让「编排者如实签下 ACCEPT」不再等价于「合并门永久拒绝」，且**不通过放宽
`min_independence`、不通过伪造 attestation** 达成。

## 背景

WP-01 与 WP-03 均已 ACCEPT，实跑 `agentic gate` 得到：

```
GATE_FAIL: independence level none does not meet minimum weak; reasons:
reviewer identity unavailable (orchestrator, attested not engine-proven);
no implementer fallback available; reviewer attestation missing
```

`independence.evaluate()` 三条路径在本仓的实际可达性：

- **strong**：要求两个 engine-observed model id 不同。本仓三签全绑同一
  `deepseek-v4-pro`（PLAN §3.3 已冻结此代价），永远不可达。
- **degraded**（consultant vs implementer）：两边都是机器观测身份，**不需要任何
  自证**，是三条里证据最硬的。但 `gate/__init__.py:738-741` 只在
  `review.decision == "N/A"` 时才 populate `implementer_id`。
- **bootstrap**：唯一信号是 `review.attestation`，而
  `ReviewerAttestation.is_valid()`（`independence.py:38-54`）要求
  `fresh_session is True` 且 `adversarial_prompt is True`（严格 `is True`）。

于是编排者一旦如实写 `ACCEPT`，degraded 路径被条件挡住，只剩 bootstrap；
而 `fresh_session` 是「审核者是否在干净会话、未参与规划」的事实断言——
本轮编排者撰写了 PLAN 与两个 brief、派发并盯完执行，该断言为假。
**要过门就得写 true，那是伪造审计记录换合并许可**，正是 `min_independence`
要防的事。唯一诚实的出路是不合并，于是两个已验收的 WP 卡死。

这是流程缺陷而非配置问题：把 `min_independence` 降到 `none` 等于关掉双签。

## 范围

**allowed_paths**
- `src/agentic_loop/independence.py`
- `src/agentic_loop/gate/__init__.py`
- `tests/test_independence*.py`
- `tests/test_gate_independence*.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`（**尤其禁止**：不得以调低 `min_independence` 的方式"解决"）
- `src/agentic_loop/wrappers/`
- 其余一切未在 allowed 列出的路径

## 输入

- 依赖的上游 WP 产出：无（本 WP 是 `lane-gate-fix` 的头，且不与任何现有 lane 重叠）
- 现状代码：`src/agentic_loop/independence.py` 的 `evaluate()` 与
  `ReviewerAttestation.is_valid()`；`src/agentic_loop/gate/__init__.py:733-796`
  的独立性评级与门限判据段
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §A0

## 交付物清单

**首选方案（编排者判断这是缺陷而非设计）**：让 degraded 路径对
`review.decision == "ACCEPT"` 也可用。

1. `gate/__init__.py`：populate `implementer_id` 的条件从「仅 `N/A`」放宽到
   「`N/A` 或 `ACCEPT`」。理由：consultant 与 implementer 都是 engine 观测身份，
   证据强度**高于**自证的 attestation；只在 `N/A` 时启用没有可辩护的理由，
   看起来是条件写窄了。
2. 相应的 attestation 语义调整：bootstrap 路径仍保留（`implementer_id` 缺失时），
   但 `fresh_session` 不再作为**通过条件**，改为**记录性字段**——如实写 `false`
   也能过，其值写进 `consult.independence` 留痕。`adversarial_prompt` 保留为条件。
   > 若你判断此条会削弱审计强度，**不要动**，只做第 1 项，并在
   > `[CONCERNS]` 说明理由。第 1 项是本 WP 的硬要求，第 2 项是可选。
3. 测试：见 DoD。

**不要做的事**：不要改 `.agentic/config.toml` 的 `min_independence`；
不要让 `evaluate()` 在任何情况下返回 `strong`（本仓同模型，strong 必须不可达）；
不要移除 fail-closed floor。

## 完成定义（DoD）

- [ ] **characterization test 先行**：先固化 `evaluate()` 现有的全部分支输出
      （strong / weak / weak-attested / none 各自的 level 与 reasons），
      证明改动只放开了 degraded 路径的**准入条件**，没有改变任何一条路径的**评级结果**。
- [ ] 反向测试：`min_independence = "strong"` 时，同模型的 consultant 与
      implementer **仍然**评不到 strong（防止"修复"变成绕过）
- [ ] 反向测试：attestation 里 `adversarial_prompt` 为 false 或缺失时仍 fail-closed
- [ ] 正向测试：`review.decision == "ACCEPT"` + 同模型 consultant/implementer
      + `min_independence = "weak"` → 评到 weak 且门放行，
      且 `consult.independence` 记录了这是 degraded 路径而非 attested
- [ ] 若做了第 2 项：测试 `fresh_session = false` 能过门，且该事实出现在
      `consult.independence` 的留痕里
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
- [ ] 无 forbidden_paths 写入（特别确认没碰 `.agentic/config.toml`）
- [ ] 无生产 DB 写入、无网络、无推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **这个 WP 改的是"谁能批准合并"的判据，是本仓最敏感的一处逻辑。**
   任何让门更容易通过的改动都要有对应的反向测试证明它没有顺手打开别的口子。
   看到可以简化的 fail-closed 分支，记进 `[CONCERNS]`，不要动。
2. **`is_valid()` 的严格 `is True` 是刻意的**（拒绝 `1` 与 `"true"`）。
   如果你动 attestation，保持这个严格性，不要改成 truthy 判断。
3. `evaluate()` 是纯函数（无 IO、无时钟），保持这个性质。
4. **本仓 Python 兼容 >= 3.9**，跟随现有 `from __future__ import annotations` 写法。
5. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
6. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的 characterization / 反向测试要求见上文 DoD。

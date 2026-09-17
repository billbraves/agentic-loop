# WP-18: Codex 评审通道 —— 文件回填/JSONL 硬化与无损分块能力合并

> 冻结日期 <待冻结> | 编排者 Kiro（DeepSeek Harness）| 执行者 kimi
> 所属 Plan：PLAN-CODEX（迭代 2026-09-14-codex-verdict-contract）；集成到 `main`，本仓 native gate 后合入。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）
让 `CodexAdapter.review()` **同时**具备两支此前分叉、从未合并的能力——(A) 每次调用的
完整 brief+diff 文件回填 + per-review 临时 cwd 隔离 + `--ignore-user-config` +
JSONL 协议硬化 + 同 session 一次性 finalization 收尾（分支 `fix/codex-isolated-review`
tip `f8eba27`），叠加 (B) WP-17 的按文件/hunk 边界无损分块 + 按严重度保守 fail-closed
聚合（`main` 已含，`beb167b`）——从而在大而复杂的真实 diff 上稳定拿到 fail-closed 的
结构化 verdict。

## 事件证据（根因诊断，只读，已钉死）
消费方 consumer-repo 的 harness-architecture 迭代 WP-34（发布治理门禁）候选 diff
`da4be64..a92af05` = **388695 字节**（`test_harness_release_gate.py` 190KB +
`harness_release_gate.py` 142KB，密集对抗性 Python），P2 high-effort native gate 两次
尝试（726s / 809s）均 `task_complete` 但 `last_agent_message=null`、answer 0 字节。

根因经受控核实：
1. 两支能力分叉，互不包含。已验证 `01312c5`（文件回填）非 `main` 祖先；
   `fix/codex-config-isolation-chunking`（=WP-17，仅分块）不含 `candidate.diff`/
   `_read_thread_id`/`_resume_finalization`；`fix/codex-isolated-review`（tip `f8eba27`，
   有文件回填/JSONL/finalization）不含 `_split_diff`/`_CHUNK_PROMPT_MAX_BYTES`。
2. WP-34 最后一次 gate 跑的正是缺分块的那一支（`PYTHONPATH=.../codex-isolated-review/src`），
   把 388KB 作为单轮负载送入 provider。
3. WP-17 分块代码实测标定：网关 ~398KB 单请求 tokens=0（拒绝），~142KB 正常；150KB 安全线。
   388KB 正落入拒绝区间。
4. 决定失败的是内容复杂度而非纯字节：合成 410KB 平凡内容曾成功，真实 388KB 密集对抗
   逻辑失败。故不能靠"按字节精简"，也不得截断（有损，违反 no-truncation 合同）。

完整诊断见消费方仓 `docs/plans/harness-architecture/WP-34-native-gate-rootcause.md`
（commit `3b1be2b`）。

## 范围
- **allowed_paths**（白名单）：
  - `src/agentic_loop/adapters/codex.py`
  - `tests/test_codex_gate_capability_merge.py`（新增；合并后的组合行为测试）
- **forbidden_paths**（黑名单）：
  - `.env`、`.context/`、`.agentic/config.toml`
  - `src/agentic_loop/gate/`、`src/agentic_loop/wrappers/`、`src/agentic_loop/independence.py`
  - `tests/test_codex_verdict_recovery.py`（WP-16 所有，不得改动）
  - `tests/test_codex_config_isolation_chunking.py`（WP-17 所有；如需调整须显式说明且不得削弱）
  - 一切消费方仓库与未显式允许的文件

## Git 治理合同
- 集成分支：`main`（本仓约定，与 WP-16/WP-17 一致）；native gate 后合入。
- WP 分支：`fix/wp-18-codex-gate-capability-merge`。
- base_commit：本仓 `main` tip（含 WP-17 分块 `beb167b`），作为分块侧基线。
- 文件回填/JSONL/finalization 侧以 `fix/codex-isolated-review` tip `f8eba27` 为能力来源
  （非 status 旧记录的 `01312c5`）。
- 默认 `merge_method=no-ff`；审核签名后禁止 amend/rebase/squash 复用旧签名。

## 输入
- 上游能力来源：`main`(`beb167b`，分块) + `fix/codex-isolated-review`(`f8eba27`，文件回填/JSONL/finalization)。
- 参考：WP-16-brief、WP-17-brief、消费方 `WP-34-native-gate-rootcause.md`。

## 关键设计约束（合并两支时必须同时满足）
1. **无损**：分块只按 `diff --git` 文件边界、必要时按 `@@` hunk 边界切分，绝不改写/截断/摘要 diff 内容；单块仍超阈值则 fail-closed，不截断。
2. **文件回填**：每块的 brief+chunk-diff 仍以字节数+SHA-256 绑定写入 per-review 临时文件，provider 完整读取；小 prompt 只承载文件名/字节/摘要。
3. **JSONL 硬化不被绕过**：每块评审、空终态 finalization 收尾都走已验证的单 thread/单 turn JSONL 状态机 + `-o` artifact 逐字一致校验；tool-free 收尾禁用 shell/multi_agent。
4. **聚合语义不变**：多块 verdict 按 `_parse_verdict` 白名单严重度降序保守聚合（最严格胜出），findings 合并；聚合层不含任何 decision 字面量、不做自然语言→决策映射。
5. **单块内仍保留 WP-16 的空返/非法输出有界恢复**（一次完整重试或一次 structure-only 归一化，二次失败 fail-closed）。
6. **provider/auth/effort/read-only sandbox** 契约保持不变。

## 交付物清单
- [ ] `src/agentic_loop/adapters/codex.py` — 合并后的 review 流水线：分块 → 每块文件回填 + JSONL 硬化评审 → 保守聚合；单块走既有有界恢复/finalization。
- [ ] `tests/test_codex_gate_capability_merge.py` — 组合行为测试：大 diff 触发分块、每块文件回填+JSONL 校验、聚合严重度、单块空返 finalization、无损性（拼接=原 diff）、超阈值 fail-closed。

## 完成定义（DoD）
- [ ] 交付物逐项就绪
- [ ] 既有 `tests/test_codex_verdict_recovery.py`(WP-16) 与 `tests/test_codex_config_isolation_chunking.py`(WP-17) 全绿，不得削弱/跳过
- [ ] 新增组合测试全绿
- [ ] 全仓测试套件通过（modulo 独立复现的既有 baseline）
- [ ] 独立评审 ACCEPT
- [ ] 本仓 native gate 对**本 WP 自己的 adapter diff**产出有效结构化 verdict（自证：合并后 runtime 能力可用）。注意与下游区分：WP-18 的 gate 审的是本 WP 的改动；消费方 WP-39 的 gate 是用合并后 runtime 审 **WP-34 的 388KB diff** 以取第二签名——两次不同 gate、不同被审对象，不是同一次。
- [ ] 无 forbidden_paths / 跨 owner 写入；无生产写入、无网络、无通知、无推送

## 风险声明
| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注
- 已知陷阱：分块后每块仍需完整文件回填，不能退回 inline，否则 JSONL 硬化的 artifact 绑定失效；聚合层若引入 decision 字面量会触发 AST 结构性 killer。
- 口径权威源：分块边界与聚合语义以 WP-17（`beb167b`）为准；JSONL 状态机与 finalization 语义以 `fix/codex-isolated-review`(`f8eba27`) 为准。

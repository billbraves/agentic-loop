# WP-20: codex finalization JSONL 校验容忍良性 provider 告警 item

> 立项日期 <待冻结> | 编排者 Kiro（DeepSeek Harness）| 执行者 <待定，可 option B 直接实现>
> 冻结后执行期间不得修改；需修订走 re-freeze。

## 目标（一句话）
在 codex adapter 的**空终态 finalization / tool-free resume** JSONL 校验里，把
codex 0.154 在**自定义 provider（DeepSeek）**下发出的**良性、无副作用的
metadata 告警 item**（`item.type == "error"`，文案为 “Model metadata for
`deepseek-v4-pro` not found. Defaulting to fallback metadata; …”）纳入**严格白
名单化**的容忍集，使空终态 resume 能正常取回 verdict——同时**绝不放宽**任何工具/
命令/未知 item 的 fail-closed 语义。下游解锁 WP-39 Run 3。

## 背景（关键，供新 session 从零重建）
- 本 iteration 目标链：WP-34（消费方 consumer-repo 的 release-governance WP）因
  P2 合同强制的 native Codex 第二签名在大 diff 上拿不到而 BLOCKED。修复路径是升级
  agentic-loop 仓的 codex adapter：
  - **WP-18**（已 MERGED `3d50ab7`）：无损分块 + 文件回填 + JSONL 硬化 + finalization。
  - **WP-19**（已 MERGED `d587992`，runtime 状态戳 `c86b35c`）：行级 sub-hunk 无损切分。
  - **WP-20（本 WP）**：finalization 校验容忍良性 provider 告警 item。
- 跨仓协调件是 consumer-repo 的 **WP-39**（分支
  `feature/harness/wp-39-codex-gate-capability-merge`，worktree
  `/Users/admin/vibe/consumer-repo/.worktrees/wp39-codex-gate-merge`）。它的
  `docs/plans/harness-architecture/WP-39-unlock-record.md` 记录了两次 gate 运行：
  - **Run 1**（runtime `3d50ab7`）：分块生效，但 fail-closed 于 190KB 单-hunk 新文件
    `.ci/tests/test_harness_release_gate.py`（`@@ -0,0 +1,4170 @@`）。→ 催生 WP-19。
  - **Run 2**（runtime `c86b35c`）：WP-19 行切生效、越过该文件；新 fail-closed：
    `codex final-message protocol mismatch: tool-free turn emitted an unexpected event`。
    gate log `/tmp/wp39-wp34-gate-run2-1789685550.log`，sha256
    `1e6ed451f3dd48db17d7821b91a2397ac8dc80850a1f8aaa7cf0eda87faa2c90`。

## 根因（含一处必须先证实的不确定性）
`_validated_final_message`（`src/agentic_loop/adapters/codex.py` ~505–573）在
`tools_forbidden`（finalization/resume）分支有**两道**校验，两者的报错文案不同：
- **L527–534 turn 生命周期**：`"error" in types` 直接判 “invalid turn lifecycle”。
  注意：这里判的是**顶层 event type**是否有 `"error"`。
- **L545–556 事件类型白名单**：event type 不在
  `{thread.started, turn.started, item.completed, turn.completed}` → “unexpected event”。
- **L557–573 item 子类型白名单**：`item.completed` 的 `item.type` 不在
  `{reasoning, agent_message}` → “tool or unknown item”。

**实测探针**（真实 codex 0.154 + DeepSeek provider，high effort）复现出：codex 会
多发一个 `item.completed`，其 `item.type == "error"`，内容是上述良性 fallback
metadata 告警。该 item **会触发 L557–573**（“tool or unknown item”）。

**但 Run 2 gate 实际报的是 L545–556 的 “unexpected event”**（顶层 event type 命中）。
两者不一致，说明 gate 真实失败的那条 JSONL 里可能还有一个**顶层 `error` 事件**或
其它非预期 event type（也可能被 L527–534 的 `"error" in types` 命中——需核实报错
文案到底来自哪一处）。**因此实现的第 0 步必须先抓到真实失败的 JSONL 事件流**，
用事实定位到底命中哪一（或哪几）道校验，再对症放行。不得凭 Run 2 单行报错猜。

## 范围
- **allowed_paths**（白名单）：
  - `src/agentic_loop/adapters/codex.py`（仅 `_validated_final_message` 相关校验的
    容忍逻辑 + 必要的私有小助手；不改 review()/分块/行切/文件回填/聚合/决策语义）
  - `tests/test_codex_finalization_benign_warning.py`（新增，本 WP 专属测试）
- **forbidden_paths**（黑名单）：
  - `.env`、`.context/`、`.agentic/config.toml`
  - `src/agentic_loop/gate/`、`src/agentic_loop/wrappers/`、`src/agentic_loop/independence.py`
  - `tests/test_codex_verdict_recovery.py`、`tests/test_codex_config_isolation_chunking.py`、
    `tests/test_codex_gate_capability_merge.py`、`tests/test_gate_diff_start.py`、
    `tests/test_codex_line_level_split.py`（WP-16/17/18/19 冻结测试，不得改动；
    若与本 WP 冲突，须停下走 re-freeze，不得擅改）
  - 一切消费方仓库文件

## 设计约束（严格白名单化——安全优先，绝不放宽真正的 fail-closed）
1. **只容忍确切的良性告警**：容忍谓词必须精确匹配「codex 发出的、无外部副作用的
   metadata fallback 告警」这一确切语义——即 `item.type == "error"` **且**其消息
   文本匹配 codex 的 fallback-metadata 告警特征（如包含 “Model metadata for” 与
   “Defaulting to fallback metadata”）。用**具名常量 + 精确子串/前缀判定**，不得
   用宽泛的“凡 error 皆放行”。
2. **绝不放宽工具/命令/未知能力**：`command_execution`、`file_change`、MCP、web、
   patch/apply 等任何工具或未知 item 仍必须 fail-closed（保持 L557–573 对
   `{reasoning, agent_message}` 之外的拒绝，仅**新增**对良性 error-item 的例外）。
3. **turn 仍须单 thread/单 turn、agent_message 仍须紧邻 turn.completed**：不改
   L509–544 与 L574 之后的最终消息定位/artifact 逐字校验；良性 error-item 被容忍
   后，仍要求存在合法 agent_message 且其为 turn 内最终内容项。
4. **真正的失败仍 fail-closed**：`turn.failed`、真实 error（非该良性告警）、rc!=0、
   空、artifact 不符、thread 不唯一/错乱等一律保持 raise。
5. **静态不变量延续**：无 regex；决策字面量仅限 `_parse_verdict`/`_build_prompt`；
   容忍逻辑不得引入 ACCEPT/REWORK/CONSULT 字面量。
6. **每块调用预算不变**（初次 + 至多一次 recovery）；本 WP 不新增 provider 调用。

## 验收判据（DoD）
- [ ] **第 0 步**：抓取真实失败 JSONL（重跑一次带 `--json` 且**保留临时目录**的
      finalization，或在 adapter 加临时诊断 dump 后跑一次 gate），确证命中的确切
      校验点与事件流，记录到 status 证据。
- [ ] 依据事实，在 finalization 校验中**严格白名单化**容忍 codex 良性 fallback-metadata
      告警 item（及若确有的对应顶层 error 事件），其余一切保持 fail-closed。
- [ ] 新测试 `tests/test_codex_finalization_benign_warning.py` 覆盖：
      - 含**良性 metadata 告警 error-item** + 合法 agent_message 的 finalization JSONL →
        正常返回 verdict（不再 raise）；
      - 含**真实 error / turn.failed** 的 → 仍 fail-closed；
      - 含**工具/命令/未知 item**（command_execution/file_change/MCP/web）的 →
        仍 fail-closed（回归守卫，证明未放宽）；
      - 良性告警**但缺 agent_message** 的 → 仍按“无最终消息”处理（返回 None / 触发既有
        空终态语义，不得凭空造 verdict）；
      - 告警文案不匹配（伪装成 error 的其它消息）→ 仍 fail-closed（防绕过）。
- [ ] WP-16/17/18/19 冻结测试**全绿不改动**；五套 codex 测试全绿。
- [ ] 全仓无新增失败（既有 git-env baseline 4 失败除外）。
- [ ] 静态 killer 绿（无 regex、无越界决策字面量）。
- [ ] 独立评审 ACCEPT；合并需用户批准。

## 风险声明
| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN（gate/probe 的 provider 调用属既有授权机制） |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 依赖与下游
- **上游**：WP-18（`3d50ab7`）、WP-19（`d587992`）均已 MERGED。base_commit = `c86b35c`。
- **下游**：WP-20 合并后，consumer-repo WP-39 跑 **Run 3**（用含本容忍补丁的 runtime
  重跑 WP-34 native gate 取第二签名）。WP-20 不含任何消费方仓改动。

## 复现与运行备忘（供新 session）
- 合并 runtime 源：`/Users/admin/vibe/agentic-loop-main-codex-merge/src`（main，
  当前 `c86b35c`）；本 WP 在其隔离 worktree 实现（option B 直接实现亦可，需在 status
  记 `deviation_from_dispatch_form`，同 WP-18/19——因 agentic-loop 主 checkout
  `/Users/admin/vibe/agentic_loop` 被另一会话占用，`agentic preflight` 会解析到它）。
- gate 运行形态（Run 3）：
  `PYTHONPATH=<merged>/src python3 -m agentic_loop.gate <jst>/docs/wp/WP-34.status.json`
  环境需 `DEEPSEEK_API_KEY`（从 `~/.zshrc` source，绝不回显）、`CODEX_HOME=~/.codex`。
- 真实事件探针命令（复现良性告警）见 Run 2 诊断：`codex exec --ignore-user-config
  -c model_provider=deepseek … -c model=deepseek-v4-pro -c model_reasoning_effort=high
  --json -`，观察 `item.type=="error"` 的 fallback-metadata 告警。
- 测试运行：`/opt/anaconda3/bin/python3 -m pytest tests/<file> -q -o addopts=""`
  （全仓 `tests/` 因真实子进程测试会超时，按文件或后台跑；`test_finalize_merge_triple_sign.py`
  的 4 个失败是既有 git-env baseline，与本 WP 无关）。

## 附注
- 本 WP 是 WP-18/19 同族的 finalization 硬化补丁，边界严格限定在
  `_validated_final_message` 的容忍逻辑 + 新测试，不重开已冻结的裁决/协议/切分面。
- 不得在本 WP 内手工补写 WP-34 的第二签名——签名必须来自真实 native gate（WP-39 Run 3）。

# WP-17: Codex 评审通道配置隔离与大 diff 分块

> 冻结日期 2026-09-16 | 编排者 Kiro（DeepSeek Harness）| 执行者 kimi
> 所属 Plan：PLAN-CODEX（迭代 2026-09-14-codex-verdict-contract）；集成到 `git.base_branch`，不直接合入 main。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）
让 `CodexAdapter.review()` 的每次 codex 调用与用户级 `~/.codex/config.toml`（hooks + MCP）隔离，并在 diff 过大时按文件边界分块评审、保守聚合，从而在被污染的配置和网关单请求体量上限下仍能稳定拿到 fail-closed 的结构化 verdict。

## 事件证据（2026-09-16 实测，根因已钉死）
消费方 harness-architecture 迭代的 WP-34（发布治理门禁，diff 8344 行 / 388KB）在 P2 high-effort native gate 下反复产不出 verdict。受控实验确证两个 WP-16 未覆盖的根因：

1. **配置污染**：`~/.codex/config.toml` 被 Claude Code 同步器写入 `features.hooks=true` + 注册的 session_start / pre_tool_use / stop(ralph-loop) / permission_request hooks + 多个 MCP servers。`codex exec` 继承后陷入 hook / 工具调用循环，产不出 verdict。对照实验：196B prompt 侥幸直接作答成功；25KB 起触发 agentic 行为后卡在 hook 循环 timeout。加 `--ignore-user-config` 后：25KB / 142KB 均正常落盘结构化 verdict（provider 参数本就靠 `-c` 显式注入，auth 走 CODEX_HOME，不依赖 config.toml）。
2. **网关体量上限**：干净配置下 398KB 单请求返回 `tokens used 0`（网关拒绝）；142KB 可正常处理。大 diff 的 verdict 无法一次拿到，需分块。

本 WP 修 adapter / provider 契约，不修消费方 WP，也不改其 verdict。

## 范围
- **allowed_paths**（白名单）：
  - `src/agentic_loop/adapters/codex.py`
  - `tests/test_codex_config_isolation_chunking.py`（新增）
- **forbidden_paths**（黑名单）：
  - `.env`
  - `.context/`
  - `.agentic/config.toml`
  - `src/agentic_loop/gate/`
  - `src/agentic_loop/wrappers/`
  - `src/agentic_loop/independence.py`
  - `tests/test_codex_verdict_recovery.py`（WP-16 所有，不得改动）
  - 一切消费方仓库与未显式允许的文件
- **owner 边界**：仅 adapter 实现及其新增聚焦测试模块。

## 输入
- 上游：WP-16（空/非法 verdict 有界恢复，已 MERGED）——本 WP 的隔离与分块必须与其两次调用恢复逻辑正交兼容。
- 参考：PLAN.md 冻结产品决策 1-7（fail-closed 不可削弱）。

## 交付物清单
- [ ] `src/agentic_loop/adapters/codex.py` — 配置隔离 + 分块评审
- [ ] `tests/test_codex_config_isolation_chunking.py` — 确定性单测

## 必需行为（Required behavior）
1. **配置隔离**：每一次 codex exec 调用（首评、空输出重试、structure-only 归一化、探针 probe_injection 除外可选）都必须携带 `--ignore-user-config`，与既有命令契约共存（同 provider `-c` 注入、`--sandbox read-only`、`--skip-git-repo-check`、精确 reasoning effort、`--output-schema`、`-o`，key 值绝不入 argv）。隔离后 auth 仍由 CODEX_HOME 提供，provider/base_url/wire_api 仍由显式 `-c` 注入。
2. **分块阈值**：当单次 review 的完整 prompt（brief + diff，UTF-8 字节）超过一个具名可配置常量（建议默认 ~150KB，命名如 `_CHUNK_PROMPT_MAX_BYTES`；低于该值走原单次路径，行为不变）时，进入分块评审。
3. **按文件边界分块**：diff 按 `diff --git` 文件边界切分；任一单文件 diff 仍超阈值时，在 hunk（`@@`）边界内继续二次切分；分块只切 diff，绝不改写 diff 内容。
4. **每块全局上下文摘要**：每块 prompt 必须附一个全局摘要——本 WP diff 涉及的完整文件清单 + 本块所含文件/片段在其中的角色定位——使 codex 理解跨文件关系；摘要为只读上下文，不得替代或篡改被审 diff。
5. **保守 fail-closed 聚合**：逐块用既有单次评审路径（含 WP-16 恢复逻辑）拿结构化 verdict；聚合规则——任一块为 REWORK → 整体 REWORK；否则任一块为 CONSULT → 整体 CONSULT；仅当所有块均 ACCEPT → 整体 ACCEPT。聚合 verdict 的 findings 合并全部块的 findings。任一块无法拿到合法 verdict（两次调用后仍空/非法/非零）→ 整体 fail-closed 抛错，绝不降级为 ACCEPT。
6. **不引入自然语言映射**：聚合是对结构化 decision 的确定性规约，不得引入任何自由文本→decision 的关键词/正则映射。
7. **保留既有语义**：probe / identity / capabilities / provider injection / prompt review-policy / WP-16 的两次调用恢复契约全部不变。分块路径内每块仍复用 WP-16 的恢复逻辑与独立 answer 文件。

## 完成定义（DoD）
- [ ] 交付物逐项就绪
- [ ] targeted 单测 + `python3.11 -m pytest tests -q` 全绿（baseline 例外须在冻结基线复现并记录，绝不隐藏）
- [ ] `agentic quality-gate <status.json>` 全绿
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范

## 风险声明
| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注
- 已知陷阱：单测必须用 fake 可执行 / mock subprocess，绝不真调 codex 或网络；断言 argv 含 `--ignore-user-config`、分块聚合的 fail-closed 语义。
- 口径权威源：PLAN.md 冻结决策 1-7；WP-16 恢复契约（codex.py 现有 review()）。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），内容与上文中文章节同义，非另一份口径。

## Acceptance tests

新增 `tests/test_codex_config_isolation_chunking.py`，用确定性 fake 可执行 / mock subprocess 证明（每条负面断言提供三项 oracle 证据：正向可达对照、原因特异 witness、代表性禁止变异转红）：

- **隔离**：每次 codex exec 的 argv 都含 `--ignore-user-config`，且既有契约标志（provider `-c` 注入、`--sandbox read-only`、`--skip-git-repo-check`、effort、`--output-schema`、`-o`）全部保留，key 值不在 argv。禁止变异：删去 `--ignore-user-config` 使测试转红。
- **阈值下界**：prompt ≤ 阈值时走单次路径，仅一次调用，行为与 WP-16 一致（正向可达对照）。
- **分块触发**：prompt > 阈值时按文件边界分块，块数 = 文件数（或 hunk 二次切分后的片数）；每块 prompt 含全局文件清单摘要且含本块 diff、不含其它块 diff。
- **保守聚合**：全 ACCEPT→ACCEPT；含一个 REWORK→REWORK 且 findings 合并；含一个 CONSULT（无 REWORK）→CONSULT；某块两次调用后仍空/非法→整体 fail-closed 抛错（原因特异 witness），绝不 ACCEPT。禁止变异：把聚合改成"多数决"或"任一 ACCEPT 即 ACCEPT"使测试转红。
- **无第三通道**：分块聚合不得绕过 `_parse_verdict()` 白名单；无自由文本→decision 映射（static killer）。

运行：
- `python3.11 -m pytest tests/test_codex_config_isolation_chunking.py tests/test_codex_verdict_recovery.py tests/test_adapter_injection.py -q`
- `python3.11 -m pytest tests -q`（baseline 例外须在冻结基线复现并记录）
- `python3.11 -m compileall -q src/agentic_loop tests/test_codex_config_isolation_chunking.py`
- `git diff --check`
- `agentic quality-gate <status.json>`

## Allowed and forbidden paths

机器 status 的 `scope` 为权威，与上文「范围」一节完全一致：只能改 allowed_paths（`src/agentic_loop/adapters/codex.py`、新增 `tests/test_codex_config_isolation_chunking.py`），绝不碰 forbidden_paths（含 WP-16 的 `tests/test_codex_verdict_recovery.py`、`gate/`、`wrappers/`、`independence.py`、`.agentic/config.toml`、`.env` 及一切消费方仓库）；owner 边界对齐 CODEOWNERS。

## Completion definition

与上文「完成定义（DoD）」同义，非另一份口径：必需行为与 killers 全通过、无 forbidden 路径改动、无网络/生产写入/通知/凭据读写/推送，status 如实记录证据与 commit，仅在测试通过后置 READY_FOR_REVIEW。

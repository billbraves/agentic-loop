# WP-19 rev5 咨询记录（codex）

> 触发时间 2026-09-15 ｜ 提问者 claude（编排者）｜ 咨询者 codex（provider: kirogpt）
> 提交 `77941f4`（基线 `15d8137`）｜ 依 `CLAUDE.md` 落盘于迭代目录。

## 触发理由

rev5 闭合 A29（判据对任意输入不抛异常）。编排者独立验收判 ACCEPT，
但双签门禁要求 codex 独立 verdict；且 rev4 的 consult 会话中断、未产出 verdict，
不计为 ACCEPT 也不计为 REWORK，故 rev5 必须重新取得有效 verdict。

## 派发历程（三次失败一次成功，均留痕）

| 尝试 | 命令形态 | 结果 |
|------|---------|------|
| 1 | `codex exec --sandbox read-only -m kirogpt` | **EXIT=1**，HTTP 400：三个 `mcp__codex_apps__*` 工具名超过 Kiro API 64 字符上限，请求在推理前即被拒 |
| 2 | 追加 `-c 'mcp_servers={}'` | **EXIT=1**，同一 400。涉事工具名由 `apps` feature 服务端注入，不来自 `~/.codex/config.toml`，清空 `mcp_servers` 无效 |
| 3 | 追加 `--disable apps` | **EXIT=0**，400 消失，codex 真正开工（读判据全文、`finalize_merge.sh`、测试文件，用 mock 复现四种 git 输出），但最终消息为空、**无 verdict**；日志尾部为 `codex_models_manager: failed to refresh available models`（与 rev4 中断同因） |
| 4 | 同 3，prompt 明确「上次未给结论，本次请直接给 verdict、不要再长时间探查」，并附 A30 定性 | **EXIT=0，取得有效 verdict** |

> 记法：`--disable apps` 是本仓咨询 codex 的必要参数（缺陷 A31 候选：
> 咨询命令形态未固化，编排者每次自行摸索）。

## codex 结论

**`[VERDICT] REWORK`**

| 级别 | 内容 |
|------|------|
| P0 | **无**。A29-1、A29-2 实现修复成立；未发现正常 `Path` 输入仍可从索引、路径拼接、最终 `resolve()` 或比较处逃逸 |
| P1 | **A30 阻断本轮 ACCEPT**。`test_long_path_fails_closed_without_raising` 在受支持的 Python 3.14 上错误地强制断言 `True`；此时路径可正常分类，主仓返回 `False` 才符合语义。**当前提交会在声明支持的解释器上产生新增测试失败** |
| P2 | 超长路径用例应改为确定性触发 `is_dir()` 抛 `OSError` 并断言 fail-closed；若保留真实超长路径，只应锁「不抛异常并返回 bool」，不能锁跨版本不稳定的异常路径 |
| P2 | `finalize_merge.sh` 命令替换 fail-open 仍是系统性风险，但已明确排除在本 WP 范围外且另立 WP，**不否定 A29 判据修复本身**；后续 WP 应作为高优先级完成 |

### `[RATIONALE]`（原文摘）

> 三处 `(OSError, RuntimeError, ValueError)` 是同一函数内统一的异常策略，不是三份业务口径；
> 权威实现仍只有 `path_is_in_worktree` 一处。A28-1 的双空行检查仍独立生效，
> 没有被大范围 `try` 吞掉；A22 环境净化、A27 先 resolve 再探测及主仓/worktree
> 基本语义均未回归。NUL 用例准确锁住契约，但超长路径用例锁住了 Python 3.11–3.13
> 的实现表现，并在项目明确支持的 Python 3.14 上失败，因此当前提交不能 ACCEPT。

这直接回答了编排者问的第 2、3、6 问：三处同形 except 不算三份口径；
A28-1 未被吞；fail-open 留到下一个 WP 可接受，不否定本轮修复。

## 编排者独立核实

A30 由 codex 在复审中主动跨版本探查发现。编排者**不依赖其报告**，直接用四个解释器
实测（真实临时仓 + `git worktree add`，复现用例 fixture 形态）：

| Python | `Path(300字符).resolve().is_dir()` | 主区超长路径判据 | linked worktree 内超长路径 | 用例断言 `is True` |
|--------|-----------------------------------|----------------|--------------------------|------------------|
| 3.11.14 | `OSError: [Errno 63]` | `True`（fail-closed） | `True` | ✅ |
| 3.12.14 | `OSError: [Errno 63]` | `True` | `True` | ✅ |
| 3.13.12 | `OSError: [Errno 63]` | `True` | `True` | ✅ |
| 3.14.2 | **`False`（不再抛）** | **`False`** | `True` | ❌ |

`pyproject.toml:8` 声明 `requires-python = ">=3.9"`，3.14 在支持范围内。
四个版本上判据「对任意输入都不抛」全部成立，主区判 False、linked worktree 判 True
全部正确——**A29 本身闭合无疑**，问题只在用例断言。

## 编排者的判断更正

编排者原把 A30 定性为「缺陷在用例，不在 A29 修复，故另立 WP，本轮仍可 ACCEPT」，
并已据此写下 `review.decision=ACCEPT`。**该处置错误，现予更正。**

定性部分（缺陷在用例、不在修复）经四版本实测成立，codex 亦未反对；
但**处置结论错**：A30 与 A26、A29 修法 2 不同——后两者落在 forbidden path，
本轮无权限修；A30 落在本轮**白名单文件** `tests/test_worktree_detection.py`，
且是**本轮自己新增的那一行断言**。把它推给下一个 WP，等于让 `77941f4` 带着
一个在声明支持的解释器上失败的新增用例进入合并候选。codex 的 P1 成立。

→ 编排者撤回 rev5 的 ACCEPT，改判 **REWORK**，转 rev6：只改断言，不动判据。

## 采纳决定（编排者）

| codex 条目 | 处置 |
|-----------|------|
| P0 无 | 采纳。A29 判据修复确认闭合，rev6 **不得再动** `path_is_in_worktree` |
| P1 A30 阻断本轮 | **采纳**，撤回自己的 ACCEPT，转 rev6 |
| P2 用例改法 | **采纳**：断言改为「不抛异常且返回 bool」，并补一条 linked worktree 内超长路径判 `True`（四版本均稳定） |
| P2 fail-open 高优先级 | 采纳。任务 #4 已在册，标记为高优先级 |

## 另附：codex 只读边界的一处越界（缺陷候选）

codex 以 `--sandbox read-only` 运行，但其 serena MCP 工具在执行者 worktree
`/Users/admin/vibe/wp19-wrapper-seams` 留下未跟踪目录 `.serena/`
（`project.yml`、`project.local.yml`、`.gitignore`）。主仓无此目录，
`.gitignore` 与 `.git/info/exclude` 均无 `serena` 规则。

违反 §5.7：审核者应只读，不应在执行者工作区留下任何写入面。
编排者未删除该目录（留作证据），登记为缺陷候选，另立 WP 处置
（修法方向：咨询 codex 时同时 `--disable` serena，或把 `.serena/` 写进
`.git/info/exclude`）。

# 迭代 2026-10-18-provider-binding-validation

> Plan：PLAN-01 | 集成分支 `plan/2026-10-18-provider-binding-validation` | 目标 `main`
> 冻结日期 2026-10-18 | 编排者 claude-code

## 这个迭代解决什么

kimi 适配器现在靠 `getattr(b, "openai_base_url", None) or b.anthropic_base_url`
取注入用的 base URL。当配置只声明 `anthropic_base_url`（本仓
`providers.deepseekflash` 正是如此）时，它会**静默**把 `/anthropic` 端点写进一个
`type = "openai_legacy"` 的 provider 块——产出一个语法合法、语义错误的配置，
故障要到派工时才以 `LLM not set` 之类看不出真因的方式暴露。

缺口是「校验的字段」与「适配器实际使用的字段」不一致。修法是把校验挪到
binding 构造期对**真正会用到的字段**做 fail-closed，并让适配器不再回退。

## 为什么需要 WP-01

`origin/main` 在本机有 4 个既有失败（`test_finalize_merge_triple_sign.py`），
根因是宿主 `init.defaultBranch=master` 而测试硬编码 `main`。基线不绿时，
后续 WP 的「全绿」无法区分真回归与既有失败，所以先用一个最小 WP 把它转绿。

## 基线依赖（重要）

本迭代的集成分支切自 `fix/tool-fixes-2026-10-14`（= `origin/main` + 两个已验证
提交），因为 `openai_base_url` 缺口**只在该 kimi 修复之上才存在**——main 上
kimi 仍走 anthropic 端点，校验是自洽的。

| 依赖分支 | 状态 |
|---|---|
| `fix/tool-fixes-2026-10-14` | 本地已验证（1082 passed 等价于其基线），推送因网络未完成 |

该分支落地到 `main` 后，本迭代分支需 rebase 到 `main` 再收敛。

## Work packages

| WP | 主题 | 状态 |
|---|---|---|
| WP-01 | 固定 triple-sign 测试初始分支，基线转绿 | READY_FOR_REVIEW · codex ACCEPT |
| WP-02 | kimi base_url 校验 fail-closed，禁止静默回退 | READY_FOR_REVIEW · r1 REWORK，返工已提交，r2 待重跑 |
| WP-03 | 表格式角色渲染成 adapter 名，修复契约漂移 | READY_FOR_REVIEW · codex ACCEPT |

## 明确不在本迭代范围

- `agentic quality-gate` 的分支配置预览（`--config-from <ref>` / `--explain`）：
  配置来源的架构问题，另开迭代。
- `agentic gate` 硬编码 `{wp_id}-brief.md`（`gate/__init__.py:979`）：re-freeze
  支持的一部分，另开迭代。
- **pre-push 钩子在 linked worktree 下漏读状态**（下一轮迭代候选，已登记）：
  `src/agentic_loop/templates/pre-push.tmpl:53` 在包可导入时调用
  `_iterations_dir()`，而 `resolve_paths.py:305` 返回主仓目录，于是漏掉当前
  worktree 的状态并输出 `PRE_PUSH_SKIP`。在 `origin/main` 与集成分支均可复现，
  **不是本迭代引入**；但它是真实的门禁盲点——推送时的 WP 门禁在工作树里会
  静默跳过，不能当作「已通过」。codex 在 r1 明确指出不得以「环境问题」消解它。
- 旧 plan 分支 `plan/2026-09-22-framework-hardening` 的收尾：已决定弃用归档，
  tag `archive/plan-2026-09-22-framework-hardening`。

## 收敛方式

全部 WP 到 `MERGED` 后，`agentic plan merge` 单次 `--no-ff` 合入 `main`，
一次推送。不做 N 个独立合并。

## 当前进度与下一步（供新 session 恢复）

plan 分支从未推送。工作树：`/Users/admin/vibe/.worktrees/pbv-plan`。
基线分支 `fix/tool-fixes-2026-10-14` 已推送到 origin（`5bd90b5`），
因此**基线那两个提交不可再重写**。

已完成：

- WP-01（`71c0658`）、WP-03（`3cdd101`）获 codex ACCEPT，且在历史重写后
  由 codex 用内容比对＋复跑重新建立依据，不是换填 SHA。
- WP-02 经三轮返工：`d0f1bf6`（钉原因与脱敏）、`eb2947c`（改等式断言、
  覆盖两种输入形态）、`5dbc0b8`（补 adapter 路径）。每轮都有变异转红证据。
- 提交纪律按 §4.3 重整，`plan lint` 仅剩合并前应有的 `finalize commit x0`。
- brief 口径残留清理（`f4c4f5a`）、WP-03 `base_commit` 修正为 `9d943b8`。

**唯一阻断项**：WP-02 在 `5dbc0b8` 之后没有独立判决。codex 的 r3 在产出判决前
配额耗尽（见 `PLAN-01-consult-codex-review-r3.answer.md`），它中断前已确认
r2 变异被杀死，并提出了 adapter 路径这个新阻断发现。

下一步：

1. codex 配额恢复后跑 **r4**，评审对象 `5dbc0b8`。r4 必须回答两件事：
   WP-02 的判决，以及**是否应按 AGENTS.md §7 升级为 CONSULT**——同一类缺陷
   （错误消息未被钉死）已在三个不同位置被连续三轮发现：provider_binding
   只断言异常类型、provider_binding 子串断言且只覆盖一种形态、adapter
   子串断言且无 canary。r1~r3 的 REWORK 在 r4 出结论前仍是最新已记录决定。
2. 判决齐备后 `agentic plan merge` 单次 `--no-ff` 合入 `main`，
   再 `agentic plan finalize` 把 status 折叠进单个 finalize 提交。
3. status 文件的当前改动**故意不提交**（§4.3：决策累积到工作树，在 finalize
   提交里一次落地）。这也是 `agentic plan check` 读主仓副本时报
   `IMPLEMENTING` 的原因，不是状态记录错误。此前每个提交的
   `validate_wp_status` 均通过（codex r2 逐提交验过 21 份快照）。

### 下一轮迭代候选（本轮登记，不在本轮范围）

- pre-push 钩子在 linked worktree 下漏读状态（详见上文「不在本迭代范围」）。
- **错误消息不变式缺少结构化保障**：本轮三处同形缺陷说明，没有共享 helper
  或 lint 来强制「报错消息按等式钉死且断言 canary 不出现」，第四处仍可能
  复发。已记入 WP-02 status 的 risks。

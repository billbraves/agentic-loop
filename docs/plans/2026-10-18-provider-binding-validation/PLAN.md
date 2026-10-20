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
| `fix/tool-fixes-2026-10-14` | 已合入本地 `main`（`--no-ff` merge `c91cf0f`，978 passed / 4 skipped）；推送因网络未完成 |

用户裁决（2026-10-20）：先落基线，再合 `main`。基线已作为一次 `--no-ff`
合并进入本地 `main`，随后把 `main` 合入本迭代分支（merge `5d1caca`），
而不是 rebase——rebase 会重写 WP-02/03 已获 codex 签名的提交 SHA。合并后
plan 分支全套 998 passed / 4 skipped。

## Work packages

| WP | 主题 | 状态 |
|---|---|---|
| WP-01 | 固定 triple-sign 测试初始分支，基线转绿 | BLOCKED · 已弃用；main `3955529` 用更优方案修复同一问题 |
| WP-02 | kimi base_url 校验 fail-closed，禁止静默回退 | MERGED · codex r5 ACCEPT（`b01dfd2`），finalize 记录 `merged_commit=5d1caca` |
| WP-03 | 表格式角色渲染成 adapter 名，修复契约漂移 | MERGED · codex r5 ACCEPT（`3cdd101`），finalize 记录 `merged_commit=5d1caca` |

WP-02/03 是顺序布局（`git.branch == git.base_branch`），`merged_commit` 即
集成分支尖端；两个 WP 各自的实现提交都在该分支的 first-parent 历史上。

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

## 当前阻断项：WP-02 已按 §7 升级为 CONSULT，等用户裁决

codex r4（完整跑完，见 `PLAN-01-consult-codex-review-r4.answer.md`）判：

| WP | 判决 | 提交 |
|---|---|---|
| WP-01 | ACCEPT | `71c0658` |
| WP-02 | **CONSULT** | `5dbc0b8` |
| WP-03 | ACCEPT | `3cdd101` |

r1~r3 的全部历史变异现在都被拦住。但 r4 发现**真实空字符串未覆盖**：两个
模块都把「声明但为空」建模为 `None`，而 TOML 的自然空值是
`openai_base_url = ""`；把 `not value` 改成 `value is None` 可放行空字符串，
27 例仍全绿（编排者已独立复现）。**未变异的代码会正确拒绝空字符串，所以这是
验收覆盖缺口，不是已泄漏凭据。**

codex 拒绝开第四轮 REWORK，理由是三轮修复都只在上一条变异周围局部打补丁，
没有系统覆盖「错误原因 × 输入形态 × 诊断路径」三个维度。归因：
**(a) 测试设计问题是直接原因，(b) 实现者兼审核者是促成因素，
(c) 对抗审核确实在起作用，但不能据此无限续跑返工。**

可延期 / 不可延期的区分（codex 明确）：共享 helper/lint **可以延期**；
空字符串覆盖缺口与本次 §7 裁决**不可延期**。

### 用户裁决（已给出）

**补空字符串覆盖后收尾。** 已在 `b01dfd2` 落地：provider_binding 的形态从
两种扩为三种（`declared_none` / `declared_empty` / `absent`），其中
`declared_empty` 从真实 TOML 解析而非手写 `""`，另加一个 fixture 自检测试
防止该形态静默失效；adapter 侧的 `None` 与 `""` 也都参数化。

codex r4 的四个空字符串变异全部转红（2/2/1/1，修复前均 27 全绿），
r1~r3 历史变异检出数普遍上升（6/3/2/2/2）。
quality-gate PASS，928 passed / 4 skipped。

**但这些是编排者自测，不是独立签名。** r5 第一次尝试在配额耗尽前未产出判决
（`PLAN-01-consult-codex-review-r5.answer.md`），配额恢复后完整跑完 r5b
（`PLAN-01-consult-codex-review-r5b.answer.md`），判决见下。

### r5b 判决（已完成）

| WP | 判决 | 提交 |
|---|---|---|
| WP-01 | ACCEPT（实现已弃用） | `71c0658` |
| WP-02 | ACCEPT | `b01dfd2` |
| WP-03 | ACCEPT | `3cdd101` |

r5b 同时判定 PLAN.md 的 rebase 前置条件阻断收敛。该条件已按用户裁决改写为
「基线先落 `main`，再把 `main` 合入迭代分支」并执行完毕（见「基线依赖」）。
WP-01 的实现因 main `3955529` 的更优修复而弃用，不计入本 plan 的
`work_packages`；其 status 置 BLOCKED，保留 codex ACCEPT 记录。

## 收敛顺序（§4.3 原文顺序，re-freeze r4 修正）

codex r4 指出原文把 `plan merge` 写在 WP finalize 之前，顺序错误。正确顺序：

1. 每个 WP 各自满足签名与证据要求，再 `agentic finalize <wp.status.json>`
   到 `state=MERGED`（status-only，不碰 git）。
2. 全部 WP 到 `MERGED` 后，plan 置 `READY_TO_MERGE`。
3. `agentic plan check` / `plan lint` 只读确认。
4. `agentic plan merge` 单次 `--no-ff` 合入 `main`。
5. `agentic plan finalize` 盖 plan 级 `MERGED` + `merged_commit`。
6. 人工批准后推送一次（`push` 是硬 `always_stop`）。

另两项 r4 指出的待办，已在 finalize 提交中处理：

- 冻结版 WP-03 status 的旧 `base_commit=480fb80` 已折叠为 `9d943b8`。
- WP-01/03 的 `evidence.tests` 已补齐，满足 finalize 的非空证据要求。
- 基线 `5bd90b5` 已经由 `c91cf0f` 进入本地 `main`，满足 PLAN 的基线前置条件。

### 签名归属（r4 纠正，已落到三份 status）

此前我把 codex 的判决记在 `review` 字段，归属错误。validator 与
`finalize_merge.sh` 都支持 `review.decision = "N/A"` 的专用路径，注释明确
写着它就是为「实现者兼审核者」这个冲突准备的。现已改为：

- `review.decision = "N/A"`，并记明 claude 同时是实现者、无法自审；
- `consult` 记录真实 codex 会话与结论：WP-01/03 为 ACCEPT，WP-02 为 CONSULT；
- r3 保留「部分发现、无正式判决」，不补造正式 REWORK；
- 不把同一次 codex 审核复制成两份 ACCEPT。

status 文件的当前改动**故意不提交**（§4.3：决策累积到工作树，在 finalize
提交里一次落地）。这也是 `agentic plan check` 读主仓副本时报 `IMPLEMENTING`
的原因，不是状态记录错误。此前每个提交的 `validate_wp_status` 均通过
（codex r2 逐提交验过 21 份快照）。

### 下一轮迭代候选（本轮登记，不在本轮范围）

- pre-push 钩子在 linked worktree 下漏读状态（详见上文「不在本迭代范围」）。
- **错误消息不变式缺少结构化保障**：本轮三处同形缺陷说明，没有共享 helper
  或 lint 来强制「报错消息按等式钉死且断言 canary 不出现」，第四处仍可能
  复发。已记入 WP-02 status 的 risks。
- **codex 调用路径仍只断言异常类型**：r4 判为可延期的既有债务；本轮不改，
  待后续迭代补上「错误消息按等式钉死 + canary 不存在」的断言。

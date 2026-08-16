# agentic-loop 快速上手（中文）

> 面向要在一个新项目里落地 `agentic-loop` 编排闭环的同事。
> 目标闭环：**迭代计划 → 工作包(dispatch) → 实现 → 独立评审 → 合并(finalize)**，
> 全程由机器可读的 status 文件驱动，质量门与独立签名在安全边界内自动执行、审批最小化。

---

## 0. 一句话

`agentic` 是一个"派发→实现→评审→合并门"的编排引擎：它不写业务代码，只负责
**验证工作包状态、跑质量门、做多签独立评审、锁并发、终态留痕**。所有门通过一个
`agentic` 命令转发到内置的 bash wrapper（外部项目无需自带 `scripts/agentic/`）。

### 0.1 它和 Claude Code SKILL / DeepSeek Harness 的区别

三者不是竞争，是**不同层面、可叠加**：

| 工具 | 层面 | 解决什么问题 |
|------|------|-------------|
| Claude Code **SKILL** | 方法 | 让**一个** agent 把某类任务做对 |
| DeepSeek **Harness** | 运行时 | 让**一个** agent 执行、并行派子任务 |
| **agentic-loop** | 治理 | 让**一群**独立 agent 协作时不失控 |

**一句话**：SKILL / Harness 让单个 agent **更能干**；agentic-loop 让一群 agent
协作时**更可信**——前者解决「能力」，后者解决「纪律」（谁改的、谁审的、出界没、
怎么合并、怎么留底，机器强制记录和拦截）。

**工地类比**：SKILL 是工人的工种手册，Harness 是工具箱+派工系统，agentic-loop
是工地的**监理+验收制度**——独立工作区（worktree）、划死边界（allowed/forbidden）、
多签验收（review+consult）、终态留底（MERGED+commit）。

---

## 1. 安装 / 更新（默认最新，一条命令）

```bash
# 默认装/更新到最新（不加 @tag = 跟踪 main，--force = 强制更新）
uv tool install "git+https://github.com/billbraves/agentic-loop.git" --force

# 或写进 ~/.zshrc 后一个短命令
agentic-up

# 冒烟验证
agentic --help
agentic contract check --dir /path/to/project   # 未 init 前应报「no .agentic/config.toml」
```

> 要锁版本（可复现）：`uv tool install "...@v0.8.4" --force`。

> Python >= 3.9 即可；3.11+ 零第三方依赖，3.9/3.10 会自动拉一个 `tomli`。

### 1.1 谁需要装、谁不用装

`agentic` 是**用户级 CLI，装一次全局可用**（`~/.local/bin/agentic`），与仓库无关、
不用每个项目装一遍。但只有**编排者角色**需要它：

| 角色 | 需要装 `agentic` 吗 | 原因 |
|------|:---:|------|
| 编排者（claude，驱动闭环的人） | ✅ 必须 | 跑 `preflight`/`dispatch-lint`/`health`/`gate`/`finalize`/`lock` 等编排门 |
| 执行者（kimi，被派发到 worktree 干活） | ❌ 不用 | 只读 brief、实现、跑测试、交证据，不碰编排门 |
| 独立评审/顾问（codex / qoder） | ❌ 不用 | 评审在独立会话看 diff、给 verdict；门由编排者触发 |
| 只读协作同事 | ❌ 不用 | 读 `AGENTS.md` + status 文件即可对齐 |

> 团队若只有一个编排者（或由 CI runner 担任），那只有那一台机器/那个人装。

**仓库内一键就绪脚本**（把"装"降到 clone 后跑一条命令）：

```bash
bash scripts/agentic-bootstrap.sh
# 内部 = uv tool install ... --force（默认跟踪 main=最新）+ agentic --help 冒烟 + bootstrap --dry-run
```

手动等价执行：

```bash
uv tool install "git+https://github.com/billbraves/agentic-loop.git" --force
agentic --help && agentic bootstrap --dry-run
```

> 注意：CI（`.gitlab-ci.yml`）已经在远端跑大部分质量门（formula/collision/reachability、
> score.py 等）。本地 `agentic` 的独特价值是 CI 覆盖不到的部分——WP 并发锁、后台执行器
> 冻结监控、多签独立评审 + 终态 stamp。别把本地 CLI 当成"再跑一遍 CI 测试"。

### 1.2 配置 DeepSeek API key（统一几个 CLI 生效）

让 claude / kimi / codex 三签统一走 DeepSeek，需要两步：

**① 设环境变量（key 只存环境变量，绝不落盘/进 argv）**

```bash
export DEEPSEEK_API_KEY=sk-...
```

**② 在 `.agentic/config.toml` 配 `[providers.deepseek]` + roles 绑 provider**

`agentic init` 生成的 config 里已带注释范本，取消注释即可（完整范本见
`examples/config.single-deepseek.toml`）：

```toml
[providers.deepseek]
anthropic_base_url = "https://api.deepseek.com/anthropic"   # claude/kimi 用
openai_base_url    = "https://api.deepseek.com/v1"          # codex 用
api_key_env        = "DEEPSEEK_API_KEY"                     # 只存 env 名
identity_model     = "deepseek-v4-pro"
[providers.deepseek.selectors]
kimi   = "deepseek/v4-pro"
codex  = "deepseek-v4-pro"
claude = "deepseek-v4-pro"

[roles]
developer   = { adapter = "kimi",   provider = "deepseek" }
reviewer    = { adapter = "claude", provider = "deepseek" }
consultant  = { adapter = "codex",  provider = "deepseek" }
```

> 配好后再跑 `agentic bootstrap`，它会**真实注入探测**每个 CLI 是否真的走通了
> DeepSeek（不是 `which` 命中就过，是发 sentinel 请求验证）；不配 `[providers]`
> 则三签回退各 CLI 自己的默认 provider，不需要 DeepSeek key。
>
> 兼容性注记：DeepSeek 的 `/v1` **同时**挂了 `/v1/chat/completions` 和
> `/v1/responses` 两个端点（已 curl 实测 HTTP 200）。codex ≥ 0.147 走 Responses
> API（`/v1/responses`），DeepSeek 的端点确实存在——但 **codex 对 inline/自定义
> provider 不会自动选 responses 协议**，必须显式声明 `wire_api = "responses"`
> （独立 profile 在 config 里写；agentic 注入时用
> `-c model_providers.<name>.wire_api=responses`，已内置）。另外 responses 档
> 官方优先保证 `deepseek-v4-flash`，`-pro` 可用（curl 实测 HTTP 200）但官方
> 承诺优先级较低。

### 1.3 官方 key 可保留 + 一键切换兜底

agentic 的 DeepSeek 是**运行时注入**，只在 agentic 派发（gate/redispatch/评审）时生效，
**不碰**各 CLI 自己的官方配置——你手动跑 `claude`/`codex`/`kimi` 时仍走各自官方 key。

两者并存、互不干扰：

| 场景 | 用什么 key |
|------|-----------|
| agentic 派发/评审 | DeepSeek（`[providers]` 注入） |
| 手动跑 `claude`/`codex`/`kimi` | 各自官方 key（`~/.codex`、`~/.kimi` 等） |

当 codex/kimi 官方 key 撞到限额（如 5 小时 / 星期限额）时，可**一键把手动 CLI 也切到
DeepSeek 兜底**（写进 `~/.zshrc` 后）：

```bash
agentic-provider deepseek         # 三个都切 DeepSeek
agentic-provider official         # 三个都切回官方
agentic-provider codex-deepseek   # 只切 codex（或 kimi-* / claude-*）
agentic-provider status           # 看当前默认 provider
```

不想写进 `~/.zshrc` 的话，直接跑框架仓库里的脚本即可（跨 macOS/GNU 的 sed）：

```bash
./examples/agentic-provider.sh <deepseek|official|codex-deepseek|kimi-deepseek|claude-deepseek|…|status>
```

---

## 2. 环境自检（一次性）

```bash
agentic bootstrap --dry-run   # 只打印安装/探测计划，不装东西、不花 DeepSeek 配额
agentic bootstrap             # 检测/安装 claude+kimi+codex、校验 DEEPSEEK_API_KEY、真实注入探测
```

`bootstrap` 会**失败即闭**：装了但不兼容的 CLI 不会被自动升级，而是报
`CLI_INSTALLED_BUT_INCOMPATIBLE` 让你处理，绝不带着假注入跑后续流程。

---

## 3. 初始化一个项目

```bash
agentic init --dir /path/to/project --non-interactive
# 生成：.agentic/config.toml + AGENTS.md + CLAUDE.md +
#       docs/agentic/OPERATING_MODEL.md + docs/agentic/templates/{STATUS.json,WORK_PACKAGE.md}
#       + docs/plans/ 骨架 + .agentic/locks/（已 gitignore）
```

然后编辑唯一需要你改的文件 `.agentic/config.toml`：

- `[roles]`：orchestrator / developer / reviewer / consultant 映射到哪个 CLI
- `[[gate]]`（kind="command", stage="pre_review"）：**你的**路径→测试命令规则
- `[safety]`：`forbidden_paths`（严禁碰）、`production_paths`（写入受门控）
- `[review_policy]`：`min_independence`（合并门对 reviewer/consultant 独立性的下限）

改完必须重渲染契约，让 AGENTS.md 等跟着 config 走：

```bash
agentic contract check --dir /path/to/project   # 只读；rc 0=全同步，rc 3=有漂移
agentic contract diff  --dir /path/to/project   # 预览重渲染 diff
agentic contract diff --apply --dir /path/to/project   # 写回 + 重新盖章
```

---

## 4. 工作包闭环（核心）

工作包（WP）的状态机：`DRAFT → APPROVED → DISPATCHED → IMPLEMENTING →
READY_FOR_REVIEW → APPROVED_FOR_MERGE → MERGED → RELEASED`（任意活跃态可转 BLOCKED）。

### 4.1 立项 + 派发

1. 从 `docs/agentic/templates/WORK_PACKAGE.md` 复制出 brief，冻结目标/范围/DoD。
2. 从 `docs/agentic/templates/STATUS.json` 复制出 status，填好
   `work_package_id / iteration_id / scope / git`，状态 `DISPATCHED`。
3. 派发前过门（校验 status + 分支/WP 锁）：

```bash
agentic preflight docs/plans/<iteration>/WP-<N>.status.json
agentic dispatch-lint docs/plans/<iteration>/WP-<N>.status.json
```

### 4.2 实现期健康监控

后台派发开发者后，编排者每 ~60s 跑一次测量脚本，按首 token 决策：

```bash
agentic health <status.json> <output-file> <snapshot-file>
# 首 token：PROGRESS（继续等）| FROZEN_<N>m（读 tail 判定卡死）| DONE（进入评审）
```

冻结判据是"输出 tail 哈希 + git dirty 都不变"，不是裸 mtime，避免误杀长推理。

### 4.3 质量门 + 独立评审

```bash
agentic quality-gate <status.json>     # 路径匹配的项目测试规则（来自 [[gate]]）
agentic gate <status.json>             # 合并门第二签名（独立 reviewer）
```

评审结果写进 status 的 `review.decision` / `consult.decision`（ACCEPT/REWORK/CONSULT），
不靠聊天记录。

### 4.4 合并 + 终态留痕

用户批准 `git merge --no-ff` 后：

```bash
agentic finalize <status.json>         # 三签门通过后 stamp state=MERGED + merged_commit
```

---

## 5. 历史状态迁移（legacy → v2）

如果项目之前用的是 `docs/wp/*.brief.md + .wp/WP-<id>.status.json` 那套旧状态
（状态机 `DISPATCHED/IMPLEMENTING/DONE/BLOCKED`），用迁移命令转成 v2：

```bash
agentic migrate-status .wp/WP-22.status.json --iteration <iteration-id> [--merged-commit <sha>]
# 输出 v2 status；DONE 默认 → READY_FOR_REVIEW，加 --merged-commit 则 → MERGED
```

注意：终态需要 `review.decision=ACCEPT + consult.decision=ACCEPT + evidence.tests`
这些旧状态里没有的字段，迁移器会以 WARN 显式提示，**不会伪造证据**。

---

## 6. 命令速查表

| 命令 | 作用 |
|------|------|
| `agentic init --dir <p>` | 脚手架 config + 契约 + 模板 + 骨架 |
| `agentic contract check/diff [--apply]` | 契约漂移检测 / 重渲染 |
| `agentic bootstrap [--dry-run]` | 检测/安装 CLI + 校验 DeepSeek key + 注入探测 |
| `agentic migrate-status <f> --iteration <id>` | 旧状态转 v2 |
| `agentic preflight <status>` | 状态校验 + 分支/WP 锁门 |
| `agentic dispatch-lint <status>` | 派发时状态 lint |
| `agentic quality-gate <status>` | 路径匹配的项目测试规则 |
| `agentic gate <status>` | 合并门第二签名 |
| `agentic finalize <status>` | 三签门 + stamp MERGED |
| `agentic lock …` | WP/合并并发锁 |
| `agentic health …` | 后台执行器进度测量 |
| `agentic redispatch <status>` | REWORK/BLOCKED 重派回流 |

---

## 7. 十分钟冒烟（验证闭环通不通）

```bash
TMP=$(mktemp -d)
agentic init --dir "$TMP" --non-interactive
# 复制 STATUS.json 模板为 WP-1，填 DISPATCHED，跑 preflight：
agentic preflight "$TMP/docs/plans/it-1/WP-1.status.json"   # 应 STATUS_VALID + 锁门过
agentic contract check --dir "$TMP"                          # 应 rc 0 全 IN_SYNC
```

---

## 8. 安全边界（审批最小化的前提）

框架的"尽量少审批"建立在这些**机器强制**的边界上，缺一不可：

- `safety.forbidden_paths` / `production_paths`：越界即 fail，不靠自觉；
- `quality-gate` 首匹配命中、横切门内联：改了哪块跑哪块，改 skills 必过三横切门；
- `min_independence`：合并门强制 reviewer 与 consultant 的身份独立性下限；
- `[[gate]]` fail-closed：项目没定义规则时拒绝放行，绝不"未定义即 PASS"；
- `[autonomy]`：把"哪些动作自动、哪些必须问人"落成机器判定——`agentic autonomy <action>`
  输出 `AUTONOMY_AUTO`/`AUTONOMY_STOP`；`agentic preflight` 强制 `dispatch_developer`、
  `agentic finalize` 强制 `finalize_merge`，`always_stop`（push/生产写入/凭证…）即使
  `ultra` 模式也硬停；
- 终态三签（reviewer + consult + qoder_security）缺一不进 MERGED。

在这些边界内，低风险派发/冻结自动进行；越过边界（生产写入、推送、通知、凭证、不可逆
git）才回到人工审批。

> `[autonomy]` 是**显式 opt-in**：不配该段则门不设防（向后兼容）；配了之后
> `default_mode="ask"`（默认）每个动作都要问，`"ultra"` 才按 `ultra_auto` 列表自动放行。

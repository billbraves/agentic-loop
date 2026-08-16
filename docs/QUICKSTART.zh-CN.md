# agentic-loop 快速上手（中文）

> 面向要在一个新项目里落地 `agentic-loop` 编排闭环的同事。
> 目标闭环：**迭代计划 → 工作包(dispatch) → 实现 → 独立评审 → 合并(finalize)**，
> 全程由机器可读的 status 文件驱动，质量门与独立签名在安全边界内自动执行、审批最小化。

---

## 0. 一句话

`agentic` 是一个"派发→实现→评审→合并门"的编排引擎：它不写业务代码，只负责
**验证工作包状态、跑质量门、做多签独立评审、锁并发、终态留痕**。所有门通过一个
`agentic` 命令转发到内置的 bash wrapper（外部项目无需自带 `scripts/agentic/`）。

---

## 1. 安装（锁版本，可复现）

```bash
# 推荐：锁到某个 tag，重装结果字节级一致
uv tool install "git+https://github.com/billbraves/agentic-loop.git@v0.5.0"

# 冒烟验证
agentic --help
agentic contract check --dir /path/to/project   # 未 init 前应报「no .agentic/config.toml」
```

> Python >= 3.9 即可；3.11+ 零第三方依赖，3.9/3.10 会自动拉一个 `tomli`。

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
- 终态三签（reviewer + consult + qoder_security）缺一不进 MERGED。

在这些边界内，低风险派发/冻结自动进行；越过边界（生产写入、推送、通知、凭证、不可逆
git）才回到人工审批。

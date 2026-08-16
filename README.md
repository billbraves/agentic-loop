# agentic-loop

可移植的 Agent 编排框架（在 baofu monorepo 中自用 dogfood）。

`agentic-loop` 把「派发 → 实现 → 评审 → 合并门」这套跨编码 Agent（Claude / Codex / Kimi / …）的工作流打包成一个引擎。它提供：

- **纯引擎**（漂移 / 独立性 / 状态 / 渲染逻辑）——不含任何业务代码；
- **`agentic` CLI** —— 把命令转发到各编排门，并额外提供面向项目的命令（`init`、`contract` 等）；
- **治理契约模板** —— 从一份小配置按项目渲染生成。

兼容 Python **>= 3.9**，可 vendor 到使用旧解释器的外部仓库。Python **3.11+** 下**零三方依赖**（用标准库 `tomllib`）；**3.9 / 3.10** 只拉一个条件依赖 `tomli`。

## 与 Claude Code SKILL / DeepSeek Harness 的区别

三者是**不同层面、可叠加**，不是竞争：

| 工具 | 层面 | 解决什么 |
|------|------|----------|
| Claude Code **SKILL** | 方法 | 让**一个** agent 把某类任务做对 |
| DeepSeek **Harness** | 运行时 | 让**一个** agent 执行、并行派子任务 |
| **agentic-loop** | 治理 | 让**一群**独立 agent 协作时不失控 |

一句话：SKILL / Harness 让单个 agent **更能干**；agentic-loop 让一群 agent 协作时**更可信**——前者解决「能力」，后者解决「纪律」（范围机器强制、多签评审、合并/终态留痕、动作级审批）。

## 安装（最新发布）

每个发布都会合入 `main` 并打 tag，因此 `main` 永远指向最新发布。**默认装/更新到最新，一条命令**（不加 `@tag` = 跟踪 `main`，`--force` = 强制更新）：

```bash
uv tool install "git+https://github.com/billbraves/agentic-loop.git" --force
```

内置命令升级（任何机器都可用，无需配置）：

```bash
agentic update    # 等价上面那条，重新装最新
```

要锁定精确版本做可复现构建，追加 tag（`@v0.8.8`）或 commit —— 见 [`MIGRATION.md`](MIGRATION.md) §1。

> 手动跑 codex/kimi/claude 想切 provider（官方 ↔ DeepSeek，限额兜底）用
> `agentic-provider`（或 `examples/agentic-provider.sh`），支持全切 + 独立切，见
> [`docs/QUICKSTART.zh-CN.md`](docs/QUICKSTART.zh-CN.md) §1.3。

## 在别的项目里落地

```bash
# 1. vendor / 安装本包（pip-from-git / vendored 见 MIGRATION.md）
# 2. 脚手架：配置 + 治理契约 + 骨架
agentic init --dir /path/to/project
# 3. 编辑 /path/to/project/.agentic/config.toml（角色、质量门、安全边界）
# 4. 重渲染契约以匹配改后的配置
agentic contract diff --apply --dir /path/to/project
# 5. 跑门
agentic preflight docs/plans/<iteration>/WP-XX.status.json
```

完整落地走查（配置各段、漂移治理、从 in-repo 脚本到安装版 CLI 的迁移）见 [`MIGRATION.md`](MIGRATION.md)。

注意：所有子命令都能在裸 `pip install` 后直接跑——wheel **内置**了 `scripts/agentic/*.sh` wrapper，所以外部项目**不需要**自己的 `scripts/agentic/` 目录。当框架自身仓库里有主仓副本时（框架 dogfood 自己），CLI 优先用主仓副本，这样改 wrapper 不用重装即可生效（见 [`MIGRATION.md`](MIGRATION.md) §5 说明）。

## 命令参考

`agentic <subcommand> [args...]` —— 跑 `agentic --help` 看实时列表。

项目命令（Python，包内实现）：

| 子命令 | 作用 |
|--------|------|
| `init` | 脚手架 `.agentic/config.toml` + 治理契约（AGENTS.md、CLAUDE.md、docs/agentic/OPERATING_MODEL.md）+ 每 WP 模板（docs/agentic/templates/{STATUS.json,WORK_PACKAGE.md}）+ `docs/plans/` 与 `.agentic/locks/` 骨架。无 `--force` 时拒绝覆盖已存在的受管文件。 |
| `contract check` | 逐契约只读漂移报告：`IN_SYNC` / `TEMPLATE_OUTDATED` / `CONFIG_DRIFT`（全同步 exit 0，有漂移 exit 3）。 |
| `contract diff [--apply]` | 展示重渲染 diff；`--apply` 写回并重新盖章。 |
| `bootstrap` | 检测/安装 claude+kimi+codex，校验 `DEEPSEEK_API_KEY`，并对每个 CLI 跑一次真实注入探测（装了但不兼容则失败即闭）。`--dry-run` 只打印计划、不安装也不花 DeepSeek 配额；`--yes` 跳过安装确认。 |
| `migrate-status` | 把旧 `.wp/WP-<id>.status.json` 转成 `agentic-wp-status/v2`（`--iteration`，可选 `--merged-commit`）。 |
| `autonomy` | 按 `[autonomy]` 策略校验一个编排动作 —— 打印 `AUTONOMY_AUTO` / `AUTONOMY_STOP` / `AUTONOMY_NOT_CONFIGURED`；`autonomy signal <signal>` 分类软限制信号。 |
| `mode` | 显示/切换自主模式 —— `agentic mode`（查当前）、`agentic mode ask\|ultra`（切）。 |

编排门（逐字转发到 wrapper —— 主仓 `scripts/agentic/<wrapper>.sh` 存在则优先，否则用 wheel 内置副本；argv、流、退出码原样透传）：

| 子命令 | 转发到 |
|--------|--------|
| `gate` | `codex_merge_gate.sh` —— 独立合并门第二签名 |
| `redispatch` | `redispatch.sh` —— 返工重派回流 |
| `preflight` | `preflight.sh` —— 状态校验 + 分支/WP 锁门 |
| `finalize` | `finalize_merge.sh` —— 三签门（reviewer + consult + Qoder，v3；v2 双签）后 stamp `state=MERGED` + `merged_commit` |
| `merge` | `merge.sh` —— 对 APPROVED_FOR_MERGE 的 WP 做本地 no-ff 合并（autonomy 门控） |
| `dispatch-lint` | `dispatch_lint.sh` —— 派发时状态 lint |
| `quality-gate` | `quality-gate.sh` —— 按路径匹配的项目测试规则 |
| `lock` | `lock.sh` —— WP / 合并并发锁 |
| `health` | `kimi-health.sh` —— 后台执行器进度探测 |

wrapper 承载真正的编排胶水；保持 bash 是冻结的设计决策（CLI 只转发，不重实现它们）。

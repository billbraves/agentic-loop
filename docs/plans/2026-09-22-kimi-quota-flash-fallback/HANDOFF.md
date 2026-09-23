# HANDOFF — kimi 额度回退 deepseek-flash（独立 session 接续点）

> 写于 2026-09-22 | 由 framework-hardening 主 session 停靠，供**独立 session** 接续。
> 本 plan 与 framework-hardening 是两条**独立**线，各有自己的集成分支，互不干扰。
> 本 plan 集成分支 = `plan/2026-09-22-kimi-quota-flash-fallback`（从 `main` 7c318f4 切出），
> worktree = `/Users/admin/vibe/.worktrees/kqff`。

## 已完成（Phase A 前两步）

- **A1 ✓**：集成分支 `plan/2026-09-22-kimi-quota-flash-fallback` 已建，独立 worktree
  `/Users/admin/vibe/.worktrees/kqff`（off `main` 7c318f4）。
- **A2 ✓**：`DESIGN.md`（spec，已与用户逐节确认）+ `IMPLEMENTATION-PLAN.md`（829 行，
  TDD 完整代码）已提交（commit `2ff9e96`）。

## 断点 = Phase A3（尚未开始）

独立 session 从 **A3** 续，**严格按 `IMPLEMENTATION-PLAN.md` 的 Phase A（A3–A5）→ B（B1–B6）→ C 执行**
（该文件是权威步骤来源，含每步完整代码/命令/预期输出，勿凭记忆替代）。概要：

- **A3**：建 `PLAN-01.status.json`（schema `agentic-plan-status/v1`）+ `WP-01-brief.md`
  （模板 `docs/agentic/templates/WORK_PACKAGE.md`）+ `WP-01.status.json`（schema
  `agentic-wp-status/v2`）→ 用 `PYTHONPATH=src python3.11 -m agentic_loop.validate_wp_status` 校验。
- **A4–A5**：按 plan 走冻结前签名 → 冻结 WP-01 `DRAFT→APPROVED` + freeze 提交（显式路径）。
- **B**：派发 kimi 实现 B1–B6（feature worktree，全脱离 launch + health 监控至 DONE）。
- **C**：独立复核 → review ACCEPT → `agentic gate` 双签 → merge --no-ff → finalize →
  plan 收敛（单一 commit 到 main，**push 保留人工批准**）。

## 关键设计决策（brainstorming 已与用户确认，**勿重复提问**）

- **落点**：框架代码（redispatch/KimiAdapter），配置驱动、全自动、无人工介入。
- **检测**：新纯函数模块 `src/agentic_loop/quota_fallback.py` 的
  `is_quota_error(output, patterns=None)`，**正向命中**额度模式（中英/429/402/quota/
  insufficient/balance/credit/exceeded/rate limit 等，可经 `[quota_fallback] patterns`
  配置覆盖）才触发；默认清单见 `DESIGN.md` §4。
- **回退目标**：`resolve_paths.py` 新增 `resolve_role_fallback_binding("developer")`，读
  `roles.developer` 的**可选** `fallback_provider` 键 → 从 `[providers.deepseekflash]`
  构造 flash binding（identity_model=deepseek-v4-flash）；键/provider 段缺失 → 返回
  `None`（**零回归**）。
- **控制流**：**派发失败后重试**（非 probe 预切）——先 kimi 原生派发，若失败且输出命中
  额度模式 → 用 flash KimiAdapter **重派一次**；flash 也额度失败 → **单跳 STOP** 交人工。
  probe 门 / circuit-breaker / 锁 / `redispatch_count` 语义**全不变**（回退不额外计数）。
- **安全**：密钥只走 env 名、输出脱敏；**不 push**（always_stop）；显式路径提交。

## 环境 / 纪律提醒（与主线一致）

- `python3.11` = /opt/homebrew（**无 agentic_loop**）→ validate 用 `PYTHONPATH=src
  python3.11 -m ...`；测试用 `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest
  tests -q`（**必须 unset AGENTIC_PYTHON**，否则泄漏进 shell 子进程绕过 python3 stub → 假失败）。
- `agentic` CLI 命令（gate/health/lock/preflight/merge/finalize）用自己的 uv venv，无需 PYTHONPATH。
- 独立 session 用**自己的** `AGENTIC_SESSION_ID`（勿复用主线 `task-a4c`，避免锁 owner 冲突）。
- 4 个预存失败在 `test_finalize_merge_triple_sign.py`（`main` 被 sibling worktree
  `agentic-loop-main-codex-merge` 占用所致），**非本 plan 回归**，属已知基线。
- 全脱离启动 kimi dispatch（Python `Popen` `start_new_session=True` + stdin `DEVNULL`），避免 tty-stop。

## 停靠时状态快照（2026-09-22 核验）

- kqff worktree：branch=`plan/2026-09-22-kimi-quota-flash-fallback`、HEAD=`2ff9e96`、**clean**。
- 本 plan 尚未建任何 status 文件、未取任何锁、未派发 kimi。
- `main` tip=`7c318f4`（本 plan base）。

## 2026-09-23 原位收敛验证记录

- 执行角色：Orchestrator；实际工具：Qoder。用户已明确批准合并并 push，并选择保留其他改动的原位手工收敛。
- 合并提交：`b49ba9d708914aeb4955b04b954b774b2cd766f3`；第二父（计划集成 tip）：`dbf53bd7a67d48ae64877fbb736e32c05addb4a8`。合并前 `agentic plan lint` 为 clean，WP 状态提交恰为 freeze + finalize。
- 合并结果树与集成 tip 完全相同；`agentic plan finalize` 已实际执行，状态以同目录 PLAN-01.status.json 为准。
- 合并提交的独立洁净副本全量验证：`env -u AGENTIC_PYTHON GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch GIT_CONFIG_VALUE_0=main PYTHONPATH=src python3.11 -m pytest tests -q`；退出码 0，**807 passed, 4 skipped in 165.75s**。仅进程级设置默认分支，不修改仓库或全局 Git 配置。
- 纠正上文历史环境归因：本次原环境四项三签测试失败是临时仓库没有 main 分支，不是 sibling worktree 占用；默认分支环境对照可消除这四项失败。
- 绝对 PYTHONPATH 下既有 pre-push 状态目录问题仍未修复；本次是已 MERGED 的 main 收敛，单独校验计划证据与全量测试，不依赖活动 WP 发现来证明通过。
- 执行时 core.hooksPath 未配置且默认 hooks/pre-push 不存在；不改 Git 配置，push 前原样执行已跟踪的 .githooks/pre-push。生产启用前仍须非生产凭据验证 flash id/selector。
- main 中其他工作文件保留，合并前后 SHA-256 一致（未暂存、未提交）：
  - `src/agentic_loop/adapters/kimi.py`：`5f932cea84b39e02f05f8ba9b6616fd6bcad214f908e29806994fd3e669b6fbc`
  - `src/agentic_loop/provider_binding.py`：`7358e9394d2cf0fdb633b4b53f5580082a67c4924db4926bab872608337ca469`
  - `tests/test_kimi_managed_k3.py`：`66aafdeb2dab2b76328475fdd341134a8402a80248fcb79bc7d028287020791a`
  - `uv.lock`：`d11edd8fe4c7c632ba80f3e202fbbe7b87466ff3beef2f815f602e6d13a534ca`

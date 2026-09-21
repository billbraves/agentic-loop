# WP-11 / WP-13 re-freeze rev2 — codex 架构复核请求

> 触发 2026-09-20 ｜ 提问者 claude（编排者）｜ 咨询者 codex（kirogpt, gpt-5.6-sol, read-only sandbox）
> 性质：**冻结前 brief 审核**（非 diff 审核）。rev2 草稿尚未实现、无 diff、未冻结。
> 角色（AGENTS.md §2）：独立架构/事件顾问。请独立判断，**不附和编排者**；若认为反转错误，直说 REWORK/CONSULT。

## 0. 一句话

P3-b 存量重估发现 WP-27（B17, commit `a3264c0`, 已 MERGED）顺带改了 preflight 的 status 读取范式，
使 WP-11(B1) / WP-13(C3) 的 rev1 前提失效。我为两者起草了 re-freeze rev2。冻结前请你独立复核
**方向与范围**，尤其 WP-13 的 **C3 方向反转**（架构判断，我最需要你独立确认，而非我自证）。

## 1. 背景：WP-27 做了什么（C3/B1 反转的依据）

commit `a3264c0`（WP-27/B17）把 preflight 的 status 读取从「bare `$1`，相对 cwd」改成：

- 相对路径锚定 `main_repo`（`resolve_paths --root main_repo`）
- `path_is_in_worktree` 拒绝解析到 linked worktree 内的 status 副本
- emit `PREFLIGHT_PASS ... status=<resolved>`

立场：**读 worktree 冻结快照本身是 bug；status 的单一事实源是主区 live 状态（INV-4）。**

## 2. rev1 与 rev2 的立场冲突（C3 核心）

**rev1 WP-13 陷阱 4 原文**（`WP-13-brief.md:133-134`）：

> C3 是纯输出层。**不得**为了「让状态一致」去改读取来源（例如改成读主区工作区）——
> 那会打穿「状态文件只提交两次」的纪律，且让门读到未提交的内容。

rev1 C3 立场：门读副 worktree 冻结副本是设计使然，只**标注来源**、**不改读取来源**。

**rev2 WP-13 反转**：WP-27 已确立「读 worktree 快照是 bug、须锚定 main-repo live」。若 quality-gate
仍读 worktree 快照而 preflight 读 main-repo live，两门读不同份 status，判定分叉。故 rev2 C3 =
把 WP-27 preflight 范式移植到 quality-gate（`quality-gate.sh:9` 仍 bare `status_file=$1`）。

## 3. 要判断的问题（逐条给 ACCEPT/REWORK/CONSULT + 理由）

**Q1（最关键，架构）C3 方向反转是否成立？**
- rev1 陷阱 4「不得改读取来源」与 WP-27「读 worktree 快照是 bug」是否真的根本冲突？
- 还是两者可调和（例如 rev1 担心的「读未提交内容」在 WP-27 范式下其实不是问题）？
- 把 preflight 范式移植到 quality-gate，是否正确、是否足够（有无遗漏 quality-gate 特有语义）？

**Q2（一致性）C3 与 B5 在 quality-gate 内是否自洽？**
- C3 rev2：status 读 **main-repo live**（锚定 `main_repo`）
- B5 rev2：quality-gate 必须在**声明的 worktree 内**跑（`status.git.worktree` ≠ cwd → 拒绝），改动集看 worktree
- 即「在 worktree 内执行、改动集看 worktree、但 status 读主区」。两个根（`current_worktree` vs `main_repo`）
  并存是否自洽？有无隐藏矛盾（执行者传的 status 路径解析、`path_is_in_worktree` 拒绝与 B5 拒绝的先后/冲突）？

**Q3（WP-11 B1 缩小）是否成立？**
- B1 核心场景（相对路径→worktree 解析→outside-repo 被吞→误报 must be tracked）已被 WP-27 消除。
- rev2 B1 残余：`preflight.sh:111` `git -C "$main_root" ls-files --error-unmatch "$status_file" >/dev/null 2>&1`
  的 `2>&1 >/dev/null` 仍把 git 真实错误（绝对路径落主仓外、非 worktree 时的 outside-repo）整条丢掉，
  与「仓内未跟踪」共用 `:112` must be tracked。
- 问：这个残余是否真实、范围是否对？还是 WP-27 之后 B1 已无残余（可整条关闭 WP-11）？

**Q4（WP-11 B4 挂起）是否成立？**
- B4：`AGENTS.md §4.1` 派发范式加 `pipefail`。
- 挂起理由：`AGENTS.md` 当前是 §2 #3 未裁决归属的禁区改动（12 增 12 删），叠加 B4 会冲突；且 grep 确认现有派发范式无 `pipefail`/`PIPESTATUS`。
- 问：B4 挂起（移出 WP-11，待 #3 裁决）是否成立？还是 B4 应保留/另有归属？

**Q5（范围收缩 + lane 收益）是否成立？**
- WP-11 rev2 去 `AGENTS.md`（只留 `preflight.sh:111` + 新测试）；WP-13 rev2 去 `preflight.sh`（只留 `quality-gate.sh` + 新测试）。
- 预期：消除 3 处交叠（WP-11/12 碰 AGENTS.md、WP-11/13 碰 preflight.sh），WP-11/13 有望脱离 lane-core 分量。
- 问：范围收缩是否正确？有无过度收缩（漏掉必要改动）或收缩不足（仍含冗余）？

## 4. 证据文件（read-only sandbox 内自行读；无需我内联）

- 草稿：`docs/plans/2026-09-13-parallel-throughput/WP-11-brief-rev2.md`、`WP-13-brief-rev2.md`
- rev1 对照：`WP-11-brief.md`、`WP-13-brief.md`（陷阱 4 在 `:133-134`）
- 重估依据：`CONVERGENCE-P3-b-stock-reassessment.md`
- 现状源码：`src/agentic_loop/wrappers/preflight.sh`（WP-27 改后）、`src/agentic_loop/wrappers/quality-gate.sh`
- WP-27 范式：`git show a3264c0 -- src/agentic_loop/wrappers/preflight.sh`
- 全局规范：`AGENTS.md §4.1/§4.3`（status 单一事实源、commit discipline）

## 5. 作答格式

- 先给一行 `VERDICT: ACCEPT | REWORK | CONSULT`（针对**整批 re-freeze 是否可冻结**）
- 再逐条 Q1–Q5 给结论 + 理由
- 若有阻塞项，明确「冻结前必须改什么」
- 你以 prose 作答即可（本 provider 下 `--output-schema` 是软约束，编排者逐字转录 + 独立核验）

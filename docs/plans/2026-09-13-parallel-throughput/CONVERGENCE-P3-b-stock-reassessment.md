# CONVERGENCE-P3-b · WP-09~14 存量重估（核验报告）

> 日期：2026-09-20（用户「按建议执行」放行 P3 存量重估）
> 范围：**只读核验 + 处置建议**。不改任何 WP 的 `state`、不 re-freeze、不派发、不 push。
> 对应裁定：CONVERGENCE-PLAN §2 **#8「WP-09~14 重估后逐份 re-freeze」（待批）**、§1 P3「#25 存量重估」。
> 结论须经用户裁定后，才落地到各 WP status / re-freeze。

## 1. 核验方法

1. 从 6 份 brief 提取目标缺陷（引用 `WP-08-candidate.md` §A1~§C3）。
2. 核验**验收测试存在性**（ABSENT = 该 WP 从未被实现）。
3. 核验**缺陷点源码现状**（grep 具体代码，判断缺陷是否还在）。
4. 核验 allowed_paths 文件的 **git log**（哪些已 MERGED 的 commit 碰过 → 前提是否变化）。
5. 对关键 commit（`a3264c0`）读 message + diff stat + 现状代码交叉验证。

## 2. 逐 WP 核验结论

| WP | 缺陷 | 源码现状（证据） | 前提变化 | 处置建议 |
|---|---|---|---|---|
| **WP-09** | A1+A3 | `init_cmd.py:57 # [[quality_gate.rule]]`、`:66 min_independence="strong"` **均在**；`test_init_gate_form.py` ABSENT | init_cmd 被 `0d4ff50`(Plan收敛)/`ba8db1d`(phase-tiers) 碰过，属功能新增，**未碰缺陷点**；行号可能微调 | **保留派发**（缺陷仍在）；派发前轻 re-freeze 核对行号 |
| **WP-10** | A2 | `STATUS.json.tmpl:7 "state":"DRAFT"` + scaffold 同 **仍在**；`test_status_template_dispatchable.py` ABSENT | 模板被 `0d4ff50`(Plan收敛) 碰过，可能新增 plan 相关字段 | **保留派发**；re-freeze 核对模板结构 |
| **WP-11** | B1+B4 | B1：`preflight.sh:111` 仍有 `2>&1`，但已加 `-C "$main_root"`；B4：`AGENTS.md` 无 pipefail/PIPESTATUS；`test_preflight_tracked_error.py` ABSENT | **B1 前提大变**：`a3264c0`(WP-27) 已锚定主仓根 + 拒绝 worktree 内路径，**消除了 B1 核心误报场景**（传相对路径→副 worktree 解析→git outside-repo 被误报未跟踪）；行号 69→111 | **需 re-freeze**：B1 缩小为「`2>&1` 吞错误的次要清理」（核心已被 WP-27 解决）；B4 依赖 `AGENTS.md`（**当前是禁区 M 改动**），须先解 §2 #3 |
| **WP-12** | B2+B6+B3 | `kimi-health.sh:55` MD5 空摘要哨兵、`kimi.py:132 dispatched=proc.returncode==0` **均在**；`test_health_unknown_no_output.py`/`test_adapter_dispatched_semantics.py` ABSENT | adapters/kimi-health 最近改动均较旧（`e52b802`/`1daf234`/`94dcd50`），**未碰缺陷点** | **保留派发**（前提基本未变，缺陷仍在） |
| **WP-13** | B5+C3 | **C3 preflight 侧已修**：`preflight.sh:143` emit `status=$status_file`、`test_preflight_status_source.py`(468行) 存在、锚定主仓根读 live status；**C3 quality-gate 侧未修**：`quality-gate.sh:9 status_file=$1` 仍 bare；**B5 未修**：`:26 repo_root` 赋值后，`:42-46` 改动集 4 条 git 命令仍无 `-C`/`cd` | **C3 前提大变**：`a3264c0`(WP-27) 修好 preflight 侧 C3，并建立**可复用模式**（main_root 锚定 + `status=` 输出 + `path_is_in_worktree` 拒绝） | **需 re-freeze**：C3 缩小为「把 WP-27 已验证的 preflight 模式移植到 quality-gate」；B5 保留。范围显著缩小且方向明确 |
| **WP-14** | C2 | `STATUS.json.tmpl:29 "evidence":{"tests":[]}` **仍在**（无形状线索）；`test_status_template_evidence_shape.py` ABSENT | 模板被 `0d4ff50` 碰过；依赖 WP-10（同碰 STATUS.tmpl，lane-template 串行） | **保留派发**；re-freeze 核对模板；与 WP-10 串行 |

## 3. 核心洞察

1. **WP-27（B17，已 MERGED，commit `a3264c0`）顺带修复了 WP-11(B1) 的核心场景 + WP-13(C3) 的 preflight 侧**。这是存量重估的最大价值——**避免把已被修好的工作再派发一遍**。两份旧 brief 引用的 preflight 缺陷形态（`:69` 无 `-C`、读 worktree 快照、不声明来源）已不复存在。
2. **没有一个 WP-09~14 可以「直接关闭/判 MERGED」**：6 个 WP 的专属验收测试**全部 ABSENT**，缺陷主体（A1/A3/A2/B2/B6/B5/C2）经 grep 确认**仍在源码里**。所以存量重估的产出**不是减少在途 WP 数量**，而是「WP-11/13 需 re-freeze 缩小范围，WP-09/10/12/14 保留待派发」。
3. **需 re-freeze 的只有 WP-11、WP-13**（前提被 WP-27 实质改变）；其余 4 个前提基本未变（或仅需核对被 Plan 收敛碰过的模板行号）。

## 4. 对 P3-a lane / 并行度的影响

- 存量重估**未减少在途 WP 数量**（6 个都仍有效）→ P3-a 分量1 的 **9 WP 串行瓶颈依旧**。
- **但** WP-13 re-freeze 后大概率**不再碰 `preflight.sh`**（C3 preflight 侧已由 WP-27 修，只余 quality-gate 侧 + B5）→ 可**消除 WP-13 与 WP-11 在 `preflight.sh` 上的交叠**，轻微松动分量1 纠缠。须在 re-freeze 重界 allowed_paths 时确认。
- 真正的并行度提升仍须靠「WP 重拆」（拆 WP-18 枢纽），见 P3-a 记录 §5，超出本次范围。

## 5. 处置建议汇总（待用户裁定 #8）

- **保留派发**（缺陷仍在、前提未变）：WP-09、WP-12 —— 可直接进入派发队列（派发前核对行号）。
- **保留派发 + re-freeze 核对模板**：WP-10、WP-14 —— 模板被 Plan 收敛碰过，re-freeze 校准后再派发（两者 lane-template 串行）。
- **需 re-freeze 缩小范围**：WP-11（B1 缩小、B4 待 AGENTS.md 解禁）、WP-13（C3 缩为 quality-gate 移植 + 保留 B5）。
- re-freeze 是「冻结」动作，须走 §2 #8 批准流；本报告只给重估结论与方向，不自行 re-freeze。

## 6. 禁区遵守 + 提交

- 全程只读核验；未改任何 WP `state`、未 re-freeze、未派发、未 push；未动 6 个无关未提交改动与 uv.lock；未清理工作树。
- 核验脚本 `.agentic/tmp_verify.sh` 为 local state，用后删除，不提交。
- 提交：`git add` + `git commit --` 显式路径（仅本报告）。

## 7. 后续

- 用户裁定 #8 后：对 WP-11/13 起草 re-freeze brief rev2（缩小范围），WP-09/10/12/14 校准后排队派发。
- 与 P3-a 衔接：re-freeze 重界 allowed_paths 后，可复跑文件重叠分析，看分量1 是否松动。
- B4（WP-11）依赖 AGENTS.md 解禁 → 挂在 §2 #3（六个无关改动归属）之后。

# WP-11 (rev2 草稿): preflight tracked 检查区分「路径在仓外」与「仓内未跟踪」（B1 残余）

> **状态：DRAFT — 待用户批准冻结（CONVERGENCE-PLAN §2 #8）。批准前不得派发、不得写 freeze 提交。**
> 冻结日期：待填 ｜ 编排者：claude ｜ 执行者：kimi（provider: deepseek）
> 所属 Plan：2026-09-13-parallel-throughput ｜ lane：`lane-core`（见 CONVERGENCE-P3-a）
> re-freeze 序号：rev2（第 1 次 re-freeze；**未**触发 WORK_PACKAGE.md.tmpl:9 的第 3 次停手复核门）
> 冻结后执行期间不得修改；需再修订走 re-freeze（新建 rev3）。

## rev2 相对 rev1 的变化（为什么 re-freeze）

rev1（`WP-11-brief.md`，冻结 2026-09-13）含 **B1+B4** 两缺陷。P3-b 存量重估
（`CONVERGENCE-P3-b-stock-reassessment.md`）核验发现前提已变：

1. **B1 核心场景已被 WP-27 消除**：commit `a3264c0`（WP-27/B17，已 MERGED）把 preflight
   的 status 路径锚定 `main_repo` + 用 `path_is_in_worktree` 拒绝 worktree 内副本。rev1 B1
   描述的主触发链「传相对路径 → 在副 worktree 解析 → git 报 outside-repo 被 `2>&1` 吞 →
   误报 must be tracked」**已断**。**残余**：绝对路径落在主仓外且非 worktree 时，`:111` 的
   `ls-files` 仍报 outside-repo 被 `2>&1` 吞掉 → 仍与「未跟踪」共用一句错误信息。rev2 只修此残余。
2. **B4 移出本 WP（挂起）**：B4 要改 `AGENTS.md §4.1` 派发范式加 `pipefail`。但 `AGENTS.md`
   当前是 §2 #3 未裁决归属的**禁区改动**（12 增 12 删），在其上叠加 B4 会与 #3 冲突。
   B4 **挂起**，待 #3 裁决 AGENTS.md 归属后另立/并入。rev2 **不含 B4**。

**净效果**：rev2 范围 = B1 残余；allowed_paths **去掉** `AGENTS.md` / `AGENTS.md.tmpl`
（→ 消除 WP-11 与 WP-12 在 AGENTS.md 的交叠，见 P3-b §4）。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

| 面 | 结论 | 依据 |
|----|------|------|
| status 路径锚定 + worktree 拒绝 | **已由 WP-27 修好，不要动、不要回退** | `preflight.sh` 的 `a3264c0` 段：`main_repo` 锚定相对路径、`path_is_in_worktree` 拒绝 worktree 内副本、`PREFLIGHT_PASS ... status=$status_file`（`:143`）；测试 `tests/test_preflight_status_source.py`（468 行） |
| tracked 检查 | **残余缺陷，rev2 只修这里** | `preflight.sh:111` `git -C "$main_root" ls-files --error-unmatch "$status_file" >/dev/null 2>&1` —— `2>&1 >/dev/null` 仍把 git 真实错误（outside-repo）整条丢掉，与「仓内未跟踪」共用 `:112` 的 must be tracked |
| B4 派发范式 | **挂起，不在本 WP** | `AGENTS.md` 属 §2 #3 禁区；现有派发范式无 `pipefail`/`PIPESTATUS`（grep 确认） |

→ 故本 WP **只收 `preflight.sh:111` tracked 检查的错误信息分辨**，不动 WP-27 已修的
路径锚定/worktree 拒绝段，不碰 AGENTS.md。

## 范围

**allowed_paths**
- `src/agentic_loop/wrappers/preflight.sh`（**仅** `:111` tracked 检查的错误信息分辨）
- `tests/test_preflight_tracked_error.py`（新建）

**forbidden_paths**
- `.env`、`.context/`
- `AGENTS.md`、`src/agentic_loop/templates/AGENTS.md.tmpl`（B4 挂起；且属 §2 #3 禁区）
- `preflight.sh` 的 WP-27 status 锚定/worktree 拒绝段（`a3264c0` 成果，不得回退或削弱）
- `src/agentic_loop/adapters/`、`wrappers/kimi-health.sh`、`wrappers/quality-gate.sh`、`gate/`
- 其余一切未在 allowed 列出的路径

## 交付物清单

**B1 残余 —— tracked 检查区分两种失败**

1. `preflight.sh:111` 的 tracked 检查改成：先分辨「路径是否落在主仓内」，再判 tracked；
   两种失败给两条**不同**错误信息，且**把 git 的 stderr 带进错误信息**（现在整条丢 /dev/null）。
   - 路径在主仓外（git 报 outside repository）→ 错误信息含「路径/仓库」语义，**不含** "must be tracked"
   - 路径在主仓内但未 `git add` → 仍报 `PREFLIGHT_FAIL: status file must be tracked before implementation`
     （**字样不改**，下游可能匹配它）
2. 退出码保持 `2` 不变（**硬要求**：rc 是契约，新增失败原因不等于新增 rc）。
3. **不得削弱** WP-27 已建的 `path_is_in_worktree` 拒绝——「worktree 内副本」与「主仓外」是
   两种不同拒绝，各自保留。

## 完成定义（DoD）

- [ ] **反向测试（B1 硬要求）**：构造两例——
      (a) status 路径指向主仓外（非 worktree）→ 断言错误信息**不**含 "must be tracked"、含路径/仓库语义、`rc==2`
      (b) status 在主仓内但未 `git add` → 断言仍报 must be tracked、`rc==2`
- [ ] **回归**：WP-27 的 worktree 拒绝仍生效（worktree 内路径 → 断言 "resolves inside a worktree" 拒绝）
- [ ] preflight 其余检查行为与 rc 不变（现有 preflight 测试全绿，含 `test_preflight_status_source.py`）
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
- [ ] 无 forbidden_paths 写入；无生产 DB/网络/推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **preflight 是派发前硬门，改失败路径格外小心「把门改松」**：新增路径判断不得让原本会 fail
   的输入变成 pass（反向测试 (b) 钉这个）。
2. **不要把 tracked 检查整段换成 Python**；wrapper 层是 shell 契约，保持形态。
3. **不要动 WP-27 段**（status 锚定/worktree 拒绝）：那是 `a3264c0` 的成果；rev2 只在其后修
   `:111` 的错误信息。若认为两处应合并，写进 `[CONCERNS]` 让编排者裁。
4. 本仓 Python 兼容 >= 3.9；测试命令用 `python3.11`（本机 `python3` 是 3.14 无 pytest）；
   跑全量**不要设** `AGENTIC_PYTHON`（B3 会打穿测试自带 python3 stub 造假失败）。
5. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 4 个，与本 WP 无关，勿修。
6. **行号以冻结时 HEAD 为准**：`:111`/`:143` 为 2026-09-20 核验值，冻结前请复核。

## Allowed and forbidden paths / Completion definition / Acceptance tests

（`agentic dispatch-lint` 英文标题锚点，内容同上，以 `WP-11.status.json` 的
`scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。）

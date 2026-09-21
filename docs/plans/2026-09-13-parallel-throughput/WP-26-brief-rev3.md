# WP-26 rev3（加固补丁返工）: dispatch_lint 失败输出契约收紧到「续行内容」

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 本 rev 是 rev2 的**加固补丁返工**，不是 rev2 主体的返工。
> rev2 已验证通过的全部行为（B21 修复本体）**不得改动**，见「不得改动」表。
> 前序：rev1 `0a12bed` → rev2 `0b4deb2` → 加固 `16bfdf3`（被复签驳回）→ 本 rev3。

## 目标（一句话）

把 `_assert_single_fail_token()` 的失败输出契约从「续行的**起点**」收紧到「续行的**内容**」，
并把 stdout 断言改为逐字节空串 —— 消除 codex 复签实测证实的两条逃逸（C1 / C2 = 缺陷 B25）。

## 背景：为什么需要 rev3

加固补丁 `16bfdf3` 声称收紧输出契约，实测**仍放过**它要防的形状：

```python
P(stdout="", stderr="DISPATCH_LINT_FAIL: brief sha256 mismatch\nunexpected diagnostic\n")
# -> 通过 helper：token 恰 1 次、位于首行、stdout.strip() 为空
```

- **C1**：三条不变量只约束续行**起点**（首行是 token），未约束续行**内容**，
  故「token 行 + 任意非 token 续行」全部逃逸。
- **C2**：`stdout.strip() == ""` 与其自身 docstring 宣称的 "stdout is empty" 不等价，
  放过 `" "` / `"\n"` 等纯空白 stdout。

两条均由编排者直接 import 被审树自己的 helper 逐形状实测证实（非转录）。详见
`WP-08-candidate.md` §B25 与 `WP-26-consult-codex-harden.md`。

## Allowed and forbidden paths

**allowed_paths**（本 rev 只准动 1 个文件）:

- `tests/test_dispatch_lint_brief_source.py`

**forbidden_paths**:

- `src/agentic_loop/wrappers/dispatch_lint.sh` —— **零 diff**。本 rev 是纯测试侧收紧，
  不得为了让断言通过而改被测脚本的输出行为。
- `src/agentic_loop/redispatch.py` —— 零 diff（参考实现）。
- `src/agentic_loop/wrappers/preflight.sh`（B17 归 WP-27）
- `src/agentic_loop/wrappers/finalize_merge.sh`
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/gate/__init__.py`
- `src/agentic_loop/templates/`
- `tests/test_finalize_merge_triple_sign.py` —— 那 4 条是既有失败，**不要修**。
- `CLAUDE.md`, `AGENTS.md`, `docs/agentic/OPERATING_MODEL.md`, `docs/plans/`
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## 输入

- 被审树：worktree `/Users/admin/vibe/wp26-brief-source-of-truth`，分支
  `feature/wp26-brief-source-of-truth`，当前 HEAD `16bfdf3`（在其上叠加，**不要** reset）。
- 编排者实测的 10 条失败路径行数表（见下「已知事实」），落地判据据此设计，无需放宽任何现有用例。

## 交付物清单

1. **stdout 逐字节断言**：`assert proc.stdout == ""`，替换 `stdout.strip() == ""`。
   docstring 同步改为与判据逐字一致的表述。
2. **普通失败路径不得有任何续行**：默认断言 `tuple(stderr.splitlines()[1:]) == ()`。
3. **多错并报路径显式声明其续行**：helper 接受一个可选参数（形如
   `expect_continuations=()`），多错用例传入其**精确**的续行元组
   （当前为 `("STATUS_INVALID: review.decision is invalid: 'NOPE'",)`），
   断言 `tuple(lines[1:]) == tuple(expect_continuations)`。
   **不得**用「续行数量 >= 1」或「续行里含某子串」这类开放式断言替代精确相等。
4. 保留并强化既有两条不变量：token 计数恰 1、首行以 token 开头。
5. **拒用理由留痕不得丢**：docstring 里「刻意不用 `len(stderr.splitlines()) == 1`
   作为**全局**约束」的理由必须保留（B24：validator 多错并报是正当路径）。
   注意本 rev 的修法与该理由**不矛盾**——普通路径严格单行是**逐用例**约束，
   多错用例走精确声明的续行，二者共存。docstring 必须把这个区别写清楚。

## Acceptance tests

- **三条逃逸形状必须全部转红**（这是本 rev 的核心判据，每条都要有用例）：
  1. `stdout=""`, `stderr="DISPATCH_LINT_FAIL: x\nunexpected diagnostic\n"` → helper 必须抛 AssertionError；
  2. `stdout=" "`, `stderr="DISPATCH_LINT_FAIL: x\n"` → 必须抛；
  3. `stdout="\n"`, `stderr="DISPATCH_LINT_FAIL: x\n"` → 必须抛。
  用 `pytest.raises(AssertionError)` 直接喂构造对象给 helper，不必起子进程。
- **两条正当路径必须不误红**（正控制，防止过度收紧）：
  1. 干净单行失败：`stdout=""`, `stderr="DISPATCH_LINT_FAIL: x\n"` → 通过；
  2. 多错并报且续行被精确声明 → 通过。
- **9 条既有失败路径用例全部保持绿**（它们实测 stderr 恰 1 行、stdout 逐字节空）。
- **forbidden 变异转红**：在 `shutil.copytree` 出来的 scratch 副本上，把
  `dispatch_lint.sh` 的 `fail()` 改为额外向 stderr 打一行非 token 续行，
  断言相应失败用例转红；随后丢弃 scratch 副本。
  **活树 `dispatch_lint.sh` 的 sha256 在测试前后必须逐字节相同**
  （当前值 `ca5d34de1ec67b9edd2c586ec5839a5ea389b67b13411ce73afbdda88d858363`），并在用例内断言之。
- 每条负面断言带 oracle 三项（正向可达性控制 / 原因特异的 witness / scratch 上能转红的变异）。
- 3.11 / 3.13 / 3.14 全绿。
- 相对基线零回归。

## 已知事实（编排者实测，不必复测，但不得与之矛盾）

- 对 helper 插桩记录的 10 次调用：**9 次 stderr 恰 1 行且 stdout 逐字节空串**；
  唯一多行者为 `test_multi_error_continuation_keeps_single_token`（2 行，
  第 2 行 `STATUS_INVALID: review.decision is invalid: 'NOPE'`），stdout 亦为空。
  因此交付物 2 的严格单行默认值**不会**让任何现有用例假红。
- 基线（加固 HEAD `16bfdf3`）：targeted `tests/test_dispatch_lint_brief_source.py` = **23 passed**；
  全量 3.11 = **4 failed, 620 passed, 4 skipped**，4 条失败全为
  `tests/test_finalize_merge_triple_sign.py` 既有失败（`git checkout -q main` CalledProcessError）。
- 编排者已验证 codex 提议的判据形式可实施：三条逃逸全捕获、两条正当路径不误红。
  本 rev 就是把那个已验证的形式落进测试文件。

## 不得改动（rev2 已验证通过，回归即驳回）

| 行为 | 现状 |
|---|---|
| sha256 校验只依赖 `sha256` 在场，与 `path` 无关 | 已修，位于 declared/fallback 汇合之后 |
| 四种在场组合矩阵 + 「无 path + 对 sha256 → PASS」正控制 | 已齐备 |
| 五种路径逃逸 fail-closed（`../` / 绝对 / symlink×2 / 不存在） | 全部 rc=2 |
| 变异测试跑在 scratch copytree 副本上 | 已改 |
| `redispatch.py` | 零 diff |

## Completion definition

- [ ] `assert proc.stdout == ""`（逐字节），docstring 与判据表述一致
- [ ] 普通失败路径默认断言续行元组为空
- [ ] 多错用例精确声明其续行元组（非开放式断言）
- [ ] token 计数恰 1 + 首行以 token 开头，两条保留
- [ ] 「不得用全局单行断言」的拒用理由保留，且与本 rev 修法的关系已写清
- [ ] 三条逃逸形状各有用例且全部转红
- [ ] 两条正当路径正控制均绿
- [ ] 9 条既有失败路径用例保持绿
- [ ] scratch 上的 forbidden 变异能转红；活树脚本 sha256 前后逐字节相同且用例内已断言
- [ ] 每条负面断言带 oracle 三项
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（那 4 条既有失败**不要修**）
- [ ] `dispatch_lint.sh` 与 `redispatch.py` 零 diff
- [ ] 无 forbidden_paths 写入、无跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

- production_writes: FORBIDDEN
- network: FORBIDDEN
- notifications: FORBIDDEN
- data_access: READ_ONLY

## 附注：已知陷阱

- **不要为了让断言通过而改 `dispatch_lint.sh`**。本 rev 的前提是脚本当前行为已正确
  （9 条路径实测恰 1 行、stdout 空），要收紧的是**测试对它的约束**，不是它的行为。
  若发现某条路径实际会打续行而用例需要放宽，那是新发现，应 BLOCKED 上报，不得自行放宽判据。
- **不要把多错用例的续行断言写松**。写成「含子串」或「行数 >= 2」等于把 C1 换个位置留下来。
- 本 WP 已 `refreeze_count=3`。按自订规则（任务 #24）第 3 次 re-freeze 应触发计划复核：
  编排者已复核，判定本 rev 范围极小（1 文件、纯断言强度）、根因明确（B25）、
  且判据形式已由编排者预先实测可实施，故继续而非停手。该复核结论记录在此。

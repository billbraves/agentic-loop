# WP-27: `preflight` 必须判主仓 live status，而不是工作树里的历史快照（B17）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。

## 目标（一句话）

`preflight.sh` 用裸赋值接 status 路径，相对路径落到 **cwd**；而协议 §4.1
要求实现必须在**次级工作树**里跑，于是 cwd 恒为工作树 —— 门禁判的是工作树里那份
**被 git 跟踪的历史快照**，不是编排者刚冻结的主仓 live 状态。
本 WP 把 status 读取面钉到主仓，使 state / scope / risk 三类判断都基于 live 值。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

**缺陷位置**：`src/agentic_loop/wrappers/preflight.sh:9`

```bash
status_file=$1
```

裸赋值 —— 相对路径按 cwd 解析。对照同仓已有的正确口径
（`dispatch_lint.sh:26-29`，把相对路径钉到主仓根）：

```bash
case "$status_arg" in
  /*) status_file="$status_arg" ;;
  *) status_file="${main_root:+$main_root/}$status_arg" ;;
esac
```

**差分对实测**（证明判的是工作树副本，不是主仓）：

| 操作 | 主仓副本 | 工作树副本 | preflight 裁决 |
|---|---|---|---|
| 初始 | `state=DRAFT` | `state=DISPATCHED`（旧快照） | `PREFLIGHT_PASS state=DISPATCHED` |
| **只**改工作树副本为 `state=BLOCKED` | 仍 `DRAFT` | `BLOCKED` | `PREFLIGHT_FAIL` |
| 传主仓**绝对**路径 | `DRAFT` | 不参与 | `PREFLIGHT_FAIL: state DRAFT is not executable` |

主仓副本全程是 `DRAFT`（不可执行），却拿到过 `PREFLIGHT_PASS`。
**真实影响**：本迭代我实际吃到过这一口 —— 一个 live 状态为 `DRAFT` 的 WP
拿到 `PREFLIGHT_PASS state=DISPATCHED`，我当时若照此派发就是在无门禁下开工。

**连带面**：`scope.allowed_paths` / `forbidden_paths` 与 `risk.*`
同样来自那份快照，所以范围与风险判断也是旧口径 —— 编排者刚收紧的白名单不生效。

## 范围

- **allowed_paths**：
  - `src/agentic_loop/wrappers/preflight.sh`
  - `tests/test_preflight_status_source.py`（新建）
- **forbidden_paths**：
  - `src/agentic_loop/wrappers/dispatch_lint.sh`（B16 归 WP-26，本 WP 不碰）
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/gate/__init__.py`、`src/agentic_loop/redispatch.py`
  - `src/agentic_loop/templates/`、`CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md`
  - `docs/plans/`（含本 brief 与全部 status JSON）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## 交付物清单

1. `preflight.sh`：status 路径解析改为与 `dispatch_lint.sh:26-29` **同一口径**
   —— 绝对路径原样用，相对路径钉到**主仓根**（不是 cwd、不是工作树）。
2. 显式拒收**工作树内**的 status 路径：若解析结果落在次级工作树里，
   `PREFLIGHT_FAIL` 并说明「status 的单一权威在主仓」
   （与 `finalize_merge.sh` 已有的 `WORKTREE` 拒收语义一致，口径复用，不新造第二份）。
3. `PREFLIGHT_PASS` 输出行增加它实际读的 status 绝对路径，
   使「判了哪份」在日志里可见（本缺陷能藏一整轮，正因为输出里看不出来）。
4. 新测试 `tests/test_preflight_status_source.py`，每条负面断言自带 oracle 三项。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/wrappers/preflight.sh`
- `tests/test_preflight_status_source.py` (new)

**forbidden_paths**

- `src/agentic_loop/wrappers/dispatch_lint.sh` (B16 belongs to WP-26)
- `src/agentic_loop/wrappers/finalize_merge.sh`
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/gate/__init__.py`, `src/agentic_loop/redispatch.py`
- `src/agentic_loop/templates/`, `CLAUDE.md`, `AGENTS.md`,
  `docs/agentic/OPERATING_MODEL.md`
- `docs/plans/` (this brief and every status JSON)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

- **Reproduce the measured differential pair, then assert it inverts.** Build a
  main repo plus a secondary worktree; write DIVERGENT statuses into the two
  copies (main = an executable state, worktree = a state that would fail, or
  vice versa); run preflight from inside the worktree with a RELATIVE status
  path. Today's behaviour follows the worktree copy; after the fix the verdict
  must follow the MAIN copy. Assert on the divergence, not on one verdict — a
  single-copy fixture cannot distinguish the two readings, which is exactly how
  B17 survived a whole round.
- Divergence must be asserted for all three consumers, not just `state`: a
  `scope.allowed_paths` narrowed only in the main copy must bind, and a
  `risk.*` value tightened only in the main copy must bind.
- A status path resolving INSIDE a worktree must fail closed with a diagnostic
  naming the main-repo single-source rule.
- An absolute path must be honoured unchanged (no re-anchoring).
- The `PREFLIGHT_PASS` line must contain the absolute status path actually read;
  assert it equals the main-repo copy, not the worktree copy.
- Each negative assertion carries the oracle three items:
  1. positive reachability control on the same fixture (same repo pair, a
     status that legitimately passes);
  2. a cause-specific witness — the diagnostic must distinguish "wrong file"
     from "right file, bad state"; if one message cannot separate them, use a
     differential pair instead of asserting on wording (defect B11);
  3. a representative forbidden mutation that turns the test red — revert `:9`
     to the bare assignment and show the divergence test goes red, then restore
     and show it green.
- Green on 3.11, 3.13 and 3.14.
- Zero regression against the baseline recorded in this WP's status JSON.

## Completion definition

- [ ] `preflight.sh` 的 status 路径解析与 `dispatch_lint.sh:26-29` 同口径
- [ ] 相对路径钉主仓根；绝对路径原样用
- [ ] 解析结果落在工作树内 → fail-closed 拒收，诊断说明单一权威在主仓
- [ ] `PREFLIGHT_PASS` 行输出实际读取的 status 绝对路径
- [ ] 差分对成立：主仓与工作树两份分歧时，裁决跟随**主仓**
- [ ] state / scope / risk **三类**都验证了跟随主仓，不只 state
- [ ] 每条负面断言带 oracle 三项，含一个能转红的 forbidden 变异
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（`tests/test_finalize_merge_triple_sign.py` 的 4 条是既有失败，**不要修**）
- [ ] 无 forbidden_paths 写入、无跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

| 维度 | 取值 |
|---|---|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **单份 fixture 证不了这个缺陷**。必须主仓与工作树两份 status **内容分歧**，
   才能区分「读主仓」与「读工作树但恰好一致」。B17 藏一整轮正因为两份长期一致。
2. **口径复用，不要新造**。主仓根解析抄 `dispatch_lint.sh:26-29`；
   工作树拒收语义抄 `finalize_merge.sh` 的 `WORKTREE` 分支。仓里已有两份权威，别写第三份。
3. **不要顺手修 B16**。`dispatch_lint.sh` 的 brief 读取面归 WP-26。
4. **preflight 本身要求在次级工作树里跑**（`PREFLIGHT_FAIL: implementation must run
   in a secondary worktree`），所以测试的正向对照也必须从工作树里发起 —— 从主仓跑会
   撞上这条无关的拒收，得到的红不是你要的那条。
5. **不要用 `agentic preflight` 自证**（B14：冻结副本落后活树 23 行）。
   直跑 `bash src/agentic_loop/wrappers/preflight.sh <status>`。
6. **`state` 之外的两类容易漏**。scope 与 risk 同样来自那份快照；
   只验 state 会留一半缺陷在原地。

### 口径权威源引用

- 主仓根解析的既有正确口径：`src/agentic_loop/wrappers/dispatch_lint.sh:26-29`
- 工作树拒收的既有语义：`src/agentic_loop/wrappers/finalize_merge.sh`（`WORKTREE` 分支）
- 缺陷实测记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B17
- 状态机与可执行状态集合：`src/agentic_loop/validate_wp_status.py`（`STATES`）
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`

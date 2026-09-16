# WP-27 rev2: scope / risk 的差分对方向必须与冻结判据一致（rev1 证的是反面）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> **这是 rev1（提交 `a3264c0`）的返工**，不是重做。rev1 已验证通过的部分见下表，**不要动**。

## 目标（一句话）

rev1 的 `test_scope_and_risk_divergence_follow_main_copy` 构造的是
「主仓宽松 / 工作树收紧 → 断言 PASS」，只证明了**工作树坏值没有污染裁决**；
而 rev1 冻结 brief 要求的是「**只在主仓收紧**的 scope / risk 必须绑定」——
方向相反，于是这条用例钉不住它声称要钉的那半判据。
本 rev2 只把这条补成正确方向，并补上各自的反向对照。

## rev1 已核验通过，**本次不得改动**

| 项 | 编排者实测结果 |
|---|---|
| 范围 | 2 个 allowed_paths，零 forbidden 写入 |
| 主仓根锚定 | 相对路径钉主仓、绝对路径原样，与 `dispatch_lint.sh:26-29` 同 `case` 形态 ✅ |
| `state` 双向差分对 | main=APPROVED/wt=BLOCKED → PASS；main=DRAFT/wt=APPROVED → `state DRAFT is not executable` ✅ |
| 工作树 status 拒收 | 绝对工作树路径 fail-closed，诊断点名「单一权威在主仓」✅ |
| 静态 symlink 形态 | 主仓路径本身是指向工作树副本的 symlink 时，探针解析后判 `WORKTREE` 被拒 ✅（编排者本轮补测） |
| 探针 fail-closed | `|| echo PROBE_FAIL` 不会把失败伪装成 `MAIN`；`MAIN\nPROBE_FAIL` 亦不等于单行 `MAIN` ✅（第二签名独立确认） |
| `PREFLIGHT_PASS` 输出 | 增加 `status=<主仓绝对路径>`，「判了哪份」在日志里可见 ✅ |
| 变异测试 | `shutil.copytree` 整个 wrappers 到 scratch 再变异，活树脚本零改动 ✅ **本次的参照实现，保持不变** |
| 测试规模 | 6 passed on 3.11 / 3.13 / 3.14；full 3.11 `4 failed, 603 passed, 4 skipped`（+6，零回归） |

> ⚠️ 不得改动 `preflight.sh` 的 B17 锚定块、拒收块、`PREFLIGHT_PASS` 输出。
> **本 rev2 预期只动测试文件**；若确需动 `preflight.sh`，须在报告里说明理由。

## 前置事实（编排者已实测 + 第二签名独立发现，执行者不必重做，但**不得与之矛盾**）

**缺陷**：rev1 `tests/test_preflight_status_source.py:302`
`test_scope_and_risk_divergence_follow_main_copy` 的 fixture 是
主仓 `allowed_paths=["docs/"]` / `network_authorized=False`（宽松、可过），
工作树 `allowed_paths=[]` / `network_authorized=True`（坏值），然后断言 **PASS**。

**实测空过**（编排者用 rev1 自己的 scratch copytree 手法验证）：
把 `preflight.sh:120` 的**整个** `dispatch_lint.sh` 调用块删掉 ——

```
# MUTATION: dispatch_lint call deleted entirely
```

—— 该用例仍 `1 passed`。即 scope / risk 的**唯一消费者**被整段摘除，
用例察觉不到；表面症状（`PREFLIGHT_PASS` 与 `status=<主仓路径>`）都还在。

**为什么这是缺陷而非风格**：rev1 冻结 brief 的 Acceptance tests 写明
「a `scope.allowed_paths` narrowed only in the main copy must bind, and a
`risk.*` value tightened only in the main copy must bind」，
DoD 写明「state / scope / risk **三类**都验证了跟随主仓」。
rev1 那条用例证的是「工作树的坏值没被读」，与「主仓的严值被读」不是同一命题：
前者在 scope/risk 完全不被消费时也成立，后者不成立。
这是 B20（锚点钉住标签词而非可操作子句）在**差分对方向**上的同构表现。

## 范围

- **allowed_paths**：
  - `tests/test_preflight_status_source.py`
  - `src/agentic_loop/wrappers/preflight.sh`（**仅在**修正上述测试方向确实需要时；
    预期零改动，如有改动须在报告说明）
- **forbidden_paths**：
  - `src/agentic_loop/wrappers/dispatch_lint.sh`（B16/B21 归 WP-26，本 WP 不碰）
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/gate/__init__.py`、`src/agentic_loop/redispatch.py`
  - `src/agentic_loop/templates/`、`CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md`
  - `docs/plans/`（含本 brief 与全部 status JSON）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_preflight_status_source.py`
- `src/agentic_loop/wrappers/preflight.sh` (expected zero change; only if
  fixing the test direction genuinely requires it — justify in the report)

**forbidden_paths**

- `src/agentic_loop/wrappers/dispatch_lint.sh` (B16/B21 belong to WP-26)
- `src/agentic_loop/wrappers/finalize_merge.sh`
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/gate/__init__.py`, `src/agentic_loop/redispatch.py`
- `src/agentic_loop/templates/`, `CLAUDE.md`, `AGENTS.md`,
  `docs/agentic/OPERATING_MODEL.md`
- `docs/plans/` (this brief and every status JSON)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## 交付物清单

1. **scope 方向的差分对**：主仓 `scope.allowed_paths` 收紧到一个会让
   `dispatch_lint.sh` 拒收的值、工作树副本放宽为可过 → 断言 **FAIL**，
   且失败原因特异于 scope（不是 state、不是 risk、不是「找不到文件」）。
2. **risk 方向的差分对**：主仓 `risk.network_authorized`（或另一 risk 维度）
   设为会让 `dispatch_lint.sh` 拒收的值、工作树副本设为可过 → 断言 **FAIL**，
   原因特异于 risk。
3. **两条各自的反向正向对照**：同一 fixture、只把主仓那一个字段翻回可过值 → PASS。
   两条对照必须**互相独立**：做 scope 对照时 risk 保持可过，反之亦然，
   避免两个拒收原因互相遮蔽（一条 FAIL 可能是另一原因造成的）。
4. **rev1 那条用例的处置**：不要删。它证明的「工作树坏值不污染裁决」是有效命题，
   保留即可，但 docstring 必须改成如实陈述它证的是哪一半，
   不得继续声称自己覆盖了「主仓收紧必须绑定」。
5. **摘除变异必须转红**：把 `preflight.sh` 的整个 `dispatch_lint.sh` 调用块
   在 scratch copytree 上删掉，新增的 scope 用例与 risk 用例**各自独立**转红。
   沿用 rev1 已有的 copytree 手法（`test_bare_status_assignment_reverts_to_worktree`），
   活树脚本零改动，变异后断言活树 `preflight.sh` sha256 与变异前逐字节相同。
   这条变异是本 rev2 的核心 oracle —— 它正是 rev1 那条用例察觉不到的那个变异。

## Acceptance tests

- **The scope differential must invert in the mandated direction**: tighten
  `scope.allowed_paths` ONLY in the main copy so `dispatch_lint.sh` refuses,
  leave the worktree copy permissive, and require FAIL. rev1 asserted the
  mirror image (main permissive, worktree tight, expect PASS), which holds even
  when scope is never consumed at all.
- **The risk differential must invert the same way**: tighten a `risk.*` value
  ONLY in the main copy, leave the worktree copy permissive, require FAIL.
- **Each has its own independent positive control**: flip that one main-copy
  field back to a passing value on the same fixture and require PASS, holding
  the other dimension passing throughout so the two refusal causes cannot mask
  one another.
- **The removal mutation must turn both new tests red, independently.** Delete
  the whole `dispatch_lint.sh` invocation from `preflight.sh` on a scratch
  copytree; the scope test must go red and the risk test must go red, each on
  its own. This is the exact mutation rev1's version survived, so it is the
  criterion that distinguishes a real fix from a restatement.
- **The live tree must be byte-identical after the mutation test**: assert the
  live `preflight.sh` sha256 equals its pre-run value.
- rev1's existing test keeps passing with an honest docstring; every row of the
  "must not change" table above stays green.
- Each negative assertion carries the oracle three items:
  1. positive reachability control on the same fixture;
  2. a cause-specific witness with a `file:line` print point — the scope
     refusal and the risk refusal must be distinguishable from each other and
     from a `state` refusal; if two of them print the same wording, use a
     differential pair instead of asserting on wording (B11);
  3. the removal mutation above, on a scratch copy.
- Green on 3.11, 3.13 and 3.14.
- Zero regression against the baseline recorded in this WP's status JSON.

## Completion definition

- [ ] scope 差分对方向正确：**只在主仓**收紧 → FAIL，原因特异于 scope
- [ ] risk 差分对方向正确：**只在主仓**收紧 → FAIL，原因特异于 risk
- [ ] 两条各有独立的反向正向对照，两个拒收原因不互相遮蔽
- [ ] 摘除 `dispatch_lint.sh` 调用块的变异使两条新用例**各自**转红
- [ ] 变异在 scratch copytree 上做，活树 `preflight.sh` sha256 变异前后逐字节相同
- [ ] rev1 那条用例保留，docstring 如实陈述它覆盖的是哪一半
- [ ] rev1 已通过的全部行为不变（见「不得改动」表）
- [ ] `preflight.sh` 预期零 diff；若有改动，报告里说明理由
- [ ] 每条负面断言带 oracle 三项
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

1. **「工作树坏值没污染」≠「主仓严值被读」**。前者在该字段完全不被消费时也成立。
   判断标准：把消费者整段删掉，你的用例会不会红？不会，就说明证的是前一半。
   这正是 rev1 的实测结果。
2. **两个拒收原因会互相遮蔽**。同时把 scope 和 risk 都设成拒收值，
   得到的红分不清是哪一条造成的 —— 与 B19（红的原因未必是你钉的那层）同族。
   每条差分对只翻**一个**字段，其余保持可过。
3. **拒收措辞可能不特异**。`preflight.sh:120` 把 `dispatch_lint.sh` 的 stderr
   整段包进 `PREFLIGHT_FAIL: dispatch-lint …`，所以 scope 与 risk 的拒收可能
   共用外层措辞。先去 `dispatch_lint.sh` 里查这两类各自的打印点（`file:line`），
   若外层措辞无法区分，就用差分对承载原因特异性，不要硬写措辞断言。
4. **preflight 要求在次级工作树里跑**（`PREFLIGHT_FAIL: implementation must run
   in a secondary worktree`），正向对照也必须从工作树里发起 ——
   从主仓跑会撞上这条无关的拒收，得到的红不是你要的那条。
5. **不要顺手修 B22**。`preflight.sh` 对 `$status_file` 有 9 次独立 open
   （判定面与消费面分离，见 `WP-08-candidate.md` §B22），
   编排者已定级为**非阻塞**并另立 WP 收口。本 rev2 不碰。
6. **不要动已验过的面**。B17 锚定块、工作树拒收块、`PREFLIGHT_PASS` 的
   `status=` 输出都已通过；改它们会把已验证的面重新变成未验证的面。
7. **不要用 `agentic preflight` 自证**（B14：冻结副本落后活树）。
   直跑 `PYTHONPATH=src bash src/agentic_loop/wrappers/preflight.sh <status>`。
8. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。

### 口径权威源引用

- scope / risk 的实际消费点：`src/agentic_loop/wrappers/dispatch_lint.sh`
  （由 `preflight.sh:120` 调用）
- scratch 变异的参照实现（rev1 自己已有）：
  `tests/test_preflight_status_source.py::test_bare_status_assignment_reverts_to_worktree`
- 缺陷实测记录：`WP-08-candidate.md` §B20（同构的锚点方向问题）、§B22（非阻塞的读取面）
- rev1 冻结 brief（本 rev2 未覆盖的部分继续有效）：`WP-27-brief.md`
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`

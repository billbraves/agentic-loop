# WP-26 rev2: 修 B21 —— sha256 校验必须与 `path` 是否在场无关（fail-closed）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> **这是 rev1（提交 `0a12bed`）的返工**，不是重做。rev1 已验证通过的部分见下表，**不要动**。

## 目标（一句话）

rev1 把 brief 读取面改成「以 `evidence.brief.path` 为权威」时，
把 sha256 校验放在了 declared 分支**之后**、fallback 分支的 `return` **之前**，
于是「声明了 `sha256` 但没声明 `path`」这一组合静默跳过校验；
本 rev2 只修这一条，并补上缺失的组合覆盖。

## rev1 已核验通过，**本次不得改动**

| 项 | 编排者实测结果 |
|---|---|
| 范围 | 4 个 allowed_paths，零 forbidden 写入 |
| 差分对构造 | 固定命名文件故意 BAD、声明 `-rev2` 文件 GOOD，PASS 只能来自读声明路径 ✅ |
| 三种逃逸拒收 | `../` 逃逸、仓外绝对路径、symlink 逃逸均 fail-closed ✅ |
| 声明路径不存在 | `brief not found` 拒收 ✅ |
| sha256 不匹配（`path` 在场） | 拒收并同时打印 `computed=` / `declared=` 双值 ✅ |
| 老 status 回退（两字段都缺） | 零回归走固定命名 ✅ |
| `redispatch.py` 侧 | `if declared_sha:` 位于分支之后，两条路径都校验 —— **这一侧是正确的，作为本 rev2 的参照实现** |
| 测试规模 | 19 passed on 3.11 / 3.13 / 3.14；full 3.11 `4 failed, 616 passed, 4 skipped`（+19，零回归） |

> ⚠️ 不得重构 rev1 的解析器整体结构，不得改动上表任何一行的行为。
> 本 rev2 的 diff 应当很小。

## 前置事实（编排者已实测 + 第二签名独立发现，执行者不必重做，但**不得与之矛盾**）

**缺陷位置**：`src/agentic_loop/wrappers/dispatch_lint.sh` 内联 python 解析器的
fallback 分支 —— `path` 缺失时 `print("BRIEF_OK")` + `SystemExit(0)`，
而 sha256 校验块在其之后，永不执行。

**实测差分**（WP-26 工作树，`state=DRAFT` 的 status 临时副本）：

| `evidence.brief` 内容 | `dispatch_lint.sh` | `redispatch.py._brief_content()` |
|---|---|---|
| `{"sha256": "0"*64}`（错，无 `path`） | `DISPATCH_LINT_PASS` rc=0 ❌ | `refused: brief sha256 mismatch: computed=e3428210… declared=000…` ✅ |
| 同一错 sha256 **+ 正确 `path`**（对照） | `DISPATCH_LINT_FAIL: brief sha256 mismatch: computed=a84d7440… declared=000…` rc=2 ✅ | — |

即**同一 status 形态，两个消费者裁决相反**。这同时违反本 WP rev1 冻结 brief 的两条：
- 交付物 2：「`evidence.brief.sha256` 存在时**必须校验**」；
- 陷阱注 4：「sha256 的失败必须 fail-closed。算不出（文件读不到、权限）也要拒收，不得跳过」；
- 交付物 3 要求 `redispatch.py`「同口径」—— 口径分裂本身是第二重违规。

**为什么一整轮没被发现**（含编排者第一轮验收）：rev1 的 19 条用例只覆盖
「`path` 与 `sha256` 同时存在」。两个可选字段有**四种在场组合**
（都无 / 只有 `path` / 只有 `sha256` / 都有），用例只走了两种。
编排者第一轮测了三种**拒收原因**，但三种都落在「`path` 在场」这一半 ——
按原因枚举，而非按在场组合枚举，是这个洞的形状。详见
`WP-08-candidate.md` §B21。

## 范围

- **allowed_paths**：
  - `src/agentic_loop/wrappers/dispatch_lint.sh`
  - `tests/test_dispatch_lint_brief_source.py`
- **forbidden_paths**（相对 rev1 收紧：本 rev2 不需要动 redispatch）：
  - `src/agentic_loop/redispatch.py` —— **rev1 该侧已正确，是本次的参照实现，不得改动**
  - `src/agentic_loop/wrappers/preflight.sh`（B17/B22 归 WP-27）
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/gate/__init__.py`
  - `src/agentic_loop/templates/`、`CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md`
  - `docs/plans/`（含本 brief 与全部 status JSON）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/wrappers/dispatch_lint.sh`
- `tests/test_dispatch_lint_brief_source.py`

**forbidden_paths**

- `src/agentic_loop/redispatch.py` (rev1 got this side right; reference
  implementation, must not change)
- `src/agentic_loop/wrappers/preflight.sh` (B17/B22 belong to WP-27)
- `src/agentic_loop/wrappers/finalize_merge.sh`
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/gate/__init__.py`
- `src/agentic_loop/templates/`, `CLAUDE.md`, `AGENTS.md`,
  `docs/agentic/OPERATING_MODEL.md`
- `docs/plans/` (this brief and every status JSON)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## 交付物清单

1. `dispatch_lint.sh`：sha256 校验只依赖 `evidence.brief.sha256` **在场**，
   与 `evidence.brief.path` 是否在场**无关**。参照 `redispatch.py._brief_content()`
   的结构 —— 校验块在 declared/fallback 分支**汇合之后**，不在任一分支内部。
   两条路径的拒收措辞与退码必须一致（`DISPATCH_LINT_FAIL: brief sha256 mismatch:
   computed=… declared=…`，rc=2）。
2. 补齐**四种在场组合**的用例矩阵（这是本 rev2 的核心交付物）：

   | `path` | `sha256` | 期望 |
   |---|---|---|
   | 缺 | 缺 | PASS，走固定命名（rev1 已有，保留） |
   | 在 | 缺 | PASS，lint 声明路径（rev1 已有，保留） |
   | 缺 | 在场且**错** | **FAIL**，`brief sha256 mismatch` + 双值（**新增，本次缺陷**） |
   | 缺 | 在场且**对** | **PASS**（**新**，上一格的正向对照，防止「无 path 一律拒收」这种过度修正冒充修好） |
   | 在 | 在场且错 | FAIL（rev1 已有，保留） |
   | 在 | 在场且对 | PASS（rev1 已有，保留） |

3. 把 `test_forbidden_mutation_fixed_name_reverts_red` 的**原地改写活树脚本**
   改成 WP-27 的做法：`shutil.copytree` 整个 `src/agentic_loop/wrappers/` 到
   `tmp_path` 下的 scratch 目录，在**副本**上做变异并从副本执行，活树脚本零改动。
   参照实现：`tests/test_preflight_status_source.py`
   的 `test_bare_status_assignment_reverts_to_worktree`（WP-27 工作树）。
   变异后须断言活树脚本 sha256 与变异前逐字节相同。
4. 清掉重复的空诊断行：内层 python 的 `fail()` 把消息写 stderr 后 `SystemExit(0)`，
   外层 `brief_ok` 读 stdout 第一行得空串，于是 `fail "$brief_ok"` 又打一行
   空的 `DISPATCH_LINT_FAIL: `。原因特异的消息与 rc=2 都不受影响
   （编排者与第二签名独立判定为**非阻塞的诊断噪声**），但既然本次要动这段，顺手清掉。
   清理后须断言：任一失败路径的 stderr 里 `DISPATCH_LINT_FAIL:` 恰好出现**一次**。

## Acceptance tests

- **The new blocking case must invert.** A status declaring a WRONG
  `evidence.brief.sha256` and NO `evidence.brief.path` must FAIL with
  `brief sha256 mismatch` printing both values. Today it passes rc=0 — assert
  the inversion, and pair it with the positive control below.
- **Positive control on the same combination**: the same status shape with a
  CORRECT sha256 and no `path` must PASS. Without this control, "refuse whenever
  `path` is absent" would masquerade as a fix and silently break the
  zero-regression fallback.
- **All four presence combinations of (`path`, `sha256`) must be covered**, per
  the matrix in deliverable 2. This is the coverage shape B21 named: enumerate
  by field PRESENCE, not by refusal REASON — the four rev1 refusal reasons all
  lived in the `path`-present half, which is exactly how this hole survived.
- Every rev1 behaviour in the "must not change" table above stays green,
  unchanged.
- **The forbidden mutation must not touch the live tree.** After the mutation
  test runs, assert the live `dispatch_lint.sh` sha256 equals its pre-run value.
  The mutation itself must still turn the declared-path test red on the scratch
  copy, then the scratch copy is discarded (no restore step to get wrong).
- Exactly one `DISPATCH_LINT_FAIL:` line per failure path in stderr.
- Each negative assertion carries the oracle three items:
  1. positive reachability control on the same fixture;
  2. a cause-specific witness with a `file:line` print point in the
     authoritative source — and note the same-wording hazard (B11): if two
     causes print identically, use a differential pair instead;
  3. a representative forbidden mutation that turns the test red, on a scratch
     copy, then discarded.
- Green on 3.11, 3.13 and 3.14.
- Zero regression against the baseline recorded in this WP's status JSON.

## Completion definition

- [ ] sha256 校验只依赖 `sha256` 在场，与 `path` 是否在场无关
- [ ] 两条路径的拒收措辞与退码一致
- [ ] 四种在场组合全覆盖，含「无 `path` + 错 sha256 → FAIL」与「无 `path` + 对 sha256 → PASS」
- [ ] 变异测试改为 scratch copytree，活树脚本 sha256 变异前后逐字节相同
- [ ] 重复的空 `DISPATCH_LINT_FAIL: ` 行已清除，每条失败路径恰好一行
- [ ] rev1 已通过的全部行为不变（见「不得改动」表）
- [ ] `redispatch.py` **零 diff**
- [ ] `CONTRACT_TEMPLATE_VERSION` 不涉及本 WP，不得改动
- [ ] 每条负面断言带 oracle 三项，含一个 scratch 上能转红的 forbidden 变异
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

1. **不要用「无 `path` 一律拒收」当修法**。那会打掉零回归的固定命名回退
   （仓里现存 status 大多两字段都无）。判据是 `sha256` 在场与否，不是 `path`。
2. **不要重构 rev1 的解析器**。rev1 的路径权威、逃逸拒收、双值打印都已验过，
   重构会把已验证的面重新变成未验证的面。本 rev2 的 diff 应当很小。
3. **参照实现在同一提交里**：`redispatch.py._brief_content()`
   的 `if declared_sha:` 在分支汇合之后。照抄这个位置关系，不要新造第三种结构。
4. **算不出也要拒收**。文件读不到、权限不足导致 sha256 算不出来，一律拒收，
   不得当作「无法校验所以跳过」。
5. **变异不要留在活树上**。rev1 的 `DISPATCH_LINT.write_text(mutated)` + `finally`
   覆盖不了 SIGKILL / 进程崩溃 / 并行读到坏脚本。改 scratch copytree 后
   连 restore 步骤都不需要，也就没有 restore 写错的可能。
6. **不要用 `agentic dispatch-lint` 自证**（B14：那是落后活树的冻结副本）。
   直跑 `PYTHONPATH=src bash src/agentic_loop/wrappers/dispatch_lint.sh <status>`。
7. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。

### 口径权威源引用

- 正确的校验位置参照：`src/agentic_loop/redispatch.py` 的 `_brief_content()`
- scratch 变异的参照实现：WP-27 工作树
  `tests/test_preflight_status_source.py::test_bare_status_assignment_reverts_to_worktree`
- 缺陷实测记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B21
- rev1 冻结 brief（本 rev2 未覆盖的部分继续有效）：`WP-26-brief.md`
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`

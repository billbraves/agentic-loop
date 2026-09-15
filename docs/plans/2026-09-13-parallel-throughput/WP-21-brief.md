# WP-21: 用例契约化收尾（A33 + A29 遗留加固 + 跨版本 DoD）

> 冻结日期 2026-09-15 | 编排者 claude（claude-code） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。
> 上游：WP-19 已合并（`f9e1664`），本 WP 以合并后的 plan 分支为基线。

## 目标（一句话）

把 WP-19 遗留的两条**测试层**问题一次做完：A33 的用例仍锁死 Python 3.11/3.12 的
实现表现（3.13+ 失败），以及 `finalize_merge.sh` 那处 fail-closed 保护既无注释锁定意图、
也无用例守护；并把「异常路径用例必须跨 3.11/3.13/3.14 验收」固化为本轮 DoD。

## 为什么打成一个包

三项共享同一个判据 `path_is_in_worktree` 与同一套临时 git 仓 fixture，
且 A33 与 A29 加固都是「把隐式的版本/shell 依赖变成显式契约」这同一件事。
分开做会两次搭同样的 fixture，且两次都要跨四个解释器跑同一个文件。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `tests/test_worktree_detection.py`（A33 断言契约化；改既有用例 + 可新增）
  - `tests/test_finalize_merge_first_call.py`（A29 加固的 characterization test 落在这里）
  - `src/agentic_loop/wrappers/finalize_merge.sh`（**仅**注释与 A33 相关的不准确表述，见下；**不改任何可执行语句**）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/gate/__init__.py`（**本轮判据实现零改动**，A33 是测试脆性不是判据缺陷）
  - `src/agentic_loop/wrappers/preflight.sh`
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/independence.py`
  - `src/agentic_loop/adapters/`、`src/agentic_loop/redispatch.py`
  - `docs/`（本 brief 与 status 由编排者维护）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ `finalize_merge.sh` 在白名单里**只为改注释**。该文件的 `in_worktree` 赋值
> 及其后所有可执行语句一行都不能动——它当前的 fail-closed 行为正是要被守护的对象。

## 输入

- 上游产出：WP-19 合并提交 `f9e1664`（判据与三个测试文件已在 plan 分支上）
- 参考文档：
  - `WP-08-candidate.md` §A30、§A33（含「A33 补充：fail-open 定性不成立」）、
    §A29 的「修法 2 经实测不成立」一节
  - `WP-19-consult-codex-rev6.md` 的 P1 与第一条 P2
  - 全局规范 §4.1（仅编排者维护 status）、§5.3（口径单一权威）、§5.7（隔离执行）

## 交付物清单

### 1. A33：`test_symlink_loop_fails_closed_without_raising` 断言契约化

- [ ] `tests/test_worktree_detection.py:181` 起那个用例：把
      `assert path_is_in_worktree(loop) is True` 降为**契约级**断言——
      不抛异常 **且** `isinstance(result, bool)`。
      **必须用 `isinstance(result, bool)`**，不可写 `result in (True, False)`
      （后者会错误接受 `0`/`1`，见 codex rev6 rationale 第 1 条）。
- [ ] 同一用例的注释改写：说明 3.13 起 `Path.resolve()` 对 symlink 循环不再抛
      `RuntimeError` 而是原样返回路径，此时主区的 symlink 循环答 `False`
      **本来就是正确答案**，故契约是「不抛异常 + 返回 bool」而非某个固定值。
- [ ] **新增**一条用例：linked worktree **内部**的 symlink 循环必须判 `True`
      （编排者已在 3.11/3.13/3.14 实测该形态跨版本稳定，拒收从未被绕过）。
      这条是**检测能力的来源**，不能省——没有它，契约化后的原用例单独看是弱断言。
- [ ] 保留既有的「主区普通路径判 `False`」用例不动（与上一条共同构成非永真的证据）。

### 2. A29 遗留加固：注释锁定意图 + characterization test

- [ ] `src/agentic_loop/wrappers/finalize_merge.sh` 的 `in_worktree=$(...)` 上方补注释，
      **锁定意图**：该处必须保持**普通赋值**形态；`set -euo pipefail` 下判据非零退出
      会直接终止脚本（fail-closed）。**不得**挪进 `if` 条件、`&&`/`||` 之后，
      也不得加 `|| true` / `|| echo false`——那会挂起 `set -e`、把 fail-closed 变成 fail-open。
- [ ] `tests/test_finalize_merge_first_call.py` 新增 characterization test：
      注入一个**语法合法但调用即抛异常**的 `path_is_in_worktree`（经 `PYTHONPATH`
      覆盖 `agentic_loop.gate`，只坏该判据、不坏 `resolve_paths` / `validate_wp_status`），
      断言 finalize **退出码非 0** 且输出中**无** `FINALIZE_OK`。
      > 编排者已实测该形态：`rc=1`、无 `FINALIZE_OK`、后续步骤零执行。本条是把这个
      > 实测固化成回归防线，防止日后有人把赋值改成 if 条件内嵌。

### 3. 同一文件里 A33 相关的不准确注释

- [ ] `tests/test_worktree_detection.py` 中 `test_long_path_fails_closed_without_raising`
      的注释里有「the fail-open command-substitution call site in finalize_merge.sh
      turns a raised predicate into a skipped refusal」——该说法**不成立**（见交付物 2）。
      改为准确表述：该调用点是普通赋值，`set -e` 下判据抛异常会终止脚本，
      故为 fail-closed；判据「never raises」的契约仍有独立价值（可读性与其他调用方）。
- [ ] 全文检索该文件与 `finalize_merge.sh`，凡有「fail-open」「跳过拒收」类表述
      指向这个调用点的，一并改准确。**不要**改指向其他真实 fail-open 场景的表述。

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] **跨版本（本轮核心证据，不能省）**：用 **`python3.11`、`python3.13`、`python3.14`**
      三个解释器分别跑 `tests/test_worktree_detection.py` 与
      `tests/test_finalize_merge_first_call.py`，**三边都全绿**。
      本机缺 pytest 的解释器用
      `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`。
      > 这一条是为了不第四次漏：A33 在 rev4、rev5 两轮都因单解释器验收而逃脱。
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线**零回归**。
      基线（合并后 `f9e1664` 起）：`4 failed + 581 passed + 4 skipped`，
      4 个预存失败在 `tests/test_finalize_merge_triple_sign.py`
      （fixture 在无 `main` 分支的临时仓跑 `git checkout main`），**不要修**。
- [ ] 按缺陷 B7：用 `PYTHONPATH=src python3.11 -m pytest` 直接跑工作树代码，
      **不要**用 `agentic quality-gate` 自证（那会跑到另一个仓的快照）
- [ ] `src/agentic_loop/gate/__init__.py` 的 diff **必须为 0 行**
- [ ] `finalize_merge.sh` 的 diff **只含注释行**（可执行语句零改动）
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 不 merge、不 push、不切生产分支
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要把 3.13/3.14 改成「让它抛异常」**。判据在四版本上行为都正确
   （从不抛异常；主区 `False`、linked worktree `True`）。要改的是断言，不是判据。
2. **不要删掉用例**。A33 那条用例必须留下并降级断言，不是移除。
3. **必须用 `isinstance(result, bool)`**。`result in (True, False)` 因 `1 in (True, False)`
   为真而会接受 `0`/`1`，等于放弃类型检查。
4. **新增的 linked worktree 循环用例是检测能力来源**，省掉它就把契约化做成了弱化。
5. **`finalize_merge.sh` 只改注释**。碰任何可执行语句都会被验收驳回——
   那处 fail-closed 行为正是本轮要守护的对象。
6. **A34（symlink TOCTOU）不在本轮范围**。它需要竞态、且修法要动判据与调用时序，
   另立 WP。看到了在 `[CONCERNS]` 里申报，不要动手。
7. **不要顺手修那 4 个预存失败**（`test_finalize_merge_triple_sign.py`）。

### 口径权威源引用

- worktree 判定：`agentic_loop.gate.path_is_in_worktree`（WP-19 建立的唯一权威点，本轮只读）
- 主仓根解析：`resolve_paths --root main_repo`（既有唯一权威，不另造）
- 范围校验：`quality-gate.sh` 的 `_path_in_scope`（既有唯一权威，不另造）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_worktree_detection.py` — A33 assertion contract; edit the existing case, add one new case
- `tests/test_finalize_merge_first_call.py` — A29 hardening characterization test
- `src/agentic_loop/wrappers/finalize_merge.sh` — **comments only**; not a single executable statement may change

**forbidden_paths**

- `src/agentic_loop/gate/__init__.py` — predicate implementation must have a **zero-line diff**
- `src/agentic_loop/wrappers/preflight.sh`
- `src/agentic_loop/validate_wp_status.py` — A14/A15/A18 surface, separate WP
- `src/agentic_loop/independence.py` — A9/A5 surface, separate WP (WP-20)
- `src/agentic_loop/adapters/`, `src/agentic_loop/redispatch.py`
- `docs/` — brief and status are orchestrator-maintained
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7: it runs
another repository's snapshot).

- `tests/test_worktree_detection.py` — A33:
  - the symlink-loop case asserts the **contract** (does not raise, and
    `isinstance(result, bool)`), never a fixed value. `result in (True, False)`
    is **not acceptable** — it wrongly accepts `0`/`1`.
  - a **new** case: a symlink loop **inside** a linked worktree must be `True`
    (verified stable across 3.11/3.13/3.14). This case carries the detection
    power and must not be omitted.
  - the existing "plain main-repo path is `False`" case stays untouched.
- `tests/test_finalize_merge_first_call.py` — A29 hardening: inject a
  syntactically valid `path_is_in_worktree` that raises when called (override
  `agentic_loop.gate` via `PYTHONPATH`, breaking only the predicate and not
  `resolve_paths` / `validate_wp_status`); assert finalize exits **non-zero**
  and prints **no** `FINALIZE_OK`.
- **Cross-version (this round's core evidence, must not be skipped)**: run both
  files under `python3.11`, `python3.13` and `python3.14`; all three green.
  Use `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`
  for interpreters without pytest.
- Whole suite: `PYTHONPATH=src python3.11 -m pytest tests -q`, zero regression
  against the baseline `4 failed + 581 passed + 4 skipped`. The 4 pre-existing
  failures live in `tests/test_finalize_merge_triple_sign.py` — **do not fix them**.

## Completion definition

- [ ] Every deliverable in place
- [ ] All three interpreters (3.11 / 3.13 / 3.14) green on both target test files
- [ ] Zero regression relative to the baseline (4 known failures stay as they are)
- [ ] `src/agentic_loop/gate/__init__.py` diff is **zero lines**
- [ ] `finalize_merge.sh` diff contains **comment lines only**
- [ ] The symlink-loop case uses `isinstance(result, bool)`, not `in (True, False)`
- [ ] The new linked-worktree symlink-loop case asserts `True`
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] Commit message follows the repository convention

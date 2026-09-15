# WP-21 rev2: 修正 A29 characterization test 的空验证（A35）

> 冻结日期 2026-09-15 | 编排者 claude（claude-code） | 执行者 kimi。
> 前序：rev1（commit `6995873`）已验收，**交付物 1、3 与全部注释改动均通过，本轮不得改动**。
> 本 rev 只修一处：交付物 2 的 characterization test 是空验证（缺陷 A35）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev3 并重派）。

## 目标（一句话）

`tests/test_finalize_merge_first_call.py::test_finalize_fails_closed_when_predicate_raises`
现在用一个**不存在**的 status 路径，导致两种被明令禁止的 fail-open 变异都能通过；
换用真正可 finalize 的 status，让断言具备区分力，并做一次变异自证。

## 这是编排者的缺陷，不是你的

rev1 Brief 交付物 2 逐字规定了「断言退出码非 0 且输出中无 `FINALIZE_OK`」这两条断言，
你严格照做，用例写得干净、前提断言齐备（影子包不影响 `resolve_paths` /
`validate_wp_status` 从真实 src 加载，这点做得对，保留）。**缺陷在用例设计。**

## 前置事实（编排者已实测，不必重做，**不得与之矛盾**）

用例现状传的是 `docs/plans/wp19-first-call/WP-FC.status.json`，而测试只
`repo.mkdir()` + init 一个 README，**从未创建该 status**。于是判据崩掉后脚本继续走到
下一步 `FINALIZE_FAIL: status file not found` 并 `exit 2`，两条断言照样成立：

| 形态 | status 缺失（现状） | 真实可 finalize 的 status |
|------|:---:|:---:|
| A 普通赋值（现行，应通过） | rc=1 → **PASS** | rc=1，无 `FINALIZE_OK` → **PASS** |
| B `\|\| echo false`（禁止） | rc=2 → **PASS ← 空过** | rc=0，**有** `FINALIZE_OK` → **FAIL ✅** |
| C 挪进 `if` 条件（禁止） | rc=2 → **PASS ← 空过** | rc=0，**有** `FINALIZE_OK` → **FAIL ✅** |

变异 B 的输出里明确打印了 `false` 并**跳过了 worktree 拒收**——正是用例该锁住的行为。

## 范围

- **allowed_paths**：
  - `tests/test_finalize_merge_first_call.py`（**仅** `test_finalize_fails_closed_when_predicate_raises`
    这一个函数体，及必要的 import；不得改同文件其他用例与 fixture 的行为）
- **forbidden_paths**（本轮全部只读，含 rev1 已通过的产物）：
  - `src/agentic_loop/wrappers/finalize_merge.sh`（rev1 的 6 行注释已通过，**0 行 diff**）
  - `tests/test_worktree_detection.py`（rev1 交付物 1、3 已通过，**0 行 diff**）
  - `src/agentic_loop/gate/__init__.py`（**0 行 diff**）
  - `src/agentic_loop/wrappers/preflight.sh`、`src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/independence.py`、`src/agentic_loop/adapters/`、`src/agentic_loop/redispatch.py`
  - `docs/`、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## 交付物清单

- [ ] 改 `test_finalize_fails_closed_when_predicate_raises`：用同文件**既有** fixture
      造一个真正可 finalize 的 status——`_make_repo_with_merged_wp()` +
      `_status_without_merged_commit()`，写入 `docs/plans/wp19-first-call/WP-FC.status.json`
      并 `git add` + `commit`（preflight/finalize 要求 status 在主仓索引里）。
      **不要**新写一份 fixture（§5.3：同文件已有唯一权威的造仓/造 status 点）。
- [ ] 保留现有的前提断言（影子包只坏判据、不坏 `resolve_paths` /
      `validate_wp_status`）——那一段是对的。
- [ ] 断言维持「`rc != 0` 且输出无 `FINALIZE_OK`」，此时它已具备区分力。
      **额外加一条正面对照**：同一 status、**不注入**影子包时 finalize 应
      `FINALIZE_OK`（证明用例走到了终点，而非在更早一步失败）。
- [ ] **变异自证（本轮核心证据，不能省）**：把下面两种形态**真的**写进
      `finalize_merge.sh`，各跑一次该用例，确认**用例变红**，然后**还原**
      （`git diff` 必须回到 0 行）：
      1. 在 `in_worktree=$(...)` 的 `)` 后追加 ` || echo false`
      2. 把赋值挪进 `if` 条件：`if in_worktree=$(...); then :; else in_worktree=false; fi`
      把两次「变红」的实际输出（rc 与是否出现 `FINALIZE_OK`）写进 `[TESTS]`。
      > ⚠️ 变异只是**临时**实验手段。提交前必须还原，`finalize_merge.sh` 的
      > diff 相对 `6995873` **必须为 0 行**。

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] **跨版本**：`tests/test_finalize_merge_first_call.py` 在 **python3.11、3.13、3.14**
      三个解释器全绿（缺 pytest 的用
      `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`）
- [ ] 变异自证两次都**变红**，且已还原
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线
      `4 failed + 583 passed + 4 skipped` **零回归**（那 4 个
      `test_finalize_merge_triple_sign.py` 预存失败**不要修**）
- [ ] 按缺陷 B7：直接跑工作树代码，**不要**用 `agentic quality-gate` 自证
- [ ] `finalize_merge.sh`、`tests/test_worktree_detection.py`、`gate/__init__.py`
      相对 `6995873` 的 diff **均为 0 行**
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

1. **不要改 rev1 已通过的东西**。`finalize_merge.sh` 的 6 行注释、
   `test_worktree_detection.py` 的 A33 契约化 + 新增 worktree 循环用例 + 注释修正，
   全部已验收通过，本轮 0 行 diff。
2. **不要新造 fixture**。同文件已有 `_make_repo_with_merged_wp` /
   `_status_without_merged_commit`，直接用。
3. **status 必须提交进索引**。finalize 链路要求 status 在主仓索引里；只写文件不
   `git add`+`commit` 会在更早一步失败，用例又会退化成空验证。
4. **变异实验必须还原**。提交前 `git diff -- src/agentic_loop/wrappers/finalize_merge.sh`
   必须为空。
5. **否定式断言要配正面对照**。这是 A35 的教训：只断言「rc != 0」无法区分
   「被拦住」与「压根没走到」。

### 口径权威源引用

- worktree 判定：`agentic_loop.gate.path_is_in_worktree`（WP-19 建立的唯一权威，本轮只读）
- 造仓 / 造 status：`tests/test_finalize_merge_first_call.py` 内既有 fixture（唯一权威，不另造）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_finalize_merge_first_call.py` — **only** the body of
  `test_finalize_fails_closed_when_predicate_raises` (plus any needed imports);
  do not change the behavior of the other cases or the shared fixtures

**forbidden_paths** (everything rev1 already delivered is read-only this round)

- `src/agentic_loop/wrappers/finalize_merge.sh` — rev1's 6 comment lines are
  accepted; **zero-line diff** against `6995873`
- `tests/test_worktree_detection.py` — rev1 deliverables 1 and 3 accepted;
  **zero-line diff**
- `src/agentic_loop/gate/__init__.py` — **zero-line diff**
- `src/agentic_loop/wrappers/preflight.sh`, `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/independence.py`, `src/agentic_loop/adapters/`,
  `src/agentic_loop/redispatch.py`
- `docs/`, `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7).

- `test_finalize_fails_closed_when_predicate_raises`, rebuilt on a **real
  finalizable** status via the existing `_make_repo_with_merged_wp()` and
  `_status_without_merged_commit()` fixtures, the status written **and
  committed** into the repo index:
  - with the broken-predicate shadow package injected: non-zero exit and
    `FINALIZE_OK` absent from both stdout and stderr
  - **positive control**: the same status without the injection reaches
    `FINALIZE_OK` (proves the case runs to the end rather than dying earlier)
  - the existing premise assertions (the shadow breaks only the predicate,
    while `resolve_paths` and `validate_wp_status` still import from real src)
    stay as they are
- **Mutation self-check** (core evidence, do not skip): temporarily apply each
  forbidden form to `finalize_merge.sh` — appending ` || echo false` after the
  substitution's `)`, and moving the assignment into an `if` condition — run the
  case each time, confirm it **goes red**, then revert so the file's diff
  against `6995873` is zero lines. Record both red runs (rc, and whether
  `FINALIZE_OK` appeared) in `[TESTS]`.
- **Cross-version**: `tests/test_finalize_merge_first_call.py` green under
  python3.11, 3.13 and 3.14.
- Whole suite: zero regression against the baseline
  `4 failed + 583 passed + 4 skipped`. The 4 pre-existing
  `test_finalize_merge_triple_sign.py` failures stay exactly as they are —
  **do not fix them**.

## Completion definition

- [ ] Every deliverable in place
- [ ] All three interpreters green on the target test file
- [ ] Both mutations confirmed **red**, and reverted
- [ ] Zero regression against `4 failed + 583 passed + 4 skipped`
- [ ] `finalize_merge.sh`, `tests/test_worktree_detection.py` and
      `gate/__init__.py` all have **zero-line** diffs against `6995873`
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] Commit message follows the repository convention

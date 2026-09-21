# WP-23: 根解析也不再继承调用者的仓库选择（A26）

> 冻结日期 2026-09-15 | 编排者 claude（claude-code） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）

`resolve_paths._git()` 直接继承环境，`GIT_DIR` / `GIT_COMMON_DIR` 可把
「主仓根」改指到任意无关仓库；把 A22 已有的净化口径**下沉**到 `resolve_paths`，
让判据与根解析共用同一份净化，且不产生反向依赖。

## 前置事实（编排者已实测，不必重做，**不得与之矛盾**）

用**无关仓**（与本仓无任何关系的临时仓）实测 `resolve_paths --root main_repo`：

| 环境变量 | 输出 | 判定 |
|---------|------|------|
| （无） | `/Users/admin/vibe/agentic_loop` | 基准 |
| `GIT_DIR=<无关仓>/.git` | `<无关仓>` | **被改指** |
| `GIT_COMMON_DIR=<无关仓>/.git` | `<无关仓>` | **被改指** |
| `GIT_WORK_TREE=<无关仓>` | 主仓 | 不受影响 |
| `GIT_CEILING_DIRECTORIES=/Users/admin/vibe` | 主仓 | 不受影响 |

> ⚠️ **探针陷阱**：用 **linked worktree 的 `.git`** 当 `GIT_DIR` 会得到假阴性
> （该 worktree 的 git-common-dir 本就指向主仓，缺陷存在时也返回正确答案）。
> 你的测试**必须**用无关仓，否则用例是空验证（缺陷 A35 同族）。

**已核实的两件事，直接决定范围**：

1. `_GIT_SELECTION_VARS`（`gate/__init__.py:187`）**已含全部 7 个变量**，
   两条活通道都在其中 → **不需要新增集合、不需要新写判据**。
2. 依赖方向：`gate/__init__.py:44-48` **已经** import `resolve_paths`；
   `resolve_paths` 不 import `gate`。→ 净化集合与净化动作必须**下沉到
   `resolve_paths`**，由 `gate` 引用；**严禁**让 `resolve_paths` 反向 import
   `gate`（§5.1 依赖方向）。

## 范围

- **allowed_paths**：
  - `src/agentic_loop/resolve_paths.py`（`_git()` 净化 + 承接下沉的净化口径）
  - `src/agentic_loop/gate/__init__.py`（**仅**把 `_GIT_SELECTION_VARS` 改为引用
    下沉后的唯一权威；`path_is_in_worktree` 的判定逻辑与行为**零改动**）
  - `tests/test_resolve_paths_env_sanitization.py`（新建）
- **forbidden_paths**：
  - `src/agentic_loop/wrappers/`（**全部** 11 个 `.sh` 的裸 `git rev-parse` 不在本轮，
    见下方「明确不做」）
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/independence.py`、`src/agentic_loop/adapters/`、
    `src/agentic_loop/redispatch.py`
  - `docs/`、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

### 明确不做（不是遗漏）

wrapper 侧共 11 个 `.sh` 有裸 `git rev-parse --git-common-dir`，都在构造
`PYTHONPATH` **之前**跑。那条链有**自举顺序问题**：要先有 `PYTHONPATH` 才能调
Python 模块，而 `PYTHONPATH` 正是用这条 `rev-parse` 算出来的。本 WP **不碰**它，
单独评估。看到了在 `[CONCERNS]` 申报，不要动手。

## 交付物清单

- [ ] `resolve_paths.py`：净化集合（沿用 A22 的 7 个变量，语义与注释一并搬来）
      与净化动作下沉到此模块，成为**唯一权威**；`_git()` 是该模块唯一的 git 调用
      出口，改为不继承这些变量。
- [ ] `gate/__init__.py`：`_GIT_SELECTION_VARS` 改为**引用**下沉后的权威
      （import 或别名），不再各留一份字面集合。
      `path_is_in_worktree` 的行为**零改动**——它的现有测试必须全部照旧通过。
- [ ] `tests/test_resolve_paths_env_sanitization.py`：
      - 造一个**无关**临时 git 仓（不是 linked worktree）
      - `GIT_DIR=<无关仓>/.git` 时 `main_repo()` 仍返回真实主仓
      - `GIT_COMMON_DIR=<无关仓>/.git` 时同样
      - 7 个变量逐个覆盖（其余 5 个本就不改指，锁住「不回归」）
      - `current_worktree()` 同样不被改指
      - **正面对照**：无环境变量时返回值与净化后一致（证明净化没把正常路径改坏）
- [ ] **变异自证（核心证据，不能省）**：把 `_git()` 的净化临时去掉，跑新测试，
      确认**变红**，再还原（`git diff` 回到 0 行）。把变红的实际输出写进 `[TESTS]`。

## 完成定义（DoD）

- [ ] 交付物逐项就绪；A26 有一个失败→通过的测试
- [ ] 净化口径在仓里**只有一份**，`gate` 与 `resolve_paths` 都引用它（§5.3）
- [ ] `resolve_paths` **不** import `gate`（§5.1，用 grep 自证并写进报告）
- [ ] `tests/test_worktree_detection.py` 与 `tests/test_finalize_merge_first_call.py`
      **全部照旧通过**（`path_is_in_worktree` 行为零改动的证据）
- [ ] **跨版本**：新测试 + 上述两个既有测试在 **python3.11、3.13、3.14** 三边全绿
      （缺 pytest 的用 `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`）
- [ ] 变异自证已做且已还原
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线**零回归**
      （基线由编排者在派发时写入 status；那 4 个
      `test_finalize_merge_triple_sign.py` 预存失败**不要修**）
- [ ] 按缺陷 B7：直接跑工作树代码，**不要**用 `agentic quality-gate` 自证
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

1. **测试必须用无关仓**。linked worktree 的 `.git` 会给假阴性（见前置事实）。
2. **不要反向依赖**。`resolve_paths` 不能 import `gate`。
3. **不要新造净化集合**。7 个变量已齐，搬下来、两处共用。
4. **不要碰 wrapper**。11 个裸 `rev-parse` 有自举顺序问题，另评估。
5. **`path_is_in_worktree` 零行为改动**。它的判定逻辑本轮只改「集合从哪来」。
6. **净化要作用于实际调用**：`subprocess.run` 不传 `env=` 就继承整个环境；
   传了 `env=` 则**其余**变量也要一并传下去（`PATH`、`HOME` 等），否则 git 可能跑不起来。
   这一条容易写成「净化成功但 git 失败」，测试的正面对照就是防它的。

### 口径权威源引用

- git 环境净化：本 WP 下沉建立唯一权威（`resolve_paths`），`gate` 引用它
- worktree 判定：`agentic_loop.gate.path_is_in_worktree`（既有唯一权威，行为不改）
- 主仓根解析：`resolve_paths --root main_repo`（既有唯一权威，本 WP 加固它）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/resolve_paths.py` — sanitize `_git()`; host the sanitization
  authority moved down from `gate`
- `src/agentic_loop/gate/__init__.py` — **only** to make `_GIT_SELECTION_VARS`
  reference the moved-down authority; `path_is_in_worktree` behavior unchanged
- `tests/test_resolve_paths_env_sanitization.py` (new)

**forbidden_paths**

- `src/agentic_loop/wrappers/` — all 11 shell wrappers with a bare
  `git rev-parse --git-common-dir`; that chain has a bootstrap-ordering problem
  (the `PYTHONPATH` needed to call Python is computed *by* that rev-parse) and is
  evaluated separately. Report it under `[CONCERNS]`, do not touch it.
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/independence.py`, `src/agentic_loop/adapters/`,
  `src/agentic_loop/redispatch.py`
- `docs/`, `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7).

- `tests/test_resolve_paths_env_sanitization.py`, built on an **unrelated**
  temporary git repo (never a linked worktree — a worktree's git-common-dir
  already points at the main repo, so it yields a false negative even when the
  defect is present, defect-A35 family):
  - `GIT_DIR=<unrelated>/.git` → `main_repo()` still returns the real main repo
  - `GIT_COMMON_DIR=<unrelated>/.git` → same
  - all 7 variables of the sanitization set covered
  - `current_worktree()` likewise not redirected
  - **positive control**: with no variables set, the value matches the sanitized
    result (proves sanitization did not break the normal path, e.g. by dropping
    `PATH`/`HOME` from the subprocess environment)
- **Mutation self-check** (core evidence, do not skip): temporarily remove the
  sanitization from `_git()`, run the new test, confirm it goes **red**, then
  revert to a zero-line diff. Record the red run in `[TESTS]`.
- `tests/test_worktree_detection.py` and `tests/test_finalize_merge_first_call.py`
  must pass **unchanged** — evidence that `path_is_in_worktree` behavior did not move.
- **Cross-version**: the new test plus those two existing files green under
  python3.11, 3.13 and 3.14.
- Whole suite: zero regression against the baseline recorded in the status JSON
  at dispatch time. The 4 pre-existing `test_finalize_merge_triple_sign.py`
  failures stay exactly as they are — **do not fix them**.

## Completion definition

- [ ] Every deliverable in place; A26 has one failing-to-passing test
- [ ] The sanitization set exists in exactly **one** place, referenced by both
      `resolve_paths` and `gate` (global rule §5.3)
- [ ] `resolve_paths` does **not** import `gate` (§5.1); prove it by grep in the report
- [ ] `path_is_in_worktree`'s existing tests all still pass
- [ ] All three interpreters green on the new and the two existing test files
- [ ] Mutation self-check performed and reverted
- [ ] Zero regression relative to the recorded baseline
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] Commit message follows the repository convention

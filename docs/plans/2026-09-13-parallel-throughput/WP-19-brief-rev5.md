# WP-19 rev5 Brief（第 6 轮代码修订）：修正 A30，用例锁契约而非实现路径

> 冻结日期 2026-09-15 | 编排者 claude（claude-code） | 执行者 kimi。
> 前序提交 `77941f4`（rev5，闭合 A29）。基线由编排者派发时写入 `git.base_commit`。
> 冻结后执行期间不得修改；需修订走 re-freeze。

## 目标（一句话）

把 `test_long_path_fails_closed_without_raising` 的断言从「实现路径」改成「契约」，
使它在 Python 3.11–3.14 全部支持版本上都成立。**判据代码一行都不许动。**

## 为什么只改一行断言

A29 的契约是「`path_is_in_worktree` 对任意输入都不抛异常」。
rev5 的判据修复已闭合该契约——编排者用四个解释器实测确认：

| Python | `Path(300字符).resolve().is_dir()` | 主区超长路径 | linked worktree 内超长路径 |
|--------|-----------------------------------|-------------|--------------------------|
| 3.11.14 | `OSError: [Errno 63]` | `True` | `True` |
| 3.12.14 | `OSError: [Errno 63]` | `True` | `True` |
| 3.13.12 | `OSError: [Errno 63]` | `True` | `True` |
| 3.14.2 | **`False`（不再抛）** | **`False`** | `True` |

3.14 起 `is_dir()` 对超长名返回 `False` 而不抛 `OSError`。此时判据走正常 git 路径，
主区答 `False` **本来就是对的**。但用例断言 `is True`，于是在 3.14 上失败。

`pyproject.toml:8` 声明 `requires-python = ">=3.9"`，3.14 在支持范围内，
所以这是一个「新增用例在声明支持的解释器上失败」的真问题，不能推给下一个 WP。

codex 的 rev5 verdict 是 `REWORK`，P1 就是这一条；P0 为无
（判据修复本身经其独立复核成立）。详见 `WP-19-consult-codex-rev5.md`。

## 范围

- **allowed_paths**（白名单，只能改这一个文件）：
  - `tests/test_worktree_detection.py`
- **forbidden_paths**（绝不能碰，看到了在 `[CONCERNS]` 里申报，不要动手）：
  - `src/agentic_loop/gate/__init__.py` ← **本轮判据代码零改动，这是硬要求**
  - `src/agentic_loop/wrappers/finalize_merge.sh`（A29 修法 2，另立 WP）
  - `src/agentic_loop/wrappers/preflight.sh`
  - `src/agentic_loop/wrappers/codex_merge_gate.sh`
  - `src/agentic_loop/resolve_paths.py`（A26，另立 WP）
  - `src/agentic_loop/cli.py`
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/independence.py`
  - `docs/`（brief 与 status 由编排者维护）
  - `.agentic/`

## 交付物清单

- [ ] `tests/test_worktree_detection.py::test_long_path_fails_closed_without_raising`
      改为只锁契约。断言应为「调用不抛异常，且返回一个 `bool`」，
      **不得**断言主区超长路径必然为 `True`。
- [ ] 追加一条 **linked worktree 内**超长路径的用例，断言 `is True`。
      该形态四个版本实测都稳定为 `True`，可以放心锁死。
      （fixture 用现有 `git worktree add` 那套，不要新造脚手架。）
- [ ] 现有其余 16 个用例（含 `test_null_byte_path_fails_closed_without_raising`）
      **零改动**。NUL 用例锁的是真契约，codex 明确认可，不要碰。

## 完成定义（DoD）

- [ ] `git diff <base>..HEAD --stat` 只出现 `tests/test_worktree_detection.py` 一个文件
- [ ] `src/agentic_loop/gate/__init__.py` diff **为空**（本轮硬要求，会被逐字节核）
- [ ] `PYTHONPATH=src python3.11 -m pytest tests/test_worktree_detection.py -q` 全绿
- [ ] **跨版本**：用 `python3.11` 与 `python3.14` 两个解释器分别跑
      `tests/test_worktree_detection.py`，两边都全绿。
      3.14 若缺 pytest，就写一段等价的 `python3.14 -c` 直呼断言脚本证明，
      并把两边输出贴进 `[TESTS]`。**这一条是本轮的核心证据，不能省。**
- [ ] 全套 `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线零回归。
      基线（`77941f4`）为 **4 failed + 580 passed + 4 skipped**；
      4 个 `test_finalize_merge_triple_sign.py` 失败是预存 B7（临时仓无 `main` 分支），
      **不要修**。用例数可因你新增用例而 +1。
- [ ] 无 forbidden_paths 写入；不 merge、不 push、不 amend、不切分支
- [ ] 无生产写入、无网络、无通知
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

1. **不要"顺手"改判据让 3.14 也抛异常**。判据行为是对的，错的是断言。
   任何对 `gate/__init__.py` 的改动都会被判返工。
2. **不要删掉超长路径用例了事**。它仍有价值——证明超长输入不会让判据崩。
   只是断言要从「必然 True」降到「不抛且返回 bool」。
3. **不要用 mock 替掉真实超长路径**。codex 的 P2 提了「确定性触发 OSError」
   这个可选方向，但本轮选定的修法是「真实路径 + 契约级断言 + 补 worktree 形态用例」，
   两者不要混做。
4. **`is True` 与 `== True` 不等价于「是 bool」**。要断言类型就用
   `isinstance(result, bool)`，不要写 `assert result in (True, False)`
   （`1 in (True, False)` 为真，锁不住类型）。
5. **不要碰 NUL 用例**。它跨版本稳定、锁的是真契约。

### 口径权威源引用

- worktree 判定：`gate/__init__.py::path_is_in_worktree`（**本轮只读，不改**）
- A29 契约原文：该函数 docstring「never raises」段
- A30 事实依据：`WP-08-candidate.md` §A30 的四版本实测表

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配）。

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_worktree_detection.py` — assertion fix only (A30)

**forbidden_paths**

- `src/agentic_loop/gate/__init__.py` — **zero diff required this round**; the
  predicate fix is already correct and independently confirmed on four interpreters
- `src/agentic_loop/wrappers/finalize_merge.sh` — A29 fix 2, separate WP
- `src/agentic_loop/wrappers/preflight.sh`, `codex_merge_gate.sh`
- `src/agentic_loop/resolve_paths.py` — A26, separate WP
- `src/agentic_loop/cli.py`, `validate_wp_status.py`, `independence.py`
- `docs/`, `.agentic/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7).

- `test_long_path_fails_closed_without_raising` — must assert the **contract**
  (the call does not raise and returns a `bool`), never that a main-repo overlong
  path is `True`. On Python 3.14 `is_dir()` returns `False` for an overlong name,
  so the predicate correctly classifies the path and answers `False`.
- A new case for an overlong path **inside a linked worktree** — asserts `True`.
  Measured stable across 3.11.14 / 3.12.14 / 3.13.12 / 3.14.2.
- The other 16 cases, including
  `test_null_byte_path_fails_closed_without_raising`, stay byte-identical.
- **Cross-version evidence (mandatory)**: run the file under `python3.11` and
  `python3.14`; both green. If 3.14 lacks pytest, supply an equivalent direct
  assertion script and paste both outputs into `[TESTS]`.
- Whole suite: zero regression against the `77941f4` baseline of
  `4 failed + 580 passed + 4 skipped`; the 4 pre-existing
  `test_finalize_merge_triple_sign.py` failures must **not** be fixed.

## Completion definition

- [ ] Diff touches exactly one file: `tests/test_worktree_detection.py`
- [ ] `src/agentic_loop/gate/__init__.py` diff is **empty**
- [ ] Both `python3.11` and `python3.14` are green on the test file
- [ ] Zero regression on the whole suite (4 known failures stay as they are)
- [ ] No writes to forbidden_paths, no merge, no push, no amend
- [ ] Commit message follows the repository convention

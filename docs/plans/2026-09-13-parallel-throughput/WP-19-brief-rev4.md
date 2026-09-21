# WP-19 rev4 Brief（返工：闭合 A29）

> 冻结日期 2026-09-15 ｜ 编排者 claude（claude-code） ｜ 执行者 kimi。
> 基线 commit `d7e90fa`。冻结后执行期间不得修改。
>
> **命名**：本文件是第四份冻结 Brief，对应第五轮代码修订。正文称本轮为 **rev5**。

## 目标（一句话）

把 `path_is_in_worktree` 最后一处 unguarded 文件系统调用收进守卫，
使 docstring 自陈的「never raises」真实成立——因为调用点是 fail-open 的，
判据抛异常等于把 worktree 拒收整道门绕开。

## 为什么这是 P0 而不是洁癖

`finalize_merge.sh:42-51` 用命令替换读判据结果，判据抛异常 -> stdout 空 ->
`in_worktree` 空串 -> `!= "true"` -> **拒收被跳过**。实测（超长路径，真实命令替换）：

```
in_worktree=[<EMPTY>]
NOT REFUSED (fail-open)
```

方向与 fail-closed 要求相反。

## 范围

- **allowed_paths**：
  - `src/agentic_loop/gate/__init__.py`（**仅** `path_is_in_worktree` 一处）
  - `tests/test_worktree_detection.py`（**追加**，现有 15 用例一条都不能删/改）
- **forbidden_paths**：
  - `src/agentic_loop/wrappers/finalize_merge.sh` —— **调用点的 fail-open 属 A29 修法 2，
    另立 WP，本轮不修**。看到了在 `[CONCERNS]` 申报。
  - `src/agentic_loop/resolve_paths.py`、`cli.py`、`wrappers/codex_merge_gate.sh` —— A26 的面
  - `src/agentic_loop/wrappers/preflight.sh`、`validate_wp_status.py`、`independence.py`、
    `adapters/`、`redispatch.py`
  - `docs/`、`.agentic/`
  - `gate/__init__.py` 里除 `path_is_in_worktree` 之外的一切（特别是 `main()`）

## 交付物清单

### A29-1：`is_dir()` 必须在守卫内

- [ ] `gate/__init__.py:253` 的 `directory = resolved if resolved.is_dir() else resolved.parent`
      移进 try。`is_dir()` 会 `os.stat()`，超长路径抛 `OSError: [Errno 63]`。
      这一行当前在所有 try 之外。**rev3 同样会抛，是既有洞，不是 rev4 回归**。

### A29-2：except 扩到 `ValueError`

- [ ] 三处守卫的 except 统一扩为 `(OSError, RuntimeError, ValueError)`。
      `resolve()` 对含 NUL 的路径抛 `ValueError`（rev4 把 `resolve()` 前移后新增的路径；
      rev3 在同输入返回 `False` 不抛）。
- [ ] 三处守卫**保持同一形式**（§5.3），不要一处写两种 except。

### 测试（追加）

- [ ] `test_long_path_fails_closed_without_raising` —— 真实超长路径（约 300 字符文件名）
      判 `True` 且不抛。这条**改前会失败**（当前抛 `OSError`）。
- [ ] `test_null_byte_path_fails_closed_without_raising` —— `Path("...a\x00b.json")`
      判 `True` 且不抛。这条**改前会失败**（当前抛 `ValueError`）。
- [ ] 现有 15 用例零改动，特别是 A22 回归保护与 PATH 对比用例。

## 完成定义（DoD）

- [ ] 两条新测试各自「改前失败、改后通过」，报告里给出改前的失败输出
- [ ] `path_is_in_worktree` 对**任何**输入都不抛异常
- [ ] 语义不变：主区真实文件仍 `False`，worktree 内真实文件仍 `True`，
      A27 的 symlink 归属结论不变
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 零回归。
      基线 = `d7e90fa` 的 `4 failed + 580 passed + 4 skipped`
      （注：`4 failed + 578 passed` 是 rev4 提交时的数字；本轮开始前请自己先跑一次记下实际基线）。
      那 4 个 `test_finalize_merge_triple_sign.py` 失败是预存的（缺陷 B7），**不要修**。
- [ ] 签名仍 `(path: Path) -> bool`，无新增可选参数
- [ ] `finalize_merge.sh` 等 forbidden 面 diff 为空
- [ ] 不 merge、不 push、不切分支、不 amend
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

1. **不要顺手修 `finalize_merge.sh` 的 fail-open**。那是 A29 修法 2，
   属 wrapper 面（与 A26 同批），须重新冻结范围。本轮只让判据不抛。
2. **`ValueError` / `RuntimeError` 都不是 `OSError` 子类**。三者都要列。
3. **不要为了「不抛」把整个函数体包一个大 try**。那会把 A28-1 的
   `return True` 判断也吞进去，掩盖真实逻辑。守卫要贴着文件系统调用。
4. **A26 / A25 本轮都不修**，见前几轮 Brief 的同名条目。

### 口径权威源引用

- worktree 判定：`agentic_loop.gate.path_is_in_worktree`（唯一权威点）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/gate/__init__.py` — **`path_is_in_worktree` only**
- `tests/test_worktree_detection.py` — append to the existing 15 cases

**forbidden_paths**

- `src/agentic_loop/wrappers/finalize_merge.sh` — A29 fix 2 (call-site fail-open),
  separate WP; report in `[CONCERNS]`, do not fix
- `src/agentic_loop/resolve_paths.py`, `cli.py`, `wrappers/codex_merge_gate.sh` — A26 surface
- `src/agentic_loop/wrappers/preflight.sh`, `validate_wp_status.py`, `independence.py`,
  `adapters/`, `redispatch.py`
- `docs/`, `.agentic/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7).

- `test_long_path_fails_closed_without_raising` — a real ~300-character filename
  answers `True` and must not raise (currently raises `OSError: [Errno 63]`)
- `test_null_byte_path_fails_closed_without_raising` — a path containing `\x00`
  answers `True` and must not raise (currently raises `ValueError`)
- All 15 existing cases keep passing unchanged, including the A22 regression
  guard and the PATH contrast case
- Whole suite: zero regression against baseline `d7e90fa`; the 4 pre-existing
  `test_finalize_merge_triple_sign.py` failures stay as they are — **do not fix them**

## Completion definition

- [ ] Both new tests demonstrably fail before the fix and pass after
- [ ] `path_is_in_worktree` never raises, for any input
- [ ] Semantics unchanged: main-repo file `False`, worktree file `True`,
      A27 symlink ownership verdicts unchanged
- [ ] Signature stays `(path: Path) -> bool` with no new parameters
- [ ] The three guards share one form (§5.3)
- [ ] Empty diff on all forbidden paths, `finalize_merge.sh` included
- [ ] No merge, no push, no branch switch, no amend
- [ ] Commit message follows the repository convention

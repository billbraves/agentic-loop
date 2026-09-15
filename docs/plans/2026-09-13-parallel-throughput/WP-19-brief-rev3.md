# WP-19 rev3 Brief（返工：闭合 A28 + A27）

> 冻结日期 2026-09-15 ｜ 编排者 claude（claude-code） ｜ 执行者 kimi。
> 基线 commit `bbfa258`（rev2+rev3 交付物已在 `feature/wp19-wrapper-seams`）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev4 并重派）。
>
> **命名说明**：交付物历史上已有「rev2 / rev3」两轮代码修订（`31d414f` / `bbfa258`），
> 本文件是**第三份冻结 Brief**，对应第四轮代码修订。为免与已提交的 commit 混淆，
> 文件名沿用 `rev3`（Brief 序号），正文一律称本轮代码修订为 **rev4**。

## 目标（一句话）

把 codex 复审判出、编排者已独立复现的两条判据缺陷修完：
`path_is_in_worktree` 的 fail-closed 在「输出退化」与「resolve 抛异常」两条路径上
不成立（A28，P0），且它判的是路径名归属而非实际被读写文件的归属（A27）。

## 为什么必须返工

rev2 Brief 写明「输出异常 -> `True`（拒收）」与 docstring 自陈「never raises」。
两条都被实证违反：

```
空白 common_dir      -> False   （应 True）
symlink loop         -> RuntimeError 抛出（应 True，且不得抛）
主区 symlink 指 worktree -> False（应 True；后续读写跟随 symlink 操作 worktree 文件）
```

这不是新增需求，是**已冻结契约未达成**。编排者上一轮 ACCEPT 是漏判
（24 向量探测全在环境变量面，未覆盖输出解析面），已在 A28 里如实记录。

## 范围

- **allowed_paths**（只能改这些）：
  - `src/agentic_loop/gate/__init__.py`（**仅** `path_is_in_worktree` 一处判据）
  - `tests/test_worktree_detection.py`（在现有 11 用例上**追加**）
- **forbidden_paths**（绝不能碰）：
  - `src/agentic_loop/resolve_paths.py` —— **A26 的面，另立 WP**。
    即使你看到 `GIT_DIR` 能把 `--root main_repo` 改指到别的仓，也**不要动手**，
    在 `[CONCERNS]` 里申报即可。在返工里临时扩权改 forbidden path，
    比缺陷本身更坏。
  - `src/agentic_loop/cli.py`、`src/agentic_loop/wrappers/codex_merge_gate.sh` —— 同上，A26 的面
  - `src/agentic_loop/wrappers/preflight.sh`、`finalize_merge.sh` —— rev2 已定稿，本轮零改动
  - `src/agentic_loop/validate_wp_status.py`、`independence.py`、`adapters/`、`redispatch.py`
  - `docs/`、`.agentic/config.toml`、`.agentic/locks/`

> ⚠️ `gate/__init__.py` 在白名单里**只为 `path_is_in_worktree` 这一个函数**。
> 该文件同时含 WP-18 的 `collect_dispatch_proof` 与独立性判定逻辑，不得改动。
> 特别地：**不要**改 `main()`（那里调用未净化的 `main_repo()`，属 A26）。

## 交付物清单

### A28-1：输出退化必须 fail-closed

- [ ] 两行各自 `strip()` 后**均非空**才继续；任一为空 -> `return True`。
      当前只校验行数与第一行是否绝对路径，空白第二行会退化成
      `common_dir = directory / Path("")` == `directory`，判 `False`。

### A28-2：`resolve()` 不得抛异常

- [ ] 两处 `Path.resolve()` 移入 `try`，捕获 `OSError` **与** `RuntimeError`
      （symlink loop 抛的是 `RuntimeError`，不是 `OSError`），异常 -> `return True`。
- [ ] docstring 的「never raises」在改完后必须真实成立。

### A27：判实际被读写的文件，不是路径名

- [ ] 取被探测目录之前先解析路径本身，使「被判的目录」与「将被读写的文件」同一。
      建议 `os.path.realpath` / `Path.resolve()`，**且该解析同样必须 fail-closed**
      （包在 try 内，异常 -> `True`）——注意这与 A28-2 是同一类守卫，
      不要写成两份不同的处理方式（§5.3）。
- [ ] 语义保持：主区真实文件仍判 `False`，worktree 内真实文件仍判 `True`。

### 测试（追加到 `tests/test_worktree_detection.py`）

- [ ] `test_blank_common_dir_fails_closed` —— mock 一个 returncode=0、
      stdout 为 `f"{directory}\n \n"` 的进程，断言 `True`。
- [ ] `test_blank_git_dir_fails_closed` —— 第一行空白，断言 `True`。
- [ ] `test_symlink_loop_fails_closed_without_raising` —— 真实造 symlink loop，
      断言 `True` 且**不抛异常**（用 `pytest.raises` 的反面：直接调用即可，
      抛了测试自然失败）。
- [ ] `test_main_repo_symlink_to_worktree_status_is_refused` —— 真实临时仓 +
      `git worktree add`，worktree 内建 status 文件，主区建指向它的 symlink，
      断言该 symlink 判 `True`（当前判 `False`）。
- [ ] **现有 11 个用例一个都不能删、不能改断言方向**。
      特别是 `test_caller_env_combined_cannot_disguise_worktree_path`（A22 回归保护）
      与那条 PATH 对比用例。

## 完成定义（DoD）

- [ ] 四条新测试各自「改前失败、改后通过」——请在报告里给出改前的失败输出
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线零回归。
      **基线 = `bbfa258` 的 `4 failed + 574 passed + 4 skipped`**。
      那 4 个 `test_finalize_merge_triple_sign.py` 失败是预存的（fixture 在无 `main`
      分支的临时仓跑 `git checkout main`，缺陷 B7），**不要修**。
- [ ] 判据仍是唯一权威（§5.3），签名仍为 `(path: Path) -> bool`，
      **不得**新增 `env` / `resolve` 之类的可选参数把语义交给调用方
- [ ] 无 forbidden_paths / 跨 owner 写入；`preflight.sh`、`finalize_merge.sh`、
      `cli.py`、`resolve_paths.py` 的 diff 必须为空
- [ ] 不 merge、不 push、不切生产分支、不 amend 已有 commit（新提交叠加）
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

1. **fail-closed 的方向是「不确定就拒收（True）」**。改完后若某个合法主区路径
   开始判 `True`，那是回归，不是变严——现有 11 用例里有主区判 `False` 的断言，
   它们必须继续通过。
2. **`RuntimeError` 不是 `OSError` 的子类**。只 `except OSError` 抓不到 symlink loop。
3. **不要用 `env={}`**。rev2 已论证过：那会丢 `PATH`，git 找不到，
   合法主区路径反而 fail-closed（回归）。本轮不碰环境净化那段。
4. **A26 就在眼前，但它是 forbidden path**。`resolve_paths.py:101` 的裸
   `subprocess.run(["git", *args])` 确实没净化环境，`GIT_DIR` 能把
   `--root main_repo` 改指到别的仓库。**看到了申报，不要动手**——已登记 A26，另立 WP。
5. **A25 是已登记的语义边界，本轮不修**。改写 worktree 内的 `.git` gitfile
   使其指向主仓后判 `False`，那是 git 定义下的正确语义，
   前置条件是攻击者已在执行者写入面内。不要为它加防线。

### 口径权威源引用

- worktree 判定：`agentic_loop.gate.path_is_in_worktree`（本 WP 建立的唯一权威点）
- 主仓根解析：`resolve_paths --root main_repo`（既有唯一权威，本轮不动，其缺陷见 A26）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/gate/__init__.py` — **`path_is_in_worktree` only**; do not
  touch `collect_dispatch_proof`, independence logic, or `main()`
- `tests/test_worktree_detection.py` — append to the existing 11 cases

**forbidden_paths**

- `src/agentic_loop/resolve_paths.py` — A26 surface, separate WP; report in
  `[CONCERNS]`, do not fix
- `src/agentic_loop/cli.py`, `src/agentic_loop/wrappers/codex_merge_gate.sh` — A26 surface
- `src/agentic_loop/wrappers/preflight.sh`, `finalize_merge.sh` — settled in rev2, empty diff required
- `src/agentic_loop/validate_wp_status.py`, `independence.py`, `adapters/`, `redispatch.py`
- `docs/`, `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7).

- `tests/test_worktree_detection.py`, four new cases:
  - blank `--git-common-dir` line (returncode 0, two lines, second blank) → `True`
  - blank `--absolute-git-dir` line → `True`
  - real symlink loop → `True`, and must not raise
  - a main-repo symlink pointing at a worktree-local status file → `True`
- All 11 existing cases keep passing unchanged, including the A22 regression
  guard `test_caller_env_combined_cannot_disguise_worktree_path` and the PATH
  contrast case.
- Whole suite: zero regression against baseline `bbfa258`
  (`4 failed + 574 passed + 4 skipped`). The 4 pre-existing
  `test_finalize_merge_triple_sign.py` failures must stay exactly as they are —
  **do not fix them**.

## Completion definition

- [ ] Each of the four new tests demonstrably fails before the fix and passes after
- [ ] Zero regression relative to baseline `bbfa258`
- [ ] The predicate stays the single authority (§5.3); signature stays
      `(path: Path) -> bool` with no new optional parameters
- [ ] `path_is_in_worktree` never raises, for any input
- [ ] Empty diff on `preflight.sh`, `finalize_merge.sh`, `cli.py`, `resolve_paths.py`
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No merge, no push, no branch switch, no amend of existing commits
- [ ] Commit message follows the repository convention

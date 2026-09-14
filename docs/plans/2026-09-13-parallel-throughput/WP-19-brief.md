# WP-19: 修复冻结/派发/finalize 接缝上的四个 wrappers 缺陷（A4 + A7 + A12 + A13）

> 冻结日期 2026-09-14 | 编排者 claude（claude-code, kiroopus） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `git.base_branch`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）

把冻结 → 派发 → finalize 这条链上四个已实证复现的缺陷（A4/A7/A12/A13）一次修完：
让 `preflight` 在字段时序与提交拓扑上不再误挂，让 `finalize` 首次调用不再自杀，
并把 worktree 拒收判据从路径字面量换成 git 事实。

## 为什么打成一个包

四条缺陷全部落在 `src/agentic_loop/wrappers/` 与其调用的解析面上，共享同一批
被测脚本与同一套临时 git 仓测试脚手架。分开做会三次重复搭建同样的 fixture，
且 A12（finalize 读自己要写的字段）与 A13（worktree 判据）在 `finalize_merge.sh`
里相隔 30 行，分包会造成同文件的连续返工。

四条互不冲突：A4 改字段时序判断，A7 改索引查询的仓，A12 补一处守卫，
A13 换判据实现。没有任何两条改写同一个条件表达式。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/wrappers/preflight.sh`
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `src/agentic_loop/gate/__init__.py`（**仅** A13 那一处 worktree 判据，见下）
  - `tests/test_preflight_branch_binding.py`（新建）
  - `tests/test_finalize_merge_first_call.py`（新建）
  - `tests/test_worktree_detection.py`（新建）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/validate_wp_status.py`（A14/A15 的面，另立 WP）
  - `src/agentic_loop/independence.py`（A9/A5 的面，另立 WP）
  - `src/agentic_loop/adapters/`
  - `src/agentic_loop/redispatch.py`
  - `docs/`（本 brief 与 status 由编排者维护）
  - `.agentic/config.toml`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ `gate/__init__.py` 在白名单里**只为 A13 一处判据**。该文件同时含 WP-18 的
> `collect_dispatch_proof`（尚未合并，见「输入」），不得改动其独立性相关逻辑。

## 输入

- 依赖的上游 WP 产出：
  - **WP-18**（`feature/wp18-dispatch-proof` @ `5711cd2`）改过 `gate/__init__.py`。
    本 WP 若与 WP-18 都改该文件，须以 WP-18 合并后的 main 为基线，避免
    A7 那种兄弟分叉。**基线由编排者在派发时确定并写入 `git.base_commit`**。
- 参考文档：
  - `WP-08-candidate.md` §A4（字段时序）、§A7（提交拓扑）、§A12（守卫缺失）、§A13（路径字面量）
  - 全局规范 §4.1（仅编排者维护 status）、§5.7（隔离执行）

## 交付物清单

### A12（最小、先做，倾向修法 1）
- [ ] `finalize_merge.sh:67` — `merged_commit_recorded=$(field git.merged_commit 2>/dev/null || true)`，
      与同文件 72-75 行读 override 可选字段的既有惯例一致。**不要**改
      `validate_wp_status.py --field` 的返回语义（那会让真正的拼写错误静默，
      且影响所有 `field()` 调用点）。
- [ ] `tests/test_finalize_merge_first_call.py` — 在临时 git 仓造一个
      `state=APPROVED_FOR_MERGE`、**无** `git.merged_commit` 字段的 status，
      跑 finalize 应 `FINALIZE_OK`；再跑一次应幂等。

### A13（换判据，不留路径字面量）
- [ ] `gate/__init__.py:692` 与 `finalize_merge.sh:38` — 把
      `if "/.worktrees/" in str(status_file)` 换成 git 事实判断：
      比较该路径所在仓的 `git rev-parse --git-dir` 与 `--git-common-dir`，
      两者不同即在 worktree 内。**两处必须同口径**（§5.3 口径单一权威），
      建议抽一个共用判定点而非各写一份。
- [ ] 保留原有主防线不动：`resolve_paths --root main_repo` 仍是第一道，
      本条只是绝对路径入参的兜底加强。
- [ ] `tests/test_worktree_detection.py` — 真实临时仓 + `git worktree add`，
      验主区路径判 False、worktree 内路径判 True、**且不依赖目录名**
      （worktree 建成 `../wpN-x` 同级形态，不是 `.worktrees/`）；
      不可解析的路径 fail-closed 且不抛异常。

### A4（字段时序，倾向「preflight 回填 + 提示」）
- [ ] `preflight.sh:45` — `git.branch` 为**空串**时不再直接失败：视为「尚未绑定」，
      用活分支回填并打印明确提示（`PREFLIGHT_WARN: git.branch empty; bound to <branch>`）。
      **非空时行为完全不变**，仍严格比对、不等即失败（防绑错分支）。
- [ ] `git.worktree` 同理。
- [ ] `tests/test_preflight_branch_binding.py` — 三个场景：空串→回填成功且有提示；
      非空且相等→通过；**非空且不等→仍然失败**（这条是回归保护，不能被放宽）。

> ⚠️ **不要**选 A4 的修法 2（把 dispatch 提交也算合法，两次提交纪律改三次）。
> 那是文档级契约变更，须用户裁定，不在本 WP 范围。

### A7（提交拓扑，倾向「在主仓索引里查」）
- [ ] `preflight.sh:69` — `git ls-files --error-unmatch "$status_file"` 改为在
      **主仓**索引里查（`main_root` 已由 `:77` 的 `resolve_paths --root main_repo`
      得出，注意取用顺序，可能需把该行上移）。status 本就是主区 live 状态
      （全局规范 §4.1），在主仓查才是对的语义。
- [ ] 该改动须使「以另一个未合并 WP 分支为基线」的场景不再误挂，
      同时保持「status 确实未提交」时仍然失败。
- [ ] 测试并入 `tests/test_preflight_branch_binding.py`：造两个分叉分支，
      status 只存在于其中一支，在另一支的 worktree 里跑 preflight 应通过
      （因为主仓索引有它）；status 完全未提交时应仍然失败。

## 完成定义（DoD）

- [ ] 交付物逐项就绪，四条缺陷各有一个失败→通过的测试
- [ ] `python3.11 -m pytest tests -q` 相对基线**零回归**（基线预存 4 个
      `test_finalize_merge_triple_sign.py` 失败，fixture 在无 `main` 分支的临时仓跑
      `git checkout main`，与本 WP 无关，**不要修**，见缺陷 B7 的记法）
- [ ] 按缺陷 B7：测试用 `PYTHONPATH=src python3.11 -m pytest` 直接跑工作树代码，
      **不要**用 `agentic quality-gate` 自证（那会跑到另一个仓的快照）
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

1. **A4 的放宽只对空串生效**。空串→回填，非空且不等→必须仍然失败。
   把「不等也回填」写进去等于废掉分支绑定校验，会被验收驳回。
2. **A13 两处同口径**。`gate/__init__.py` 和 `finalize_merge.sh` 若各写一份
   git 判断，就造出了第二份可执行判据，违反 §5.3。
3. **A7 注意取用顺序**。`main_root` 在 `preflight.sh:77` 才算出，而
   `ls-files` 在 `:69`。上移那行时确认没有别的语句依赖当前顺序。
4. **`set -euo pipefail` 下的读取一律要守卫**。A12 就是这么来的；本 WP 新增的
   任何 `$(field ...)` 读取，若字段可能不存在，都要 `2>/dev/null || true`。
5. **不要顺手修 A14/A15/A9**。它们落在 `validate_wp_status.py` /
   `independence.py`，是 forbidden path，另立 WP。看到了就在
   `[CONCERNS]` 里申报，不要动手。
6. **`gate/__init__.py` 只碰 A13 那一处**。该文件的独立性判定逻辑属 WP-18/WP-20 的面。

### 口径权威源引用

- worktree 判定：本 WP 建立的唯一权威点（A13 交付物），两个调用方都引用它
- 主仓根解析：`resolve_paths --root main_repo`（既有唯一权威，不另造）
- 范围校验：`quality-gate.sh` 的 `_path_in_scope`（既有唯一权威，不另造）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/wrappers/preflight.sh` — A4 (branch/worktree binding), A7 (main-repo index lookup)
- `src/agentic_loop/wrappers/finalize_merge.sh` — A12 (missing guard), A13 (worktree predicate)
- `src/agentic_loop/gate/__init__.py` — **A13 predicate only**; do not touch independence logic
- `tests/test_preflight_branch_binding.py` (new)
- `tests/test_finalize_merge_first_call.py` (new)
- `tests/test_worktree_detection.py` (new)

**forbidden_paths**

- `src/agentic_loop/validate_wp_status.py` — A14/A15/A18 surface, separate WP
- `src/agentic_loop/independence.py` — A9/A5 surface, separate WP (WP-20)
- `src/agentic_loop/adapters/`
- `src/agentic_loop/redispatch.py`
- `docs/` — brief and status are orchestrator-maintained
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7: it runs
another repository's snapshot).

- `tests/test_finalize_merge_first_call.py` — A12: a status at
  `state=APPROVED_FOR_MERGE` **without** a `git.merged_commit` key must reach
  `FINALIZE_OK` on the first call, and be idempotent on the second.
- `tests/test_worktree_detection.py` — A13: real temporary repo plus
  `git worktree add`; main-repo path is False, worktree path is True, and the
  verdict must **not** depend on the directory name (worktrees here are created
  as sibling `../wpN-x`, never `.worktrees/`). Unresolvable paths fail closed
  without raising.
- `tests/test_preflight_branch_binding.py` — A4 and A7:
  - empty `git.branch` → back-filled from the live branch, with a warning
  - non-empty and equal → pass
  - **non-empty and different → still fails** (regression guard, must not be relaxed)
  - status committed on a sibling branch only → passes when run from another
    worktree, because the main-repo index has it (A7)
  - status never committed → still fails
- Whole suite: `PYTHONPATH=src python3.11 -m pytest tests -q`, zero regression
  against the baseline. The baseline carries 4 pre-existing failures in
  `tests/test_finalize_merge_triple_sign.py` (its fixture runs `git checkout main`
  in a temporary repo that has no `main` branch). These are unrelated to this
  WP — **do not fix them**.

## Completion definition

- [ ] Every deliverable in place; each of the four defects has one
      failing-to-passing test
- [ ] Zero regression relative to the baseline (4 known pre-existing failures
      stay exactly as they are)
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] A13's predicate exists in exactly **one** place, referenced by both
      call sites (single authoritative definition, global rule §5.3)
- [ ] A4's relaxation applies **only** to the empty-string case
- [ ] Commit message follows the repository convention

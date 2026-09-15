# WP-19 rev2（返工）：A13 判据环境净化（修 A22）

> 冻结日期 2026-09-15 | 编排者 Claude | 执行者 Kimi。冻结后执行期间不得修改。
> 前序：rev1 @ `b97ce67` 被 codex 判 REWORK（`consult.decision=REWORK`），
> 单条阻断发现 A22。rev1 的 A4/A7/A12 三条已通过独立复核，**不返工、不改动**。

## 目标（一句话）

让 A13 的 worktree 判据读**文件系统拓扑**而非调用方声明的仓库选择，
使 `GIT_DIR` 等环境变量无法翻转判据。

## 唯一要修的问题（A22）

`src/agentic_loop/gate/__init__.py` 的 `path_is_in_worktree()` 内部
`subprocess.run(...)` 继承调用者环境，未清除 git 的仓库选择变量。实测：

```
worktree 路径，干净环境                    -> True   正确拒收
worktree 路径，GIT_DIR=<主仓>/.git         -> False  ← 绕过成功
worktree 路径，GIT_WORK_TREE=<主仓>        -> True   不绕过
worktree 路径，GIT_COMMON_DIR=<主仓>/.git  -> True   不绕过
```

从 CLI 入口即可复现（`cli.py:212` 用 `dict(os.environ)` 原样传给 wrapper，
且无任何 wrapper unset 这些变量）：

```bash
GIT_DIR=/main/.git agentic gate /linked-worktree/WP.status.json
```

两处调用方（`gate/__init__.py` main() 与 `finalize_merge.sh`）全部越过守卫。
这是口径单一的**必然结果**，不是各自的实现缺陷 —— 所以只需修谓词一处。

## 范围

### allowed_paths（仅 2 个）

- `src/agentic_loop/gate/__init__.py` —— **仅** `path_is_in_worktree()` 函数体内的
  环境净化。该函数的签名、返回语义、fail-closed 方向、两处调用点**全部不变**。
- `tests/test_worktree_detection.py` —— 追加环境变量反向用例。
  **现有 5 个用例一个都不许改、不许删**。

### forbidden_paths（其余全部，重点）

- `src/agentic_loop/wrappers/preflight.sh` —— rev1 的 A4/A7 已验收，**不许碰**
- `src/agentic_loop/wrappers/finalize_merge.sh` —— rev1 的 A12/A13 已验收，**不许碰**
  （谓词修好后本文件自动继承修复，无需改动；若你认为必须改，那是 BLOCKED，来报告）
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/independence.py`
- `src/agentic_loop/adapters/`
- `src/agentic_loop/redispatch.py`
- `src/agentic_loop/cli.py` —— **不要**在 CLI 层净化环境。判据自己必须站得住，
  不能依赖上游调用者替它擦干净（这正是 A22 的教训）
- `docs/`、`.agentic/`、`.env`、`.context/`
- 其余 `tests/` 下的任何既有文件

## 实现要求

- [ ] 给 `subprocess.run` 传显式 `env`，从继承环境中**剔除**：
      `GIT_DIR`、`GIT_WORK_TREE`、`GIT_COMMON_DIR`、`GIT_INDEX_FILE`、
      `GIT_OBJECT_DIRECTORY`、`GIT_ALTERNATE_OBJECT_DIRECTORIES`、`GIT_CEILING_DIRECTORIES`。
      建议做法：`env = {k: v for k, v in os.environ.items() if k not in _GIT_SELECTION_VARS}`，
      把变量名集合提成模块级常量并注明为什么每一个都要剔除。
- [ ] **不要**用 `env={}`（清空整个环境）—— 那会丢掉 `PATH`，git 可能找不到，
      反而把「正常路径」变成 fail-closed 拒收，构成回归。
- [ ] 保持 fail-closed 方向不变：不可解析 / git 缺失 / 输出异常 -> 返回 `True`（拒收），且不抛异常。
- [ ] 保持单一权威点：仍只有这一个谓词定义，两处调用方不各写一份（§5.3）。
- [ ] 函数签名不变（仍 `(path: Path) -> bool`），不新增参数、不加 `env` 入参
      —— 净化是判据的**内在属性**，不是调用方可选项。

## 测试要求

`tests/test_worktree_detection.py` 追加（现有 5 例保持不动）：

- [ ] `GIT_DIR` 指向主仓 `.git` 时，linked worktree 内路径**仍判 True**
      （这条就是 A22 的回归保护，修复前必须红）
- [ ] `GIT_WORK_TREE` 指向主仓时，worktree 内路径仍判 True
- [ ] `GIT_COMMON_DIR` 指向主仓 `.git` 时，worktree 内路径仍判 True
- [ ] 三个变量**同时**设置时仍判 True
- [ ] 干净环境下主区路径仍判 False（证明净化没把正常路径也变成拒收）
- [ ] `PATH` 仍可用：净化后 git 仍能被找到（若你用 `env={}` 会在这条上失败）
- [ ] 用 `monkeypatch.setenv` 或 `env=` 传给子进程，**不要**污染 pytest 自身进程环境

## 完成定义（DoD）

- [ ] A22 有一个失败→通过的测试（修复前红、修复后绿）
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对 rev1 基线零回归。
      **rev1 基线：4 failed + 568 passed + 4 skipped @ `b97ce67`**
      （4 个失败是预存 `test_finalize_merge_triple_sign.py` 的 `git checkout main`
      fixture 问题，与本 WP 无关，**不要修**，见缺陷 B7）
- [ ] 按缺陷 B7：测试用 `PYTHONPATH=src python3.11 -m pytest` 直接跑工作树代码，
      **不要**用 `agentic quality-gate` 自证（那会跑到另一个仓的快照）
- [ ] 无 forbidden_paths 写入；`preflight.sh` 与 `finalize_merge.sh` 的 diff 必须为空
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 不 merge、不 push、不切分支；只在本 worktree 内 commit
- [ ] commit message：`🐛 fix(gate): worktree 判据净化 git 环境变量（WP-19 rev2 / A22）`

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注：已知陷阱

1. **`env={}` 是陷阱**，见上。要的是「剔除特定变量」，不是「清空环境」。
2. **不要在 wrapper 或 cli 层 unset** 来「解决」问题。判据必须自己站得住 ——
   依赖调用方替它擦环境，等于把守卫的正确性外包给每一个未来的调用点。
3. **不要动 rev1 已验收的三条**。A4/A7/A12 与 A13 的其余部分都已独立复核通过，
   本次只修谓词内的环境净化。多改一行都会让已完成的复核失效、需要整体重验。
4. **不要改现有 5 个 worktree 检测用例**。它们是 A13 的既有回归保护。
5. `path_is_in_worktree` 的 fail-closed 方向是「不确定就拒收」。净化环境后若某些
   合法场景开始不可解析，那是回归，不是「更安全」—— DoD 里主区判 False 那条防这个。

## 报告格式

```
[STATUS] DONE / DONE_WITH_CONCERNS / BLOCKED
[COMMIT] hash / message
[CHANGES] - path（修改说明）
[TESTS]   - 失败→通过证据（还原源码重跑）+ 全量结果
[CONCERNS]（仅 DONE_WITH_CONCERNS）
[BLOCKER] （仅 BLOCKED）
```

## Scope (English anchors for dispatch-lint)

- `src/agentic_loop/gate/__init__.py` — A22: sanitize git selection env vars inside
  `path_is_in_worktree()` only; signature, fail-closed direction and both call sites unchanged
- `tests/test_worktree_detection.py` — A22 regression cases for GIT_DIR / GIT_WORK_TREE /
  GIT_COMMON_DIR; the 5 existing cases must not be modified or removed

## Completion definition

- [ ] A22 has one failing-to-passing test
- [ ] Zero regression against rev1 baseline `4 failed + 568 passed + 4 skipped` @ `b97ce67`
- [ ] `preflight.sh` and `finalize_merge.sh` diffs are empty (rev1 work untouched)
- [ ] No writes to forbidden_paths; no production writes, network, notifications, pushes
- [ ] No merge, no push, no branch switch
- [ ] The predicate remains the single authoritative definition referenced by both call sites
- [ ] Commit message follows the repository convention

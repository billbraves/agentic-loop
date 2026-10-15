# WP-01 — status 来源判据改为「target_branch 持有者」而非「物理主仓」

> rev1 冻结日期 2026-10-15 | 编排者 Kiro（DSH 会话）| 执行者 kimi。
> 状态：**DRAFT（待用户批准冻结；`agentic autonomy freeze_scope` 为 AUTONOMY_STOP）**。
> 本 WP 修改一条经过 A13/A19/A22 加固、且曾被真实绕过的安全判据，因此范围冻结必须由用户批准。

## 1. 问题（编排者已实测复现）

五个调用点共用同一条「status 文件不得位于 worktree 内」的判据：

- `src/agentic_loop/wrappers/finalize_merge.sh:275`
- `src/agentic_loop/wrappers/preflight.sh:48`
- `src/agentic_loop/wrappers/merge.sh:38`
- `src/agentic_loop/gate/__init__.py:812`
- `src/agentic_loop/gate/qoder_security.py:1014`

判据本体是单一权威 `gate.path_is_in_worktree()`（`gate/__init__.py:200`）：当某路径所属仓库的
`--git-dir` 不等于 `--git-common-dir` 时，判定为 linked worktree 并拒绝。

**该判据本身没有写错，错的是它编码的布局假设**：它假设 `main`（即 plan 的
`git.target_branch`）签出在**物理主仓**里，于是「不在 linked worktree 内」≡「在 main 签出里」。

本机实测布局（2026-10-15，commit `9ec3c38`）：

```text
物理主仓 /Users/admin/vibe/agentic_loop        分支 = plan/2026-09-22-framework-hardening
main 签出 /Users/admin/vibe/agentic-loop-main-codex-merge   ← 这是一个 LINKED worktree
  git-dir        = /Users/admin/vibe/agentic_loop/.git/worktrees/agentic-loop-main-codex-merge
  git-common-dir = /Users/admin/vibe/agentic_loop/.git      （二者不等 ⇒ 判为 worktree）
```

于是两条路同时不可走，形成死锁：

1. **物理主仓副本不存在** —— `/Users/admin/vibe/agentic_loop/docs/plans/2026-10-12-sequential-plan-gates/WP-03.status.json`
   实测 `exists() == False`（该迭代的文件只提交在集成分支上）。判据对无法 resolve 的路径
   **fail-closed**，按设计答 True，拒绝。
2. **真正持有文件的 main 签出被拒** —— 它确实存在该文件，但它自己就是 linked worktree，
   判据按设计答 True，拒绝。

实测两条路径都返回 `in_worktree=True`。后果：`agentic finalize`、`agentic preflight`、
`agentic merge` 对这种布局**完全不可用**。2026-10-12 迭代因此只能由编排者手工套用
`finalize_merge.sh` 自身的 sequential 规则盖章（已在该 WP 的 status 中记明）。

**不是什么**：这不是「plan 文件只提交在集成分支」造成的（那只是触发第 1 条的原因之一）。
即使文件在物理主仓存在，只要 `main` 签出在 linked worktree 里，第 2 条仍然成立。根因是
**判据把「单一真相源」定义成了一个物理位置（primary repo），而它实际要表达的是一个
仓库角色（持有 target_branch 的那个签出）**。

## 2. 方向（用户已选定）

把判据从「**是否位于 linked worktree**」改为「**是否是持有 target_branch 的那个签出**」。
允许该签出本身是 linked worktree；其余所有 worktree 一律仍然拒绝。

**明确不做**：不放宽、不删除、不旁路 `path_is_in_worktree()` 的任何现有加固。A22 的环境变量
剥离、A27 的先 resolve 再探测、A28 的 fail-closed 必须逐条保留，并由现有测试继续钉住。

## 3. 不变量

**INV-1（角色而非位置）**：status 文件的受信任来源是「当前检出 `git.target_branch` 的那个
registered worktree」。该 worktree 是物理主仓还是 linked worktree **不影响**判定。

**INV-2（仍然唯一，且必须是活的）**：受信任来源必须唯一。若零个或多于一个 registered
worktree 检出 `target_branch`，一律 fail-closed，两种失败给出**各自特异**的 witness
（`no checkout holds target_branch` / `target_branch checkout not unique`），不得混同。

**INV-2b（幽灵持有者，编排者实测补入）**：git 的注册表会保留目录已被删除的 worktree 条目，
`git worktree list --porcelain` 对其标记 `prunable`，而 `branch refs/heads/<target>` 仍然在列。
实测：删除 main worktree 目录后它仍被列为 `main` 的持有者，且此时 `git worktree add <new> main`
会以「`main` 已经检出到 `<已删除路径>`」失败 —— 即仓库会卡在一个**无法落地的受信任来源**上。
因此候选必须同时满足「目录存在」且「未被标记 prunable」；只命中幽灵条目时 fail-closed，
witness 为 `target_branch holder is stale (prunable)`，**不得**退化成 `no checkout holds`
（二者的修复动作不同：前者需 `git worktree prune`）。

**INV-3（target_branch 必须来自被校验的文件，且不可自证）**：`target_branch` 取自 status
文件本身，因此不得仅凭文件内容建立信任。必须同时满足：

1. 该字段通过单一路径组件校验（非空、不含 `/` `\`、不等于 `.` `..`、不以 `.` 开头、无 NUL）；
2. 候选 worktree 的**当前分支**严格等于该字段；
3. 候选 worktree 与物理主仓共享同一 resolved `git-common-dir`（即确实是同一仓库的注册
   worktree，而非任意目录）。

**INV-4（加固不得退化）**：A22 环境剥离、A27 先 resolve 再探测、A28 全路径 fail-closed
（含空行、symlink 环的 `RuntimeError`、超长路径、NUL 字节）必须原样保留。
`tests/test_worktree_detection.py` 现有 **17** 个用例必须**全部保持绿**。

**INV-5（单一权威）**：五个调用点必须继续引用**同一个**判据函数，不得各自实现。新判据与旧
判据不得并存为两条可选路径。

## 4. 验收测试

沿用 `tests/test_worktree_detection.py` 既有真实 git fixture 风格。

- **E1 `[main-branch-in-linked-worktree-is-trusted]`**：构造物理主仓停在
  `plan/x`、`main` 签出在 linked worktree 的真实布局；该 worktree 内的 status 路径
  必须**被接受**。本用例必须自证布局：断言该签出的 `--git-dir != --git-common-dir`
  （即在旧判据下会被拒），否则节点可能因无关原因变绿。
- **E2 `[primary-repo-holding-target-branch-still-trusted]`**：物理主仓本身检出 `main`
  的传统布局必须仍然被接受（兼容性，不得只支持新布局）。
- **E3 `[other-worktree-still-refused]`**：同一仓库另一个检出 `plan/y` 的 worktree 内的
  status 路径必须**仍被拒绝**，witness 为 `checkout does not hold target_branch`。
- **E4 `[no-holder-fails-closed]`**：没有任何 registered worktree 检出 `target_branch`
  → 拒绝，witness 为 `no checkout holds target_branch`。
- **E5 `[stale-holder-fails-closed]`**（原「多持有者」形态经实测不可构造，改为此形态）：
  注册一个检出 `target_branch` 的 worktree 后**删除其目录**，使注册表留下 `prunable`
  幽灵条目 → 必须 fail-closed，witness 为 `target_branch holder is stale (prunable)`。
  本用例必须自证前提：断言该条目仍出现在 `git worktree list --porcelain` 且带 `prunable`、
  断言其目录确实不存在。
  **实测说明（编排者）**：git 硬性拒绝同一分支被签出两次（`fatal: 'main' is already
  checked out at ...`），detached HEAD 的 `branch --show-current` 为空字符串，故「两个活的
  worktree 同时检出 target_branch」在真实 git 下**无法构造**。INV-2 的「多于一个」分支因此
  是**防御性**的（防注册表损坏或未来 git 行为变化），由代码 fail-closed 承担，不要求验收用例；
  承重由 E5 的幽灵形态提供。
- **E6 `[target-branch-field-is-validated]`**：`target_branch` 取
  `"../../etc"` / `"a/b"` / `"."` / `".."` / `""` 五种形态 → 各自 fail-closed，原因必须
  指向**字段校验**，不得是偶然的「分支不存在」。
- **E7 `[foreign-repo-checkout-refused]`**：另建一个**独立**仓库、其分支也叫 `main`，
  该路径必须被拒绝（witness：不共享 git-common-dir）。该节点证明 INV-3 第 3 条承重。
- **E8 `[hardening-preserved]`**：A22/A27/A28 的既有断言在新判据下复跑全绿 —— 不新增
  用例，直接复用 `tests/test_worktree_detection.py` 的 17 个节点作为护栏。

## 5. 承重变异（DoD 必做，逐条分别施加、分别验证、精确还原）

- **M-1**：把 INV-2b 的存活性检查去掉（接受 prunable 幽灵条目）→ **E5 必须转红**。
- **M-2**：去掉 INV-3 第 3 条（不比对 git-common-dir）→ **E7 必须转红**。
- **M-3**：去掉 INV-3 第 1 条（字段校验）→ **E6 必须转红**。
- **M-4**：把判据退回旧形态（纯 `--git-dir != --git-common-dir`）→ **E1 必须转红**，
  且红的原因必须是「被判为 worktree 而拒绝」。该变异锁死本 WP 要消除的死锁。
- **M-5**：把判据放宽成「任何 registered worktree 都接受」→ **E3 必须转红**。
  该变异证明新判据没有把门彻底打开（与 M-4 方向相反，两者都必须承重）。
- **M-6**：恢复 A22 的环境继承（不剥离 `GIT_DIR` 家族）→
  `test_caller_env_cannot_disguise_*` 必须转红。证明加固未退化。

M-4 与 M-5 必须**分别**验证：两者同时承重才说明判据既解了死锁、又没有放开边界。

## 6. 范围

**允许修改**：

- `src/agentic_loop/gate/__init__.py`（判据本体）
- `src/agentic_loop/gate/qoder_security.py`（调用点对齐）
- `src/agentic_loop/wrappers/finalize_merge.sh`、`preflight.sh`、`merge.sh`（调用点对齐）
- `tests/test_worktree_detection.py`（新增 E1–E7）
- `tests/test_preflight_status_source.py`、`tests/test_finalize_merge_first_call.py`、
  `tests/test_finalize_merge_toctou.py`（仅在新判据使其断言失真时**最小**调整；
  调整必须在报告中逐条说明理由，**不得**为了变绿而削弱攻击形态）

**禁止修改**：`src/agentic_loop/plan_cmd.py`、`validate_wp_status.py`、`autonomy.py`、
`.agentic/config.toml`、`uv.lock`、任何 `docs/plans/**`、`docs/agentic/templates/**`。

## 7. 完成定义（DoD）

- [ ] E1–E7 全绿（E6 的 **5** 种字段形态逐一参数化，不得合并成一条）。
- [ ] INV-2 的「多于一个持有者」分支虽无验收用例（真实 git 不可构造），代码仍必须显式
      fail-closed 并给出该 witness；报告须指出该分支在代码中的位置。
- [ ] E8 护栏：`tests/test_worktree_detection.py` 原有 **17** 个用例全部仍绿。
- [ ] M-1 ~ M-6 逐条红证齐备（含还原回绿，还原后 `git diff` 为空），报告附逐条实际输出。
- [ ] 保护集全绿：`tests/test_preflight_status_source.py`、
      `tests/test_finalize_merge_first_call.py`、`tests/test_finalize_merge_toctou.py`、
      `tests/test_finalize_merge_sequential.py`。
- [ ] 全量不低于基线 **902 passed / 4 skipped**（新增用例会使总数上升）。
- [ ] **单一权威自检**：报告须列出五个调用点，并证明它们引用的是同一个判据函数；
      新旧判据不得并存为两条可选路径（INV-5）。
- [ ] **端到端自检**：在「物理主仓停在别的分支、`main` 在 linked worktree」的真实布局下，
      `agentic finalize` 对一个双签完毕的 WP 能够正常盖章（这是本 WP 的存在理由）。
      报告须附实际命令与输出。
- [ ] 不得出现任何旁路开关（`--allow-worktree-status` / 环境变量等）。

## 8. 残余风险

- 判定与使用之间仍存在 ref/worktree 竞态：某 worktree 可在判定通过后切换分支。与既有
  `base_branch` 判定同类，不在本 WP 范围内，记录在此。
- 本 WP 不改变「status 文件是单一真相源」这一产品语义，只改变「哪个签出持有它」的判定方式。

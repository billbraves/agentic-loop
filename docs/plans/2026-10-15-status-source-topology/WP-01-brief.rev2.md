# WP-01 — status 来源判据改为「受信任目标分支的持有者」而非「物理主仓」

> rev2 冻结日期 2026-10-15 | 编排者 Kiro（DSH 会话）| 执行者 kimi。
> 状态：**APPROVED（范围已由用户批准冻结）**。
> rev1 快照见 `WP-01-brief.rev1.md`（SHA `96a7398f…`），已被 `topo-brief-r1` 判 REWORK。
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

## 1.9 rev2 触发原因（brief-r1 REWORK，三条缺陷编排者均独立复现）

**D1（致命，规格不可实现）**：rev1 让判据读 status 的 `git.target_branch`。实测该字段
**只存在于 PLAN schema**，WP schema 根本没有：

```text
WP 模板   git keys = base_branch, base_commit, branch, commit, dispatch_commit, worktree
PLAN 模板 git keys = base_branch, merged_commit, target_branch
```

而五个调用点里**四个**（preflight / finalize / merge wrapper / 两个 gate）校验的是 **WP**
status。rev1 要求判据读一个在被校验对象上不存在的字段 —— 规格无法实现。

**D2（自证循环未被切断）**：即便字段存在，它仍来自被校验的文件本身。攻击者在自己的 worktree
里 `git checkout -b feat/evil`，再把 status 的 `target_branch` 改成 `feat/evil`，即可同时满足
rev1 INV-3 的三个合取项（字段合法、当前分支相等、共享 git-common-dir），把自己的签出变成
受信任来源。rev1 缺的是「与一个**在被校验文件之外**独立确定的期望分支相等」。

**D3（INV-4 自相矛盾）**：rev1 宣称 17 个护栏全部只读保持绿。实测它们**全部**是单参数调用
`path_is_in_worktree(path)`（17 处，见 `tests/test_worktree_detection.py:59,68,78,84,…`），
无法向目标相关的新判据传入期望分支；且其断言编码了旧前提「任何 linked worktree 都拒绝」，
而新契约刻意接受其中一个。新增必填第二参数会让 17 处在调用层全断；给默认值则由默认值决定
语义。rev1 未提及签名变更。

## 2. 方向（用户已选定，rev2 细化锚点）

把判据从「**是否位于 linked worktree**」改为「**是否是持有受信任目标分支的那个签出**」。
允许该签出本身是 linked worktree；其余所有 worktree 一律仍然拒绝。

rev2 的关键修正（针对 D1/D2）：期望分支**不从被校验的 status 文件读取**，而由一个
**外部锚点**独立确定。实测可用锚点：

```text
git symbolic-ref refs/remotes/origin/HEAD  ->  refs/remotes/origin/main   （实测存在）
去 origin/ 前缀                            ->  main
```

该锚点不在被校验文件的控制范围内。但它本身可被本地 `git symbolic-ref` 改写，因此必须与
配置中的显式声明**双锚一致**才采信（见 INV-1b）。

**明确不做**：不放宽、不删除、不旁路 `path_is_in_worktree()` 的任何现有加固。A22 的环境变量
剥离、A27 的先 resolve 再探测、A28 的 fail-closed 必须逐条保留，并由现有测试继续钉住。

## 3. 不变量

**INV-1（角色而非位置）**：status 文件的受信任来源是「当前检出**受信任目标分支**的那个
registered worktree」。该 worktree 是物理主仓还是 linked worktree **不影响**判定。

**INV-1b（锚点在被校验文件之外，双锚一致，关闭 D1/D2）**：受信任目标分支**不得**取自被
校验的 status 文件。它由两个互不隶属的来源共同确定，且必须**逐字节相等**才采信：

1. `git symbolic-ref refs/remotes/origin/HEAD`，去掉 `origin/` 前缀后的分支名。
   实测：raw = `refs/remotes/origin/main`，`--short` = `origin/main`，**去前缀后** = `main`。
   实现必须显式去前缀；直接用 `--short` 会得到 `origin/main`，与任何本地分支名都不相等，
   导致判据恒 fail-closed（无声死锁，与本 WP 要修的病症同类）；
2. `.agentic/config.toml` 中新增的显式声明（例如 `[project] protected_branch = "main"`）。

两者不一致、任一缺失或无法读取 → fail-closed，witness 为
`trusted target branch anchor unavailable or inconsistent`。
理由：锚点 1 可被本地 `git symbolic-ref` 改写，锚点 2 可被能改仓库文件的人改写；要求二者
一致，使单一改写面不足以移动受信任来源。被校验的 status 文件对两者**都没有**影响力。

若 status 文件自身也带目标分支字段（PLAN schema 有、WP schema 没有），它只能用作
**一致性交叉校验**：不等则 fail-closed，**绝不**用它覆盖锚点。

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

**INV-3（候选必须是本仓库的真实活签出）**：候选 worktree 必须同时满足：

1. 受信任目标分支名通过单一路径组件校验（非空、不含 `/` 与 `\\`、不等于 `.` `..`、
   不以 `.` 开头、无 NUL 字节）；
2. 该候选的**当前分支**严格等于受信任目标分支；
3. 该候选与**锚点所属仓库**共享同一 resolved `git-common-dir`。此处的对照基准必须取自
   锚点侧（独立确定），**不得**取自候选路径自己发现的仓库 —— 否则两个事实都来自候选，
   独立仓库里同名 `main` 会被接受（brief-r1 Q3 指出，编排者已实测两个独立仓库的
   common-dir 必然不同，故该合取项可承重）。

**INV-4（加固不得退化，rev2 改为「保证不变、断言可改写」，关闭 D3）**：A22 环境剥离、
A27 先 resolve 再探测、A28 全路径 fail-closed（含空行、symlink 环的 `RuntimeError`、超长
路径、NUL 字节）的**攻击保证**必须原样保留。

但 rev1 的「17 个用例全部只读保持绿」经实测**不可成立**：17 处全是单参数
`path_is_in_worktree(path)`，无法传入受信任目标分支，且断言编码了「任何 linked worktree
都拒绝」这一被新契约刻意改变的前提。因此 rev2 允许对这些用例做**保前提的改写**，约束是：

1. 每一个旧节点必须在新套件中有**明确对应**的断言，交付时提交一份
   **旧节点 → 新断言**的逐条映射表（17 行，不得遗漏，不得合并）；
2. 改写只允许调整**调用形式**（补齐新参数/构造 fixture）与**因契约改变而必须翻转的期望值**；
   **不得**削弱或删除任何攻击形态（环境伪装、symlink 跟随、NUL、超长路径、symlink 环）;
3. 任何期望值翻转必须在报告中逐条给出理由，说明它是契约刻意改变所致，而非为了变绿。

签名变更必须在交付中显式说明：新判据需要「受信任目标分支」这一入参或由其内部解析锚点，
二者择一但必须**全仓统一**（INV-5）。

**INV-5（单一权威）**：五个调用点必须继续引用**同一个**判据函数，不得各自实现。新判据与旧
判据不得并存为两条可选路径。

## 4. 验收测试

沿用 `tests/test_worktree_detection.py` 既有真实 git fixture 风格。

- **E1 `[target-branch-in-linked-worktree-is-trusted]`**：构造物理主仓停在
  `plan/x`、受信任目标分支签出在 linked worktree 的真实布局（两个锚点在 fixture 中均
  指向该分支）；该 worktree 内的 status 路径必须**被接受**。本用例必须自证布局：断言该
  签出的 `--git-dir != --git-common-dir`（即在旧判据下会被拒），否则节点可能因无关原因变绿。
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
- **E6 `[trusted-branch-name-is-validated]`**：受信任目标分支名取
  `"../../etc"` / `"a/b"` / `"a\\b"` / `"."` / `".."` / `".hidden"` / `""` /
  含 NUL 共 **8** 种形态 → 各自 fail-closed，原因必须指向**名称校验**，不得是偶然的
  「分支不存在」。（rev1 只列 5 种，brief-r1 指出漏了反斜杠、点号前缀与 NUL。）

- **E9 `[anchors-must-agree]`**（rev2 新增，承载 INV-1b）：两个锚点不一致
  （`origin/HEAD` 指向 `main`、配置声明 `release`）→ fail-closed，witness 为
  `trusted target branch anchor unavailable or inconsistent`。另加一个分支：任一锚点缺失
  （未设 `origin/HEAD`；配置缺键）同样 fail-closed。本节点证明双锚承重。

- **E10 `[status-field-cannot-override-anchor]`**（rev2 新增，承载 D2 的关闭）：status
  文件声明的目标分支与锚点**不一致**时必须 fail-closed，且**不得**改用文件里的值。
  构造：攻击者在自己的 linked worktree 检出 `feat/evil` 并把 status 的目标分支字段写成
  `feat/evil` → 必须拒绝。该节点直接复现 brief-r1 Q1 的攻击。
- **E7 `[foreign-repo-checkout-refused]`**：另建一个**独立**仓库、其分支也叫 `main`，
  该路径必须被拒绝（witness：不共享 git-common-dir）。该节点证明 INV-3 第 3 条承重。
- **E8 `[hardening-preserved]`**：A22/A27/A28 的既有断言在新判据下复跑全绿 —— 不新增
  用例，直接复用 `tests/test_worktree_detection.py` 的 17 个节点作为护栏。

## 5. 承重变异（DoD 必做，逐条分别施加、分别验证、精确还原）

- **M-1**：把 INV-2b 的存活性检查去掉（接受 prunable 幽灵条目）→ **E5 必须转红**。
- **M-2**：去掉 INV-3 第 3 条（不比对 git-common-dir）→ **E7 必须转红**。
- **M-2b（rev2 新增）**：把 INV-3 第 3 条的对照基准从**锚点侧**改成**候选自己发现的仓库**
  → **E7 必须转红**。该变异证明「基准必须独立」这半是承重的，而不只是「比了就行」。
- **M-3**：去掉 INV-3 第 1 条（名称校验）→ **E6 必须转红**（8 种形态中至少 1 种）。
- **M-7（rev2 新增，关键）**：把受信任目标分支的来源从**锚点**改回**被校验的 status 文件**
  → **E10 必须转红**，且红的形态必须是攻击者的 worktree 被判为受信任来源。该变异锁死
  brief-r1 Q1 指出的自证循环。
- **M-8（rev2 新增）**：把 INV-1b 的双锚一致降级为「任一锚点可用即采信」→
  **E9 必须转红**。
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
- `tests/test_worktree_detection.py`（新增 E1–E10，并按 INV-4 做保前提改写）
- `.agentic/config.toml` —— **仅允许新增** `[project] protected_branch` 这一个键（INV-1b
  的锚点 2）。不得修改该文件其他任何内容；新增后需在报告中给出 diff。
- `tests/test_preflight_status_source.py`、`tests/test_finalize_merge_first_call.py`、
  `tests/test_finalize_merge_toctou.py`（仅在新判据使其断言失真时**最小**调整；
  调整必须在报告中逐条说明理由，**不得**为了变绿而削弱攻击形态）

**禁止修改**：`src/agentic_loop/plan_cmd.py`、`validate_wp_status.py`、`autonomy.py`、
`uv.lock`、任何 `docs/plans/**`、`docs/agentic/templates/**`。
（`.agentic/config.toml` 从「禁止」移到「允许」，但**仅限新增 `protected_branch` 一个键**。）

## 7. 完成定义（DoD）

- [ ] E1–E10 全绿（E6 的 **8** 种名称形态逐一参数化，不得合并成一条）。
- [ ] INV-2 的「多于一个持有者」分支虽无验收用例（真实 git 不可构造），代码仍必须显式
      fail-closed 并给出该 witness；报告须指出该分支在代码中的位置。
- [ ] INV-4 映射表：**旧 17 节点 → 新断言**逐条映射齐备（17 行），每个期望值翻转附理由；
      A22/A27/A28 的攻击形态一个都没少（环境伪装、symlink 跟随与环、NUL、超长路径）。
- [ ] M-1 ~ M-8（含 M-2b）逐条红证齐备（含还原回绿，还原后 `git diff` 为空），
      报告附逐条实际输出。M-4/M-5 与 M-7/M-8 必须分别施加、分别验证。
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

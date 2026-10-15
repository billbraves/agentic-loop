# WP-01 — status 来源判据改为「受信任目标分支的持有者」而非「物理主仓」

> rev3 冻结日期 2026-10-15 | 编排者 Kiro（DSH 会话）| 执行者 kimi。
> 状态：**APPROVED（范围已由用户批准冻结）**。
> rev1 快照 `WP-01-brief.rev1.md`（`96a7398f…`）被 `topo-brief-r1` 判 REWORK。
> rev2 快照 `WP-01-brief.rev2.md`（`4e101dca…`）被 `topo-brief-r2` 判 REWORK。
> 本 WP 修改一条经过 A13/A19/A22 加固、且曾被真实绕过的安全判据，因此范围冻结必须由用户批准。

## 1. 问题（编排者已实测复现）

三个调用点共用同一条「status 文件不得位于 worktree 内」的判据：

真实调用那条判据的只有**三处**（rev3 按实测更正，见 D6）：

- `src/agentic_loop/wrappers/preflight.sh:44`
- `src/agentic_loop/wrappers/finalize_merge.sh:160`
- `src/agentic_loop/gate/__init__.py:810`

另有两处只是打印同样的错误文案、但用的是路径字面量而非该判据
（`wrappers/merge.sh:37`、`gate/qoder_security.py:1012`）—— 已拆为独立 WP。

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

## 1.95 rev3 触发原因（brief-r2 REWORK，编排者独立实测确认）

**D4（rev2 的安全主张不成立，必须撤回）**：rev2 声称「两份数据一致即独立锚点」。实测证伪 ——
两个锚点处在**同一写权限域**：

```text
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/evil
  → 单条本地命令即改写锚点 1，不经服务端、不经 push、不需任何批准（/tmp/anchprobe 已复现）
.agentic/config.toml 实测为 git TRACKED 文件
  → 锚点 2 根本不在「仓库之外」，能提交的人与锚点 1 一并移动且保持逐字节一致
```

结论：rev2 的方向是错的，不是实现细节问题。**「同一信任域内的两份数据」不构成独立锚点**，
该安全主张在 rev3 中撤回。

**D5（范围自相矛盾）**：rev2 的 §6 允许新增 `.agentic/config.toml` 的键，但冻结的
`WP-01.status.json` 仍把该文件列在 `forbidden_paths`，实现第一次落笔即越界。

**D6（调用点清单错误）**：rev2 称有五个调用点、其中 `plan_cmd.py` 是 PLAN 侧那个。实测
`plan_cmd.py` **从不调用**该判据（grep 计数 0）。真实调用者只有三个：
`wrappers/preflight.sh:44`、`wrappers/finalize_merge.sh:160`、`gate/__init__.py:810`。

**另一处既存缺陷（已拆为独立 WP，不在本 WP 范围）**：`wrappers/merge.sh:37` 与
`gate/qoder_security.py:1012` 根本没用那条加固判据，而是测路径字面量 `"/.worktrees/"` ——
正是 `test_verdict_does_not_depend_on_directory_name` 记为错误的被废弃做法。实测后果：本机
main 签出路径不含该片段，故这两处**接受**、另三处**拒绝**，即 INV-5 在当前树中**已被违反**，
与本 WP 改动无关。用户已决定由单独 WP 修复。

## 2. 方向（用户已选定；rev3 把锚点移到仓库写权限之外）

把判据从「**是否位于 linked worktree**」改为「**是否是持有受信任目标分支的那个签出**」。
允许该签出本身是 linked worktree；其余所有 worktree 一律仍然拒绝。

rev3 的关键修正（针对 D4）：期望分支由一个**位于仓库写权限之外**的策略文件确定。

```text
锚点（唯一）：  $XDG_CONFIG_HOME/agentic_loop/policy.toml
                 缺省 $HOME/.config/agentic_loop/policy.toml
                 键：  [trust] protected_branch = "main"
```

实测该位置**不在任何 git 工作树内**（`git -C ~/.config rev-parse --show-toplevel` 无仓库），
因此仓库内容 —— 包括被跟踪的 `.agentic/config.toml`、任何 ref、任何提交 —— 都**无法**覆盖它。
改动它需要操作者在自己的用户目录动手，而这正是「仓库写权限之外」的含义。

**明确排除的候选及理由（均经实测）**：

| 候选 | 为何不行 |
| --- | --- |
| `.agentic/config.toml` 的键 | 实测为 git TRACKED 文件，属仓库写权限域内 |
| `refs/remotes/origin/HEAD` | 单条本地 `git symbolic-ref` 即可改写 |
| `git ls-remote --symref origin HEAD`（服务端） | 真在服务端，但 `remote.origin.url` 在本地 `.git/config` 内可改写，可把 origin 指向攻击者仓库；且引入网络依赖 |
| 环境变量（如 `AGENTIC_PROTECTED_BRANCH`） | 调用者声明式事实 —— A22 的绕过家族正是这一类，判据的 docstring 已明确拒绝 |

**INV-1b 随之重写为单锚 + 严格 fail-closed**（见下）。不再有「双锚一致」这一说法。

## 3. 不变量

**INV-1（角色而非位置）**：status 文件的受信任来源是「当前检出**受信任目标分支**的那个
registered worktree」。该 worktree 是物理主仓还是 linked worktree **不影响**判定。

**INV-1b（单一仓库外锚点，关闭 D4）**：受信任目标分支**只**取自仓库外策略文件
`$XDG_CONFIG_HOME/agentic_loop/policy.toml`（缺省 `$HOME/.config/...`）的
`[trust] protected_branch`。

1. 文件缺失、不可读、TOML 非法、缺键、值非字符串或未通过 INV-3 第 1 条的名称校验
   → **一律 fail-closed**，witness 为 `trusted branch policy unavailable`。
   **不得**在任何情形下回退到仓库内的值、`origin/HEAD`、环境变量或硬编码 `"main"`。
2. 该文件若位于任何 git 工作树内 → fail-closed，witness 为
   `trusted branch policy must live outside any git worktree`。此检查使「把策略文件塞进仓库」
   这条回路也被堵死。
3. 仓库内任何同名/同义字段（PLAN 的 `git.target_branch`、WP 状态字段等）**只能**做
   一致性交叉校验：不等则 fail-closed，**永远不**用它覆盖锚点。

实测依据：`~/.config` 不属于任何 git 仓库；而 `.agentic/config.toml` 是被跟踪文件、
`refs/remotes/origin/HEAD` 可被单条本地命令改写，故二者都不能充当锚点。

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

**INV-5（单一权威）**：三个调用点必须继续引用**同一个**判据函数，不得各自实现。新判据与旧
判据不得并存为两条可选路径。

## 4. 验收测试

沿用 `tests/test_worktree_detection.py` 既有真实 git fixture 风格。

- **E1 `[target-branch-in-linked-worktree-is-trusted]`**：构造物理主仓停在
  `plan/x`、受信任目标分支签出在 linked worktree 的真实布局（fixture 中的仓库外策略文件
  声明该分支）；该 worktree 内的 status 路径必须**被接受**。本用例必须自证布局：断言该
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

- **E9 `[policy-anchor-fail-closed]`**（rev3 重写，承载 INV-1b）：参数化覆盖锚点的每一种
  退化形态 —— 文件缺失、不可读、TOML 非法、缺 `[trust]` 段、缺 `protected_branch` 键、
  值非字符串、值未过名称校验 —— **每一种都必须 fail-closed** 且 witness 为
  `trusted branch policy unavailable`。本节点必须额外断言：**没有**任何形态退化成
  「回退到 `main`」或「回退到仓库内值」而放行。

- **E9b `[policy-inside-worktree-is-refused]`**（rev3 新增）：把策略文件放在一个 git 工作树
  内 → fail-closed，witness 为 `trusted branch policy must live outside any git worktree`。

- **E10 `[in-repo-value-cannot-override-anchor]`**（rev3 重写，关闭 D2/D4，并修掉 brief-r2
  对旧 E10 的质疑）：仓库内声明值与锚点不一致时必须 fail-closed，且**不得**改用仓库内的值。
  构造必须使用**合法 schema 对象**（PLAN status 的 `git.target_branch`，或冻结接口的显式
  declared-target 入参），**不得**往 WP fixture 里塞未知字段 —— 否则用例可能因 validator
  拒绝未知字段而变绿，而不是因为锚点不可覆盖（brief-r2 Q3 指出此点）。
  断言必须命中**特异的 mismatch 原因**。

- **E11 `[coordinated-in-repo-move-cannot-retarget]`**（rev3 新增，直接钉死 D4）：同时
  改写 `refs/remotes/origin/HEAD` **并**修改仓库内所有声明值（含 `.agentic/config.toml`），
  模拟「单一行为者协同移动仓库内一切」→ 受信任来源**必须不变**。该节点是 rev2 被判 REWORK
  的那次攻击的回归测试；brief-r2 明确指出 rev2 的 E9/M-8 无法捕获它。

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
- **M-8（rev3 重写）**：给锚点加一条「缺失时回退到 `"main"`」的兜底 →
  **E9 必须转红**。该变异证明严格 fail-closed 承重。
- **M-9（rev3 新增，关键）**：把锚点来源从仓库外策略文件改回仓库内任一位置
  （`.agentic/config.toml` 或 `origin/HEAD`）→ **E11 必须转红**，且红的形态必须是
  协同移动后受信任来源被改写。该变异锁死 D4。
- **M-10（rev3 新增）**：去掉 INV-1b 第 2 条（不检查策略文件是否在工作树内）→
  **E9b 必须转红**。
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
（rev3 取消 rev2 对 `.agentic/config.toml` 的写许可 —— 它是被跟踪文件，不能充当锚点，
故本 WP **不需要也不允许**修改它，D5 的自相矛盾随之消失。锚点文件位于仓库之外，不属于
本仓库任何路径范围；实现须在报告中给出它读取该文件的代码位置与 fail-closed 分支。）
- `tests/test_preflight_status_source.py`、`tests/test_finalize_merge_first_call.py`、
  `tests/test_finalize_merge_toctou.py`（仅在新判据使其断言失真时**最小**调整；
  调整必须在报告中逐条说明理由，**不得**为了变绿而削弱攻击形态）

**禁止修改**：`src/agentic_loop/plan_cmd.py`、`validate_wp_status.py`、`autonomy.py`、
`uv.lock`、任何 `docs/plans/**`、`docs/agentic/templates/**`。

## 7. 完成定义（DoD）

- [ ] E1–E11（含 E9b）全绿（E6 的 **8** 种名称形态、E9 的 **7** 种退化形态逐一参数化）。
- [ ] INV-2 的「多于一个持有者」分支虽无验收用例（真实 git 不可构造），代码仍必须显式
      fail-closed 并给出该 witness；报告须指出该分支在代码中的位置。
- [ ] INV-4 映射表：**旧 17 节点 → 新断言**逐条映射齐备（17 行），每个期望值翻转附理由；
      A22/A27/A28 的攻击形态一个都没少（环境伪装、symlink 跟随与环、NUL、超长路径）。
- [ ] M-1 ~ M-10（含 M-2b）逐条红证齐备（含还原回绿，还原后 `git diff` 为空），
      报告附逐条实际输出。M-4/M-5 与 M-7/M-9 必须分别施加、分别验证。
- [ ] **锚点不可回退自检**：报告须证明不存在任何到 `"main"`、仓库内值或环境变量的回退路径
      （grep 出锚点读取处的全部分支，逐条说明每个分支的归宿）。
- [ ] 保护集全绿：`tests/test_preflight_status_source.py`、
      `tests/test_finalize_merge_first_call.py`、`tests/test_finalize_merge_toctou.py`、
      `tests/test_finalize_merge_sequential.py`。
- [ ] 全量不低于基线 **902 passed / 4 skipped**（新增用例会使总数上升）。
- [ ] **单一权威自检**：报告须列出**三个**真实调用点，并证明它们引用的是同一个判据函数；
      新旧判据不得并存为两条可选路径（INV-5）。
- [ ] **端到端自检**：在「物理主仓停在别的分支、`main` 在 linked worktree」的真实布局下，
      `agentic finalize` 对一个双签完毕的 WP 能够正常盖章（这是本 WP 的存在理由）。
      报告须附实际命令与输出，并说明策略文件当时的内容与位置。
- [ ] 不得出现任何旁路开关（`--allow-worktree-status` / 环境变量等）。

## 8. 残余风险

- 判定与使用之间仍存在 ref/worktree 竞态：某 worktree 可在判定通过后切换分支。与既有
  `base_branch` 判定同类，不在本 WP 范围内，记录在此。
- 本 WP 不改变「status 文件是单一真相源」这一产品语义，只改变「哪个签出持有它」的判定方式。

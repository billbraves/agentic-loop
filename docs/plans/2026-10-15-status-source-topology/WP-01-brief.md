# WP-01 — status 来源判据改为「权威分支（集成分支）持有者」而非「物理主仓」

> rev6 冻结日期 2026-10-15 | 编排者 Kiro（DSH 会话）| 执行者 kimi。
> 状态：**APPROVED（范围已由用户批准冻结）**。
> rev1 快照 `WP-01-brief.rev1.md`（`96a7398f…`）被 `topo-brief-r1` 判 REWORK。
> rev2 快照 `WP-01-brief.rev2.md`（`4e101dca…`）被 `topo-brief-r2` 判 REWORK。
> rev3 快照 `WP-01-brief.rev3.md`（`e94a7670…`）被 `topo-brief-r3` 判 REWORK。
>
> **rev4 是一次降级，不是又一次加固尝试（用户决策 (c)，已批准）。**
> rev1–rev3 都试图建立一个「能写仓库的本地行为者也无法移动的信任根」。rev3 把锚点放到
> 仓库外策略文件 `$XDG_CONFIG_HOME/agentic_loop/policy.toml`，而 `topo-brief-r3` 的 D7
> 实测击穿了它：`XDG_CONFIG_HOME` 本身是**调用者提供**的，`XDG_CONFIG_HOME=/tmp/evil`
> 配一个声明 `feat/evil` 的 policy.toml 即可改向，且该文件不在任何工作树内、**通过** E9b。
> 编排者已独立复现。
>
> 用户据此裁定：在本威胁模型下，能写仓库或能设调用方环境的人本来就能改代码，
> 「不可移动的本地信任根」是伪目标。**本 WP 因此只主张可用性，不主张任何安全性质。**
> rev4 删除锚点架构及其全部验收项与变异，保留与安全主张无关的正确性要求。
> rev4 快照 `WP-01-brief.rev4.md`（`bbe4be96…`）被 `topo-brief-r4` 判 REWORK：
> 判据对象选错（见 §1.98）。**rev5 只改判据对象与三处一致性缺陷，降级决策不变。**
> rev5 快照 `WP-01-brief.rev5.md`（`34dd681b…`）被 `topo-brief-r5` 判 REWORK：
> 名称校验会拒绝真实集成分支（见 §1.99）。**rev6 只修校验规则与冗余条款。**

## 1. 问题（编排者已实测复现）

五个调用点共用同一条「status 文件不得位于 worktree 内」的判据（rev6 更正；WP-02 合并前为三处，见下）：

调用那条判据的共 **五处**（rev6 按 WP-02 合并后的实际状态更正，关闭 D17）：

- `src/agentic_loop/wrappers/preflight.sh:44`
- `src/agentic_loop/wrappers/finalize_merge.sh:160`
- `src/agentic_loop/gate/__init__.py:810`
- `src/agentic_loop/wrappers/merge.sh`（WP-02 前为路径字面量，已改为引用同一判据）
- `src/agentic_loop/gate/qoder_security.py`（同上）

**历史说明**：rev1–rev5 写「三处」，因为当时后两处尚是路径字面量、已拆为 WP-02。
WP-02 已在本集成分支合并（双签 ACCEPT），故本 WP 面对的是五处。

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

## 1.97 rev4 触发原因（brief-r3 REWORK → 用户决策 (c)：撤回安全主张）

`topo-brief-r3` 判 rev3 REWORK，两条缺陷编排者均独立复现：

**D7（锚点被击穿，rev3 的核心主张不成立）**：rev3 把锚点定为仓库外策略文件
`$XDG_CONFIG_HOME/agentic_loop/policy.toml`，声称「仓库写权限之外」。但
`XDG_CONFIG_HOME` 本身是**调用者提供的环境变量** —— 正是 rev3 自己在排除候选表里
以「调用者声明式事实，A22 绕过家族」为由否决的那一类。实测：

```text
XDG_CONFIG_HOME=/tmp/evil  +  /tmp/evil/agentic_loop/policy.toml 声明 feat/evil
  → 受信任目标分支变为 feat/evil
  → 该文件不在任何 git 工作树内，因此 rev3 的 E9b 检查通过
```

即 rev3 的 E9b（「策略文件不得在工作树内」）无法捕获这条路径，而 rev3 把它当作 D4 的
解决方案。锚点与 rev2 被否决的候选处在同一类别。

**D9（INV-3 第 3 条自指矛盾）**：rev3 要求比对基准「取自锚点侧（独立确定）」，同时规定
锚点必须不在任何 git 工作树内 —— 于是「锚点所属仓库」并不存在，该条无法实现。

**用户裁定（决策 (c)）**：在本威胁模型下，能写仓库或能设调用方环境的人本来就能改判据
代码，追求「不可移动的本地信任根」是伪目标。rev1→rev2→rev3 三轮都卡在同一处，说明问题
不在实现细节而在目标设定。**撤回全部安全主张，本 WP 降级为纯可用性修复。**

rev4 因此删除：锚点架构（INV-1b 原文）、排除候选表、E9/E9b/E11、M-8/M-9/M-10/M-2b。
保留与安全主张无关的正确性要求：INV-1/2/2b/3/4/5、E1–E6/E8、E10（改为结构正确性）、
M-1~M-7。

## 1.98 rev5 触发原因（brief-r4 REWORK，编排者独立实测确认，含一处致命缺陷）

**D10（致命：判据对象选错，rev4 的可用性目标不可满足）**：rev4 把判据定为「持有 PLAN
`git.target_branch` 的那个签出」，而 `git.target_branch = main`。实测本机：

```text
git worktree list --porcelain | grep -c "branch refs/heads/main$"   → 0
git cat-file -e main:docs/plans/.../WP-01.status.json               → ABSENT on main
git cat-file -e plan/2026-10-15-...:docs/plans/.../WP-01.status.json → 存在
```

即：**零个 worktree 检出 `main`**，且权威 status 根本不在 `main` 上 —— 它只在集成分支上，
而集成分支的持有者正是本签出。rev4 落地后 INV-2 会立即、必然地
fail-closed（`no checkout holds target_branch`），所有入口仍然全拒 —— 只是把**物理位置
死锁换成了分支生命周期死锁**。这不是实现细节，是对象选择错误。

**用户裁定**：改用**集成分支**（PLAN `git.base_branch`）作为判据对象。理由是它与 WP 生命
周期一致 —— WP 实现期间，权威 status 就在集成分支上，持有它的签出就是单一真相源。

**D11（E1 残留锚点依赖，与 §6 直接矛盾）**：rev4 的 E1 仍写「fixture 中的仓库外策略文件
声明该分支」，而 §6 已明令本 WP 不读取任何仓库外策略文件。rev5 改为用合法 PLAN status
fixture 声明。

**D12（M-2 指向 E3 仍不承重）**：rev4 把 M-2 从已删除的 E7 改指 E3，但 E3 构造的是
「同仓库、检出错误分支」的 worktree —— 去掉 `git-common-dir` 比对后，它仍会被 INV-3
第 2 条（当前分支不等于目标分支）拒绝，E3 不可能因 M-2 转红。rev5 恢复一个**跨仓库混淆
专用**节点 E7 并让 M-2 指向它。

**D13（范围与入口数不一致）**：brief §6 允许改 `merge.sh` / `qoder_security.py`，而 status
的 `forbidden_paths` 明确禁止二者；§1 说「三个调用点」，§7 又说 WP-02 合并后「五个入口」。
rev5 统一为**五个入口**（WP-02 已把 `merge.sh`、`qoder_security.py` 并入同一判据），
并相应修正 status 白名单；同时为 INV-5 补一个验收节点 E12。

## 1.99 rev6 触发原因（brief-r5 REWORK，编排者独立实测确认，含一处致命缺陷）

**D14（致命：名称校验会拒绝真实的权威分支）**：rev5 的 INV-3 第 1 条沿用 rev1 的
「单一路径组件」校验（不含 `/`），但权威分支改为集成分支后，真实值就是
`plan/2026-10-15-status-source-topology` —— **含 `/`**。实测：

```text
PLAN git.base_branch = plan/2026-10-15-status-source-topology   （含 '/'）
INV-3 第 1 条 → 拒绝 → authoritative branch unresolved
git check-ref-format --branch "plan/2026-10-15-status-source-topology" → OK
```

即规格会拒绝它自己指定的权威分支，rev5 仍然 fail-closed，死锁未解。E1/E3/E10 的
fixture 分支名（`plan/x`、`plan/y`、`plan/authoritative`）同样全部不合法。

该校验的**原始目的**是防路径穿越（分支名曾被用于拼接路径）。rev6 改为：
**分支名合法性由 `git check-ref-format --branch` 等价规则判定**（git 自己的 ref 语法），
路径安全由「不把分支名拼进任何路径」这一实现约束保证 —— 候选来自
`git worktree list --porcelain` 的结构化输出，分支名只用于**字符串相等比较**，不参与路径构造。

**D15（M-2 不承重，INV-3 第 3 条冗余）**：brief-r5 指出：候选集由**被校验路径所解析出的
仓库**执行 `git worktree list` 枚举得到，外部仓库 B 的 worktree **根本不可能进入**仓库 A 的
候选集。因此 INV-3 第 3 条（比对 `git-common-dir`）是冗余的，E7 不可能因 M-2 转红。
编排者确认该推理成立。rev6 采用 brief-r5 给的**更小修复**：删除 INV-3 第 3 条、E7 与 M-2，
并把「跨仓库混淆已被候选枚举方式排除」写成显式理由。

**D16（M-11 前提不足）**：rev5 的 M-11（加 `"main"` 回退）需要 E9 的 fixture 中**确有一个活的
`main` 持有者**，否则加回退只会从 `unresolved` 变成 `no holder`，仍是 fail-closed，E9 不会
因错误放行而转红。rev6 在 E9 中补上该前提。

**D17（措辞与旧值残留）**：§2 仍写「`git.target_branch` 的读取不是信任边界」；§1 仍称
「三个调用点」；status 的 `literal_defect` / `wp02_split` 旧值仍说那两个文件禁止修改，与
`allowed_paths` 和 `scope_rev5` 相反。rev6 全部订正，并把旧值显式标记为 superseded。

## 2. 方向（rev6：纯可用性修复，判据对象为集成分支）

把判据从「**是否位于 linked worktree**」改为「**是否是持有权威分支的那个签出**」。
允许该签出本身是 linked worktree；其余所有 worktree 一律仍然拒绝。

**权威分支 = 同一 plan 目录下 PLAN status 的 `git.base_branch`（集成分支）** —— 这是一个
已有的合法 schema 字段，不新增任何机制。

**为什么是 `base_branch` 而不是 `target_branch`（rev5 的核心修正，见 D10）**：WP 实现期间，
权威 status 文件就提交在集成分支上，`target_branch`（`main`）既无人检出、也不含该文件。
按 `target_branch` 判会立即 fail-closed，把物理死锁换成生命周期死锁。按 `base_branch` 判
才与「哪个签出实际持有权威副本」这一产品语义吻合。

PLAN 并入 `main` 之后，**无论集成分支被保留还是删除**，该 plan 目录下的 status 都不再
进入这些 gate（PLAN 已 MERGED），因此不需要阶段感知的来源切换。

**本 WP 明确不主张的性质（rev4 撤回）**：

- 不主张抵御能写仓库内容的本地行为者。该行为者可直接改判据代码。
- 不主张抵御能设置调用方环境的本地行为者。`topo-brief-r3` D7 已实测证明
  `XDG_CONFIG_HOME` 这类调用者提供的位置无法充当信任根。
- 因此 `git.base_branch` 的读取**不是信任边界**，只是配置读取。rev1–rev3 反复试图
  为它找一个不可移动的锚点，rev4 停止这一尝试。

**本 WP 主张的性质**：消除 §1 实测的死锁 —— 在「物理主仓停在别的分支、目标分支签出在
linked worktree」这一真实布局下，`agentic preflight` / `merge` / `finalize` 从完全不可用
变为可用，且不把门放开到「任何 worktree 都接受」。

WP-02 合并后该死锁已从 3 个入口扩大到 **5 个**（`merge.sh`、`qoder_security.py` 由路径
字面量改为引用同一判据），rev4 的收益相应变大。

## 3. 不变量

**INV-1（角色而非位置）**：status 文件的单一真相源是「当前检出**权威分支**（PLAN 的
`git.base_branch`，即集成分支）的那个 registered worktree」。该 worktree 是物理主仓还是
linked worktree **不影响**判定。

**INV-1b（rev5 重写：权威分支来自 PLAN `git.base_branch`，且这不是信任边界）**：权威分支名
取自被校验 status 文件所在 plan 目录下的 PLAN status 的 `git.base_branch`。
（rev4 用 `git.target_branch`，经实测会立即 fail-closed —— 见 D10。）

1. 该字段缺失、非字符串、或未通过 INV-3 第 1 条的名称校验 → fail-closed，witness 为
   `authoritative branch unresolved`。**不得**回退到硬编码 `"main"`、`target_branch` 或任何环境变量。
2. 读取失败（文件不存在、JSON 非法）→ 同样 fail-closed，同一 witness 族。
3. **本条不是信任边界。** 能写仓库的行为者可以改写这个字段，也可以直接改判据代码；
   rev4 不主张抵御该行为者（见 §2 与 §8）。本条的作用是让判据有一个**声明式、单一、
   可审计**的来源，而不是让它抗攻击。rev1–rev3 曾试图为此寻找不可移动锚点并全部失败，
   不要在实现中重新引入锚点、环境变量或仓库外策略文件。

**INV-2（仍然唯一，且必须是活的）**：受信任来源必须唯一。若零个或多于一个 registered
worktree 检出权威分支，一律 fail-closed，两种失败给出**各自特异**的 witness
（`no checkout holds authoritative branch` / `authoritative branch checkout not unique`），不得混同。

**INV-2b（幽灵持有者，编排者实测补入）**：git 的注册表会保留目录已被删除的 worktree 条目，
`git worktree list --porcelain` 对其标记 `prunable`，而 `branch refs/heads/<authoritative>` 仍然在列。
实测：删除 main worktree 目录后它仍被列为 `main` 的持有者，且此时 `git worktree add <new> main`
会以「`main` 已经检出到 `<已删除路径>`」失败 —— 即仓库会卡在一个**无法落地的受信任来源**上。
因此候选必须同时满足「目录存在」且「未被标记 prunable」；只命中幽灵条目时 fail-closed，
witness 为 `authoritative branch holder is stale (prunable)`，**不得**退化成 `no checkout holds`
（二者的修复动作不同：前者需 `git worktree prune`）。

**INV-3（候选必须是本仓库的真实活签出）**：候选 worktree 必须同时满足
（rev4 修正 rev3 的 D9 自指矛盾：比对基准改为**被校验路径自身解析出的仓库**，
rev3 写的是「锚点所在仓库」，而锚点被规定为不在任何仓库内，自相矛盾）：

1. 权威分支名通过 **git 自身的 ref 语法校验**（等价于 `git check-ref-format --branch`）。
   **rev6 修正 D14**：rev1–rev5 沿用「单一路径组件（不含 `/`）」校验，而真实集成分支名
   `plan/2026-10-15-status-source-topology` 含 `/`，规格会拒绝它自己的权威分支。
   原校验的目的是防路径穿越；rev6 改由**实现约束**承担：分支名**只**用于与
   `git worktree list --porcelain` 结构化输出中的 `branch refs/heads/<name>` 做字符串
   相等比较，**不得**拼接进任何路径。空值、非字符串、含 NUL、以及 git 判定非法的 ref
   一律 fail-closed。
2. 该候选的**当前分支**严格等于权威分支；
（**rev6 删除原第 3 条**，关闭 D15：原条款要求比对 `git-common-dir` 以排除「另一个独立
仓库里同名分支」。但候选集本就由**被校验路径所解析出的仓库**执行 `git worktree list`
枚举得到 —— 外部仓库的 worktree 根本不可能进入候选集，该条款冗余，其配套的 E7 与 M-2
也不可能承重。`topo-brief-r5` 指出此点，编排者确认成立。跨仓库混淆的排除理由因此改为
**显式记录在枚举方式上**：候选只来自被校验仓库自己的注册表。）

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

签名变更必须在交付中显式说明：新判据需要「目标分支」这一入参，或由其内部从 PLAN status
解析，二者择一但必须**全仓统一**（INV-5）。rev4 不再有「解析锚点」这一选项。

**INV-5（单一权威，rev5 更正为五个入口）**：WP-02 合并后 `merge.sh` 与 `qoder_security.py` 已由
路径字面量改为引用同一判据，故调用点共 **五个**，必须继续引用**同一个**判据函数，不得各自实现。新判据与旧
判据不得并存为两条可选路径。

## 4. 验收测试

沿用 `tests/test_worktree_detection.py` 既有真实 git fixture 风格。

- **E1 `[authoritative-branch-in-linked-worktree-is-trusted]`**：构造物理主仓停在
  `plan/x`、**权威分支签出在 linked worktree** 的真实布局（由 fixture 中的**合法 PLAN
  status** 的 `git.base_branch` 声明该分支 —— rev5 修掉 rev4 残留的仓库外策略文件依赖，
  见 D11）；该 worktree 内的 status 路径必须**被接受**。本用例必须自证布局：断言该
  签出的 `--git-dir != --git-common-dir`（即在旧判据下会被拒），否则节点可能因无关原因变绿。
- **E2 `[primary-repo-holding-authoritative-branch-still-trusted]`**：物理主仓本身检出权威分支
  的传统布局必须仍然被接受（兼容性，不得只支持新布局）。
- **E3 `[other-worktree-still-refused]`**：同一仓库另一个检出 `plan/y` 的 worktree 内的
  status 路径必须**仍被拒绝**，witness 为 `checkout does not hold authoritative branch`。
- **E4 `[no-holder-fails-closed]`**：没有任何 registered worktree 检出权威分支
  → 拒绝，witness 为 `no checkout holds authoritative branch`。
- **E5 `[stale-holder-fails-closed]`**（原「多持有者」形态经实测不可构造，改为此形态）：
  注册一个检出权威分支的 worktree 后**删除其目录**，使注册表留下 `prunable`
  幽灵条目 → 必须 fail-closed，witness 为 `authoritative branch holder is stale (prunable)`。
  本用例必须自证前提：断言该条目仍出现在 `git worktree list --porcelain` 且带 `prunable`、
  断言其目录确实不存在。
  **实测说明（编排者）**：git 硬性拒绝同一分支被签出两次（`fatal: 'main' is already
  checked out at ...`），detached HEAD 的 `branch --show-current` 为空字符串，故「两个活的
  worktree 同时检出权威分支」在真实 git 下**无法构造**。INV-2 的「多于一个」分支因此
  是**防御性**的（防注册表损坏或未来 git 行为变化），由代码 fail-closed 承担，不要求验收用例；
  承重由 E5 的幽灵形态提供。
- **E6 `[authoritative-branch-name-is-validated]`**（rev6 重写，关闭 D14）：
  **正向（必须通过）**：合法的带 `/` 集成分支名，至少含真实形态
  `plan/2026-10-15-status-source-topology` 与 `feature/x-y` —— rev1–rev5 的校验会错误地
  拒绝它们，本断言钉死该缺陷不再出现。
  **负向（必须 fail-closed，原因须指向名称校验，不得是偶然的「分支不存在」）**：
  空字符串、含 NUL、`..`、`.`、以 `.` 开头、以 `/` 开头或结尾、含 `//`、含空格、
  含 `~` `^` `:` `?` `*` `[`、以 `.lock` 结尾 —— 即 `git check-ref-format --branch`
  判定非法的形态，至少覆盖上述 **12** 种。
  （rev1 只列 5 种；brief-r1 补入反斜杠/点号前缀/NUL；rev6 改为 git ref 语法后，形态集
  相应重排，并新增正向用例。）

- **E9 `[authoritative-branch-unresolved-fails-closed]`**（rev5 重写，承载 INV-1b 第 1/2 条）：
  参数化覆盖 PLAN status 的每一种退化形态 —— 文件不存在、JSON 非法、缺 `git` 段、
  缺 `base_branch` 键、值非字符串、值未过名称校验 —— **每一种都必须 fail-closed**，
  witness 为 `authoritative branch unresolved`。本节点必须额外断言：**没有**任何形态退化成
  「回退到 `main`」而放行。
  **fixture 前提（rev6 补入，关闭 D16）**：本节点的 fixture 中必须**确有一个活的 `main`
  持有者**。否则 M-11（加 `"main"` 回退）只会把 `unresolved` 变成 `no holder`，仍是
  fail-closed，E9 不会因错误放行而转红 —— `topo-brief-r5` 指出此点。有该持有者时，加入
  回退会使一个本应 unresolved 的输入**被错误接受**，E9 才真正承重。
  （rev3 的 E9/E9b 绑定仓库外策略文件锚点，随锚点架构一并删除；rev3 的 E11
  `[coordinated-in-repo-move-cannot-retarget]` 断言「协同改写仓库内一切后受信任来源不变」，
  这正是 rev4 撤回的安全主张，故删除。）

- **E10 `[judged-object-cannot-declare-its-own-basis]`**（rev4 重写，承载 M-7）：
  权威分支**必须**取自 PLAN status 的 `git.base_branch`，**不得**取自被校验的 WP status
  文件自身。构造必须精确指定被误读的字段（rev5 按 brief-r4 Q4 要求消除歧义）：
  **WP status 自身的 `git.base_branch`** —— 它是合法 schema 字段、且与 PLAN 同名，正是
  实现最可能误读的位置。令 PLAN 声明 `plan/authoritative`、而该 WP 自身声明
  `plan/attacker`，判定必须以 **PLAN** 的值为准。
  构造必须使用**合法 schema 对象**，**不得**往 fixture 里塞未知字段 —— 否则用例可能因
  validator 拒绝未知字段而变绿，而不是因为来源正确（brief-r2 Q3 指出此点）。
  **这是结构正确性要求（判定依据不能由被判定对象提供），不是安全主张** —— 能写仓库者
  同样可以改 PLAN status，rev4 不主张抵御他。

- **E12 `[one-predicate-across-all-five-call-sites]`**（rev5 新增，承载 INV-5，关闭 D13）：
  静态断言五个入口（`preflight.sh`、`merge.sh`、`finalize_merge.sh`、`gate/__init__.py`、
  `gate/qoder_security.py`）全部引用**同一个**判据函数，且不存在第二条可选路径。
  rev4 只在 DoD 里要求报告自检，没有验收节点 —— brief-r4 Q2 指出此为缺口。

- **E8 `[hardening-preserved]`**：A22/A27/A28 的既有断言在新判据下复跑全绿 —— 不新增
  用例，直接复用 `tests/test_worktree_detection.py` 的 17 个节点作为护栏。

## 5. 承重变异（DoD 必做，逐条分别施加、分别验证、精确还原）

- **M-1**：把 INV-2b 的存活性检查去掉（接受 prunable 幽灵条目）→ **E5 必须转红**。
- **M-3**：去掉 INV-3 第 1 条（名称校验）→ **E6 必须转红**（12 种负向形态中至少 1 种）。
- **M-7（rev5 重写，消除 brief-r4 Q4 指出的歧义）**：把权威分支的来源从 PLAN status 的
  `git.base_branch` 改为**被校验 WP status 自身的 `git.base_branch`** →
  **E10 必须转红**，且红的形态必须是「被校验对象自己声明了自己的判定依据」。
  该变异保留 brief-r1 Q1 指出的自证循环防护 —— 这是**结构正确性**要求（判定依据不能由
  被判定对象提供），不是安全主张。
- **M-4**：把判据退回旧形态（纯 `--git-dir != --git-common-dir`）→ **E1 必须转红**（E1 已按 D11 改用合法 PLAN fixture），
  且红的原因必须是「被判为 worktree 而拒绝」。该变异锁死本 WP 要消除的死锁。
- **M-5**：把判据放宽成「任何 registered worktree 都接受」→ **E3 必须转红**。
  该变异证明新判据没有把门彻底打开（与 M-4 方向相反，两者都必须承重）。
- **M-6**：恢复 A22 的环境继承（不剥离 `GIT_DIR` 家族）→
  `test_caller_env_cannot_disguise_*` 必须转红。证明加固未退化。
- **M-11（rev5 新增，承载 INV-1b 的「不得回退」）**：给权威分支读取加一条「PLAN 读取失败
  时回退到 `"main"`」的兜底 → **E9 必须转红**。brief-r4 Q4 指出 rev4 的 INV-1b 这半没有
  变异守护。
- **M-12（rev5 新增，承载 INV-5）**：让五个入口中的任意一个绕过统一判据、改为自己实现
  → **E12 必须转红**。brief-r4 Q4 指出 INV-5 没有变异守护。

M-4 与 M-5 必须**分别**验证：两者同时承重才说明判据既解了死锁、又没有放开边界。

## 6. 范围

**允许修改**：

- `src/agentic_loop/gate/__init__.py`（判据本体）
- `src/agentic_loop/gate/qoder_security.py`（调用点对齐；WP-02 已把它并入同一判据）
- `src/agentic_loop/wrappers/finalize_merge.sh`、`preflight.sh`、`merge.sh`（调用点对齐）

（rev5 关闭 D13：brief §6 与 status `forbidden_paths` 此前对 `merge.sh` /
`qoder_security.py` 相互矛盾。WP-02 合并后二者已引用同一判据，本 WP 必须能改它们，
故 status 白名单同步更正为**五个入口**。）
- `tests/test_worktree_detection.py`（新增 E1–E10，并按 INV-4 做保前提改写）

（rev4：锚点架构已删除，故本 WP 既不修改 `.agentic/config.toml`，也不读取任何仓库外
策略文件。实现须在报告中给出它读取 PLAN status `git.base_branch` 的代码位置与全部
fail-closed 分支，并确认**没有**引入环境变量或仓库外文件作为来源。）
- `tests/test_preflight_status_source.py`、`tests/test_finalize_merge_first_call.py`、
  `tests/test_finalize_merge_toctou.py`（仅在新判据使其断言失真时**最小**调整；
  调整必须在报告中逐条说明理由，**不得**为了变绿而削弱攻击形态）

**禁止修改**：`src/agentic_loop/plan_cmd.py`、`validate_wp_status.py`、`autonomy.py`、
`uv.lock`、任何 `docs/plans/**`、`docs/agentic/templates/**`。

## 7. 完成定义（DoD）

- [ ] E1–E6、E8、E9、E10、E12 全绿（E6 的 **1 组正向 + 12 种负向**形态、E9 的 **6** 种退化形态逐一参数化）。
- [ ] INV-2 的「多于一个持有者」分支虽无验收用例（真实 git 不可构造），代码仍必须显式
      fail-closed 并给出该 witness；报告须指出该分支在代码中的位置。
- [ ] INV-4 映射表：**旧 17 节点 → 新断言**逐条映射齐备（17 行），每个期望值翻转附理由；
      A22/A27/A28 的攻击形态一个都没少（环境伪装、symlink 跟随与环、NUL、超长路径）。
- [ ] M-1、M-3、M-4、M-5、M-6、M-7、M-11、M-12 逐条红证齐备（含还原回绿，还原后
      `git diff` 为空），报告附逐条实际输出。M-4 与 M-5 必须分别施加、分别验证。
      （rev6 删除 M-2 与 E7：候选枚举方式已排除跨仓库混淆，该变异不可能承重 —— D15。）
- [ ] **分支名校验自检**：报告须证明合法的带 `/` 集成分支名被接受（含真实值
      `plan/2026-10-15-status-source-topology`），且分支名**没有**被拼接进任何路径
      （给出代码位置）。
- [ ] **不可回退自检**：报告须证明不存在任何到硬编码 `"main"`、`target_branch` 或环境变量的回退路径
      （grep 出目标分支读取处的全部分支，逐条说明每个分支的归宿）。
- [ ] 保护集全绿：`tests/test_preflight_status_source.py`、
      `tests/test_finalize_merge_first_call.py`、`tests/test_finalize_merge_toctou.py`、
      `tests/test_finalize_merge_sequential.py`。
- [ ] 全量不低于基线 **912 passed / 4 skipped**（WP-02 已把基线从 902 提升到 912；新增用例会使总数继续上升）。
- [ ] **单一权威自检**：报告须列出**五个**真实调用点，并证明它们引用的是同一个判据函数；
      新旧判据不得并存为两条可选路径（INV-5）。该自检由 E12 承载、M-12 守护。
- [ ] **端到端自检（本 WP 的存在理由）**：在「物理主仓停在别的分支、目标分支在 linked
      worktree」的真实布局下，`agentic preflight`、`agentic merge`、`agentic finalize`
      三者对一个双签完毕的 WP 都必须可用。报告须附实际命令与输出。该死锁覆盖 **5** 个
      入口，实现须确认五者一致。
      **实测前提（编排者 2026-10-15）**：本机零个 worktree 检出 `main`，而集成分支
      `plan/2026-10-15-status-source-topology` 由本签出持有且含权威 status —— 这正是
      rev5 改用 `base_branch` 的依据（D10）。端到端自检须在该真实布局下进行。
- [ ] 不得出现任何旁路开关（`--allow-worktree-status` / 环境变量等）。

## 8. 残余风险

- **本 WP 不防御能写仓库内容的本地行为者**，也不防御能设置调用方环境的本地行为者。
  该行为者可改写 PLAN status 的 `git.base_branch`，也可直接改判据代码。依据：
  `topo-brief-r3` D7 实测 —— rev3 把锚点放到仓库外策略文件后，
  `XDG_CONFIG_HOME=/tmp/evil` 配一个声明 `feat/evil` 的 policy.toml 即可改向，且该文件
  不在任何工作树内、通过了 rev3 的 E9b；编排者已独立复现。用户据此裁定此类本地信任根
  为伪目标（决策 (c)）。**凡在评审中要求本 WP 抵御该行为者的意见，都超出已批准范围。**
- 判定与使用之间仍存在 ref/worktree 竞态：某 worktree 可在判定通过后切换分支。与既有
  `base_branch` 判定同类，不在本 WP 范围内，记录在此。
- 本 WP 不改变「status 文件是单一真相源」这一产品语义，只改变「哪个签出持有它」的判定方式。
- 权威分支取 `base_branch`（集成分支）而非 `target_branch`。**rev6 按 brief-r5 更正措辞**：
  不声称「集成分支随之消失」（git merge 并不必然删除分支），而是：**无论集成分支在 PLAN
  合并后被保留还是删除，已 MERGED 的 plan 的 status 都不再进入这些 gate**，故不需要阶段
  感知切换。若未来出现「PLAN 已 MERGED 但仍需校验其 status」的流程，需另开 WP。
- 判据仍对无法 resolve 的路径 fail-closed（A19/A27 行为），rev4 不改变这一点。

# WP-17: 给「实现者身份不可观测」补一条 engine-verifiable 的独立性判据（A5 修法 2）

> 冻结日期 2026-09-14 ｜ 编排者 Claude ｜ 执行者 kimi
> **状态：已冻结，执行期间不得修改**（修订须走 re-freeze，出 `rev2`）。
> 本 WP 改动合并门的准入语义，属产品级契约变更。
> 三个设计点 + 基线分支均已由用户于 2026-09-14 裁定
> （见「设计裁定」与「⚠️ 顺序约束」两节）。
> 基线：`feature/wp08-independence-degraded` @ `a46578c`，合并序 WP-08 → WP-17。

## 目标（一句话）

在 `independence.evaluate()` 里补一条判据：当实现者身份 engine 观测不到时，
用 **engine 可自行验证的隔离证据**（而非自证声明、也非可伪造的配置字符串）
支撑一个诚实 `ACCEPT` 达到 `weak`。

## 背景

缺陷 A0 / A5 的合流结果是：本仓拓扑下 `evaluate()` 三条路径全部不可达。

| 路径 | 阻塞点 | 可达 |
|------|--------|------|
| strong | `gate/__init__.py:756` 硬编码 `reviewer_id=None` | 否 |
| degraded | kimi 跑 codingplan/k3、不经框架 provider 层，implementer 身份观测不到 | 否 |
| bootstrap | 唯一信号是 `ReviewerAttestation`，其 `fresh_session` 本轮为假，如实写必不过 | 否 |

用户 2026-09-14 裁定走修法 2（不走「给 developer 绑 provider」的修法 1）。
修法 1 被 codex 咨询否掉的核心理由（`WP-15-consult-codex.md` P0）：
`identity_model` 直接来自可手改的 TOML，`build_binding()` 原样读、
`identity()` 原样返回，注入探针只验 sentinel 不验模型——**任何人都能声明一个
与真实路由不符的模型来伪造 degraded 独立性，现有代码无任何防线**。

**本 WP 必须避免重犯同一错误。** 这是本 WP 最重要的设计约束：

> 新判据的证据必须是 **engine 能自己核对的事实**，
> 不能是「某人在某个文件里写的一句话」。

一条「实现者身份不可观测时就放宽」的路径，如果它的证据是编排者填的字段，
那它跟 bootstrap 的自证没有本质区别，只是换了字段名——这种改法**不要做**。

## 核心设计：什么算 engine-verifiable

A5 原记录提出的方向是「commit 作者 + 隔离 worktree」。它可用，但要挑出其中
engine 真能验证的部分：

| 候选证据 | engine 能否自验 | 判断 |
|---------|----------------|------|
| commit 的 author/committer 与编排者身份**不同** | 能：`git log -1 --format=%an%n%ae` | ✅ 可用 |
| 实现提交落在**独立 branch**，且不是 base_branch | 能：`git rev-parse --abbrev-ref` + 与 `git.base_branch` 比 | ✅ 可用 |
| 实现提交的 **tree 与 base_commit 的 tree 不同**（真有改动，不是空提交） | 能：`git rev-parse <c>^{tree}` | ✅ 可用 |
| 改动**全部落在 `scope.allowed_paths` 内** | 能：已由 `quality-gate.sh` 的 scope enforcement 实现 | ✅ 可复用 |
| 「实现者是另一个进程/另一个模型」 | **不能**：无可信信号 | ❌ 不可用 |
| `executor.tool` 字段的值 | **不能**：status 文件里的自填字符串 | ❌ 不可用 |
| `identity_model` | **不能**：见上文 P0 | ❌ 不可用 |

**共同点**：可用的四项都是 **git 事实**——engine 拿 `git` 命令就能独立核对，
不依赖任何角色的自我声明。这是它与 bootstrap attestation 的本质区别。

**这条判据证明的到底是什么**（诚实边界，必须写进 reasons 与文档）：

> 它证明的是「**审核对象是一份由他方产生、经隔离、范围受限的改动**」，
> **不是**「审核者与实现者是不同的模型」。后者在本仓拓扑下 engine 无法证明。

所以它**只能评到 `weak`，绝不能评 `strong`**。`strong` 的语义是
engine 观测到两个不同模型，这条判据一个模型都没观测到。

## 设计裁定（用户 2026-09-14 已裁定，实现须照此办）

### 裁定 1：复用 `weak`，**不新增级别**

**`INDEPENDENCE_LEVELS` 与 `_LEVEL_RANK` 一处不改。** 新判据评出的就是 `weak`，
在 `reasons` 里以 `level=weak-isolated` 标明来源。

曾考虑的方案 1b（新增一级 `weak-isolated` 排在 `weak` 与 `none` 之间）已否决：
改 `_LEVEL_RANK` 是破坏性变更——现有 `min_independence = "weak"` 的配置会
**拒绝**这个更低的新级别，A0 依然锁死，还得连带改 `.agentic/config.toml`（用户域）。

代价（已接受）：`weak` 承载三种来源（同模型 / attested / isolated），
靠 `reasons` 与 `consult.independence` 的留痕区分。因此 **reasons 必须写清来源**，
这不是可选的日志美化，而是本裁定成立的前提——审计要能从留痕分辨走的是哪条路。

### 裁定 2：**要求** `capabilities.sandbox_enforced`

consultant 是这条路上唯一的外部签名，它的沙箱与结构化输出必须已证，
否则「他方审核」不成立。

对齐现状：现有 bootstrap override（`gate/__init__.py:777-779`）已额外要求
`capabilities.sandbox_enforced`；`_weak_engine_enforced()` 要求
`sandbox_enforced` + `structured_output`。CodexAdapter 两项皆 `True`
（`adapters/codex.py:38-43`），故此要求不会挡住本仓。

实现上直接复用 `_weak_engine_enforced()` 的 `weak_ok` 即可（它已含这两项），
**不要另写一份并行的能力检查**——那会造出第二份口径（全局 CLAUDE.md §5.3）。

### 裁定 3：`git` 事实由 `gate/` 读好后传入

`independence.evaluate()` 是**纯函数**（`independence.py:5` 明确「no I/O」），
git 事实**不得在 `evaluate()` 里读**。

新增 frozen dataclass `IsolationEvidence`，字段是 engine 已核对的
**布尔结论 + 供留痕的原始值**，由 `gate/main()` 用 `git` 填充后传给 `evaluate()`。
这保住 `evaluate()` 的纯函数性质（全局 CLAUDE.md §5.8）。

**硬性约束**：`evaluate()` 里不得出现 `subprocess`、`os`、`pathlib` 的任何调用，
也不得 import `git` 相关模块。DoD 有一条专门验这个。

## 范围

**allowed_paths**
- `src/agentic_loop/independence.py`
- `src/agentic_loop/adapters/base.py`（仅新增 `IsolationEvidence` dataclass）
- `src/agentic_loop/gate/__init__.py`
- `tests/test_independence_isolated.py`（新建）
- `tests/test_gate_independence_isolated.py`（新建）

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`（**尤其禁止**：不得改 `min_independence`，
  不得给任何角色加 provider 绑定）
- `src/agentic_loop/provider_binding.py`（修法 1 的地盘，本 WP 不碰）
- `src/agentic_loop/adapters/kimi.py`（WP-15 的 allowed path，避免撞车）
- `src/agentic_loop/wrappers/`
- 其余一切未在 allowed 列出的路径

## ⚠️ 顺序约束（用户 2026-09-14 已裁定：选 A，WP-08 作上游依赖）

**本 WP 与 WP-08 改同两个文件，且 WP-08 尚未合并。**

已核实：主区 `src/agentic_loop/gate/__init__.py` **不含**
`_should_populate_implementer`（`grep -c` 为 0），该函数只存在于未合并的
`feature/wp08-independence-degraded`。而 `quality-gate.sh:26` 用的是
**当前 worktree** 的代码，`:112` 的配置读 `main_repo`。

后果：
1. 若本 WP 从主区开分支，会与 WP-08 的 diff 在 `gate/__init__.py` 的同一区域冲突；
2. 更要紧的是 **WP-08 的合并本身还卡在 A0**——而本 WP 就是去解 A0 的。
   本 WP 自己的合并也要过同一道门，形成自举问题。

### 裁定：基于 `feature/wp08-independence-degraded` 开分支

不动用例外合并授权。据此固定：

| 项 | 值 |
|----|----|
| `git.base_branch` | `feature/wp08-independence-degraded`（**不是** `plan/2026-09-13-parallel-throughput`） |
| `git.base_commit` | `a46578c`（该分支 HEAD，编排者已核实） |
| `git.branch` | `feature/wp17-isolation-evidence` |
| `git.worktree` | `../wp17-isolation-evidence` |
| 合并顺序 | **WP-08 → WP-17**，不可调换 |

基线已核实干净（2026-09-14）：
- `feature/wp08-independence-degraded` = `a46578c`，其父提交正是
  `802b667`（本 plan 分支 HEAD），**无分叉、无需 rebase**；
- 该分支上 `gate/__init__.py` 含 `_should_populate_implementer`（`grep -c` = 2），
  `independence.py` 不含 `IsolationEvidence`（`grep -c` = 0）——本 WP 是净新增，
  与 WP-08 的改动不在同一函数内；
- WP-08 状态 `READY_FOR_REVIEW`，`review.decision = ACCEPT`，
  `git.commit = a46578cf…`，只差用户授权合并。作为上游依赖合格。

### 为什么两者互补而非替代（实现者必须理解这条，否则会写出重复判据）

WP-08 的 `_resolve_implementer_identity()` 从 **developer 角色的 provider 绑定**
解析实现者 model。它在有绑定时有效，走 degraded 路径拿 `weak`。

但 WP-08 的验收证据里记着一条决定性事实：`.agentic/config.toml` 在
2026-09-13T23:37 被会话外改动，`developer` 从
`{adapter = "kimi", provider = "deepseek"}` 变成裸字符串 `"kimi"`。
**没有 developer 绑定时** `_resolve_implementer_identity()` 正确地 fail-close 到
`None`，于是 `is_bootstrap_normal` 又变回 `True`，`evaluate()` 返回 `none`,
A0 原封不动地回来了。这就是缺陷 A5。

所以两条路径的分工是：

```
有 developer 绑定  -> WP-08 的 degraded 路径（实现者 model 可观测）-> weak
无 developer 绑定  -> 本 WP 的 isolation 判据（实现者 model 不可观测，
                      但 git 事实可核）              -> weak（weak-isolated）
两者都不满足        -> none（fail-closed，不变）
```

**实现要求**：本 WP 的判据必须放在 WP-08 的 degraded 检查**之后**，
只在 `bootstrap and compare_against is None` 分支内生效。
绝不能绕过或改写 degraded 路径——有绑定时仍应优先走 WP-08 的路径，
因为「实现者 model 被 engine 观测到」是比「git 事实可核」更强的证据。

## 交付物清单

1. `adapters/base.py` 新增 frozen dataclass `IsolationEvidence`，字段建议：
   `author_differs_from_orchestrator: bool`、`branch_is_isolated: bool`、
   `tree_differs_from_base: bool`、`scope_respected: bool`，
   外加供审计留痕的原始值（author、branch、commit、base_commit）。
   **不带默认真值**：所有布尔默认 `False`，fail-closed。
2. `independence.py`：`evaluate()` 增 keyword-only 参数
   `isolation: IsolationEvidence | None = None`（**必须有默认值**，
   否则破坏所有现有调用点与测试）。
   在 bootstrap 且 `compare_against is None` 的分支里，
   **排在现有 attestation 判定之后**作为另一条出路：
   四项布尔全 `True` 且 `weak_ok` 为真 → 返回 `weak`，
   reasons 记 `level=weak-isolated` 及每一项的原始值。
   任一项为 `False` → 不放行，落回现有 fail-closed。
3. `gate/__init__.py`：在 `is_bootstrap_normal` 为真时，用 `git` 读出四项事实
   构造 `IsolationEvidence` 传入 `evaluate()`。
   git 调用失败/信息缺失 → 传 `None` 或全 `False`，**绝不猜**。
4. 文档：在 reasons 与 `consult.independence` 留痕里明确
   「isolated 证明的是改动来源与隔离，不是模型差异」。
5. 测试：见 DoD。

## 完成定义（DoD）

- [ ] **characterization test 先行**：先固化 `evaluate()` 现有全部分支
      （strong / weak / weak-attested / degraded / none）在
      `isolation=None` 时**逐字不变**，证明零回归
- [ ] 正向：四项布尔全 `True` + `weak_ok` → `weak`，reasons 含 `weak-isolated`
- [ ] **反向逐项**：四项里每次只置一项 `False`（共 4 个用例）→ 均不放行
- [ ] 反向：`isolation` 四项全 `True` 但 `capabilities` 不满足 → 不放行
- [ ] **反证 strong 不可达**：`isolation` 全 `True` 时
      `meets_threshold(level, "strong")` 仍为 `False`——这条判据永不评 strong
- [ ] **`evaluate()` 仍是纯函数**：不引入任何 I/O、`subprocess`、
      文件读写或 `git` 调用（全局 CLAUDE.md §5.8）
- [ ] `ReviewerAttestation` 的既有语义与 `is_valid()` 的严格 `is True`
      判定**一处未改**——本 WP 是补一条出路，不是放宽既有那条
- [ ] **`INDEPENDENCE_LEVELS` 与 `_LEVEL_RANK` 一处未改**（裁定 1）
- [ ] **`reasons` 必须标明来源**：走本判据时含 `level=weak-isolated`，
      且四项 git 事实的原始值（author / branch / commit / base_commit）均在
      `reasons` 里可见——裁定 1 复用 `weak` 的前提就是留痕可区分三种来源
- [ ] **能力检查复用 `_weak_engine_enforced()`**（裁定 2），
      不另写一份并行的 `sandbox_enforced` / `structured_output` 判断
- [ ] **`evaluate()` 内无 `subprocess` / `os` / `pathlib` 调用、无 git 相关 import**
      （裁定 3）——可用 `grep` 于该函数体内核验
- [ ] **WP-08 的 degraded 路径仍然优先且仍然可达**：给 developer 加回
      provider 绑定的场景下（实现者 model 可观测），`evaluate()` 必须仍走
      WP-08 的 degraded 路径拿 `weak`，reasons **不含** `weak-isolated`——
      本 WP 只在实现者 model 不可观测时才生效，不得抢先。
      这条要有正向用例，因为它是「互补而非替代」的可执行证明
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
- [ ] 无 forbidden_paths 写入（特别确认没碰 `.agentic/config.toml`）
- [ ] 无生产 DB 写入、无网络、无推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **本 WP 是合并门的准入语义变更，写宽一寸就等于把门拆了。**
   任何「拿不到证据就当通过」的写法都是缺陷。所有缺失信号一律 fail-closed。
2. **不要把新判据做成「实现者说自己独立就算独立」。** 判据的每一项都必须是
   engine 用 `git` 独立核对出来的，不接受任何来自 status 文件的自填字段
   （`executor.tool` 尤其不算证据）。
3. `evaluate()` 现有 `bootstrap and compare_against is None` 分支里
   attestation 的判定**不要动**，新判据**并列**在其后。两条都不满足才落 none。
4. `_LEVEL_RANK` 里 `none` 永不满足任何门限（含 `min_independence="none"`），
   这是 fail-closed 地板，别动。
5. **本仓 `requires-python = ">=3.9"`**（`pyproject.toml:8`）。
6. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
7. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个与本 WP 无关，勿修。
8. **`git` 事实的读取要能在 detached HEAD 与 worktree 下正确工作**，
   拿不到就 fail-closed，不要退化成「假设在 base_branch 上」。
9. **本 WP 的基线不是 plan 分支**（见「⚠️ 顺序约束」）。建 worktree 时是
   `git worktree add ../wp17-isolation-evidence -b feature/wp17-isolation-evidence feature/wp08-independence-degraded`。
   若误从 `plan/2026-09-13-parallel-throughput` 开，`gate/__init__.py` 里
   就没有 `_should_populate_implementer`，「degraded 路径仍可达」那条 DoD
   无从验证，且合并时会与 WP-08 的 diff 冲突。
10. **`git rev-parse HEAD` 的 author 不能拿编排者当对照物写死。**
    `author_differs_from_orchestrator` 的对照基准要说清楚是跟谁比——
    实现建议取 `base_commit` 的 committer 或配置里的编排者身份，
    但**无论取哪个都必须在 reasons 里写明对照基准是什么值**，
    否则这项布尔在审计时无法复核。拿不到对照基准 → `False`，不猜。
11. **B7（见 `WP-08-candidate.md`）**：本机 `agentic *` 跑的是 uv 非 editable
    安装的另一个仓的快照，不是本仓 `src/`。所以**改完 `independence.py` 后，
    用 `agentic quality-gate` 是验不到你的改动的**。本 WP 的测试一律用
    `python3.11 -m pytest`（直接跑工作树代码），不要靠 `agentic` 子命令自证。

## ⚠️ 合并操作序（编排者用，执行者不执行合并）

`merge.sh:82` 要求 `git merge` 时**必须站在 `base_branch` 上**
（`if [[ "$current" != "$base_branch" ]] -> MERGE_FAIL`）。
本 WP 的 `base_branch` 是 `feature/wp08-independence-degraded`，不是 plan 分支。
故合并序固定为：

1. 用户授权后，先在 `plan/2026-09-13-parallel-throughput` 上合 WP-08
   （`git merge --no-ff feature/wp08-independence-degraded`），
   再 `agentic finalize docs/plans/…/WP-08.status.json`；
2. WP-08 落地后，WP-17 的 `base_branch` 已被并入 plan 分支。此时**须先把
   WP-17.status.json 的 `git.base_branch` re-freeze 成
   `plan/2026-09-13-parallel-throughput`**，否则 `merge.sh` 会要求站到一个
   已合并掉的 feature 分支上；
3. 然后在 plan 分支上合 WP-17，再 `agentic finalize`。

第 2 步是必须的一次 status 修订，不是疏漏——`base_branch` 在派发期
指向 WP-08 分支（为了 worktree 起点正确），在合并期必须指向 plan 分支
（为了 `merge.sh` 的站位检查）。这一对时序矛盾与缺陷 A4 同源。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的 characterization / 逐项反向 / strong 不可达反证见上文 DoD。

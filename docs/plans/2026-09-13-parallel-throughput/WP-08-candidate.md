# WP-08（候选）：dogfood 首轮暴露的框架自身缺陷清单

> 状态：**候选，未冻结**，等用户裁定纳入本迭代 / 另起迭代 / 拆分。
> 来源：2026-09-13 首轮并行（WP-01 + WP-03）dogfood 期间由编排者实测踩到，
> 每条都有可复现证据，非推测。

## 分级

**A 类 = 开箱即坏**（`agentic init` 出来的默认配置过不了自己的门，
或框架允许的合法配置过不了自己的派发门——A4、A7 属后者，
A8 更进一步：判据设计正确但本仓拓扑让它恒不放行），
**B 类 = 误导性错误信息**（信息不足导致误诊，浪费一轮排查），
**C 类 = 契约与模板不一致**（模板默认值与生命周期约束互相打脸）。

> ⚠️ **B7 是 B 类里的异类**：它不只是信息误导，而是「门禁跑的根本不是本仓的代码」。
> 之所以仍归 B 而非 A，是因为它不改变任何单个 WP 的判定正确性（判据文件当前两边一致），
> 但它使整轮 dogfood 的验证证据链失去机制保证。**修 B7 的优先级应高于其余 B 类。**

## A 类

### A0. 双签合并门在「编排者即审核者」的正常路径下无法通过，除非编排者自证一个可能为假的声明

- 证据：`agentic gate` 对 WP-01 实跑结果：
  `GATE_FAIL: independence level none does not meet minimum weak; reasons:
  reviewer identity unavailable (orchestrator, attested not engine-proven);
  no implementer fallback available; reviewer attestation missing`。
- 机制：`independence.evaluate()` 有三条路径。strong 要求两个 engine-observed
  model id 不同——本仓三签全绑同一 `deepseek-v4-pro`，永远达不到。degraded 路径
  （consultant vs implementer，两边都是机器观测身份，无需自证）**只在
  `review.decision == "N/A"` 时才populate `implementer_id`**
  （`gate/__init__.py:738-741`）。于是编排者一旦如实写下 `ACCEPT`，就只剩
  bootstrap 路径，其唯一信号是 `review.attestation`，而
  `ReviewerAttestation.is_valid()` 要求 `fresh_session is True` 且
  `adversarial_prompt is True`（严格 `is True`，字符串与 1 都不认）。
- 后果：**流程把「如实审核」惩罚成「过不了门」**。`fresh_session` 是关于「审核者是否
  在一个干净会话里、未参与规划」的事实断言。本轮我（编排者）撰写了 PLAN 与两个
  brief、派发并盯完执行，`fresh_session` 为假。要过门就得写 `true`，
  那是伪造审计记录以换取合并许可——正是 `min_independence` 想防的事。
  于是唯一诚实的出路是不合并。本轮两个 WP 已 ACCEPT 但卡在此处。
- 这不是「配置调松一点」能解决的：把 `min_independence` 降到 `none` 等于关掉双签。
- 修法（需要产品决策，建议交 Codex 复核）：
  1. 让 degraded 路径对 `review.decision == "ACCEPT"` 也可用——
     consultant 与 implementer 都是机器观测身份，比自证的 attestation **更强**，
     没有理由只在 `N/A` 时才用；这看起来就是个条件写窄了的缺陷。
  2. 或把 `fresh_session` 从 attestation 必填项里移除，改为记录性字段
     （如实写 false 也能过），只保留 `adversarial_prompt` 作为条件；
     并让门在 `fresh_session=false` 时把该事实写进 `consult.independence` 留痕。
  3. 或引入「审核者由独立会话签署」的真实机制（另起一个 claude 会话专做 review，
     其身份可被 engine 观测），从根上让 strong/weak 可挣得而非自证。
- 优先级：**最高**。它挡住的不是某个 WP，而是整条流水线的最后一步。


### A1. `agentic init` 生成的 gate 配置形式，`quality-gate.sh` 读不到

- 证据：`src/agentic_loop/init_cmd.py:57` 注释掉的示例是 `[[quality_gate.rule]]`；
  而 `quality-gate.sh` 与 `resolve_paths.py:254` 只认统一 `[[gate]]`
  （`kind="command"`, `stage="pre_review"`）。`docs/QUICKSTART.zh-CN.md:209` 确认
  `[[gate]]` 是正式形式。
- 后果：照 init 模板填规则 → `QUALITY_GATE_FAIL: [[gate]] (kind=command,
  stage=pre_review) is absent or defines no rules`，fail-closed 直接拒绝。
  新用户第一次跑门就撞墙，且错误信息不提示「你写的是旧形式」。
- 修法：init 模板改吐 `[[gate]]`；并在 `resolve_paths` 侧对残留
  `[[quality_gate.rule]]` 给一条明确的迁移提示而不是当作「没有规则」。

### A2. `STATUS.json.tmpl` 默认 `state="DRAFT"`，与「状态文件只提交两次」纪律冲突

- 证据：`src/agentic_loop/templates/STATUS.json.tmpl:7` 是 `DRAFT`；
  `preflight.sh:56-67` 的可执行状态集是 `APPROVED|DISPATCHED|IMPLEMENTING|CHANGES_REQUESTED`；
  且 preflight/quality-gate 读的是**副 worktree 已提交的副本**。
- 后果：按模板冻结 → preflight 报 `state DRAFT is not executable`；
  要修就得补一个 `DRAFT→APPROVED` 的提交，而那是第三次提交，
  `agentic plan lint` 立刻判 DIRTY（状态文件只允许 freeze + finalize 两次提交）。
  本轮实测被迫 `git commit --amend` 把冻结提交本身改成 `APPROVED` 才走通。
- 修法：模板默认值改 `APPROVED`（`validate_wp_status.py` 的
  `active_states = STATES - {"DRAFT","APPROVED"}` 已使 APPROVED 不要求
  base_commit/branch/worktree/executor，冻结形式天然合法）；
  或在 lint 侧显式放行一次 DRAFT→APPROVED 转换提交。二者择一，不能都不做。

### A3. `agentic init` 的默认配置自相矛盾：三签同模型 + `min_independence = "strong"`

- 证据：`init_cmd.py:38-53` 的默认 `[providers.deepseek]` 把
  `identity_model = "deepseek-v4-pro"` 作为「独立性评级唯一依据」，
  并让 `[roles]` 的 developer/reviewer/consultant 三签全绑该 provider；
  同一份模板第 65-66 行写 `[review_policy] min_independence = "strong"`。
  而 `independence.evaluate()` 的 strong 要求两个 engine-observed model id **不同**。
- 后果：`agentic init` 出来的默认配置，合并门**永久拒绝**——三签同 id 最高只能评到
  weak，而门限要 strong。与 A1 合起来，init 的默认配置在两个独立维度上都过不了自己的门。
- 本仓 `.agentic/config.toml:56-59` 已经手写了这条警告并把门限降到 `weak`，
  说明踩过；但 init 模板没跟上，下一个新项目照样撞。
- 修法：init 模板的 `min_independence` 默认值与默认 roles 绑定保持一致——
  三签同 provider 时默认吐 `weak` 并在注释里写明「若改成 strong，
  必须先把三签拆到不同 identity_model，否则门永久拒绝」。
  **不是**把警告写进注释就算了：默认值本身必须自洽。
- 归属：并入 WP-09（与 A1 同文件同区域）。

### A4. 冻结期填不了 `git.branch`/`worktree`，但 preflight 又要求它——冻结与派发的字段时序冲突

**现象**（本轮实跑，`a556c26`）：七个 WP 冻结时 `git.branch`/`git.worktree` 留空
（模板 `STATUS.json.tmpl` 默认即为空串），派发时 `agentic preflight` 直接拒绝：

```
PREFLIGHT_FAIL: current branch feature/wp08-independence-degraded != status branch
```

`preflight.sh:45` 拿活分支比 `git.branch`，空串永不相等，七个 WP 全部无法派发。

**为什么不能在派发时补**：三条路都堵着——

1. **另起一个提交补字段**：`_wp_commit_discipline`（`plan_cmd.py:355-367`）把
   非 freeze、非 `state=MERGED` 的提交一律归为 `sync`，于是 `plan lint` 对该 WP
   永久 DIRTY，`plan merge` fail-closed。正是 §4.3 要消灭的「review 同步 / codex 同步」污染。
2. **只改工作区不提交**：`quality-gate.sh` 的改动集含 `git diff`（未提交改动），
   status 文件不在 `allowed_paths` 里，于是实测报
   `QUALITY_GATE_FAIL: changed path outside allowed scope: ...WP-08.status.json`
   ——执行者必跑的门被自己的协调文件打挂。
3. **把 status 路径加进 `allowed_paths`**：等于把状态写入面交给执行者，
   违反全局规范 §4.1「仅编排者维护 status」与 §5.7 隔离。

**本轮的处置**：用户授权 `git commit --amend` 改写未推送的 `a556c26`
（→ `802b667`），把七个 WP 的 branch/worktree 补进**同一个** freeze 提交，
保持「每 WP 恰好一次 freeze」。事后 `plan lint` 对 WP-08..14 只剩
`finalize commit x0`，无 sync 提交。

**这是缺陷而非操作失误的理由**：冻结（`APPROVED`，scope 与验收标准定稿）
天然发生在开 worktree 之前，此时 branch/worktree **尚不存在**；
而 `validate_wp_status.py:462-464` 只在 `active_states`（不含 `APPROVED`）
才要求这三个字段非空——**校验器认为冻结期留空是合法的**，
`preflight.sh` 却要求它非空。两者对同一状态的要求不一致。

**候选修法**（择一，需评估）：

- `preflight.sh`：`git.branch` 为空时视为「尚未绑定」，
  用活分支回填并提示，而不是失败；绑定后再比对（要防止绑错分支）。
- 或：承认 `APPROVED -> DISPATCHED` 的状态跃迁本身就该带一次合法的状态写入，
  在 `_wp_commit_discipline` 里把「freeze 之后、`state=DISPATCHED` 的第一个提交」
  也算合法（freeze/dispatch/finalize 三次提交纪律），而非一律判 sync。
- 或：`agentic preflight` 增一个 `--bind-branch` 子动作，由编排者显式在
  freeze 提交里 amend/补齐，把本轮的人工操作变成有据可循的一等命令。

> 注意第二条会把「两次提交」纪律改成「三次」，是文档级契约变更，
> 需要用户裁定，不能由执行者顺手改。

### A7. 以另一个 WP 分支为基线时，本 WP 的 status 在副 worktree 索引里不可见，preflight 必挂

**现象**（2026-09-14 实跑 WP-17）：WP-17 经用户裁定以
`feature/wp08-independence-degraded` @ `a46578c` 为基线（WP-08 作上游依赖）。
worktree 建好、分支起点正确（已核实 `_should_populate_implementer` 在场），
但 `agentic preflight` 在副 worktree 里报：

```
PREFLIGHT_FAIL: status file must be tracked before implementation
```

**根因是提交拓扑，不是传参错误**。`preflight.sh:69` 是
`git ls-files --error-unmatch "$status_file"`，它按**当前 worktree 的索引**解析。
而各 status 文件首次出现的提交不同：

| 文件 | 所在提交 | `a46578c` 能否看到 |
|------|----------|--------------------|
| `WP-08.status.json` | `802b667`（七 WP 冻结） | **能**——`a46578c` 是 `802b667` 的子提交 |
| `WP-17.status.json` | `2dd9cfc`（WP-15/17 冻结） | **不能**——`2dd9cfc` 与 `a46578c` 是 `802b667` 的两个分叉 |

已用 `git cat-file -e` 逐一核实：
`feature/wp08-independence-degraded:…/WP-17.status.json` →
`fatal: path … exists on disk, but not in 'feature/wp08-independence-degraded'`；
同一路径在 `2dd9cfc` 下存在。

**为什么这是缺陷而非操作失误**：常规 WP 的基线就是 plan 分支，冻结提交天然是
基线的祖先，`ls-files` 永远能看到。但**一旦某 WP 以另一个未合并的 WP 分支为基线**
（A5 修法 2 这种自举场景的必然形态），冻结提交与基线就成了兄弟分叉，
`ls-files` 必然查不到。框架允许 `git.base_branch` 填任意分支
（`validate_wp_status.py:439` 只校验非空），却没有任何一处提示这会打挂 preflight。

**本轮的处置**：在副 worktree 里 `git merge --no-ff plan/2026-09-13-parallel-throughput`
把冻结提交并进 WP-17 分支。该提交只动 `docs/plans/`，不含代码，
故不污染 WP-17 的代码 diff，且副作用是好的——执行者在自己 worktree 里
就能读到自己的冻结 brief。

**候选修法**（择一）：

- `preflight.sh:69` 改成在**主仓**索引里查 status（用已有的 `main_root`，
  `resolve_paths --root main_repo` 那一行就在 `:77`），而不是当前 worktree。
  status 本就是主区 live 状态（全局规范 §4.1），在主仓查才是对的语义。
- 或：`dispatch-lint` 增一条检查——`git.base_branch` 不是 plan 分支时，
  校验冻结提交是否为 `base_commit` 的祖先，不是则明确报
  「以 WP 分支为基线须先把冻结提交并入该分支」，把这次的摸索变成一次性提示。
- 或：文档化「上游依赖型 WP 的派发前置步骤」，写进 `AGENTS.md` §4.2。

> 与 A4 同源但不是同一条：A4 是「冻结期填不了 branch/worktree」（字段时序），
> A7 是「派发期 status 在副 worktree 索引里不可见」（提交拓扑）。
> 两者都出现在冻结与派发的接缝处，修 A4 不会顺手修掉 A7。

### A8. WP-17 的隔离证据判据在框架自己的仓里无法自证——单一 git 身份 + A7 处置的 merge 双杀

> 发现于 WP-17 验收（编排者独立复核，非执行者报告）。**实现无缺陷**，
> 这是判据口径与本仓拓扑的交互后果，属设计层问题。

WP-17 交付了第三条 bootstrap 逃逸路径 `weak-isolated`：engine 用 git 核对四项
事实（作者不同于编排者、分支已隔离、树与基线不同、改动全在 scope 内），
四项全 True 才给 `weak`。拿**本 WP 自己**去验 A0，判据未放行：

```
implementer_id      = None        （A5 现场，正确 fail-close）
is_bootstrap_normal = True        （WP-08 的 degraded 路径进不去）
author_differs_from_orchestrator = False   ← 卡点 1
branch_is_isolated               = True
tree_differs_from_base           = True
scope_respected                  = False   ← 卡点 2
evaluate() -> none
```

**卡点 1：单一 git 身份。** kimi 提交署名取本机 `git config` 身份
`xizhu <8543264+billbraves@users.noreply.github.com>`，与 `base_commit` 的 committer 同为一人。
判据要「作者不同」，但本机上编排者与执行者共用同一 git 身份，
这项在任何单机 dogfood 场景里都恒为 False。

**卡点 2：A7 处置引入的区间污染。** 为解 A7，编排者把 7 个 `docs/plans/`
文件 merge 进了 WP-17 分支（见 A7）。`base_commit..tip` 区间因此含
不在 WP-17 `allowed_paths` 内的路径，采集函数**如实**报告超范围 → False。
采集正确，但「编排者为让 preflight 通过而做的 merge」与「判据要求区间内
路径全在 WP scope 内」两条纪律互相拆台。

**后果**：A0 依然没解开。三条逃逸路径在本仓的实际可达性：

| 路径 | 判据 | 本仓可达 | 阻因 |
|------|------|----------|------|
| WP-08 degraded | 实现者 model 由 engine 观测 | ❌ | A5：`developer` 未绑 provider，`implementer_id=None` |
| WP-07 attested | 审核者具名签署 | ⚠️ | 可达，但需人工签，非自动 |
| WP-17 isolated | git 四项事实 | ❌ | 本条 A8 两个卡点 |

**候选修法**（需用户裁定，另立 WP）：

- **修 A5 而非改判据**（最小、最正）：给 `developer` 角色补 provider 绑定，
  让 `implementer_id` 可观测，WP-08 的 degraded 路径自然放行；
  WP-17 判据保留作「无 developer 绑定时」的兜底，不为自证而放宽。
- **卡点 1 松绑口径**：把「作者不同于编排者」改为「作者身份可归因且已留痕」，
  即 author 非空且写进 reasons 即可，不要求与 baseline 不同。
  ⚠️ 这会削弱判据强度——同一人扮两角也能过，须评估是否等于放弃本判据的意义。
- **卡点 2 排除编排者提交**：scope 判定跳过 merge commit 引入的、
  仅含 `docs/plans/` 的改动（即「规划产物不计入 WP scope」）。
  须与 `quality-gate.sh` 的 `_path_in_scope` 保持口径单一权威（§5.3），
  不能只在 `collect_isolation_evidence` 里单独开洞。
- **接受现状**：承认框架无法在自己的仓里自证独立性，A0 在本仓永久走
  WP-07 的人工 attestation 路径，`weak-isolated` 只为下游真实项目服务。
  这是诚实的选项，但要在文档里写明，不能让人以为 A0 已解。

> 与 A5 同源：两条都是「判据设计得对，但本仓配置/拓扑让它落不了地」。
> 与 A7 耦合：A7 的处置动作直接造成本条的卡点 2，修 A7（在主仓索引里查
> status，不必 merge）会顺手消掉卡点 2。

### A9. degraded 路径异源比较返回 `strong`，而 bootstrap 语义只允许 `weak`

> Codex 独立审核 WP-08 时发现（2026-09-14），编排者核证为**预存缺陷**，非 WP-08 引入。

`independence.py:132-139`：`_different_model()` 为真时**无条件** `return "strong"`，
bootstrap 分支只往 reasons 追加一句 `level=strong-attested`，**级别本身仍是 strong**。

```python
if _different_model(consultant_id, compare_against):
    ...
    if bootstrap:
        reasons.append("level=strong-attested: reviewer=orchestrator, attested not engine-proven")
    return "strong", reasons          # <-- bootstrap 也走这里
```

`git log -L 128,140` 证明这段自 `c555daf`（框架 0.1.0 初始提交）就存在；
WP-08 **完全没碰** `independence.py`（只改 `gate/__init__.py` +44 与两个测试文件），
故非本 WP 回归。`[review_policy]` 注释也明确写着「strong 目前在 gate 路径上不可达」，
即设计意图是 bootstrap 下最高 weak —— 代码与意图不一致。

**当前不可达，修 A5 后立即可达**：本仓 `developer = "kimi"` 不绑 provider →
`binding=None` → `_resolve_implementer_identity()` 返回 `None` → 落回 bootstrap，
异源比较不发生。一旦按 A8 裁定给 developer 绑上异源 provider，
consultant(gpt-5.6-sol) vs implementer(kimi-*) 立刻命中此分支评出 `strong`。

> ⚠️ **修 A5 的前置条件**：必须先封 strong 上限（bootstrap 下 `_different_model`
> 命中时返回 `weak` 而非 `strong`），否则修 A5 会顺手把一个预存缺陷激活成
> 「合并门给出 strong」的实际误判。两者必须同一个 WP 或严格前后序。

### A10. 身份 `identity_model` 来自可编辑的 config 声明，不是执行时实测

> Codex 独立审核 WP-08 时发现（2026-09-14），编排者核证为**框架预存的身份模型问题**。

`gate/__init__.py` 的 `resolve_role_binding("developer"|"consultant")` 读
`.agentic/config.toml` 的 `providers.<name>.identity_model`。该值：

- 是人工书写的**声明**，不是 dispatch 时对实际模型的探测结果；
- dispatch 之后仍可被编辑，与产出 commit 无任何绑定；
- 没有任何 probe 去核验「实际应答的模型确实是这个 id」。

因此「双方身份均由 engine 观测」这一 degraded 路径的立论前提并不严格成立。
同一批评**同等适用于 consultant_identity**（走同一个 `resolve_role_binding`），
故这不是 WP-08 的新增问题 —— WP-08 只把准入条件从 `N/A` 放宽到 `N/A|ACCEPT`，
未改变身份来源的可靠性。但 A0 的解法依赖这条链，所以必须记账。

**候选修法**：dispatch 时探测实际模型并写入 status 的 engine-only 字段
（执行者不可写），评级时以探测值而非 config 声明为准；或至少在
`agentic --version` / gate 输出里标注「身份来自声明，未实测」，不让读者误以为已核。

### A11. `weak-isolated` 判据可被一条环境变量伪造 —— 比不加更糟

> Codex 独立审核 WP-17 时发现（2026-09-14），**编排者实证复现后撤回原 ACCEPT，
> 改判 REWORK**。这是本轮唯一一条「实现有实质缺陷」的记录，其余 A 类均为设计/配置问题。

WP-17 的 `author_differs_from_orchestrator` 用「tip 的 author 异于 base 的 committer」
代理「改动来自他方主体」。但 commit author 是**提交者可自由声明的字段**，
三条途径任选其一即可设定：`git config user.*`、`GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`
环境变量、`git commit --author`。

**决定性反证**（编排者自建临时 git 仓实测，非采信 Codex 论断）：

```
同一操作者、同一终端，仅加环境变量：
  GIT_AUTHOR_NAME=totally-other-agent GIT_AUTHOR_EMAIL=other@agent.ai git commit

采集结果：
  author_differs_from_orchestrator = True   ← 伪造成功
  branch_is_isolated               = True
  tree_differs_from_base           = True
  scope_respected                  = True
  evaluate() -> 'weak'   meets_threshold(weak,'weak') = True   ← 合并门被骗过
```

且 reasons 打出的是一句**假陈述**：

```
isolation evidence verified by engine via git: author=totally-other-agent ...
level=weak-isolated: change proven to originate elsewhere ...
```

改动并非来自他方，是同一主体换了个署名。判据把「可自我声明的字段」当成
「engine 核对的事实」，用于满足独立性门，等于把「隔离的改动」冒充
「独立的签署」—— **实质削弱既有 fail-closed 地板，比不加这条路径更糟**。

**旁证判据加固不足**：同一次提交的 committer 仍是 `orchestrator <orch@x.com>`，
真相就在 committer 字段里，但判据只读 author 没读 committer。
连「两个字段交叉核对」这种最低成本的加固都没做。

**编排者原验收失误的性质**（记录以免重犯）：我核了纯函数性、级别表不变、
strong 不可达、口径单一权威、`collect_isolation_evidence` 签名无自填字段、
七个反向场景 fail-closed、零回归 —— 全部成立且**仍然成立**。失误在于
把「函数签名里没有 executor/tool/model 参数」当成了「判据不可伪造」的充分证据，
漏了 **git author 本身就是一个可自填字段**这一层。诚实性检查做在了错误的层面：
查了「状态文件能不能自填」，没查「git 事实本身能不能自造」。

**返工方向**（Codex 建议，编排者认可）：移除 author 代理，改用实现者无法自行
声明的来源证明 —— engine 侧记录的执行会话身份、签名提交（受信密钥）等；
或大幅降低本判据的语义主张（不再声称 "proven to originate elsewhere"）
并交叉核对 committer，仅作为**辅助**信号而非独立性门的充分条件。

> 与 A8 的关系：A8 说「本判据在本仓拓扑下无法自证（恒不放行）」，
> A11 说「本判据在他处可被轻易伪造（该拦的不拦）」。**两条并存**：
> 判据同时过严（对诚实场景）和过松（对恶意场景），说明 author 这个代理量
> 选错了，不是阈值调整能解决的。

## B 类

### B1. `preflight.sh` 的 tracked 检查吞掉 stderr，把「路径不在本 worktree 内」误报成「未跟踪」

- 证据：`preflight.sh:69` `git ls-files --error-unmatch "$status_file" >/dev/null 2>&1`
  把 git 的真实错误一起丢进 `/dev/null`。传主区**绝对路径**时，git 实际报的是
  "outside repository"，wrapper 却输出
  `PREFLIGHT_FAIL: status file must be tracked before implementation`。
- 后果：本轮据此误判「文件没提交」，去查提交状态查了一轮，实际问题是路径形式。
- 修法：区分两种失败——先判路径是否落在当前 worktree 内，再判 tracked；
  或把 git 的 stderr 带进错误信息。

### B2. `agentic health` 的输出尾哈希信号，会被「缓冲式 subprocess 捕获」的派发形态整体致盲

- 证据：`kimi-health.sh` 的 freeze 判据是「输出尾内容哈希未变 **且** git dirty 未变」。
  本轮用 `KimiAdapter.implement()`（`subprocess.run(stdout=PIPE)`，全程缓冲）派发，
  `.out` 文件始终 0 字节，`tail_hash` 恒为空串哈希 `da39a3ee…`，
  两个信号里的一个从一开始就是死的；只剩 git dirty，而 kimi 写一个大文件期间
  dirty 本来就不变 → 连报 `FROZEN_3m` / `FROZEN_7m` 假警。
- 后果：假警会触发 §4.2 的仲裁流程，浪费编排者动作；更糟的是它训练人忽略告警。
- 修法：health 脚本在输出文件不存在或为空串哈希时，明确报
  `UNKNOWN_NO_OUTPUT` 而不是并入 frozen 判定（缺信号 ≠ 冻结）；
  并在 AGENTS.md §4.2 写明派发必须是 `| tee <log>` 的流式形态，
  buffered 捕获不满足 health 前置条件。

**2026-09-13 WP-08 派发期二次实测复现**（不再是推演，是完整跑了一遍的观测）：

- 派发 3 分钟后 monitor 报 `FROZEN_3m tail=""`——`tail` 就是空串，B2 描述的
  「一个信号从一开始就是死的」在实盘上原样出现。
- 同一时刻的独立核查：`.out` 文件 0 字节；health snapshot 里
  `tail_hash=da39a3ee5e6b4b0d3255bfef95601890afd80709`（空串的 SHA-1）；
  而 `ps` 显示派发 wrapper 与 `Kimi Code` 进程都活着，其子进程正在跑
  `python3.11 -m pytest tests -q`，worktree 里三个目标文件已就位
  （`gate/__init__.py` 已改，两个测试文件各 220 / 123 行）。
  **执行者完全健康，告警纯属虚报。**
- 附带确认了 §B2 修法里「空串哈希」这一判据的可用性：`tail_hash` 恒等于
  `da39a3ee…` 正是 `UNKNOWN_NO_OUTPUT` 该识别的特征值。
  （注意与 §B2 原记的 `d41d8cd9…` 区分：那个是 `tail_hash()` 在**文件缺失**
  分支返回的 MD5-of-empty，此处是文件存在但为空时 `shasum` 的 SHA-1。
  两个空态走两条不同的哈希算法，本身也是 B2 该一并收敛的口径不一致。）
- 编排者的临时对策（不属任何 WP，仅本轮操作）：monitor 改用
  「health 输出 + 派发进程是否存活」双判据，`FROZEN_*` 不再单独作为终止条件。
  这恰好印证 B2 的修法方向——**缺信号必须与冻结区分开**。

### B3. `AGENTIC_PYTHON` 覆盖会打穿测试自带的 `python3` stub，制造假失败

- 证据：`tests/test_gate_runner_shell.py` 与 `tests/test_init_githooks.py`
  会在 PATH 上装一个 stub `python3`；设 `AGENTIC_PYTHON=python3.11` 会绕过 stub。
  实测：带该环境变量跑这两个文件 1 failed，不带则 2 passed。
- 后果：本轮据此得出「门跑出 6 个失败，kimi 报 4 个」的差异，怀疑执行者漏报；
  实际是编排者的仪表把测试搞坏了。**kimi 报的 4 是对的。**
- 修法：文档明确 `AGENTIC_PYTHON` 只管 wrapper 自身调用，
  且跑全量测试时不得设置；或让这两个测试对 `AGENTIC_PYTHON` 免疫。

### B4. `| tee` 会吞掉派发的真实退出码

- 证据：本轮 WP-03 续跑 `kimi … | tee out2` 返回 exit 0，
  但 out2 内容是 `StepInterrupted()` + `Tool call arguments must be valid JSON.`
  ——kimi 在第 1 步就死了。exit 0 是 tee 的状态。
  `redispatch.sh:8` 有 `set -euo pipefail`，但编排者手写的派发命令没有。
- 后果：把「派发失败」读成「派发成功」，直接影响下一步判断。
- 修法：AGENTS.md §4.2 的派发范式里显式要求 `set -o pipefail`
  或检查 `${PIPESTATUS[0]}`。

### B5. `agentic quality-gate` 从主区跑会把编排者自己的改动算成 WP 越界

- 证据：`quality-gate.sh:41-46` 收集改动集的四条 git 命令都在**进程的当前工作目录**
  执行；脚本第 26 行确实调了 `resolve_paths --root current_worktree` 拿到 `repo_root`，
  但**该变量之后从未被使用**（全文只有赋值处与一句注释提到它），脚本也从不 `cd`，
  所以改动集完全由调用者的 cwd 决定。在主区对着某个 WP 的
  status 文件跑，会把编排者自己的 `.agentic/config.toml`、别的 WP 的 status、
  甚至 `uv.lock` 全部报成 `changed path outside allowed scope`。
- 后果：本轮实测得到 4 条假越界，看起来像 WP 违规，实则是「跑错目录」。
  这在并行场景下尤其危险：编排者本来就总有未提交的协调性改动。
- 修法：门在检测到「status 文件声明的 worktree ≠ 当前 worktree」时，
  直接 `QUALITY_GATE_FAIL: must run inside <declared worktree>` 拒绝，
  而不是照着错误的改动集算 scope。

### B6. kimi CLI 成功完成一轮后仍可能返回非零退出码，`dispatched` 判据不可信

- 证据：WP-03 的 rework 派发用了 `set -o pipefail` + `${PIPESTATUS[0]}`（已按 B4 修正），
  拿到 rc=1；但 stdout 里 kimi 明确输出 `[STATUS] DONE` + `[COMMIT] 78b33f2`，
  且 worktree 里该 commit 确实存在、工作区干净、改动完全正确。rc=1 是假失败。
- 后果：`KimiAdapter._run` 用 `dispatched = (returncode == 0)`
  （`adapters/kimi.py`），据此会把一次成功执行判成派发失败。
  与 B4 合起来看更糟：rc 既可能假 0（被 tee 吞）也可能假 1（kimi 自身），
  **两个方向都不可信**。
- 修法：不要把 kimi 的 rc 当作成功判据。判据应是「stdout 末尾有执行报告
  且 [STATUS] 为 DONE/DONE_WITH_CONCERNS」+「worktree 里 commit 确实存在」，
  由编排者独立核验。rc 只作为辅助信号记录，不用于分支决策。
  `ImplementResult.dispatched` 的语义应改为「进程已启动」而非「执行成功」。

### B7. dogfood 改的是 `src/`，但 `agentic` 跑的是 uv 装的另一个仓的快照——本仓的框架改动在门禁运行中完全不生效

- 触发：给 WP-15 跑 `dispatch-lint` 时，直接
  `bash src/agentic_loop/wrappers/dispatch_lint.sh` 报
  `ModuleNotFoundError: No module named 'agentic_loop'`（真实退出码 2，fail-closed 正确），
  只有 `PYTHONPATH=src` 或走 `agentic dispatch-lint` 才通。顺着查出下面整条链。
- 证据（三段，全部实测）：
  1. **wrapper 的 preamble 路径不存在**。11 个 wrapper 全都 export
     `PYTHONPATH="…:$main_root/packages/agentic-loop/src"`
     （`dispatch_lint.sh:21` 等），但本仓 `ls -d packages/agentic-loop/src` →
     No such file or directory。本仓源码在 `src/`。这句 export 从头到尾是空操作。
  2. **CLI 的 dogfood 通道在本仓落不到地**。`cli.py` 的 `resolve_wrapper()`
     优先取 `_main_root()/scripts/agentic/<name>`（注释写明 "live edits (dogfood) win"），
     否则退回 wheel 内置 `agentic_loop/wrappers/<name>`。本仓
     `ls -d scripts` → 不存在，wrapper 全在 `src/agentic_loop/wrappers/`。
     故 `agentic dispatch-lint` 实际跑的是 **wheel 内置副本**，不是工作树那份。
  3. **Python 模块也来自另一个仓的快照**。`agentic` 的 shebang 指向
     `~/.local/share/uv/tools/agentic-loop/bin/python`（3.12.7），
     其 `dist-info/direct_url.json` = `file:///Users/admin/vibe/agentic-loop-main-codex-merge`，
     **非 editable**（无 `.pth` 指向本仓）。装载源那个仓的 HEAD 是 `600c2f1`
     `✅ chore(plan): finalize Codex verdict recovery merge`（分支 `main`，已 merge WP-16）。
     `diff -rq -x __pycache__` 已装副本 vs 本仓 `src/agentic_loop`：唯一差异是
     `adapters/codex.py`——**已装副本比本仓工作树新**，含 WP-16 的有界恢复实现
     （`grep -c _NORMALIZATION_INPUT_MAX_BYTES`：已装 4，工作树 0）。
- 后果（这是本条的要害，不是"少配了个环境变量"）：
  - 本仓对 `src/agentic_loop/**` 的任何改动，**在 `agentic *` 的门禁运行里一律不生效**，
    要等 `agentic update` 重装才进副本。dogfood 的核心假设——"改框架、立刻用改后的框架验自己"
    ——在本仓不成立，且**没有任何一处提示**（不像 C3 至少两边都"对"，
    这里是跑了完全另一个仓的代码却显示 PASS）。
  - 反向也成立：我给 WP-15 拿到的 `DISPATCH_LINT_PASS`，是**另一个仓的
    `dispatch_lint.sh` + `validate_wp_status.py`** 判的。判据本身没差异（该文件两边一致），
    所以这次结论仍然有效；但这是运气，不是机制保证。
  - 版本号相同（两边都 `0.8.13`）无法暴露漂移：装载源与本仓同版本号但不同内容。
- 与已有条目的关系：不是 B3 的重复。B3 说 `AGENTIC_PYTHON` 覆盖会打穿测试的
  `python3` stub；本条说的是**模块本体来源错仓**，`AGENTIC_PYTHON`
  在这里恰好是让它能跑起来的那一半（`cli.py:213` 把 `sys.executable` 注入 wrapper env，
  见 `docs/KNOWN-ISSUE-bare-python3.md`）。
- 修法（三处，按优先级）：
  1. `resolve_wrapper()` 的 dogfood 分支要认本仓的实际布局：
     除 `scripts/agentic/<name>` 外，也探 `src/agentic_loop/wrappers/<name>`
     （或反过来，把本仓 wrapper 迁到 `scripts/agentic/` 以对齐 CLI 契约）。
     二者选一，但必须让"框架自己的仓"命中 main 分支而非 bundled。
  2. wrapper preamble 的 `packages/agentic-loop/src` 改成本仓真实源码根，
     并在解析失败时明确报"framework source root not found"，
     而不是靠 `python3 -m` 的 `ModuleNotFoundError` 间接暴露。
  3. dogfood 场景应 editable 安装（`uv tool install -e .` 或等价），
     否则 `agentic` 与工作树永久脱钩。至少要有一条 gate 或 `agentic --version`
     输出装载来源路径 + 是否 editable，让"我跑的是哪份代码"可见。
- 归 B 类而非 A 类：不阻塞任何单个 WP 的判定正确性（判据文件当前两边一致），
  但会让整轮 dogfood 的验证证据链失去意义，且随任一侧继续改动即刻恶化为假绿。

### B7 处置记录（2026-09-14，已修，含对原判断的两处纠正）

**修法**：`uv tool install --force --editable /Users/admin/vibe/agentic_loop`（用户执行）。

修后核验：

```
direct_url.json = {"url":"file:///Users/admin/vibe/agentic_loop","dir_info":{"editable":true}}
site-packages/agentic_loop/            -> 已不存在（独立快照副本消失）
site-packages/_editable_impl_*.pth     -> 指向本仓 src/
agentic_loop.__file__                  -> /Users/admin/vibe/agentic_loop/src/agentic_loop/__init__.py
```

行为一致性（证明修的是装载源，没顺手改门禁语义）：
`dispatch-lint WP-17` 仍 `DISPATCH_LINT_PASS`；`merge WP-01` 仍卡同一条
`consult.decision must be ACCEPT`；主区 `pytest` 4 failed + 492 passed
（plan 分支基线，不含 WP-17 代码，符合预期）。

**纠正 1：装载源不是「另一个仓」。** 原记录说 `agentic` 跑的是
`/Users/admin/vibe/agentic-loop-main-codex-merge` 这个「另一个仓」。实际三者
`git rev-parse --git-common-dir` 全部指向 `/Users/admin/vibe/agentic_loop/.git`
——它和 `agentic-loop-codex-verdict` 都是**本仓的副 worktree**，只是停在 `main`
分支（已并 WP-16，故 `adapters/codex.py` 比本迭代分支新）。性质是「跑了本仓另一
个分支的工作树」，不是跨仓。

**纠正 2：dogfood 通道不是「落不到地」，是从来没有过。** 原记录归因为
「本仓没有 `scripts/agentic/` 所以 dogfood 通道落不到地」，暗示别处有。实际
`cli.py:129` 的 `resolve_wrapper()` 找 `_main_root()/"scripts"/"agentic"/<name>`，
而**两个目录都没有** `scripts/`——wrappers 早已搬到 `src/agentic_loop/wrappers/`。
这条分支是**死代码**，任何布局下都不会命中。

**残留（低优先，可并入 A4/A7 那个 WP）**：`resolve_wrapper()` 的
main-repo 优先分支应当删除，或改为识别 `src/agentic_loop/wrappers/` 这一实际
布局。editable 装载已让整包指向本仓 src/，故此残留不再影响正确性，
但留着会继续误导下一个读 docstring 的人（docstring 明确承诺
「live edits (dogfood) win」，而实际不会）。

**对已出判定的影响**：无。修前已核实 `merge.sh`/`preflight.sh`/`quality-gate.sh`/
`dispatch_lint.sh` 与 `validate_wp_status.py`/`resolve_paths.py`/`independence.py`/
`cli.py` 两侧逐字节一致，故本迭代此前所有门禁结论仍然有效；修后复跑亦一致。

## C 类

### C1. scope 是前缀匹配，不是 glob——但 PLAN/brief 里用 glob 写法不会报错

- 证据：`gate/__init__.py` 的 `scope_prefix()` 只剥尾部 `/**` 与 `/*`；
  `scope_matches(path, prefix)` 是 `path == prefix or path.startswith(prefix + "/")`。
  故 `tests/test_gate_report` 永远匹配不上 `tests/test_gate_report.py`。
- 后果：本轮 PLAN §5 写的是 `tests/test_gate_report*.py`（glob 意图），
  编排者手抄进 status 时降级成 `tests/test_gate_report`，
  中间的 `*` 被静默吃掉，门到实现完成后才报
  `changed path outside allowed scope: tests/test_gate_report.py`，
  修它要 `--amend` 冻结提交并 rebase 两条 feature 分支。
  **同一个坑在 WP-03 上又踩了一次**：PLAN §5 写 `tests/test_plan*.py`，
  status 里降级成 `tests/test_plan`，同样匹配不到 `tests/test_plan_lanes.py`，
  同样要第二次 `--amend` + rebase 两条分支。一轮 dogfood 两个 WP 全中，
  说明这不是手误而是形式陷阱——PLAN 里的 glob 写法与 status 里的前缀语义
  长得一样但含义不同，人抄一遍就错。
- 修法：`validate_wp_status.py` 已对非尾缀 wildcard 有校验
  （见 `validate_wp_status.py:150` 附近），但对「写了 glob 却被剥成无效前缀」
  这种情况应直接 STATUS_INVALID，而不是接受一个匹配不到任何东西的前缀。
  另：`dispatch-lint` 应校验 status 的 allowed_paths 与 brief/PLAN 的 scope 表一致。

### C2. `evidence.tests` 的结构要求只在校验器里，模板与文档没写

- 证据：`validate_wp_status.py` 要求每条 `evidence.tests` 是 dict 且带 `exit_code`；
  本轮先写成字符串列表 → `STATUS_INVALID: each evidence.tests entry requires an exit_code`。
- 修法：`STATUS.json.tmpl` 给一条带 `name`/`command`/`exit_code`/`note` 的注释示例。

### C3. `agentic preflight` / `quality-gate` 读的是副 worktree 已提交副本，
但 review 阶段编排者写的是主区工作区——两者永久不一致，无机制提示

- 证据：本轮 preflight 对 WP-03 报 `state=DISPATCHED`，而主区工作区已是
  `CHANGES_REQUESTED`（编排者刚写的 REWORK）。两个都"对"，只是读的不是同一份。
- 后果：编排者容易误以为自己的状态写入生效了。C 类而非 B 类，因为这是设计使然
  （状态文件只提交两次，中间的变更本就只在主区工作区累积），
  但**没有任何一处提示读者「你看到的是冻结副本」**。
- 修法：preflight/quality-gate 的输出行显式标注读取来源，如
  `state=DISPATCHED (from committed copy at <branch>)`。纯输出层，零风险。

## 拆包结论（用户已裁定：立 WP-08，按建议拆）

用户 2026-09-13 决定：合并两个已 ACCEPT 的 WP、把编排者的 `.agentic/config.toml`
修复并入 WP-08、其余按编排者建议执行。合并已尝试并卡在 A0（见上），
故本节只落拆包。

| 新 WP | 内容 | lane | 依赖 | 理由 |
|-------|------|------|------|------|
| **WP-08** | A0 双签独立性死锁 | `lane-gate-fix` | 无 | 挡住整条流水线最后一步，优先级最高，且需产品决策 |
| **WP-09** | A1 gate 配置形式不一致 + A3 默认门限与默认 roles 自相矛盾 + 编排者已做的 `.agentic/config.toml` 迁移 | `lane-config` | 无 | 开箱即坏（两个独立维度）；把编排者的现存改动正式纳入一个 WP 的 scope |
| **WP-10** | A2 `STATUS.json.tmpl` 默认 DRAFT | `lane-template` | 无 | 开箱即坏，与 A1 独立，可并行 |
| **WP-11** | B1 + B4 错误信息与派发范式 | `lane-gate` | WP-02 之后 | 都碰 `wrappers/`，与 WP-02 同 lane 串行避免撞车 |
| **WP-12** | B2 + B6 health 致盲 + kimi rc 不可信 + B3 `AGENTIC_PYTHON` 打穿 stub | `lane-gate` | WP-11 之后 | 同碰 `wrappers/` 与测试，同 lane 串行 |
| **WP-13** | B5 quality-gate 跑错目录 + C3 读冻结副本不提示 | `lane-gate` | WP-12 之后 | 同上 |
| **WP-14** | C2 `evidence.tests` 模板补注释 | `lane-template` | WP-10 之后 | 与 A2 同碰 `templates/`，同 lane |
| **并入 WP-04** | C1 scope 前缀 vs glob | `lane-gate`（原） | WP-02 | 与「派发前 scope 交叉检查」天然同域，不单列 |

并行结构：`lane-gate-fix`（WP-08）、`lane-config`（WP-09）、`lane-template`
（WP-10 → WP-14）三条可同时开工；`lane-gate` 的 WP-11/12/13 排在既有
WP-02 → WP-04 之后。C1 并入 WP-04 的 scope。

**WP-08 优先单独开工**，因为在 A0 解掉之前，任何 WP 做完都同样卡在合并门前。

## 原始建议（保留）


A1 与 A2 是「新用户第一次用就撞」的开箱缺陷，建议优先，且彼此独立可并行。
B1/B4 是纯错误信息与范式文档，成本低。B2/B3 需要碰测试与 health 脚本，
建议与 WP-02（wrapper 输出层）同 lane 串行以免撞 `wrappers/`。
C1 与 WP-04（派发前 scope 交叉检查）天然同域，建议并入 WP-04 而不是单列。

### A5 `developer` 角色不绑 provider 会让 WP-08 的 A0 解锁静默失效

**发现时间**：2026-09-13 23:46（WP-08 已 ACCEPT 之后）
**触发**：`.agentic/config.toml` 于 23:37 被会话外手工改动（reviewer/consultant
重指向本机 kiro 网关），其中 `developer` 从
`{ adapter = "kimi", provider = "deepseek" }` 改为裸字符串 `"kimi"`。

**现象**：A0 完全复现，reasons 与原缺陷逐字相同：

```
level='none'  meets_threshold(none,'weak')=False
  - reviewer identity unavailable (orchestrator, attested not engine-proven)
  - no implementer fallback available
  - reviewer attestation missing
  - fail-closed: independence level none
```

**机理**：WP-08 的修复把 degraded 路径的准入条件放宽到 `ACCEPT` 之后，
`implementer_id` 由 `_resolve_implementer_identity(executor_tool, binding)` 解析，
而该函数在 `binding is None` 时返回 `None`（这是刻意的 fail-closed：
拿不到 engine 观测的 model 就不假装有身份）。于是：

- `implementer_id = None` → `is_bootstrap_normal = True`
- degraded 路径根本不进入，退回 bootstrap
- bootstrap 唯一信号是 `review.attestation`，而 `fresh_session` 为假

即回到「要过门就得伪造审计记录」的死锁。

**config 注释与实况不符**：该次改动在 `[roles]` 写下
「developer 不绑 provider…绑了也不影响评级——只有 `review.decision == "N/A"`
时才用 `executor.tool` 构造 `implementer_id`」。这句话在 WP-08 之前成立，
在 WP-08 之后不成立：`_should_populate_implementer` 已含 `ACCEPT`，
`developer` 的 provider 绑定自此成为 degraded 路径的**必要输入**。
注释是按旧语义写的。

**这不是 WP-08 的缺陷**：`a46578c` 的代码在有绑定时正确解锁 A0（已实测），
fail-closed 行为也正确。这是一处**配置—代码耦合未被文档化**的问题。

**候选修复（未指派，需用户裁决）**

1. `developer` 恢复 provider 绑定（任一有 `identity_model` 的 provider 即可，
   不必与 consultant 同源——degraded 只要求两边都被 engine 观测）。
   最小改动，但 `.agentic/config.toml` 是 WP-08 的 forbidden path，
   且改配置属用户决策，编排者不得自行改。
2. `gate` 在 `_should_populate_implementer(review_decision)` 为真却拿不到
   implementer 绑定时，输出一条明确诊断（如
   `developer role has no provider binding; degraded independence path unavailable`），
   而非现在这样并入通用的 `no implementer fallback available`。
   属新 WP，可与 A4 同批。
3. 在 `[roles]` 的注释里记录该耦合，防止下次再按旧语义解绑。

**另一处观察（非缺陷）**：新配置下 reviewer=`claude-opus-5` 与
consultant=`gpt-5.6-sol` 确为异源，但 `gate/__init__.py:795` 仍硬编码
`reviewer_id=None`，故 strong 在 gate 路径上依旧不可达。
该配置的 `[review_policy]` 注释已如实说明这一点，与代码一致。

#### A5 定性修正（2026-09-14，用户澄清后）

上文把 A5 记为「配置与代码耦合未文档化，补上 developer 的 provider 绑定即可」，
**该定性错误，作废**。用户澄清：kimi 实际跑在 codingplan 的 k3，只有 claude/codex
走 kiro 代理。因此 `developer = "kimi"` 不绑 provider 是**如实反映现状**，
不是疏漏。

编排者原建议「给 developer 绑 kirogpt」是错的，撤回。两处危害：

1. `identity_model` 会记成 `gpt-5.6-sol`——给 implementer 挂一个它没在使用的
   模型身份，**属伪造审计记录换合并许可**，与写 `fresh_session = true` 同类。
   WP-08 存在的意义正是禁止此类操作。
2. 并非只改 identity。`provider_binding.build_binding()` 对 `kimi`
   （属 `_ANTHROPIC_ADAPTERS`）强制要求 `anthropic_base_url`，且
   `adapters/kimi.py:58` 将其写入配置、`:95` 以 `--model <cli_selector>` 覆盖模型。
   即**不存在「只声明 identity_model 而不改路由」的写法**，绑定必然把 kimi 的
   实际流量改指到代理上，改变执行环境。

**A5 的真实性质**：不是配置错误，而是**判据设计与本仓实际拓扑不匹配**。
degraded 要求 implementer 身份 engine 可观测，而本仓 implementer 不经框架
provider 层，架构上就观测不到。三条路径因此全部落空：

| 路径 | 阻塞点 | 可达 |
|------|--------|------|
| strong | `gate/__init__.py:795` 硬编码 `reviewer_id=None` | 否 |
| degraded | k3 不经 provider 层，implementer 身份观测不到 | 否 |
| bootstrap | 唯一信号 `fresh_session` 本轮为假，如实写必不过 | 否 |

WP-08 的代码正确、配置也正确，A0 仍锁死。这比原记录的严重。

**修正后的候选修法（待用户裁决，编排者不自行选）**

1. **让 kimi 真实身份可观测**：`[providers]` 增一条如实描述 codingplan/k3 的条目
   （`identity_model` 填 k3 真实模型 id，`anthropic_base_url` 填其实际端点）。
   degraded 由此成立且无任何伪造。**前提：kimi 确有 anthropic 兼容端点**，未确认。
2. **扩judgment判据**：立新 WP，在 degraded 之外补一条「实现者身份不可观测」下的
   合法替代证据（如 commit 作者 + 隔离 worktree）。最重，但对得上本仓拓扑。
3. **本轮显式记账放行**：承认三路径在当前拓扑下均不可达，作为一次有完整记录的
   例外合并 WP-01/03/08，修判据留给后续 WP。需用户明确授权，理由须完整写入 status。

三条都不涉及放宽 `min_independence`（仍为 `weak`），也都不伪造任何字段。

#### A5 裁定（2026-09-14，用户选定修法 2）

**用户裁定：走修法 2**——立新 WP 扩展评级判据。修法 1 不再是首选。

裁定前的关键输入是 codex 对 WP-15 的独立审核
（`WP-15-consult-codex.md`，`[VERDICT] REWORK`），它推翻了修法 1 的前提。
修法 1 的三项阻断条件：

| 阻断条件 | 依据 | 严重性 |
|---------|------|--------|
| `identity_model` 直接来自可手改的 TOML，`build_binding()` 原样读、`identity()` 原样返回，注入探针只验 sentinel 不验模型——**任何人都能把真实路由指向模型 A 却声明模型 B，凭此伪造 degraded 独立性** | `provider_binding.py` `build_binding()`；`adapters/kimi.py:45-47` | P0 |
| `--config-file` **独立加载**，不与 `~/.kimi/config.toml` 合并；`_temp_config()` 只输出 provider/model，绑定即丢 `default_thinking`、模型 `capabilities`、`[loop_control]`、`[background]`、`[notifications]`、`[mcp.client]` 与 13 个 `[[hooks]]` | `adapters/kimi.py:49-64`；`~/.kimi/config.toml:2,50,79+` | P1 |
| 模板硬编码 `type = "anthropic"` 且要求 `anthropic_base_url`，但本机 K3 实为 `type = "kimi"` managed provider + OAuth（A5 原记录已自注「anthropic 兼容端点未确认」） | `adapters/kimi.py:56-63`；`~/.kimi/config.toml:70-75` | P1 |

其中 **P0 是方向性的**：修法 1 本质上是让合并门去读一个用户可手改的字符串，
与 WP-08 存在的理由（不许自证）属同一类问题，只换了个字段。
`identity_model` 的可信性没有任何代码防线——这是 codex 对
「有人能否借这条路填假 model 伪造 degraded」一问的直接回答。

**编排者已核实的事实**（不依赖 codex 报告，直读 `~/.kimi/config.toml`）：
`default_thinking = true`（`:2`）；`[models."kimi-code/k3"]` 的
`max_context_size = 1048576`（`:49`）与
`capabilities = ["thinking", "video_in", "image_in"]`（`:50`）；
K3 provider 是 `type = "kimi"`（`:70-71`）走 OAuth（`:75`）。
**未能独立验证**：「`--config-file` 不与全局配置合并」这一机制，
目前仅有 codex 的核实为依据（`kimi --version` / `--help` 当时被 auto mode
安全分类器拦下）。

**修法 2 的目标**：让 orchestrator-as-reviewer 的诚实 `ACCEPT`
有一条通路，既不靠自证 attestation（A0 的死结），也不靠可伪造的
`identity_model`（修法 1 的 P0）。

**已起草 `WP-17-brief.md`（草案，未冻结）**。核心设计判断：新判据的证据必须是
**engine 能用 `git` 自行核对的事实**（commit author 与编排者不同、branch 与
base_branch 不同、tree 与 base_commit 不同、改动全在 `allowed_paths` 内），
不能是任何来自 status 文件的自填字段——否则就是把 bootstrap 的自证换个字段名，
重犯修法 1 被否掉的同一错误。该判据只证明「改动由他方产生、经隔离、范围受限」，
**不证明模型差异，故只能评 `weak`，永不评 `strong`**。

**三个设计点用户已于 2026-09-14 裁定**：
(1) **复用 `weak`**，`INDEPENDENCE_LEVELS` / `_LEVEL_RANK` 一处不改，
靠 `reasons` 标 `level=weak-isolated` 区分来源（新增级别会让现有
`min_independence = "weak"` 拒绝更低的新级别，A0 依然锁死，还要连带改配置）；
(2) **要求** `capabilities.sandbox_enforced`，直接复用
`_weak_engine_enforced()` 的 `weak_ok`，不另写并行判断；
(3) **git 事实由 `gate/` 读好后以 `IsolationEvidence` 传入**，
`evaluate()` 内不得有任何 I/O，保住纯函数性质。

**另有一项起草时核实出的顺序约束**：主区 `gate/__init__.py` 不含
`_should_populate_implementer`（`grep -c` 为 0，该函数只在未合并的
`feature/wp08-independence-degraded` 上），而 WP-17 改的正是同两个文件。
更要紧的是 WP-08 的合并本身卡在 A0，而 WP-17 就是去解 A0 的——**存在自举问题**。
编排者倾向让 WP-17 基于 `feature/wp08-independence-degraded` 开分支
（把 WP-08 当上游依赖），而非动用一次例外合并先把 WP-08 落地。

修法 1 不作废、只是不作首选；其三项阻断条件记录在案，供日后重启该路线时参考。
WP-01/WP-03/WP-08 的合并在修法 2 落地前继续挂起。

### A6 `kimi.py` 把 `max_context_size` 硬编码为 DeepSeek 的 768K

**发现时间**：2026-09-14（为 A5 修法 1 评估代价时）

`adapters/kimi.py:63` 在临时配置模板里写死：

```python
f'max_context_size = 786432\n'
```

无参数、无配置项、不读 provider 配置。786432 = 768K 是当初为 DeepSeek 端点选的值
（同一函数 docstring `:51` 与注释 `:54` 至今仍写 DeepSeek）。

**后果**：kimi 的实际后端是 codingplan/k3，真实窗口 1048576（1M）。一旦
`developer` 绑上任何 provider，`kimi.py:107` 便以该临时配置启动 kimi，
768K 覆盖 1M —— **k3 静默损失约 25% 可用上下文，无任何告警**。

**绕不开**：绑定路径上 `:107`（派发）与 `:171`（注入探针）都只经
`_temp_config()`，不存在「绑定但不套用该模板」的路径。

**定性**：这是缺陷，不是绑定应付的代价。该值本应随 provider 配置走
（如 `[providers.X].max_context_size`，缺省时保留现值），却被钉死成某一个
provider 的数值。编排者先前把它表述为「需用户接受的风险」措辞不当，已更正。

**顺带**：同一模板不产出 `CLAUDE_CODE_EFFORT_LEVEL` 等字段，框架派发路径下丢失；
`_PROBE_PROMPT`/`_SENTINEL`（`:165-166`）也仍写 `DEEPSEEK_PROBE_OK`，
与实际 provider 无关，属同一处未随 provider 泛化的遗留。

**候选修法**：`max_context_size` 提为 provider 配置项，`build_binding()` 透传，
模板改为读 binding；未声明时回退 786432 以零回归。

**已立 WP-15**（`WP-15-brief.md`，rev2）。

**rev2 的两处修正**（依 codex 咨询 `WP-15-consult-codex.md`）：

1. **A6 与 A5 解耦**。上文「与 A5 修法 1 同批（A5 修法 1 落地前 A6 必须先修）」
   的因果**已作废**：修法 1 另有三项独立阻断条件（见 §A5 裁定节的表），
   修完 A6 一条也不解决；且用户已裁定 A5 走修法 2。WP-15 现为**独立修复**。
2. **回退值的落点**。原设想「`ProviderBinding.max_context_size = 786432`
   作 dataclass 默认值」被 codex 否掉：`max_context_size` 是 Kimi 的 model 属性
   而非 provider 身份属性，把 768K 放进默认值会让「provider 未声明」与
   「provider 声明了 768K」在 binding 上无法区分。改为
   `int | None = None` + renderer 侧命名常量 `_LEGACY_MAX_CONTEXT_SIZE`。
   模板那一行不能省略——Kimi 配置模型的 `LLMModel.max_context_size` 是必填项。

**A6 的定性经 codex 确认成立**：「硬编码 768K 应改为可配置，并保留旧配置的
兼容回退」。编排者先前把它表述为「需用户接受的风险」确属措辞不当。

### A12. `finalize_merge.sh` 读自己要写的字段，`set -e` 下首次 finalize 必然中止

> 编排者合并 WP-01/03/08 后调用 `agentic finalize` 时发现（2026-09-14），实证复现。

`finalize_merge.sh:67`：

```bash
merged_commit_recorded=$(field git.merged_commit)
```

`field()` 调 `validate_wp_status.py --field`，该实现遇到不存在的点分字段
打印 `STATUS_INVALID: unknown field <name>` 并 `return 2`。而
`git.merged_commit` **正是 finalize 自己要写入的字段** —— 首次 finalize 时它
必然不存在。脚本开头 `set -euo pipefail`，故此行直接中止，报出

```
STATUS_INVALID: unknown field git.merged_commit
```

**实证**（编排者直接复现，非推断）：三个 WP（WP-01/03/08）在
`state=APPROVED_FOR_MERGE`、schema 校验 `STATUS_VALID` 的前提下，
`agentic finalize` 均报此错；同一状态文件用
`--field consult.override.approved` 读取正常返回 `True`。

**根因是守卫不一致**：同一脚本第 72-75 行读 override 的四个可选字段时**都加了**
`2>/dev/null || true` 守卫：

```bash
override_approved=$(field consult.override.approved 2>/dev/null || true)
```

第 67 行读同样「可选、可能不存在」的 `git.merged_commit` 时**漏了**这个守卫。
第 161 行 `if [[ "$state" == "MERGED" && -n "$merged_commit_recorded" ]]` 的逻辑
本身就假定该值可以为空 —— 即脚本的意图是「读不到就当空」，实现却是「读不到就死」。

**影响**：`state=MERGED` 无法通过 `agentic finalize` 盖章，合并留痕链断在最后
一步。当前只能手写 status，绕过了 finalize 的幂等校验（唯一解析 merge commit、
校验 recorded 与 resolved 一致）。

**候选修法**（三选一，倾向 1）：

1. 给第 67 行补齐与 override 同样的守卫：
   `merged_commit_recorded=$(field git.merged_commit 2>/dev/null || true)`。
   最小改动，与同文件既有惯例一致。
2. 让 `validate_wp_status.py --field` 对缺失字段返回空串 + rc=0。改动面大，
   会影响所有 `field()` 调用点的语义，且会让真正的拼写错误静默。
3. 在 status 模板里预置 `git.merged_commit: ""`。治标，老状态文件仍中招。

> ⚠️ 修法 1 落在 `src/agentic_loop/wrappers/finalize_merge.sh`，与 A4/A7 的
> preflight 侧修法同属 wrappers 目录，可并入同一个 WP。

**修法 1 已验证成立**（编排者在沙箱副本上验证，未改动仓内 wrappers —— 那是
A4/A7 WP 的范围）：把 `finalize_merge.sh` 复制到 job tmp、只改第 67 行补上守卫，
对 WP-01/03/08 三个 `APPROVED_FOR_MERGE` 状态各跑一次，全部

```
FINALIZE_OK merged_commit=<hash>
```

且写入的 `merged_commit` 经编排者用 `git rev-list --merges --parents` 独立复核
逐个一致（WP-01 -> 6e67f0a、WP-03 -> 97141db、WP-08 -> ee74473，均为对应
`--no-ff` merge commit，唯一解析）。三个 WP 已借此进入 `state=MERGED`。

> 副本运行时报 `FINALIZE_WARN: WP lock release failed ... lock.sh: No such file`
> —— 脚本按自身目录定位兄弟 wrapper（`here="$(cd "$(dirname "$0")" && pwd)"`），
> 副本不在 wrappers 目录故找不到同级 `lock.sh`。这是设计的预期结果，不是缺陷；
> 锁已由编排者单独 `agentic lock release` 释放。

即：A12 的唯一障碍就是那一处缺失的守卫，一行改动即可修复，行为无其他变化。

### A13. worktree 拒收判据用路径字面量 `/.worktrees/`，本仓拓扑下完全不生效

> 编排者验收 WP-18 时核实执行者申报的防线而发现（2026-09-14）。

`gate/__init__.py:692` 与 `finalize_merge.sh:38` 用同一模式判断「status 文件是否
落在 worktree 内」：

```python
if "/.worktrees/" in str(status_file):
    raise GateError(f"status file resolves inside a worktree ({status_file}); ...")
```

判据是**路径字面量**，前提是所有 worktree 都建在 `<repo>/.worktrees/` 下。
但本仓 8 个已注册 worktree 无一命中：

```
/Users/admin/vibe/agentic_loop                   (主区)
/Users/admin/vibe/agentic-loop-codex-verdict     MISS
/Users/admin/vibe/agentic-loop-main-codex-merge  MISS
/Users/admin/vibe/wp01-gate-report               MISS
/Users/admin/vibe/wp03-plan-lanes                MISS
/Users/admin/vibe/wp08-independence-degraded     MISS
/Users/admin/vibe/wp17-isolation-evidence        MISS
/Users/admin/vibe/wp18-dispatch-proof            MISS
```

全局规范 §3.1 与本仓既有实践都是 `git worktree add ../wpN-<desc>`（同级目录），
**根本不会**产生 `.worktrees/` 路径段。故这条防线在本仓从未生效过。

**为什么仍不构成 WP-18 的阻塞**：真正的主防线是路径解析而非字面量匹配 ——
`resolve_paths --root main_repo` 在任何 worktree 内执行都返回主区根
`/Users/admin/vibe/agentic_loop`（编排者在 wp18 worktree 内实测确认），
相对路径 status 一律落到主区副本；叠加 §4.1 禁执行者写主区 + WP 锁。
`/.worktrees/` 那条只是对**绝对路径**入参的补充兜底。

**候选修法**：改用 git 事实而非路径字面量 —— 比较
`git rev-parse --git-dir` 与 `--git-common-dir`，两者不同即在 worktree 内；
或直接比较 status 文件所在仓根与 `resolve_paths --root main_repo` 的结果。

### A14. `executor.dispatch_proof` 不受 schema 保护（WP-18 已知缺口，执行者主动申报）

> WP-18 brief 陷阱 2 预先声明，执行者在 `[CONCERNS] 2` 如实申报，
> 编排者实证确认（2026-09-14）。

`validate_wp_status.py:377-383` 的未知字段检查**只在顶层**
（`allowed = required | OPTIONAL_TOP_LEVEL`），不递归进 `executor` 块。
故 `executor.dispatch_proof` 目前既不被 schema 要求、也不被 schema 禁止。

**实证**：编排者构造类型完全合法的伪造块
（`dispatched_by_engine: true`、`child_pid: 99999`、`exit_code: 0`、
`argv_hash` 64 位十六进制、`orchestrator_session: "forged-session"`）
写入 status 副本，`collect_dispatch_proof` 全字段采集成功，
`evaluate()` 返回 `weak` —— 门被骗过。

**为什么仍 ACCEPT WP-18**：

1. 这是 brief 冻结时就明示的边界，`validate_wp_status.py` 是 WP-18 的
   forbidden path，加严必然另立 WP —— 执行者遵守了范围而非擅自扩权。
2. 任何**不完美**的伪造都被逐字段 fail-closed 归一到 `none`（编排者实测
   七种畸形块全部落 none，含 bool 冒充 int pid 这种最易漏的情形）。
3. 前置防线仍在：status 单一来源在主区（A13 已核实主防线是路径解析）、
   §4.1 禁执行者写主区、WP 锁。伪造需要先突破「执行者不得写主区」这条
   独立约束。
4. 与 A11 的性质截然不同：A11 是**判据本身**把可自我声明的字段当 engine 事实，
   一条环境变量即可、不需违反任何其他约束；A14 是判据正确但**存储层**缺
   schema 强制，需先违规写主区。前者是设计错误，后者是纵深防御的一层缺口。

**候选修法**：在 `validate_wp_status.py` 中把 `executor` 块的字段纳入白名单
校验，并把 `dispatch_proof` 标记为 engine-only —— 校验时比对其
`orchestrator_session` 是否等于当前锁 owner，不等则视为伪造落 fail-closed。
与 A9 的 strong 上限同属 `independence`/`validate` 加严面，可评估并入同一 WP。

### A15. schema 无顶层 `blocker` 字段，`BLOCKED` 状态无处记录阻塞原因

> 编排者废弃 WP-17 时发现（2026-09-14），实证复现。

`validate_wp_status.py` 的 `STATES` 含 `BLOCKED`，全局规范 §4 的状态流转图
把 `BLOCKED` 列为四个状态之一、§6.C 的执行报告模板有 `[BLOCKER]` 字段，
但 `REQUIRED_TOP_LEVEL_V1/V2/V3` 与 `OPTIONAL_TOP_LEVEL`
（`{"qoder_security", "plan_id"}`）**都没有 `blocker`**。

**实证**：给 WP-17 写入顶层 `blocker` 字段后校验直接失败：

```
STATUS_INVALID: unknown top-level fields: blocker
```

即：状态机允许进入 `BLOCKED`，但 schema 不允许记录**为什么**被阻塞。规范
（§4.1 状态文件结构示例中确有 `concerns`/`blocker`）与实现不一致。

**当前绕法**：把废弃说明并入 `review.evidence`，保留原审核记录在后。可行但
语义错位 —— 阻塞原因不是审核证据，且这样写会让 `review.decision=REWORK` 与
一段「已废弃、不返工」的说明混在同一字段里，机器无法区分。

**候选修法**：把 `blocker` 与 `concerns` 加入 `OPTIONAL_TOP_LEVEL`
（与 §4.1 的结构示例对齐），并在 `state == "BLOCKED"` 时要求 `blocker` 非空
（fail-closed：进 BLOCKED 必须说明原因）。改动落在
`src/agentic_loop/validate_wp_status.py` —— 与 A14 的 `executor` 块字段校验、
A9 的 strong 上限同属 validate/independence 加严面，可评估并入同一 WP。

### A16. `DispatchProof` 的放行字段可由执行者子进程自造真值——engine 观测 ≠ 执行者不可及

> Codex 独立审核 WP-18 时指出（2026-09-14，finding 2，confidence 10/10），
> 编排者实证复现后确认成立。**这是 A11 的同构缺陷，同一层错误第二次出现。**

WP-18 用 engine 在 fork 时观测的事实替换 WP-17 可伪造的 git author，五项放行条件是
`dispatched_by_engine` / `child_pid` / `exit_code` / `argv_hash` / `orchestrator_session`
（`independence.py` 的 `weak-dispatched` 判据要求五项同时成立）。声称的安全性质是
**执行者不可读、不可写、不可预测**。

**实证推翻**（编排者自建真实 argv-bearing 子进程，非推断）：

| 字段 | 执行者能否自造真值 | 途径 |
|------|------------------|------|
| `child_pid` | **能** | `os.getpid()`，与 engine 观测的 `proc.pid` 逐位相同 |
| `argv_hash` | **能** | 算法公开（`kimi.py:_argv_hash` 就是 sha256 逐元素 + `\x00`），子进程从自身 `sys.argv` 精确重算，哈希字符串完全一致 |
| `orchestrator_session` | **能** | `kimi.py:140` 的 `subprocess.Popen(cmd, stdout=…, stderr=…, text=True)` **未传 `env=`**，`AGENTIC_SESSION_ID` 完整继承给子进程 |
| `exit_code` | **能** | 子进程自选退出码 |
| `dispatched_by_engine` | **能** | 常量 `True`，无信息量 |

即：五项全部可由执行者自行取得**真值**，不需要猜测、不需要类型伪造。
`collect_dispatch_proof` 只做逐字段类型校验（bool 不冒充 int 那类），
没有写入者验证、没有签名，故任何完整且类型正确的 `executor.dispatch_proof`
都会被构造成可信 `DispatchProof` 并放行 `weak`。

**与 A14 的关系**：A14 说的是「`executor` 块不受 schema 保护，但不完美的伪造会
fail-closed 归一到 `none`」。A16 说明**完美伪造无需任何猜测即可构造**，
于是 A14 那条「伪造需要突破执行者不得写主区这条独立约束」的兜底论证，
就是本判据**唯一**剩下的防线 —— 而那是外部流程约束，不是判据自身的性质。

**与 A11 的同构关系**（最该记住的一条）：

| | A11（WP-17） | A16（WP-18） |
|---|---|---|
| 判据读什么 | git commit `author` | engine fork 时的观测值 |
| 声称的性质 | engine 可核对的身份事实 | 执行者不可读写不可预测 |
| 实际为何不成立 | author 是提交者可自由声明的字段 | 观测值可被被观测方自我重现 |
| 伪造成本 | 一条环境变量 | 零（子进程本来就知道这些） |

两次的编排者失误性质完全相同：查了「状态文件的字段能不能被 schema 拦住」，
没查「字段所声称的事实本身能不能被执行者取得」。**诚实性检查做在了错误的层面。**
A11 时的教训写作「查了状态文件能不能自填，没查 git 事实能不能自造」，
A16 时应写作「查了判据不读 git，没查判据读的东西能不能被自我重现」。

**候选修法方向**（须先由用户裁定是否值得继续这条路）：

1. **认证密封（seal）**：engine 用执行者环境中**不存在**的密钥对 proof 做 HMAC/签名，
   gate 侧验签。关键是密钥材料必须不继承给子进程（`Popen(env=…)` 显式白名单，
   而非当前的完整继承），且 proof 须绑定具体 WP id + 派发命令 + 会话，防重放。
2. **engine-only 侧信道**：proof 根本不经过 `status.json`，由 engine 直接写入
   执行者无写入权的位置（如锁目录下的派发记录），gate 侧对照。
3. **承认这条路不通**，把独立性证明整体移到 A5（给 developer 角色绑异构 provider），
   即 proof 类判据一律降为辅助信号、不作为独立性评级的充分条件。

> ⚠️ 无论选哪条，**修法 1 的 `env=` 白名单是最低前提** —— 当前
> `kimi.py:_run` 的完整环境继承会让任何基于「engine 环境秘密」的方案当场失效。

> A16 与 A14（`executor` 块无 schema 保护）、A9（bootstrap 未封 strong 上限）
> 同属独立性判据面，且 A16 的修法 3 直接指向 A5。四者的先后顺序须一并裁定。

### A17. `CodexAdapter._parse_verdict` 只认纯 JSON，模型带前缀输出即整条裁决丢失

> 编排者复审 WP-18 时实证（2026-09-14）。**裁决内容本身完好，是解析层把它判死。**

`codex.py:212-234` 的 `_parse_verdict` 先 `json.loads(raw)`，失败则退回
`re.search(r"\{.*\}", raw, re.DOTALL)` 抓第一个花括号块。两条都不中就抛
`ValueError: Could not parse structured verdict from codex output: <raw>`。

**实证**：Codex（gpt-5.6-sol）对 WP-18 返回的是

```
VERDICT: REWORK

1. [阻断，confidence 10/10] `DispatchProof` 仍可通过 `status.json` 伪造……
```

—— 一份**结构清晰、内容完整、判定明确**的中文裁决，含 4 条 finding 与修复要求。
但因为它以 `VERDICT: REWORK` 开头而非 `{`，且正文的反引号代码块里没有成对花括号，
两条解析路径全部落空，整条裁决以 `ValueError` 抛出。

**为什么这是缺陷而非模型不听话**：`review()` 已经传了 `--output-schema`
（`codex.py:132`），即已用 CLI 层的结构化输出约束。模型仍以自然语言前缀回答，
说明该约束在当前 provider/wire_api 组合下**不是强保证**。而解析层的设计假定它是
强保证 —— 于是唯一的失败模式是「丢掉整条裁决」，最坏的一种：
编排者若不看 `ValueError` 里的 `raw`，会以为顾问审核失败、可能重跑或干脆跳过，
**而实际上顾问已经给出了阻断级发现**。

本轮就差点如此：`raw` 恰好被完整打进异常消息才保住这份裁决。

**候选修法**（倾向 1+2 并做）：

1. `_parse_verdict` 增第三条路径：从纯文本里提 `VERDICT|DECISION:\s*(ACCEPT|REWORK|CONSULT)`，
   命中即构造 `Verdict(decision=…, rationale=<全文>)`，findings 留空并在 rationale
   里保全原文。fail-open 到「拿到裁决但结构降级」，而不是 fail-closed 到「什么都没有」。
2. 解析失败时**先把 `raw` 落盘**到迭代目录（如 `WP-N.consult-raw.txt`）再抛异常，
   保证裁决不因异常处理丢失。
3. 评估 `wire_api=responses` + `--output-schema` 在本 provider 下是否真能强制 JSON；
   若不能，文档化「结构化输出为尽力而为」，别让下游按强保证写代码。

> 修法 1 须注意：不能因为「文本里出现 ACCEPT」就放行 —— 只认行首锚定的
> `VERDICT:`/`DECISION:` 标签，且全文出现多个不同判定时 fail-closed 取最严
> （REWORK > CONSULT > ACCEPT），防止把 rationale 里引用的词误当裁决。

> **A9 顺序风险已实证**（编排者，2026-09-14，纯内存构造未改 config）：
> `developer` 无 binding 时 `evaluate()` 返 `none`（A0 现场）；一旦 binding
> 带上 `identity_model`，同一调用直接返 `strong` 且 `meets_threshold(strong,"strong")=True`。
> 即 **A5 一解开，A9 立刻由理论缺陷变成每次 gate 都走的实际路径**。
> 故 A9 的 strong 上限必须先落地（WP-20 第一步），否则中间态是
> 「双签门放行、但放行依据是语义上不成立的 strong」—— 比 A0 锁死更坏。

### A18. schema 无顶层 `brief` 字段，全局规范要求的 `brief.sha256` 冻结锚定无处落地

> 编排者创建 WP-19 状态文件时发现（2026-09-14），实证复现。

全局规范 §4.1 的状态文件结构示例明确含：

```json
"brief": { "path": "docs/wp/WP-N.brief.md", "sha256": "" }
```

并在紧随其后的说明里写明用途 ——「`brief.sha256` 锚定冻结版 Brief，
执行报告据此证明『执行的确是冻结版』」。§6.C 的执行报告模板也依赖这条。

**实证**：按规范写入顶层 `brief` 字段后校验直接失败：

```
STATUS_INVALID: unknown top-level fields: brief
```

`REQUIRED_TOP_LEVEL_V1/V2/V3` 与 `OPTIONAL_TOP_LEVEL`（`{"qoder_security", "plan_id"}`）
均无 `brief`。核查本迭代既有 WP（WP-01/08/18）顶层键，**全部没有** `brief`，
`docs/agentic/templates/STATUS.json` 模板同样没有 —— 即这条审计链从未落地过。

**影响**：冻结版 Brief 与实际执行之间没有任何机器可核对的锚点。当前只能靠
「brief 文件已提交、执行期不改」这条流程约定，而 §4.1 允许 re-freeze 走 rev2，
一旦发生就无法从 status 判断执行者当时读的是哪一版。这与 A15（`BLOCKED` 无处
记录 `blocker`）同型：**规范定义了字段，实现不接受该字段**。

**候选修法**：把 `brief` 加入 `OPTIONAL_TOP_LEVEL`，并校验其内部结构
（`path` 非空字符串 + `sha256` 为 64 位十六进制或空串）；模板
`docs/agentic/templates/STATUS.json` 同步补上该字段。进一步可在 `preflight`
里比对 `brief.sha256` 与实际文件摘要，不符即拒绝派发（fail-closed），
把「执行的确是冻结版」从口头约定变成门禁。

> A18 与 A15（`blocker`）、A14（`executor` 块字段无白名单）同属
> `validate_wp_status.py` 的 schema 面。三者可并入同一个 WP。
> 注意本轮 WP-19/WP-20 均把该文件列为 forbidden_paths，故这三条须另立 WP。

### A19. 框架只有返工用的 `redispatch`，没有首次派发命令——`DispatchProof` 在首次派发时无从产生

> 编排者派发 WP-19 时发现（2026-09-14）。**这是 A16 的下游后果，也解释了
> WP-18 自举失败的第二层原因。**

`agentic` 的子命令表里派发相关只有 `redispatch`（`-> scripts/agentic/redispatch.sh`），
而 `redispatch.py:206` 的分支表明它只处理 `BLOCKED` 与 `REWORK` 两种状态
（prompt 里写死 "Reason for redispatch"、"Recent log tail"、`diff --stat` 等
返工上下文）。**`DISPATCHED` 状态的首次派发没有任何 engine 侧命令**。

于是首次派发只能由编排者手工调用开发者工具（本仓即 `kimi --afk ...`）。
后果是 `executor.dispatch_proof` 在首次派发时**必然缺失** —— 不是执行者不写，
而是没有任何 engine 代码路径会写它：写入点 `redispatch.py:_proof_payload`
只在 redispatch 流程里。

**这解释了 WP-18 为何无法自证**（此前只归因于「WP-18 未合并所以主仓 gate 没有
`collect_dispatch_proof`」，那只是第一层）：即便 WP-18 已合并，首次派发依然
产不出 proof，`weak-dispatched` 判据只有在**返工**派发时才可能生效。
一个只在返工路径上成立的独立性判据，无法用于首次验收 —— 而首次验收正是
双签门最需要独立性的时刻。

**与 A16 的关系**：A16 说 proof 的内容可被执行者自我重现（判据不可靠）；
A19 说 proof 在首次派发时压根不存在（判据不可用）。两条叠加，
`weak-dispatched` 在正常首次验收流程中**既不可靠也不可用** ——
这为用户 2026-09-14 对 A16 的裁定（修法 3：放弃 proof 路线，
独立性证明整体移交 A5）补充了一条独立理由。

**候选修法**（与 A16 修法 3 并行，互不冲突）：

1. 增 `agentic dispatch <status.json>` 子命令：engine 侧读 status、
   构造开发者工具 argv、fork 并记录执行结果，把当前手工调 kimi 的步骤
   变成一等命令。这同时使「记录 `executor.tool` 与 session id」
   （CLAUDE.md §Dispatch 的要求）从人工誊抄变成 engine 事实。
2. 或把 `redispatch` 的状态前置放宽到含 `DISPATCHED`，prompt 按状态分支
   （首次派发用 brief 全文，返工用 diff + 日志尾）。改动更小但语义混淆，
   命令名会与行为不符。

> ⚠️ 修法 1/2 都**不**能解决 A16（proof 内容可自我重现），只解决可用性。
> 若按 A16 修法 3 放弃 proof 路线，A19 依然值得修 —— 因为
> 「engine 观测到的 `executor.tool` 与 session」对审计留痕仍有价值，
> 只是不再作为独立性评级依据。

### A22. A13 的 worktree 判据可被 `GIT_DIR` 环境变量绕过

> codex 独立审 WP-19 时判 REWORK 而发现（2026-09-15）；编排者在 consult 窗口内
> 独立复现同一结论，两条证据链互不依赖。

WP-19 的 A13 把 worktree 判据从路径字面量换成 git 事实：比较路径所在仓的
`--absolute-git-dir` 与 `--git-common-dir`，不同即在 linked worktree。
但 `gate/__init__.py:183` 的 `subprocess.run(...)` **继承调用者环境**，
未清除 git 的仓库选择变量：

```
worktree 路径，干净环境                             -> True   （正确拒收）
worktree 路径，GIT_DIR=<主仓>/.git                  -> False  ← 绕过成功
worktree 路径，GIT_WORK_TREE=<主仓>                 -> True   （不绕过）
worktree 路径，GIT_COMMON_DIR=<主仓>/.git           -> True   （不绕过）
```

`GIT_DIR` 单独一个变量即可翻转判据。两处调用方都中招（这是口径单一的必然
结果，不是各自的实现缺陷）：

```
finalize_merge.sh   干净 -> FINALIZE_FAIL: resolves inside a worktree
finalize_merge.sh   GIT_DIR 伪造 -> 越过守卫，死在后面无关的 schema 检查
codex_merge_gate.sh 干净 -> GATE_FAIL: resolves inside a worktree
codex_merge_gate.sh GIT_DIR 伪造 -> 同样越过
```

`cli.py:212` 用 `dict(os.environ)` 原样传给 wrapper，且无任何 wrapper unset
这些变量，所以从 CLI 入口即可复现：

```bash
GIT_DIR=/main/.git agentic gate /linked-worktree/WP.status.json
```

**主防线未被打穿**：`resolve_paths --root main_repo` 在 `GIT_DIR`、
`GIT_WORK_TREE`、`GIT_COMMON_DIR` 三种伪造下均返回主区根，相对路径 status
仍一律落主区副本。

**定级分歧的处置（重要留痕）**：编排者据「主防线未破 + 严格强于基线
（基线字面量在本仓 8 个 worktree 全 MISS，无需任何环境变量即失效）+ Brief
明确把本条定义为绝对路径入参的兜底」判为**登记级**；codex 判**阻断**。
编排者**服从 consult 结论**，不行使覆盖：一个单个环境变量即可关掉的安全守卫
不应以「看起来正确」的姿态合并，而 WP-17 的教训恰恰是**编排者对可伪造判据的
严重性判断本身**是失效环节。分歧记录在 `WP-19.status.json`
`consult.orchestrator_disagreement_on_severity`，不删改。

**修法**：在谓词内部净化环境 —— 给 `subprocess.run` 传剔除了 `GIT_DIR` /
`GIT_WORK_TREE` / `GIT_COMMON_DIR`（连带 `GIT_INDEX_FILE` /
`GIT_OBJECT_DIRECTORY`）的 env，使判据读**文件系统拓扑**而非调用方声明的
仓库选择。保持单一权威谓词，两处调用方自动继承修复。

### A23 —— 派发无「执行者真的开工了」验收位，静默空转 6 分钟

**等级**：流程级（编排面），非代码缺陷
**发现**：2026-09-15，WP-19 rev2 派发（编排者自证）

**实证**：rev2 首次派发用 `kimi --afk < prompt.txt`。`--afk` 单独使用会拉起
交互 TUI，**不消费 stdin**；prompt 落进输入框但从未提交。表现为：

```
kimi 进程存活、%cpu 非零、日志有内容（欢迎横幅）
health 判 PROGRESS baseline -> PROGRESS -> FROZEN_3m
worktree 干净，HEAD 未动，零改动
```

`agentic health` 的 `PROGRESS` 只测「日志尾部哈希是否变化」与「工作树是否脏」，
TUI 的 spinner 动画足以让尾部持续变化，于是启动即空转被判成正常进展，
直到 spinner 停下才转 FROZEN。**6 分钟浪费，且 FROZEN 的成因被误导为「执行者卡住」，
而真实成因是「执行者从未收到任务」。**

第二次派发改 `--afk --print -w -p` 后，kimi 3 秒退出 exit=1：
自动加载的 `mcp-server-starrocks`（属另一项目）返回 503，启动即中止。
这次 health 会正确报 FROZEN，但同样无法区分「没开工」与「开工后卡住」。

**要点**：两次失败形态不同（一次假活、一次早退），但暴露同一个缺口 ——
**派发后缺一个「执行者已接收并开始执行」的正向确认**。现有 health 契约
（`PROGRESS`/`FROZEN_<N>m`/`DONE`）三个取值都不区分「未开工」。

**候选修法**：
1. 派发命令形态收进代码（`agentic dispatch` 或 wrapper），不由编排者每次手写。
   rev1 日志头 `(retry: --afk --print -w -p)` 已记录过正确形态，靠人记会再犯。
2. health 增第四个取值 `NOT_STARTED`：日志中无执行者的首个工具调用/首行实质输出，
   且 worktree 无改动，超过 N 分钟即报。与 FROZEN 区分开。
3. 派发时用空 MCP 配置（`--mcp-config-file <empty>`)，把无关项目的 MCP 依赖
   从执行者启动路径上摘掉。本仓 WP 不需要任何 MCP server。

**与 A19 的关系**：A19 是「无首次派发命令，DispatchProof 首派无从产生」。
A23 是同一个空缺的另一面：没有命令，就既没有证据，也没有形态保证。
两条应由同一个 WP 一并解决。

### A24 —— 冻结 Brief 落在编排分支，执行者在 feature worktree 里读不到

**等级**：流程级（编排面）阻断，非代码缺陷
**发现**：2026-09-15，WP-19 rev2 执行者 `[CONCERNS]` 主动申报，编排者复核成立

**实证**：

```
主区 plan/2026-09-13-parallel-throughput：
  docs/.../WP-19-brief-rev2.md          存在（317594b 冻结）
  docs/.../WP-08-candidate.md §A22      存在（9de1885 登记）

worktree feature/wp19-wrapper-seams：
  docs/.../WP-19-brief-rev2.md          不存在
  grep -c A22 WP-08-candidate.md        0（该分支的文档只到 A19）
```

编排者把 Brief 冻结提交到 plan 分支，却把执行者派到 feature worktree，
两者不含同一份文档。执行者按提示里的摘要执行，**从未读到冻结权威**。

**后果（本次实测）**：rev2 Brief 要求剔除 7 个 git 变量并提成模块级常量
`_GIT_SELECTION_VARS`，派发提示只摘了 3 个。执行者严格按提示做，交付
3 个变量、无常量、缺「三变量同时设置」用例。核心缺陷 A22 已闭合（编排者
独立探针证实 10 个向量全 True），但**冻结要求有三条未实现，成因是派发缺陷**。

执行者自己发现了这个矛盾并在 `[CONCERNS]` 里写明「请编排者补落 rev2 Brief，
若其口径与提示有出入，以 Brief 为准裁定本提交」—— 判断正确，处置正确。

**要点**：这不是执行者失职。全局规范 §4.1 说 Brief 是「冻结输入、可审计、
执行期只读」，隐含前提是**执行者能读到**。规范没写「冻结提交必须对执行者
可达」，于是这个前提可以静默不成立，而且**不成立时没有任何门禁报警**：
`dispatch-lint` 校验 Brief 存在于主区，不校验它在执行者的工作树里可见。

**与 A19/A23 的关系**：三条同源于「首次派发没有代码化的命令」。
A19 缺证据，A23 缺「已开工」确认，A24 缺「冻结输入可达」前置校验。
`agentic dispatch` 若存在，这三条都是它的入口检查。

**候选修法**：
1. `dispatch-lint`（或未来的 `agentic dispatch`）增一条：在**执行者工作树的
   HEAD** 上校验 Brief 与其引用的缺陷文档可读，且 sha256 与 status 锚点一致。
   不可达即拒绝派发（fail-closed）。
2. 派发前把冻结文档合入/cherry-pick 到 feature 分支，或
3. Brief 放在双方共同祖先提交上冻结。

修法 1 是根治：它把「可达」变成派发的准入条件，而不是靠编排者每次记得。

### A25 —— `path_is_in_worktree` 的语义边界：能写 worktree 内文件者可改变判据答案

**等级**：登记备查（非缺陷，是判据的固有边界）
**发现**：2026-09-15，编排者在 WP-19 rev3 验收时的对抗探测

**实证**（rev3 代码，`bbfa258`）：

```
worktree 路径，改写 worktree/.git 这个 gitfile 指向主仓 .git  -> False
```

**这不是绕过。** 改写后该目录在 git 的定义下**确实**属于主仓，判 False 是
正确语义。但它划出了这类判据的能力上限：

`path_is_in_worktree` 回答的是「**git 认为**这个路径属于哪个仓」。
A22 修的是「调用方能否用环境变量**声明**这个答案」——已修好（24 个向量实测全闭合，
含 GIT_CONFIG_COUNT 注入、GIT_TRACE 系列污染 stdout、symlink、
extensions.worktreeConfig 注入 core.worktree）。
但「能写 worktree 内 `.git` 文件者能否**改变**这个答案」——能，且无法由此判据阻止。

**为什么仍然可接受**：

1. 能写 worktree 内 `.git` 的攻击者已在执行者的写入面内。全局规范 §5.7 的隔离
   假设本就是「执行者能写自己 worktree」，这不是新增攻击面。
2. **主防线仍是路径解析**（`resolve_paths --root main_repo`），A13 起就是如此，
   本判据是绝对路径入参的兜底。改写 gitfile 骗过兜底，仍要另外突破主防线。
3. 真正需要「不可伪造」的是独立性判据（A11/A16 那条线），不是 worktree 拒收。
   worktree 拒收保护的是「别把 worktree 里的 status 副本当单一来源」，
   是防误用，不是防对抗。

**要点（与 A11/A16 同一透镜的自查结论）**：
A11 的教训是「查了状态文件能不能自填，没查 git 事实能不能自造」。
A16 是「查了判据不读 git，没查判据读的东西能不能自我重现」。
本条的自查是「查了环境变量能不能声明答案，也要查文件系统能不能改变答案」——
答案是能，但这条**不构成 A22 未修完**，因为它不依赖环境变量、需要更强的前置
（写 worktree 内 .git），且撞不动主防线。**登记而不返工**，理由写在此处备查。

**若将来要收紧**：判据可改为「由主仓的 `git worktree list --porcelain` 反查
该路径是否在已注册 worktree 列表内」——权威从被测目录移到主仓，
写 worktree 内文件就改不动答案了。但那会引入「主仓根从哪来」的依赖，
与 `resolve_paths --root main_repo` 形成环，须另行设计，不在 WP-19 范围。

---

### A26 —— 入口在到达净化判据之前就已信任调用者的仓库选择

**来源**：codex 复审 WP-19 rev2+rev3 的 finding 3（2026-09-15）。

**实证**（编排者独立复现，在 `/Users/admin/vibe/wp19-wrapper-seams`）：

```
$ PYTHONPATH=src python3.11 -m agentic_loop.resolve_paths --root main_repo
/Users/admin/vibe/agentic_loop
$ GIT_DIR=/Users/admin/vibe/data_agent/.git PYTHONPATH=src python3.11 -m agentic_loop.resolve_paths --root main_repo
/Users/admin/vibe/data_agent
```

`resolve_paths.py:101` 用 `subprocess.run(["git", *args])` 直接继承环境，
没有 A22 那套净化。于是：

- `gate main()` 先调未净化的 `main_repo()`；
- `finalize_merge.sh:23`、`codex_merge_gate.sh:21` 也先跑继承环境的
  `git rev-parse --git-common-dir`，并据其结果构造 `PYTHONPATH`；
- 相对路径的 status 入参可在判据运行之前被重绑定到另一个仓库。

**与 A22 的关系**：A22 是「判据本身被环境变量翻转」，已在 WP-19 修完
（`GIT_DIR=<预期主仓>/.git` + 绝对 worktree 路径这条具体通道已闭合）。
A26 是「判据上游的根解析被同一类变量翻转」。**这不是 A22 未修完**：
WP-19 rev2 Brief 明确写了「**不要**在 CLI 层净化环境。判据自己必须站得住，
不能依赖上游调用者替它擦干净」——那条要求是对的，判据现在确实自己站得住；
但它没有、也不能顺带保证上游根解析的正确性。

**为何不在 WP-19 内修**：`resolve_paths.py`、`cli.py`、`codex_merge_gate.sh`
均不在 WP-19 的 `allowed_paths`（`codex_merge_gate.sh` 从未出现在任何 rev 的
白名单里）。codex 自己也指出「完整修复可能需要重新冻结范围」。
在验收阶段临时扩权改 forbidden_paths，等于用返工绕过范围冻结，比缺陷本身更坏。

**候选修法**：
1. 在 `resolve_paths.py` 里把 A22 的 `_GIT_SELECTION_VARS` 净化下沉为
   **该模块唯一的 git 调用出口**（§5.3：净化口径只有一份，判据与根解析都引用它）。
   注意这与 rev2 Brief 那条禁令不冲突——禁的是「在 CLI 层替判据擦环境」，
   这里是「根解析自己也站得住」。
2. wrapper 里那两处裸 `git rev-parse` 改为调用 `resolve_paths`，消灭第二份可执行判据。

**优先级**：P1。威胁模型与 A22 同级（无需写权限、只需一个环境变量），
但主防线 `resolve_paths --root main_repo` 恰恰是被打穿的那一环，比 A25 更实。

---

### A27 —— 判据判的是路径名归属，不是实际被读写文件的归属（status symlink）

**来源**：codex 复审 WP-19 rev2+rev3 的 finding 4（2026-09-15）。

**实证**（编排者独立复现，真实临时仓 + `git worktree add`）：

```
worktree 内真实文件            -> True （拒收，正确）
主区里指向它的 symlink         -> False（放行）
link.resolve() -> .../wt/WP.status.json   # 实际读写的是 worktree 里那个文件
```

`path_is_in_worktree` 取的是**未解析的** `path.parent`（`gate/__init__.py:224`
附近的 `directory = path if path.is_dir() else path.parent`），
而后续 `is_file()`、validator 读取、finalize 写回都跟随 symlink。
于是「判的目录」与「读写的文件」可以属于两个不同的仓。

**与 A25 的区别**：A25 要求攻击者能写 worktree 内的 `.git` gitfile；
A27 只要求能在**主区**放一个 symlink。两者都属「拓扑可被布置」，
但 A27 的前置更弱，且它绕过的是判据的**语义**（问错了对象），不只是它的权威来源。

**候选修法**：判据先 `path.resolve()`（或 `os.path.realpath`）再取父目录，
使「被判的目录」与「将被读写的文件」是同一个。注意 fail-closed 方向：
`resolve()` 自身可能抛 `RuntimeError`（symlink loop，见 A28），须包在 try 内。

**范围**：落在 `gate/__init__.py` 的 A13 判据一处，**在 WP-19 的 allowlist 内**，
故并入 rev4 返工，不另立 WP。

---

### A28 —— `path_is_in_worktree` 的 fail-closed 在两条路径上不成立

**来源**：codex 复审 WP-19 rev2+rev3 的 finding 1（2026-09-15）。**P0**。

**实证 1：空白 `common_dir` 被当成「不在 worktree」**

git 成功退出但第二行为空白时：

```
F1a blank common_dir -> False   （Brief 要求 True）
```

判据只校验「恰好两行」与 `git_dir` 为绝对路径，没有校验两行 strip 后均非空。
`Path("")` 被当作相对路径，于是 `common_dir = directory / Path("")` == `directory`；
若第一行也正好是该目录，两侧相等 -> `False`，worktree-local status 被放行。
这直接违反 rev2 Brief「输出异常 -> `True`（拒收）」。

**实证 2：`resolve()` 在 try 之外，symlink loop 直接抛异常**

```
F1c symlink loop RAISED: RuntimeError Symlink loop from '...'
```

违反 docstring 自己写的「Fail-closed and never raises」。

**为什么编排者的 24 向量探测没抓到**：那 24 个向量全是**环境变量**面
（`GIT_DIR` 家族、`GIT_CONFIG_*`、`GIT_TRACE*`、`PATH`……），
验的是「调用者能否声明仓库归属」。A28 是**输出解析**面：
git 正常退出、行数正确，但内容退化。两个面互不覆盖，
而 Brief 的 fail-closed 条款同时约束两者。**这是编排者验收的漏项，不是执行者新引入的回归**
——rev1 判据同样没有这两个校验，A22 的修复没有触及它们。

**范围**：`gate/__init__.py` 的 A13 判据一处，**在 WP-19 的 allowlist 内**，并入 rev4。

---

### A29 —— `path_is_in_worktree` 仍有一处 unguarded 文件系统调用，且调用点 fail-open

**来源**：codex 复审 WP-19 rev4 期间的中途实证（该次咨询因网关错误提前中断、
未给出 verdict，但留下了可复现的证据）。编排者独立复现并定级。**P0**。

**缺陷 1（rev4 未闭合的既有洞）**：`gate/__init__.py:253`

```python
directory = resolved if resolved.is_dir() else resolved.parent
```

`is_dir()` 会 `os.stat()`，在超长路径上抛 `OSError: [Errno 63] File name too long`。
这一行**在所有 try 之外**——A28-2 只把 `resolve()` 与末尾两处 `resolve()` 包进了 try。
`OSError` 恰恰是 Brief 点名要求 fail-closed 的类型。

rev3 在同一输入上同样抛 `OSError`，故这是**既有洞，不是 rev4 引入的回归**；
A28 的修复范围没覆盖它。

**缺陷 2（rev4 引入的新 raising 路径）**：`ValueError: embedded null byte`

rev4 把 `resolve()` 前移到函数开头（A27 的修法），而 `resolve()` 对含 NUL 的路径抛
`ValueError`——既不是 `OSError` 也不是 `RuntimeError`，现有 except 抓不到。

```
rev3: path_is_in_worktree(Path("/...a\x00b.json")) -> False   （不抛）
rev4: 同一输入                                      -> RAISED ValueError
```

**缓解**：`execve` 禁止 argv 含 NUL，故两个调用点（`finalize_merge.sh` 的
命令替换、`gate main()`）都无法从 shell 传入这种路径。属于契约违反
（docstring 自陈「never raises」）而非可达攻击面。缺陷 1 则**可达**。

**为何必须修：调用点是 fail-open 的**

`finalize_merge.sh:42-51` 用命令替换取判据结果：

```bash
in_worktree=$("${AGENTIC_PYTHON:-python3}" - "$status_file" <<'PY' ... )
if [[ "$in_worktree" == "true" ]]; then ... exit 2; fi
```

判据抛异常 -> stdout 为空 -> `in_worktree` 为空串 -> `!= "true"` -> **worktree 拒收被跳过**。
实测（超长路径，走真实命令替换）：

```
in_worktree=[<EMPTY>]
NOT REFUSED (fail-open)
```

即：判据内部一个未捕获异常，会把「拒收 worktree-local status」这道门整个绕开——
方向与 Brief 的 fail-closed 要求相反。这使缺陷 1 的严重度从「不优雅」升为 P0。

**候选修法**

1. 判据侧（本轮）：把 `resolved.is_dir()` 移进 try，并把 except 扩到
   `(OSError, RuntimeError, ValueError)`。三处守卫仍保持同一形式（§5.3）。
2. 调用点侧（另立 WP，属 A26 那批 wrapper 面）：`finalize_merge.sh` 应把
   「判据未输出 true/false」本身当失败，而不是当 false。这是 shell 层的
   fail-open 模式，不止影响这一个判据。

### A30 · `test_long_path_fails_closed_without_raising` 锁的是实现细节，不是契约（P2，测试脆性）

**面**：`tests/test_worktree_detection.py`（WP-19 rev5 新增用例）

**事实**（编排者跨版本实测，4 个解释器）：

| Python | `Path(300字符).resolve().is_dir()` | 主区长路径判据 | 用例断言 |
|--------|-----------------------------------|--------------|---------|
| 3.11.14 | `OSError: [Errno 63]` | `True`（fail-closed） | True ✅ |
| 3.12.14 | `OSError: [Errno 63]` | `True` | True ✅ |
| 3.13.12 | `OSError: [Errno 63]` | `True` | True ✅ |
| 3.14.2 | `False`（不再抛） | **`False`**（正常走 git，主区本就该 False） | True ❌ |

3.14 起 `is_dir()` 对超长名返回 `False` 而不抛 `OSError`（`Path.stat()` 的
`ENAMETOOLONG` 处理改变）。此时判据**行为正确**——超长路径落在主区，答 `False`
本就是对的——但用例把「超长名必然 fail-closed」当成契约写死，于是在 3.14 上失败。

`pyproject.toml:8` 声明 `requires-python = ">=3.9"`，3.14 在支持范围内。

**定性**：**不是 A29 修复的缺陷**。判据在 3.11/3.12/3.13/3.14 四个版本上都
「对任意输入不抛」，主区判 False、linked worktree 判 True 全部正确（已实测）。
缺陷在用例：它断言的是「触发 OSError 后 fail-closed」这一实现路径，
而 A29 的契约是「不抛异常」。契约级写法应是「调用不抛」+
「在 linked worktree 内的超长路径判 True」（后者在 3.14 上实测仍为 `True`）。

**发现者**：codex（rev5 复审中主动做跨版本探查后提出），编排者独立复现确认。

**修法建议**：把断言从 `is True` 改为「不抛异常」，或改用 linked worktree 内的
超长路径（跨四版本都为 `True`）。**不在 WP-19 rev5 范围内**，另立 WP 或并入
A29 修法 2 的 WP。

### A31 · codex 咨询命令形态未固化，默认形态直接 HTTP 400（P1，流程）

**面**：编排流程（`AGENTS.md` 的 codex 咨询触发点未给出可用命令形态）

**事实**（WP-19 rev5 咨询实测，四次尝试）：

| 形态 | 结果 |
|------|------|
| `codex exec --sandbox read-only -m kirogpt` | EXIT=1，HTTP 400 |
| `+ -c 'mcp_servers={}'` | EXIT=1，同一 400 |
| `+ --disable apps` | EXIT=0，能开工 |

400 原文：`Tool name(s) exceed Kiro API limit of 64 characters:
'mcp__codex_apps__codex_document_control___execute_document_command' (66)`
等三个工具名。这些名字由 `apps` feature（`codex features list` 显示 stable/true）
**服务端注入**，不来自 `~/.codex/config.toml`，故清空 `mcp_servers` 无效，
必须 `--disable apps`。

**影响**：默认形态下 codex 咨询在推理前即被拒，编排者若不逐层排查，会误判为
「codex 无法审」或「模型不可用」。WP-19 已有两轮咨询未取得 verdict
（rev4 中断、rev5 第 3 次空结论），排查成本全部落在编排者身上。

**修法建议**：把 `codex exec --sandbox read-only -m kirogpt --disable apps`
固化进 `AGENTS.md` 的咨询触发点，或包一个 `agentic consult` wrapper。
与 A19/A23（派发命令形态与「已开工」确认）同类，建议并包。

**另**：`codex_models_manager: failed to refresh available models` 在 rev4 与
rev5 第 3 次尝试中都出现，且都伴随「最终消息为空、无 verdict」。二者是否因果
未证实，但已两次共现，重试时应显式要求「直接给结论、不要长时间探查」。

### A32 · 审核者 codex 在执行者 worktree 留下写入痕迹（P2，隔离）

**面**：`--sandbox read-only` 下的 serena MCP 工具

**事实**：rev5 咨询后，`/Users/admin/vibe/wp19-wrapper-seams` 出现未跟踪目录
`.serena/`（`project.yml`、`project.local.yml`、`.gitignore`）。主仓无此目录；
`.gitignore` 与 `.git/info/exclude` 均无 `serena` 规则，故它会出现在
`git status --porcelain` 里，污染「树是否干净」这一验收判据。

**定性**：违反全局规范 §5.7——审核者只读，不应在执行者工作区留下写入面。
`--sandbox read-only` 约束的是 codex 自身的 exec，未约束其 MCP 工具的落盘。

**编排者处置**：未删除，留作证据。

**修法建议**：咨询 codex 时一并 `--disable` serena（或用不带 MCP 的 profile），
并把 `.serena/` 写进 `.git/info/exclude` 作为兜底。可并入 A31 的 WP。

### A33 · `test_symlink_loop_fails_closed_without_raising` 同类脆性，且从 Python **3.13** 起就失败（P1，测试脆性）

**面**：`tests/test_worktree_detection.py`（WP-19 **rev4** 新增用例，非 rev5/rev6 引入）

**事实**（编排者跨四版本实测，真实自指 symlink + 真实临时仓）：

| Python | `Path(自指symlink).resolve()` | `is_dir()` | 判据 | 用例断言 `is True` |
|--------|------------------------------|-----------|------|------------------|
| 3.11.14 | `RuntimeError` | `False` | `True`（fail-closed） | ✅ |
| 3.12.14 | `RuntimeError` | `False` | `True` | ✅ |
| 3.13.12 | **不抛，原样返回路径** | `False` | **`False`** | ❌ |
| 3.14.2 | **不抛，原样返回路径** | `False` | **`False`** | ❌ |

自 3.13 起 `Path.resolve()`（非 strict 模式）对 symlink 循环不再抛 `RuntimeError`，
而是原样返回路径。此时判据走正常 git 路径：该 symlink 位于主区，答 `False`
**本来就是对的**。判据行为正确，错的仍是断言——它锁死了 3.11/3.12 的实现表现。

**与 A30 的关系**：**同一个类，不同实例**。A30 是 `is_dir()` 在 3.14 变，
A33 是 `resolve()` 在 3.13 变。共同根因：rev4/rev5 的「fail-closed 用例」都用
**触发某个特定异常**的方式构造输入，而这些异常的抛出条件跨 Python 版本会变；
契约（「不抛异常且返回 bool」）却是稳定的。

**引入轮次**：A33 的用例来自 **rev4**（A28-2），比 A30 更早。
编排者在 rev4 与 rev5 两轮验收中**都只用 python3.11 单解释器测**，
故两次都没发现。这是编排者验收方法的漏项，不是执行者新引入的回归。

**实测分层证据**（基线 `16e59ff` = rev5 代码，未含 rev6 改动）：

| 解释器 | rev5 代码（基线） | rev6 工作树 |
|--------|------------------|------------|
| 3.11 | 17 passed | 18 passed |
| 3.13 | **1 failed** + 16 passed | （A33 仍在） |
| 3.14 | **2 failed** + 15 passed | **1 failed** + 17 passed（A30 已修，A33 仍在） |

→ rev6 确实修掉了 A30（3.14 上 2 failed → 1 failed），且未引入新失败；
剩下的 1 failed 是 A33，**在 rev6 范围之外**（该用例不在 rev6 Brief 的交付物里）。

**修法建议**：与 A30 同法——断言降为「不抛异常且返回 `bool`」，
并补一条 linked worktree 内 symlink 循环判 `True` 的用例（若跨版本稳定）。
**建议与 A30 的收尾并成一个「用例契约化」WP 一次做完**，并把
「验收必须跨 3.11/3.13/3.14 三个解释器」写进该 WP 的 DoD，避免第三次漏。

**编排者方法更正**：本轮起，凡涉及「异常路径 / fail-closed」的用例，
验收一律用 `uv run --python <ver> --with pytest --no-project` 跨版本实跑，
不再只用 python3.11。

#### A33 补充：执行者「fail-open」定性经编排者实测**不成立**

rev6 执行者在 `[STATUS] BLOCKED` 的理由里称该形态下判据 **fail-open**，
并据此认为必须改判据（本轮硬禁）才能闭合。**编排者独立实测否证了这一点。**

判别方法：fail-open 的定义是「本该拒收的输入被放行」，即
**位于 linked worktree 内**的 status 被判 `False`。故必须测 worktree 内的 symlink 循环，
而不是主区的。

| Python | 主区内 symlink 循环（正确答案 False） | **linked worktree 内** symlink 循环（正确答案 True） | fail-open？ |
|--------|--------------------------------|------------------------------------------|-----------|
| 3.11.14 | `True`（因 `resolve()` 抛错而 fail-closed，答案偏保守） | `True` ✅ | 否 |
| 3.13.12 | `False` ✅（正确） | `True` ✅ | **否** |
| 3.14.2 | `False` ✅（正确） | `True` ✅ | **否** |

**结论**：三个版本上，worktree 内的 symlink 循环**始终被拒收**，拒收从未被绕过。
3.13+ 主区答 `False` 是**正确**答案；3.11 答 `True` 只是因为 `resolve()` 抛异常
触发了 fail-closed 兜底，属"偏保守但恰好也不错"。

→ A33 的定性维持为**测试脆性（P1）**，**不是安全缺陷**，
也**不需要改 `gate/__init__.py`**。修法只需把断言契约化（与 A30 同法）。
执行者判 BLOCKED 的前提有误，但其「不擅自扩权改禁改文件、交回编排者裁决」
的处置是**正确**的——按 §4.1，范围裁决权在编排者。

#### A29 修法 2「wrapper 命令替换 fail-open」经编排者实测**不成立**（撤销该待办）

原登记的担忧：`finalize_merge.sh:42-50` 用命令替换取判据结果
（`in_worktree=$(python … path_is_in_worktree …)`），若判据抛异常则 `$in_worktree`
为空串，`[[ "$in_worktree" == "true" ]]` 不成立，**拒收分支被跳过**，即 fail-open。

编排者在真实调用点直测（worktree `wp19-wrapper-seams` @ `949b976`）：
构造一个语法合法但调用即抛 `RuntimeError` 的 `path_is_in_worktree` 覆盖版，
经 `PYTHONPATH` 注入，只让该判据失败而 `resolve_paths` / `validate_wp_status` 正常：

| 观测项 | 结果 |
|--------|------|
| 脚本退出码 | `rc=1` |
| 是否打印 `FINALIZE_OK` | 否 |
| 是否执行到后续任何 finalize 步骤 | 否（0 处匹配） |
| 是否打印 worktree 拒收信息 | 否（但也**没有**放行） |

根因：`finalize_merge.sh:4` 是 `set -euo pipefail`，而该命令替换出现在
**普通赋值语句**中，不在 `if` 条件、`&&`/`||` 或 `!` 之后。POSIX shell 语义下，
简单赋值的命令替换退出码即赋值语句退出码，`set -e` 因此立即终止脚本。
对照实验确认了这条边界：

```
v=$(python3 -c 'raise RuntimeError("boom")')        -> script_rc=1（中止）
if [[ "$(python3 -c 'raise ...' 2>/dev/null)" == "true" ]]  -> PROCEED（set -e 在 if 条件里被挂起，才会 fail-open）
```

→ 现有形态是**赋值**而非 if 条件内嵌，故 **fail-closed**，A29 修法 2 不构成缺陷，
待办撤销。**遗留加固建议（非缺陷，P2）**：该保护依赖「赋值 + `set -e`」这一隐式
耦合，若日后有人把它挪进 `if` 条件或加上 `|| true`，就会真的变成 fail-open；
建议在该行上方留一行注释锁定意图，并补一个 characterization test（注入抛异常的判据，
断言 `rc != 0` 且无 `FINALIZE_OK`）。此项并入「用例契约化」WP。

### A34 · `path_is_in_worktree` 判定与后续使用之间存在 symlink TOCTOU 窗口（P2，安全，另立 WP）

**来源**：WP-19 rev6 codex 复审的 P2 新发现（编排者与执行者均未看到）。

`finalize_merge.sh` 的时序是：先算 `in_worktree`（解析路径 + git 探测）→ 再 `[[ -f ]]`
→ 再 `validate_wp_status` → 再写回。判定与后续每一步都各自重新解析同一路径，
其间存在时间窗：若本地并发者在判定通过后把该路径（或其中一段目录）替换为
指向 worktree 内文件的 symlink，则拒收判据已过、后续操作却落到被替换后的目标上。

**与 A33 的区别**：A33 是**静态** symlink 循环，codex 与编排者各自独立确认其不构成绕过；
A34 需要**竞态**，是另一类问题。

**定级理由（P2 而非 P0/P1）**：需要本地并发写权限的攻击者，而当前威胁模型是
「防自证、防误操作」，未纳入本机恶意并发。**若日后把本地并发写入纳入威胁模型，
本条应重估为 P1**。

**修法方向（供后续 WP 参考）**：判定与使用共用**同一个已解析结果**（一次解析、
后续复用），或改用文件描述符 / `O_NOFOLLOW` 语义，而非每步各自重新按路径解析。

#### A31 补充：不能只看日志尾部判断 codex 是否给出结论

rev6 咨询这一轮，codex **完整输出了 `[VERDICT] ACCEPT` 与全部 findings**，
随后才以 `codex_models_manager: failed to refresh available models` 结束，
故 verdict 位于日志**中段**而非末尾。编排者第一次只 `tail` 日志，误判为「无结论」
并发起了一次多余的重试。

→ 判据修正：读 codex 日志须**全文检索** `[VERDICT]`（注意 ANSI 转义与非 UTF-8 字节，
`grep` 前先剥转义或用 `LC_ALL=C grep -a`），不得以 `tail` 的内容作为「是否有结论」的依据。

#### A19 补充：codex 指出「同基线替代提交」不能用 `A..B` 判范围

rev5（`77941f4`）与 rev6（`949b976`）是**同基线的替代提交**，不是父子关系，
故 `77941f4..949b976` 不等于本轮范围。正确写法是 `949b976^..949b976`。
编排者原用 AST 逐 def 比对得出同样结论，但 range 写法应统一为后者，
并入派发/验收命令形态 WP（任务 A19+A23）。

#### A32 补充：证据内容已核实并留痕，worktree 已清理

清理 `wp19-wrapper-seams` worktree 前，编排者核实了 codex 以 `--sandbox read-only`
运行却留下的 `.serena/` 目录内容（20K，3 个文件）：

| 文件 | 内容性质 |
|------|----------|
| `.serena/project.yml` | serena 项目配置模板，`project_name: "wp19-wrapper-seams"`（**以 worktree 名自动命名**，证明确由该 worktree 内的运行生成），其余为默认注释 |
| `.serena/.gitignore` | 两行：`/cache`、`/project.local.yml` |
| `.serena/project.local.yml` | 仅注释，无实际设置 |

**无敏感内容，也无 codex 的分析产物**（不含代码摘要、记忆或索引缓存）。
故 A32 的实质危害仅限于**污染「树是否干净」判据**：`git status --short` 因此长期显示
`?? .serena/`，使「worktree 无未跟踪文件」这一验收信号失效。

定性维持 **P2**：`--sandbox read-only` 的语义应是「不写被审仓」，但 MCP 工具的副作用
绕过了该声明。修法方向：咨询命令加 `--disable serena`（同 A31 的 `--disable apps`），
或把 serena 的项目目录重定向到仓外。并入 A31 的「固化 codex 咨询命令形态」待办。

清理动作已由用户批准：`git worktree remove` + 删除已并入的 `feature/wp19-wrapper-seams`
分支（`949b976` 已是 `plan/2026-09-13-parallel-throughput` 的祖先，且已推送 origin）。

#### A34 补充：编排者实测——写面**不可利用**，读面**可换掉**，窗口仍在（维持 P2）

编排者用独立临时仓（不碰被审仓）按 `finalize_merge.sh` 的真实时序做了两次探测。

**探测 1：写回是否会落到 worktree 副本？→ 不会。**

时序：判定通过 → 攻击者把主区 status 换成指向 worktree 副本的 symlink →
`[[ -f ]]` → `mktemp "$status_file.XXXXXX"` → `mv "$tmp" "$status_file"`。

| 观测项 | 结果 |
|--------|------|
| `[[ -f ]]` 是否跟随 symlink | **是**（通过） |
| 写回后主区路径是否仍是 symlink | 否 |
| 写回内容落在 | **主区路径**（`{"FINALIZED_BY_SCRIPT": true}`） |
| worktree 副本 | **未被触碰**（内容原样） |

根因：`mv` 是 `rename(2)`，**替换 symlink 本身**而不跟随它。故 `finalize_merge.sh:206-229`
的 mktemp+mv 写回形态**天然免疫**这条路径的 symlink 重定向。

**探测 2：读取是否会读到 worktree 副本？→ 会。**

同一路径在替换前后读到不同内容：`MAIN_COPY_REWORK` → `WORKTREE_COPY_FORGED_ACCEPT`。
故 `finalize_merge.sh:56`（`-f`）、`:61`/`:64`（两处 validator）、`:209`（读旧 JSON）
这四处**都会跟随替换后的 symlink**。理论危害：用一份「伪造已双签」的 worktree status
骗过 finalize 的决策逻辑。

**但**：判据对**替换后**的该路径答 `True`（实测），即若判定发生在替换之后，
拒收会正常启动。可利用性**完全取决于替换是否精确落在「判定完成」与「读取」之间的窗口**。

**定级维持 P2**，理由更明确了：需要本地写权限 + 精确竞态时机 + 一份预置的伪造 status；
而当前威胁模型是「防自证、防误操作」。写面已免疫，读面需竞态。
**若日后把本地并发写入纳入威胁模型，重估为 P1。**

**修法方向收窄**（供 WP 参考）：不必改写回形态（已免疫），重点是**判定与读取共用同一个
已打开的文件**——判定后拿到 fd 并全程复用（`os.open` + `O_NOFOLLOW` 后按 fd 读），
或判定与首次读取之间不再有第三方可插入的间隙。

---

### A35 · WP-21 的 A29 characterization test 是**空验证**：两种被明令禁止的变异都能通过（P1，测试有效性，编排者自身缺陷）

**发现于**：WP-21 rev1 验收（编排者变异测试）。
**责任**：**编排者**。WP-21 Brief 交付物 2 逐字规定了这两条断言
（「断言 finalize **退出码非 0** 且输出中**无** `FINALIZE_OK`」），执行者严格照做，
用例本身写得干净且前提断言齐备。缺陷在 Brief 的用例设计，不在执行。

**现象**：`tests/test_finalize_merge_first_call.py::test_finalize_fails_closed_when_predicate_raises`
用一个**不存在**的 status 路径（`docs/plans/wp19-first-call/WP-FC.status.json`，
测试只 `repo.mkdir()` + init 一个 README，从未创建该 status）调用 finalize。
于是 fail-open 变异并不会被抓住——判据崩掉后脚本继续走到下一步的
`FINALIZE_FAIL: status file not found` 而 `exit 2`，两条断言（`rc != 0`、无
`FINALIZE_OK`）**照样成立**。

**实测（编排者变异测试，status 缺失 = 用例现状）**：

| 形态 | rc | 有 `FINALIZE_OK`？ | 用例判定 |
|------|----|-------------------|---------|
| A 普通赋值（现行，应通过） | 1 | 无 | **PASS** |
| B `\|\| echo false`（注释明令禁止） | 2 | 无 | **PASS ← 应当失败** |
| C 挪进 `if` 条件（注释明令禁止） | 2 | 无 | **PASS ← 应当失败** |

变异 B 的输出里还明确打印了 `false`，随后**跳过了 worktree 拒收**——正是用例
本该锁住的行为，却因为 status 不存在而被下一步的 `not found` 掩盖。

**修法（已实测有效）**：换成一个**真正可 finalize** 的 status。同文件已有现成
fixture：`_make_repo_with_merged_wp()` + `_status_without_merged_commit()`，
写入并提交后再跑。此时断言立刻具备区分力：

| 形态 | rc | 有 `FINALIZE_OK`？ | 用例判定 |
|------|----|-------------------|---------|
| A 普通赋值（现行） | 1 | 无 | **PASS** |
| B `\|\| echo false` | 0 | **有** | **FAIL ✅ 抓住** |
| C 挪进 `if` 条件 | 0 | **有** | **FAIL ✅ 抓住** |

**教训（写进 Brief 设计纪律）**：**凡 characterization test 锁的是「某个错误形态会
被拦住」，Brief 必须同时要求执行者做一次变异自证**——把被禁止的形态真的写进去、
跑一次、确认用例**变红**，并把这次变红写进 `[TESTS]`。只断言「rc != 0」这类
**否定式**结论极易空过：脚本在任何更早的一步失败都能满足它。否定式断言必须配
「正常路径能走到终点」的正面对照，否则无法区分「被拦住」与「压根没走到」。

> 与 A31 补充同类：都是「用一个太弱的观测口径下结论」。A31 是用 `tail` 判有无
> verdict，本条是用 `rc != 0` 判有无拦住。

---

#### A26 补充：编排者复核——通道比原记录更宽（含 `GIT_COMMON_DIR`），且**探针形态会误判为已修**

**复核日期** 2026-09-15（WP-21 rev2 执行期间，编排者独立复核）。

**先纠正一个探针陷阱**：用**linked worktree 的 `.git`** 当 `GIT_DIR` 探测，会得到
「不受影响」的假阴性——

```
$ GIT_DIR=/Users/admin/vibe/wp21-test-contracts/.git \
    PYTHONPATH=src python3.11 -m agentic_loop.resolve_paths --root main_repo
/Users/admin/vibe/agentic_loop          # 看似已修，其实是因为该 worktree 的
                                        # git-common-dir 本来就指向主仓
```

`main_repo()` 取的是 `--git-common-dir` 的父目录，而 linked worktree 的
common-dir **本就是主仓的 `.git`**，所以这条探针**在缺陷存在时也会返回正确答案**。
必须用**无关仓**探测。与 A31/A35 同一族教训：观测口径太弱，无法区分「已修」与
「压根没测到」。

**用无关仓复测的通道矩阵**（临时仓 `a26repo`，与本仓无任何关系）：

| 环境变量 | `resolve_paths --root main_repo` 输出 | 判定 |
|---------|--------------------------------------|------|
| （无） | `/Users/admin/vibe/agentic_loop` | 基准 |
| `GIT_DIR=<无关仓>/.git` | `<无关仓>` | **被改指** |
| `GIT_COMMON_DIR=<无关仓>/.git` | `<无关仓>` | **被改指（原记录未列此条）** |
| `GIT_WORK_TREE=<无关仓>` | `/Users/admin/vibe/agentic_loop` | 不受影响 |
| `GIT_CEILING_DIRECTORIES=/Users/admin/vibe` | `/Users/admin/vibe/agentic_loop` | 不受影响 |

**根因未变，仍然成立**：`resolve_paths.py:100-104` 的 `_git()` 是该模块**唯一**的
git 调用出口，但 `subprocess.run(["git", *args])` 直接继承环境，无任何净化：

```python
def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
```

对比 `gate/__init__.py:256` 已有的净化口径 `if key not in _GIT_SELECTION_VARS`
——**净化逻辑在仓里已经有唯一权威了，只是根解析没引用它**。
这使修法 1（下沉净化到 `_git()`）比原记录所写更直接：不是新造判据，
而是让第二个调用方引用既有权威（§5.3）。

**对修法的补充要求（已核实，结论更好）**：`_GIT_SELECTION_VARS` **已含全部 7 个变量**
（`GIT_DIR`、`GIT_WORK_TREE`、`GIT_COMMON_DIR`、`GIT_INDEX_FILE`、
`GIT_OBJECT_DIRECTORY`、`GIT_ALTERNATE_OBJECT_DIRECTORIES`、
`GIT_CEILING_DIRECTORIES`），本次实测的两条活通道 `GIT_DIR` / `GIT_COMMON_DIR` 都在其中。
→ 故修法 1 **不需要新增集合、不需要新写判据**，只需让 `resolve_paths._git()`
**引用既有唯一权威**。这是纯粹的「第二个调用方接上已有权威」，是 §5.3 最干净的形态，
WP 范围因此可以很窄。

注意方向：净化集合当前定义在 `gate/__init__.py` 内（以 `_` 私有前缀）。让
`resolve_paths` import `gate` 会造成**依赖方向问题**（§5.1）——`gate` 是上层门禁，
`resolve_paths` 是被它调用的基础解析层。修法须把集合与净化动作下沉到**双方都能依赖的
低层**（例如 `resolve_paths` 自身，再由 `gate` 引用），**不得**让 `resolve_paths` 反向
import `gate`。

**另注**：wrapper 侧共 **11 个** `.sh` 有裸 `git rev-parse --git-common-dir`
（dispatch_lint / gate-runner / finalize_merge / codex_merge_gate / kimi-health /
lock / merge / preflight / redispatch / quality-gate / qoder_security_gate），
都在构造 `PYTHONPATH` 之前跑、都继承环境。修法 2（改调 `resolve_paths`）
面比原记录估计的大得多，且存在自举顺序问题（要先有 `PYTHONPATH` 才能调 Python
模块，而 `PYTHONPATH` 正是用这条 `rev-parse` 算出来的）。
→ **建议 WP 只做修法 1**（Python 侧根解析净化），wrapper 侧的自举链单独评估，
不要在同一个 WP 里混做。

---

### B8 · 范围核验的基线取错：把编排者自己的 `docs/` 提交误报成执行者越界（编排者工具缺陷）

**发现于** WP-21 rev2 验收（2026-09-15）。**责任**：编排者的验收脚本。

**现象**：`verify_wp21r2.sh` 用 `git diff --name-only <rev1 commit>..HEAD` 判越界，
报出 5 个 `docs/` 文件「白名单外」→ `SOME CHECKS FAILED`。实际全是**编排者自己**的
提交（`a806e8e` 报告与 rev2 Brief、`d28f626` status、`4aab0e5` WP-22 Brief），
经 A24 的「合入 plan 分支使冻结 Brief 在执行者 worktree 内可达」这一步进入 worktree。
执行者本轮 commit（`4b9fdfa`，父提交 `daf537c`）**只改了 1 个文件**。

**根因**：范围核验的基线取了**上一轮的执行者 commit**（`6995873`），而两轮之间
夹了一个编排者的 A24 merge。`6995873..HEAD` 这个区间因此同时包含
「执行者本轮改动」与「编排者经 merge 带进来的 docs 改动」，两者混在一起。

**正确口径**：范围核验必须只看**执行者本轮 commit 自身的改动面**，即
`<派发时 worktree HEAD>..<执行者 commit>`——本例是 `daf537c..4b9fdfa`。
派发时的 worktree HEAD 应在 status 里记下来（现在 `git.base_commit` 记的是主区
基线，不是 worktree 派发点，两者在有 A24 merge 时不同）。

**辅助判据**（本次用来快速定性，可并用）：
- `git log --format='%h %an' -1 -- <file>` 看每个可疑文件到底是谁改的
- `git diff --name-only <exec_commit>^..<exec_commit>` 只看执行者那一个 commit

**与 A31/A35/A26-补充同族**：都是「观测口径选错，导致结论不可靠」。前三条是
**假阴性**（该报的没报出来），本条是**假阳性**（不该报的报了）。假阳性同样有害：
它会诱使编排者去驳回一个合规的交付，或在噪声里漏掉真实越界。

**待办**：把「范围核验用派发点作基线」写进编排者的验收脚本模板，并在 status 里
补记 worktree 派发点 commit（需确认 schema 是否已有合适字段，若无则走
`evidence.artifacts` 或另立字段的 WP，不要擅自加 top-level 字段——`redispatch_count`
就因为放在 top-level 被 `validate_wp_status` 拒过一次）。

**已修（2026-09-15）**：

1. **字段**：实测 `validate_wp_status.py` 对 `git` 子块**不做**未知键拒收
   （只有 top-level 有白名单，`:377-383`）。故 `git.dispatch_commit` 可直接写入，
   无需新立 WP、无需 `evidence.artifacts` 变通。已在 `WP-21.status.json` 落地
   （`dispatch_commit=daf537c`），`STATUS_VALID` 通过。
2. **工具**：新增 `review_scope.sh`（编排者验收工具，暂存
   `~/.claude/jobs/8a8bf01e/tmp/`，待并入 `.ci/` 或 `docs/agentic/templates/`）。
   口径：区间恒为 `git.dispatch_commit..git.commit`。
3. **fail-closed**：`dispatch_commit` 缺失时**拒绝核验**（`SCOPE_UNVERIFIABLE`，rc=3），
   既不退化成 `base_commit`，也不猜 `HEAD^`——猜错基线正是 B8 本身。
4. **配正面对照**（A35 的教训）：区间内 0 个文件改动时报 `SCOPE_VACUOUS` 并失败，
   否则「无越界」本身就是空验证。
5. **实测对比**（WP-21 rev2，同一执行者 commit `4b9fdfa`）：

   | 基线 | 报出的改动文件 | 判定 |
   |------|:---:|------|
   | `6995873..4b9fdfa`（B8 错误口径） | 6（含 5 个编排者 `docs/`） | 假阳性越界 ❌ |
   | `daf537c..4b9fdfa`（派发点口径） | 1 | `SCOPE_OK` ✅ |

**辅助判据的一处修正**：B8 原文建议用 `git log --format='%h %an'` 看责任归属——
**该判据在本仓无效**。实测 worktree 内 7 个提交的 `%an` **全部**是 `xizhu`
（编排者与执行者的提交都经同一 git 身份落盘），作者名无法区分角色。
责任归属只能靠**记录在 status 里的派发点**，不能靠启发式推断。


### A35 后续加固（P2，来自 codex 复核 WP-21 rev2）

**发现于** 2026-09-15，codex 复核 WP-21 rev2 时点名（该次咨询未出正式裁定，
见 `WP-21-consult-codex.md`；以下事实由编排者独立实测复核）。

负向运行只断言 `rc != 0` 且输出无 `FINALIZE_OK`，**未断言 stderr 确实含注入的
`RuntimeError`**，因此形式上不能排除「影子环境在判据之前某一步失败」这一新空过通道。

编排者实测：该运行 `rc=1`，stderr **确实**含
`RuntimeError: injected broken predicate (WP-21 A29 hardening)`——结论正确，
但**该事实没有被断言锁住**。用例第 62 行的 `probe` 断言只证明影子包会抛，
不证明 finalize 那一次死在判据上。

**为何不阻断 rev2**：正面对照（同一 status、不注入影子包必达 `FINALIZE_OK`）
已排除「更早一步失败」——唯一变量是影子包。

**待办**：随下一次触及 `tests/test_finalize_merge_first_call.py` 的 WP 加一行
`assert "injected broken predicate" in res.stderr`。**不在验收阶段临时扩权改。**

### A29 注释方向写反（P2，来自 codex 复核 WP-21 rev2）

`finalize_merge.sh` 的 A29 注释写「Never move it into an `if` condition or after
`&&`/`||`」。编排者实测（`set -euo pipefail`）：

| 形态 | rc | 语义 |
|------|:--:|------|
| `x=$(crash)`（现行） | 7 | **fail-closed** ✅ |
| `x=$(crash) && true`（赋值在 `&&` **左**） | 0 | **fail-open** ❌ |
| `true && x=$(crash)`（赋值在 `&&` **右**） | 7 | fail-closed ✅ |
| `x=$(crash) \|\| echo false`（赋值在 `\|\|` **左**） | 0 | **fail-open** ❌ |

注释里的「after `&&`/`||`」**恰是安全的那一侧**（右操作数）；危险的是**位于
`&&`/`||` 之前**（左操作数），此时赋值成为 AND/OR-list 的一部分，`set -e` 被抑制。

**额外发现（编排者扩测，超出 rev2 Brief 指定的两种变异）**：变异 D
（`in_worktree=$(...) && true`，左操作数形态）也是 fail-open，且 rev2 用例
**能抓住**（`AssertionError: (0, 'FINALIZE_OK merged_commit=565d01b...')`）。
即 rev2 用例的区分力超出 Brief 指定范围。变异已还原，0 行 diff。

**归责**：那 6 行注释由 rev1 Brief 规定、rev1 已验收，属编排者遗留，非执行者本轮问题。
**不影响**代码正确性（代码是安全形态）与用例区分力（实测能抓住）。

**待办**：随下一次触及 `finalize_merge.sh` 的 WP 把方向改对——
禁的是「赋值出现在 `&&`/`||` 的**左侧**」以及「挪进 `if` 条件」。

### B9 · 「观测通道选错」是一族反复出现的编排者缺陷，且流程上没有任何防线

**等级**：流程级（编排面），P1
**发现于** 2026-09-15，编排者在 WP-21 rev2 收尾时对 A31/A35/B8/A26-补充 做同族归纳

**同族清单**（全部由编排者自己犯，全部与被审代码无关）：

| 缺陷 | 用了什么通道 | 想判断什么 | 错法 |
|------|-------------|-----------|------|
| A31 | `tail` 看日志尾部 | 裁定是否存在 | 假阴性：裁定在中段，尾部看不到 |
| A35 | `rc != 0` | 判据是否被拦住 | 假阴性：任何更早一步失败都满足 |
| A26-补充 | 在 linked worktree 里探 `GIT_DIR` | 缺陷是否已修 | 假阴性：linked worktree 的 git-common-dir 本就指主仓 |
| B8 | `<上轮执行者 commit>..HEAD` | 执行者是否越界 | 假阳性：区间夹了编排者的 A24 merge |
| **本轮又一次** | 全文 `grep '\[VERDICT\]'` | codex 是否出了裁定 | 假阳性：命中的是 codex 用 `nl -ba` 打印的**文档正文**第 1728 行 |

最后一条是决定性的：**在已经登记了前四条、并写了一条 memory 之后，同一类错误
当轮再犯**。这说明「记住教训」不构成防线——编排者每次都要重新想起来，
而想不起来时没有任何东西会报警。

**共同结构**：判据与结论之间存在**未验证的等价假设**。
`rc != 0` ⇒「被拦住」、`grep 命中` ⇒「裁定存在」、`区间有 docs/` ⇒「执行者越界」——
这些蕴含关系都**不成立**，但都在「结论恰好正确」的场合下不会暴露。

**为什么单靠「更仔细」无效**：三个错法各自都很自然，且**失败时静默**。
假阴性看起来像「通过了」，假阳性看起来像「抓到了」，两者都不会自我暴露。

**候选防线（按成本递增）**：

1. **每条否定式断言必须配正面对照**（最小、已在实践中生效）。
   已应用于：rev2 Brief（要求正面对照 `FINALIZE_OK`）、`review_scope.sh`
   （区间 0 文件改动报 `SCOPE_VACUOUS`）。
   一般形式：**任何「X 没发生」的判定，必须同时证明「同一通道下 X 发生时能被观测到」。**
2. **变异自证进 DoD 模板**：凡 characterization test 锁的是「禁止形态」，
   Brief 必须要求执行者真的把禁止形态写进去、证明变红、再还原。
   已在 rev2 Brief 落地，建议提为通用 DoD 条目。
3. **结构化输出替代文本抓取**：判定另一个 agent 的输出时，不要 `grep` 日志——
   用 `--output-schema` + `-o <file>` 让裁定落进独立文件。
   codex adapter（`adapters/codex.py:120-145`）**本来就是这么做的**；
   编排者手搓 `codex exec` 时绕开了它，这才有了 `grep` 的机会。
   **本条是根治**：通道从「在噪声里找信号」变成「读一个只含信号的文件」。
4. **基线/区间必须来自记录，不得来自推断**：B8 的修法（`git.dispatch_commit`
   写进 status，缺失即 `SCOPE_UNVERIFIABLE`）是这条的实例。

**codex 的补充（2026-09-15 第二轮咨询 P2-3，已采纳）**：

codex 独立归纳的口径比上面四条更可操作——「评审验证了测试结果，却没有系统验证
测试所用 **oracle** 是否真正观察到目标事实」。它给出的最小「oracle 校验」三项：

1. 同 fixture 的**正向可达性对照**（证明前置条件可达终点）
2. 负向运行的**原因特异 witness**（异常标记、状态或精确事件）
3. 至少一个**代表性禁止变异必须使测试转红**

**第 2 项是编排者漏掉的一环**。上面防线 1 写的是「否定式断言配正面对照」，只对应
第 1 项；而正面对照证明的是**前置可达**，witness 证明的是**失败归因**，
两者不能互相替代——「无注入时能到终点」并不排除「带注入时死在别处」。
WP-21 rev2 恰好就缺第 2 项（实测 stderr 确实含 `injected broken predicate`，
但没被断言锁住），这是 A35 后续加固项的由来。

**待办**：把 oracle 校验三项提为 Brief 模板中「安全性/负向测试」的通用 DoD 条目，
评审时逐项记录证据；把「编排者不得手搓 `codex exec`，一律走 adapter 或至少带
`--output-schema`」提为硬规则。
建议与 A19/A23/A24（都是「派发/咨询缺少代码化入口」）合成一个 WP——
根因相同：**编排者的动作没有代码化，于是每次靠记性，而记性会失效。**

**又一条实证（同轮）**：`--output-schema` 在本 provider 下是**软约束**。
codex 输出的 `findings` 是按 severity 分键的对象，而 schema 声明的是数组。
内容完整不影响采信，但消费方（如 `adapters/codex.py` 的 `_parse_verdict`）
不能假定严格贴合，否则会在解析处炸。

---

### B10 · WP Brief 模板过不了 `dispatch_lint` 自己要求的三个锚点

**等级**：流程级（工具面），P1
**发现于** 2026-09-15，编排者在推进 B9 待办（把 oracle 校验三项提为模板 DoD）时实测

**事实**：`dispatch_lint.sh:69-76` 要求每份 brief 必须含三个 `## ` 精确锚点且各段非空：

```
Acceptance tests / Allowed and forbidden paths / Completion definition
```

而两份模板母本**一个锚点都没有**，且互为同一份内容：

| 文件 | 角色 | 同一判据下的结果 |
|------|------|----------------|
| `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` | 打包母本（`init_cmd.py:109` 铺开来源） | `FAIL missing 'Acceptance tests'` |
| `docs/agentic/templates/WORK_PACKAGE.md` | 项目内被引用的骨架 | `FAIL missing 'Acceptance tests'`（与母本 `diff` 为空） |
| `WP-22-brief.md`（真实派发过） | 正面对照 | `OK` |
| 模板 + 三个空锚点 | witness | `FAIL empty 'Acceptance tests'`（非 `missing`，证明第二段判据也活着） |

**后果**：照模板写的 brief 必然在 `agentic preflight` 里挂掉。历史上每个人都是
在挨了一次 lint 之后**手工补**三个英文锚点——所以 `WP-20-brief.md`（三个全缺）
和 `WP-19-brief-rev2.md`（缺两个）留在了仓里，它们要么从未真正过 preflight，
要么过的是别的路径。锚点靠记性补，而记性会失效（同 B9 结构）。

**与 B9 的关系**：B9 的待办之一是「把 oracle 校验三项提为 Brief 模板中的通用
DoD 条目」。落这条时才发现模板连**现有**硬要求都不满足——**往一个本身不合规的
模板里加 DoD 条目，加完还是不合规**。故 B10 必须先修，是 B9 待办的前置。

**修法（单一，无争议）**：在两份模板里补齐三个英文锚点段，且与既有中文段
**同义不同份**——按 `WP-19-brief.md:147-149` 已确立的写法，显式标注
「以下为 `dispatch-lint` 要求的英文锚点，内容与上文中文章节同义，非另一份口径」，
避免造出第二份可执行口径（§5.3）。同时把 B9 的 oracle 校验三项写进
`Acceptance tests` 段作为通用要求。

**为什么不能只改 `docs/` 那份**：`init_cmd.py:109` 从 `.tmpl` 铺开，只改项目内
那份会在下次 `agentic init` 被覆盖回不合规状态。两份必须同改（它们本就 `diff` 为空）。

**待办**：与 B9 的模板改造合成一个 WP（都改模板、都要跑 `dispatch_lint` 自证），
建议记为 WP-24。修完须以「模板副本喂 `dispatch_lint` 的 section 检查得 `OK`」
自证，并保留失败前状态的对照（否则又是一条空验证）。

---

## B11 · 编排者用「抄出来的判据副本」当观测通道，把副本自造的措辞写成冻结 Brief 的必达断言

**发现时间**：2026-09-15，WP-24 交付验收时，由**执行者的 `[CONCERNS]` 反向指出**。
**责任方**：编排者（claude）。这是一条**编排者自身**的缺陷，不是执行者的。
**族属**：B9「观测通道选错」同族（判定通道与结论之间隔着未核验的等价假设）。

### 事实

登记 B10 时，我需要判断「模板过不过 `dispatch_lint.sh` 的 section 检查」。
我没有调真脚本，而是把脚本里那段 Python **抄进一个临时副本**
（`lintcheck.py`）去跑，副本里我给两条失败路径写了**不同**的措辞：

```
lintcheck.py:7    print(f"FAIL missing '{heading}'"); sys.exit(0)   # 标题缺失
lintcheck.py:12   print(f"FAIL empty '{heading}'");   sys.exit(0)   # 标题在、段内空
```

于是我在 B10 的证据表里写下 witness 一行：「模板 + 三个空锚点 → `FAIL empty
'Acceptance tests'`（非 `missing`）」，并据此在 **WP-24 冻结 Brief** 的交付物与
`Acceptance tests` 段里把它定成必达断言：「断言报的是 `empty` 而**不是** `missing`」。

真脚本从不这么说：

```
dispatch_lint.sh:86   print(f"brief missing section '{heading}'")   # 标题缺失
dispatch_lint.sh:98   print(f"brief missing section '{heading}'")   # 标题在、段内空
```

两条路径打印**同一句** `missing`。脚本里 `empty` 一词只出现在注释
（:67、:128）、内部变量名（`non_empty` :91/95/97、`allowed_empty` :129/135）
和一条**无关**的判据消息（:136 `scope.allowed_paths is empty`）里——
section 检查的两条失败路径**都不**带 `empty`。
用真脚本跑被掏空锚点的 brief，实际输出是
`DISPATCH_LINT_FAIL: brief missing section 'Acceptance tests'`。

**后果链**：副本的自造措辞 → 被当成真 gate 的行为写进 B10 证据表 → 被写进冻结
Brief 的必达断言 → 执行者面对一条**不可能满足**的验收条件（因为 `dispatch_lint.sh`
同时是 forbidden path、零改动项，无法通过改 gate 来满足）。
若执行者选择「照做」，唯一出路是改 gate（越界）或伪造断言（空验证）。

### 为什么是 B9 同族

B9 的形态是：判据通道（`rc != 0` / `grep hit`）与结论（「阻塞」/「有裁决」）之间
存在一条**未被核验的等价假设**。这里的等价假设是「我抄出来的副本 ≡ 真脚本」。
抄的时候语义（两条路径都判失败）确实对了，但**可观测输出**不对——而我恰恰是拿
可观测输出当证据。B10 的证据表里那三行「正面对照 + witness」在结构上是对的，
**通道选错**使其中一行成了虚构。

讽刺之处：WP-24 Brief 自己的陷阱第 4 条写着「**测试不要抄判据**。抄一份 checker
进测试 = 测副本，模板漂移时不报警」。我在**写这条陷阱的同一轮**，用抄来的副本
产出了 Brief 的另一条要求。规则写在纸上不等于作用于写规则的人。

### 执行者的处理（正确，记录为正面样例）

1. 在 `[CONCERNS]` **显式申报**该断言不可达，附真脚本行号与输出，而不是默默跳过；
2. 用等价的三段证据链替代——非空段 → PASS / 删标题 → 红 / 留标题清段内 → 红——
   把「段内非空」那一半判据**单独证明活着**，达成 Brief 的**意图**；
3. 没有为了让字面断言成立去碰 `dispatch_lint.sh`。

裁决 ACCEPT，Brief 之错归编排者。

### 修法（针对编排者自己的工作面）

1. **判据只能来自真脚本**。编排者做前置实测时，若结论要进 Brief 成为断言，
   必须**实际调用**该脚本/命令，把**真实 stdout/stderr 原文**贴进 Brief，
   而不是转述、不是跑副本。抄副本只允许用于**理解语义**，其输出不得进证据表。
2. **Brief 里的负面断言必须给出「谁打印这句话」的行号**。若无法指出真实的
   打印点（file:line），该断言不许写进 Brief。
3. **前置事实表须标注取证方式**。每一行加一列：真实调用 / 副本推演 / 阅读推断。
   只有「真实调用」那一档可以升格为 DoD 必达项。
4. **执行者申报「Brief 有错」时，编排者的第一动作是核 Brief，不是核执行者**。
   本轮若先去质疑执行者，错误会被冻结进仓。

### 待办

- [ ] 把上述 1–3 写进编排者协议（`CLAUDE.md` 的 Dispatch 段或 `AGENTS.md`），
      作为「冻结前自检」的一条；未落地前每次冻结靠人工记性，同 B10 的教训。
- [x] 顺带评估：`dispatch_lint.sh` 两条失败路径共用 `missing` 一句，
      **本身也降低了可观测性**（标题缺失与段内为空无法从输出区分）。
      这是 gate 侧的**可选**改进，不是缺陷；若改，须同步任何依赖该措辞的断言。
      本轮不动（WP-24 已判零改动）。

      **2026-09-16 结论（codex 第二签名撞上同一条，已实测定案）**：
      codex 咨询 WP-24 时把这条判为唯一阻塞项，并要求 `assert "empty" in stderr`
      ——不可达，它是被本 Brief 里我自己那处 B11 错误措辞误导的。
      按修法 1 用**真脚本**实测：对 later 锚点 `Completion definition` 分别做
      「改标题」（走 :86）与「留标题清段体」（走 :98）两种变异，
      两次 stderr **逐字节相同**：

      ```
      DISPATCH_LINT_FAIL: brief missing section 'Completion definition'
      ```

      故**任何对 stderr 措辞的断言都无法区分这两条路径**，这不是用例写得差，
      是可观测性本身缺失。**不改 gate 的替代判据是差分对**：保持
      `## Acceptance tests` 标题恒定，仅增删一行段体 —— 实测
      `清空段体 → rc=2` / `补一行 'x' → rc=0 DISPATCH_LINT_PASS`。
      标题两次都在，`:86` 不可能是原因，红只能来自 `:98`。
      **这条应进模板的 oracle 三项作为第 2 项的写法示例**：当权威判据对两种成因
      打印同一句话时，原因特异 witness 只能由差分对承载，不能由消息断言承载。

---

## B12 · 派发时基线既未落盘、又在提示里写错，零回归判据一度无锚

**发现时间**：2026-09-15，WP-22 交付验收时，由**执行者的 `[CONCERNS] 3`** 指出。
**责任方**：编排者（claude）。
**族属**：与 B9 同族的一个变体——判据（「零回归」）依赖一个**未落盘、未复核**的数字。

### 事实

WP-22 的 Brief DoD 写着「相对基线**零回归**（基线届时由编排者在派发时写入 status）」。
实际：

1. `WP-22.status.json` 的 `evidence` 里**没有** `baseline` 块——我漏了；
2. 我在派发提示里口述了一个基线「583 passed」——**这个数是错的**；
3. 执行者在自己 worktree 的干净树上实测得 `581 passed`，在 `[CONCERNS] 3` 提出
   「疑基线录自集成分支快照，多出 2 个测试」，并改用**同树前后对照**自证零回归。

编排者复核：在 `b72e9c4`（该 WP 的 `dispatch_commit`）起一个 detached worktree
实测 `PYTHONPATH=src python3.11 -m pytest tests -q` → `4 failed, 581 passed, 4 skipped`。
**执行者正确**。交付后 586 = 581 + 5 个新用例，零回归成立。

### 危害

「零回归」是每个 WP 的 DoD 硬项。基线不落盘时，这条判据的锚点只存在于派发提示
（一次性、不可审计）和编排者记忆里；基线写错时，判据会给出**假阳性或假阴性**：
- 若执行者照 583 比，交付 586 会被算成「+3」，而真实是「+5」——两个新用例的存在
  会被悄悄吞掉；
- 反向情形（基线报低）则会把真实回归读成正常。

本轮之所以没出错，**唯一**原因是执行者没照抄我的数字，而是自己测了一遍并申报。
这不是流程的功劳。

### 修法

1. **基线必须落 `evidence.baseline`**，且带 `measured_at_commit`——必须等于
   `git.dispatch_commit`（不是 `base_commit`，B8 同理），以及 `measured_by`。
2. **基线必须在 `dispatch_commit` 上实测**，不能取自集成分支快照或另一个 worktree
   的顺手一跑（本轮 583 就是这么来的）。
3. **`preflight` 应把「`evidence.baseline` 缺失」判为 fail**，让漏录在派发时就被拦住，
   而不是靠执行者事后质疑。当前 `validate_wp_status` 只强制 `evidence.tests` 每项有
   `exit_code`，不强制 baseline 存在。
4. **执行者质疑基线时，编排者第一动作是复测，不是解释**。本轮复测花了 97 秒，
   收益是把一条错判据从仓里拿掉。

### 待办

- [ ] `validate_wp_status` / `preflight` 增加 baseline 必填校验（含
      `measured_at_commit == git.dispatch_commit` 的一致性检查）。与 B8 同一处口径，
      建议合成一个 WP。
- [ ] 回查已交付各 WP 的 status，补齐缺失的 `evidence.baseline`（WP-22 已补）。

---

## B13 · finalize 写回段「落点免疫」被当成「读取也免疫」

**发现时间**：2026-09-15，WP-22 验收时，由**执行者的 `[CONCERNS] 2`** 指出。
**责任方**：编排者（写 WP-22 Brief 前置事实的那份实测）。
**族属**：B9「观测通道选错」——测了 A，结论写成 A+B。

### 事实

WP-22 Brief 的前置事实表把写回面判为「**已免疫，不要改**」，依据是：
`mktemp "$status_file.XXXXXX"` 取路径字符串的 dirname（不解析 symlink），
`mv` 是 `rename(2)`（替换 symlink 本身而非跟随它）——实测写回**落在主区路径**，
worktree 副本未被触碰。该实测本身**正确**。

但写回段是这样的（`finalize_merge.sh:325-348`，本轮 diff=0）：

```
tmp_status=$(mktemp "$status_file.XXXXXX")
python3 - "$status_file" "$tmp_status" ... <<'PY'
with open(src, encoding="utf-8") as fh:      # ← 按路径重新打开、重新解析
    data = json.load(fh)
... data["state"] = "MERGED" ...
mv "$tmp_status" "$status_file"
```

`open(src)` 是**第 N+1 次按路径解析同一个文件**。probe 关掉的是「判定→决策读取」
之间的窗口；「判定→写回读取」之间的窗口**没关**。我实测的是**写到哪里**（落点），
写进 Brief 的结论却覆盖了**读到什么**（内容）。这两件事不是一回事：

- 落点免疫 ⇒ 不会把 MERGED 戳到 worktree 伪造副本上。**已证。**
- 读取免疫 ⇒ 写回时读到的旧 JSON 一定是判定时那一份。**未证，且现在看是假的。**

后果面：攻击者若在 probe 之后、写回之前换入 symlink，`open(src)` 会读到伪造内容，
脚本把**伪造内容 + MERGED 戳**写进 tmp，`mv` 再把它落到**真实主区路径**上。
落点对了，内容被换了——这比落点被换更隐蔽。

（尚未构造 PoC，故记为缺陷而非已证漏洞；`state`/`review.decision` 等决策字段已由
probe 定过，被换的是写回时一并保留的**其余全部字段**。）

### 为什么 WP-22 不该扩范围

Brief 明令写回段 diff 必须为 0 行，执行者按约未动并在 `[CONCERNS] 2` 申报——
处理正确，判 ACCEPT。本条是**Brief 前置事实的缺陷**，不是交付的缺陷。

### 修法（另立 WP）

把写回也收进同一个 fd 面：probe 已经读过整份 JSON，可让它把**整份 data** 交回
（或直接由 probe 所在进程完成「读—改—写 tmp」），写回段不再 `open(src)` 第二次。
`mv` 形态保持（已免疫，不要动）。

### 待办

- [ ] 立 WP：写回段消除按路径重读（复用 probe 已读的内容），`mv` 形态零改动。
- [ ] 先构造 PoC 确认可利用性（probe 后、`open(src)` 前换入 symlink 是否真能改写
      非决策字段），再决定优先级——**不要在没有 witness 的情况下当已证漏洞写进 Brief**
      （B11 的教训）。

---

## B14 · `agentic` CLI 是指向**另一个 worktree** 的 editable 安装，所有 wrapper 判据都跑别人的代码

**发现时间**：2026-09-15，合入 WP-21 后调 `agentic finalize` 时。
**族属**：B7（「不要用 `agentic quality-gate` 自证」）的**根因**。B7 记的是现象，
这条记的是机制——且比 B7 描述的更严重。

### 事实

```
$ which agentic
/Users/admin/.local/bin/agentic          # uv tool，shebang 指向 tools/agentic-loop/bin/python

$ cat .../site-packages/_editable_impl_agentic_loop.pth
/Users/admin/vibe/agentic-loop-main-codex-merge/src
```

即 `agentic` 是 **editable 安装**，源码路径固定指向
`/Users/admin/vibe/agentic-loop-main-codex-merge`——一个**停在 `main`（600c2f1）
的另一个 worktree**，不是当前工作分支。

实测后果（`agentic finalize` 对一份 `APPROVED_FOR_MERGE` 前的 WP-21 status）：

```
$ agentic finalize docs/plans/.../WP-21.status.json
STATUS_INVALID: unknown field git.merged_commit
```

原因：两个树的同一行不同——

| 树 | 行 | 代码 |
|----|----|------|
| `agentic-loop-main-codex-merge`（CLI 实际跑的） | `:67` | `merged_commit_recorded=$(field git.merged_commit)` |
| `agentic_loop`（当前 plan 分支） | `:89` | `merged_commit_recorded=$(field git.merged_commit 2>/dev/null \|\| true)` |

后者是 A12 的修法（WP-19 交付）。CLI 跑的是**未修版**，所以**任何第一次 finalize
调用都必然失败**——`git.merged_commit` 正是该脚本要写的字段，首次调用时不存在。

改用当前树自己的 wrapper 即通过：

```
$ PYTHONPATH=src bash src/agentic_loop/wrappers/finalize_merge.sh <status>
FINALIZE_OK merged_commit=4a3e6f6ea91266f13035372135d2489f79ec8935
```

### 危害面（比 B7 记的大）

B7 只说 `quality-gate` 自证不可信。实际上**每一个** `agentic` 子命令都受影响：
`preflight`、`dispatch-lint`、`quality-gate`、`finalize`、`lock`、`health`、
`redispatch`、`gate`。这意味着：

1. **判据版本漂移不可见**。当前分支修好的判据（A12、A29、A34、A35…）在 CLI 上
   全部不生效；CLI 通过/拒收反映的是 `main` 在某个时刻的行为。
2. **方向双向错**。既可能「当前分支已修但 CLI 报旧错」（本轮，噪声），
   也可能「当前分支引入回归但 CLI 照旧放行」（**危险**，假绿）。
3. **`agentic health` 也在其中**。它的 `FROZEN_<N>m` 判据同样跑别人的代码。
4. 编排者协议（`CLAUDE.md`）通篇写 `agentic preflight <status>`、
   `agentic finalize <status>`——**协议本身在指导使用一个错误的通道**。

本轮之所以只造成噪声而非放行，纯属运气：`main` 的版本恰好比当前分支**更严格**
（少一个守卫 → 更容易失败）。反向情形不会有任何提示。

### 修法

1. **判据必须来自被判定的那棵树**。凡对某分支/worktree 做判定，一律
   `PYTHONPATH=src bash src/agentic_loop/wrappers/<script>.sh`（或
   `PYTHONPATH=src python3.11 -m agentic_loop.<mod>`）直跑该树，不走 PATH 上的 `agentic`。
2. **协议要改**。`CLAUDE.md` / `AGENTS.md` 里所有 `agentic <sub>` 的示例须改成
   直跑形态，或明确写「`agentic` 仅用于与被判定树无关的操作」。
3. **给 CLI 加自检**：启动时比对「editable 源码路径」与「`resolve_paths --root
   main_repo` 解析出的仓根」，不一致则**打印醒目告警**（不宜直接 fail——可能有正当
   的跨仓用法），把版本漂移变成可见事实而非静默假设。
4. 这条与 B11/B13 是同一族的第三个实例：**判定通道 ≠ 被判定对象**。
   B11 是「副本 vs 真脚本」，B13 是「落点 vs 内容」，B14 是「另一棵树 vs 本棵树」。

### 待办

- [ ] 立 WP：给 `agentic` 加源码路径 / 主仓根一致性自检告警（修法 3）。
- [ ] 改协议：`CLAUDE.md` / `AGENTS.md` 的 `agentic <sub>` 示例改直跑形态（修法 2）。
- [ ] 回查：本迭代此前所有「`agentic preflight` 通过 / `dispatch-lint` 通过」的结论，
      标注它们实际由 `main` 的快照判定，必要时用当前树重跑。**这一条影响已交付
      各 WP 的证据可信度**，优先级高于前两条。

---

## B15 · WP-22 的 probe 传输协议可被字段内容注入，绕过合入门禁（已证，PoC 可复现）

**级别**：P0（合入门禁被绕过；WP-22 引入的回归）
**发现者**：codex 第二签名（WP-22 咨询 P0-2），编排者据其提示写出 PoC 证实并加重
**状态**：WP-22 已因此转 `CHANGES_REQUESTED`

**缺陷**：`finalize_merge.sh` 的 probe 用 `key<TAB>value` 单行文本把 20 个字段
交回 bash，消费端是：

```bash
while IFS=$'\t' read -r probe_key probe_value; do
  [[ -n "$probe_key" ]] && printf -v "$probe_key" '%s' "$probe_value"
done <<< "$probe_fields"
```

`render()` 不转义换行（`str(value)` 原样返回），因此**任何字符串字段的内容里的
换行都会被当成新的一行 `key<TAB>value` 解析，成为一次变量赋值**。可选字段在
必需字段**之后**发出，所以注入行可以覆盖先前已正确读出的任一变量。

**PoC（已实测，非推演）**：`consult.override.justification` 写

```
looks fine\nbranch\tfeature/decoy
```

`validate()` 对此**全绿**（它不约束 justification 的内容）。真脚本运行后：

```
FINALIZE_OK merged_commit=c5e5b55e...     rc=0   state -> MERGED
```

——而 `git.branch` 声明的 `feature/real` **从未合入 base**。合入检测
（`merge-base --is-ancestor`）被绕过，因为它检查的是被覆盖后的 `feature/decoy`。

**是回归，不是既有问题**：派发点 `b72e9c4` 的旧版对同一份 status 拒收：

```
FINALIZE_FAIL: merge not detected (branch tip c1612103... is not an ancestor of base c5e5b55e...)
```

旧版每个字段一次 `field` 子进程调用，返回值经命令替换赋给单个变量，换行是惰性的。
WP-22 把「一次调用一个值」换成「一段文本多行赋值」，换行由此获得语法意义。

**根因（缺陷族）**：与 B11/B13/B14 同族——**判据的通道变了，判据本身没变**。
我逐字段核验了 probe 与 `--field` 的**渲染**等价（值相同），却没核验**传输**
（承载值的通道换了）。等价性核验必须覆盖「值 + 通道」两面。

**修复方向**（留给 WP，不在本轮修）：
1. probe 与 bash 之间改用无歧义编码（NUL 分隔、或 JSON + `jq`/python 单点解析）；
2. 赋值端**白名单字段名**，拒绝任何不在 `REQUIRED_FIELDS`/`OPTIONAL_FIELDS` 里的 key；
3. 与 B13 一并处理：写回段读的旧 JSON 也应来自 probe 那一次 `open()`（`raw` 传递），
   而不是按路径重读。

**证据**：PoC 工程 `/Users/admin/.claude/jobs/8a8bf01e/tmp/poc-b15b/`；
裁决记录 `WP-22-consult-codex-verdict.json`。

## B16 · 冻结 Brief 的 rev 路径写在 status 里，门禁却按固定命名去 lint 另一个文件（rev2 冻结实际无门禁）

**发现于**：2026-09-16，准备把 WP-22 rev2 派发给执行者时。

**事实**（真脚本实测，非读码推断）：

`dispatch_lint.sh:60` 按**固定命名约定**算 brief 路径，完全不读 `evidence.brief.path`：

```bash
brief_file="$iterations_dir/$iteration_id/${work_package_id}-brief.md"
```

`redispatch.py:493` 同样硬编码同一约定，且它是**喂给执行者 prompt 的那一份**：

```python
brief_path = iteration_dir / f"{work_package_id}-brief.md"
```

实测：WP-22 的 `evidence.brief.path` 已冻结为 `WP-22-brief-rev2.md`，
`bash -x` 抓到门禁实际 lint 的却是

```
+ brief_file=/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-22-brief.md
+ echo DISPATCH_LINT_PASS
```

**差分对（原因特异性由用例承载，非 fixture）**：把 `evidence.brief.path`
改指 `DOES-NOT-EXIST.md`（sha256 一并置零）——门禁仍 `DISPATCH_LINT_PASS rc=0`；
同一份临时 status 只把 `work_package_id` 换成 `WP-999`——门禁立刻
`DISPATCH_LINT_FAIL: brief not found at .../WP-999-brief.md rc=2`。
两次运行只差一个输入，红只可能来自固定命名那条路径，故证明：
门禁读的是 `work_package_id`，**从不读 `evidence.brief.path`**。

**后果（两层，均已证）**：
1. **rev 冻结没有门禁**。所有 `-revN` 冻结的 Brief 都不在 lint 面内；
   门禁 PASS 只证明**被 supersede 的 rev1** 三锚点齐全。本迭代命中三例：
   WP-19（claimed rev5）、WP-22（claimed rev2）、WP-21（`evidence.brief` 整块缺失，
   但门禁照样 PASS）。
2. **`redispatch` 会把过期 Brief 喂给执行者**。重派读的也是 `WP-N-brief.md`，
   即执行者可能照 rev1 施工，而我以为它在照 rev2 施工。

**且 `evidence.brief.sha256` 全仓无人校验**：`grep -rn brief src/agentic_loop`
只有上述两处硬编码 + 无关命中，没有任何一处把 `sha256` 与文件内容比对。
「冻结锚定」目前是纯文档承诺，无可执行判据。

**根因（缺陷族）**：与 B11/B13/B14/B15 同族——**判据的通道变了，判据本身没变**。
我把冻结产物换了个文件名（rev2），却没核验消费该产物的通道是否跟着走；
门禁的「PASS」和我心里的「rev2 已过闸」指的根本不是同一个文件。

**修复方向**（留给 WP，不在本轮修）：
1. `dispatch_lint.sh` / `redispatch.py` 统一从 `evidence.brief.path` 取路径，
   固定命名只作缺省回退；两处必须来自**同一个**解析函数（§5.3 口径单点）。
2. 校验 `evidence.brief.sha256` 与文件内容一致，不一致 fail-closed —— 让
   「冻结」变成可执行判据。
3. `evidence.brief.path` 缺失时（WP-21 那种）应判 FAIL，而非静默走约定。
4. 回查：凡 `evidence.brief.path` 与固定命名不一致的历史 WP，其
   `DISPATCH_LINT_PASS` 证据须重新标注为「lint 的是 rev1」。

**本轮规避**：WP-22 rev2 派发前，先让固定命名那份路径承载 rev2 内容
（见 WP-22.status.json 的 `evidence.brief.gate_alignment`），
不依赖尚未修好的门禁行为。

## B17 · `preflight` 判的是**工作树里那份 status 快照**，不是编排者刚冻结的主仓 live 状态

**发现于**：2026-09-16，B16 规避后跑 WP-22 rev2 派发前门禁时。

**症状**：`preflight` 打印 `PREFLIGHT_PASS ... state=DISPATCHED`，而主仓 live
状态文件此刻是 `state=DRAFT`——`DRAFT` 根本不在可执行集
（`preflight.sh:70` 只放行 `APPROVED|DISPATCHED|IMPLEMENTING|CHANGES_REQUESTED`）。
两者不可能同真，说明它读的不是同一个文件。

**根因**：`preflight.sh:9` 直接 `status_file=$1`，相对路径按**当前工作目录**解析。
而 §4.1 要求 preflight 必须在**次级工作树**内运行（`preflight.sh:39` 的
`PREFLIGHT_FAIL: implementation must run in a secondary worktree`），
于是相对路径必然落到工作树自己那份 git 追踪副本上。
对比 `dispatch_lint.sh:26-29` —— 那里显式用 resolver 求主仓根并 `${main_root:+$main_root/}$status_arg`
把相对路径钉到主仓。**同一仓里两个 wrapper 对同一个参数用了两种解析口径**（违 §5.3）。

**差分对（真脚本，原因特异性由用例承载）**：
- 控制 A：工作树副本 `state=DISPATCHED`，主仓副本 `DRAFT` → `PREFLIGHT_PASS ... state=DISPATCHED`
- 控制 B：**只**把工作树副本改成 `BLOCKED`，主仓副本一字不动 → `PREFLIGHT_FAIL: state BLOCKED is not executable`
- 两次运行主仓副本恒为 `DRAFT`，红绿只随工作树副本翻转 → 判据读的是工作树快照，主仓 live 状态从不参与。

**后果（比 B16 更重）**：
1. **派发门禁形同虚设**。工作树副本是 commit 时的历史快照，编排者冻结/改写 live
   状态（state、scope.allowed_paths、risk、evidence.brief）后，preflight 全部看不见。
   本例：rev2 冻结把 state 打回 `DRAFT`（未就绪），preflight 却按上一轮 commit 里的
   `DISPATCHED` 放行——**我差点在「门禁已过」的错觉下派发**。
2. **scope/risk 判据同样跑偏**。同一份文件里的 `scope.allowed_paths`、`risk.*`
   也来自快照，故越界与风险边界的判定用的都是旧口径。
3. **`evidence.brief.path` 叠加 B16**：工作树副本的 brief.path 还是 rev1
   （`WP-22-brief.md`），与主仓 rev2 记录不一致，两个缺陷叠加后
   「lint 过的 brief」与「冻结的 brief」可以完全无关。

**根因（缺陷族）**：与 B11/B13/B14/B15/B16 同族——**判据的通道变了，判据本身没变**。
`preflight` 的判据文本（可执行状态集）一直正确，但它取状态的通道从「主仓唯一事实源」
悄悄变成了「本分支的历史快照」；而 §4.1 明写 status 是主仓 live 协调面、
只有编排者维护，工作树里那份按定义就是过期的。

**修复方向**（留给 WP，不在本轮修）：
1. `preflight.sh` 的 `status_file` 解析改与 `dispatch_lint.sh:26-29` 同源：
   相对路径一律钉到 resolver 求出的主仓根；两处必须调**同一个**解析函数，不各写一份。
2. 加自检：若参数解析出的路径落在当前工作树内（`path_is_in_worktree` 已有权威判据），
   直接 fail-closed —— status 只能读主仓那份。
3. 回查：所有 `PREFLIGHT_PASS` 历史证据都须重新标注「判的是工作树快照」；
   凡快照与当时 live 状态不一致的，该次放行不构成门禁证据。
4. 与 B16 合并考虑：status 与 brief 两条读取面都要统一到主仓 + 单点解析。

**证据**：上述差分对可复现；工作树 `/Users/admin/vibe/wp22-finalize-toctou` 已还原干净
（`git status --porcelain` 空）。

## B14 补充实测（2026-09-16）：`agentic` 不是 editable 安装，而是**冻结副本**，且落后活树 26/23/191 行

登记 B14 时我的描述是「指向另一棵 worktree 的 editable 安装」。回查（任务 #13）后
更正：**比那更糟，它根本不是 editable**。

```
/Users/admin/.local/bin/agentic  ->  shebang /Users/admin/.local/share/uv/tools/agentic-loop/bin/python
agentic_loop.__file__            =  …/uv/tools/agentic-loop/lib/python3.12/site-packages/agentic_loop/__init__.py
```

site-packages 下是**实体文件副本**（无 `.pth`、无 `__editable__*` finder），
即 `uv tool install` 时的快照，之后活树怎么改都不会跟随。
（顺带：该路径的 `git rev-parse --show-toplevel` 落到 `/Users/admin`、
分支 `feature/v3-skill-standardization` —— 一个与本项目无关的仓，
所以任何「按 git 事实自证」的判据在该副本里跑都会得到别人的答案。）

**冻结副本与活树的差异（`diff -rq`，排除 `__pycache__`）**：

| 文件 | 差异行数 | 说明 |
|---|---|---|
| `wrappers/finalize_merge.sh` | 26 | 缺 WP-21 的 A29 fail-closed 注释（活树有、副本 0 处） |
| `wrappers/preflight.sh` | 23 | —— |
| `gate/__init__.py` | 191 | 权威判据 `path_is_in_worktree` 所在文件 |
| `adapters/codex.py` | 差异 | 第二签名的取数通道 |
| `plan_cmd.py` | 差异 | —— |
| `gate/report.py` | **副本里根本没有** | 活树新增文件 |

即：`agentic preflight` / `agentic finalize` / `agentic dispatch-lint` 跑的是
一份落后活树上百行、且 `gate/__init__.py`（§5.3 单一权威判据的物理位置）都不同的代码。

**与 B16/B17 合看**，本迭代的门禁读取面共有三处走偏，且是同一族：

| 缺陷 | 判据读错了什么 | 后果 |
|---|---|---|
| B14 | 读**冻结副本的代码** | wrapper 判据本身是旧的 |
| B16 | 读**固定命名的 brief** | rev 冻结不在 lint 面内 |
| B17 | 读**工作树快照的 status** | state/scope/risk 全用旧口径 |

三者叠加的最坏情形：用旧代码、按旧 brief、判旧状态，然后打印 PASS。
本轮 WP-22/WP-24 的门禁我已全部改为「直跑活树脚本 + 主仓绝对路径」规避，
但历史上凡以 `agentic <sub>` 输出作为证据的结论都须重新标注。

**回查结论**：本迭代 status 里记录的 wrapper 证据，凡命令形态写作
`agentic <sub>` 的，都不构成活树证据；写作
`PYTHONPATH=src bash src/agentic_loop/wrappers/<x>.sh` 或
`docs/agentic/tools/<x>.sh` 的，跑的是活树，证据有效。
（本轮 WP-22/WP-24 的 SCOPE_OK、zero-diff、preflight 均属后者。）

**修复方向**（并入任务 #14 的 WP）：
1. `agentic` 启动时自检：`agentic_loop.__file__` 是否落在**当前主仓**的 `src/` 下；
   不是则显著告警或 fail-closed（至少在 dogfood 场景）。
2. 协议示例一律改为直跑活树脚本形态，不再示范 `agentic <sub>` 作为验收证据。
3. 把 `uv tool install` 改为 editable/`--with-editable`，或在仓库 README 明写
   dogfood 必须用活树路径调用。

### B14 回查结果（任务 #13，已完成，2026-09-16）

扫描全部 `docs/plans/*/WP-*.status.json` 的 `evidence.tests[].command`，
命令形态含 `agentic <sub>` 的**只有 1 条**：

- `WP-01.status.json` → `agentic quality-gate WP-01.status.json`（exit_code 1）

该条**不构成需要推翻的结论**，两个独立理由：

1. **同一检查已有活树形态的复跑**，就在同一份 status 的下一条：
   `PYTHONPATH=src bash src/agentic_loop/wrappers/quality-gate.sh docs/plans/…/WP-01.status.json`
   （rebase 后复跑，STATUS_VALID、scope 通过、4 failed/502 passed/4 skipped）。
2. **`wrappers/quality-gate.sh` 在冻结副本与活树之间逐字节相同**
   （`diff -q` 无输出），故即便只有 `agentic` 那一条，其判据代码也未偏。

其余所有 wrapper 证据的命令形态都是
`PYTHONPATH=src bash src/agentic_loop/wrappers/<x>.sh` 或 `docs/agentic/tools/<x>.sh`，
即直跑活树，证据有效。

**结论**：B14 未污染本迭代任何已合入结论；风险是前瞻性的——只要协议示例仍示范
`agentic <sub>`，下一次就可能踩中（`gate/__init__.py` 差 191 行、
`gate/report.py` 副本里根本不存在）。故任务 #14 的 WP 仍须做，
优先级是「防再犯」而非「补救已发生的误判」。

## B18 · 把「值」搬进 argv 换掉「按路径重读」，顺手引入了一条原先不存在的 ARG_MAX 上限

**同族**：与 B15 同一根因的**反向面**。B15 是「值经文本通道走私成了记录分隔」；
B18 是「为修 B13 把整份 JSON 搬上 argv，通道本身有了长度上限」。
判据没变（还是那份 JSON），通道又变了一次。

**发生位置**：`src/agentic_loop/wrappers/finalize_merge.sh:408`（WP-22 rev2 `b216b50`）

rev2 为关掉 B13（写回段按路径重读旧 JSON），把 probe 单次 `O_NOFOLLOW open()`
读到的原始字节作为 `status_raw` 记录传回 bash，写回段改为：

```bash
python3 - "$tmp_status" "$merged_commit" "$updated_at" "$status_raw" <<'PY'
data = json.loads(raw)
```

**这个方向是对的**（判定与写回读同一批字节，窗口关闭），但整份 status 从此走 argv。

**实测（编排者，2026-09-16，`/Users/admin/.claude/jobs/8a8bf01e/tmp/argv_size.py`）**：

| status 大小 | rc | state 事后 | 落章 | 备注 |
|---|---|---|---|---|
| 1322 B | 0 | MERGED | 有 | 正常 |
| 603913 B | 0 | MERGED | 有 | 2000 条 evidence 全部保留 |
| 1811913 B | 1 | APPROVED_FOR_MERGE | 无 | `python3: Argument list too long` |

- `getconf ARG_MAX` = 1048576（本机）
- 本仓最大真实 status = 15129 B（`WP-18.status.json`），**约 70 倍余量**

**性质判定**：**fail-closed**，不是静默截断 —— 超限时状态不变、不盖章，
这是安全的一侧。但两点不足：

1. 诊断是**裸的 bash 报错**，不是 `FINALIZE_FAIL:` 行，与脚本其余全部拒收路径的
   口径不一致；调用方按 `FINALIZE_FAIL` 抓错会漏掉这一类。
2. 上限**原先不存在**（按路径重读没有长度限制），属修复引入的新约束，
   未在任何地方声明。

**不阻断 WP-22 合入**（70 倍余量 + fail-closed），已记入
`WP-22.status.json` 的 `evidence.remaining_risks`。

**建议修法**：`status_raw` 改走**文件描述符或临时文件**（probe 已经在写临时文件了，
再复用一次即可），而不是 argv；同时补一条 `FINALIZE_FAIL: status too large for
the write-back transport` 诊断。—— 注意这条修法本身又是一次通道更换，
按纪律须给差分对。

## B19 · fixture 的**无关格式选择**（`indent=2`）让用例改由分层守卫转红，遮住了它本该复现的突破

**同族**：B9/B11 的变体。判据在、用例在、红也转了 —— 但**红的原因**不是用例声称的那个。

**发生位置**：`tests/test_finalize_merge_toctou.py::test_newline_injection_cannot_override_branch_b15`
（WP-22 rev2 `b216b50`）

**实测（编排者变异自证 2，2026-09-16）**：把 rev2 的传输**只**回退成换行分记录
（probe 侧 `\0` → `\n`，bash 侧 `read -r -d ''` → `read -r`），
该用例转红 —— 但红在 `assert "merge not detected" in result.stderr` 上，
实际 stderr 是 `FINALIZE_FAIL: probe record without field separator`。
即它是被**分层防御里的「记录无 TAB 分隔」守卫**拦下的，**没有复现伪造 OK**。

**原因**（实测）：`_write_status()` 用 `json.dumps(data, indent=2)`，
于是 `status_raw` 天然多行；换行传输下，`status_raw` 的第二行先被当成一条无 TAB 的
记录，触发该守卫，控制流在到达伪造记录之前就退出了。

编排者用**紧凑 JSON** 的独立 PoC 在同一变异下确认 A/C/E 三种载荷**仍可完整复现突破**
（`rc=0`，未合入分支盖上 decoy 的真 merge commit），故用例的钉住能力由外部证据补足。

**教训**：fixture 里一个看似与判据无关的格式参数（`indent=2` vs 紧凑），
决定了变异下**哪一层守卫先响**。变异自证转红了，不等于转红的原因是你想钉的那一层；
**要核对红的那一行断言是不是你声称的 witness**。

> 执行者如实上报了这一点（`[CONCERNS]` 里明写「未复现伪造 OK，因为多行的 status_raw
> 记录先触发了该守卫」），没有把它写成干净的击杀 —— 这是正确的报告行为，
> 缺陷归 fixture 设计，不归诚信。

**建议修法**：补一条紧凑 JSON fixture 的用例（同一载荷、`json.dumps` 无 `indent`），
让「仅传输编码回退」这一变异有一条能复现突破的用例钉住。已记入
`WP-22.status.json` 的 `evidence.remaining_risks`。

---

## B20 · 语义锚点钉住的是**标签词**，不是它命名的**可操作子句**（WP-25 实测）

**发现者**：codex（第二签名咨询中，它崩溃前最后一个成功探针）；编排者独立复现。

**位置**：`tests/test_orchestrator_protocol_disciplines.py` 的 `DISCIPLINE_ANCHORS`
（WP-25 commit `359cb1a`）。

```python
DISCIPLINE_ANCHORS = {
    "criteria_sourcing": ["authoritative source itself", "retype"],
    "negative_assertion": ["file:line", "differential pair"],
    "read_face_pinning": ["PYTHONPATH=src bash src/agentic_loop/wrappers/", "historical snapshot"],
}
```

**实测**：保留全部六个锚点字串不动，只做两处删除 ——

1. 纪律 2 的方法整句：
   `use a differential pair instead: hold everything else constant, flip exactly one
   input, and require the red/green verdict to flip with it.`
   → `use a differential pair instead.`
2. 纪律 3 的 rev 改名子句整段删除：
   `When a frozen artifact is renamed (-revN), verify that every consumer channel
   follows the new name (a gate that reads a fixed filename does not).`

结果：`pytest tests/test_orchestrator_protocol_disciplines.py -q` → **9 passed**，全绿。

**为什么这是缺陷而非风格问题**：本 WP 的主题恰恰是「判据来源」与「负面断言不得空验证」
（B11 / B19）。锚点只钉住了纪律的**名字**，没钉住它的**做法**。一份被掏空 how 的模板
仍然会渲染进每个接入项目、仍然通过自己的守卫 —— 纪律以口号形态到达项目，方法丢失。
这是 A19/B10「锚点缺失」的**下一层**：锚点存在，但钉的位置不承重。

**教训**：语义锚点的选取要落在**可操作子句**上，而不是该子句的标题词。
判断标准：假想有人把这段话压缩成一句口号，你的锚点还在不在？在，就说明没钉住。

**修法**（WP-25 rev2）：为两处可操作子句各补语义锚点 ——
差分对方法（恒定其余 / 只翻一个输入 / 红绿随之翻转）与 rev 改名的消费通道核验；
仍用短语锚点，不锁整段措辞（避免反向踩 B10 的脆断言）。

> 关联：本条与 B10（锚点缺失）、B11（判据来自副本）、B19（红的原因未必是你钉的那层）
> 同属「断言看起来成立、实际没钉住判据」这一族。

---

## B21 · 回退分支在校验之前就 `return`，于是「声明了 sha256」被静默跳过（WP-26 实测）

**位置**：`src/agentic_loop/wrappers/dispatch_lint.sh`（WP-26 提交 `0a12bed` 引入的内联
python 解析器）。`evidence.brief.path` 缺失时走固定命名回退，该分支直接
`print("BRIEF_OK")` + `SystemExit(0)`，而 sha256 校验块在其后，永不执行。

**实测**（WP-26 工作树，`state=DRAFT` 的 status 临时副本）：

| status 的 `evidence.brief` | dispatch_lint 裁决 |
|---|---|
| `{"sha256": "0"*64}`（故意写错，无 `path`） | `DISPATCH_LINT_PASS` rc=0 |
| 同一个错 sha256 + 正确 `path`（对照） | `DISPATCH_LINT_FAIL: brief sha256 mismatch: computed=a84d7440… declared=000…` rc=2 |

**为什么是缺陷而非风格**：WP-26 冻结 brief 的陷阱注 4 写明
「sha256 的失败必须 fail-closed。算不出（文件读不到、权限）也要拒收，不得跳过」，
交付物 2 写明「`evidence.brief.sha256` 存在时**必须校验**」。声明了却不校验，
是 brief 判据的直接反面。

**同一提交里的对照实现是正确的**：`redispatch.py` 的 `_brief_content()` 把
`if declared_sha:` 放在 declared/fallback 分支**之后**，两条路径都校验。
实测同一形态（错 sha256、无 path）：

```
redispatch:    refused -> brief sha256 mismatch: computed=e3428210… declared=000…
dispatch_lint: DISPATCH_LINT_PASS rc=0
```

即**两个消费者对同一 status 给出相反裁决**，而 brief 交付物 3 要求
`redispatch.py`「同样以 `evidence.brief.path` 为权威」「同口径」。
口径分裂本身独立于 fail-closed 那条，是第二重违规。

**为什么一整轮没被发现**（含编排者自己的验收）：19 条用例只覆盖
「`path` 与 `sha256` 同时存在」。缺失维度不是断言写错，而是**组合没被枚举**——
两个可选字段有四种在场组合（都无 / 只有 path / 只有 sha256 / 都有），
用例只走了两种。编排者第一轮验收测了三种拒收方向（路径不存在、`../` 逃逸、
sha256 不匹配），全部落在「path 在场」这一半。

**教训**：可选字段的守卫必须按**在场组合**枚举，不是按「拒收原因」枚举。
按原因枚举会让「某原因在某组合下根本到不了」这种漏洞整齐地落在覆盖之外。

**修法**（WP-26 rev2）：把 sha256 校验移出分支（或在回退分支内同样校验），
使其只依赖 `sha256` 在场、与 `path` 是否在场无关；并补
「无 `path`、有错误 `sha256` → 必须 FAIL」的用例，其正向对照为
「无 `path`、有正确 `sha256` → PASS」。

> 关联：与 B19（红的原因未必是你钉的那层）、B20（锚点钉不住语义）同族，
> 但这一条的失效面是**覆盖的形状**，不是断言的强度。

---

## B22 · 判定面与消费面分离：拒收判据只 open 一次，后续消费各自 re-open（WP-27 观察）

**位置**：`src/agentic_loop/wrappers/preflight.sh`（WP-27 提交 `a3264c0` 之后）。
`$status_file` 被独立打开 **9 次**：`:40` 的工作树探针、`:56` 校验、
`:58`/`:59`/`:60` 三次 `--field`、`:111` 的 `git ls-files`、`:120` 转交
`dispatch_lint.sh`、`:134`/`:135` 两次 `--field`。每次各自 re-resolve 路径字符串。

**已确认 fail-closed 的一路**：主仓路径本身是指向工作树副本的静态 symlink 时，
`path_is_in_worktree` 解析后判 `WORKTREE`，被 `:47` 拒收（实测：
main `state=APPROVED` / worktree `state=BLOCKED`，探针返回 `WORKTREE`）。
即「一开始就是 symlink」这一形态不漏。

**残留面**：探针通过之后路径被换掉，则判定与消费落在不同快照上；
不同字段之间也可能来自不同快照。仓内 `finalize_merge.sh:54` 已按 A34 把
「判定 + `os.open(O_NOFOLLOW)` + 读取 + 校验 + 取字段」收进**一次** open。

**定级：非阻塞**。理由三条：
1. WP-27 冻结 brief 只要求复用 `finalize_merge.sh` 的**拒收语义**
   （陷阱注 2：「工作树拒收语义抄 `finalize_merge.sh` 的 `WORKTREE` 分支」），
   从未要求复用 A34 的读取快照；brief 全文不含 TOCTOU/A34/单次 open 的要求。
   按未写进冻结判据的标准驳回，等于让判据在执行后长出来 —— 这正是 B16 一族的反面错误。
2. preflight 在**派发前**由编排者调用、路径由编排者给出，与 finalize 的处境
   （合入后写回、路径来自更长的链路）blast radius 不同。
3. 第二签名（codex）把它读成了 brief 要求，这一点超出冻结判据；结论记录分歧，
   不据此驳回。

**处置**：单独立 WP 收口（与任务 #7/A34 同族），不塞进 WP-27 返工。

**教训（对编排者）**：同族缺陷在一处修好之后，其余读取面**不会**自动继承。
A34 在 `finalize_merge.sh` 收口时，没有机制把「还有哪些 wrapper 是多次 open」
登记成待办 —— 于是新写的 WP-27 又长出一处。这是任务 #23
（学习回边机械化）要覆盖的形状：新 brief 的 DoD 应被强制核验
是否覆盖了与其 `allowed_paths` 相交的既有缺陷。

## B23 · 冻结者自己漏段：rev2 正文丢掉了 rev1 有的**门禁锚点段**（WP-25 实测）

**位置**：`docs/plans/2026-09-13-parallel-throughput/WP-25-brief-rev2.md`（冻结时刻的版本，
sha256 `ebf8e12c…`）。

**现象**：该 rev2 只写了中文的 `## 范围`，丢掉了 rev1 有的英文段
`## Allowed and forbidden paths`。而活树 `dispatch_lint.sh:66-104` 的 section 判据要求三个
**英文**锚点段同时在场且非空：

```
required = ["Acceptance tests", "Allowed and forbidden paths", "Completion definition"]
```

**实测**（把该判据 heredoc 按行号原文切片直跑，B11 修法 1）：

| 输入 | rc | 输出 |
|---|---|---|
| `WP-25-brief-rev2.md`（冻结版） | 0 | `brief missing section 'Allowed and forbidden paths'` |
| `WP-25-brief.md`（rev1） | 1 | 无输出（通过） |
| `WP-26-brief-rev2.md` / `WP-27-brief-rev2.md` | 1 | 无输出（通过） |
| `WP-20-brief.md`（已知坏样本，区分力对照） | 0 | `brief missing section 'Acceptance tests'` |

即：同一批冻结的三份 rev2 里，**只有 WP-25 那份**漏了段。这不是执行者的问题，
是编排者自己在 re-freeze 时把中文小标题当成了那段的替代品。

**为什么能漏掉**：rev2 的写法是「先列 rev1 已核验通过不要动的部分，再写增量」，
于是那些**只服务于门禁、对人类读者冗余**的英文段落最容易在重写时蒸发——它们在人眼里
是重复的（中文「范围」已经说过了），在门禁眼里是唯一判据。

**与 B16 的关系**：B16 是「门禁不读 status 声明的路径」，所以本缺陷在 B16 修好之前
**不会被门禁抓到**——门禁去读固定命名的 `WP-25-brief.md`（rev1，有那段，能过），
声明的 rev2 完全不参与。两个缺陷叠加的结果是：一份过不了门禁的 brief 可以顺利派发，
而且派发时门禁还会给出 PASS。

**处置**：补回该段（与中文段的反引号路径集合做差为空集，避免制造第二口径），
sha256 由 `ebf8e12c…` 变为 `9d19fbe7…`，status 的 `evidence.brief` 同步重指，
旧值留痕在 `evidence.brief.superseded_sha256`。纠正发生在派发之前，无执行者读过旧版。

**教训（可机械化）**：冻结前必须用**判据本身**（原文切片，不 retype）跑一遍待冻结的
brief，而不是靠人眼比对。这条已并入任务 #23（学习回边机械化）：`dispatch_lint` 应当
在 brief 冻结时刻就能被调用，而不是只在派发时刻。

## B24 · 第二签名的**诊断正确、但其提议的判据被实测证伪**（WP-26 rev2 实测）

**背景**：codex 对 WP-26 rev2 判 REWORK，唯一阻塞项是交付物 4 的断言强度：

```python
stderr.count("DISPATCH_LINT_FAIL:") == 1   # 现状
```

它指出这不能排除额外的非 token 输出，并**提议**改为
`len(stderr.splitlines()) == 1` 且首行以 token 开头。

**诊断部分成立**：该断言确实没有钉住 stdout 为空、也没钉住 token 的位置。

**但提议的判据被实测证伪**。构造一份 `state` 与 `review.decision` **同时**非法的 status，
活树脚本实测：

```
rc=2
stderr 第 1 行: DISPATCH_LINT_FAIL: STATUS_INVALID: invalid state: 'NOT_A_STATE'
stderr 第 2 行: STATUS_INVALID: review.decision is invalid: 'NOPE'
token 计数: 1
stdout: 0 行
```

这是 validator **多错并报**的正当续行诊断——正是 codex 举的「unexpected diagnostic」形状，
但它是合法输出。按行数判会把这条正当路径判红。

**编排者处置**：取其关切、弃其形式。加固为三条并存——stdout 为空 + token 计数恰 1 +
`stderr.splitlines()[0].startswith("DISPATCH_LINT_FAIL:")`，并新增一条「多错并报」用例，
把「不得按行数判」这条纪律钉进测试，防止后人照原提议改回去。
阻塞级别不成立（未写入判据、且其具体形式被证伪），故不 re-freeze，以同一 rev2 brief
派发最小加固补丁。

**教训**：审核者的 finding 与其 prescription 是**两个独立的断言**，只有前者是从证据推出的。
读不到运行时（只读沙箱）的审核者在「缺口在哪」上可靠，在「换成什么判据」上没有经过任何
真实输入。凡是带 prescription 的 finding，都要把 prescription 对**当前全部通过的输入**
跑一遍再采纳，并把证伪输入留痕在 status 里，否则同一形式会被反复提出。

**与 B22 同一纪律**：以未写入判据的标准驳回 = 让判据在执行后生长（B16 家族错误）。
区别在于：B22 是编排者不接受 codex 的阻塞级别**且不接受其关切**（另立 WP）；
本条是不接受级别**但接受关切**（同 rev 内加固）。两者都必须把分歧原文留在 status 里。

---

## B25 · 用「关切的一部分」冒充「关切的全部」：加固只约束续行的**起点**，没约束续行的**内容**（WP-26 加固补丁实测）

**形状**：审核者指出「`count(token)==1` 不能排除额外的非 token 输出」。编排者把这条关切
落成三条不变量——stdout 为空 + token 计数恰 1 + **首行**以 token 开头——自评「已覆盖」，判 ACCEPT。
第二签名复签时指出：这三条**仍然放过**关切的本体。实测证实：

```python
P(stdout="", stderr="DISPATCH_LINT_FAIL: brief sha256 mismatch\nunexpected diagnostic\n")
# -> PASSES helper：token 恰 1 次、位于首行、stdout 空
```

关切是「续行**内容**不受约束」，而我只约束了续行的**起点**（首行必须是 token）。
「首行是 token」与「只有 token 行」是两个不同的断言，我用前者结了后者的账。

**同批次第二条（同源）**：`stdout.strip() == ""` 与它自己 docstring 写的 "stdout is empty"
不是同一件事——放过 `" "`、`"\n"`。判据与其自我描述不符，且我写这条 docstring 时没测过纯空白输入。

**为什么两轮都是我先判绿**：B21 是我按「拒收原因」枚举而漏了「在场组合」的另一半；
本条是我按「关切的关键词」枚举而漏了关切的谓语。两次的共性是：
我用一个**与关切同话题**的断言替代了**与关切同外延**的断言，然后停止检查。
自检问句应当是「我这条断言的反例集合，是否等于对方指出的反例集合」——
而不是「我这条断言是否谈论了对方谈论的东西」。

**与 B24 的关系（同一 WP、相邻两轮、结论相反）**：
- B24：审核者的 prescription 被实测**证伪** → 取关切、弃形式。
- B25：审核者的 prescription 经实测**可实施且无假红**（三条逃逸全被捕获、两条正当路径不误红）
  → 采纳其形式。

差别不在审核者可信度，而在**编排者是否先跑了那条 prescription**。B24 的教训是
「别直接采纳 prescription」，本条补上另一半：**也别直接否定它**——两次都必须实测。
本轮我在裁定前先对 prescription 跑了逃逸形状 + 正当路径两组输入，才落判，这是 B24 教训的正向应用。

**落地判据（经实测，供返工使用）**：
普通失败路径 `tuple(stderr.splitlines()[1:]) == ()`（不得有任何续行）；
多错用例显式声明其预期续行元组；stdout 改为逐字节 `proc.stdout == ""`。
插桩实测 10 条失败路径：**9 条恰 1 行 stderr + 逐字节空 stdout**，唯一多行者是多错用例（2 行），
故该判据落地不需要放宽任何现有用例。

**流程教训**：加固补丁本身也必须走第二签名，不能因为「补丁很小、只改测试」就自签自过。
本轮若不复签，一个自称收紧输出契约、实则放过原始逃逸形状的补丁就会带着 ACCEPT 进合并门。

---

## B26 · 冻结者把**未经复核的测试计数**写进 brief 当基线（WP-26 rev3 实测，执行者反向指出）

**现象**：我在 `WP-26-brief-rev3.md:98` 写「基线（加固 HEAD `16bfdf3`）：targeted = **23 passed**」。
执行者在自己树上实测该文件 collect 为 **14**，在 `[CONCERNS]` 里指出这条出入并给出实测值。
编排者复核：`git show 16bfdf3:tests/test_dispatch_lint_brief_source.py` 单独 collect = **14 tests**
（13 个 test 函数 + 1 处 parametrize×2），执行者正确，我错。

**错误来源**：那个 23 来自更早一轮 `evidence.hardening_rev2.tests` 的记录，
而那一轮的 targeted 命令跑的是**两个文件**（`test_dispatch_lint_brief_source.py`
**加** `test_redispatch_brief_source.py`）。我把双文件的计数抄进了单文件的基线行，
抄的时候没重跑、也没核对命令形态是否一致。

**为什么没造成危害（这次）**：派发 prompt 里没有引用这个数字，
而全量数字（`4 failed / 620 passed / 4 skipped`）是对的、执行者据此算的零回归也是对的
（620 → 626 = +6 == 新增用例数，与 14 → 20 = +6 自洽）。危害被挡住是**运气**，不是设计。

**教训**：**数字在 brief 里就是判据，抄来的判据必须重跑。**
尤其危险的是「同一指标、不同命令形态」的计数（单文件 vs 多文件、targeted vs 全量）——
它们看起来是同一个量，实际不是。抄之前先确认命令形态一致，或干脆重跑一遍再写。

**与 B12 的关系**：B12 是「`evidence.baseline` 无机制强制存在、无机制强制与 dispatch_commit 一致」。
B26 是同一根因的另一面：基线数字**存在**、但**与它声称的命令形态不匹配**。
机械化时两者应一并收口 —— 基线条目必须同时记录 `cmd` 与 `measured_at_commit`，
且校验器应能按 cmd 重跑核对，而不只是检查字段在场。

**自检问题**：我写下的这个数字，是我在**这个 commit、用这条命令**跑出来的吗？
若答案是「抄的」，就必须重跑；若命令形态变了，旧数字一律作废。

---

## B27 · 守卫用例的**变异构造**锚在非锚点措辞上（WP-25 rev2 实测，非阻塞）

**现象**：WP-25 rev2 的 `test_evisceration_of_how_turns_discipline_anchors_red` 用两条正则
在活树模板上复现 B20 的两处掏空。编排者反向探针：只改写锚点**周边**措辞
（`use a differential pair instead:` → `rely on a differential pair instead —`，
或把纪律 3 那句重述一遍）而保留全部六个锚点短语 —— 九条锚点断言全绿（正确，证明锚点是短语级、
未反踩 B10），但**守卫用例自己**红了，措辞为 `discipline-N evisceration produced no change`。

**为什么定级非阻塞**：这是 **fail-closed**，不是空过。用例先断言
`assert text2 != text, "discipline-2 evisceration produced no change"`，
所以正则失配时它响亮失败并自解释，迫使改写措辞的人回来重新确认锚点是否还钉得住。
真正危险的形态是反过来的：正则失配 → 变异等于没变 → `pytest.raises` 拿不到异常 →
用例**静默通过**。那才是空过。本用例的断言顺序恰好挡住了这条。

**残留成本**：模板措辞每次打磨，这条守卫用例都可能需要同步改正则。
这是「变异构造依赖字面措辞」的固有成本，与 B10（断言锁整段）同族但位置不同 ——
B10 在**断言**侧，B27 在**变异构造**侧。锚点已经摆脱了字面依赖，变异构造还没有。

**可选的收口方向**（未做，留待机械化）：变异构造也改成锚点驱动 ——
用「删掉包含锚点短语 X 的那个句子」这类结构化操作代替字面正则，
使变异构造与锚点共享同一份真值，措辞改写时只需维护一处。

**自检问题**：我的变异**构造**失配时，用例是响亮地红，还是静默地绿？
前者是可接受的维护成本，后者是缺陷。

---

## B28 · 存在性锚点钉不住**极性**：保留全部锚点短语、把纪律改成相反规则，十条用例全绿（WP-25 rev2，第二签名发现）

**现象**：WP-25 rev2 为修 B20 把锚点从标签词（`differential pair`）补到可操作子句
（`flip exactly one input`、`flip with it`、`consumer channel`、`-revN`），并加了掏空守卫用例。
第二签名指出：这些锚点是**存在性**判据，检测不到**语义反转**。编排者两级实测确证：

- 内存级：构造 `use a differential pair instead: do not flip exactly one input, and do not
  require the verdict to flip with it.` —— 六个锚点**全部在场**，`_assert_discipline_anchors`
  对两条纪律**均 GREEN**；且掏空守卫的正则仍匹配、仍转红、witness 仍特异，
  即反转文本能**同时**通过锚点断言与守卫断言。
- 活树级：把纪律 2 正文换成语义完全相反的措辞，整文件 `pytest` → **10 passed**。
  一份指导「不要只翻一个输入、不要要求红绿随之翻转」的纪律，被全部用例判为合规。

**根因**：与 B20 是同一根因的下一层。B20 = 标签词钉不住方法；B28 = 方法短语钉不住极性。
`X in text` 这个判据形状，无论 X 取多细，都只能回答「这个词组在不在」，
永远回答不了「这句话是在要求它还是在禁止它」。加长锚点不解决问题，只是把 X 变长。

**为什么我一审判 ACCEPT 是错的**：我的双向探针覆盖了「删/压缩」（掏空必红）与
「改写周边措辞」（不误红）两个方向，**没有覆盖「保留全部锚点但反转极性」**。
B20 的教训我只吃了一半：做到了「锚点要钉可操作子句」，却没问
「子句在场之后，谁来钉住子句的极性」。这正是记忆 `same-topic-is-not-same-extension` 的形态 ——
同一主题的下一层反例集合并未被覆盖，而我把「同一主题」当成了「同一外延」。

**加长锚点这条路已被实测排除**（编排者补测，供 rev3 定形）：
把整条可操作从句当一个锚点行不通 —— 模板正文折行，
`hold everything else constant, flip exactly one input` 在原文里并不逐字存在（需先归一化空白）；
且把子句顺序做一次**无害重排**（`flip exactly one input while holding everything else constant`）
就会让整句锚点失配、短语锚点却全部保留。即：整句锚点会**反踩 B10**（断言与措辞耦合 → 误红）。
rev3 的极性判据必须换形式（例如禁忌反义词表 + 语义反转变异用例），不能靠把锚点写长。

**自检问题**：我的判据能区分「这条规则在场」与「这条规则说的是哪个方向」吗？
如果把被判对象改成**意思相反**但用词相同的版本，判据会红吗？

---

## B29 · 校验的快照与使用的快照不是同一份：`read_text()` 派发、`read_bytes()` 另读一份算 sha256（WP-26 累计面，第二签名发现，前三轮均漏）

**现象**：`redispatch._brief_content()`（`redispatch.py:173-187`）先
`content = brief_path.read_text(...)` 取得**将要派发**的正文，随后
`digest = hashlib.sha256(brief_path.read_bytes())` **另读一次**文件算 sha256。
两次读之间文件若变化，则校验的是第二份、派发的是第一份。

**实测确证**（编排者构造，import 被审树自己的 `_brief_content`，B14 纪律）：
拦下 `Path.read_text` 使其返回 EVIL 正文、同时把磁盘还原为 GOOD 让 `read_bytes` 读到 ——
**sha256 校验通过（对 GOOD），函数返回并将派发 EVIL**。基线对照（不拦截）返回 GOOD、校验通过。

**为什么是靶心**：本 WP 的全部立意就是「sha256 锚定**实际派发**的 Brief」——
B16（按固定命名推路径，不读 evidence.brief.path）与 B21（sha256 校验被回退分支跳过）
两轮返工皆为此。缺口正落在立意的靶心上，故阻塞成立，不是「理论上的 TOCTOU，非常规路径」。

**同族缺口在兄弟消费面**（编排者顺手核出，rev4 应一并收口）：
`dispatch_lint.sh` 的 sha256 段虽是单次 `open(real,'rb').read()`，
但它**只把路径**交给 bash（`print(real)`），brief 正文由后续 section 判据**另行按路径重读** ——
形态与 B13（finalize 写回段按路径重读）同族。即同一 WP 的两个消费面都有
「校验对象 ≠ 使用对象」的缺口，只是表现层不同：python 侧是双次读，bash 侧是传路径而非传内容。
只修 python 侧则 bash 侧仍在。

**修法**：只读一次字节 —— `raw = brief_path.read_bytes()`，对 `raw` 算 sha256，
从**同一个** `raw` 解码出返回内容；解码失败规范化为 `BriefIntegrityError`。
bash 侧则应把已校验的内容本身传下去，或至少让 section 判据消费同一份已读入的字节。

**为什么前三轮都没发现**：三轮咨询（rev1/rev2/rev2+harden）与三轮编排者验收的注意力
全在**本轮增量**上（每轮增量都只有测试文件），而这处缺陷由 rev1 提交 `0a12bed` 引入、
此后各轮零 diff。**增量审查会系统性放过前轮引入的缺陷**——这不是谁不认真，是审查面选择的结构性后果。
本轮我在请求 brief 里同时提供了累计 diff 与增量 diff，第二签名正是在累计面查出的；
这个做法应固化：**每轮咨询都必须同时提供累计 diff，并明确请其审累计面**。

**自检问题**：我校验的那份字节，和我实际交出去的那份字节，是同一次读取的产物吗？
中间隔了几次 I/O？

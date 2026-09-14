# 并行吞吐迭代 执行计划

> 迭代 id：`2026-09-13-parallel-throughput` ｜ 编排者 Claude ｜ 冻结日期 2026-09-13
> 目标：把「默认串行、并行靠人工声明」改成「机器算出可并行集、事前挡住撞车、成果分批落地」。

## §0.1 审核结论（Codex 关键纠正）

待 Codex 审核。以下为编排者自审已识别的结构性风险，供审核者优先复核：

1. **WP-A 的 schema 升级必须双形兼容。** `work_packages` 现有三处消费点：
   `plan_cmd.validate()`（第 151–155 行，硬校验 `list[str]`）、`_status_git_paths()`
   （第 252 行）、`cmd_check()`（第 417 行）。升级成对象数组时若漏改任一处，
   旧 plan 文件会在校验期直接炸。
2. **WP-G（worktree 隔离）与 WP-B（事前查撞车）存在职责重叠嫌疑。** 物理隔离之后，
   scope 交叉检查是否还必要？编排者判断仍必要——worktree 隔离的是 git index，
   不阻止两个 WP 都声明改同一文件后在合并期冲突。请审核者确认这个判断。
3. **WP-C 的分批收敛会削弱「一个 plan 一次 push」的原有保证。** 按 lane 收敛后，
   integration 分支会收到多次 lane 合并。需确认 push 仍只发生一次（在全部 lane
   收敛后），而不是每个 lane 一次。

## §1 需求概述

用户诉求原话：「项目迭代慢，希望可以多 Agent/人并行」。

经排查，并行**能力**已完备（`lock.sh` 双层锁 + heartbeat/TTL/活性探测、
`preflight.sh` 副 worktree 强制、`quality-gate.sh` scope 机器强制）。慢的根因是
**默认路径串行**，以及三处缺失使并行无法安全开启。

用户已确认的两个取向：

- **人不参与并行**：不改 `lock.sh` 的 owner 派生逻辑（保持「拿不到 session id
  就拒绝伪造 owner」）。并行主体只有 agent。
- **彻底隔离 git 工作区**：接受 WP-G，每条并行 lane 独立 worktree，不只是独立分支。

## §2 规格 vs 代码实况对照表

| 关注点 | 契约/文档怎么说 | 代码实况 | 差异 |
|--------|----------------|----------|------|
| WP 并行 | `AGENTS.md` §5「Parallel lanes require separate branches and non-overlapping file ownership」 | plan 无依赖图，无 lane 字段，无就绪计算 | 并行是人工判断，无机器支持 |
| plan 收敛 | §4.3「所有 WP MERGED 才能收敛」 | `cmd_check` 第 417 行全量栅栏 | 一个 WP 卡住堵住全部成果 |
| scope 冲突 | `quality-gate.sh` 事后校验改动路径 | 派发前无交叉检查 | 撞车要等实现完才暴露 |
| git index | `AGENTS.md` §5 自述「锁管得住谁写 WP，管不住共享索引」 | 靠「显式路径 commit」纪律，机器不强制 | 隔离不彻底 |
| 门输出 | 无约定 | `QUALITY_GATE_PLAN:` 逐行 + 原始 pytest stdout | 并行 N 路 = N 倍噪音 |
| 匹配逻辑 | — | `gate/__init__.py` 有 `scope_prefix`/`scope_matches`；`quality-gate.sh` heredoc 又抄一遍，注释自承「keep verbatim-aligned…tests assert parity」 | 靠测试维持的重复 |
| 经验沉淀 | 无 | 无入口 | 踩坑反复踩 |

## §3 冻结的产品决策

1. **人不并行。** `lock.sh` owner 逻辑不动，不加 `AGENTIC_OWNER` 兜底。
2. **worktree 彻底隔离。** 每条 lane 独立 worktree，纳入本迭代（WP-G）。
3. **`min_independence` 降为 `weak`。** 三签全绑同一 DeepSeek `identity_model`
   （`deepseek-v4-pro`），`independence.evaluate()` 最高只能评 weak；留 `strong`
   会让合并门永久拒绝。已在 `.agentic/config.toml` 显式声明代价，不伪装 strong。
4. **autonomy 开 ultra。** 并行度若受每步人工确认制约则等于 1。`always_stop`
   （push / 生产写 / 凭据）保持硬停。
5. **「一个 plan 一次 push」不变。** WP-C 放开的是 lane 级合并，不是 push 次数。

## §4 交付物总览

| WP | 标题 | 交付物 | 性质 |
|----|------|--------|------|
| WP-01 | 门输出压成摘要行 | `gate` report 层改造 | 纯输出层，不动判定 |
| WP-02 | 路径匹配逻辑去重 | `gate/plan.py` + wrapper 改调用 | 消除重复，为 WP-04 铺路 |
| WP-03 | plan 加依赖图与 lane | schema 升级 + `agentic plan lanes` | 纯引擎逻辑，可单测 |
| WP-04 | 派发前 scope 交叉检查（含 C1 前缀/glob 陷阱） | `dispatch_lint.sh` 加交叉检查 + `validate_wp_status.py` 拒绝无效前缀 | 依赖 WP-02 |
| WP-05 | plan 按 lane 分批收敛 | `plan merge --lane` | 依赖 WP-03，碰 git，风险最高 |
| WP-06 | lane 独立 worktree 强制 | `preflight.sh` worktree 校验升级 | 依赖 WP-03 |
| WP-07 | 经验活页 + 准入/退出规则 | `.agentic/lessons.md` + 规则 | 最后做，等真坑 |

首轮 dogfood（WP-01 + WP-03）实测踩出 12 个框架自身缺陷，证据见
`WP-08-candidate.md`。用户 2026-09-13 裁定：立 WP-08 并按下表拆分纳入本迭代。
C1 并入 WP-04（见 §5 的 scope 纪律说明），其余各成一 WP。

派发 WP-08 时又踩出第 13 个（**A4**：冻结期 `git.branch`/`worktree` 必须留空，
但 `preflight.sh:45` 要求非空，而补字段的三条路——另起 sync 提交 / 只改工作区 /
把 status 加进 `allowed_paths`——分别被 `plan lint`、`quality-gate.sh` 和
隔离纪律堵死）。本轮经用户授权 `--amend` 冻结提交绕过（`a556c26` → `802b667`）。
**A4 尚未拆包**，候选修法见 `WP-08-candidate.md` §A4，其中一条会把「状态文件提交
两次」改成三次，属文档级契约变更，待用户裁定后再定归属。

WP-08 验收（ACCEPT）之后踩出第 14 个（**A5**：`.agentic/config.toml` 于
2026-09-13 23:37 被会话外手工改动，`developer` 由
`{ adapter = "kimi", provider = "deepseek" }` 改为裸字符串 `"kimi"`；
没有 provider 绑定，`_resolve_implementer_identity()` 如实 fail-closed 返回
`None`，degraded 路径因此不进入，A0 逐字复现）。**WP-08 的代码没有回归**——
在有绑定时实测解锁 A0，fail-closed 亦正确；这是配置与代码的耦合未被文档化：
该次改动的注释「绑了也不影响评级」按的是 WP-08 之前的语义。
`min_independence` 仍为 `weak`，未被放宽。

**A5 的定性经用户澄清后已修正**（`WP-08-candidate.md` §A5 修正节）：kimi 实际跑
codingplan/k3、不经框架 provider 层（只有 claude/codex 走 kiro 代理），
所以这不是「配置漏了绑定」，而是**判据设计与本仓实际拓扑不匹配**——
strong/degraded/bootstrap 三条路径在当前拓扑下全部不可达。

**用户 2026-09-14 裁定：A5 走修法 2**（立新 WP 扩展评级判据）。
裁定依据是 codex 对 WP-15 的独立审核（`WP-15-consult-codex.md`，`REWORK`），
它推翻了原首选修法 1（给 `developer` 绑 provider）的前提：`identity_model`
直接来自可手改的 TOML，注入探针只验 sentinel 不验模型，**任何人都能声明一个
与真实路由不符的模型来伪造 degraded 独立性**，现有代码无任何防线。
那条路本质是让合并门去读一个用户可手改的字符串，与 WP-08 存在的理由
（不许自证）属同一类问题。另有两项 P1 阻断（`--config-file` 替换整份 kimi 配置、
模板硬编码 `type="anthropic"` 与本机 K3 的 `type="kimi"`+OAuth 不符），
均见 §A5 裁定节。

修法 2 的 WP 待起草。**改配置仍属用户决策，编排者不自行改**；
WP-01/WP-03/WP-08 的合并在修法 2 落地前继续挂起。

派发 A6 修复时立第 15 个 WP（**A6**：`adapters/kimi.py:63` 把
`max_context_size` 硬编码为 DeepSeek 的 768K，绑定路径绕不开，
会把 k3 的 1M 窗口静默压掉约 25%）。已出 `WP-15-brief.md` rev2，
经 codex 审核后**收窄为独立的 context-size 透传修复**，不再承担 A5 解锁责任。

| WP | 标题 | 交付物 | 性质 |
|----|------|--------|------|
| WP-08 | 解开双签合并门的独立性死锁（A0） | `independence.py` + `gate/__init__.py` 准入条件 | **优先级最高**，挡住整条流水线最后一步 |
| WP-09 | gate 配置形式统一（A1）+ 默认门限自洽（A3）+ 本仓 config 迁移 | `init_cmd.py` 吐 `[[gate]]` 与自洽的 `min_independence` + `.agentic/config.toml` | 开箱即坏（两个维度） |
| WP-10 | 状态模板默认值改可派发（A2） | `STATUS.json.tmpl` + scaffold 副本 | 开箱即坏，纯模板 |
| WP-11 | 两个静默说谎的失败路径（B1+B4） | `preflight.sh` 区分失败原因 + `AGENTS.md` 派发范式 | 信号可信度 |
| WP-12 | 缺信号≠冻结，退出码≠成功（B2+B6+B3） | `kimi-health.sh` `UNKNOWN_NO_OUTPUT` + `dispatched` 语义 | 仪表可信度 |
| WP-13 | 门拒绝跑错目录并标注读取来源（B5+C3） | `quality-gate.sh` 前置校验 + 输出层标注 | 假阳性治理 |
| WP-14 | `evidence.tests` 结构写进模板与文档（C2） | 模板示例 + QUICKSTART | 纯文档/模板 |
| WP-15 | `max_context_size` 随 provider 配置走（A6） | `provider_binding.py` 增 `max_context_size: int \| None` + `adapters/kimi.py` 模板读 binding | 静默降级，独立修复（rev2 已与 A5 解耦） |
| WP-17 | 补一条 engine-verifiable 的独立性判据（A5 修法 2） | `independence.py` + `adapters/base.py` 新增 `IsolationEvidence` + `gate/__init__.py` 读 git 事实 | **REWORK**（原 ACCEPT 已撤回）：判据可被一条 `GIT_AUTHOR_NAME` 环境变量伪造，见 A11。待重新设计来源证明 |

> **A4 尚未拆包**，待用户裁定归属（涉及「状态文件提交两次」的契约变更）。
>
> **A7 新增（2026-09-14，派发 WP-17 时实测）：以另一个 WP 分支为基线时，
> 本 WP 的 status 在副 worktree 索引里不可见，`preflight.sh:69` 的
> `git ls-files` 必挂。** 根因是提交拓扑——冻结提交 `2dd9cfc` 与基线
> `a46578c` 是 `802b667` 的两个分叉，而常规 WP 的冻结提交天然是基线祖先，
> 所以这个坑只在「上游依赖型 WP」这种自举场景下暴露。本轮处置：在副
> worktree 里把冻结提交（纯 `docs/plans/`，无代码）merge 进 WP-17 分支。
> 与 A4 同源不同条，详见 `WP-08-candidate.md` §A7。
>
> **WP-16 不属本迭代**：归 `docs/plans/2026-09-14-codex-verdict-contract/`，
> 由另一会话执行中（`state=IMPLEMENTING`），与本迭代无路径冲突。
> 但它**已经 merge 进本机 `agentic` 实际运行的那份代码**（装载源
> `/Users/admin/vibe/agentic-loop-main-codex-merge` 的 `main`，HEAD `600c2f1`），
> 而本仓工作树的 `adapters/codex.py` 仍是旧版——见新增缺陷 B7。
>
> **⚠️ B7（新增，2026-09-14）：本迭代所有门禁结论的证据链有机制性缺口。**
> `agentic *` 跑的是 uv 非 editable 安装的**另一个仓的快照**，不是本仓 `src/`；
> 本仓也没有 `scripts/agentic/`，故 `cli.py` 的 dogfood 通道落不到地。
> 本轮已核实 `dispatch_lint.sh` / `validate_wp_status.py` / `resolve_paths.py`
> 两侧逐字节一致，所以**已出的判定（含 WP-15 的 `DISPATCH_LINT_PASS`）仍然有效**；
> 但这是巧合而非保证。任一侧继续改动即刻恶化为假绿。
> 详见 `WP-08-candidate.md` §B7。
>
> **✅ B7 已修（2026-09-14）**：`uv tool install --force --editable` 指向本仓，
> 独立快照副本消失，`agentic_loop.__file__` 现为本仓 `src/`。行为一致性已复核
> （`dispatch-lint` 仍 PASS、`merge` 仍卡同一条 consult 门、pytest 一致）。
> 两处原判断已纠正：装载源是**本仓停在 `main` 的副 worktree**（非另一个仓）；
> `resolve_wrapper()` 的 dogfood 分支是**死代码**（找 `scripts/agentic/`，
> 两个目录都没有）。残留清理并入 A4/A7 那个 WP。详见 §B7 处置记录。
>
> **WP-17 的三个设计点已裁定**（2026-09-14）：复用 `weak` 不新增级别；
> 要求 `capabilities.sandbox_enforced` 并复用 `_weak_engine_enforced()`；
> git 事实由 `gate/` 读好后以 `IsolationEvidence` 传入以保 `evaluate()` 纯函数。
>
> **WP-17 的自举与顺序约束已裁定**（2026-09-14，用户选 A）：WP-17 基于
> `feature/wp08-independence-degraded` @ `a46578c` 开分支，WP-08 作上游依赖，
> **合并序固定 WP-08 → WP-17**，不动用例外合并授权。已冻结，`DISPATCH_LINT_PASS`。
> 合并期须把 WP-17 的 `base_branch` re-freeze 回 plan 分支（`merge.sh:82`
> 要求站在 base_branch 上，而那时 WP-08 分支已被并掉）——详见 brief
> 「⚠️ 合并操作序」一节，此时序矛盾与 A4 同源。
>
> **⚠️ A8（新增，2026-09-14，WP-17 验收时实测）：WP-17 的判据在框架自己的仓里
> 无法自证，A0 依然没解开。** 实现无缺陷（已 `ACCEPT`），但四项 git 事实里两项
> 恒为 False：`author_differs=False` 因本机编排者与执行者共用同一 git 身份
> `xizhu`；`scope_respected=False` 因 A7 的处置把 7 个 `docs/plans/` 文件
> merge 进了 WP-17 分支，落在 `base_commit..tip` 区间内且不在 allowed_paths 中
> （采集函数如实报告，判断正确）。三条 bootstrap 逃逸路径在本仓的实际可达性：
> WP-08 degraded ❌（A5 未绑 provider）、WP-07 attested ⚠️（可达但需人工签）、
> WP-17 isolated ❌（本条）。四个候选修法（首选修 A5 而非放宽判据）详见
> `WP-08-candidate.md` §A8，**需用户裁定后另立 WP**。
> 与 A7 耦合：修 A7（改在主仓索引里查 status，不必 merge）会顺手消掉卡点 2。

> 以下为裁定前的原始记录，保留备查：它改的
> `gate/__init__.py` 与 `independence.py` 正是 WP-08 的范围，而 WP-08 的合并
> 本身卡在 A0——即 WP-17 要解的那个问题。基线分支（基于 WP-08 分支开，
> 还是先例外合并 WP-08）是冻结前唯一待定项。

> **⚠️ Codex 双签审核结果（2026-09-14）：WP-08 与 WP-17 双双 REWORK，合并暂停。**
> 用户授权合并后，`agentic merge` 卡在双签门（`consult.decision must be ACCEPT`），
> 遂派 Codex（consultant, gpt-5.6-sol via kirogpt）实审两个改独立性判据的 WP。
>
> **WP-08 → REWORK（编排者维持 ACCEPT）**：两条发现现象成立但均为**预存缺陷**，
> 非本 WP 引入（WP-08 完全没碰 `independence.py`）。已登记 **A9**（degraded 异源
> 比较返回 `strong` 而 bootstrap 只允许 `weak`，自 `c555daf` 即存在；本仓当前
> 不可达，**修 A5 后立即可达**）与 **A10**（`identity_model` 来自可编辑 config
> 声明而非执行时实测，同等适用于 consultant）。
>
> **WP-17 → REWORK（编排者撤回原 ACCEPT，已登记 A11）**：Codex 指出 author 判据
> 可伪造，编排者**自建临时 git 仓实证复现**——同一操作者仅加
> `GIT_AUTHOR_NAME=... GIT_AUTHOR_EMAIL=... git commit`，四项判据全 True、
> `evaluate()` 返回 `weak`、合并门被骗过，且 reasons 打出假陈述
> "change proven to originate elsewhere"。判据把可自我声明的字段当作 engine 核对的
> 事实，**实质削弱 fail-closed 地板，比不加这条路径更糟**。同一提交的 committer
> 仍是 orchestrator，真相就在那个字段里，但判据没读。
>
> 原验收失误性质：查了「状态文件能不能自填」，没查「git 事实本身能不能自造」——
> 诚实性检查做在了错误的层面。其余结论（纯函数、级别表、strong 不可达、口径单一、
> 零回归）全部成立且仍然成立，问题在判据设计而非实现工艺。
>
> **A8 与 A11 并存**：判据同时**过严**（本仓恒不放行）和**过松**（他处可伪造），
> 说明 `author` 这个代理量选错了，不是阈值调整能解决的。
>
> **修 A5 的前置条件（新增）**：必须先封 A9 的 strong 上限，否则给 developer 绑
> 异源 provider 会把预存缺陷激活成「合并门实际给出 strong」的误判。

## §5 工作包拆分

依赖关系（`depends_on` 已写入 `PLAN-01.status.json`）：

```
lane-gate:      WP-01 ──→ WP-02 ──→ WP-04 ──→ WP-11 ──→ WP-12 ──→ WP-13
lane-plan:      WP-03 ──┬─→ WP-05
                        └─→ WP-06
lane-docs:      WP-07（依赖 WP-04 + WP-05 + WP-06，最后收）
lane-gate-fix:  WP-08（无依赖，优先级最高）
lane-config:    WP-09（无依赖）
lane-template:  WP-10 ──→ WP-14
```

`lane-gate-fix` / `lane-config` / `lane-template` 三条与既有两条互不重叠，可同时开工。
`lane-gate` 加长到六个：WP-11/12/13 都碰 `wrappers/`，与 WP-02、WP-04 同域，
必须串行。**WP-08 优先单独开工**——A0 解掉之前，任何 WP 做完都同样卡在合并门前。

WP-01 与 WP-03 无依赖，是首轮可并行的两个头。这正好用本迭代自己的机制 dogfood：
第一轮手工开两条 lane，WP-03 落地后改用 `agentic plan lanes` 算就绪集。

各 WP 的 Brief 见 `WP-<N>.brief.md`，运行时状态见 `WP-<N>.status.json`。

### scope 划分（保证同 lane 内无重叠）

| WP | allowed_paths |
|----|---------------|
| WP-01 | `src/agentic_loop/gate/`, `tests/test_gate_report*.py` |
| WP-02 | `src/agentic_loop/gate/plan.py`, `src/agentic_loop/wrappers/quality-gate.sh`, `tests/test_gate_plan*.py` |
| WP-03 | `src/agentic_loop/plan_cmd.py`, `src/agentic_loop/templates/PLAN.json.tmpl`, `tests/test_plan*.py` |
| WP-04 | `src/agentic_loop/wrappers/dispatch_lint.sh`, `src/agentic_loop/validate_wp_status.py`, `tests/test_dispatch_lint*.py` |
| WP-05 | `src/agentic_loop/plan_cmd.py`, `tests/test_plan*.py` |
| WP-06 | `src/agentic_loop/wrappers/preflight.sh`, `tests/test_preflight*.py` |
| WP-07 | `.agentic/lessons.md`, `docs/` |
| WP-08 | `src/agentic_loop/independence.py`, `src/agentic_loop/gate/__init__.py`, `tests/test_independence*.py`, `tests/test_gate_independence*.py` |
| WP-09 | `src/agentic_loop/init_cmd.py`, `src/agentic_loop/resolve_paths.py`, `.agentic/config.toml`, `tests/test_init_gate_form.py` |
| WP-10 | `src/agentic_loop/templates/STATUS.json.tmpl`, `docs/agentic/templates/STATUS.json`, `tests/test_init_contract.py`, `tests/test_status_template_dispatchable.py` |
| WP-11 | `src/agentic_loop/wrappers/preflight.sh`, `AGENTS.md`, `src/agentic_loop/templates/AGENTS.md.tmpl`, `tests/test_preflight_tracked_error.py` |
| WP-12 | `src/agentic_loop/wrappers/kimi-health.sh`, `src/agentic_loop/adapters/{base,kimi,claude}.py`, `AGENTS.md`, `src/agentic_loop/templates/AGENTS.md.tmpl`, `tests/test_health_unknown_no_output.py`, `tests/test_adapter_dispatched_semantics.py` |
| WP-13 | `src/agentic_loop/wrappers/quality-gate.sh`, `src/agentic_loop/wrappers/preflight.sh`, `tests/test_quality_gate_wrong_worktree.py`, `tests/test_gate_status_source_label.py` |
| WP-14 | `src/agentic_loop/templates/STATUS.json.tmpl`, `docs/agentic/templates/STATUS.json`, `docs/QUICKSTART.zh-CN.md`, `tests/test_status_template_evidence_shape.py` |

注意 WP-03 与 WP-05 都声明 `plan_cmd.py`，**故意放在同一 lane 串行**，不并行。
WP-01 与 WP-02 都碰 `gate/`，同理同 lane。这两处是 WP-04 交叉检查要挡的典型场景。

> **本表用的是 glob 写法，`<WP>.status.json` 的 `scope.allowed_paths` 用的是前缀语义，
> 两者长得一样但含义不同。** `gate/__init__.py` 的 `scope_prefix()` 只剥尾部 `/**`
> 与 `/*`，`scope_matches()` 是 `path == prefix or path.startswith(prefix + "/")`；
> 所以本表里的 `tests/test_dispatch_lint*.py` 手抄进 status 时若降级成
> `tests/test_dispatch_lint`，那是一个**匹配不到任何文件**的死前缀，
> 门要等到实现完成才报越界。本轮 dogfood 两个 WP（WP-01 的
> `tests/test_gate_report*.py`、WP-03 的 `tests/test_plan*.py`）全中同一个坑，
> 各付出一次 `--amend` 冻结提交 + rebase 两条 feature 分支的代价。
> **纪律：status 的 `allowed_paths` 只写具体文件路径或目录前缀，不写 glob。**
> 把这条变成机器可验的检查是 WP-04 的范围（缺陷 C1，见 `WP-08-candidate.md` §C1）：
> `validate_wp_status.py` 应对「写了 glob 却被剥成无效前缀」直接 STATUS_INVALID，
> 且 `dispatch-lint` 应校验 status 的 allowed_paths 与 brief/PLAN 的 scope 表一致。

## §6 门禁测试定义

`.agentic/config.toml` 的 `[[gate]]`（`kind="command"`, `stage="pre_review"`）
下的 `[[gate.rule]]`：`src/agentic_loop/**` 或 `tests/**` 任一改动 →
`python3.11 -m pytest tests -q` 全量。本仓测试量小，全量比按目录挑更省心。
规则匹配是「首条命中者胜」（`apply=first_match`），故不在 `src/agentic_loop/**`
之后再写更窄的前缀（那条永不命中，形同虚设）。

> 两处口径修正，均为本轮 dogfood 实测：
> (a) 正式形式是 `[[gate]]` / `[[gate.rule]]`，不是 `[[quality_gate.rule]]`——
> 后者 `quality-gate.sh` 与 `resolve_paths.py` 读不到，会 fail-closed 报
> `[[gate]] ... is absent or defines no rules`。`agentic init` 的模板恰好吐的是
> 前者，即默认配置过不了自己的门（缺陷 A1，归 WP-09）。
> (b) 命令写 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
> 注意 `AGENTIC_PYTHON` 只管 wrapper 自身对 Python 模块的调用，**管不到
> `gate.rule.run` 里的命令**，且跑全量测试时不得设置（缺陷 B3，归 WP-12）。

每个 WP 的 DoD 额外要求（全局规范 §3）：

- characterization test：WP-01/WP-02 属重构性质，必须先锁当前输出再改。
  WP-01 要先固化现有 gate 输出的**判定结果**（PASS/FAIL 与退出码），
  证明压缩输出没有改变判定。
- WP-05 碰 git 操作，必须有「lane 未全 MERGED 时拒绝收敛」的反向测试。
- WP-06 必须有「同 lane 两 WP 指向同一 worktree 时拒绝」的反向测试。

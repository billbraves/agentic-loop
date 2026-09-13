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

| WP | 标题 | 交付物 | 性质 |
|----|------|--------|------|
| WP-08 | 解开双签合并门的独立性死锁（A0） | `independence.py` + `gate/__init__.py` 准入条件 | **优先级最高**，挡住整条流水线最后一步 |
| WP-09 | gate 配置形式统一（A1）+ 默认门限自洽（A3）+ 本仓 config 迁移 | `init_cmd.py` 吐 `[[gate]]` 与自洽的 `min_independence` + `.agentic/config.toml` | 开箱即坏（两个维度） |
| WP-10 | 状态模板默认值改可派发（A2） | `STATUS.json.tmpl` + scaffold 副本 | 开箱即坏，纯模板 |
| WP-11 | 两个静默说谎的失败路径（B1+B4） | `preflight.sh` 区分失败原因 + `AGENTS.md` 派发范式 | 信号可信度 |
| WP-12 | 缺信号≠冻结，退出码≠成功（B2+B6+B3） | `kimi-health.sh` `UNKNOWN_NO_OUTPUT` + `dispatched` 语义 | 仪表可信度 |
| WP-13 | 门拒绝跑错目录并标注读取来源（B5+C3） | `quality-gate.sh` 前置校验 + 输出层标注 | 假阳性治理 |
| WP-14 | `evidence.tests` 结构写进模板与文档（C2） | 模板示例 + QUICKSTART | 纯文档/模板 |

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

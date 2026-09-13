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
| WP-04 | 派发前 scope 交叉检查 | `dispatch_lint.sh` 加交叉检查 | 依赖 WP-02 |
| WP-05 | plan 按 lane 分批收敛 | `plan merge --lane` | 依赖 WP-03，碰 git，风险最高 |
| WP-06 | lane 独立 worktree 强制 | `preflight.sh` worktree 校验升级 | 依赖 WP-03 |
| WP-07 | 经验活页 + 准入/退出规则 | `.agentic/lessons.md` + 规则 | 最后做，等真坑 |

## §5 工作包拆分

依赖关系（`depends_on` 已写入 `PLAN-01.status.json`）：

```
lane-gate:   WP-01 ──→ WP-02 ──→ WP-04
lane-plan:   WP-03 ──┬─→ WP-05
                     └─→ WP-06
lane-docs:   WP-07（依赖 WP-04 + WP-05 + WP-06，最后收）
```

WP-01 与 WP-03 无依赖，是首轮可并行的两个头。这正好用本迭代自己的机制 dogfood：
第一轮手工开两条 lane，WP-03 落地后改用 `agentic plan lanes` 算就绪集。

各 WP 的 Brief 见 `WP-<N>.brief.md`，运行时状态见 `WP-<N>.status.json`。

### scope 划分（保证同 lane 内无重叠）

| WP | allowed_paths |
|----|---------------|
| WP-01 | `src/agentic_loop/gate/`, `tests/test_gate_report*.py` |
| WP-02 | `src/agentic_loop/gate/plan.py`, `src/agentic_loop/wrappers/quality-gate.sh`, `tests/test_gate_plan*.py` |
| WP-03 | `src/agentic_loop/plan_cmd.py`, `src/agentic_loop/templates/PLAN.json.tmpl`, `tests/test_plan*.py` |
| WP-04 | `src/agentic_loop/wrappers/dispatch_lint.sh`, `tests/test_dispatch_lint*.py` |
| WP-05 | `src/agentic_loop/plan_cmd.py`, `tests/test_plan*.py` |
| WP-06 | `src/agentic_loop/wrappers/preflight.sh`, `tests/test_preflight*.py` |
| WP-07 | `.agentic/lessons.md`, `docs/` |

注意 WP-03 与 WP-05 都声明 `plan_cmd.py`，**故意放在同一 lane 串行**，不并行。
WP-01 与 WP-02 都碰 `gate/`，同理同 lane。这两处是 WP-04 交叉检查要挡的典型场景。

## §6 门禁测试定义

`.agentic/config.toml` 的 `[[quality_gate.rule]]`：`src/agentic_loop/**` 或
`tests/**` 任一改动 → `python3 -m pytest tests -q` 全量。本仓测试量小，全量比按
目录挑更省心。规则匹配是「首条命中者胜」，故不在 `src/agentic_loop/**` 之后再写
更窄的前缀（那条永不命中，形同虚设）。

每个 WP 的 DoD 额外要求（全局规范 §3）：

- characterization test：WP-01/WP-02 属重构性质，必须先锁当前输出再改。
  WP-01 要先固化现有 gate 输出的**判定结果**（PASS/FAIL 与退出码），
  证明压缩输出没有改变判定。
- WP-05 碰 git 操作，必须有「lane 未全 MERGED 时拒绝收敛」的反向测试。
- WP-06 必须有「同 lane 两 WP 指向同一 worktree 时拒绝」的反向测试。

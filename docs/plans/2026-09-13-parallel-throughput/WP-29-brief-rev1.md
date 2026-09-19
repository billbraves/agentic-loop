# WP-29: 模板受保护块的「活动渲染」判据 —— 先定方言与消费链，再谈判据

> 冻结日期 2026-09-18 | 编排者 claude | 执行者 kimi。
> 所属 Plan：PLAN-01（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 本 WP 由 WP-28 rev3 的承诺收缩拆出，来源裁定见
> `WP-28-plan-review-before-rev3.md` §5 与 `WP-28-consult-codex-shape.md` §2/§4。
> **本 WP 第 1 次冻结（rev1）。**

## 目标（一句话）

回答一个 WP-28 在原理上无法回答的问题：受保护的模板块**是否作为活动规范文本被渲染与消费** ——
并且**先定义清楚这个问题在本仓的含义**（权威 Markdown 方言、parser 版本、目标 AST、消费链），
再决定是否、以及如何为它建立机械判据。

## 为什么必须另立一个 WP（不是 WP-28 的续作）

WP-28 收缩为「受保护表示（逐字节）+ 副本同一 + 变更可见性」，并明文声明**不覆盖**渲染上下文。
编排者已实测四条逃逸：三条保持两块 body 逐字节完好而判据 GREEN（整份文档外包
`<!-- … -->`、文档开头留未闭合 `<!--`、在 `## 附注` 内开未闭合代码围栏），
一条是远距离去规范化句（文档开头加「下列所有流程规则均已废止，仅供历史参考。」）。

这些不是 WP-28 漏测，而是**块内字节相等在原理上无法覆盖块外上下文**：
`active_embedding` 必然是至少部分依赖块外的性质。三项独立核实的事实决定了它必须拆包：

1. 全仓**没有**任何 Markdown parser 依赖。
2. **没有**任何文档声明权威 Markdown 方言。
3. `WORK_PACKAGE.md.tmpl` 在仓内的**唯一**消费者是 `src/agentic_loop/init_cmd.py:109`
   （`_REFERENCE_TEMPLATES`），它**逐字节复制**该文件，**不解析** markdown。

第 3 条尤其关键：**在当前消费链下，「渲染」这件事在仓内根本没有发生**。
所以本 WP 的第一阶段不是写判据，而是判定这个问题此刻是否真实存在。

## 范围

**本 WP 分两阶段，第一阶段的交付物是一份裁定，不是代码。**

### 阶段 1（本次冻结的全部内容）：范围界定与可行性裁定

allowed_paths：

- `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md`（新建，本阶段唯一产出）

阶段 1 须回答并逐项给出证据：

1. **消费链实况**：除 `init_cmd.py:109` 外，`WORK_PACKAGE.md` / `.md.tmpl` 还被谁读取？
   人（在编辑器/GitHub 上阅读）算不算消费者？agent（读模板以决定如何冻结）算不算？
   给出 `grep -rn` 的完整证据面，不要凭印象。
2. **渲染面实况**：这两份文件事实上会被哪些渲染器渲染（GitHub / 编辑器预览 / 静态站点）？
   它们的 Markdown 方言各是什么？彼此是否一致？**不一致时以谁为权威？**
3. **威胁是否真实**：一个把整份模板注释掉的改动，在**当前**流程里会被什么拦住？
   （提示：它会被 WP-28 的 T4/T6 拦住吗？编排者实测是**不会**。那会被 code review 拦住吗？
   `git diff` 里可见吗？）请给出「若无本 WP，该攻击的实际后果链」。
4. **方案对比**（至少三条，各带成本与判别力）：
   - (a) 引入权威 parser（如 `markdown-it-py`），解析整份文档并校验目标 AST 节点位置与类型
   - (b) 不引 parser，锁定一个明确定义的**完整 envelope**（例如整份模板逐字节冻结）
   - (c) 承认机械不可兑现，把限制**明文写入模板**作为已知限制，并把防线交给 review
5. **裁定**：推荐哪条，为什么；若推荐 (a)，须给出方言选择、版本钉法、依赖引入的影响面
   （`pyproject.toml` / CI / 离线约束）；若推荐 (c)，须给出模板里该限制的确切措辞。

**forbidden_paths（阶段 1）**：

- 一切代码与测试文件。**阶段 1 不写任何判据、不引任何依赖。**
- `src/` 下全部文件、`tests/` 下全部文件、`pyproject.toml`、`uv.lock`
- `src/agentic_loop/templates/`、`docs/agentic/templates/` —— **不要碰模板**，
  WP-28 rev3 正在对这两份做逐字节冻结，任何改动会与之冲突
- `docs/plans/` 下除 `WP-29-scope-decision.md` 外的全部文件
- `.agentic/`、`.env`、`.context/`
- owner 边界对齐 CODEOWNERS。

### 阶段 2（**本次不冻结**）

阶段 2 的范围由阶段 1 的裁定决定，须**另行冻结并经用户批准**。
在阶段 1 裁定落地并获批准前，**不得**开始阶段 2 的任何实现。

## 输入

- WP-28 rev3 brief 的「本 WP 明文不覆盖什么」一节 —— 本 WP 的问题定义即由此而来
- `WP-28-plan-review-before-rev3.md` §4.1（三条 B44 族逃逸的实测证据）与 §4.2（B45 族）
- `WP-28-consult-codex-shape.md` §2（`active_embedding` 为何必然依赖块外上下文）、
  §4（不引 parser 时应如何诚实降级）
- 被审树：由编排者在派发时创建的独立 worktree（阶段 1 只写一份文档，仍走隔离流程）

## 交付物清单

- [ ] `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md` ——
      含上述 5 项的逐项作答与证据，末尾一条明确裁定

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收要求同义，非另一份口径。

阶段 1 的产出是文档，其「测试」是**证据可核验性**。编排者验收时会逐条复现，
所以每一项论断都必须附可执行的复现命令或精确文件行号引用：

1. **消费链论断**须附 `grep -rn` 命令原文与其完整输出（不得只写结论）
2. **渲染面论断**须区分「实测」与「推断」：无法实测的（如 GitHub 的确切方言版本）
   必须标注为推断并说明依据
3. **威胁真实性论断**须附一次实际构造：把模板整份注释掉，跑
   `PYTHONPATH=src python3.11 -m pytest tests/test_wp_template_dispatch_lint.py -q`，
   记录它是否转红。**跑完须 `git checkout` 还原并确认 `git status` 干净。**
4. **方案对比**的每条须给出「它能拦住哪条实测逃逸、拦不住哪条」——
   对照 WP-28 停手复核 §4.1 的三条 + §4.2 的一条，逐条填表
5. **裁定**须是三条方案之一或其明确组合，不得写成「视情况而定」

**若你的结论是 (c)「机械不可兑现」，那是一个合格的交付，不是失败。**
本 WP 存在的意义之一就是允许这个答案 —— WP-28 两轮返工的代价，正是因为当时没人被允许说这句话。

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径。
阶段 1 只能新建 `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md` 一个文件；
绝不能碰 `src/` 与 `tests/` 下任何文件、`pyproject.toml`、`uv.lock`、
`src/agentic_loop/templates/`、`docs/agentic/templates/`、`docs/plans/` 下其余文件、
`.agentic/`、`.env`、`.context/`；不得引入任何第三方依赖；
owner 边界对齐 CODEOWNERS，不跨 owner 写入。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径。

- [ ] `WP-29-scope-decision.md` 存在，5 项逐条作答，每项附可核验证据
- [ ] 消费链一项附 `grep -rn` 原文命令与完整输出
- [ ] 渲染面一项区分「实测」与「推断」
- [ ] 威胁真实性一项附实际构造与 pytest 实测输出，且 `git status` 跑完干净
- [ ] 方案对比逐条对照 WP-28 停手复核 §4.1 三条 + §4.2 一条填表
- [ ] 末尾有明确裁定（(a)/(b)/(c) 之一或明确组合）
- [ ] **零代码改动**：`git diff --stat` 只含那一个 md 文件
- [ ] 未引入任何依赖（`pyproject.toml` / `uv.lock` 零 diff）
- [ ] 未碰两份模板（WP-28 rev3 正在冻结它们）
- [ ] 相对基线零回归（本阶段不改代码，跑一次全量确认与基线一致：
      `4 failed / 619 passed / 4 skipped`，4 条全在 `tests/test_finalize_merge_triple_sign.py`）
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

| 维度 | 取值 |
|---|---|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要在阶段 1 写判据。** 两轮 WP-28 返工的教训是：在问题定义清楚之前写判据，
   只会得到一个又一个不完整的 mini-parser。先答「这个问题在本仓是什么」。
2. **不要碰两份模板。** WP-28 rev3 正在对它们做逐字节冻结，任何改动会撞上那边的判据。
3. **不要引依赖。** 引 parser 是阶段 2 的事，且须先经裁定与用户批准。
4. **(c) 是合法答案。** 见 §Acceptance tests 末段。
5. **不要用 `agentic <sub>` 自证**（B14：那是别棵树的冻结副本）。
   用 `PYTHONPATH=src python3.11 -m pytest`。
6. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。
7. **既有 4 条失败不是你引入的**（本机 `git init.defaultBranch=master` 与 fixture 冲突）。不要修。

### 口径权威源引用

- 本 WP 的问题定义：`WP-28-brief-rev3.md`「本 WP 明文不覆盖什么」一节
- 四条实测逃逸的证据：`WP-28-plan-review-before-rev3.md` §4.1 / §4.2
- 设计依据：`WP-28-consult-codex-shape.md` §2 / §4
- 模板的唯一仓内消费者：`src/agentic_loop/init_cmd.py:109`（`_REFERENCE_TEMPLATES`）

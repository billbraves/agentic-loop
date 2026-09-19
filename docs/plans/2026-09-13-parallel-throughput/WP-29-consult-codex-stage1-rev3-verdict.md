# WP-29 阶段 1 rev3 第二签名裁定（codex，逐字存档）

> 咨询者 codex（provider kirogpt，model gpt-5.6-sol，reasoning_effort=high，sandbox read-only）
> 2026-09-19｜被审提交 `e493c2a`｜冻结 brief `WP-29-brief-rev3.md` sha256 `05b00b72…`
> 请求文档 `WP-29-consult-codex-stage1-rev3-request.md` sha256 `3718e2b4…`
> 输入：累积 diff `2e5f2c0..e493c2a`（1 文件 +458/−0），prompt 47171 字节
> harness `/Users/admin/.claude/jobs/8a8bf01e/tmp/consult-wp29-stage1-rev3/run.py`，RC=0
> 派发环境仅剥离 `OPENAI_BASE_URL`

## 裁定：REWORK

以下为 codex 输出的逐字存档（`--output-schema` 为 advisory，codex 以散文而非 JSON 形态返回；
按记忆 `codex-output-schema-is-advisory` 逐字转录，不改写不归纳）：

---

结论：**REWORK**

### 阻断项 C1-R3：消费链证据仍不满足“仓库级完整原始输出”

D 类使用行号级证据替代字面命中本身成立：`*.tmpl`、变量 `name` 与 `read_text()` 不会命中两个精确文件名，且现有证据足以说明该已知路径不解析 Markdown。四分类也无需增加“第五类”；问题在于可能未发现的通用读取入口仍会归入 A 或 D。

但当前证据有三处可直接验证的不闭合：

1. 两条命令搜索范围是 `.`，却没有排除当前交付物。被审文件自身包含两个搜索串，但粘贴结果没有任何 `WP-29-scope-decision.md` 命中。因此这些内容不是命令针对最终被审树产生的完整输出。
2. `WP-28-consult-codex-shape-verdict.json:6` 被 `……` 替换，明确不是 brief 要求的“原始命中行，不得摘要”。
3. 宽口径 `WORK_PACKAGE` 搜索只粘贴 5 个新增命中并称其“归 C 类”，但已知遗漏中包含两个 B 类测试读取点。精确文件名 grep 本来就发现不了这种拼接路径，因此宽口径输出的不完整与误分类会实质削弱“没有其它通用消费者”的结论。文档另称 `grep -rn 'load_template' src/ tests/` 只有指定调用点，但没有附该命令的原始输出。

这是有界修复：显式增加并声明 `--exclude=WP-29-scope-decision.md` 以避免证据文件自命中，针对最终树重新运行搜索；逐字粘贴输出，不用省略号；完整呈现宽口径及 `load_template`/资源读取入口搜索，并将拼接路径的两个测试命中归入 B 类。完成后 C1 可以闭合。

### 其余裁决

- **C2 已闭合**：方案 (b) 的 E1–E4/G1–G4 均明确对应整文件字节判据并由带 no-op 守卫的实验支持；推荐方案不再误伤权威定义的 G1–G4。
- **(c′) 量词基本闭合**：文档只承诺受保护 body 与冻结常量的字节同一，明确不承诺 `active_embedding`，没有把 E1–E4 外推成被覆盖的攻击族。
- G1–G4 都在受保护跨度之外不构成缺陷。受保护 body 的合法政策升级本应使旧 oracle 转红，再通过显式更新冻结常量完成变更；它不属于必须无条件 GREEN 的普通编辑。阶段 2 brief 仍应冻结具体标题锚点、body 边界、缺失/重复标题和换行处理。
- 编排者对“错误层”的归因正确：预先变异磁盘夹具后再运行自带变异与夹具前置断言的完整测试，测到的是测试载具前置条件，不是 (c′) 不变式。
- **M1、M2 合并后是本轮阻断项，而非纯措辞问题**，因为本 WP 的主要交付物就是可复现、完整的消费面证据。**M3 定性正确且仅加强结论。**
- 范围、零代码改动、依赖、生产安全及信号/阈值语义方面未见其它阻断问题。
---

## 编排者对本裁定的独立核验（2026-09-19）

**结论：接受 REWORK，撤回我自己的 rev3 ACCEPT（`WP-29-review-stage1-rev3.md`）。**
codex 的第 1 条是我漏掉的可直接验证的事实，且它把我判为非阻断的 M1/M2 重新定性为阻断 ——
这个改判是对的，我的定性错了。

### codex 第 1 条：命令声明的过滤器 ≠ 产生粘贴输出的过滤器（实测成立）

我原地实测（在被审树 `e493c2a` 上）：

```text
交付物自身含搜索串：'WORK_PACKAGE\.md\.tmpl' 49 处，'docs/agentic/templates/WORK_PACKAGE\.md' 57 处

按交付物**声明**的命令（仅 --exclude-dir=.git,__pycache__,.pytest_cache）：
  grep #1 -> 88 行（其中 49 行来自交付物自己）
  grep #2 -> 104 行（其中 57 行来自交付物自己）

再加 --exclude=WP-29-scope-decision.md：
  grep #1 -> 39 行
  grep #2 -> 47 行   <- 与交付物粘贴的 39 / 47 完全一致
```

即：粘贴的输出是**加了一个未声明的 `--exclude`** 之后的结果。这正是 C1 的缺陷类别
（「『完整输出』省略了命中却未声明排除参数」），只是这次省略的是自命中而非
`__pycache__`。我上一轮把 39/47 与「按声明命令重跑」逐行比对时，**自己也加了
`--exclude=WP-29-scope-decision.md`**（否则自命中会淹没输出），于是比对当然逐行一致 ——
我的核验方法复制了交付物的未声明过滤器，所以查不出这条。这是我的核验缺陷，记为
**B57**：核验「完整输出」类声明时，必须先按**声明的命令原文**重跑一次，再讨论差异；
不得为了让输出可读而私自加过滤器。

排除自命中本身是**正当**的（否则证据文件自己的引用会淹没消费面），问题只在**未声明**。
所以这是有界修复，与 codex 的判断一致。

### codex 第 2、3 条：与我的 M1 / M2 同料，但定性应为阻断

我把 M1（`WP-28-consult-codex-shape-verdict.json:6` 长行用 `……` 省略）与 M2（宽口径块只粘
5/17 行且把 2 个 B 类命中标为 C 类）记为非阻断，理由是「实质结论不受影响」。codex 的理由更
站得住：**本 WP 阶段 1 的主要交付物就是「可复现、完整的消费面证据」本身**，证据的可复现性
就是标的，不能用「结论不变」豁免。我接受这个定性。

另外 codex 指出交付物声称 `grep -rn 'load_template' src/ tests/` 的调用点只有两处却未附原始
输出。我实测该命令有 6 行命中（`init_cmd.py:148`、`contract_render.py:12/243/250`、
`tests/test_contract_render.py:165/167`）。交付物的文字表述与实况不矛盾，但同样是「有断言、
无原始输出」，与 C1 同类。

### codex 其余裁决与我的一致

- C2 闭合、(c′) 量词基本闭合、错误层归因正确、M3 定性正确且仅加强结论 —— 与我的第一签名同向。
- **G1–G4 都在受保护跨度之外不构成缺陷**：codex 给了一个我没写出的正面理由 —— 受保护 body 的
  合法政策升级**本应**让旧 oracle 转红，再由显式更新冻结常量完成变更，它不属于必须无条件
  GREEN 的普通编辑。这条应带进阶段 2 的 brief。
- codex 给阶段 2 追加了冻结项：**具体标题锚点、body 边界、缺失/重复标题、换行处理**四项都要
  在阶段 2 的 brief 里冻结。这与本仓既有教训（`verbatim-lock-needs-unique-anchor`、
  `byte-exact-claims-need-a-byte-read`）同向，采纳。

### 处置

双签名结果：`review.decision` 由 ACCEPT **撤回**为 REWORK，`consult.decision` = REWORK，
state -> `CHANGES_REQUESTED`。rev4 的返工目标是 C1 一条（有界）：

1. 按**声明即所用**重跑两条主 grep：显式写出并声明 `--exclude=WP-29-scope-decision.md`
   （或换用不自命中的取证方式），粘贴逐字输出，不得再有未声明过滤器。
2. 取消所有 `……` 省略，长行逐字粘贴。
3. 宽口径 `WORK_PACKAGE` 搜索完整粘贴 17 行，并把两个拼接路径测试命中
   （`tests/test_init_contract.py:62`、`tests/test_wp_template_dispatch_lint.py:24`）改归 B 类。
4. 补 `load_template` / 资源读取入口搜索的原始输出。

**rev4 = 第 4 次冻结 = 第 3 次 re-freeze**，触发 `WORK_PACKAGE.md.tmpl:9` 的强制停手复核规则：
冻结前必须停手复核计划，**未经用户批准不得冻结**。故 rev4 不得直接派发。

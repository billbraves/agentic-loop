# WP-25 第 4 次 re-freeze 强制停手复核（rev5 前置）

> 复核者 claude-code（编排者，计划面自审）| 2026-09-18
> 规则来源：`WORK_PACKAGE.md.tmpl:9`「第 3 次**及以后** re-freeze：冻结前必须停手复核计划，
> 未经用户批准不得冻结。」
> 前序：`WP-25-plan-review-before-rev4.md`（第 3 次）。本文件是第 4 次，规则连续命中。

## 1. 规则命中确认

`WP-25.status.json` 的 `evidence.refreeze_count = 3`（口径 = brief rev 号），
re-freeze 次数 = rev 号 − 1 = 2 已完成，rev5 将是**第 3 次 re-freeze 之后的第 4 次冻结**，
即第 3 次 re-freeze 之后的又一次。按规则字面（第 3 次及以后）**触发**，且这是本 WP 连续
第二次触发。当前 `state = CHANGES_REQUESTED`，`review.decision = REWORK`（rev4，`f4c6e7d`）。

## 2. 四轮是不是同一个根因

是，而且根因始终在计划面。

| 轮次 | 阻塞项 | 根因归属 |
|---|---|---|
| rev2 | 缺 `Allowed and forbidden paths` 段（任务 #28） | 编排者 brief 缺段 |
| rev3 | B33 定位唯一性、B34 结构完整性 | 判据设计不足 |
| rev4 | **B38** 去规范化引导句、B39 用例内 sha256 断言未落地 | **编排者 brief 缺陷** |

rev4 的复核已自认（`WP-25-review-rev4.md` 末节）：B38 不是执行者的实现缺陷 —— 执行者严格
照「指定修法」三项做完，两环确已收口。**不变式写宽了（INV-P 覆盖 B38），修法清单却按已知
形状收窄（只列定位与结构两类），执行者照清单做就够不着不变式。** 这与 WP-26 的 B35 同型。

## 3. 我这一轮的计划面失误（本次复核的实质产出）

### 失误 1：我在 rev4 复核里给出的「修法方向」未经实测，且实测下不成立

rev4 复核的 B38 修法方向原文是：

> 把三块紧邻的前一行 …… 与所属段标题（当前 `## Dispatch`）一并纳入冻结常量，
> 或断言块起点前 N 字符的规范化文本等于冻结值。

三条候选我这轮全部实测，**没有一条可用**：

| 候选 | A1 紧邻块前插句 | A2 高一行插句 | A3 段首插句 | G 必须保持 GREEN |
|---|---|---|---|---|
| R1 冻结前一非空行 | RED ✅ | **GREEN 逃逸** | **GREEN 逃逸** | 全 GREEN ✅ |
| R2 冻结前 240 字符规范化窗口 | RED ✅ | RED ✅ | **GREEN 逃逸** | 全 GREEN ✅ |
| R3 冻结 h2 段首→块末 envelope | RED ✅ | RED ✅ | RED ✅ | **同段无关 bullet 改写 → RED 误红** |

R1/R2 漏掉插入位置；R3 三条攻击全红，但把**同一 `## Dispatch` 段内无关 bullet 的改写**
也判红（实测 G2 `Freeze product scope … before dispatch.` → `… before any dispatch.` = RED；
G4 同理在 `## Review` 段）。原因是 envelope 覆盖了 1421 / 1826 / 182 字节的**活文本**：
`criteria_sourcing` 的 envelope 有 1847 字节，其中块前 1421 字节全是会正常演进的规范条文。

这正是记忆 `discrimination-without-specificity-is-not-a-fix` 的同一个病，只是尺度小一号：
我上一轮为了拦住 B38 把冻结面推到段级，判别力上去了、特异性掉下来了。

**我第一轮只测了一条 G（无关 *段落* 改标题），就断言 R3 可用。** must-stay-green 集只有
一个元素时，任何过宽的判据都能通过 —— 这是取样不足，不是判据合格。

### 失误 2：我把「处境」当成一个位置，而它是两个独立维度

B38 的攻击面实际是两维，我上一轮混为一谈：

- **维度 A 结构插入**：在块与其所属段之间**新增**一个规范单元（段落 / bullet / 小标题）。
- **维度 B 邻句改写**：不新增任何单元，直接把**紧邻的前一个单元**的文本改成去规范化措辞。

R1/R2/R3 都是「冻结一段文本」的单一手法，同时兼顾两维必然在其中一维上过宽或过窄。
分成两条腿才同时成立：

**R7 = 腿 (i) 结构骨架 + 腿 (ii) 紧邻单元正文**
- 腿 (i)：冻结「h2 段标题 → 块起点」之间的**引导符种类序列**（bullet / 有序项 / 列 0 段落 /
  小标题；空行与缩进续行折叠进其所属单元）。当前值：`HLLLLL` / `HLLLLLL` / `HLL`。
- 腿 (ii)：冻结**紧邻前一个单元**的规范化正文（续行折叠后）。

实测 8 攻击 / 7 无害，零错判：

| # | 变异 | 期望 | R7 |
|---|---|---|---|
| A1 | 列 0 段落，紧邻块前 | RED | RED (skeleton) |
| A2 | 列 0 段落，高一行 | RED | RED (skeleton) |
| A3 | 列 0 段落，段首 | RED | RED (skeleton) |
| A4 | bullet 形态的引导句 | RED | RED (skeleton) |
| A5 | 缩进续行形态的引导句 | RED | RED (prev-unit) |
| A6 | `###` 小标题形态 | RED | RED (skeleton) |
| A7 | 引导句并进前一 bullet 自身正文 | RED | RED (prev-unit) |
| A8 | 段首 bullet 形态 | RED | RED (skeleton) |
| G1 | 无关段改标题 | GREEN | GREEN |
| G2 | 同段无关 bullet 改写（块前） | GREEN | GREEN |
| G3 | 同段追加 bullet（块后） | GREEN | GREEN |
| G4 | `## Review` 段无关 bullet 改写 | GREEN | GREEN |
| G5 | 无关 bullet 换行点挪动 | GREEN | GREEN |
| G6 | **紧邻前一 bullet** 换行点挪动 | GREEN | GREEN |
| G7 | 续行缩进 2→3 空格 | GREEN | GREEN |

G6/G7 是关键：腿 (ii) 冻结的是**规范化后**的正文，所以合法折行与缩进调整不误红，
而 A7 那种改词（插入去规范化措辞）转红。

### 失误 3：我上一轮仍在拿一个覆盖有限形状的判据承诺一个开放族

R7 不是闭合的。实测四条**仍然逃逸**的形状：

| # | 变异 | R7 |
|---|---|---|
| X1 | 引导句并进同段**更早**的某个 bullet | **GREEN 逃逸** |
| X2 | 引导句写进 h2 标题行本身（`## Dispatch (non-binding historical examples)`） | **GREEN 逃逸** |
| X3 | 引导句放在**另一个段**（`## Session start`） | **GREEN 逃逸** |
| X4 | 引导句放在文档前言（`# Orchestrator Protocol` 下） | **GREEN 逃逸** |

X1–X4 与 WP-29 的 E4「远距离去规范化句」是**同一个开放族**，和记忆
`open-world-claims-cannot-be-enumerated` 同型：判据每补一个面，就又漏一个更远的面，
因为「规范力」是渲染后**全文语义**的属性，任何锚定局部区间的机械判据都够不着。

所以 rev5 的正确做法不是继续加面，而是**把承诺的量词改掉**：

- INV-P 保留为**方向性不变式**（供复核者与未来编排者判断，不作为用例的验收量词）；
- 用例承诺降级为**有界**：「块的**紧邻语境**（所属段标题到块起点的结构骨架 + 紧邻前一单元
  正文）任何改动必须转红」，并在 docstring 里明文写出 X1–X4 属于承诺边界之外；
- 远距离去规范化（X2–X4）转为**复核期人工检查项**，写进 `## Review` 的纪律，而不是假装
  用例能拦住。

## 4. rev5 的范围裁定（本次复核的决定）

**收窄，不扩大。** rev5 只做三件事：

1. **B38（有界版）**：按 R7 两条腿实现，自检变异集必须按 INV-P 的**组成维度**生成
   （内容 / 极性 / 结构 / 定位 / 处境-结构插入 / 处境-邻句改写 / 同形新增），
   而不是按缺陷编号列举。A1–A8 与 G1–G7 全部进自检，且 **G6/G7 必须 GREEN**。
2. **B39**：补一条卫生用例，用例内断言活树模板字节同一性（照抄 WP-26 的 `live_before` 做法），
   不用 sha256 常量替代逐字正文比较（与 `:96` 注释不冲突）。
3. **承诺边界明文化**：X1–X4 写进判据 docstring 与 brief，明示不在机械承诺内。

**不做**：不引 Markdown parser（无权威方言，与 WP-29 §2 结论一致）；不整份冻结
（`discrimination-without-specificity-is-not-a-fix`）；不扩 `allowed_paths`。

## 5. 实测证据（编排者本轮独立复现，不采信任何一方转述）

对象 `/Users/admin/vibe/wp25-protocol-disciplines/src/agentic_loop/templates/CLAUDE.md.tmpl`，
判据逻辑从 `tests/test_orchestrator_protocol_disciplines.py` 的 `DISCIPLINE_BLOCK_START/END`
实际取值解析，纯内存变异，活树未写。探针均带 no-op 守卫（`assert mut != T`），
避免「变异没生效」与「真实逃逸」同样打印绿（记忆 `your-own-probe-needs-a-noop-guard`、
`mutations-must-assert-they-changed-something`）。

- `probe.py`  R1/R2/R3 × A1–A3 + G1
- `probe2.py` 线型骨架候选 R5（因 G5 折行误红被否）
- `probe3.py` R7 两条腿 × A1–A8 + G1–G7 → **0 错判**
- `probe4.py` R7 的残余逃逸 X1–X5（X5 被捕，X1–X4 逃逸）

三块的实测位置：`criteria_sourcing` @ 2883（h2 `## Dispatch`）、
`read_face_pinning` @ 3288（同段）、`negative_assertion` @ 4230（h2 `## Review`）。
envelope 长度 1847 / 2379 / 594 字节，块前活文本 1421 / 1826 / 182 字节 —— 这组数就是
R3 特异性为何不足的直接原因。

## 6. 门

- 本文件是 rev5 冻结的**前置**，规则要求**未经用户批准不得冻结**。
- 待办：用户批准后方可写 `WP-25-brief-rev5.md` 并派发。
- 本文件不改 `WP-25.status.json` 的 `state`（仍 `CHANGES_REQUESTED`）。

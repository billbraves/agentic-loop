# WP-28 第 4 次冻结强制停手复核（rev4 前置）

> 编排者 claude｜日期 2026-09-18｜规则来源：本 WP 自己交付的
> `## Re-freeze 规则（编排者冻结前自检）`「第 3 次**及以后** re-freeze：冻结前必须停手
> 复核计划，未经用户批准不得冻结。」
>
> **本文不冻结任何东西。** rev4 brief 须经用户批准方可冻结。

## 1. 规则是否实弹命中

命中。rev1（`7a30f50`）→ rev2 → rev3（`2ba5ef5`）已三次冻结，rev4 为第 4 次，
re-freeze 计数 = 3，落在「第 3 次及以后」区间。这是该规则第二次对本 WP 生效
（rev3 前置为 `WP-28-plan-review-before-rev3.md`）。

规则由本 WP 自己交付、又反复约束本 WP 自己的冻结节奏 —— 这不是巧合，见 §3。

## 2. 本轮两个阻断项的根因是同一个，且是计划面的

B49（换行归一化绕过逐字节冻结）与 B50（T3 无步骤特异 witness）表面无关，
根因是同一条：**我把变异集的生成范围划在了「比较逻辑」上，没划在「判据的完整管线」上。**

判据的实际管线有两段：

```
① 取得输入： Path.read_text(encoding="utf-8")   ← 无任何变异覆盖
② 比较判定： T1/T2/T3/T4/T6/T7 + 诊断分类        ← 21 条变异全在这里
```

rev3 brief §B 把变异集定义为「按 §A.1 的 T1/T2/T3/T4/T6/T7 六个步骤 + T5 兜底逐条生成」。
§A.1 是**比较逻辑**的分解表。于是 21 条变异全部形如「改字符串，喂进比较函数」——
`_mutate_both()` 拿 `read_text()` 的结果做内存字符串变换，
再交给 `_check_both(packaged_text, docs_text)`。**没有一条变异经过 ① 段。**

两个阻断项因此各自成立：

- **B49**：① 段的 universal-newline 折叠从未被攻击过。`LF`→`CRLF` 是唯一一类
  「文件字节变了但 `read_text()` 结果不变」的变异，它恰好落在变异集的盲区里。
- **B50**：`T3 块体切分` 在 §A.1 里是一个独立步骤，但在实现中它没有自己的 code ——
  切分错误只会表现为 body 与常量不等，即 `BODY_MISMATCH`（T4 的 code）。
  §A.1 给了 T3 一行要求却没给它一个 witness，我在写 DoD 时没发现这个缺口。

### 2.1 一个更尖锐的事实：rev3 已经有一条「纯折行」变异，仍然漏了 B49

`test_invn_t4_pure_rewrap_red`（第 659 行）是我在 rev3 brief 里亲自指定的，
口径反转的说明写得很清楚：「纯折行在 rev2 是无害探针（须绿），在 rev3 是变异（须红）」。
它确实红。

但它挪的是**判据已经持有的那个字符串内部**的换行点，不是**文件里的换行字节**。
两者在 `read_text()` 之后无法区分，在 `read_text()` 之前完全不同：
前者改的是 `\n` 的位置，后者改的是 `\n` 本身的编码。
**我用一条看起来正好覆盖换行的变异，买到了一个假的安全感。** 这比完全没测更危险。

## 3. 我的计划面失误

### 失误 1：变异集的生成范围划错了层（B49 的根因）

`mutation-set-follows-criterion-structure` 这条规矩我自己立的，也自认为遵守了 ——
但「判据的组成步骤」被我实际理解成了「判定函数的组成步骤」。判据 = 读 + 判，
只按判的部分分解，读的部分就是结构性盲区。

**修法（写进 rev4 brief）**：变异集必须覆盖判据的**每一段管线**，含输入取得。
输入取得段至少一条变异：只改文件的编码层字节（行尾 / BOM / NFC-NFD），
不改任何字符，须转红。

### 失误 2：给了步骤却没给 witness（B50 的根因）

§A.1 表格里 T3 有一行要求，但 A.2/A.3 的 code 清单里没有 T3 的 code。
DoD:238 写着「七类步骤各有至少一条转红变异，结构化 code 互不相同」——
这条 DoD 与 §A.1 表格自相矛盾，因为 §A.1 根本没有为 T3 分配 code。
**我在同一份 brief 里写下了互相不可能同时满足的两条要求，执行者只能满足其中一条。**

**修法**：rev4 brief 的 §A.1 表格增加一列「witness code」，逐步骤填满；
任何步骤若共用 code，必须在该格写明理由（并相应放宽 DoD 的措辞），不留隐式冲突。

### 失误 3：我的复核按自己的关注点走，没按冻结的 DoD 逐条走

我对「诊断兜底 load-bearing」做了 9 条探针 —— 那是 B44/B45 留下的心结。
DoD:238 这条没人攻击过的要求，我读过去了。第二签名一遍就抓到。
这是 `review-the-dod-not-your-own-concerns` 的实弹案例。

**修法（超出本 WP，见 §5）**：复核报告须逐条列出 DoD 条目及其「已复现 / 未复现」，
不允许只报自己关心的维度。

## 4. 实测确证（编排者独立复现，不采信任何一方转述）

### 4.1 B49：文件字节已变，判据全绿

两份模板同步 `LF`→`CRLF`，冻结常量不动：

```text
bytes changed:                     True
read_text(CRLF) == read_text(LF):  True
codes via read_text path :         []                    ← GREEN
codes if newlines kept   :         ['SECTION_MISSING']
```

`SECTION_MISSING` 而非 `BODY_MISMATCH`：`_heading_line_matches` 的正则是
`(?m)^<title>$`，`$` 在 `\r\n` 前不匹配（`\r` 挡在行尾），故两个标题的精确匹配数
都从 1 掉到 0。`_h2_line_matches` 的宽松正则仍匹配到 11 行 —— 即标题还在，只是不再
逐字节等值。保留字节时判据反应剧烈，经 `read_text()` 后毫无反应。

**影响面**：一次 `.gitattributes` 调整、一次 Windows 检出、一次编辑器改 EOL，
就能让两段冻结文字整体失效而判据保持全绿，且 oracle 无任何 diff ——
这正是 INV-N4 承诺要拦住的情形。

### 4.2 B50：T3 的 witness 与 T4/T5/T6 完全重叠

```text
T3 = ['BODY_CLAUSE_MISSING', 'BODY_MISMATCH', 'SECTION_ANCHOR_MOVED']
T4 = ['BODY_CLAUSE_MISSING', 'BODY_MISMATCH']
T5 = ['BODY_MISMATCH']
```

三个 code 分属诊断分类、T4/T5 兜底、T6，无一特异表示「块体被新 `## ` 截断」。

### 4.3 变异集确实全部绕开读路径

`_mutate_both()` 对 `read_text()` 的返回值做字符串变换，
`_check_both(packaged_text, docs_text)` 收字符串而非路径。
21 条变异中经过文件读取的次数：**0**。仅正向控制
`test_invn_positive_control_clean_template` 读真实文件，而它读的是未变异的文件。

## 5. 应固化为常规的流程改动（超出本 WP）

1. **变异集覆盖管线，不只覆盖判定**（失误 1）—— 候选进 `AGENTS.md` 判据自检条目。
2. **复核报告须逐条对账冻结 DoD**（失误 3）—— 候选进 `CLAUDE.md` Review 段。
3. **brief 内部一致性自检**：§A 的步骤表与 §DoD 的计数/命名要求不得隐式冲突（失误 2）。
   这与任务 #23（学习回边机械化）同源，可并入。

## 6. rev4 的范围裁定（待用户批准）

**主张：rev4 只修这两个阻断项，不扩范围。**

- 判据输入改为 `read_bytes()`（或显式 `newline=''`），冻结常量相应为 bytes；
  新增 T0 段变异：只改编码层字节（行尾），须转红。
- T3 增设独立硬 code（建议 `SECTION_BODY_TRUNCATED`），T3 用例显式断言；
  `BODY_MISMATCH` 保留为 T4/T5 承重兜底。
- §A.1 表格补「witness code」列，消除与 DoD:238 的隐式冲突。
- **不动** INV-N1/N3/N4 的承诺边界，**不碰** WP-29 的 `active_embedding`。
  allowed_paths 保持 rev3 的 3 个文件。

**不主张的**：不因为「已经第 4 次」就降低标准放行 rev3。B49 使本 WP 的核心承诺
（受保护字节变化必然可见）在一类常见的日常操作下不成立，这不是余量问题。

## 7. 门

- [x] 停手复核已产出（本文）
- [x] 两个阻断项已由编排者独立复现
- [ ] **用户批准 rev4 范围裁定** ← 当前卡点
- [ ] rev4 brief 冻结并重派

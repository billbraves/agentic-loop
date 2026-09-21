# WP-28 (rev4): 把受保护表示的冻结判据补齐到判据的完整管线（读 + 判）

> 冻结日期 2026-09-18 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 所属 Plan：PLAN-01（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> **本 WP 第 4 次冻结（rev4），re-freeze 计数 = 3，「第 3 次及以后停手复核」规则第二次实弹命中。**
> 前置门已完成：`WP-28-plan-review-before-rev4.md`（停手复核）+
> `WP-28-consult-codex-rev3-verdict.json`（第二签名判 REWORK，两项编排者已复现）+ **用户已批准 rev4 范围裁定**。
> rev4 取代 rev3（`WP-28-brief-rev3.md`，sha256 `c14782ed…`）。
> **rev3 交付 `2ba5ef5` 保留不动，在其之上继续提交。**

## 目标（一句话）

rev3 的判据只攻击了「比较判定」这一段，`Path.read_text()` 取输入那一段从未被攻击 ——
补齐这个盲区（B49），并给 T3 一个属于自己的 witness code（B50），使 INV-N1/INV-N4
在文件字节层面真正成立。

## 本 rev 的验收标的（两个阻断项，各自封闭）

### B49 —— 读路径的换行归一化绕过「逐字节」冻结

`_mutate_both()` 与所有 T1–T6 用例经 `Path.read_text(encoding="utf-8")` 取输入。
Python universal-newline 把 `CRLF` 折成 `LF`，因此存在一类变异：**文件字节已改，
`read_text()` 结果不变，冻结常量不动，判据返回 `[]`（GREEN）**。

编排者实测（两份模板同步 `LF`→`CRLF`）：

```text
bytes changed:                     True
read_text(CRLF) == read_text(LF):  True
codes via read_text path :         []                    ← GREEN，逃逸
codes if newlines preserved:       ['SECTION_MISSING']
```

`SECTION_MISSING` 的成因：`_heading_line_matches` 用 `(?m)^<title>$`，`$` 在 `\r\n`
之前不匹配（`\r` 挡在行尾），两个标题的精确匹配数从 1 掉到 0。
注意 `_h2_line_matches` 的宽松正则在 CRLF 下仍匹配 11 行 —— 标题还在，只是不再逐字节等值。

**这违反**：INV-N1（完整 body 与冻结常量逐字节相等）、INV-N4（任何受保护字节变化必须
在测试 oracle 留下可审查 diff）、以及 rev3 DoD 的「T4 用真逐字节相等」。

**注意 `TEMPLATE_*.read_bytes()` 已在第 158 行用于副本比较**，故 T7（副本同一）不受本项影响；
本项的范围是 T1–T6 的输入取得路径。

**一个已存在但买到假安全感的用例**：`test_invn_t4_pure_rewrap_red`（rev3 第 659 行）
挪的是**判据已持有字符串内部**的换行点，不是**文件里的换行字节**。两者在 `read_text()`
之后不可区分。**不得**以该用例已存在为由认为换行已被覆盖。

### B50 —— T3（块体切分）没有属于自己的 witness

实测三个步骤的 witness 集合：

```text
T3 = ['BODY_CLAUSE_MISSING', 'BODY_MISMATCH', 'SECTION_ANCHOR_MOVED']
T4 = ['BODY_CLAUSE_MISSING', 'BODY_MISMATCH']
T5 = ['BODY_MISMATCH']
```

三个 code 分别属于诊断分类、T4/T5 兜底、T6，**无一特异表示「块体被新 `## ` 行截断」**。

**这违反** rev3 brief §E② 与 rev3 DoD:238「§B 七类步骤各有至少一条转红变异，
结构化 code 互不相同」。

**根因（编排者的失误，不是执行者的）**：rev3 §A.1 表格给了 T3 一行要求却没给它分配
witness code，同一份 brief 里的 DoD 又要求各步骤 code 互不相同 —— 两条不可能同时满足。
rev4 的 §A.1 表格因此补上「witness code」一列（见下），不再留隐式冲突。

## 范围

### allowed_paths（与 rev3 相同的 3 个文件，不扩）

- `tests/test_wp_template_dispatch_lint.py`
- `docs/agentic/templates/WORK_PACKAGE.md`
- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`

### forbidden_paths（其余全部）

特别地，**不得**改：`src/agentic_loop/contract_render.py`（含 `CONTRACT_TEMPLATE_VERSION`，
须保持 `"6"`）、`src/agentic_loop/init_cmd.py`、`pyproject.toml`、任何其他 `tests/*.py`、
`.agentic/config.toml`、任何 `docs/plans/**`。

### 明确不在本 rev 范围内

- **不动 INV-N1 / INV-N3 / INV-N4 的承诺边界**。判据源码顶部的边界声明（module docstring）
  除下述一处外**不得改写**：B49 修好后，「块内 raw text 逐字节」这一承诺从
  「`read_text()` 之后的字符」升级为「文件字节」，docstring 须如实反映这一点。
- **不碰 WP-29 的标的**（`active_embedding` / 活动渲染语义）。三条已声明为边界的逃逸
  （整份文档注释外包、文档开头未闭合 `<!--`、`## 附注` 内未闭合围栏）**仍应 GREEN**，
  它们是声明的边界而非漏测。**把它们改红即为超范围。**
- 不重构判据结构、不改硬判据与诊断分类的分离方式、不改 `_mutate_both` 的 no-op guard 契约。

## 输入

- 本轮起点 commit：`2ba5ef5`（rev3 交付，**保留不动，在其之上提交**）
- 停手复核：`WP-28-plan-review-before-rev4.md`（§2 根因、§4 实测、§6 范围裁定）
- 第二签名原文：`WP-28-consult-codex-rev3-verdict.json`（`raw_verbatim` 含两项的建议修法）
- 前一轮 brief：`WP-28-brief-rev3.md`（§A.1 / §B 的步骤定义，rev4 在其上增量）
- 判据形状的设计依据：`WP-28-consult-codex-shape.md` §2/§3/§4

## 交付物清单

仅 `tests/test_wp_template_dispatch_lint.py` 一个文件的改动即可满足本 rev；
若 docstring 的承诺措辞需同步（见「明确不在本 rev 范围内」第 1 条），亦在该文件内。
两份模板文件在 allowed_paths 内但**本 rev 预期无需修改** —— 若你认为必须改，
须在报告里写明理由（改模板会动到冻结常量，属于 INV-N4 要求「可见」的那类变更）。

## Acceptance tests

### A. 判据的管线分解（rev4 的核心修正：变异集按【管线】生成，不只按【判定逻辑】生成）

rev3 的失误是把变异集的生成范围划在 §A.1 的比较逻辑分解表上。判据实际有两段，
**两段都须被攻击**：

```
① 取得输入： 文件字节 → 判据持有的表示     ← rev3 覆盖数 0，本 rev 必须补
② 比较判定： 表示 → witness codes          ← rev3 的 T1..T7
```

**A.1 硬不变式（决定放行，各自独立运行，任一失败即红）**

| 段 | 步骤 | 要求 | witness code |
|---|---|---|---|
| ① | **T0 输入保真** | 判据持有的表示必须是**文件字节**的忠实表示；编码层字节（行尾 / BOM / NFC-NFD）的任何改动都不得在取输入阶段被抹平 | 由 ②段各 code 承担（T0 本身不产 code，它保证 ②段看得见字节 —— 见 A.4） |
| ② | T1 定位唯一 | 两个标题各须**恰好出现 1 次**，逐字节精确匹配。0 次 → `SECTION_MISSING`；>1 次 → `SECTION_NOT_UNIQUE` | `SECTION_MISSING` / `SECTION_NOT_UNIQUE` |
| ② | T2 同形副本 | 存在 NFKC 归一化后与目标标题相等、但字节不等的 `## ` 行 | `SECTION_HOMOGLYPH_DUPLICATE` |
| ② | **T3 块体切分** | body = 标题后一行 至 下一个 `## ` 行之前（含其间空行），逐字节保留。**块体边界被移动**（如块内插入新 `## ` 行使 body 被提前截断）须产出**属于 T3 自己的** code | **`SECTION_BODY_TRUNCATED`（本 rev 新增）** |
| ② | T4 块体等值 | body 与冻结常量**逐字节相等**。**不得**使用任何空白折叠或换行归一化 | `BODY_MISMATCH` |
| ② | T5 兜底 | 诊断分类识别不出任何形状时，`BODY_MISMATCH` 单独即为合格的红 | `BODY_MISMATCH`（无诊断 code） |
| ② | T6 位置锚点 | 每块的前 / 后一个 `## ` 标题与冻结值相等（首块前锚点为 `<BOF>`） | `SECTION_ANCHOR_MOVED` |
| ② | T7 副本同一 | 两份模板逐字节相等 | `REPLICA_MISMATCH` |

**A.2 诊断分类（不决定放行，仅在 `BODY_MISMATCH` 已红后对 diff 二次归因）**

沿用 rev3：`BODY_CLAUSE_MISSING` / `BODY_POLARITY_CHANGED` / `BODY_INDENT_CODEBLOCK` /
`BODY_LIST_SPLIT` / `BODY_QUANTITY_PHRASE_CHANGED` 等。

**硬要求（沿用 rev3，不得削弱）**：分类识别不出任何形状时 `BODY_MISMATCH` 单独兜底即合格；
分类缺失**绝不**构成放行依据。

**A.3 T3 与 T4 的 code 关系（本 rev 必须明确处理的一点）**

块体被截断时，body 与冻结常量必然也不等，故 `BODY_MISMATCH` 会与
`SECTION_BODY_TRUNCATED` **同时**出现 —— 这是允许的（rev3 §A.3 已定「一个变异可以产生
多个 witness」）。要求是：**T3 用例必须显式断言 `SECTION_BODY_TRUNCATED` 在场**，
使红可归因到 T3 而非仅归因到 T4。反向要求同样成立：**T4 / T5 的变异不得产出
`SECTION_BODY_TRUNCATED`** —— 否则该 code 没有区分力，等于换个名字的 `BODY_MISMATCH`。

`SECTION_BODY_TRUNCATED` 是**硬 code**（进 A.1，独立决定红），不是诊断分类，
因此**不得**加入 `DIAGNOSTIC_CODES`。注意 rev3 的四条兜底用例断言
`not (codes & DIAGNOSTIC_CODES)`，若你把新 code 误放进该集合，那四条会连带失效。

**可达性（编排者已实测，供你参考，不强制用这个判法）**：截断与删句在结构上可区分 ——
切分被截断时 body 是冻结常量的**严格前缀**，而删一条分句不是。实测
`base body len = 93`（= 冻结常量长度）、`T3 = 50`（严格前缀）、`T4 = 81`（非前缀）。
你可以用这个性质，也可以用别的判法（如「body 内出现了 `## ` 行」或「切分终止于
非预期锚点」），只要 T3 / T4 的 code 确实分得开。

**A.4 T0 的判定方式（关键，请按此实现，不要自行发明）**

T0 不产自己的 code。它的正确性由「**编码层字节变异必须被 ②段看见**」来证明：

1. 判据取输入改为**以文件字节为事实源** —— `Path.read_bytes()`，或
   `open(..., newline="")` 之类**不做 newline translation** 的显式读取。
   两种都可，选一种并在报告里说明。
2. 冻结常量与比较口径相应对齐（若以 bytes 为事实源，冻结常量须为 UTF-8 bytes；
   若解码但禁用 newline translation，则常量仍可为 str）。**两种路线都必须使
   `\r\n` 与 `\n` 可区分。**
3. 新增变异 **M-T0**：两份模板**同步**把全部 `\n` 改为 `\r\n`，**不改任何字符、
   不动冻结常量**，判据必须转红。
   - 该变异须经 `_mutate_both()` 的统一 no-op guard（`assert mutated != original`）。
   - 因两份同步改动，`REPLICA_MISMATCH` **不得**在场 —— 否则红来自副本不一致而非
     字节保真，是归因错层（这正是 rev3 §C 已立的规矩，本 rev 沿用）。
   - 断言其具体 witness code：按当前实现应为 `SECTION_MISSING`（`$` 不匹配 `\r\n`）。
     **若你的修法使该 code 变为别的值，以实测为准并在报告里写明**，但不得只断言
     「codes 非空」—— 那是真空断言。
4. **再加一条负面对照 M-T0b**：只改**一侧**模板的行尾。此时 `REPLICA_MISMATCH`
   必须在场（T7 生效）。这条是为了证明 M-T0 的红确实来自 T0/T1 而非 T7。

### B. 变异集（rev4 = rev3 的 21 条 + 本 rev 新增）

**沿用 rev3 全部 21 条，一条不删。** 它们当前全绿（29 passed 含正向控制与既有 dispatch_lint 用例），
你的改动**不得**使其中任何一条变黄或变红失效。

新增：

- **M-T0**（①段，1 条）：两份模板同步 `\n`→`\r\n`，不改字符、不改常量 → 必须红，
  `REPLICA_MISMATCH` 不在场。
- **M-T0b**（①段负面对照，1 条）：只改一侧行尾 → 必须红且 `REPLICA_MISMATCH` 在场。
- **M-T3**（②段，改造 rev3 第 569 行的 `test_invn_t3_body_slicing_truncated_red`）：
  增加 `assert SECTION_BODY_TRUNCATED in codes`。
- **M-T3-neg**（②段，1 条）：一条 T4 类变异（如删一条冻结分句）须断言
  `SECTION_BODY_TRUNCATED not in codes`，证明新 code 有区分力。

**可选加强（不强制，加了在报告里说明）**：BOM 变异（文件开头加 `﻿`）、
NFC↔NFD 变异（把带音标或全角字符换成等价的分解/合成形式）。二者同属「编码层字节改动」，
若你的修法正确它们应当也红；若某一条不可攻击（例如模板内无可分解字符），
**须在报告里写明理由** —— 这是本 WP 自己要落成的规范条目。

### C. 沿用 rev3 的两条硬要求（不得削弱）

1. **空操作变异禁止**：每条变异必须断言 `mutated != original`。
   一条空操作变异与一条真实逃逸在测试结果上完全无法区分。
2. **副本混淆归因禁止**：T1–T6（含 M-T0）的变异须**同步施加于两份模板**，
   使 `REPLICA_MISMATCH` 不在场；只有 T7 / M-T0b 单侧变异。
   否则 `REPLICA_MISMATCH` 会出现在每一条变异的 witness 里，任何步骤的红都无法与副本同一区分。

### D. 零回归基线（在本 WP 自己的起点 `2ba5ef5` 实测，编排者已跑）

```text
targeted (tests/test_wp_template_dispatch_lint.py):  29 passed
full suite:                                          4 failed / 628 passed / 4 skipped
```

4 条 failed 全部在 `tests/test_finalize_merge_triple_sign.py`（既有环境失败，
`git checkout -q main` 在工作树内失败所致）—— **不得修，不得跳过，不得动那个文件**。

交付后全量应为 `4 failed / (628 + 新增用例数) passed / 4 skipped`，
且 failed 集合逐条同上。**请在报告里给出这个算术**（`新 passed − 628 = 新增用例数`）。

### E. 用例契约要求（沿用 rev3）

- ① **原因特异 witness**：断言**结构化 code**。**不许「rc != 0」/「assert 抛了异常」式真空断言。**
- ② **每个步骤的 code 可归因**：A.1 表格的 witness code 列即为口径。
  共用 code 的情形已在表格与 A.3 写明，不再有隐式冲突。
- ③ 跨 Python 版本：3.11 必须通过；3.13 / 3.14 若可用亦须通过
  （`uv run --with pytest --no-project`）。

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_wp_template_dispatch_lint.py`
- `docs/agentic/templates/WORK_PACKAGE.md`
- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`

**forbidden_paths**：以上三者之外的全部路径。特别包括
`src/agentic_loop/contract_render.py`、`src/agentic_loop/init_cmd.py`、`pyproject.toml`、
`tests/` 下其他任何文件、`.agentic/config.toml`、`docs/plans/**`。

**风险与隔离**：在 worktree `/Users/admin/vibe/wp28-norms-into-template`、
分支 `feature/wp28-norms-into-template` 内工作。禁 merge / 禁 push / 禁切分支。
禁跨 worktree 写主区（含主区的 `docs/plans/**` 与任何 status JSON）。

## Completion definition

- [ ] **B49 已修**：判据以文件字节为事实源（`read_bytes()` 或禁用 newline translation 的显式读取），
      并在报告里说明选了哪条路线
- [ ] **M-T0 在场且红**：两份模板同步 `\n`→`\r\n`、不改字符、不改冻结常量 → 转红，
      断言具体 witness code（非「codes 非空」），且 `REPLICA_MISMATCH` 不在场
- [ ] **M-T0b 在场且红**：只改一侧行尾 → 转红且 `REPLICA_MISMATCH` 在场
- [ ] **B50 已修**：新增硬 code `SECTION_BODY_TRUNCATED`，**未**加入 `DIAGNOSTIC_CODES`
- [ ] **T3 用例显式断言** `SECTION_BODY_TRUNCATED in codes`
- [ ] **区分力已证**：至少一条 T4 类变异断言 `SECTION_BODY_TRUNCATED not in codes`
- [ ] **A.1 表格的 witness code 列逐步骤兑现**：T1/T2/T3/T4/T6/T7 各有至少一条转红变异，
      其 code 与表格一致；共用 code 仅限表格与 §A.3 已写明的情形
- [ ] **rev3 的 21 条变异一条不删且全绿**，四条兜底用例（断言 `not (codes & DIAGNOSTIC_CODES)`）
      仍在承重
- [ ] **边界声明与实现一致**：module docstring 除「raw text 逐字节」升级为文件字节层这一处外未改写；
      三条已声明为边界的逃逸（整份文档注释外包 / 文档开头未闭合 `<!--` / `## 附注` 内未闭合围栏）
      **仍 GREEN**
- [ ] **`CONTRACT_TEMPLATE_VERSION` 仍为 `"6"`**，`contract_render.py` / `init_cmd.py` / `pyproject.toml` 零 diff
- [ ] 零回归：全量 `4 failed / (628 + 新增用例数) passed / 4 skipped`，failed 集合逐条同 §D，
      **报告里给出算术**
- [ ] 3.11 通过；3.13 / 3.14 若可用亦通过
- [ ] 无 forbidden_paths 写入；无 merge / push / 切分支；无跨 worktree 写主区
- [ ] 执行报告按 `AGENTS.md` §6.C 格式输出，含上述算术与「选了哪条读取路线」的说明

## 风险声明

| 维度 | 取值 |
|---|---|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **`test_invn_t4_pure_rewrap_red` 不算换行覆盖**。它挪的是判据已持有字符串内部的
   换行点，与文件里的换行字节在 `read_text()` 之后不可区分。**不得**以它已存在为由
   跳过 M-T0。
2. **`read_bytes()` 已在第 158 行用于副本比较**（T7），所以 T7 从一开始就不受 B49 影响。
   本 rev 要改的是 T1–T6 的输入路径，别误以为整个文件都还在用 `read_text()`。
3. **`SECTION_BODY_TRUNCATED` 不要放进 `DIAGNOSTIC_CODES`**。rev3 有四条兜底用例断言
   `not (codes & DIAGNOSTIC_CODES)`，误放会让它们连带失效 —— 而那四条正是证明
   「分类缺失不构成放行」的承重用例。
4. **三条边界逃逸必须保持 GREEN**。把它们改红看起来像「加强」，实际是把 WP-29 的标的
   偷进本 WP，属超范围，会被判 REWORK。
5. **4 条既有 failed 不得修**。它们在 base 上即已红（工作树内 `git checkout -q main` 失败），
   属环境问题，修它们等于改 forbidden_paths 下的文件。
6. **口径提醒**：rev3→rev4 没有口径反转。rev3 已把「纯折行」定为须红的变异，
   rev4 只是把「换行字节」这一层补上，两者方向一致。
7. **规范条目的自指**：本 WP 交付的规范条目要求「变异集按判据自身的组成步骤生成，
   不得按已知缺陷清单枚举；某步骤不可攻击须写明理由」。rev4 的 B49 正是因为
   「组成步骤」被理解成「判定逻辑的步骤」而漏掉了「取输入」这一段。
   **你的变异集须覆盖判据的每一段管线** —— 这条要求本身就是本 WP 的标的。

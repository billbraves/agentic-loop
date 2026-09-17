# WP-28 (rev2): 把两条编排规范从任务列表落成机械可检的模板条目（INV-N）

> 冻结日期 2026-09-18 | 编排者 claude | 执行者 kimi。
> 所属 Plan：PLAN-01（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 冻结与 re-freeze 的规则见本仓 `docs/agentic/templates/WORK_PACKAGE.md`「Re-freeze 规则」一节。
> 本 WP 第 2 次冻结（rev2），re-freeze 计数 = 1，「第 3 次及以后停手复核」规则不命中。
> 但本轮仍按用户批准另做了一件事：把「冻结前自检的变异集也须按判据组成步骤生成」
> 写入 §F 并对编排者自己生效（理由见 §F 首段）。

## 目标（一句话）

把两条目前只存在于任务列表与复核文档里的编排规范 —— ①「判据自检的变异集按判据组成步骤生成」
②「同一 WP 第 3 次及以后 re-freeze 强制停手复核计划」—— 写进 WP brief 模板并配可转红的用例，
使其成为 AGENTS.md §10 意义上的持久规则，而不是靠编排者记性执行的口头约定。

## 本 rev 的验收标的是不变式，不是缺陷编号

> **INV-N（规范持久化不变式）**：这两条规范一旦落入模板，任何**削弱其规范力**的模板改动 ——
> 无论通过删正文、改极性（必须/不得 → 可以/建议）、改结构（缩进成 code block、插空行断开列表）、
> 改定位（挪走标题、插入同形 decoy 块）、还是改处境（在块前插入「以下仅为历史示例，不具规范
> 约束力」这类去规范化引导句）—— 都必须使测试转红，且转红只能通过修改测试文件里的冻结常量来解除。
> 即：**给削弱开绿灯，必须在测试文件的 diff 里可见。**

这条与 WP-25 的 INV-P、WP-26 的 INV-B 同型，但本 WP 是**第一个从立项起就按不变式冻结**的 WP。
若你在实现中发现本 brief 未枚举的第六类逃逸（例如 Unicode 同形字、HTML 注释包裹、
把整节搬进 deprecated 附录），一并钉住并在报告里点名；不要因为 brief 没列就放过。

## 范围

**allowed_paths**（3 个文件）：

- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`
- `docs/agentic/templates/WORK_PACKAGE.md`
- `tests/test_wp_template_dispatch_lint.py`

**forbidden_paths**：

- `src/agentic_loop/contract_render.py` —— **`CONTRACT_TEMPLATE_VERSION` 不要 bump**。
  理由：`WORK_PACKAGE.md.tmpl` 是 `init_cmd._REFERENCE_TEMPLATES` 里的 reference skeleton，
  含 0 个 `string.Template` 占位符，不在 `contract_render` 的渲染目标内（渲染目标是
  AGENTS.md / CLAUDE.md / OPERATING_MODEL.md 三份）。改它不构成契约模板漂移。
  编排者已实测：`grep -c '\$' WORK_PACKAGE.md.tmpl` = 0。
- `src/agentic_loop/templates/` 下其余全部 `.tmpl`（含 `CLAUDE.md.tmpl`、`AGENTS.md.tmpl`、
  `OPERATING_MODEL.md.tmpl`）
- `AGENTS.md`、`CLAUDE.md`、`docs/agentic/OPERATING_MODEL.md` —— 主仓活树这三份当前有
  **未提交的本地改动**（provider 重命名，与本 WP 无关）。零行 diff，不要顺手提交、不要 revert。
- `src/agentic_loop/wrappers/` 下全部 `.sh` —— 尤其 `dispatch_lint.sh`：
  编排者已实测**现行模板与候选模板都过 lint**，即 lint 管不到新条目，判据必须落在 pytest 侧。
  不要试图给 dispatch_lint.sh 加新的 required section。
- `tests/test_finalize_merge_triple_sign.py` —— 那 4 条是既有环境失败（本机
  `git init.defaultBranch=master` 与 fixture 的 `git checkout main` 冲突），**不要修**
- `tests/test_init_contract.py` —— 它引用 `docs/agentic/templates/WORK_PACKAGE.md`
  但只检存在性，不应因本 WP 改动
- `docs/plans/`（含本 brief 自身）、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

## 输入

- 被审树：worktree `/Users/admin/vibe/wp28-norms-into-template`，分支
  `feature/wp28-norms-into-template`，从 `plan/2026-09-13-parallel-throughput` HEAD 起。
- 两条规范的来源（**只作为规范的出处，不是验收标的**）：
  - 第 4 项变异规则：`WP-25-plan-review-before-rev4.md` §3 失误 2；根因见
    `WP-25-review-rev4.md` B38 与 `WP-26-review-rev4.md` B35 —— 两处同型：
    不变式写宽、修法清单按已知缺陷形状收窄，执行者照清单做就够不着不变式。
  - re-freeze 停手规则：原任务 #24。**本 WP 按用户本轮决定把它扩展到「第 3 次及以后」**，
    因为 WP-25/WP-26 都已在走第 4 次 re-freeze，而原规则字面只覆盖第 3 次。
- 现行模板落点（编排者实测）：`## Acceptance tests` 一节已有 oracle 三项（WP-24 落入），
  新增的是**第 4 项**；`## 目标（一句话）` 之前没有任何 `## ` 段，是 re-freeze 一节的插入点。

## 交付物清单

- [ ] `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 新增 `## Re-freeze 规则（编排者冻结前自检）`
      一节（插在 `## 目标（一句话）` 之前）+ `## Acceptance tests` 段内 oracle 第 4 项
- [ ] `docs/agentic/templates/WORK_PACKAGE.md` —— 与上一份**逐字节同一**
      （现有 `test_templates_byte_identical` 已守，勿破）
- [ ] `tests/test_wp_template_dispatch_lint.py` —— 新增 INV-N 的判据与按组成步骤生成的变异集

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。

### A. 判据（新增，必须落在 pytest 侧）

判据须切出两块并逐字锁定，六个面各自把守。**编排者已实测该判据形式可实施**（见 §F），
你可另择实现，但六个面必须都被钉住：

| 面 | 要求 |
|---|---|
| S1 定位 | 两个标题各须**恰好出现 1 次**，不成立即判红且措辞点明「边界不唯一」。不得用 `text.index()` 取首个 |
| S2 内容 | 冻结常量逐字出现在对应块内（归一化空白后比对），缺失即红并点名缺哪条 |
| S3 极性 | 冻结常量**必须包含承载极性的分句本身**（如「冻结前必须停手」「不得按已知缺陷清单枚举」），使「必须→可以」「不得→建议不」这类改写落进 S2 的网 |
| S4 结构 | 冻结分句所在行不得缩进 ≥4 空格（会变成 code block），不得被空行断开所属列表 |
| S5 处境 | 每块**紧邻前一非空行**纳入冻结常量，拒绝在块前插入去规范化引导句 |
| S6 同形 | 块前不得存在同形完好副本（由 S1 的唯一性覆盖，但须有独立变异证明）。同形判定须**先于** S5，否则诱饵块把 S5 的前一行顶掉，红的归因会落到处境面 |
| S4b 渲染语义 | 块不得落在未闭合代码围栏内，块内不得出现围栏。冻结分句一字未改也可能因整节被围栏成 code block 而失去规范力 |
| S5b 块内处境 | 块**内部**任意位置不得出现去规范化引导语（「仅供参考」「不作要求」「历史遗留」「不再要求」「不具规范约束力」「仅为示例」「不作强制」「可不遵守」等）。S5 只守块前一行，块内不设防即等于没守 |
| S7 数量口径 | 治理冻结清单的**数量词**本身须冻结（`oracle 校验四项证据`），且块内编号条目数须等于该数量。数量词被改回「三项」时第 4 项仍在但沦为死条文 |

### B. 变异集（按判据的组成步骤生成，不按缺陷清单）

**本 WP 的自检必须自食其果**：变异集按上表六个面逐条生成，每面至少一条，全部转红。
编排者实测的 7 条（可照用，也可加强）：

1. S1/S6 —— 在 `## Re-freeze 规则` 块前插入该块的完好副本 → 须红，witness 点明「边界不唯一」
2. S2 —— 删掉 `不得取代不变式成为标的。` → 须红并点名该条
3. S3 —— `冻结前必须停手` → `冻结前可以停手` → 须红
4. S3 —— `不得按已知缺陷清单枚举` → `建议不按已知缺陷清单枚举` → 须红
5. S4 —— `- 验收标的必须写成**不变式**` 缩进 6 空格成 code block → 须红
6. S5 —— 在 `## Re-freeze 规则` 标题前插入 `以下仅为历史示例，不具规范约束力：` → 须红
7. S5 —— 同形攻击 `## Acceptance tests` 块 → 须红

**若某一面你确实构造不出变异，须在报告里写明为什么该面不可攻击，不得默认略过。**
这条正是本 WP 要落入模板的第 4 项规则，请按它自己的要求执行。

**rev1 的三处逃逸（必须堵住，但不要只堵这三处）**：rev1 的判据六个面里有三个名义存在、
实际不设防。编排者按组成步骤自行生成 8 条变异，其中 3 条全绿：

- B40（S4b）：标题后插一行 ``` 把整节围栏成 code block → 冻结分句一字未改、缩进未变、
  列表未断，判据全绿，但渲染后整节降级为示例文本
- B41（S5b）：去规范化引导句插在**块内**（如「（下列第 4 项为历史遗留，不再要求）」）→
  S2/S3/S4/S5 全过，判据全绿，第 4 项规范力被剥掉而测试 diff 为空
- B42（S7）：`oracle 校验四项证据` 的数量词未进任何冻结常量，改回「三项」→ 判据全绿，
  模板自我矛盾，第 4 项沦为死条文
- B43（次要）：`_section_block()` 用了本 brief 明禁的 `text.index()`。当前未逃逸只因 S1
  的唯一性检查先判红；但 S1 用逐行精确匹配、`index()` 用子串匹配，两者匹配面不同，
  是靠执行顺序侥幸成立。改为 `re.finditer` 枚举，与 S1 共用同一匹配面。

**注意这四条是按面归类给你的，不是让你按编号打补丁。** rev2 的变异集必须按上表**八个面**
重新生成一遍（含新增的 S4b / S5b / S7），不是在 rev1 的 7 条上追加 4 条。
按编号补，只买到这四个形状；按面生成，才买到同族的未知形状。

### C. 无害探针（必须仍 GREEN，证判据不过紧）

1. H1 纯折行：把第 4 项正文的换行点挪动（不改字）→ 须绿
2. H2 无关段落编辑：改 `<这个 WP 要交付什么>` 占位符 → 须绿

### D. oracle 三项 + 第 4 项（对每条负面用例）

- ① 正向可达控制：未变异的真实模板必须 PASS（证判据非在干净模板上就红）
- ② 原因特异 witness：断言**精确措辞**，且每个面的措辞互不相同，使红的来源可归因到具体面。
  **不许「rc != 0」/「assert 抛了异常」式真空断言。**
- ③ 代表性禁止变异转红：即 §B
- ④ 变异集按判据组成步骤生成：即 §B 的生成方式本身

### E. 反向差分（方向别写反）

新增用例断言的是「判据转红」，所以在**旧实现**（本 WP 之前的 HEAD，模板尚无这两条）上
新增用例应当 **FAIL**（要的红没出现，因为冻结常量在模板里根本不存在），
在**新实现**上 **PASS**。报告须含两次实测输出。

### F. 编排者冻结前实测（供你确认起点，非转述）

**本节的规则（rev2 新增，对编排者自己生效）**：编排者的冻结前自检，其变异集也必须
**按判据的组成步骤生成**，不得按上一轮的缺陷清单生成。理由是实测得来的：rev1 冻结前
我实测过 7 条变异全红才放行，但那 7 条是按我当时想到的形状造的；复核时我改按组成步骤
重造 8 条，立刻漏出三个面。**冻结前自检与执行者自检受同一条规则约束**，否则就是用一个
自己没做到的判据去要求执行者做到。

rev2 冻结前实测（判据原型 `probe2.py`，八个面）：

- 正向对照：真实模板（`b34deb9`）→ `POSITIVE CONTROL: GREEN`（证判据非在干净模板上就红）
- 变异集**按八个面生成，共 18 条，全红，0 逃逸**：
  S1 定位 2 条（诱饵副本 / 标题重命名）、S2 内容 2 条、S3 极性 3 条、
  S4 结构 2 条（缩进 / 空行断开）、**S4b 渲染 3 条**（标题后开围栏 / 块前留未闭合围栏 /
  块内插围栏）、S5 处境 1 条、**S5b 块内处境 2 条**、S6 同形 1 条（全角 Ａ）、
  **S7 数量口径 2 条**（四项→三项 / 删第 4 项本体）
- 无害探针 3 条全绿：纯折行、无关占位符改写、块外新增无关小节
- **归因逐面正确**：每条变异的首条 witness 前缀与其所攻击的面一致（`mis_attributed=[]`）

实测中判据原型自己暴露的两个问题（请勿重蹈，这正是按面生成的价值）：

1. **极性常量不得跨行**：初版把 `不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由`
   整句作为极性常量，而该句在模板里跨两行 → **纯折行的无害探针被判红**（假阳性）。
   极性常量必须是单行内的单个分句。
2. **同形判定须先于处境判定**：初版 S5 先跑，诱饵块把 `## Acceptance tests` 的前一行顶成
   `占位`，于是同形攻击被报成「处境污染」→ 红的来源归因错面。改为 S6 先判、S5 在
   有诱饵时让位。

另附 rev1 已确认成立、rev2 不必重做的事实（编排者独立复现，非转述执行者报告）：

- 现行 lint 管不到新条目（候选模板与现行模板都 `DISPATCH_LINT_PASS` rc=0）→ 判据必须落 pytest 侧
- 反向对照仍有判别力：`WP-20-brief.md` → `DISPATCH_LINT_FAIL` rc=2
- rev1 的模板文本（两块六条明文）已满足 DoD，**rev2 不需要改模板正文**，
  只需补 S7 要求的数量词冻结所依赖的现状（`oracle 校验四项证据` 已在模板中，无需改动）
- rev1 的零回归数据：targeted 20 passed；全量 4 failed / 619 passed / 4 skipped（基线 4/608/4）

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径：只能改
`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
`tests/test_wp_template_dispatch_lint.py` 三个文件；绝不能碰 `contract_render.py`
（不 bump `CONTRACT_TEMPLATE_VERSION`）、其余 `.tmpl`、三份渲染产物、`wrappers/*.sh`、
`tests/test_finalize_merge_triple_sign.py`、`tests/test_init_contract.py`、`docs/plans/`、
`.agentic/`、`.env`、`.context/`；owner 边界对齐 CODEOWNERS，不跨 owner 写入。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径。

- [ ] 模板新增 `## Re-freeze 规则（编排者冻结前自检）` 一节，含「第 3 次**及以后**」的明文
      （不能只写「第 3 次」）、「未经用户批准不得冻结」、「验收标的必须写成不变式，
      台账编号只作破口清单」三条
- [ ] 模板 `## Acceptance tests` 段新增 oracle **第 4 项**，含「按判据自身的组成步骤生成」
      「不得按已知缺陷清单枚举」「某步骤不可攻击须在报告里写明理由」三条
- [ ] 抬头第 5 行不再复述 re-freeze 口径（改为指向新节，避免第二份可执行口径，§5.3）
- [ ] 两份模板逐字节同一（`test_templates_byte_identical` 仍绿）
- [ ] 候选模板过活树 `dispatch_lint.sh`（`test_templates_pass_dispatch_lint_section_check` 两参数仍绿）
- [ ] S1–S6 + **S4b / S5b / S7** 八个面各有判据，各有至少一条转红变异，witness 措辞互不相同
- [ ] 每条变异的首条 witness 归因到它所攻击的那个面（不得靠别的面顺带判红）
- [ ] 极性常量均为单行内单分句（跨行常量会让纯折行探针假阳性，rev2 实测过）
- [ ] S6 同形判定先于 S5 处境判定（否则诱饵块顶掉前一行，归因落错面）
- [ ] `_section_block()` 改用 `re.finditer` 枚举，与 S1 共用同一匹配面（B43）
- [ ] §C 两条无害探针全绿
- [ ] 反向差分方向正确（旧实现 FAIL / 新实现 PASS），报告含两次实测输出
- [ ] 每条负面断言带 oracle 三项 + 第 4 项，无真空断言
- [ ] `CONTRACT_TEMPLATE_VERSION` 保持 `"6"` 不动
- [ ] 现有 7 条 `test_wp_template_dispatch_lint.py` 用例全部保留且仍绿（只增不减）
- [ ] 变异纯内存或 copytree scratch，**不写活树模板**；跑完 `git status` 干净
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归。**rev2 的起点是 rev1 的 commit `b34deb9`**（不是主区 HEAD）：
      targeted `tests/test_wp_template_dispatch_lint.py` = **20 passed**；
      全量 `PYTHONPATH=src python3.11 -m pytest tests -q` = **4 failed / 619 passed / 4 skipped**，
      4 条全在 `tests/test_finalize_merge_triple_sign.py`。**不要修那 4 条。**
      rev1 的 20 条用例只增不减（新增面的用例是追加，不是替换）。
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

1. **不要 bump `CONTRACT_TEMPLATE_VERSION`。** WORK_PACKAGE 是 reference skeleton，
   0 个占位符，不在契约渲染目标内。bump 会让所有采纳方误以为三份契约要重渲。
2. **不要给 `dispatch_lint.sh` 加 required section。** 现行模板与候选模板都过 lint，
   加了会让全仓既有 brief 集体拒收（B23 家族的形态）。
3. **不要用 sha256 常量代替逐字文本。** 两者判别力相同，但 sha256 让「给削弱开绿灯」
   在 diff 里隐形 —— 这与 INV-N 的「必须在测试 diff 里可见」直接冲突。
4. **不要写活树模板。** 变异走纯内存或 `shutil.copytree` scratch 副本。
5. **不要只盯 §B 那 7 条变异。** 判据是 INV-N，凡「削弱了规范力而测试仍绿」皆在范围内。
   §B 是编排者实测过的**下界**，不是上界。
6. **不要用 `agentic <sub>` 自证**（B14：那是冻结副本）。
   用 `PYTHONPATH=src python3.11 -m pytest`。
7. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。
8. **既有失败不是你引入的**（4 条 defaultBranch 冲突）。不要顺手修。
9. **主仓有 6 个与本 WP 无关的未提交改动**（provider 重命名等）。它们不在你的
   worktree 里，但若你看到相关渲染产物差异，那是主仓状态，不要动。
10. **反向差分的方向别写反。** 见 §E。

### 口径权威源引用

- oracle 三项（本 WP 新增第 4 项的落点）：`docs/agentic/templates/WORK_PACKAGE.md`
  `## Acceptance tests` 段，WP-24 落入
- 两份模板同一性：`tests/test_wp_template_dispatch_lint.py::test_templates_byte_identical`
- 契约渲染目标（证 WORK_PACKAGE 不在其中）：`src/agentic_loop/contract_render.py`
  `_REQUIRED_PLACEHOLDERS` 与 `src/agentic_loop/init_cmd.py` `_REFERENCE_TEMPLATES`

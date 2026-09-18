# WP-28 (rev3): 把两条编排规范落成机械可检的模板条目 —— 受保护表示 + 变更可见性

> 冻结日期 2026-09-18 | 编排者 claude | 执行者 kimi。
> 所属 Plan：PLAN-01（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 冻结与 re-freeze 的规则见本仓 `docs/agentic/templates/WORK_PACKAGE.md`「Re-freeze 规则」一节。
> **本 WP 第 3 次冻结（rev3），re-freeze 计数 = 2，「第 3 次及以后停手复核」规则已实弹命中。**
> 前置门已完成：`WP-28-plan-review-before-rev3.md`（停手复核）+
> `WP-28-consult-codex-shape.md`（codex 只读设计咨询，裁定 `NARROW_SCOPE`）+ **用户已批准缩小承诺**。

## 目标（一句话）

把两条目前只存在于任务列表与复核文档里的编排规范 —— ①「判据自检的变异集按判据组成步骤生成」
②「同一 WP 第 3 次及以后 re-freeze 强制停手复核计划」—— 写进 WP brief 模板，
并用**封闭模型的判据**锁住这两块文字的受保护表示，使任何改动必须在测试 diff 里可见。

## 本 rev 的验收标的（三条各自封闭的硬不变式）

> **INV-N1（受保护块身份）**：在两份 WP 模板中，`## Re-freeze 规则（编排者冻结前自检）`
> 与 `## Acceptance tests` 各恰好存在一次（逐行精确匹配；NFKC 同形副本按「边界不唯一」判红）；
> 每块的**完整 body 与测试中的冻结常量逐字节相同**；每块的前后 `## ` 兄弟锚点与冻结值相同。
> 任何受保护字节的新增、删除、替换或**重排**，若不同时修改冻结常量，测试必须转红。

> **INV-N3（副本同一）**：`docs/agentic/templates/WORK_PACKAGE.md` 与
> `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 逐字节相同。

> **INV-N4（变更可见性）**：改变上述受保护字节或锚点，必须在测试的冻结常量里留下可审查 diff。
> 测试只负责强迫变更**可见**，不负责判断该变更**是否获批**。

### 本 WP 明文不覆盖什么（这是承诺边界，不是脚注）

rev1/rev2 用的是一条全称命题（「**任何**削弱其规范力的模板改动都必须转红」）。
该命题不可兑现：「规范力」是开放世界的自然语言语义性质，而攻击面清单本身就是一次枚举，
枚举只能证明有界的存在/排除命题。两轮返工的根因即此（详见停手复核文档 §2）。rev3 起：

**本判据只保证冻结块的 raw text 身份、唯一性与声明的位置锚点不变。它不保证**：

1. 块外编辑不改变其 Markdown 渲染上下文。**编排者已实测三条现成逃逸**：整份文档外包
   `<!-- … -->`、文档开头留未闭合 `<!--`、在 `## 附注` 内开一个未闭合代码围栏 ——
   三者两块 body 均逐字节完好，判据 GREEN。
2. 文档远处不存在去规范化或矛盾条款。**已实测逃逸**：在文档最开头加
   「下列所有流程规则均已废止，仅供历史参考。」→ 判据 GREEN。
   自然语言的规范力没有有限的上下文半径。
3. 任意渲染器把它显示为活动文本；实际消费者一定采纳这份模板；
   所有「语义等价的削弱」都会被识别；规范一定被人或 agent 遵守。

**「规范力」本身不是本 WP 的验收标的。** 上述第 1、2 条移交 **WP-29**，
该 WP 须先定义权威 Markdown 方言、parser 版本与依赖、目标 AST 与消费链。
**你不得在本 WP 内以 HTML 注释深度计数器或围栏状态机伪收口这两条** ——
那只是又一个不完整的 Markdown mini-parser，编排者已判定为伪收口。

## 范围

**allowed_paths**（3 个文件，与 rev2 相同）：

- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`
- `docs/agentic/templates/WORK_PACKAGE.md`
- `tests/test_wp_template_dispatch_lint.py`

**forbidden_paths**：

- `src/agentic_loop/contract_render.py` —— **`CONTRACT_TEMPLATE_VERSION` 不要 bump**。
  `WORK_PACKAGE.md.tmpl` 是 `init_cmd._REFERENCE_TEMPLATES` 里的 reference skeleton，
  含 0 个 `string.Template` 占位符，不在 `contract_render` 渲染目标内（目标是
  AGENTS.md / CLAUDE.md / OPERATING_MODEL.md 三份）。编排者实测 `grep -c '\$'` = 0。
- **任何新增第三方依赖，尤其 Markdown parser**（`markdown-it-py` / `mistune` / `commonmark` 等）。
  编排者实测：全仓无 Markdown parser 依赖，也无文档声明权威方言。引入 parser 属 WP-29。
- `src/agentic_loop/templates/` 下其余全部 `.tmpl`
- `AGENTS.md`、`CLAUDE.md`、`docs/agentic/OPERATING_MODEL.md` —— 主仓活树这三份有**未提交的
  本地改动**（provider 重命名，与本 WP 无关）。零行 diff，不要顺手提交、不要 revert。
- `src/agentic_loop/wrappers/` 下全部 `.sh` —— 尤其 `dispatch_lint.sh`：编排者已实测
  现行模板与候选模板都过 lint，即 lint 管不到新条目，判据必须落 pytest 侧。不要加 required section。
- `tests/test_finalize_merge_triple_sign.py` —— 那 4 条是既有环境失败（本机
  `git init.defaultBranch=master` 与 fixture 的 `git checkout main` 冲突），**不要修**
- `tests/test_init_contract.py`
- `docs/plans/`（含本 brief 自身）、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

## 输入

- 被审树：worktree `/Users/admin/vibe/wp28-norms-into-template`，分支
  `feature/wp28-norms-into-template`。**rev3 的起点是 rev2 的 commit `b34deb9`**。
  rev2 对 `tests/test_wp_template_dispatch_lint.py` 的未提交改动（+228/−65，九个面版本）
  **按 rev3 的判据形状重做**：块体等值取代 S2/S3/S5b/S7 的放行地位，那四个面降级为诊断分类。
  模板正文（两块明文）rev1 已落，**rev3 不需要改模板正文**。
- 两条规范的来源（只作为规范的出处，不是验收标的）：
  - 第 4 项变异规则：`WP-25-plan-review-before-rev4.md` §3 失误 2；根因见
    `WP-25-review-rev4.md` B38 与 `WP-26-review-rev4.md` B35
  - re-freeze 停手规则：原任务 #24，本 WP 按用户决定扩展到「第 3 次及以后」
- 本轮的形状依据：`WP-28-plan-review-before-rev3.md` §5 裁定；
  `WP-28-consult-codex-shape.md` §2/§3/§4（codex 只读设计咨询）

## 交付物清单

- [ ] `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 模板正文**不改**（rev1 已落两块明文）
- [ ] `docs/agentic/templates/WORK_PACKAGE.md` —— 同上，与上一份逐字节同一
- [ ] `tests/test_wp_template_dispatch_lint.py` —— 按 rev3 判据形状重做 INV-N1/N3/N4 的判据与变异集

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。

### A. 判据形状（硬不变式独立运行 + 诊断分类兜底）

**这是 rev3 相对 rev2 的实质改变：不再用「九个面按固定顺序跑、取 `violations[0]` 归因」。**

**A.1 硬不变式（决定放行，各自独立运行，任一失败即红）**

| 步骤 | 要求 |
|---|---|
| T1 定位唯一 | 两个标题各须**恰好出现 1 次**，逐行精确匹配。0 次 → `SECTION_MISSING`；>1 次 → `SECTION_NOT_UNIQUE` |
| T2 同形副本 | 存在 NFKC 归一化后与目标标题相等、但字节不等的 `## ` 行 → `SECTION_HOMOGLYPH_DUPLICATE`（按「边界不唯一」处理） |
| T3 块体切分 | body = 标题后一行 至 下一个 `## ` 行之前（含其间空行），逐字节保留 |
| T4 块体等值 | body 与冻结常量**逐字节相等**，否则 `BODY_MISMATCH`。**不得**使用 `_normalize_ws()` 或任何空白折叠 |
| T6 位置锚点 | 每块的前一个 / 后一个 `## ` 标题与冻结值相等，否则 `SECTION_ANCHOR_MOVED`（首块前锚点为 `<BOF>`） |
| T7 副本同一 | 两份模板逐字节相等，否则 `REPLICA_MISMATCH` |

**A.2 诊断分类（不决定放行，仅在 T4 已红后对 diff 二次归因）**

rev2 的 S2 内容 / S3 极性 / S4 结构 / S7 数量口径**降级到此处**，输出结构化 code
（如 `BODY_CLAUSE_MISSING` / `BODY_POLARITY_CHANGED` / `BODY_INDENT_CODEBLOCK` /
`BODY_QUANTITY_PHRASE_CHANGED` / `BODY_ITEM_COUNT_CHANGED`）。

**硬要求：分类识别不出任何形状时，`BODY_MISMATCH` 单独兜底即为合格的红。**
分类缺失**绝不**构成放行依据。编排者实测两条变异（块内追加散文、块内列表项重排）
确实只命中兜底而无任何分类 —— 这两条必须在你的用例里在场，以证明兜底在承重。

**A.3 witness 形式**

结构化 code，**不得**依赖 `violations[0]` 的执行顺序做归因。
若测试需要主因，可另设稳定的 `primary_code` 优先级，但该优先级只用于展示，不参与放行。
一个变异可以产生多个 witness。

### B. 变异集（按【本判据】的组成步骤生成，不按 B44/B45 缺陷清单）

变异集须按 §A.1 的 **T1/T2/T3/T4/T6/T7 六个步骤 + T5 兜底**逐条生成，每步骤至少一条，全部转红。
编排者冻结前实测的 17 条（可照用，也可加强）：

- **T1** 2 条：标题完好副本（定位不唯一）/ 标题改名
- **T2** 1 条：全角括号同形副本（NFKC 等、字节不等）
- **T3** 1 条：块内插 `## ` 行截断块体切分
- **T4** 8 条：删一条冻结分句 / 极性 必须→可以 / 极性 不得→建议不 / 缩进 6 空格成 code block /
  空行断开列表 / 数量词 四项→三项 / **纯折行（不改字，只挪换行点）** /
  **行尾加两空格（markdown hard break）**
- **T5 兜底** 2 条：块内追加散文 / 块内列表项重排（字节集合不变、顺序变）——
  两条须命中 `BODY_MISMATCH` 且**无任何**诊断分类
- **T6** 2 条：整块搬走（块体一字不改）/ 受保护块前插入新章节（顶掉前锚点）
- **T7** 1 条：只改 `.tmpl` 一侧

**注意 rev2→rev3 的口径反转**：「纯折行」在 rev2 是**无害探针（须绿）**，在 rev3 是
**变异（须红）** —— 因为 rev3 用真逐字节相等，折行即受保护字节变化，须同步改冻结常量。
冻结文字本就不需要支持随意格式化。**不要把 rev2 的折行探针留在无害集里，否则自相矛盾。**

**若某一步骤你确实构造不出变异，须在报告里写明为什么该步骤不可攻击，不得默认略过。**
这条正是本 WP 要落入模板的第 4 项规则，请按它自己的要求执行。

### C. 变异集自身的两条硬要求（编排者两轮踩坑得来，rev3 新增）

1. **每个变异函数须带 `assert 变异后 != 变异前`。** 空操作变异会被报成「判据放行」，
   实际是变异自身缺陷。编排者在 rev2 复核踩过一次（`NFD` 归一化后字符串未变，
   实际造出的是**精确**副本）、在 rev3 冻结前自检又踩一次（折行变异找不到匹配行，
   成了恒等映射，误报为逃逸）。**两次都短暂得出了错误结论。**
2. **T1–T6 的变异须同步施加到两份模板。** 若只变异一份却同时比对副本同一，
   `REPLICA_MISMATCH` 会出现在**每一条**变异的 witness 里，任何步骤的红都无法与副本同一区分。
   T7 必须是唯一考察副本同一的步骤。

### D. 无害探针（必须仍 GREEN，证判据不过紧）

编排者实测 4 条全绿，须在场：

1. 改无关占位符 `<这个 WP 要交付什么>`
2. 文末追加无关新章节
3. 改无关章节 `## 范围` 的正文
4. 改抬头 `> 冻结日期 <YYYY-MM-DD>` 行

**注意**：rev2 的「纯折行」探针已按 §B 移入变异集，不得再作无害探针。

### E. oracle 三项 + 第 4 项（对每条负面用例）

- ① 正向可达控制：未变异的真实模板必须 PASS（编排者实测 `POSITIVE CONTROL: GREEN`）
- ② 原因特异 witness：断言**结构化 code**，且每个步骤的 code 互不相同，
  使红的来源可归因到具体步骤。**不许「rc != 0」/「assert 抛了异常」式真空断言。**
- ③ 代表性禁止变异转红：即 §B
- ④ 变异集按判据组成步骤生成：即 §B 的生成方式本身，外加 §C 两条

### F. 反向差分（方向别写反）

新增用例断言的是「判据转红」，所以在**旧实现**（本 WP 之前的 HEAD，模板尚无这两块）上
新增用例应当 **FAIL**（要的红没出现，因为冻结常量在模板里根本不存在），
在**新实现**上 **PASS**。报告须含两次实测输出。

### G. 编排者冻结前实测（供你确认起点，非转述）

**本节规则（rev2 起对编排者自己生效）**：编排者的冻结前自检，其变异集也必须按判据的组成步骤
生成，不得按上一轮的缺陷清单生成。rev3 冻结前实测（原型 `narrow.py` + `probe5b.py`）：

- 正向对照：真实模板（worktree `b34deb9`）→ `POSITIVE CONTROL: GREEN`
- **变异集按收缩后判据的 7 个组成步骤生成，共 17 条，全红，0 逃逸**
- **归因逐步骤正确**：`MISATTRIBUTED: none`
- **无害探针 4 条全绿**
- **兜底承重已验证**：块内追加散文、块内列表项重排 → 只命中 `BODY_MISMATCH`，无任何诊断分类
- **不覆盖面已实测确证**（这是承诺边界的证据，不是待修缺陷）：
  三条 B44 族变体（外包整份 / 开头未闭合 `<!--` / `## 附注` 内开围栏）两块 body 逐字节完好而
  判据 GREEN；一条 B45 族变体（文档开头加废止句）判据 GREEN。
- **编排者自己的两个原型缺陷**已写成 §C 的两条硬要求（空操作变异、副本混淆归因）

另附前两轮已确认成立、rev3 不必重做的事实（编排者独立复现，非转述执行者报告）：

- 现行 lint 管不到新条目（候选模板与现行模板都 `DISPATCH_LINT_PASS` rc=0）→ 判据必须落 pytest 侧
- 反向对照仍有判别力：`WP-20-brief.md` → `DISPATCH_LINT_FAIL` rc=2
- 模板正文（两块明文）rev1 已满足 DoD，rev3 不改模板正文
- 全仓无 Markdown parser 依赖、无权威方言声明；`WORK_PACKAGE.md.tmpl` 在仓内唯一消费者是
  `init_cmd.py:109`，**逐字节复制**，不解析 markdown → 故 `active_embedding` 属 WP-29

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径：只能改
`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
`tests/test_wp_template_dispatch_lint.py` 三个文件；绝不能碰 `contract_render.py`
（不 bump `CONTRACT_TEMPLATE_VERSION`）、**任何新增第三方依赖尤其 Markdown parser**、
其余 `.tmpl`、三份渲染产物、`wrappers/*.sh`、`tests/test_finalize_merge_triple_sign.py`、
`tests/test_init_contract.py`、`docs/plans/`、`.agentic/`、`.env`、`.context/`；
owner 边界对齐 CODEOWNERS，不跨 owner 写入。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径。

- [ ] 模板正文**零改动**（rev1 已落两块明文；若你认为需要改，先在报告里说明理由并停手）
- [ ] 两份模板逐字节同一（`test_templates_byte_identical` 仍绿）
- [ ] 候选模板过活树 `dispatch_lint.sh`（`test_templates_pass_dispatch_lint_section_check` 两参数仍绿）
- [ ] **T1/T2/T3/T4/T6/T7 六个硬不变式各自独立运行**，任一失败即红，不靠检查顺序放行
- [ ] **T4 用真逐字节相等**；代码里不存在 `_normalize_ws()` 或任何空白折叠参与放行判定
- [ ] **S2/S3/S4/S7 已降级为诊断分类**，只在 T4 红后对 diff 归因；`BODY_MISMATCH` 单独兜底即合格
- [ ] 兜底承重有用例：至少 2 条变异只命中 `BODY_MISMATCH` 而无任何诊断分类
- [ ] witness 为结构化 code，归因不依赖 `violations[0]` 的执行顺序
- [ ] 每个变异函数带 `assert 变异后 != 变异前`（§C.1）
- [ ] T1–T6 变异同步施加到两份模板，T7 是唯一考察副本同一的步骤（§C.2）
- [ ] §B 七类步骤各有至少一条转红变异，结构化 code 互不相同
- [ ] §D 四条无害探针全绿；**「纯折行」不在无害集里**（已按 §B 移入变异集）
- [ ] **brief 的「明文不覆盖」三条原样体现在测试文件的模块 docstring 里**，
      使后人读判据时看到边界，而不是误以为「规范力已被守住」
- [ ] `_section_block()` 用 `re.finditer` 枚举，与 T1 共用同一匹配面（B43，rev2 已修，不回退）
- [ ] 反向差分方向正确（旧实现 FAIL / 新实现 PASS），报告含两次实测输出
- [ ] 每条负面断言带 oracle 三项 + 第 4 项，无真空断言
- [ ] `CONTRACT_TEMPLATE_VERSION` 保持 `"6"` 不动
- [ ] 现有 7 条 `test_wp_template_dispatch_lint.py` 用例全部保留且仍绿（只增不减）
- [ ] 变异纯内存或 copytree scratch，**不写活树模板**；跑完 `git status` 干净
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归。**rev3 的起点是 commit `b34deb9`**（不是主区 HEAD）：
      targeted `tests/test_wp_template_dispatch_lint.py` = **20 passed**；
      全量 `PYTHONPATH=src python3.11 -m pytest tests -q` = **4 failed / 619 passed / 4 skipped**，
      4 条全在 `tests/test_finalize_merge_triple_sign.py`。**不要修那 4 条。**
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

1. **不要试图覆盖「规范力」。** 那是开放世界命题，两轮返工的根因即此。
   本 WP 只证受保护表示 + 变更可见性。渲染语义与远距离矛盾条款属 WP-29，
   **不得**用 HTML 注释计数器或围栏状态机伪收口。
2. **不要 bump `CONTRACT_TEMPLATE_VERSION`。** WORK_PACKAGE 是 reference skeleton，0 个占位符。
3. **不要给 `dispatch_lint.sh` 加 required section。** 现行与候选模板都过 lint，
   加了会让全仓既有 brief 集体拒收（B23 家族形态）。
4. **不要用 sha256 常量代替逐字文本。** 两者判别力相同，但 sha256 让「给削弱开绿灯」
   在 diff 里隐形 —— 与 INV-N4 的「变更必须可见」直接冲突。
5. **不要写活树模板。** 变异走纯内存或 `shutil.copytree` scratch 副本。
6. **不要用 `agentic <sub>` 自证**（B14：那是别棵树的冻结副本）。
   用 `PYTHONPATH=src python3.11 -m pytest`。
7. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。
8. **既有失败不是你引入的**（4 条 defaultBranch 冲突）。不要顺手修。
9. **主仓有若干与本 WP 无关的未提交改动**（provider 重命名等）。不要动。
10. **反向差分的方向别写反。** 见 §F。
11. **空操作变异是假绿的头号来源。** 见 §C.1，编排者两轮各踩一次。

### 口径权威源引用

- oracle 三项 + 第 4 项：`docs/agentic/templates/WORK_PACKAGE.md` `## Acceptance tests` 段
- 两份模板同一性：`tests/test_wp_template_dispatch_lint.py::test_templates_byte_identical`
- 契约渲染目标（证 WORK_PACKAGE 不在其中）：`src/agentic_loop/contract_render.py`
  `_REQUIRED_PLACEHOLDERS` 与 `src/agentic_loop/init_cmd.py` `_REFERENCE_TEMPLATES`
- 本轮承诺边界的裁定：`WP-28-plan-review-before-rev3.md` §5
- 判据形状的设计依据：`WP-28-consult-codex-shape.md` §2/§3/§4

结论：应收手并改判据形状。B44/B45 不是“还差两个面”，而是在证明当前承诺属于开放世界语义命题，有限攻击面无法穷尽。推荐把 WP-28 收缩为“受保护文本及其指定 Markdown 结构保持不变”，将“在实际渲染/消费链中仍为有效规范”另作独立不变式；不要再用新增黑名单或手写注释/围栏状态机宣称覆盖“规范力”。

### 1. 递归诊断

判断基本成立，但需要更精确地表述：

“面清单”本身不必然错误。若这些面来自一个封闭、形式化的输入模型，并能证明它们构成完备分解，那么有限枚举可以是完整判据。例如“块体必须与常量逐字节相等”实际覆盖了所有字节位置，并不是按已知缺陷枚举。

当前递归的真正原因是：

- `削弱规范力` 是开放世界的自然语言语义性质，没有形式化定义；
- Markdown 方言、渲染器和模板实际消费方式没有成为判据输入；
- 允许块外任意编辑，却试图靠有限局部探针证明全局语义不受影响；
- S2/S3/S5b 等检查使用“必须包含某些片段”或“不得包含已知坏短语”，只能证明有限的存在/排除命题；
- “按判据组成步骤生成变异”只能验证已声明步骤的实现，不能证明步骤集合本身完备。

所以每轮逃逸不是偶然漏测，而是规格量词超过了判据模型：brief 声称覆盖“任何削弱”，实现只能覆盖“当前识别出的削弱表示”。

### 2. 判据形状

正确形状不是一个主判据，而是几个正交、可形式化的硬不变式：

```text
VALID =
    identity_and_placement
  ∧ protected_body_identity
  ∧ active_embedding
  ∧ replica_identity
```

其中：

1. `identity_and_placement`：两个目标 section 在指定语法层级各恰好出现一次，并位于指定相邻 section 之间。
2. `protected_body_identity`：完整块体与冻结常量相等。
3. `active_embedding`：在明确指定的 Markdown 方言/解析器下，它们确实解析为活动的顶层 heading、paragraph、list，而不是 code、raw HTML/comment 等不可见内容。
4. `replica_identity`：两份模板逐字节相同。

块体等值确实比继续补 S2/S3/S5b/S7 更收口。但建议用真正的逐字节相等，而不是无限制的 `_normalize_ws()` 相等。Markdown 中空白可能有语义：

- 行首四空格可能变成 code block；
- 空行可能结束 list；
- 行尾两个空格可能产生 hard line break；
- block quote/list continuation 也依赖空白。

如果必须允许折行变化，就要明确一个经过证明的等价关系，例如比较指定 Markdown parser 产生的规范 AST；不能把所有 whitespace 无条件折叠后称为“等值冻结”。最稳妥的 WP-28 范围是：块内不允许所谓无害改写，任何折行也要求同步修改冻结常量。冻结文字本来就不需要支持随意格式化。

块体一字不改仍然能被 B44 一族绕过。是的，`active_embedding` 必然是至少部分依赖块外上下文的性质：

```markdown
<!--
## Acceptance tests
完整冻结块
-->
```

块体相等只证明 substring；不能证明它在完整文档中的解释。类似逃逸还包括不同类型的 Markdown raw HTML block、不同长度围栏、缩进 code、`<pre>`/`<script>` 等，具体集合依赖 Markdown 方言。

因此，不建议把 HTML 注释深度计数当成最终收口。它是有价值的 B44 回归检查，却仍是一个不完整的 Markdown mini-parser。若要承诺渲染语义，应使用实际权威 parser 解析整份文档，并校验目标 AST 节点；若项目没有权威 parser，就必须把承诺降级为 raw-text preservation。

“紧邻前一非空行”也不够。自然语言规范力没有有限的上下文半径，例如文档开头可以加入：

> 下列所有流程规则均已废止，仅供历史参考。

它可以离冻结块任意远。渲染状态同样可能从很远的未闭合结构开始。要机械收口，只能：

- 锁定一个明确定义的完整 envelope；或
- 按整份文档解析，并锁定目标节点的顶层位置和 sibling 关系；或
- 锁整份模板。

即使锁定 AST 位置，也只能证明“作为活动规范文本出现”，不能证明文档其他位置没有自然语言矛盾，除非把整份文档都纳入冻结范围。

### 3. 归因保留

应把“判定”和“诊断”分开，而不是靠检查顺序决定第一个 witness。

建议结构：

```python
facts = extract_and_parse(text)

hard_violations = [
    check_unique_top_level_sections(facts),
    check_frozen_body_identity(facts),
    check_active_embedding(facts),
    check_required_placement(facts),
]

if body_mismatch:
    diagnostic_violations = classify_body_diff(actual, expected)
    if not diagnostic_violations:
        diagnostic_violations = [BODY_MISMATCH]
```

也就是：

- 所有硬不变式独立运行；任一失败即红。
- 块体不等后，再用 S2/S3/S4/S7 对 diff 做二次归因。
- 细化面不是放行依据；漏掉某种分类时由通用 `BODY_MISMATCH` 兜底。
- `active_embedding` 与块体等值并列，因为可能出现“块体绿、上下文红”。
- witness 最好返回结构化 code，例如 `BODY_POLARITY_CHANGED`、`BODY_ITEM_COUNT_CHANGED`、`SECTION_NOT_TOP_LEVEL`，不要依赖 `violations[0]` 的执行顺序。
- 一个变异可以产生多个 witness；若测试需要主因，可另设稳定的 `primary_code` 优先级，但该优先级只用于展示，不参与是否放行。

因此，在用户给出的两个选项中，“主判据红后再按面二次定位”更正确；但渲染/定位类硬不变式仍须独立运行，不能依附于块体先红。

### 4. 不变式表述

不应再写“任何削弱其规范力的模板改动都必须转红”。建议改成以下可机械兑现的命题：

> **INV-N1（受保护块身份）**：在两份 WP 模板中，指定的两个二级 section 各恰好存在一次；每个 section 的 heading 与完整 body 必须与测试中的冻结常量逐字节相同。任何受保护字节的新增、删除、替换或重排，若不同时修改冻结常量，测试必须转红。

> **INV-N2（结构与活动上下文）**：在指定版本和方言的 Markdown parser 下解析完整模板后，两个 section 必须分别表现为唯一的顶层 level-2 heading，并具有与冻结参考相同的 section AST，且位于冻结的前后 sibling 锚点之间。落入 code、raw HTML/comment 或其他非活动上下文必须转红。

> **INV-N3（副本同一）**：`docs/agentic/templates/WORK_PACKAGE.md` 与 `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 必须逐字节相同。

> **INV-N4（变更可见性）**：改变上述受保护文本或结构，必须在测试冻结常量或结构期望中留下可审查 diff；测试不负责判断该变更是否获得用户批准。

最后一句很重要：测试能强迫变更“可见”，但无法证明“已经批准”。

如果不引入权威 Markdown parser，则 INV-N2 应诚实降级为：

> 判据只保证冻结块的 raw text、唯一性和声明的位置锚点保持不变；不保证块外编辑不会改变其 Markdown 渲染上下文、产生远距离去规范化语句或改变实际消费者对文本的解释。

在这种降级下，最强可达命题是：

> 两段冻结文字的受保护表示在两份模板中保持不变，任何受保护表示变化必须显式修改测试 oracle。

它不能升级为：

- 规范一定被人或 agent 遵守；
- 文档中不存在远处矛盾条款；
- 任意渲染器都把它显示为活动文本；
- 实际 scaffold/consumer 一定采用这份模板；
- 所有“语义等价的削弱”都会被识别。

### 5. 是否收手

是。WP-28 下一次冻结已经命中它自己要建立的第 3 次冻结停手规则。当前机器状态也仍是 `CHANGES_REQUESTED / REWORK`，阻断项为 B44、B45；不应直接冻结 rev3。

建议先让用户裁定以下承诺边界：

- WP-28 收缩为 `INV-N1 + INV-N3`，必要时加固定 section 顺序/锚点；完整块体逐字节冻结，S2/S3/S4/S7只作诊断分类。
- 明文声明 WP-28 不证明全局“规范力”，只证明受保护表示和变更可见性。
- 若确实要求 B44 意义上的活动渲染保证，另立 WP 定义权威 Markdown 方言、parser 版本、目标 AST 和消费链。不要继续在 WP-28 中追加 HTML 注释计数器。
- 如果项目已有且明确使用的 Markdown parser，`active_embedding` 可以留在 WP-28；否则引入 parser/依赖和决定渲染方言已经超出当前三个 `allowed_paths` 的冻结范围，应拆包。

你实测的 B44/B45 修法都可作为回归证据，但定位不同：块体等值应成为内容身份的正式判据；HTML 注释深度计数最多是临时回归保护，不能作为“渲染上下文已经完备覆盖”的依据。

本次仅作只读设计咨询，没有修改文件。现场依据包括 [WP-28 brief rev2](/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md)、[WP-28 状态](/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-28.status.json) 和 [实际判据](/Users/admin/vibe/wp28-norms-into-template/tests/test_wp_template_dispatch_lint.py:252)。
# WP-29 阶段 1 独立复核

> 复核者 claude-code（编排者兼独立复核者）| 复核日期 2026-09-18
> 被复核对象：`feature/wp29-render-scope-decision` @ `bd4ac7a`
> 冻结输入：`WP-29-brief.md`（sha256 `1dfd72aceb3649efc449a75f3a8e7893a27c0fa5480970f763265e0a6d29efd6`，复核时重算一致）

## 裁定

**ACCEPT（裁定成立），但推荐方案 (b) 我不采纳，改判 (c′)。**

拆开说：

- **交付物本身 ACCEPT**：五项必答逐条有据，证据我逐条复现全部成立，标注纪律（实测 vs 推断）
  遵守，零代码改动、零依赖、模板未碰、`git status` 干净。执行者按 brief 交付了它该交付的东西。
- **它的推荐结论我不采纳**：§5 推荐「整份模板逐字节冻结」在判别力上正确，但代价被低估了
  一个数量级——见 §3。这不是执行者的失误：brief 明确把 (a)/(b)/(c) 三选一交给它裁定，
  它给出了理据完整的裁定；采不采纳是编排者的权。

## 1. 我复现了什么

### §1 消费链——**成立**

```text
$ grep -rn 'WORK_PACKAGE' src/ tests/        # 已滤 __pycache__（0 命中）
src/agentic_loop/init_cmd.py:109:    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
src/agentic_loop/templates/AGENTS.md.tmpl:84:- a tracked brief created from `docs/agentic/templates/WORK_PACKAGE.md`;
tests/test_init_contract.py:62 / tests/test_wp_template_dispatch_lint.py:23,24
```

代码路径逐跳核过：`init_cmd.py:109` → `_write_asset()`（`:138`）→ `contract_render.load_template()`
（`:148`）→ `resource.read_text(encoding="utf-8")`（`contract_render.py:250-255`）→ `target.write_text()`。
**全链无 Markdown 解析**，是逐字节复制。`load_template` 的调用点只有 `init_cmd.py:148` 与
`contract_render.py:243` 自身，无第二个解析入口。结论「唯一仓内机器消费者是逐字节复制」成立。

### §2 渲染面——**成立，标注正确**

`git remote -v` 确认 origin 是 GitLab；无 `.github`、无 `mkdocs.yml` / `docusaurus.config.js` /
`conf.py` / `_config.yml`、无 `.gitlab-ci.yml`、无 `.pre-commit-config.yaml`、无 markdownlint 配置。
对 `commonmark|GFM|markdown-it|mistune|GLFM` 的全仓 grep 只命中 `docs/plans/` 下本轮自己的文档
与 WP-28 rev3 brief 的禁令行，**无任何权威方言声明**。文档把 GLFM / 编辑器预览明确标为「推断」，
未冒充实测——这条纪律遵守到位。

我补查了它没查的一面：**没有任何 CI、hook 或 wrapper 读取这两份模板**
（`grep -rn 'WORK_PACKAGE' src/agentic_loop/wrappers/ scripts/` 零命中）。这进一步支持它的结论。

### §3 威胁真实性——**成立，且我把它的一处「推断」升级为实测**

我用 `git archive HEAD | tar -x` 建独立 scratch（不碰活树），复现：

```text
基线：7 passed in 2.02s，exit 0
变异：两份模板各在首行前加 `<!--`、末行后加 `-->`；2889 字节 → 2898 字节
变异后：7 passed in 1.98s，MUTATED_EXIT=0     ← 判据未转红，与文档一致
活树：git status --porcelain 空（LIVE_TREE_CLEAN）
```

文档对 `dispatch_lint.sh` 只做了代码审查推断。**我把它跑成了实测**：抽出
`dispatch_lint.sh:68-99` 那段 python 段落检查器，对「整份外包注释」的模板副本执行——
输出为空、rc 与未变异对照完全相同，即该门禁**同样不转红**。原推断成立，现在有实测背书。

后果链因此确立：这条改动没有任何机械防线，只有 `git diff` 与人眼。

### §4 方案对比——**表格判别力列成立**

E1–E4 四条都是字节改变型，故 (b) 全拦；(a) 对 E4 原理上无效（自然语言矛盾在 AST 之外）；
(c) 一条不拦。这三列我认同。

## 2. 一处需修正的措辞（不阻断）

§0 与 §5 说 (b) 判别力「覆盖 E1–E4 全部」。准确说法是：**(b) 拦住的是「文件被改」，
不是「E1–E4 这四种攻击」**。整份逐字节冻结对任何字节改动都红，它并不区分攻击与合法编辑——
判别力是 1，特异性是 0。这不是笔误级的小事，它直接引出下面的成本问题。

## 3. 为什么我不采纳 (b)

我把 WP-28 rev3 的 4 条**无害探针**（brief §D 明确要求必须绿的合法编辑）拿去跑 (b) 的判据：

| 合法编辑 | rev3 INV-N | (b) 整份逐字节冻结 |
|---|---|---|
| 改占位符 `<这个 WP 要交付什么>` → `<这个 WP 要交付的内容>` | GREEN | **RED** |
| 文末追加一节无关内容 | GREEN | **RED** |
| 改 allowed_paths 说明措辞 | GREEN | **RED** |
| 改「冻结日期」字样 | GREEN | **RED** |

**(b) 会把 WP-28 rev3 已明文承诺必须绿的四类编辑全部判红。** 文档估的成本是
「任何合法模板编辑都需同步更新冻结常量并过 review」，对一份 76 行骨架「可接受」——
但这份骨架里只有两个二级 section 是受保护的，其余 8 个 section（`## 目标`、`## 范围`、
`## 输入`、`## 交付物清单`、`## 完成定义`、`## 风险声明`、`## 附注` 等）是**本就该随 WP 演进的
活文本**。把它们一并冻死，等于宣布模板骨架不可再演进，与 WP-28 rev3 的承诺直接冲突。

这也不只是「多改一次常量」的成本：它把每次正常的模板演进都变成一次「改判据 oracle」的动作，
而 oracle 改动恰恰是最需要 review 注意力的东西——高频无害的 oracle 改动会把 review 对
oracle 改动的敏感度磨平。这是 WP-28 一路踩过的同一个坑的镜像（判据的红必须稀有才有信息量）。

## 4. 我的裁定：(c′)

**(c′) = 承诺边界明文化 + 把「非受保护区」与「受保护区」分离，不引 parser、不整份冻结。**

具体（供阶段 2 冻结时参考，本复核不冻结）：

1. **不引 parser**——这一点采纳 (b) 的理由：无权威方言、无挂载点、对 E4 无效。执行者论证充分。
2. **不整份冻结**——理由见 §3。
3. 阶段 2 的可选加固方向（择一或组合，须先冻结再实施）：
   - **受保护 envelope 冻结**：把「两个受保护 section 及其定界」这一段连续区间逐字节冻结，
     而非整份文件——比 rev3 的「块体 + 锚点」更严（连块间字节也锁），但仍不锁其余 8 个 section。
     这拦得住 E3（在 `## 附注` 内开围栏，若 `## 附注` 在 envelope 内）但拦不住 E1/E2/E4。
   - **文首/文末哨兵**：只锁文档首行与末行必须是特定形态（非 `<!--`、非围栏），
     成本极低，专拦 E1/E2 这一族「从文档边缘做手脚」的攻击。**这是我认为性价比最高的一条。**
   - **E4 明文降级**：远距离去规范化句在任何机械判据下都不可兑现（codex 咨询与本文档 §4 一致），
     写进承诺边界，不假装覆盖。
4. **不论选哪条，措辞必须落地**：文档 §5 给的那段限制措辞我认同，建议原样进阶段 2 的判据 docstring。

## 5. B48：我自己的 brief 缺陷（执行者无责）

文档 `[CONCERNS]` 报的 606-vs-619 是**我的错**，不是回归：

- WP-29 brief DoD 把零回归基线写成 `4 failed / 619 passed / 4 skipped`，619 是 **WP-28 lane** 的数。
- WP-29 的 base 是 `2e5f2c0`，实测 `4 failed / 606 passed / 4 skipped`（`--collect-only` 收 614 = 4+606+4）。
- 我复核时另跑对照：wp29 树 606 / wp28 树 619；两侧 targeted 分别 7 与 20；`20 − 7 = 13 = 619 − 606`。
  三棵树测试文件数同为 41。差额完全由 WP-28 lane 自己的新增用例解释。
- 根因：我在冻结时把跨 lane 的数字抄进了 brief，而两个 WP 的 base commit 不同。

执行者的处理是对的：它按禁令没改 `docs/plans/` 下其他文件，只在报告里标出差异并交回编排者裁定。
**零回归成立**（本阶段零代码改动）。缺陷编号 **B48**，归因编排者。

## 6. 结论

- 交付物 **ACCEPT**，阶段 1 的五项必答与证据纪律达标。
- 推荐方案不采纳，改判 **(c′)**：不引 parser（采纳其论证），不整份冻结（§3 的四条反证），
  优先考虑「文首/文末哨兵 + 承诺边界明文化」。
- 阶段 2 **仍未冻结**，且须在用户批准本裁定后才可冻结。
- 新增缺陷 **B48**（编排者自己的 brief 跨 lane 基线数）。

---

## 7. 更正（2026-09-18，codex 第二签名后）

**§4.3 第二条「文首/文末哨兵」的推荐作废。** 我在那里写「专拦 E1/E2 这一族」并称之为
「性价比最高的一条」，这个判断是错的。codex 第二签名给出了具体绕过，我用探针
（`probe-wp29-sentinel.py`，对象是 `src/agentic_loop/templates/WP-brief.md.tmpl`）复现成立：

| 变异形状 | 哨兵判据 | 期望 |
|---|---|---|
| 首尾两行字节不变，中间全部包进 `<!-- -->` | **GREEN（逃逸）** | 应 RED |
| 首行后插入未闭合 `<!--`，末行字节不变 | **GREEN（逃逸）** | 应 RED |
| 整档外包前后缀（首尾行被顶走） | RED | RED ✓ |
| baseline（未变异） | GREEN | GREEN ✓ |

哨兵只约束「首行/末行仍是特定形态」，而注释化攻击可以让首尾行原位不动、把中间规范全部失活。
所以它拦住的不是 E1/E2 **这一族**，而是「在 sentinel 外侧追加前后缀」**这一个精确形状**。

这与记忆 `open-world-claims-cannot-be-enumerated` 同型：我又一次拿一个覆盖单个形状的判据去
承诺一个开放族。阶段 2 的方向须改为——要么冻结一个明确 envelope（且按 §3 核对必须保持 GREEN 的
四条无害探针），要么把承诺降级为逐形状枚举并写进边界，不再声称覆盖族。

§4.3 其余两条（受保护 envelope 冻结、E4 明文降级）不受此更正影响；§1/§2/§3/§5 结论不变。
阶段 1 的交付物裁定由 ACCEPT 改为 **CHANGES_REQUESTED**，理由是 codex 的两条阻断项
（消费面证据完整性 C1、方案 (b) 遗漏强制 GREEN 约束 C2），详见
`WP-29-consult-codex-stage1-verdict.md` 与 `WP-29.status.json` 的
`consult` / `evidence.orchestrator_cross_check_of_consult`。

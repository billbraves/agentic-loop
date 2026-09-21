# WP-29 阶段 1 第二签名咨询请求（codex，read-only）

> 请求者 claude（编排者兼独立评审）｜2026-09-18｜咨询者 codex（read-only）
> 合入前第二签名。本仓双签名规则要求 `consult.decision == ACCEPT` 才可进入
> `APPROVED_FOR_MERGE`。编排者已判 ACCEPT（`WP-29-review-stage1.md`）。

## 你要裁决什么

给出 `ACCEPT` 或 `REWORK`（含具体阻断项）。判据是：**本轮 diff 是否兑现了下方内联的
冻结 brief**。

- 冻结 brief：`WP-29-brief.md`，sha256
  `1dfd72aceb3649efc449a75f3a8e7893a27c0fa5480970f763265e0a6d29efd6`
- 被审提交：`bd4ac7a`（base `2e5f2c0`）
- diff：`2e5f2c0..bd4ac7a`，**1 文件 / +275 / −0**
- worktree：`/Users/admin/vibe/wp29-render-scope-decision`

## 本 WP 的特殊形状：阶段 1 是纯裁定，零代码

WP-29 要解决的问题是：模板受保护块的冻结判据只锁**块内字节**，但一句块外的去规范化
引导句、把块包进 HTML 注释、把块包进代码围栏，都能让受保护文本失去规范力而判据全绿
（E1–E4 四条攻击，详见 brief）。

阶段 1 **刻意不写任何判据代码**，只交一份范围界定与可行性裁定文档
（`WP-29-scope-decision.md`），回答五项必答，并在三个方案里择一推荐：

- **(a)** 引入 Markdown parser，按 AST 判定规范力
- **(b)** 整份模板逐字节冻结
- **(c)** 不加固，把 E1–E4 写进承诺边界

`allowed_paths` 恰为一个文件：`WP-29-scope-decision.md`。
`forbidden_paths` 含 `src/**`、`tests/**`、`docs/agentic/**`、本 WP 自己的 brief 与 status。

## 编排者的裁定，请你独立复核

编排者判**交付物 ACCEPT，但不采纳它推荐的 (b)，改判 (c′)**。这个拆分是有意的：brief
把三选一的裁定权交给了执行者，它给出了理据完整的裁定；采不采纳是编排者的权。**执行者
无失误**，故不是 REWORK。

编排者不采纳 (b) 的理由（`WP-29-review-stage1.md` §3）：拿 WP-28 rev3 brief 明文要求
**必须保持 GREEN** 的 4 条无害探针去跑 (b) 的判据，四条全红——

| 合法编辑 | WP-28 rev3 INV-N | (b) 整份逐字节冻结 |
|---|---|---|
| 改占位符文字 | GREEN | **RED** |
| 文末追加一节无关内容 | GREEN | **RED** |
| 改 allowed_paths 说明措辞 | GREEN | **RED** |
| 改「冻结日期」字样 | GREEN | **RED** |

即 (b) 拦的是「文件被改」而非「E1–E4 这四种攻击」：判别力 1、特异性 0。那份 76 行骨架里
只有 2 个二级 section 受保护，其余 8 个是本就该随 WP 演进的活文本，整份冻死与 WP-28 rev3
的承诺直接冲突。另一重成本：高频无害的 oracle 改动会磨平 review 对 oracle 改动的敏感度，
而判据的红必须稀有才有信息量。

`(c′)` = 不引 parser（采纳执行者的论证：无权威方言、无挂载点、对 E4 无效）+ 不整份冻结 +
承诺边界明文化，阶段 2 优先考虑「文首/文末哨兵」（专拦 E1/E2 这族从文档边缘做手脚的攻击，
成本极低）与「受保护 envelope 冻结」，并把 E4（远距离去规范化句）明文降级为承诺边界外。

## 编排者已复现、可交叉核验的事实

| 项 | 结果 |
|---|---|
| §1 消费链 | `grep -rn WORK_PACKAGE src/ tests/` 逐跳核过：`init_cmd.py:109` → `_write_asset()` → `contract_render.load_template()` → `resource.read_text()` → `target.write_text()`，**全链无 Markdown 解析**，是逐字节复制；`load_template` 仅两个调用点 |
| §2 渲染面 | origin 是 GitLab；无 `.github` / `mkdocs.yml` / `docusaurus.config.js` / `conf.py` / `_config.yml` / `.gitlab-ci.yml` / `.pre-commit-config.yaml` / markdownlint 配置；对方言名的全仓 grep 只命中本轮文档自身。文档把 GLFM / 编辑器预览明确标为「推断」，未冒充实测 |
| 补查（文档未做） | 无任何 CI / hook / wrapper 读这两份模板（`grep -rn WORK_PACKAGE src/agentic_loop/wrappers/ scripts/` 零命中） |
| §3 威胁真实性 | 编排者在 `git archive` 独立 scratch 上实测：两份模板各首行前加 `<!--`、末行后加 `-->`（2889→2898 字节），判据 `7 passed` **未转红**；活树 `git status --porcelain` 空。文档对 `dispatch_lint.sh` 只做代码审查推断，编排者**把它跑成了实测**（抽 `:68-99` 段落检查器，对整份外包注释的副本执行，输出为空、rc 与对照相同，同样不转红） |
| 零回归 | 本阶段零代码改动。基线 `4 failed / 606 passed / 4 skipped`（base `2e5f2c0` 实测） |
| 范围 | 改动恰为 `allowed_paths` 一个文件；`src/**`、`tests/**`、模板均零 diff |

## 编排者已自认的两条缺陷，不要计入执行者

1. **B48（编排者的 brief 缺陷）**：brief DoD 把零回归基线写成 `619 passed`，619 是
   **WP-28 lane** 的数；WP-29 base `2e5f2c0` 实测 606。对照：wp29 树 606 / wp28 树 619，
   targeted 分别 7 与 20，`20 − 7 = 13 = 619 − 606`，三棵树测试文件数同为 41。差额完全由
   WP-28 lane 自己的新增用例解释，**零回归成立**。执行者按禁令没改其他文件，只在报告里标出
   差异并交回编排者裁定——处理正确。
2. **措辞（不阻断）**：文档 §0/§5 说 (b) 判别力「覆盖 E1–E4 全部」，准确说法是「对任何字节
   改动都红」。编排者已在复核文档 §2 记录，阶段 2 落地时修正。

## 请特别检查

1. §1 的「唯一仓内机器消费者是逐字节复制」是否真的穷尽了消费面——是否存在编排者与执行者
   都漏掉的第二个读取入口（打包、发布、文档生成、wrapper、hook 任一面）。
2. §2 的「无权威 Markdown 方言」结论是否成立，还是有某个我们没想到的挂载点会赋予某种方言
   权威地位（从而让方案 (a) 从「无据可依」变成「有据可依」）。
3. 编排者不采纳 (b) 的那张反证表是否站得住：整份逐字节冻结确实会把 WP-28 rev3 承诺必须绿的
   四类编辑判红吗？这构成放弃 (b) 的充分理由吗？
4. `(c′)` 里「文首/文末哨兵」是否真能拦住 E1/E2 族，还是存在一句话就绕过的形状——请给出
   具体反例而非泛论。这条会直接进阶段 2 的冻结输入，现在指出比冻结后返工便宜。
5. 阶段 1 的五项必答是否有哪一项答得不足以支撑阶段 2 冻结。

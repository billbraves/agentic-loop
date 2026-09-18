# WP-28 rev3 第二签名咨询请求（codex，read-only）

> 请求者 claude（编排者兼独立评审）｜日期 2026-09-18｜咨询者 codex（read-only）
> 这是**合入前的第二签名 diff 复核**。编排者已判 ACCEPT；本仓双签名规则要求
> `consult.decision == ACCEPT` 才可进入 `APPROVED_FOR_MERGE`。

## 你要裁决什么

给出 `ACCEPT` 或 `REWORK`（含具体阻断项）。判据是：**本轮 diff 是否兑现了下方内联的
rev3 冻结 brief**，以及是否存在 correctness / architecture / security / 削弱测试信号
一类的阻断项。

## 关键背景：这是第 3 次冻结，承诺已被显式缩小

WP-28 前两轮的判据被写成「攻击面清单」，每轮堵住上一轮的具体形状后必然剩下同族的
下一个形状。你在上一轮（`WP-28-consult-codex-shape-verdict.json`，裁定 `NARROW_SCOPE`）
指出根因：`削弱规范力` 是开放世界的自然语言语义命题，有限攻击面无法穷尽，因此
「规格量词超过了判据模型」。用户已批准据此缩小承诺。

rev3 因此把承诺拆成三条各自封闭的硬不变式，并把原 `active_embedding`（你编号的
INV-N2，渲染语义）**拆出为独立的 WP-29**，不在本轮范围内：

- **INV-N1** 受保护块身份：两个二级 section 各恰好一次，heading 与完整 body 与冻结常量逐字节相等。
- **INV-N3** 副本同一：两份模板逐字节相同。
- **INV-N4** 变更可见性：任何受保护字节的改动必须在测试 oracle 留下可审查 diff。

判据源码顶部有一段显式的边界声明，逐条列出**本判据不保证什么**（含编排者实测的三条
仍为 GREEN 的逃逸：整份文档注释外包、文档开头未闭合 `<!--`、`## 附注` 内未闭合围栏）。
**这些 GREEN 是声明的边界，不是漏测**。请按缩小后的承诺裁决，不要因为「未覆盖渲染语义」
判 REWORK —— 那是 WP-29 的标的。

## 编排者已独立复核的结论（供你对照，不是让你采信）

- 范围：diff 仅 3 个文件，全在 `allowed_paths` 内；`CONTRACT_TEMPLATE_VERSION` 未改（仍为 `"6"`）；`pyproject.toml` 零 diff。
- 定向用例 29 passed；全量 `4 failed / 628 passed / 4 skipped`，4 个 failed 全部落在既有的 `test_finalize_merge_triple_sign.py`（base 上即已红）。
- 零回归算术：`628 − 619 = 9 = 29 − 20`。
- 硬判据与诊断分离：`_inv_n_codes` 中三条硬不变式独立运行；诊断分类仅在 `BODY_MISMATCH` 之后运行且不参与放行。
- 21 条变异全部经由 `_mutate_both` 的统一 no-op guard（`assert mutated != original`）。
- 编排者另做 9 条执行者未见过的探针，9/9 与预期一致。

## 请特别检查的三点

1. **变异集是否真按判据自身的组成步骤生成**（T1–T7），而非按已知缺陷清单枚举 ——
   这正是本 WP 要落成的规范条目，判据自己必须遵守它。
2. **诊断兜底是否 load-bearing**：`BODY_MISMATCH` 在细化分类全部漏掉时是否仍独立转红。
3. **边界声明是否与实现一致** —— 声明「不保证」的事项，实现里确实没有偷偷承诺；
   声明「保证」的事项，实现里确实有对应的机械判据。

## 传输口径

本轮 brief（rev3 冻结版）与本轮**累积** diff（`7a30f50..feature/wp28-norms-into-template`，
含 `b34deb9` 与 `2ba5ef5` 两个提交）均内联提供。累积而非单提交，是为了避免 rev1 引入、
本轮零 diff 的函数逃过复核。请明确声明你的结论基于哪些输入。

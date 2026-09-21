# WP-28 rev6 第二签名咨询请求（codex，read-only）

> 请求者 claude（编排者兼独立评审）｜2026-09-18｜咨询者 codex（read-only）
> 合入前第二签名。本仓双签名规则要求 `consult.decision == ACCEPT` 才可进入
> `APPROVED_FOR_MERGE`。编排者已判 ACCEPT（`WP-28-review-rev6.md`）。

## 你要裁决什么

给出 `ACCEPT` 或 `REWORK`（含具体阻断项）。判据是：**本轮 diff 是否兑现了下方内联的
rev6 冻结 brief**，以及是否存在 correctness / architecture / security / 削弱测试信号
一类的阻断项。

- 冻结 brief：`WP-28-brief-rev6.md`，sha256
  `ee57a96c5f15157e70817ea9e4a99b520a214b3be874e7ae2e35e045229335fd`
- 被审提交：`361b3ad`（起点 `2923255` = rev5 交付）
- 累积 diff：`7a30f50..361b3ad`（3 文件 / +709 −4）
- 本轮增量：`2923255..361b3ad`（3 文件 / +61 −39）
- worktree：`/Users/admin/vibe/wp28-norms-into-template`

## rev6 的由来：你在 rev5 轮判的 REWORK 已被采纳

你在 rev5 轮给出唯一阻断项 R1「`_mutate_on_disk` 的异常恢复边界不完整」，五条 evidence
全部成立（变异写入在 `try` 之外；`write_bytes()` 部分写入不可恢复；`finally` 内逐文件
inline assert 会中止后续恢复；报告的 `assert False` 只覆盖主体异常）。

编排者复核后判定**根因在计划侧，且与 rev5 同源**：rev5 brief 把「变异须落到判据真实的
输入面」翻译成了「写那两个真实模板文件的字节」——输入面指的是「一个文件的字节」这个面，
不是那两个特定路径。连续两轮根因都在编排者的 brief 措辞上。

第 6 次冻结再次触发「同一 WP 第 3 次及以后 re-freeze 强制停手复核计划」规则
（`WP-28-plan-review-before-rev6.md`）。停手复核时**先实测了两种修法再写 brief**：

- 方案 A（按你的五条 required_fix 原地硬化）：实测有效（第二份 guard 失败时两份都恢复；
  主体抛异常与正常路径均恢复），但 `finally` 内第一份写入抛错时该文件仍无法恢复
  （磁盘真写不进去，无法可为）——风险面被压小，没有消除。
- 方案 B（变异临时副本）：实测承重性完全保留（撤销 B49 fix 后两条用例仍转红），
  且 B54 整个失败类不存在——判据保护的正是「模板逐字节冻结」，而 rev5 载具的失效模式与
  保护目标同向，这类载具本身就不该存在。

用户选择方向 2 = 方案 B + 顺带把这条口径折进模板 oracle。故 rev6 只有两个标的：

1. **换载具**：`M-T0`/`M-T0b` 改为把变异写到 `tmp_path` 下的临时副本，删除
   `_mutate_on_disk`；判据读副本路径。保留 no-op guard（`mutated != original`）与
   `_crlf_rewrap_bytes()` 及 witness code 断言。新增断言：两份真实模板在用例前后
   **字节完全一致**（brief 明确禁止把 sha256 硬编码进用例，须运行时快照对比）。
   报告须给出「撤销 B49 fix 后两条用例转红」的实测。
2. **同步口径**：两份模板 oracle 第 4 项末尾各追加两行（3 空格缩进）——
   「同类输入面的等价载体（如临时副本）满足本项；若变异会写到被判据保护的制品本身，
   须优先选用不写该制品的等价载体。」并同步 `FROZEN_BODY_ACCEPTANCE` 常量。

**承诺边界未变**，仍是 rev3 缩小后的 INV-N1（受保护块身份逐字节）+ INV-N3（副本同一）。

## 本轮范围外，请勿据此判 REWORK

- **B52**：`SECTION_BODY_TRUNCATED` 谓词归因过宽（任务 #42），独立 WP。
- **B47**：`dispatch_lint.sh` 按固定命名读 `WP-28-brief.md` 而非 `evidence.brief.path`，
  revN brief 从未过段落门禁（任务 #38），独立 WP。rev6 三段由编排者独立核。
- **E1/E2/E3 三条边界逃逸**（整档注释 / BOF 未闭合 `<!--` / `## 附注` 内未闭合围栏）：
  rev4 起即为**声明的承诺边界**，不在 INV-N1/N3 之内，实测仍返回 `[]`。
- **3.13/3.14 未实测**：环境未装 pytest，与 rev5 同。

## 编排者已自查过、可交叉核验的事实

| 项 | 结果 |
|---|---|
| 目标文件 | `32 passed` |
| 全量 | `4 failed / 631 passed / 4 skipped`，4 failed 全在 `tests/test_finalize_merge_triple_sign.py`（既有环境失败，`git checkout -q main`） |
| 零回归算术 | `def test_` 全仓 514→514、目标文件 31→31、用例名集合 `diff` 空 |
| 范围 | 改动恰为 `allowed_paths` 三项；`contract_render.py` / `init_cmd.py` / `pyproject.toml` / `AGENTS.md` / `CLAUDE.md` 零 diff |
| 判据函数体 | 7 个未变（逐函数体 sha 对比）：`_read_text_preserving_newlines` / `_check_both` / `_inv_n_codes` / `_mutate_both` / `_crlf_rewrap_bytes` / `_classify_body_diff` / `_extract_body` |
| 模板双副本 | `cmp` IDENTICAL，两份 sha256 均 `bf2cb2858e37c53202259c830be601c074f0e920d8e1d3ea91b59fdb701595e5` |
| 全仓写入面 | 无任何 `write_bytes` / `write_text` / `open(...,"w")` 指向 `TEMPLATE_PACKAGED` / `TEMPLATE_DOCS` |
| 编排者自撰 5 探针（执行者未见过） | O1 撤销 B49 fix → `2 failed`；O3 重新植入 B54 形状（载具改回写真实文件）→ `2 failed`；O4 常量脱同步 → `7 failed`；O5 变异退化为恒等 → `2 failed`；O2 删 no-op guard → `2 passed` |

O2 是一个值得你注意的形状：删掉 no-op guard 用例仍绿，但把变异函数退化为恒等（O5）
就转红——guard 承的是 O5 那一维，单看「删掉是否转红」会误判其承重性。编排者已把这条
写进 review 文档的遗留项，不作为本轮阻断。

## 请特别检查

1. 新载具 `_copy_bytes_to_tmp` 是否真的让「读路径」成为变异字节到 witness 之间的唯一
   环节，还是又绕开了某个环节（对照 rev4 的 B49 教训：变异施加于判据已持有的内存值）。
2. 「真实模板字节前后一致」的新断言是否真能挡住 rev5 那类载具（编排者 O3 探针说能，
   请独立判断该断言的覆盖面：它只在用例末尾比对，用例中途的写入+还原能否漏过）。
3. oracle 第 4 项追加的两行是否与该项既有文字冲突，是否与两份模板及
   `FROZEN_BODY_ACCEPTANCE` 三处一致。
4. 是否有任何测试阈值、witness 语义、断言强度在本轮被削弱。

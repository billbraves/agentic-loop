# WP-29 阶段 1 rev4 第二签名咨询（codex）

> 咨询日期 2026-09-19 | 发起：Claude（编排者）| 目的：合入前的独立第二签名
> 第一签名：`WP-29-review-rev4.md`（ACCEPT），sha256 `59a53368d70f7507168c2851c474d21a5701262ce048986570f5b33e1a06e78c`

## 被审对象

- 交付物：`docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md`
- worktree：`/Users/admin/vibe/wp29-render-scope-decision`，分支 `feature/wp29-render-scope-decision`
- 提交：`f1eee7e`（基线 `e493c2a`，1 file，+137/−37，纯文档）
- 冻结 brief：`WP-29-brief-rev4.md`，sha256 `03a56829bd661aa32762fbc973033d36d4b01a8e17724f12e3ebde2f2fa2e422`

## 背景：为何有 rev4

rev3 被双签名判 REWORK，根因缺陷 **B57**：交付物 §1 声称给出「仓库级完整 grep 输出」，
但实际粘贴的是**加了未声明过滤**（`--exclude=WP-29-scope-decision.md`）后的输出；而我
（第一签名）在核验时**给自己的重跑加了同一个未声明过滤**，于是「39/39、47/47 逐行一致」
必然成立，判据无法发现缺陷。即：声明面与所用面不一致，且验证者复制了同一偏差。

rev4 因此引入机械判据 **标的 0**：

> §1 里每一个形如 `$ <命令>` 的命令块，按字面原文重跑，其输出行数必须等于紧随其后
> 粘贴的输出块行数。

推论：过滤必须出现在命令文本里（不得是散文括注）；粘贴输出须逐字零省略；任何声明的
行数/条数必须能从粘贴块数出来。

## 第一签名的结论与证据（供你独立复核，不必采信）

标的 0 重跑（`/usr/bin/grep`，BSD grep，worktree 根，命令文本逐字取自粘贴块）：

| 块 | 命令 | 粘贴 | 重跑 | diff |
|----|------|-----|-----|------|
| 1 | 主 grep `WORK_PACKAGE\.md\.tmpl` | 38 | 38 | identical |
| 2 | 主 grep `docs/agentic/templates/WORK_PACKAGE\.md` | 46 | 46 | identical |
| 3 | `comm -23` 宽口径差集 | 17 | 17 | identical |
| 4 | `load_template` 调用点 | 6 | 6 | identical |
| 5 | `_resources_files` 资源入口 | 4 | 4 | identical |

排除项代价实测：`--exclude=WP-29-scope-decision.md` 移除 51/59/122 行（自指）；
`--exclude=WP-28-consult-codex-shape-verdict.json` 移除**恰 1 行**（`:6`，单行 9574 字节）。
宽口径 96 = 两条主 grep 并集 79（38+46−5 重叠）+ 差集 17（15 C 类 + 2 行重分类为 B 类）。
`git diff -U0` 显示旧行 193..363 零 hunk ⇒ §2/§3/§4/§5（含 (c′) 裁定）逐字未动。
基线 4 failed / 606 passed / 4 skipped，4 个失败均为既有（`git checkout -q main` 与本机
`init.defaultBranch=master` 冲突）。

## 请你独立裁定的四个问题

**Q1（核心）：标的 0 是否真的闭合了 B57，还是只把偏差挪了一层？**
rev4 的做法是「把过滤写进命令文本」。这让声明面与所用面一致了；但**过滤本身仍在**——
被排除的 1 行 codex 二签记录与 51/59/122 行自指命中，都不在粘贴的「完整输出」里。
「声明即所用」是否足以支撑 §1 仍自称「仓库级消费面证据」？还是说这类判据必须同时约束
「排除项不得改变被回答问题的答案」，而不仅仅是「排除项须声明」？

**Q2：执行者对标的 2 的替代是否可接受？**
brief 标的 2 要求两处省略（`:47`、`:90`）「都改为逐字完整粘贴该 grep 输出行（整行，含长
JSON 内容）」。执行者改为在命令里 `--exclude` 掉该文件 + 文中说明理由 + 在 C 类按行号点名。
我判其等效可接受（同样达成零省略与声明即所用，损失恰 1 行且该行被点名归类），并登记
**B59**（brief 把手段而非目的写进判据）。你是否同意？若不同意，请说明该 1 行的缺席
具体如何改变 C1（「谁把模板当作活动 Markdown 结构来解析」）的答案。

**Q3：我自己的复核失效（B58）是否还有未清的残留？**
我首轮判 BLOCK1/2/3 DIFFERS，后查明是**假红**：本机 shell 的 `grep` 是指向 `ugrep` 的函数壳，
注入 `--ignore-files --hidden -I` 且不输出 `./` 前缀。我改用 `/usr/bin/grep` 后全部 identical。
问题：一个「字面重跑」判据，若不约束执行面（binary 身份、locale、cwd、shell 函数），是否
本质上不可机械化？B58 的修法应当是「重跑前核验 `type`」，还是「判据本身必须携带
可复现的执行面声明（如绝对路径 binary + `LC_ALL=C` + cwd）」？

**Q4：量词是否已真正收敛？**
交付物 §1 D 类写「『读取 package data 的入口只有 `load_template` 一处』在 `src/` 运行时源码
这一搜索面内成立」，并申报 `cli.py:25` 的未覆盖面（用 `importlib.resources.path()` 定位
打包 wrapper，不读模板）。这是否满足「封闭模型或有界声明」的要求？还是仍留有同族未覆盖
形态（例如通过 `__import__` / `importlib.import_module` 动态取资源、或 `pkgutil.get_data`）？

## 约束（请勿越界）

- 你只做**只读**审核，不改文件、不提交、不合并、不推送。
- **不要**评判 (c′) 裁定本身该不该被采纳——那是 §5 的内容，rev4 逐字未动，且其批准权在用户。
- **不要**设计阶段 2。
- 请只回 `ACCEPT` / `REWORK` / `CONSULT` 之一，并给出具体证据（文件 + 行号 + 可重跑命令）。

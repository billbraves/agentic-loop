# WP-29 阶段 1 rev4 独立复核（第一签名 · Claude 编排者）

> 复核对象：`docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md`
> 被审提交：`f1eee7e`（worktree `/Users/admin/vibe/wp29-render-scope-decision`，分支
> `feature/wp29-render-scope-decision`，基线 `e493c2a`）
> 冻结输入：`WP-29-brief-rev4.md`，sha256 `03a56829bd661aa32762fbc973033d36d4b01a8e17724f12e3ebde2f2fa2e422`
> 复核日期：2026-09-19 | 结论：**ACCEPT**（第一签名；第二签名待 codex）

---

## 0. 复核者自身的失效与更正（先记，因为它决定了本轮判据的可信度）

首轮我对标的 0 的重跑判定为 BLOCK1/2/3 **DIFFERS**。该判定是**假红**，根因在我自己的
执行环境，不在交付物：

```
$ type grep
grep is a shell function from /Users/admin/.claude/shell-snapshots/snapshot-zsh-*.sh
  -> exec -a ugrep "$CLAUDE_CODE_EXECPATH" -G --ignore-files --hidden -I \
       --exclude-dir=.git --exclude-dir=.svn --exclude-dir=.hg ... "$@"
$ grep --version | head -1
ugrep 7.8.4 aarch64-apple-macosx
```

即：我 shell 里的 `grep` 是指向 `ugrep` 的函数壳，且**注入了交付物未声明的
`--ignore-files --hidden -I` 等过滤**，并且不输出 `./` 路径前缀。对照：

```
$ grep    -rn 'WORK_PACKAGE\.md\.tmpl' . | head -1
tests/test_wp_template_dispatch_lint.py:23:...        <- 无 ./，ugrep
$ /usr/bin/grep -rn 'WORK_PACKAGE\.md\.tmpl' . | head -1
./tests/test_wp_template_dispatch_lint.py:23:...      <- 有 ./，BSD grep
```

**这正是 B57 的镜像形态**：上一轮我给「完整输出」判据偷加了自己的过滤器，造成假绿；
这一轮我的 verifier 偷换了 `grep` 实现，造成假红。两者同一病根——**验证者未核验自己的
执行面与被验证命令的字面一致性**。故本复核的全部重跑改用 `/usr/bin/grep`，并在下文
逐条给出重跑口径。

> 新缺陷 **B58**（复核者侧）：重跑「字面命令」前须核验 `type <cmd>` / `command -v <cmd>`，
> 确认没有 alias / shell function / 同名异实现注入未声明的过滤。登记入任务 #46 同一批。

---

## 1. 标的 0（机械判据）：§1 每个 `$ <命令>` 块字面重跑，输出行数与紧随的粘贴块相等

重跑口径：`unset -f grep` 后以 `/usr/bin/grep`（BSD grep）在 worktree 根执行，命令文本
逐字取自交付物粘贴块（含续行反斜杠），**不追加任何自有过滤**。

| 块 | 交付物行 | 命令 | 粘贴行数 | 重跑行数 | 逐行比对 |
|----|---------|------|---------|---------|---------|
| 1 | `:39-41` / 粘贴 `:42-79` | 主 grep `WORK_PACKAGE\.md\.tmpl` | 38 | 38 | **IDENTICAL** |
| 2 | `:83-85` / 粘贴 `:86-131` | 主 grep `docs/agentic/templates/WORK_PACKAGE\.md` | 46 | 46 | **IDENTICAL** |
| 3 | `:142-148` / 粘贴 `:150-166` | `comm -23` 宽口径差集 | 17 | 17 | **IDENTICAL** |
| 4 | `:180` / 粘贴 `:181-186` | `load_template` 调用点 | 6 | 6 | **IDENTICAL** |
| 5 | `:226` / 粘贴 `:227-230` | `_resources_files` 资源入口 | 4 | 4 | **IDENTICAL** |

不仅行数相等，且 `diff` 逐行**零差异**。判据的三条推论亦满足：

- **推论 1（过滤须在命令文本里）**：三条 grep 的 `--exclude=WP-29-scope-decision.md`
  `--exclude=WP-28-consult-codex-shape-verdict.json` 均写在命令行内，非散文括注。
- **推论 2（零省略）**：`grep -c '…'` = 0、`grep -c '……'` = 0（全文，非仅 §1）。
- **推论 3（声明的计数可从粘贴块数出来）**：见 §3。

**标的 0：PASS。** 这是 rev3 判 REWORK 的直接原因（B57），本轮已闭合。

## 2. 标的 1：主 grep 的排除项声明与最小性

交付物选了「做法 A」（把过滤写进命令 + 文中说明理由），未选做法 B。排除项的实际效果实测：

| 模式 | 无排除 | −自指 | −自指 −codex 二签 | 自指移除 | codex-json 移除 |
|------|-------|-------|------------------|---------|----------------|
| `WORK_PACKAGE\.md\.tmpl` | 90 | 39 | 38 | 51 | **1** |
| `docs/agentic/templates/WORK_PACKAGE\.md` | 106 | 47 | 46 | 59 | **1** |
| 宽口径 `WORK_PACKAGE` | 219 | 97 | 96 | 122 | **1** |

两点值得记录：

1. **排除集是最小的**。`WP-28-consult-codex-shape-verdict.json` 全文只有 **1 行**含
   `WORK_PACKAGE`（`:6` 的 `raw_verbatim`，单行 9574 字节，为本仓最长行）。即该排除项
   代价恰为 1 行，不是一个可藏东西的宽口径过滤。
2. **理由写在文中且可核**：交付物 `:134-136` 给出排除理由，并在 C 类 `:214-215` 把被排除的
   `WP-28-consult-codex-shape-verdict.json:6` **按行号点名并归类**，未让它从证据面消失。

**标的 1：PASS。**

## 3. 标的 2：两处省略（`:47`、`:90`）的处置——执行者做了替代方案

brief 原文要求：两处「都改为**逐字完整粘贴该 grep 输出行**（整行，含长 JSON 内容）」。
执行者改为**在命令里显式 `--exclude` 掉该文件**，并在文中说明理由 + 在 C 类按行号点名。

判定：**接受该替代**。理由三条：

- **满足判据本意**。标的 2 的目的是消灭「声明与所用不一致」（B57），手段是零省略。
  执行者路径同样达成零省略：被排除的行不再出现在粘贴块里，因为它**也不在命令的输出里**——
  声明与所用一致，这正是标的 0 要保的东西。逐字粘贴 9574 字节单行同样合判据，但不是唯一解。
- **证据面损失可量化且已补偿**：损失恰 1 行（见 §2 表），且该行被 C 类按 `:6` 点名归类。
  对 C1（「谁把模板当活动 Markdown 结构解析」）的答案无影响：该行是 codex 二签对 INV-N3
  原文的引用，属认知消费，不是机器解析路径。
- **可读性不是借口，但此处是真实约束**：9574 字节单行嵌进 markdown 围栏，会让整个 §1
  的粘贴块实质不可人工核对；而标的 0 的机械可核性恰恰要求粘贴块能被人/机逐行比对。

**保留意见（不阻断）**：brief 写的是「都改为逐字完整粘贴」，执行者换了手段而未回到编排者
确认。本轮我判其等效且更优，但流程上更稳妥的是在报告里显式标注「偏离 brief 字面要求，
理由如下」。**这是给 brief 写法的反馈，不是给执行者的返工项**：标的 2 把「手段」写进了
判据，而应写「目的 + 可接受手段集」。登记为 **B59**（brief 判据过度指定手段）。

## 4. 标的 3：宽口径差集 17 行与两处 B 类重分类

- 宽口径算术自洽且实测吻合：宽口径 96 行、两条主 grep 并集 79 行（38 + 46 − 5 重叠）、
  差集 17 行。四个数我独立实测全部一致（`comm -12` 实测重叠 = 5）。
- 17 行的归类闭合：**15 行 C 类**（非 `docs/plans/` 5 行 + `docs/plans/` 10 行，交付物
  `:207-213` 逐个点名）+ **2 行 B 类**（`test_init_contract.py:62`、
  `test_wp_template_dispatch_lint.py:24`）= 17。两处 B 类重分类正确：这两行是测试读取模板
  做断言，属「测试验证」而非「人/agent 阅读」。
- 差集由 `comm -23` 字面求得，非手挑，且该命令本身通过标的 0（块 3）。

**标的 3：PASS。**

## 5. 标的 4：`load_template` / `_resources_files` 与量词诚实性

引用的行号我逐条独立核验，全部准确：

| 交付物断言 | 实测 |
|-----------|------|
| `init_cmd.py:109` 唯一把 `.md.tmpl` 映到 `docs/agentic/templates/WORK_PACKAGE.md` | ✅ `("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),` |
| `init_cmd.py:148` 调 `load_template`，随后逐字节 `write_text` | ✅ `:148` 调用、`:150` `target.write_text(text, encoding="utf-8")` |
| `init_cmd.py:253-254` 对 `_REFERENCE_TEMPLATES` 逐项 `_write_asset` | ✅ |
| `contract_render.py:19/21/252/254` 四行即 `_resources_files` 全部命中 | ✅ `:19` import、`:21` None 回退、`:252` None 守卫、`:254` 唯一调用 |
| `contract_render.py:255` `read_text(encoding="utf-8")`，不解析 Markdown | ✅ |
| `pyproject.toml:24-29` artifacts 含 `src/agentic_loop/templates/*.tmpl` | ✅ |

**量词已收敛（本轮关键改进）**：交付物 `:234-235` 写的是「故『读取 package data 的入口只有
`load_template` 一处』在 **`src/` 运行时源码这一搜索面内**成立」——点名了所覆盖的输入维度，
而非裸的全称断言。并在 `:249-251` **主动申报未覆盖面**：`cli.py:25` 也 import
`importlib.resources`（别名 `_resources`），但只用 `.path()` 定位打包 wrapper
（`:119` / `:222`），不读模板 package data。我独立扫 `src/` 全部
`importlib.resources` 使用点，结果与申报一致，无第四处。

**标的 4：PASS**（含量词诚实性）。

## 6. PRESERVED：§2–§5 是否逐字未动

`git diff -U0 e493c2a f1eee7e` 的 hunk 头（旧文件行号）：

```
@@ -1 / -7,2            §0 头部 + 摘要
@@ -33 / -36 / -47 / -79 / -90 / -129 / -132 / -135 / -136,0 / -147,2 / -151,3 / -156,8 / -168 / -173 / -180,0    §1（旧 28..192）
@@ -364 / -385,0       §6 标题 + 新增 6.2
@@ -389 / -399,2 / -413 / -417,2 / -420    §7 selfcheck
@@ -441,2 / -443,0 / -451    附：DoD 对照
```

旧版章节边界：§2 在 `:193`、§3 `:222`、§4 `:255`、§5 `:327`、§6 `:364`。
**旧行 193..363 区间零 hunk** ⇒ §2 / §3 / §4 / §5（含 (c′) 裁定）**逐字未动**。
§6 只新增 `6.2` 子节并把标题从「rev1 → 本轮」改为「rev1 → rev4」，§7 与 DoD 附录的改动
均为本轮 §1 证据的同步记账。范围与 brief 的 方向 1 一致，**无越界**。

## 6b. 标的 0 范围外的抽查（超出 brief 要求，主动做的）

标的 0 只约束 §1。但 §2 在 `:271` 另有一个 `$ git remote -v` 块，且 §2 的三条否定性断言
（无 `.github`、无静态站点生成器配置、全仓无权威方言声明）本轮虽逐字未动，却从未被任何
一轮判据重跑过——正是「增量复核漏掉前几轮」那一类逃逸。故独立实测：

| §2 断言 | 实测 |
|---------|------|
| origin 是 GitLab | ✅ `git@github.com:billbraves/agentic-loop.git`（fetch/push 同一） |
| 无 `.github` 目录 | ✅ 不存在 |
| 无 `mkdocs.yml` / `docusaurus` / `sphinx` / `_config.yml` 等 | ✅ 逐个探测均不存在 |
| 全仓无权威 Markdown 方言声明 | ✅ `CommonMark\|GFM\|GLFM` 全仓唯一命中就是本交付物自身 |

四条全部成立。§2「不存在权威单一渲染器」这一支撑 (c′) 不走 parser 路线的事实**可复现**。
（注：本节是对 §2 的事实核验，**不**是对 (c′) 裁定是否该被采纳的判断——后者属用户。）

## 7. 门禁与基线

| 项 | 结果 |
|----|------|
| 改动文件 | 仅 `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md`（1 file，+137/−37） |
| `allowed_paths` | 未越界；`git diff --name-only` 单文件 |
| 模板零 diff | `TEMPLATES_UNCHANGED`（`src/agentic_loop/templates/` + `docs/agentic/templates/`） |
| `pyproject.toml` 零 diff | `PYPROJECT_UNCHANGED` |
| 两份模板同一 | `wc -c` 均 2889，`cmp` → `IDENTICAL` |
| worktree | clean |
| 跨 worktree 回写主区 | 无（主区 `.status.json` 仍由编排者维护） |
| 测试基线 | **4 failed, 606 passed, 4 skipped**，与 brief 声明的基线一致 |
| 4 failed 归因 | 全在 `test_finalize_merge_triple_sign.py`，`git checkout -q main` 与本机 `init.defaultBranch=master` 冲突，**既有失败**，与本轮纯文档改动无因果 |

## 8. 结论

**ACCEPT（第一签名）。**

rev3 的判 REWORK 原因（B57：声明即所用）已以机械可核的方式闭合——五个粘贴块全部字面重跑
逐行一致，零省略符，排除项写进命令文本且代价可量化（codex-json 恰 1 行）。宽口径差集补到
完整 17 行并归类闭合。量词从裸全称收敛为「点名搜索面 + 申报未覆盖面」。§2–§5 含 (c′) 裁定
逐字未动，范围严守 方向 1。

**本轮新登记缺陷（均不阻断本 WP）**：

- **B58**（复核者侧，优先）：重跑「字面命令」前须核验 `type` / `command -v`，防 alias、
  shell function 或同名异实现注入未声明过滤。本轮我自己踩中，造成假红。
- **B59**（brief 侧）：标的 2 把「逐字粘贴」这一**手段**写进判据，而应写「零省略 +
  声明即所用」这一**目的** + 可接受手段集，否则等效更优解会被判偏离。

**仍属用户权限、本复核不触碰**：

1. **(c′) 裁定本身尚未获批**。本复核只判「§1 证据是否可字面重跑」，不判 (c′) 是否采纳。
2. **合入需用户批准**，本复核不合并、不推送。
3. 阶段 2 的冻结依赖 (c′) 获批，未启动。

**下一步**：派发 codex 第二签名；二签到位后再行裁定，合入仍待用户批准。

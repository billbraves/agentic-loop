# WP-29 阶段 1 rev7 第一签名（编排者 Claude）

> 审核日期 2026-09-20 | 与 codex 二签**并行**产出，写此文时未读二签结论
> 冻结 brief：`WP-29-brief-rev7.md`（sha256 `527a741298d530f6d7493fe2e452b6aa287e02439e0ba0f5c9c037ca4823e607`）
> 被审提交：`e6b733047c9b325c17f5cb8824cfbdb81f6f85b0`（基线 `dffae33`，纯文档，单 hunk）
> 执行者自报 `[STATUS] DONE`，session `8c062249-467c-4390-870b-e19b300d6972`，exit 0

## 结论

**ACCEPT**

单句返工按判据完成，十条判据全 PASS，无阻断项。一处非阻断观察记于文末 N1。

## 本轮的改动全貌

```
$ git diff --stat dffae33..e6b7330
 docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

$ git diff -U0 dffae33..e6b7330 | /usr/bin/grep -c '^@@'
1
```

唯一 hunk `@@ -514,8 +514,7 @@`（§6.4 首句，原两行合为一行）：

```diff
-本 rev 是五轮里唯一不动证据的一轮（零重跑、零新命令、零新输出），只改本文件对自身版本 /
-提交 / 节结构 / 命令形态的描述，使其与现行内容同真（INV-S1）：
+本 rev 不改 §1 证据面与 §2–§5，只收口自指陈述，并按实跑刷新 §7 自核查的数字：
```

## 判据逐条

执行面：`/usr/bin/grep`（BSD grep 2.6.0-FreeBSD，避开 `ugrep` 函数壳造成的假红，B58）、
`LC_ALL=C`、cwd `/Users/admin/vibe/wp29-render-scope-decision`、`bash`。

| # | 判据 | 结论 | 取证 |
|---|---|---|---|
| 1 | `:517` 新写法合格（无轮数/序数、不声称零重跑/零新输出、与 §6.4 后续不矛盾） | **PASS** | 见下方「判据 1 展开」 |
| 2 | 新写法对 rev8 成立 | **PASS** | 见下方「判据 2 展开」 |
| 3 | 本轮新增/改写行自身满足 INV-S1（定稿后再扫） | **PASS** | 执行者报告给出扫法与结果；我独立复跑见下 |
| 4 | 未新增修订史条目 | **PASS** | `/usr/bin/grep -n '6\.5' → 无命中`；`/usr/bin/grep -n 'rev7\|rev 7' → 无命中` |
| 5 | §7 与 DoD 对照零改动 | **PASS** | 分区字节哈希 §7 `46895a3d…`、DoD 尾 `7354a96e…` 两版一致 |
| 6 | §1 证据面零改动 | **PASS** | §1 分区哈希 `0ade8aab…` 两版一致 |
| 7 | §2–§5 零改动（含 (c′)） | **PASS** | §2 `a926fd3d…` / §3 `2364ebf2…` / §4 `068be8ed…` / §5 `a4705650…` 均一致 |
| 8 | §6.1–§6.3 零改动，§6.4 除标的句外零改动，`:458` 未被顺手更正 | **PASS** | §6 lead `13ebf732…` / §6.1 `6ccf9f74…` / §6.2 `d29adb11…` / §6.3 `1777a6ad…` 一致；§6.4 是唯一 CHANGED 分区 |
| 9 | 两条 9659 长行零改动 | **PASS** | `awk 'length($0)>1000{print length($0)}'` 在 `dffae33` 与 `e6b7330` 均输出两行 `9659` |
| 10 | 零代码改动 | **PASS** | `git diff --stat` 只含 `WP-29-scope-decision.md` |

分区哈希表（我自己跑的否证尝试，全部落空 → 支持交付物自身的保留区声明）：

```bash
# 在 worktree 内
git show dffae33:docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md > /tmp/wp29-rev6.md
git show e6b7330:docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md > /tmp/wp29-rev7.md
# 按 '^## N.' / '^### 6.N' 切分，逐区 sha256 前 16 位比对
# 结果：14 个分区中仅 §6.4 为 CHANGED（02f2bef3… → 49a5827f…），其余 13 区全 SAME
```

### 判据 1 展开

三条必须满足项逐条：

**(a) 无轮数/序数、不以「本文件是第几版」为前提** —— PASS。

```bash
$ sed -n '517p' docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md \
  | /usr/bin/grep -n '五轮\|六轮\|零重跑\|零新命令\|零新输出\|唯一一轮\|第 *N *轮\|第[一二三四五六七八九十]轮'
（无输出）
```

全文范围内该族残留仅一处：`:458`「（上一轮，已提交 `e493c2a`）」，**brief 明写获豁免**
（§6.x 条目描述其自身主题那一轮的语境），不得改动 —— 交付物确实未动它。

**(b) 不声称本轮未发生的「零重跑 / 零新命令 / 零新输出」** —— PASS。新句不含该族任何词。

**(c) 与 §6.4 后续条目不矛盾** —— PASS。新句说「按实跑刷新 §7 自核查的数字」，
与同小节 `:523`「哈希按实跑更新」、`:524`「§7 diff stat：按实跑更新」**方向一致**。
原句的「零重跑」正是与这两条相反，这一矛盾已消除。

（行号说明：两行并一行后，rev6 时的 `:524`/`:525` 现为 `:523`/`:524`。）

### 判据 2 展开（本轮核心）

新句只作三个关于 **rev6 那一轮实际动作**的历史断言。我逐条否证，全部落空：

**断言 (a)「不改 §1 证据面与 §2–§5」**：rev6 的 hunk 在 rev5 侧起始行为
`1, 8, 455, 497, 513, 517, 527, 573, 577, 590, 601`。rev5 时 §1 为 29–283、§2–§5 为 284–454。
落在 29–454 内的 hunk 数为 **0**。断言真。

```bash
git diff -U0 e2c483d..dffae33 -- docs/plans/.../WP-29-scope-decision.md \
  | /usr/bin/grep '^@@' | sed 's/^@@ -\([0-9]*\).*/\1/' \
  | /usr/bin/awk '$1>=29 && $1<=454 {print "IN RANGE: "$1}'
（无输出）
```

**断言 (b)「只收口自指陈述」**：§6.4 的八条 bullet 逐条对应 rev6 的实际 hunk（标题、头注、
§6 节标题、§6.3 节标题、§7 HEAD 标注、§7 diff stat、§7「全量」标签、DoD 对照），无遗漏项。

**断言 (c)「按实跑刷新 §7 自核查的数字」**：rev6 确实刷新了三处数字。

```bash
$ git diff e2c483d..dffae33 -- …/WP-29-scope-decision.md | /usr/bin/grep '^[-+].*insertions\|^[-+].*passed\|^[-+].*HEAD `'
-…HEAD `f1eee7e650c300c0cdc8be42a0c879961ebc83d8`（rev5 提交）执行。
+…HEAD `e2c483d26ef9999ac77aaaa22db59b2e0db5abe4`（本轮修订的基线提交 / 父提交）执行。
-# ->   1 file changed, 72 insertions(+), 22 deletions(-)
+# ->   1 file changed, 30 insertions(+), 12 deletions(-)
-4 failed, 606 passed, 4 skipped in 116.99s
+4 failed, 606 passed, 4 skipped in 96.04s (0:01:36)
```

三个断言都是**既成事实**，不随本文件版本号递增而改变。§6.4 标题「rev5 → rev6 改了什么」
把句中「本 rev」收口到该条目的主题轮 rev6 —— 与 `:480` §6.2 标题里的「本轮」同一形状，
brief 对该形状明文豁免。故 rev8 视角下新句仍真。判据 2 PASS。

执行者报告给出的理由与此一致，且是它自己写的（不是我补的）。

### 判据 3 展开

执行者报告：定稿后、`git commit` 前对唯一改动行（`:517`）用 `/usr/bin/grep` 扫禁词族，
零命中；另目检确认无序数、无「第几版」前提、无「零重跑/零新输出」、与 `:523`/`:524` 一致。

我独立复跑同一扫描（见判据 1(a) 的命令），同样零命中 —— **否证落空**。
这是 rev6 翻车的那一面，本轮未复发。

### 零回归基线（我自己实测）

```
$ cd /Users/admin/vibe/wp29-render-scope-decision && PYTHONPATH=src python3.11 -m pytest tests -q
4 failed, 606 passed, 4 skipped in 118.15s (0:01:58)
# 4 failed 全在 tests/test_finalize_merge_triple_sign.py（git checkout -q main /
# 本机 init.defaultBranch 与 fixture 冲突），既有失败
```

与 brief 声明的 `4 failed / 606 passed / 4 skipped` 一致。

**并且**：我这次的挂钟 118.15s、执行者报告的 132.31s、§7 里记的 96.04s **三者都不同**，
而 §7 仍是 96.04s —— 正是判据要的结果。执行者没有去追平，硬禁止 2 守住了。

## 隔离与风险

- worktree `git status --porcelain` 为空（工作树干净）；分支 `feature/wp29-render-scope-decision`。
- 无 push：`origin/feature/wp29-render-scope-decision` 不存在（远端无该分支）。
- 无 merge、未切生产分支。
- 主区工作目录变更集与会话开始时一致（6 M + 2 ??，均为本 WP 之外的既有未提交项），
  **无跨 worktree 回写**。
- `production_writes` / `network` / `notifications` 均 FORBIDDEN，`data_access` READ_ONLY，未触碰。

## 非阻断观察

**N1（措辞强度，不构成 REWORK）**：新句用「本 rev」而非显式「rev6」。二者在
§6.4 标题的语境下等价，且「本 rev」是 brief 自己给出的参考写法（brief `:44`），
执行者近乎逐字采用（仅把首个「：」改为「，」、把列表导引「：」移到句末，语义不变）。
但指示代词比显式轮号弱：若未来某轮移动或改写 §6.4 的标题，收口就会失效。

我**不**据此判 REWORK —— 那会是签名者在审时追加冻结 brief 之外的判据（B60 的另一面），
且要判的正是 brief 自己写的参考措辞。记为下一轮可选建议：§6.x 条目内的「本轮 / 本 rev」
一律改为显式轮号，把收口从「依赖标题」变为「不依赖任何上下文」。

## B60 自查（签名者约束）

- **未用自己的重跑替交付物补证**：我跑的分区哈希、rev5 侧 hunk 落点、`awk` 长行、pytest
  基线，全部是**否证尝试**，结论都是「落空」，即支持交付物自身已给出的声明；没有一条
  PASS 是靠「我跑出但交付物没写」的证据支撑的。判据 2 的历史事实核验是判据本身要求
  签名者独立裁定的内容（执行者给理由，我判理由是否成立），不是补证。
- **未追认任何「等效替代」**：执行者未替换任何判据；它把对判据的观察写进 `[CONCERNS]`
  而非自行改判据，符合 B60。
- **未追加冻结 brief 之外的新判据**：唯一可能越界的 N1 已明确降级为非阻断建议。
- **未评判 (c′)**（§5 内容，批准权在用户，已批准），**未评判 §6.x 豁免本身**
  （经停手复核并获用户批准路 A），**未设计阶段 2**。

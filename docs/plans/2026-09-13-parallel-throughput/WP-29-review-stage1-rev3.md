# WP-29 阶段 1 rev3 独立复核

> 复核者 claude-code（编排者兼独立复核者）| 复核日期 2026-09-19
> 被复核对象：`feature/wp29-render-scope-decision` @ `e493c2a62e14f9a7f9fc5528168b9be5d2b2bf23`
> 交付物：`docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md`
> （458 行，sha256 `f98b571375c260b8ca3d41ac69442a80b8687e0ce1097b8c646057d98d4400f2`）
> 冻结输入：`WP-29-brief-rev3.md`（sha256 `05b00b729f52eb2b38eadf27ddfe4b234108be3dae2ef477c022b647f3c2889d`，
> 复核时重算一致，与 `WP-29.status.json` 的 `evidence.brief_rev3.sha256` 相符）
> 本轮是 rev1（`bd4ac7a`）的原地修订，处置 codex 第二签名的 C1 / C2 与编排者自陈的四处缺陷。

## 裁定

**ACCEPT**（第一签名）。两个阻断项 C1、C2 均已闭合，且我逐条复现了交付物的每一项实测。
下列 3 条为不阻断的次要项，不要求返工，登记后随阶段 2 brief 一并处理。

阶段 2 **仍未冻结**，须用户批准本裁定后方可冻结；本 ACCEPT 不构成合入批准。

## 1. C1（消费面证据）—— 闭合

brief 标的 1 要求仓库级搜索、显式 `--exclude-dir`、原始命中行、A/B/C/D 四分类、
「唯一」带限定词、D 类给行号级结论。逐条复现：

| 要求 | 复核方式 | 结果 |
|---|---|---|
| 仓库级 grep + 显式 `--exclude-dir` | 在被审树重跑交付物粘贴的两条命令原文 | 命令可执行，参数与文档一致 |
| 粘贴的是**原始命中行**且完整 | 把 §1 两个代码块里以 `./` 开头的行抽出排序，与实跑输出 `comm` 逐行比对 | grep-1：39 / 39 行**逐行一致**；grep-2：47 / 47 行**逐行一致**（各含 1 行长 JSON 被显式标注为「全文略」，见次要项 M1） |
| A 类（运行时复制） | 读 `init_cmd.py:109` `_REFERENCE_TEMPLATES`、`:138-152` `_write_asset`、`:253-254` 循环 | 成立。`:148` `load_template` → `:149` `write_text`，无中间变换，逐字节复制 |
| B 类（测试验证） | `grep -rn 'WORK_PACKAGE' src/ tests/` | 成立：`test_init_contract.py:62`、`test_wp_template_dispatch_lint.py:23,24`，三处一个不多一个不少 |
| C 类（人 / agent 阅读） | 抽查 `AGENTS.md:84`、`templates/AGENTS.md.tmpl:84`、`QUICKSTART.zh-CN.md:202,230`、`README.md:70`、`CHANGELOG.md:88,328,330` | 全部成立 |
| D 类（打包读取）**零命中须明写** | `grep -cn 'WORK_PACKAGE' pyproject.toml src/agentic_loop/contract_render.py` | 两者皆 **0**。「零命中」的声明**正确**，且它给出的原因（`*.tmpl` glob + `name` 变量，都不含字面串）成立 |
| D 类行号级结论 | 读 `pyproject.toml:18-30`、`contract_render.py:18-19 / 27-28 / 250-255` | 全部核对一致：`[tool.hatch.build.targets.wheel]` 的 `artifacts` 含 `src/agentic_loop/templates/*.tmpl`；`load_template` 终点是 `resource.read_text(encoding="utf-8")`，**只做 UTF-8 解码，不解析 Markdown**。结论成立 |
| 「唯一」带限定词 | `grep -n '唯一'` 全文逐条看 | §0 / §1 / §6 / DoD 四处均为「唯一的**非测试运行时**消费者」，无限定版本**已消失** |

**我另做的一项加强核验**（交付物未写，不影响结论，见次要项 M3）：
包内模板还有第二条读取路径 `contract_render.render_template`（`:231-247`），它会把模板送进
`Template(...).safe_substitute` 做占位符替换。但 `contract_cmd.CONTRACT_FILES` 只含
`AGENTS.md.tmpl` / `CLAUDE.md.tmpl` / `OPERATING_MODEL.md.tmpl` 三份，
`WORK_PACKAGE.md.tmpl` **不在其中** —— 它走的是 `_REFERENCE_TEMPLATES` → `_write_asset` 的
纯复制路径。这条事实**加强**而非削弱交付物的结论：唯一会对包内模板做变换的路径也碰不到它。

## 2. C2（特异性与裁定）—— 闭合

### 2.1 (b) 列的四个 RED：执行者自测，我复现

brief 要求 (b) 列 G1–G4 的 RED 由执行者自己实测、只在 `/tmp` 副本上做、每条带空操作守卫。

我读了它的脚本 `/tmp/wp29-optionb-measure.py` 并原地重跑：

```text
ORIGINAL bytes = 2889
E1 2898 RED / E2 2894 RED / E3 2893 RED / E4 2951 RED
G1 2892 RED / G2 2941 RED / G3 2895 RED / G4 2889 RED
```

- **8/8 与文档粘贴的输出逐格一致**，包括 G4 字节数不变（2889）仍判 RED 这一格。
- 脚本对模板**只读**（`TMPL.read_text`），变异全在内存里，无任何写回。
  跑完 `git -C <被审树> status --porcelain` 为空。
- 每条带 `assert m != ORIG` 空操作守卫，我核了守卫在 `crit_b` 之前执行（B53 教训已落实）。
- 四条 E、四条 G 的变异函数我逐条对照了 `WP-28-plan-review-before-rev3.md` §4.1/§4.2 与
  `WP-28-brief-rev3.md:166-173` 的权威定义，八条**语义对得上**，且每个锚点在模板里
  `grep -cF` 均为 1（不存在「找不到锚点 ⇒ 恒等映射」的隐患，这是 WP-28 rev3 踩过的坑）。

### 2.2 B56（每格实测须写清测的是哪个判据）—— 落实

§4 开头有一张判据实况表，把三个判据形态分开：本树 WP-28 rev1（7 passed，无 `FROZEN_BODY`）、
主仓 plan 分支 WP-28 rev6（32 passed，有 `FROZEN_BODY`）、假设的 (b) 整份冻结。
每格「实测」都指名了脚本或 pytest 文件。我复现两侧：

- **WP-28 rev1 行**（文档称 8/8 全 GREEN，灵敏度 0 / 特异性 1）：重跑它的
  `/tmp/wp29-wp28rev1-measure.py`，baseline `7 passed`，E1–E4 / G1–G4 **八条全 GREEN**，
  收尾断言两份副本还原为原字节。**与文档一致**。
- **WP-28 rev6 行**：文档诚实标注「不在本树，**未实测**；按 brief 描述应 GREEN」。
  标注方式正确（不把别棵树的红绿当本树事实，正是 B55 的教训）。

### 2.3 裁定 (c′) 与 G1–G4 的兼容性 —— 我独立实测，成立

这是 C2 的核心，我不采信推断，自己测了 (c′) 的两条不变式
（`protected_body_identity` + `replica_identity`）：

第一次我在主仓 HEAD 的 `/tmp` 副本上跑 rev6 完整测试文件，得到 G1/G3/G4 **RED**。
追下去发现**红来自错误的层**：`test_invn_t7_replica_mismatch_red:886` 会自己再变异一次
模板并断言 `mutated != packaged`，`test_invn_harmless_placeholder_edit_green:896` 断言
原始占位符在场 —— 两者都假定盘上模板是未变异的，我预先变异后触发的是**它们自己的
夹具前置条件**，不是 (c′) 判据。（记忆 `mutation-red-may-come-from-wrong-layer`
实弹命中一次。）

改为直接从 rev6 的冻结常量 `FROZEN_BODY` 取判据、纯内存施加八条变异：

```text
baseline -> GREEN
E1 GREEN / E2 GREEN / E3 GREEN / E4 GREEN
G1 GREEN / G2 GREEN / G3 GREEN / G4 GREEN
（脚本不写任何文件；主仓 src/tests/templates 复核前后 git status 均无改动）
```

脚本留痕：`probes/WP-29-cprime-vs-g-probe.py`（纯内存，八条变异各带 no-op 守卫）。

结论：**(c′) 对 G1–G4 四条全部放行（特异性 1），对 E1–E4 四条全部放过（不承诺覆盖）**，
与交付物 §4 (c′) 列逐格一致。裁定**不把任何 G 判红**，满足 brief 的硬要求
（「把 G1–G4 判红却仍被推荐的方案是不合格的」）。

### 2.4 承诺量词闭合 —— 达标

§5 把覆盖面写成「两个受保护节字节跨度内发生字节改变」这一个**闭合输入维度**
（由冻结常量的精确字节序列界定），并明写这**不是** active-embedding 族的覆盖、
E1–E4 明确申报为不承诺、交 `git diff` + review。
这正是 `open-world-claims-cannot-be-enumerated` 与 `closed-model-or-bounded-claim`
两条要求的形态：要么覆盖整个输入维度，要么把说法降级为精确形状并申报未覆盖同族。

### 2.5 哨兵 —— 未采用，并申报为已作废

§5 有独立一段说明「文首/末哨兵」推荐已被编排者自己撤回（`WP-29-review-stage1.md` §7），
与 codex 绕过、编排者探针 `probes/WP-29-sentinel-bypass-probe.py` 实测一致，
**本裁定不采用哨兵**。符合 codex 的阶段 2 约束。

## 3. 保留项与措辞 —— 达标

- **§2 / §3 逐字节保留**：按段落抽出 rev1（`bd4ac7a`）与本轮的文本做字符串比较，
  `## 2. 渲染面实况` 847 字节、`## 3. 威胁是否真实` 1328 字节，两段
  **identical=True**。「实测 / 推断」标注纪律未被削弱。
  §2 的三条可核事实我另抽查：`git remote -v` 指向 GitLab ✓、无 `.github` 目录 ✓、
  无 `mkdocs.yml` / `docusaurus.config.js` / `_config.yml` / `conf.py` ✓。
- **措辞（标的 3 第 2 条）**：全文 `grep` 不再出现「(b) 覆盖 E1–E4 全部」「拦得住」式表述
  （仅 §6 与 DoD 对照表以「不再出现……」的否定形式引用该措辞，属正确引用）。
  §0 / §5 统一改为灵敏度 / 特异性二分。
- **§6 rev delta**：逐条对应 C1 / C2 / 措辞 / 基线四项，与 brief 标的一一对得上。

## 4. 基线与卫生 —— 全部复现

| 项 | 命令 | 结果 |
|---|---|---|
| 零回归基线（B48 修正后的 WP-29 lane 数） | 在被审树 `PYTHONPATH=src python3.11 -m pytest tests -q` | **`4 failed, 606 passed, 4 skipped`**，与 DoD 与文档 §7 **完全一致**。4 条失败全在 `tests/test_finalize_merge_triple_sign.py`，均为 `git checkout -q main` 的本机 `init.defaultBranch` 既有失败，非本轮引入 |
| 改动面 | `git diff --name-only bd4ac7a HEAD` | 只有 `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md` 一个文件 |
| 改动量 | `git diff --stat HEAD~1 HEAD` | 1 file changed, 308 insertions(+), 125 deletions(-) |
| 依赖 | `git diff --exit-code bd4ac7a HEAD -- pyproject.toml uv.lock` | 零 diff（`uv.lock` 在本树不存在） |
| 两份模板（B55：本树无冻结判据兜底，只能用 diff 证） | `git diff --exit-code bd4ac7a HEAD -- src/agentic_loop/templates/ docs/agentic/templates/` | **零 diff**，`TEMPLATES_UNCHANGED` 成立。文档 §7 已按要求贴出该命令而非拿「测试仍绿」当证据 |
| 工作树 | `git status --porcelain` | 干净 |
| 变异实验落点 | 读两个脚本的路径常量 | (b) 脚本纯内存；rev1 脚本只写 `/tmp/wp29-wp28rev1`；`/tmp/wp29-threat.ZFhIU9` 为 §3 的 scratch。仓内文件零写入 |

## 5. 次要项（不阻断，登记）

- **M1（证据完整性，轻微）**：两条主 grep 中 `WP-28-consult-codex-shape-verdict.json:6`
  那一行是 codex 长文原文（数千字），文档把它替换成
  `"……（此 JSON 行 raw_verbatim 为 codex 二签的长文原文，与消费面无关，全文略）……"`。
  省略被**显式声明**且内容确与消费面无关，因此不构成 C1 复发（C1 的问题是**未声明**地
  省略 `__pycache__` 命中）。但严格讲这不是「完整输出」。
  处置：阶段 2 brief 若再要求粘贴完整 grep，应允许「超长单行可截断但须标注」的显式豁免。
- **M2（宽口径补充块的归类标签不准）**：`grep -rn 'WORK_PACKAGE' .` 相对两条主 grep 的
  新增命中实为 17 行，文档的「宽口径补充命中」块只粘了 5 行，且块头写「均归 C 类」。
  未粘的 12 行中有 2 行其实是 **B 类**（`tests/test_init_contract.py:62`、
  `tests/test_wp_template_dispatch_lint.py:24` —— 这两处的路径由片段拼接，不匹配主 grep 的
  字面串），其余 10 行是 `docs/plans/**` 的历史治理文档（确属 C 类）。
  **实质结论不受影响**：那两行在 §1 的 B 类里被正确列出并被我核实。
  受影响的只是补充块的块头标签与粘贴完整度。
- **M3（可加强，非缺陷）**：§1 A 类只说 `load_template` 调用点是 `init_cmd.py:148` 与
  「`contract_render.py` 自身定义/测试」。更强的写法是点明 `contract_render.py:243`
  这个调用在 `render_template` 里、而 `render_template` 的目标集合 `CONTRACT_FILES`
  只含 AGENTS / CLAUDE / OPERATING_MODEL 三份，**不含 `WORK_PACKAGE.md.tmpl`** ——
  即唯一会对包内模板做占位符替换的路径也碰不到本 WP 的判定对象。
  这条只会加强结论，故不返工。

## 6. 结论

C1 与 C2 两个阻断项均已闭合，证据面可复现，(c′) 裁定与 must-stay-GREEN 集兼容
（我独立实测 4/4 GREEN），承诺量词闭合，B55 / B56 两条编排者缺陷在交付物里都按修正后的
口径落地。三条次要项不影响任何论断，不要求返工。

**第一签名 ACCEPT。** 下一步：派 codex 做第二签名；阶段 2 的冻结须待用户批准本裁定。
合入仍需用户批准，本文件不构成该批准。

---

## 7. 更正：本文件的 ACCEPT 已被撤回（2026-09-19，第二签名后）

**上文 §6 的第一签名 ACCEPT 作废，改判 REWORK。** 触发原因是 codex 第二签名
（`WP-29-consult-codex-stage1-rev3-verdict.md`）指出一条我漏掉的可直接验证的事实：

交付物 §1 声明的两条主 grep 只带 `--exclude-dir=.git,__pycache__,.pytest_cache`，
但交付物自身含搜索串 49 / 57 处。按**声明的命令原文**重跑得 88 / 104 行；
粘贴的 39 / 47 行只有在再加一个**未声明**的 `--exclude=WP-29-scope-decision.md`
之后才能得到。即「完整输出」再次带了未声明的过滤器 —— 正是 C1 的缺陷类别。

**我上一轮为什么查不出来**：§1 的 39/39 与 47/47 逐行比对里，我自己也加了
`--exclude=WP-29-scope-decision.md`（否则自命中淹没输出），于是比对必然一致。
我的核验方法复制了交付物的未声明过滤器。记为 **B57**：核验「完整输出」类声明，
必须先按声明的命令原文重跑一次再讨论差异，不得为可读性私自加过滤器。

连带改判：§5 的 **M1 与 M2 由非阻断升为阻断**。我原来的豁免理由是「实质结论不受
影响」，但本 WP 阶段 1 的交付标的**就是**可复现、完整的消费面证据本身，证据的可
复现性不能用结论不变来豁免。codex 的定性比我的严，且是对的。

§2（C2 / (c′) / 错误层归因）、§3、§4、M3 的结论不变，codex 同向确认。

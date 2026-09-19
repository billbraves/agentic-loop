# WP-29 (rev3) 阶段 1: 模板受保护块的「活动渲染」判据 —— 先定方言与消费链，再谈判据

> 冻结日期 2026-09-19 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> **本 WP 阶段 1 第 3 次冻结（rev3）= 第 2 次 re-freeze。** 模板「Re-freeze 规则」的停手条款
> 在第 3 次及以后 re-freeze（即 rev4）才触发，本次不触发，故无须用户批准即可冻结。
> **下一次 re-freeze 将触发停手复核，冻结前须经用户批准。**
> rev1 = `WP-29-brief-rev1.md`（与 `WP-29-brief.md` 逐字节同一，sha256
> `1dfd72aceb3649efc449a75f3a8e7893a27c0fa5480970f763265e0a6d29efd6`）。
> rev2 = `WP-29-brief-rev2.md`（sha256
> `027789c64cfeb838a02236c2b93612d6931d0b4e63faf0da9afc69d4e4aec6ea`）——
> **已冻结但从未派发**：编排者在写派发 prompt 时对着被审树独立核验，发现它自己的两处事实错误
> （见「标的 3」第 3、4 条），故在任何执行者读到它之前就地作废并改出本 rev3。
> **rev2 不是判据**，两者冲突处一律以 rev3 为准。

## 本 rev 的由来（双签名结果）

rev1 的交付物 `WP-29-scope-decision.md`（commit `bd4ac7a`）经两签名后判 **CHANGES_REQUESTED**：

- 编排者复核 `WP-29-review-stage1.md`：§1/§2/§3 成立，**§5 裁定 (b) 不采纳**（§3 给出四条反证）。
- codex 第二签名 `WP-29-consult-codex-stage1-verdict.md`：**REWORK**，两条阻断项 C1/C2。
- 编排者独立复核 codex 的三条论断，全部成立，见 `WP-29.status.json`
  `evidence.orchestrator_cross_check_of_consult`。

**rev1 已 ACCEPT 且不得重做的部分**（本 rev 零改动，直接保留）：

- §2 渲染面：「本仓无权威 Markdown 方言」的结论与「实测 / 推断」标注纪律 —— codex 明文认可。
- §3 威胁真实性：scratch 变异 + targeted pytest 已证威胁真实、零代码改动 —— codex 明文认可。
- §1 的代码路径核验（`init_cmd.py:109` / `:138` / `:253-254` 与
  `contract_render.load_template` 不解析 markdown）—— 编排者独立复现成立。
- 606-vs-619 基线差异的解释 —— codex 明文「不构成本次 REWORK」。

**本 rev 只有三件事**：补完消费面证据（标的 1）、把必须保持 GREEN 的约束写进方案表并改裁定
（标的 2）、修编排者自己的四处缺陷（标的 3：措辞 + B48 基线数 + B55 判据实况 + B56 判据归属）。

## 目标（一句话）

把阶段 1 的裁定建立在**完整的消费面证据**和**必须保持 GREEN 的合法编辑约束**之上 ——
即：证据面从「几个手挑目录」升级为「仓库级且噪声显式排除」，方案判别力从「能拦住哪些攻击」
升级为「能拦住哪些攻击 **且** 放过哪些必须放过的编辑」。

## 本 rev 的验收标的（三项，各自封闭）

### 标的 1 —— C1：消费面证据必须是仓库级、可复现、分类的（阻断项）

rev1 §1 的搜索范围只有 `src/`、`tests/`、`AGENTS.md`、一个 Quickstart，并且把
`__pycache__` 命中写成括注「另匹配 4 处」而非排除后重跑。两个后果：

1. **未覆盖的目录**：仓根其余文件（`CHANGELOG.md`、`README.md`、`MIGRATION.md`、
   `install.sh`）、`docs/` 下非 plans 部分、`examples/`、`.githooks/`、`pyproject.toml`
   的打包配置，都未出现在证据面里。
2. **结论字面不成立**：rev1 自己的输出已经显示 `tests/test_init_contract.py` 与
   `tests/test_wp_template_dispatch_lint.py` 会读模板，所以
   **「唯一的仓内机器消费者是 `init_cmd.py`」这句话被它自己的输出证伪**。

**要求**：在 `WP-29-scope-decision.md` §1 给出一次**仓库级**搜索，显式排除噪声目录，
并把命中**按消费性质分四类**。

- 搜索须覆盖仓根（`.`），显式带 `--exclude-dir`（至少 `.git`、`__pycache__`、
  `.pytest_cache`），并附**命令原文与完整输出**；输出很长时可按分类分块粘贴，
  但**每一类都必须是原始命中行**，不得写成摘要计数。
- 分类（四类，缺一不可，某类为空须明写「零命中」）：
  - **A. 运行时复制**：程序执行期读取模板内容的代码路径。
  - **B. 测试验证**：测试用例读取模板以断言其内容/结构。
  - **C. 人 / agent 阅读**：文档或治理契约指示人或 agent 去读模板。
  - **D. 打包读取**：打包配置把模板作为 package data 纳入 wheel/sdist，
    以及运行时经 `importlib.resources` 读取该 package data 的路径。
    **rev1 完全未排除这一项，必须在本 rev 给出结论。**
- 结论中「唯一」二字必须带限定词。参照措辞（可改进，但量词必须同等收紧）：
  > 唯一的**非测试运行时**消费者是 `src/agentic_loop/init_cmd.py:109`，行为是逐字节复制。
  不得再出现无限定的「唯一的仓内机器消费者」。
- D 类须回答一个具体问题：`pyproject.toml` 把
  `src/agentic_loop/templates/*.tmpl` 纳入 artifacts 后，读取它的运行时路径
  （`contract_render.load_template` → `importlib.resources`）是否解析 markdown？
  给出行号级证据。

### 标的 2 —— C2：方案表必须含「必须保持 GREEN」的合法编辑，裁定须与之兼容（阻断项）

rev1 §4 的表格只有四列攻击（E1–E4），四条 (b) 全填「拦得住」，据此在 §5 裁定 (b)。
这个表只测了**灵敏度**，没测**特异性**。WP-28 rev3 brief §D 明文要求四条无害探针
**必须仍 GREEN**（`WP-28-brief-rev3.md:166-173`）：

1. 改无关占位符 `<这个 WP 要交付什么>`
2. 文末追加无关新章节
3. 改无关章节 `## 范围` 的正文
4. 改抬头 `> 冻结日期 <YYYY-MM-DD>` 行

**整份逐字节冻结把这四条全部判红。** 编排者已实测，见 `WP-29-review-stage1.md` §3 的表。
因此 (b) 的判别力是 1、特异性是 0：它拦的是「文件被改」，不是「E1–E4 这四种攻击」。

**要求**：

- §4 的表**加四行**（G1–G4，即上述四条无害编辑），每个方案列填 GREEN / RED，
  并标注该值是**实测**还是**推断**。(b) 列的四个 RED 须由本 WP 自己实测复现
  （构造合法编辑 → 跑冻结判据原型或等价的字节比较 → 记录结果），
  不得只引用编排者复核文档的结论。

- **每一格「实测」都必须写清：你测的是哪个判据？**（rev2 漏掉了这条，属编排者缺陷，见标的 3 第 4 条）
  本仓同一份测试文件在三个位置有三个不同版本，测出来的红绿含义完全不同：

  | 判据 | 在哪 | 形态 | 对 G1–G4 的表现 |
  |---|---|---|---|
  | **WP-28 rev1** | 你的树 `2e5f2c0`（6 用例 / 7 passed，无 `FROZEN_BODY`） | 只查段落在场与两份副本一致 | 4 条**全 GREEN**（编排者用你树里的真实 `dispatch_lint.sh` 实测，4/4 `DISPATCH_LINT_PASS`；判据不看 body 内容） |
  | **WP-28 rev6** | 主仓 plan 分支 `cc22212`（32 passed，有 `FROZEN_BODY`） | 两个受保护节的 body 逐字节冻结 | 4 条**全 GREEN**（WP-28 brief §D 要求，rev6 已 ACCEPT） |
  | **(b) 整份模板逐字节冻结** | **不存在，是本 WP 要评估的假设方案** | 全文 76 行逐字节比较 | 4 条**全 RED**（编排者实测，4/4 bytes differ；这是标的 2 的核心） |

  编排者的这次实测同时跑了 baseline（未变异）作对照：baseline 在两个判据下都 GREEN，
  四条变异各自带 `mutated != original` 守卫（守卫触发即中止，不出表），
  变异只施加在 `tempfile.TemporaryDirectory()` 下的副本上，跑完
  `git -C <被审树> status --porcelain` 为空、模板字节未变。
  **这份实测不替代你自己的测量**（标的 2 明写 (b) 列须由你复现），
  它的用途是让本 brief 的判据分类可核验。

  所以 (b) 列 G1–G4 的四个 RED，你测的是**你自己写的一个 `/tmp` 字节比较脚本**
  （对照冻结全文 vs 施加 G1–G4 后的副本），**不是**跑 `pytest`。
  跑 `pytest tests/test_wp_template_dispatch_lint.py` 只能告诉你 WP-28 rev1 判据的表现，
  **那不是 (b)**。把两者混同会得到「G1–G4 在 (b) 下是绿的」这种反向错误结论。

- **同理，(a)/(c)/你自己命名的方案，凡填「实测」的格子都须给出判据的具体形态**
  （是哪段代码 / 哪个脚本 / 哪个 pytest 文件的哪个版本）。判据不明的格子只能标「推断」。
- §0 与 §5 里「(b) 覆盖 E1–E4 全部」的措辞须改为区分灵敏度与特异性的表述。
- **裁定必须与 G1–G4 兼容**：任何把 G1–G4 判红的方案不得作为推荐裁定。
- 可选裁定不限于 (a)/(b)/(c)。若推荐一个新组合，须给它命名并写清其判据形状，
  例如编排者复核 §4 提出的 (c′)：不引 parser、不整份冻结、承诺边界明文化 +
  可选的受保护 envelope 冻结。**但 (c′) 不是被指定的答案**，它只是一个已知可行方向；
  执行者可提出别的，判据是「与 G1–G4 兼容且对 E1–E4 的覆盖面诚实申报」。
- **承诺量词必须闭合**（这是本 WP 最容易再犯的错，已犯两次）：
  裁定里任何「拦住 X 族」的说法，都必须能指出该族的**输入维度**以及判据覆盖该维度的方式；
  做不到就把说法降级为「拦住这一个精确形状」，并明写未覆盖的同族形状。

**编排者已作废的一条推荐（不得再作为依据）**：`WP-29-review-stage1.md` §4.3 第二条
「文首/文末哨兵，专拦 E1/E2 这一族，性价比最高」**已由编排者自己撤回**，见该文档 §7。
codex 给出的绕过与编排者探针（`probes/WP-29-sentinel-bypass-probe.py`）实测一致：

```markdown
<!-- START_SENTINEL -->
<!--
# 后续全部受保护内容
-->
<!-- END_SENTINEL -->
```

| 变异形状 | 哨兵判据实测 |
|---|---|
| 首尾两行字节不变，中间全部包进 `<!-- -->` | **GREEN（逃逸）** |
| 首行后插入未闭合 `<!--`，末行字节不变 | **GREEN（逃逸）** |
| 整档外包前后缀（首尾行被顶走） | RED |
| baseline（未变异） | GREEN |

哨兵只约束「首行/末行仍是特定形态」，拦住的是「在 sentinel **外侧**追加前后缀」这一个精确
形状，不是 E1/E2 这一族。**若你在裁定里采用哨兵，必须按上表申报其真实覆盖面。**

### 标的 3 —— 编排者自己的四处缺陷（非执行者过失，本 rev 一并修正）

1. **B48 基线数抄错 lane。** rev1 DoD 写的零回归基线
   `4 failed / 619 passed / 4 skipped` 是 **WP-28 lane** 在 `b34deb9` 的数字。
   WP-29 自己的 lane 实测是 **`4 failed / 606 passed / 4 skipped`**
   （编排者在 `feature/wp29-render-scope-decision` 的 `bd4ac7a` 上实测，耗时 102s；
   4 条失败全在 `tests/test_finalize_merge_triple_sign.py`，是本机
   `git init.defaultBranch=master` 与 fixture 冲突的既有失败，不是你引入的，不要修）。
   本 rev 的 DoD 用 606。执行者 rev1 主动报出这处差异并交回编排者裁定，处置正确。
2. **rev1 §4 的表格设计缺陷。** 它只要求「能拦住哪条逃逸、拦不住哪条」，没有要求
   must-stay-GREEN 一侧 —— 这是标的 2 的根因，属编排者冻结时的口径缺陷，不是执行者漏答。
3. **rev2 写错了你树里的判据实况（B55）。** rev2 三处（forbidden_paths、DoD、附注）都写着
   「WP-28 rev6 已合入，两份模板受逐字节冻结判据保护，改了就转红」。编排者在写派发 prompt 时
   对着被审树核验，发现这句话对你的树是假的：

       git merge-base --is-ancestor b940248 2e5f2c0   # -> 假（base 不含 WP-28 合入）
       grep -c 'FROZEN_BODY' tests/test_wp_template_dispatch_lint.py   # -> 0（你树）
       PYTHONPATH=src python3.11 -m pytest tests/test_wp_template_dispatch_lint.py -q   # -> 7 passed（你树）
       # 主仓 plan 分支 cc22212 同文件 -> 32 passed，且模板含 ## Re-freeze 规则 一节

   把「有判据兜底」当成事实，会让执行者以为「测试绿 ⇒ 没碰模板」，
   而你树里碰了模板测试照样全绿。rev3 已在三处改正并说明真实的保护手段是
   allowed_paths + `git diff --exit-code`。
4. **rev2 没说清 G1–G4 的「实测」该对着哪个判据（B56）。** 本仓同一份测试文件在你树、
   主仓 plan 分支、以及「假设的 (b)」三处形态不同，红绿含义完全不同；rev2 只写了
   「跑冻结判据原型或等价的字节比较」，没有禁止把 `pytest` 的结果当成 (b) 的结果。
   rev3 已在标的 2 加入判据对照表与「凡填实测必须写清测的是哪个判据」的要求。

## 范围

**本 WP 分两阶段；本次冻结仍只含阶段 1，交付物是一份裁定文档，不是代码。**

### 阶段 1（本次冻结的全部内容）

allowed_paths：

- `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md`
  （rev1 已存在，本轮**原地修订**该文件；本阶段唯一产出）

阶段 1 仍须回答五项并逐项给出证据（五项不变，第 1 项与第 4/5 项按标的 1/2 加严）：

1. **消费链实况** —— 按**标的 1** 的仓库级 + 四分类要求作答。
2. **渲染面实况** —— rev1 已 ACCEPT，**保留原文，不必重做**（如需微调措辞可改，
   但「实测 / 推断」标注纪律不得削弱）。
3. **威胁是否真实** —— rev1 已 ACCEPT，**保留原文，不必重做**。
4. **方案对比** —— 按**标的 2** 加 G1–G4 四行，(b) 列的 RED 须自行实测。
5. **裁定** —— 按**标的 2** 改为与 G1–G4 兼容的方案，承诺量词闭合。

### 阶段 2（**本次仍不冻结**）

阶段 2 的范围由阶段 1 裁定决定，须**另行冻结并经用户批准**。
在阶段 1 裁定获批准前，**不得**开始阶段 2 的任何实现。

**forbidden_paths（阶段 1）**：

- 一切代码与测试文件。**阶段 1 不写任何判据、不引任何依赖。**
- `src/` 下全部文件、`tests/` 下全部文件、`pyproject.toml`、`uv.lock`
- `src/agentic_loop/templates/`、`docs/agentic/templates/` —— **不要碰模板**。
  **注意判据实况（编排者已实测，见「标的 3」第 3 条）**：WP-28 rev6 已在主仓 plan 分支合入
  （commit `b940248`），但**你的被审树 base `2e5f2c0` 不含该合入** ——
  `git merge-base --is-ancestor b940248 2e5f2c0` 为假。你树里的判据是 **WP-28 rev1**
  （`tests/test_wp_template_dispatch_lint.py` 6 个用例 / 7 passed，`grep -c 'FROZEN_BODY'` = 0，
  模板无 `## Re-freeze 规则` 节，76 行）。
  所以**你树里并没有逐字节冻结判据**，碰了模板不会「转红」——
  但仍然禁止碰：allowed_paths 只有一个文档，且主仓 plan 分支上那两份模板确实受冻结判据保护，
  任何残留改动在集成时必然撞红。
- `docs/plans/` 下除 `WP-29-scope-decision.md` 外的全部文件
  （包括本 brief、`WP-29.status.json`、`WP-29-review-stage1.md`、
  `WP-29-consult-codex-stage1-verdict.md`、`WP-28-*`）
- `.agentic/`、`.env`、`.context/`
- owner 边界对齐 CODEOWNERS。

**关于标的 2 要求的实测**：构造 G1–G4 与 E1–E4 的变异只能在 `/tmp` 下的**副本**上做，
不得原地改写仓内任何文件。这是 WP-28 B54 的教训（载具不得写入被判据保护的制品本身），
已成规范条目。跑完须 `git status` 干净并在文档里贴出该输出。

## 输入

- `WP-29-review-stage1.md` —— 编排者独立复核（§3 的四条 must-stay-GREEN 反证、
  §4 的 (c′) 方向、§7 对哨兵推荐的撤回）
- `WP-29-consult-codex-stage1-verdict.md` —— codex 第二签名 REWORK 的逐字原文（C1/C2/阶段 2 约束）
- `WP-29.status.json` 的 `consult` 与 `evidence.orchestrator_cross_check_of_consult`
- `WP-28-brief-rev3.md` §D（`:166-173`）—— 四条无害探针的权威定义
- `WP-28-plan-review-before-rev3.md` §4.1 / §4.2 —— 四条实测逃逸 E1–E4 的证据
- `WP-28-consult-codex-shape.md` §2 / §4 —— `active_embedding` 为何必然依赖块外上下文
- `probes/WP-29-sentinel-bypass-probe.py` —— 哨兵绕过的编排者探针
- 被审树：`/Users/admin/vibe/wp29-render-scope-decision`（branch
  `feature/wp29-render-scope-decision`，当前 HEAD `bd4ac7a`）

## 交付物清单

- [ ] `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md` 修订版 ——
      §1 按标的 1 重做、§4/§5 按标的 2 重做、§2/§3 保留、§0 摘要同步改
- [ ] 文档内含一节「rev1 → 本轮改了什么」，逐条对应 C1 / C2 / 措辞 / 基线

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收要求同义，非另一份口径。

阶段 1 的产出是文档，其「测试」是**证据可核验性**。编排者验收时会逐条复现，
所以每一项论断都必须附可执行的复现命令或精确文件行号引用：

1. **消费链论断（标的 1）**须附一次**仓库级** `grep -rn` 的命令原文与完整输出，
   命令须含显式 `--exclude-dir`（至少 `.git`、`__pycache__`、`.pytest_cache`），
   命中按 A 运行时复制 / B 测试验证 / C 人-agent 阅读 / D 打包读取**四类**归入；
   某类零命中须明写「零命中」。结论中的「唯一」必须带限定词。
   D 类须含 `pyproject.toml` 的 artifacts 行与 `contract_render.load_template` 的行号级证据。
2. **渲染面论断**须区分「实测」与「推断」（rev1 已达标，保留即可）。
3. **威胁真实性论断**须附一次实际构造与 pytest 实测输出（rev1 已达标，保留即可）。
   若你重跑，仍须 `git checkout` 还原并贴出干净的 `git status`。
4. **方案对比（标的 2）**的表须同时含两侧：
   - 攻击侧 E1–E4（对照 `WP-28-plan-review-before-rev3.md` §4.1 三条 + §4.2 一条）
   - **合法编辑侧 G1–G4**（对照 `WP-28-brief-rev3.md:166-173` 的四条无害探针）
   每格填 RED / GREEN 并标注实测或推断；**(b) 列 G1–G4 的四个 RED 必须是你自己实测的**，
   附构造方式、命令与输出。变异只能施加在 `/tmp` 副本上。
5. **裁定（标的 2）**须是一个与 G1–G4 兼容的具体方案（可以是 (a)/(b)/(c) 之一、
   明确组合，或你自己命名的新方案），不得写成「视情况而定」；
   且裁定里每一条「拦住 X」的说法都须标明是「一个精确形状」还是「一个覆盖了某输入维度的族」，
   后者须指出该维度。
6. **变异自检（承自 WP-28 规范条目）**：你构造的每个变异（E1–E4、G1–G4）都须带
   `assert 变异后 != 变异前` 或等价的 `cmp -s` 守卫并在文档里说明。
   **空操作变异会打印出和真实逃逸一模一样的绿**，编排者在 WP-25/WP-26/WP-28 三次踩过这个坑。
   若某条你构造不出，须写明为什么不可构造，不得默认略过。

**(c) 或 (c′) 或任何「机械不可兑现，承诺须降级」的结论仍是合格交付，不是失败。**
本 WP 存在的意义之一就是允许这个答案。反过来，**一个把 G1–G4 判红却仍被推荐的方案是不合格的**，
无论它对 E1–E4 多灵敏。

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径。
阶段 1 只能修改 `docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md` 一个文件；
绝不能碰 `src/` 与 `tests/` 下任何文件、`pyproject.toml`、`uv.lock`、
`src/agentic_loop/templates/`、`docs/agentic/templates/`、`docs/plans/` 下其余文件
（含本 brief 与 `WP-29.status.json`）、`.agentic/`、`.env`、`.context/`；
不得引入任何第三方依赖；变异实验只能在 `/tmp` 副本上做，不得原地改写仓内文件；
owner 边界对齐 CODEOWNERS，不跨 owner 写入。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径。

标的 1（C1 消费面）：

- [ ] §1 含一次仓库级 `grep -rn`，命令原文含显式 `--exclude-dir`，附完整命中输出
- [ ] 命中按 A 运行时复制 / B 测试验证 / C 人-agent 阅读 / D 打包读取四类归入，零命中类明写
- [ ] D 类给出 `pyproject.toml` artifacts 行 + `contract_render.load_template` 行号级结论
- [ ] 结论中「唯一」带限定词（如「唯一的非测试运行时消费者」），不再出现无限定版本

标的 2（C2 特异性与裁定）：

- [ ] §4 表格含攻击侧 E1–E4 与合法编辑侧 G1–G4 两组行，每格 RED/GREEN 且标注实测或推断
- [ ] (b) 列 G1–G4 的四个 RED 由执行者自己实测，附构造方式与输出
- [ ] 每个变异带 `assert 变异后 != 变异前` 或 `cmp -s` 守卫，并在文档中说明
- [ ] §0 与 §5 不再出现「(b) 覆盖 E1–E4 全部」式表述，改为区分灵敏度与特异性
- [ ] §5 裁定与 G1–G4 兼容（不把任何一条判红），承诺量词闭合（族须指出输入维度，
      否则降级为「精确形状」并申报未覆盖同族形状）
- [ ] 不把已撤回的「文首/文末哨兵拦住 E1/E2 族」当作依据；若采用哨兵须按本 brief 的表申报覆盖面

保留项（rev1 已 ACCEPT，不得削弱）：

- [ ] §2 渲染面结论与「实测 / 推断」标注保留
- [ ] §3 威胁真实性的构造与 pytest 输出保留（若重跑，`git status` 须干净并贴出）

通用：

- [ ] 文档含「rev1 → 本轮改了什么」一节，逐条对应 C1 / C2 / 措辞 / 基线
- [ ] **零代码改动**：`git diff --stat` 只含 `WP-29-scope-decision.md` 一个文件
- [ ] 未引入任何依赖（`pyproject.toml` / `uv.lock` 零 diff）
- [ ] 未碰两份模板（禁止改动；注意你树里的判据是 WP-28 rev1，**不含**逐字节冻结，
      所以别把「测试仍绿」当成没碰过的证明，要用 `git diff --exit-code` 证明）
- [ ] 相对基线零回归（本阶段不改代码，跑一次全量确认与基线一致：
      **`4 failed / 606 passed / 4 skipped`**，4 条全在
      `tests/test_finalize_merge_triple_sign.py`，是既有环境失败，不要修）
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

1. **不要在阶段 1 写判据。** 本轮加严的是证据面与裁定的约束，不是让你开始实现。
   G1–G4 的实测可以用最小的字节比较脚本（`/tmp` 下），那是**测量**，不是判据落地。
2. **不要碰两份模板。** 但不要误信「改了就转红」：主仓 plan 分支上 WP-28 rev6 已合入
   （逐字节冻结判据在那里），**你的树 base `2e5f2c0` 不含该合入**，判据是 WP-28 rev1，
   碰了模板测试照样全绿。因此对模板的保护在本轮**只靠 allowed_paths 与 `git diff --exit-code`**，
   没有判据兜底 —— 这正是必须贴出 `TEMPLATES_UNCHANGED` 的原因。
3. **不要引依赖。** 引 parser 是阶段 2 的事，且须先经裁定与用户批准。
4. **(c) / (c′) / 「须降级承诺」都是合法答案。** 见 §Acceptance tests 末段。
5. **不要用 `agentic <sub>` 自证**（B14：那是别棵树的冻结副本）。
   用 `PYTHONPATH=src python3.11 -m pytest`。
6. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。
7. **既有 4 条失败不是你引入的**（本机 `git init.defaultBranch=master` 与 fixture 冲突）。不要修。
8. **空操作变异是最危险的假绿**（B53 / 编排者三次踩坑）。每个变异都要守卫。
9. **不要把编排者复核文档的结论当成实测。** 标的 2 明确要求 (b) 列 G1–G4 由你自己复现；
   引用编排者的表只能作为交叉验证，不能替代你的测量。

### 口径权威源引用

- 四条无害探针（must-stay-GREEN）的权威定义：`WP-28-brief-rev3.md:166-173`
- 四条实测逃逸 E1–E4 的证据：`WP-28-plan-review-before-rev3.md` §4.1 / §4.2
- codex 第二签名原文：`WP-29-consult-codex-stage1-verdict.md`
- 编排者复核与哨兵推荐的撤回：`WP-29-review-stage1.md` §3 / §4 / §7
- 哨兵绕过探针：`docs/plans/2026-09-13-parallel-throughput/probes/WP-29-sentinel-bypass-probe.py`
- 模板的非测试运行时消费者：`src/agentic_loop/init_cmd.py:109`（`_REFERENCE_TEMPLATES`）
- 变异载具不得写受保护制品：WP-28 B54 的模板规范条目（`WORK_PACKAGE.md` oracle 第 4 项）

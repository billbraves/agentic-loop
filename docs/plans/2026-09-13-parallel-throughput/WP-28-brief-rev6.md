# WP-28 (rev6): 变异载具不得写入被判据保护的制品本身

> 冻结日期 2026-09-18 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 用户已批准第 6 次冻结的**方向 2**（停手复核见 `WP-28-plan-review-before-rev6.md`）。
>
> **rev5 的大部分已 ACCEPT 且承重，不得重做**：`_read_text_preserving_newlines()`
> 的 B49 修法、M-T0 / M-T0b 的落盘字节变异思路、oracle 第 4 项已扩写的三句、
> T1–T7 全部用例、四条兜底、四条 harmless-green —— 全部保留原样。
> 本 rev 只有两件事：**换掉 M-T0 / M-T0b 的变异载具**，**给 oracle 第 4 项再补一句口径**。

## 目标（一句话）

把 M-T0 / M-T0b 的变异从「原地改写真实模板文件、再 `try/finally` 恢复」改为
「变异临时副本、真实模板全程不被写入」，从而使 B54 的整个失败类不再存在；
并把这条教训（等价载体优先）写进本 WP 交付的模板条目。

## 本 rev 的验收标的（两项，各自封闭）

### 标的 1 —— B54：载具不再写真实模板（阻断项）

`_mutate_on_disk()`（判据第 538 行起）的还原保证只覆盖 `yield` **之后**的失败：

```python
originals = {p: p.read_bytes() for p in paths}
mutated = {p: mutate_bytes(data) for p, data in originals.items()}
for p, data in mutated.items():
    assert data != originals[p], ...      # ← 第二份在此失败时，第一份已落盘
    p.write_bytes(data)                    # ← 写入在 try 之外
try:
    yield
finally:
    for p, data in originals.items():
        p.write_bytes(data)
        assert p.read_bytes() == data, ... # ← 第一份 assert 失败即中止循环，第二份不获恢复
```

**根因在计划侧，不在你。** rev5 brief §标的 1 第 3 条把载具钉成「写入模板文件的字节」
并要求 `try / finally` 恢复 —— 我把「变异须落到判据真实的输入面」翻译成了
「写那两个真实路径」。**输入面是「一个文件的字节」，不是那两个特定路径。**
连续两轮（rev5 的 B49 承重性、rev6 的 B54）根因都在我的措辞。

可达性不是理论的：`_crlf_rewrap_bytes()` 对**已是 CRLF** 的文件是恒等函数，
所以一旦某份模板以 CRLF 签出，第一份写入成功后第二份的 no-op guard 立刻失败，
留下一份**在判据存在意义所指的那一个字节维度上**被污染的受保护制品。

编排者已实测（`probe-optionB.py`，直接 import 交付的判据模块，只动临时副本）：

```
M-T0   fix 在场 → ['SECTION_MISSING']                    REPLICA_MISMATCH 不在场 ✓
M-T0   fix 撤销 → []                                      转红 ✓（仍杀得掉自己的 fix）
M-T0b  fix 在场 → ['REPLICA_MISMATCH','SECTION_MISSING']  两码皆在 ✓
M-T0b  fix 撤销 → []                                      转红 ✓
真实模板 sha256 前后一致：True
```

**要求**：

1. **M-T0 / M-T0b 改为变异临时副本**。把两份模板 `shutil.copyfile()` 到
   `tmp_path`（pytest fixture）或 `tempfile.mkdtemp()`，只对副本 `write_bytes()`
   变异后的字节，然后让判据**读副本**。

2. **判据本体零改动**。`_read_text_preserving_newlines(path)` 接受任意路径、
   `_check_both(packaged_text, docs_text)` 接受任意文本 —— 编排者已核实两者
   与路径无关，副本形态无需改动判据。改判据本体属超范围。

3. **删除 `_mutate_on_disk()`**（或改写为不写真实模板的副本载具）。
   交付后仓库内**不得存在任何对 `TEMPLATE_PACKAGED` / `TEMPLATE_DOCS`
   的 `write_bytes()` / `write_text()` / `open(..., "w")`**。

4. **保留 rev5 已 ACCEPT 的全部要素**：
   - `_crlf_rewrap_bytes()` 的先归一再改（`\r\n` → `\n` → `\r\n`）**保留**。
   - **no-op guard 用字节比对**（`assert mutated_bytes != original_bytes`）**保留**，
     只是现在断在副本上。
   - **断言具体 witness code** 保留：M-T0 断 `SECTION_MISSING in codes` 且
     `REPLICA_MISMATCH not in codes`；M-T0b 断两者皆在场。
   - 两条用例**仍不经 `_mutate_both()`**；`_mutate_both()` 与 T1–T7 其余用例零改动。

5. **新增一条「真实模板未被写入」的断言**。两条用例各自在结束时断言两份真实模板的
   sha256（或 `read_bytes()`）与用例开始前一致。这条断言是本 rev 的核心证据：
   它把「载具不碰受保护制品」变成机械可判，而不是靠代码走查。
   起点值须在用例内自行采集，不得硬编码 sha256 字面量。

6. **报告必须给出承重性实测**：把 `_read_text_preserving_newlines()` 临时还原为
   `path.read_text(encoding="utf-8")`，运行 `pytest -k t0`，**贴出转红的实际输出**，
   然后恢复并确认 `git diff` 对该文件无残留。这条与 rev5 相同、依然必须做 ——
   换载具不得以牺牲承重性为代价。

### 标的 2 —— 把 B54 的教训写进模板条目（阻断项）

rev5 已把 oracle 第 4 项扩写为「变异必须施加于判据真实的输入面（文件字节 /
进程边界 / 外部状态）」。B54 说明这句还差一层：**它没说清「真实输入面」是否要求
写生产制品本身**。我读成了「要」，才把方案钉在原地改真文件上。

**要求**：在**两份模板**（`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
`docs/agentic/templates/WORK_PACKAGE.md`）的 `## Acceptance tests` 段，
在第 4 项**末尾追加以下两行**（逐字节确定，不得改写、不得增删标点，缩进为 3 个空格）：

```
   同类输入面的等价载体（如临时副本）满足本项；若变异会写到被判据保护的制品
   本身，须优先选用不写该制品的等价载体。
```

追加位置：紧跟在现有的
`   判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。`
这一行之后，在第 4 项与其后空行之间。第 4 项因此共 6 行。

**这是本 WP 唯一允许的冻结常量编辑。** 同步要求：

- 两份模板的这段改动必须**逐字节一致**（否则 `REPLICA_MISMATCH` 会红）。
- `FROZEN_BODY_ACCEPTANCE`（判据第 288 行起）必须同步追加对应的两个字符串字面量，
  否则 `BODY_MISMATCH` 会红。编排者已在一次性副本树实测：
  **同步 → 32 passed；只改模板不改常量 → 7 failed**（含三条 harmless-green），
  所以这条同步是承重的，不是形式要求。
- `test_invn_positive_control_clean_template` 必须仍绿（这是同步是否成功的判据）。
- 段内其余文本（第 1/2/3 项、第 4 项原有四行、开头两句、结尾「注意」两行）
  **逐字节不动**；`## Re-freeze 规则` 段及其 `FROZEN_BODY_RE_FREEZE` **完全不动**。

编辑后两份模板的 sha256 应为
`bf2cb2858e37c53202259c830be601c074f0e920d8e1d3ea91b59fdb701595e5`
（编排者在副本树实测；此值仅供你自检对齐，不得写进任何用例）。

## 范围

允许改动的文件仅三个（与 rev5 相同）：

- `tests/test_wp_template_dispatch_lint.py` —— 仅 M-T0 / M-T0b 两条用例、
  载具函数、必要的 `import`（`shutil` / `tempfile` / `hashlib` 视实现而定）+
  `FROZEN_BODY_ACCEPTANCE` 常量同步。
- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 仅 oracle 第 4 项末尾两行。
- `docs/agentic/templates/WORK_PACKAGE.md` —— 同上，与上一份逐字节一致。

## 输入

- 本 brief（冻结版）。
- `WP-28-plan-review-before-rev6.md` —— 第 6 次冻结裁定、根因归属、两个方案的实测对照。
- `WP-28-consult-codex-rev5-verdict.json` —— codex 第二签名原文（B54 的 R1）。
- `WP-28-review-rev5.md` —— 编排者复核（含撤回 ACCEPT 的理由）。
- rev5 交付 commit `2923255`（你的起点，base `5d94387`）。

## 交付物清单

1. `tests/test_wp_template_dispatch_lint.py`：M-T0 / M-T0b 改为变异临时副本；
   删除（或改写）`_mutate_on_disk()`；新增「真实模板未被写入」断言；
   `FROZEN_BODY_ACCEPTANCE` 同步追加两行。
2. 两份模板的 oracle 第 4 项末尾追加两行（逐字节一致）。
3. 执行报告（`AGENTS.md` §6.C 格式），含标的 1 第 6 条的**撤销 fix 转红实测输出**、
   零回归算术、以及「载具改为副本后判据本体为何无需改动」的说明。

## Acceptance tests

沿用 rev5 的全部用例，**一条不删**。本段只规定本 rev 改造的判据。

**M-T0（改造）**：两份模板**副本的文件字节**同步 `\n` → `\r\n`，不改任何字符、
不动冻结常量 → 判据读副本必须红，`SECTION_MISSING` 在场，`REPLICA_MISMATCH` **不在场**；
且**两份真实模板字节前后一致**。

**M-T0b（改造）**：只改**一侧副本**的文件字节行尾 → 必须红，
`REPLICA_MISMATCH` 与 `SECTION_MISSING` 皆在场；且**两份真实模板字节前后一致**。

**载具净洁性**：仓库内不存在对 `TEMPLATE_PACKAGED` / `TEMPLATE_DOCS` 的任何写入调用。

**承重性证明（报告项，非用例）**：`_read_text_preserving_newlines()` 临时还原为
`path.read_text(encoding="utf-8")` → M-T0 / M-T0b 必须转红，贴出实测输出。

**同步证明**：`test_invn_positive_control_clean_template` 仍绿，证明模板与
`FROZEN_BODY_ACCEPTANCE` 逐字节一致。

**不得回归**：rev5 的 32 条全绿用例（含四条兜底 `not (codes & DIAGNOSTIC_CODES)`、
四条 harmless-green、T1–T7 全部变异）保持绿。三条已声明为边界的逃逸
（整档注释外包 / 文档开头未闭合 `<!--` / `## 附注` 内未闭合围栏）**仍 GREEN**。

## Allowed and forbidden paths

**allowed_paths**（仅此三项）：

- `tests/test_wp_template_dispatch_lint.py`
- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`
- `docs/agentic/templates/WORK_PACKAGE.md`

**forbidden_paths**（其余全部，重点列举）：

- `src/agentic_loop/contract_render.py`、`src/agentic_loop/init_cmd.py`、`pyproject.toml`
  —— 必须零 diff，`CONTRACT_TEMPLATE_VERSION` 仍为 `"6"`。
- `docs/plans/**` —— 含本 brief 与任何 status JSON。**禁跨 worktree 写主区。**
- 其余 `src/**`、`tests/**`（除上列判据文件）、`.agentic/**`、`AGENTS.md`、`CLAUDE.md`。

## Completion definition

- [ ] **M-T0 变异副本**：两份副本同步改行尾；判据读副本；红且 `SECTION_MISSING` 在场、
      `REPLICA_MISMATCH` 不在场
- [ ] **M-T0b 变异副本**：只改一侧副本；红且 `REPLICA_MISMATCH` 与 `SECTION_MISSING` 皆在场
- [ ] **两条用例各含「真实模板字节前后一致」断言**，起点值用例内自采，无硬编码 sha256
- [ ] **`_mutate_on_disk()` 已删除或已改为不写真实模板**；全仓不存在对
      `TEMPLATE_PACKAGED` / `TEMPLATE_DOCS` 的写入调用
- [ ] **判据本体零改动**：`_read_text_preserving_newlines()` / `_check_both()` /
      `_inv_n_codes()` / `_mutate_both()` / T1–T7 其余用例全部零 diff
- [ ] **no-op guard 保留**（`mutated_bytes != original_bytes`，断在副本上）
- [ ] **`_crlf_rewrap_bytes()` 保留**先归一再改，不产出 `\r\r\n`
- [ ] **承重性实测已贴**：读路径还原为 `path.read_text` 后两条用例转红，报告含实际输出，
      且事后已恢复、`git diff` 无残留
- [ ] **oracle 第 4 项已追加两行**，两份模板逐字节一致，文本与本 brief 标的 2 逐字节相同，
      第 4 项共 6 行
- [ ] **`FROZEN_BODY_ACCEPTANCE` 已同步**，`test_invn_positive_control_clean_template` 绿
- [ ] **段内其余文本零改动**：第 1/2/3 项、第 4 项原有四行、开头两句、结尾「注意」两行
      逐字节不动；`## Re-freeze 规则` 段与 `FROZEN_BODY_RE_FREEZE` 完全不动
- [ ] **rev5 的 32 条用例保持绿**，四条兜底仍承重，三条边界逃逸仍 GREEN
- [ ] **`CONTRACT_TEMPLATE_VERSION` 仍 `"6"`**，`contract_render.py` / `init_cmd.py` /
      `pyproject.toml` 零 diff
- [ ] 零回归：全量 `4 failed / 631 passed / 4 skipped`（在 `2923255` 实测基线，
      用例条数不变故 passed 不变），failed 集合全在
      `tests/test_finalize_merge_triple_sign.py`，**报告里给出算术**
- [ ] 3.11 通过；3.13 / 3.14 若可用亦通过
- [ ] 无 forbidden_paths 写入；无 merge / push / 切分支；无跨 worktree 写主区
- [ ] 执行报告按 `AGENTS.md` §6.C 格式输出

## 风险声明

- production_writes: FORBIDDEN
- network: FORBIDDEN
- notifications: FORBIDDEN
- data_access: READ_ONLY

## 附注：已知陷阱

1. **别改判据本体**。编排者已核实 `_read_text_preserving_newlines(path)` 与
   `_check_both(text, text)` 都与路径无关，副本形态直接可用。
   把读路径改成 `read_bytes()`、或给判据加 `path` 参数，都属超范围。

2. **别用 `try/finally` 恢复真实模板来"顺带"保险**。本 rev 的标的就是
   *不写真实模板*；再留一条写入路径等于 B54 没修。

3. **「真实模板未被写入」的断言别写成硬编码 sha256**。硬编码会在下一次
   模板合法演进时假红，且它锁的是内容不是"未被写入"。用例内自采起点值。

4. **两份模板必须逐字节一致**，否则 `REPLICA_MISMATCH` 会污染每一条变异的 witness，
   任何步骤的红都无法与副本同一区分（rev3 §C 已立的规矩）。

5. **同步顺序无所谓，一致才算**。先改模板还是先改常量都行；
   编排者实测只改一侧会 7 failed，你会立刻看到。

6. **三条边界逃逸必须保持 GREEN**。把它们改红看起来像加强，实际是把 WP-29 的标的
   偷进本 WP，属超范围，会被判 REWORK。

7. **4 条既有 failed 不得修**。它们在 base 上即已红（工作树内 `git checkout -q main`
   失败），属环境问题，修它们等于改 forbidden_paths 下的文件。

8. **B52 不在本 rev 范围**。截断谓词归因过宽（删 body 末尾亦触发
   `SECTION_BODY_TRUNCATED`）已单独登记（任务 #42），留待后续 WP，别顺手收紧。

9. **自指提醒（第二次）**：rev5 你交付的是「用例必须杀得掉自己的 fix」，
   rev6 你交付的是「载具不得写被保护的制品本身」——
   而你交付它的方式必须先满足它：这一轮的两条用例，正是这条规矩的第一个实例。

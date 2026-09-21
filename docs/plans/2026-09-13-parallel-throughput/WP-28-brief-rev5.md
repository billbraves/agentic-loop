# WP-28 (rev5): 变异必须施加于判据真实的输入面，并证明用例杀得掉自己的 fix

> 冻结日期 2026-09-18 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 用户已批准第 5 次冻结方案 (a)（停手复核见 `WP-28-plan-review-before-rev5.md`）。
>
> **rev4 已 ACCEPT 的部分不得重做**：B50 判 ACCEPT 且承重，范围 / 零回归 / 三处 pin 全部干净。
> 本 rev 只有两件事：修 B49 的用例承重性，加一条规范条目的判别句。

## 目标（一句话）

把 rev4 的 M-T0 / M-T0b 从「变异判据已持有的字符串」改为「变异文件字节」，
使它们真的跨过读路径；并把「撤销 fix 后用例必须转红」这句可机械判别的要求
写进本 WP 交付的模板条目。

## 本 rev 的验收标的（两项，各自封闭）

### 标的 1 —— B49 的用例承重性（阻断项）

**修法本身已 ACCEPT，不要动它。** `_read_text_preserving_newlines()` 用
`open(path, encoding="utf-8", newline="")` 是 rev4 §A.4 路线 2，理由成立，保留原样。

问题在证明它的用例。rev4 的 M-T0 / M-T0b 形如：

```
packaged = _read_text_preserving_newlines(TEMPLATE_PACKAGED)   ← 读发生在这里
...
mutated = packaged.replace("\n", "\r\n")                        ← 变异发生在这之后
```

读在变异之前，所以读路径怎么写都不影响结果。编排者实测（三种读路径实现，
`pytest -k t0`）：

```
open(..., newline="")            → 2 passed     （rev4 交付态）
open(..., newline=None)          → 2 passed
path.read_text(encoding="utf-8") → 2 passed     ← 即 B49 缺陷原状，用例仍全绿
```

**把 fix 完整还原成缺陷原状，两条用例依然全绿** —— 它们证明的是「判据对含 `\r\n`
的字符串会红」，不是「判据能看见文件里的 `\r\n` 字节」。后者才是 B49 / INV-N1 / INV-N4 的内容。

这与 rev4 §A.2 亲手警告过的形态是同一个（`test_invn_t4_pure_rewrap_red` 挪的是
判据已持有字符串内部的换行点）。**根因在 rev4 brief 的措辞，不在你**：§A.4 说
「两份模板同步把 `\n` 改为 `\r\n`」而「模板」可读作文件或读出的字符串，
同条又要求变异须经 `_mutate_both()`（签名 `mutate(str) -> str`），
等于指定了一个跨不过读路径的载具。rev5 把这一点说死。

**要求**：

1. M-T0 / M-T0b 改为**落盘字节变异** —— 变异写入模板文件的字节，然后让判据自己去读。
   编排者已实测该形态具备杀伤力：

   ```
   同步改两份模板行尾字节 → 判据自己读
     open(..., newline="")            → ['SECTION_MISSING']    红，REPLICA_MISMATCH 不在场
     path.read_text(encoding="utf-8") → []                     绿 ← 逃逸复现
   ```

2. 这两条用例**不再经 `_mutate_both()`**（它的载具是 str，跨不过读路径）。
   `_mutate_both()` 与 T1–T7 其余用例保持原样，不得改动。

3. 落盘变异必须满足以下全部工程要求，缺一条即视为未完成：
   - **no-op guard 用字节比对**：`assert mutated_bytes != original_bytes`。
   - **`try / finally` 恢复**，且 `finally` 中断言恢复后**逐字节相等**
     （`assert p.read_bytes() == original[p]`）。测试无论通过还是失败都不得留下脏模板。
   - **两份模板同步变异**（M-T0），使 `REPLICA_MISMATCH` 不在场；M-T0b 只改一侧，
     `REPLICA_MISMATCH` 必须在场。归因分层规则沿用 rev3 §C。
   - **断言具体 witness code**：M-T0 断言 `SECTION_MISSING in codes` 且
     `REPLICA_MISMATCH not in codes`；M-T0b 断言两者皆在场。不得只断言「codes 非空」。
   - 变异从**当前文件字节**出发（`read_bytes()`），先 `b"\r\n" -> b"\n"` 归一再
     `b"\n" -> b"\r\n"`，避免仓库已有 CRLF 时产出 `\r\r\n`。

4. **报告必须给出撤销 fix 后转红的实测输出**：把 `_read_text_preserving_newlines()`
   临时还原为 `path.read_text(encoding="utf-8")`，运行这两条用例，**贴出转红的实际输出**，
   然后恢复。这是本 rev 的核心证据，缺它即未完成。恢复后须确认
   `git diff` 对该文件为干净（除你本轮的正式改动外无残留）。

### 标的 2 —— 把判别句写进模板条目（阻断项）

本 WP 交付的 oracle 第 4 项当前措辞是：

> 4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，
>    不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。

这句判别不了「变异施加点对不对」—— rev3 → rev4 → rev5 三轮的阻断项都是它漏掉的下一层
（比较逻辑 → 完整管线 → 真实输入面）。**能机械判别的是：撤销 fix，用例必须转红。**

**要求**：在**两份模板**（`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
`docs/agentic/templates/WORK_PACKAGE.md`）的 `## Acceptance tests` 段，把第 4 项扩写为
以下**逐字节确定**的文本（不得改写、不得增删标点）：

```
4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，
   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。变异必须施加于判据
   真实的输入面（文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示。
   判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。
```

**这是本 WP 唯一允许的冻结常量编辑。** 同步要求：

- 两份模板的这段改动必须**逐字节一致**（否则 `REPLICA_MISMATCH` 会红）。
- `FROZEN_BODY_ACCEPTANCE`（判据第 287 行起）必须同步更新为新文本，
  否则 `BODY_MISMATCH` 会红。**先改模板再改常量，或反之都可，但必须一致。**
- `test_invn_positive_control_clean_template` 必须仍绿（这是同步是否成功的判据）。
- 段内其余文本（第 1/2/3 项、开头两句、结尾「注意」两行）**逐字节不动**。
- `## Re-freeze 规则` 段及其 `FROZEN_BODY_RE_FREEZE` **完全不动**。

## 范围

允许改动的文件仅三个：

- `tests/test_wp_template_dispatch_lint.py` —— 仅 M-T0 / M-T0b 两条用例 +
  `FROZEN_BODY_ACCEPTANCE` 常量同步。
- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 仅 oracle 第 4 项。
- `docs/agentic/templates/WORK_PACKAGE.md` —— 仅 oracle 第 4 项，与上一份逐字节一致。

## 输入

- 本 brief（冻结版）。
- `WP-28-review-rev4.md` —— 编排者的实测表格与修法验证，是本 rev 的事实基础。
- `WP-28-plan-review-before-rev5.md` —— 第 5 次冻结裁定与根因归属。
- rev4 交付 commit `5d94387`（你的起点，base `7a30f50`）。

## 交付物清单

1. `tests/test_wp_template_dispatch_lint.py`：M-T0 / M-T0b 改落盘字节变异；
   `FROZEN_BODY_ACCEPTANCE` 同步新文本。
2. 两份模板的 oracle 第 4 项扩写（逐字节一致）。
3. 执行报告（`AGENTS.md` §6.C 格式），含标的 1 第 4 条要求的**撤销 fix 转红实测输出**、
   零回归算术、以及「落盘变异如何保证恢复」的说明。

## Acceptance tests

沿用 rev4 的全部用例，**一条不删**。本段只规定本 rev 新增/改造的判据。

**M-T0（改造）**：两份模板**文件字节**同步 `\n` → `\r\n`，不改任何字符、不动冻结常量
→ 判据必须红，`SECTION_MISSING` 在场，`REPLICA_MISMATCH` **不在场**。

**M-T0b（改造）**：只改**一侧**模板的文件字节行尾 → 必须红，
`REPLICA_MISMATCH` 与 `SECTION_MISSING` 皆在场。

**承重性证明（报告项，非用例）**：`_read_text_preserving_newlines()` 临时还原为
`path.read_text(encoding="utf-8")` → M-T0 / M-T0b 必须转红，贴出实测输出。

**同步证明**：`test_invn_positive_control_clean_template` 仍绿，证明模板与
`FROZEN_BODY_ACCEPTANCE` 逐字节一致。

**不得回归**：rev4 的 32 条全绿用例（含四条兜底 `not (codes & DIAGNOSTIC_CODES)`、
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

- [ ] **M-T0 落盘**：变异写入两份模板**文件字节**，判据自己读；红且 `SECTION_MISSING` 在场、
      `REPLICA_MISMATCH` 不在场
- [ ] **M-T0b 落盘**：只改一侧文件字节；红且 `REPLICA_MISMATCH` 与 `SECTION_MISSING` 皆在场
- [ ] **两条用例不再经 `_mutate_both()`**；`_mutate_both()` 及 T1–T7 其余用例零改动
- [ ] **no-op guard 用字节比对**（`mutated_bytes != original_bytes`）
- [ ] **`try / finally` 恢复且断言逐字节相等**；用例失败时亦不留脏模板
- [ ] **变异先归一再改**（`\r\n` → `\n` → `\r\n`），不产出 `\r\r\n`
- [ ] **承重性实测已贴**：读路径还原为 `path.read_text` 后两条用例转红，报告含实际输出，
      且事后已恢复、`git diff` 无残留
- [ ] **oracle 第 4 项已扩写**，两份模板逐字节一致，文本与本 brief 标的 2 逐字节相同
- [ ] **`FROZEN_BODY_ACCEPTANCE` 已同步**，`test_invn_positive_control_clean_template` 绿
- [ ] **段内其余文本零改动**：第 1/2/3 项、开头两句、结尾「注意」两行逐字节不动；
      `## Re-freeze 规则` 段与 `FROZEN_BODY_RE_FREEZE` 完全不动
- [ ] **rev4 的 32 条用例保持绿**，四条兜底仍承重，三条边界逃逸仍 GREEN
- [ ] **`CONTRACT_TEMPLATE_VERSION` 仍 `"6"`**，`contract_render.py` / `init_cmd.py` /
      `pyproject.toml` 零 diff
- [ ] 零回归：全量 `4 failed / 631 passed / 4 skipped`（在 `5d94387` 实测基线，
      用例条数不变故 passed 不变），failed 集合逐条同 rev4 §D，**报告里给出算术**
- [ ] 3.11 通过；3.13 / 3.14 若可用亦通过
- [ ] 无 forbidden_paths 写入；无 merge / push / 切分支；无跨 worktree 写主区
- [ ] 执行报告按 `AGENTS.md` §6.C 格式输出

## 风险声明

- production_writes: FORBIDDEN
- network: FORBIDDEN
- notifications: FORBIDDEN
- data_access: READ_ONLY

## 附注：已知陷阱

1. **别改修法**。`open(..., newline="")` 是对的。本 rev 改的是**证明它的用例**，
   不是它本身。把读路径改成 `read_bytes()` 属超范围。

2. **落盘变异会动真实仓库文件**，务必 `try / finally` + 恢复后字节断言。
   建议把恢复逻辑写成 fixture 或 contextmanager，两条用例共用一份，
   避免一条漏恢复污染另一条。

3. **仓库可能已含 CRLF**。直接 `b"\n" -> b"\r\n"` 会把已有 `\r\n` 变成 `\r\r\n`，
   那是另一种变异、witness 可能不同。先归一再改。

4. **两份模板必须逐字节一致**，否则 `REPLICA_MISMATCH` 会污染每一条变异的 witness，
   任何步骤的红都无法与副本同一区分（rev3 §C 已立的规矩）。

5. **三条边界逃逸必须保持 GREEN**。把它们改红看起来像加强，实际是把 WP-29 的标的
   偷进本 WP，属超范围，会被判 REWORK。

6. **4 条既有 failed 不得修**。它们在 base 上即已红（工作树内 `git checkout -q main`
   失败），属环境问题，修它们等于改 forbidden_paths 下的文件。

7. **B52 不在本 rev 范围**。截断谓词归因过宽（删 body 末尾亦触发
   `SECTION_BODY_TRUNCATED`）已单独登记，留待后续 WP，别顺手收紧。

8. **自指提醒**：你这一轮交付的正是「用例必须杀得掉自己的 fix」这条规矩，
   而你交付它的方式必须先满足它 —— 报告里那段撤销 fix 转红的输出，
   就是本 WP 对自己标的的兑现。

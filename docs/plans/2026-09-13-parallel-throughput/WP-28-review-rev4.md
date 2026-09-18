# WP-28 rev4 独立复核

> 复核者 Claude（编排者兼独立复核）| 2026-09-18
> 交付 commit `5d94387`（base `7a30f50`）| brief `WP-28-brief-rev4.md`
> sha256 `5cbfa77d04803e63f7481ed5fe9cf696ed24d479ccfb0a1e5368c4cb8d5840e2`

## 判定

**REWORK** —— 一个阻断项：**B49 的修法正确，但证明它的用例（M-T0 / M-T0b）不承重**。

B50 已修且承重；范围、零回归、各项 pin 全部干净。若只看「fix 在不在」，rev4 是通过的；
判 REWORK 的理由是**判据自检本身没有自检**，而这恰好是本 WP 的标的。

## B49 —— 修法 ACCEPT，用例 REJECT

修法本身正确。执行者选了 A.4 路线 2（`open(path, encoding="utf-8", newline="")`），
理由（保留冻结常量为 `str`，不改 INV-N4 的 diff 可见性语义）成立。

**但 M-T0 / M-T0b 变异的是判据已持有的内存字符串，不是文件字节**，
因此这两条用例从未跨过它们声称要钉住的那段读路径。实测（我自己的探针，非执行者断言）：

| 读路径实现 | M-T0 / M-T0b 结果 |
|---|---|
| `open(..., newline="")`（rev4 交付态） | `2 passed` |
| `open(..., newline=None)` | `2 passed` |
| `path.read_text(encoding="utf-8")`（= B49 缺陷原状） | `2 passed` |

**把 fix 完整还原成缺陷原状，两条用例依然全绿。** 这正是 brief §A.2 亲手警告过的形态：

> `test_invn_t4_pure_rewrap_red` 挪的是**判据已持有字符串内部**的换行点，
> 不是**文件里的换行字节**。**不得**以该用例已存在为由认为换行已被覆盖。

M-T0 复制了这个形态：`_mutate_both()` 先经 `_read_text_preserving_newlines()` 读入，
再对返回的 `str` 做 `.replace("\n", "\r\n")`。读取发生在变异之前，
所以读路径怎么写都不影响结果。红是真的（`SECTION_MISSING` 确实在场，
`REPLICA_MISMATCH` 确实不在场，两条断言都非真空），但它证明的是
「判据对含 `\r\n` 的字符串会红」，**不是**「判据能看见文件里的 `\r\n` 字节」。
后者才是 B49、INV-N1 与 INV-N4 的内容。

### 修法可行且已验证

把变异下沉到磁盘字节层即可判别。我实测的形态（同步改两份模板的行尾字节 → 判据自己去读）：

| 读路径实现 | 落盘变异后的 codes | 红？ |
|---|---|---|
| `open(..., newline="")` | `['SECTION_MISSING']` | 是（`REPLICA_MISMATCH` 不在场） |
| `path.read_text(...)` | `[]` | **否 —— 逃逸复现** |

同一条变异在 fix 在场时红、fix 撤销时绿，即具备杀伤力。要求：变异写文件字节
（`write_bytes`）、no-op guard 用字节比对、`try/finally` 恢复并断言恢复后逐字节相等。

## B50 —— ACCEPT

- `SECTION_BODY_TRUNCATED` 在 `HARD_CODES`，**不在** `DIAGNOSTIC_CODES`（四条兜底用例未被连带失效，仍在承重）。
- 区分力实测：T3 截断 → `['BODY_MISMATCH', 'SECTION_BODY_TRUNCATED']`；
  T4 删分句 → `['BODY_MISMATCH']`，`SECTION_BODY_TRUNCATED` 不在场。
- **承重性实测**：删掉发射点（`if frozen_body.startswith(body): codes.add(...)`）
  → `test_invn_t3_body_slicing_truncated_red` 转红。用例确实钉住了这段实现。

## 非阻断发现 —— 登记为 B52

截断谓词的真实语义是「body 是冻结值的真前缀」，比 §A.1 给 T3 的定义
（「块体边界被移动」）宽：**只删 body 末尾**（不插入 `## `、边界未动）也会产出
`SECTION_BODY_TRUNCATED`。

不阻断，因为它**不是逃逸**：该输入仍红（`['BODY_MISMATCH', 'SECTION_BODY_TRUNCATED']`），
是已红输入上的归因过宽，而非放行。brief §A.3 要求的区分力针对的是
「T4 类变异」——即删分句那一条，已满足。

收紧可行且已验证：真 T3（插入 `## `）同时产出 `SECTION_ANCHOR_MOVED: True`，
删尾则为 `False`，故谓词可收紧为「前缀 AND 块内出现新 `## ` 行」。留待后续 WP。

## 其余 DoD 逐项

| 项 | 结果 |
|---|---|
| rev3 的 21 条变异一条不删 | 通过（与 `2ba5ef5` 逐名对比，`none dropped`；6 → 31 条 test def） |
| 四条兜底用例仍承重 | 通过（744 / 756 / 774 / 787 行 `not (codes & DIAGNOSTIC_CODES)` 均在） |
| 三条边界逃逸仍 GREEN | 通过（E1 整档注释 / E2 BOF 未闭合 `<!--` / E3 `## 附注` 内未闭合围栏，实测 codes 均 `[]`） |
| `CONTRACT_TEMPLATE_VERSION` 仍 `"6"` | 通过 |
| `contract_render.py` / `init_cmd.py` / `pyproject.toml` 零 diff | 通过（三者 ZERO_DIFF） |
| 模板承载规范条目 | 通过（两份模板同步 +11/−4：新增「Re-freeze 规则」段 + oracle 第 4 项「变异集按判据自身的组成步骤生成」） |
| 零回归 | 通过：`4 failed / 631 passed / 4 skipped`；算术 `631 − 628 = 3` = 新增 M-T0 / M-T0b / M-T3-neg |
| 范围 | 通过（累计 diff 仅 3 文件：两份模板 + 判据用例） |
| 无 merge / push / 跨 worktree 写主区 | 通过 |

## 返工要求（rev5 唯一标的）

1. M-T0 / M-T0b 改为**落盘字节变异**，并在报告里给出「fix 撤销后该用例转红」的实测输出
   —— 即证明用例杀得掉自己的 fix。
2. 其余一切不动。B50 已 ACCEPT，勿重做；B52 不在本 rev 范围。

> 附：本轮暴露的是「负面断言需要变异自检」在**变异自身**上的递归缺口 ——
> 判据自检的变异集若不施加于真实输入面，就只是换个写法的真空断言。
> 这条应回流到本 WP 交付的规范条目里，作为后续 WP 的标的。

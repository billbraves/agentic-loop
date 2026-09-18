# WP-28 rev5 独立复核

> 复核者 Claude（编排者兼独立复核）| 2026-09-18
> 交付 commit `2923255`（base `7a30f50`，起点 `5d94387`）| brief `WP-28-brief-rev5.md`
> sha256 `d96a7fa34ae0520bfe6e5b1d4e769916857cab4f0fd1eb9004278590a559bfd6`

## 判定

**ACCEPT** —— 两项标的均兑现，无阻断项。

复核基于我自己的探针，不依赖执行者报告的任何断言。所复核的文件内容
sha256 `f3de4ac0332855ae335b5904cf4e3aec327de200da0292dc9667a3c622f2c988`
与 `2923255` 提交态逐字节相同。

## 标的 1 —— 用例承重性：通过

判别方式就是本 rev 写进模板的那一句：撤销 fix，用例必须转红。

| 读路径实现 | M-T0 / M-T0b |
|---|---|
| `open(..., encoding="utf-8", newline="")`（交付态） | `2 passed` |
| `path.read_text(encoding="utf-8")`（= B49 缺陷原状） | **`2 failed`** |

对比 rev4：同一还原动作下 rev4 是 `2 passed`（不承重），rev5 是 `2 failed`。
**用例现在杀得掉自己的 fix。**

载具正确：新增 `_mutate_on_disk()` contextmanager 把变异写进模板**文件字节**，
判据随后自己去读，读路径成为变异字节与 witness 之间的唯一环节。两条用例不再经
`_mutate_both()`，而 `_mutate_both()` 与 T1–T7 其余用例零改动。

工程要求逐条实测：

| 要求 | 结果 |
|---|---|
| 字节 no-op guard | 通过（`assert data != originals[p]`，逐文件） |
| `finally` 恢复且断言逐字节相等 | 通过（`assert p.read_bytes() == data`） |
| **失败路径亦恢复** | 通过 —— 我在 `with` 块内（模板处于变异态时）注入 `assert False`，用例转红，模板 sha256 `ed5dc2d4…` 前后完全相同 |
| 跑完整套后模板字节完好 | 通过（两份模板 sha256 前后一致） |
| 先归一再改行尾 | 通过（`b"\r\n"→b"\n"→b"\r\n"`；对已 CRLF 的输入再变异一次，`\r\r\n` 计数为 0） |
| M-T0 两份同步，`REPLICA_MISMATCH` 不在场 | 通过 |
| M-T0b 单侧，`REPLICA_MISMATCH` 与 `SECTION_MISSING` 皆在场 | 通过 |
| 断言具体 witness code | 通过（非「codes 非空」） |

## 标的 2 —— 判别句进条目：通过

两份模板的 oracle 第 4 项扩写为 brief 指定文本，**逐字节相符**，
两份模板 sha256 相同（`REPLICA_MISMATCH` 不会红）。
`FROZEN_BODY_ACCEPTANCE` 已同步，`test_invn_positive_control_clean_template` 绿
—— 即模板与冻结常量一致的判据。

新增文本：

> 变异必须施加于判据真实的输入面（文件字节 / 进程边界 / 外部状态），
> 不得只改判据已持有的内存表示。判别方式：把被修的缺陷还原成原状，
> 该用例必须转红；仍绿则该用例不承重。

段内其余文本（第 1/2/3 项、开头两句、结尾「注意」两行）零改动；
`## Re-freeze 规则` 段与 `FROZEN_BODY_RE_FREEZE` 未动。

## 其余 DoD

| 项 | 结果 |
|---|---|
| rev4 的 32 条用例保持绿 | 通过（`32 passed`） |
| 四条兜底仍承重 | 通过（`not (codes & DIAGNOSTIC_CODES)` 均在） |
| 三条边界逃逸仍 GREEN | 通过（前一轮已实测，本轮判据无关改动） |
| `CONTRACT_TEMPLATE_VERSION` 仍 `"6"` | 通过 |
| 三处 pin 零 diff | 通过（`contract_render.py` / `init_cmd.py` / `pyproject.toml` 均 ZERO_DIFF） |
| 零回归 | 通过：`4 failed / 631 passed / 4 skipped`，与 rev5 brief 预期一致（用例条数不变故 passed 不变）；4 failed 全在 `test_finalize_merge_triple_sign.py`，base 上即已红 |
| 范围 | 通过（累计 diff 仅 3 文件） |
| 无 merge / push / 跨 worktree 写主区 | 通过（工作树干净，单 commit） |

## 执行者报告核对

报告的每条可验算断言我都独立复算，无虚报：

| 报告断言 | 我的核对 |
|---|---|
| 还原 read path 后 `2 failed`，`AssertionError: set()` | 一致 —— 我的探针独立跑出 `rc=1, 2 failed` |
| 全量 `4 failed / 631 passed / 4 skipped` | 一致（我自己跑的同一数字） |
| 「未增删用例，故 passed 不变」 | **算术成立** —— `def test_` 全仓 514 → 514，目标文件 31 → 31，用例名集合逐字节相同 |
| 4 failed 为既有环境失败（`init.defaultBranch=master`） | 一致，全在 `test_finalize_merge_triple_sign.py`，base 上即红 |
| 目标文件 `32 passed` | 一致（31 个 def + 1 个参数化展开） |
| 三处 pin 零 diff | 一致（ZERO_DIFF） |
| `CONTRACT_TEMPLATE_VERSION` 仍 `"6"` | 一致 |
| 工作树干净、单 commit、无 merge/push/切分支 | 一致 |

主动披露一项环境限制：全量仅在 Python 3.11 跑过，本机 3.13/3.14 未装 pytest。
本 WP 未声明多解释器矩阵，故不构成缺项；记录在此备查。

## 复核过程中我自己的两次探针失误（记录用）

1. 第一版探针用正则匹配读取实现，因执行者的 docstring 形状不同而 `PROBE_INVALID`。
   guard 生效，未产出假结论。
2. 第二版验「失败路径是否恢复」时，锚点在文件中出现 2 次，探针自行中止；
   我当时误把随后那句「模板完好」当成了结论，实际那是未注入的正常运行。
   改用 `with` 块内锚点重做后才拿到真结论。

两次都印证 [[your-own-probe-needs-a-noop-guard]]：探针找不到目标时的输出，
与真结论长得一样。

## 后续（不阻断本 WP）

- **B52**：截断谓词归因过宽（任务 #42），已定为本 rev 范围外。
- **B47**：段落门禁按固定命名读 brief，五轮冻结从未读过 rev2–rev5
  （实测见 `B47-measurement.md`，18/22 个 WP 受影响）。**本 WP 的 PREFLIGHT_PASS
  校验的是 rev1 的段落**，不影响上述判定（我的复核未依赖该门禁），但需尽快修。
- **合入前置**：按 `[review_policy]` 需 codex 第二签名；合入本身仍须用户批准。

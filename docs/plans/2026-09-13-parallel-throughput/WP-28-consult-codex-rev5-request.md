# WP-28 rev5 第二签名咨询请求（codex，read-only）

> 请求者 claude（编排者兼独立评审）｜2026-09-18｜咨询者 codex（read-only）
> 合入前第二签名。本仓双签名规则要求 `consult.decision == ACCEPT` 才可进入
> `APPROVED_FOR_MERGE`。编排者已判 ACCEPT（`WP-28-review-rev5.md`）。

## 你要裁决什么

给出 `ACCEPT` 或 `REWORK`（含具体阻断项）。判据是：**本轮 diff 是否兑现了下方内联的
rev5 冻结 brief**，以及是否存在 correctness / architecture / security / 削弱测试信号
一类的阻断项。

- 冻结 brief：`WP-28-brief-rev5.md`，sha256 `d96a7fa34ae0520bfe6e5b1d4e769916857cab4f0fd1eb9004278590a559bfd6`
- 被审提交：`2923255`（起点 `5d94387` = rev4 交付）
- 累积 diff：`7a30f50..2923255`（3 文件 / +687 −4）
- 本轮增量：`5d94387..2923255`（3 文件 / +59 −20）
- worktree：`/Users/admin/vibe/wp28-norms-into-template`

## rev5 的范围极窄，请勿扩边界

你在 rev3 轮（`WP-28-consult-codex-rev3-verdict.json`）判 REWORK，两个阻断项：
B49（`read_text()` 让「逐字节」被 universal-newline 归一化绕过）与 B50（T3 无步骤特异
witness）。rev4 修了两者：新增 `_read_text_preserving_newlines()` 与
`SECTION_BODY_TRUNCATED`。

**但编排者在 rev4 复核时发现 B49 的用例不承重**：M-T0/M-T0b 把 CRLF 变异施加于判据
**已持有的内存字符串**，从不经过读路径 —— 撤销 fix（换回 `Path.read_text`）后两条
用例仍 `2 passed`。根因在编排者自己 rev4 brief §A.4 的措辞把变异载具默认成了内存值。
第 5 次冻结触发本仓「第 3 次及以后 re-freeze 强制停手复核」规则，用户批准了缩小方案。

rev5 因此**只有两个标的**：

1. M-T0/M-T0b 改为对**真实落盘文件字节**变异（新增 `_mutate_on_disk` contextmanager，
   带 no-op guard 与 byte-exact 还原保证），使读路径成为变异字节与 witness 之间的唯一环节；
   报告须给出「撤销 fix 后两用例转红」的实测。
2. 把判别句折进模板 oracle 第 4 项（B53）：变异必须施加于判据真实的输入面
   （文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示；判别方式是把被修的
   缺陷还原成原状看用例是否转红。

**承诺边界未变**，仍是 rev3 缩小后的 INV-N1（受保护块身份逐字节）+ INV-N3（副本同一）
+ INV-N4（变更可见性）。判据源码 docstring 里那三条「明文不覆盖」（整份文档注释外包、
文档开头未闭合 `<!--`、`## 附注` 内未闭合围栏）**仍是声明的边界，不是漏测**；渲染语义是
WP-29 的标的。请不要因为「未覆盖渲染语义」判 REWORK。

## 编排者已独立复核的结论（供你对照，不是让你采信）

- **承重性**：撤销 fix（`_read_text_preserving_newlines` → `Path.read_text`）后
  `pytest -k t0` = `2 failed`（`AssertionError: set()`）；恢复 fix 后 `2 passed`。
  rev4 同一动作是 `2 passed`。
- **失败路径下的还原**：我在 `with _mutate_on_disk(...)` 块内（模板处于变异态时）注入
  `assert False`，用例转红，两份模板 sha256 前后完全相同 —— `finally` 在异常传播前已还原。
- **CRLF 幂等**：`_crlf_rewrap_bytes` 先 `\r\n→\n` 再 `\n→\r\n`；对已 CRLF 的输入再变异
  一次，`\r\r\n` 计数为 0。
- **归因分层**：M-T0 两份同步施加，`REPLICA_MISMATCH` 不在场；M-T0b 单侧，
  `REPLICA_MISMATCH` 与 `SECTION_MISSING` 皆在场。
- **oracle 第 4 项**：两份模板与 brief 指定文本逐字节相符，两份模板 sha256 相同；
  `FROZEN_BODY_ACCEPTANCE` 已同步，`test_invn_positive_control_clean_template` 绿。
- **零回归算术**：`4 failed / 631 passed / 4 skipped`，与 rev4 相同。`def test_` 全仓
  514→514、目标文件 31→31、用例名集合逐字节相同 —— 未增删用例，故 `passed` 不变。
  4 个 failed 全在既有的 `test_finalize_merge_triple_sign.py`（base 上即已红）。
- **范围**：累积 diff 仅 3 文件全在 `allowed_paths`；`contract_render.py` / `init_cmd.py`
  / `pyproject.toml` 均零 diff；`CONTRACT_TEMPLATE_VERSION` 仍 `"6"`。
- **纪律**：工作树干净、单 commit、无 merge/push/切分支/网络/生产写入。

## 请特别检查的四点

1. **`_mutate_on_disk` 的还原保证是否真的无洞**：异常路径、嵌套使用、部分写入失败、
   多文件间的顺序。这个载具直接写测试仓里的真实模板文件，一旦漏还原会污染工作树。
2. **M-T0/M-T0b 现在是否真的过读路径**：变异字节与 witness 之间除了
   `_read_text_preserving_newlines` 还有没有别的环节能吸收掉差异。
3. **oracle 第 4 项扩写后是否仍与判据的冻结常量一致**，以及扩写文本本身是否引入了
   与模板其他条目矛盾的口径。
4. **T1–T7 与其余 30 条用例是否被这次改动无意削弱**（rev5 只该动 M-T0/M-T0b 两条）。

## 已知的、本轮范围外的缺陷（请勿据此判 REWORK）

- **B52**：`SECTION_BODY_TRUNCATED` 谓词归因过宽（编排者自己在 rev4 轮发现，已立任务 #42）。
- **B47**：`dispatch_lint.sh` 按固定命名 `{wp_id}-brief.md` 读 brief，忽略
  `evidence.brief.path`，故本 WP 五轮冻结的 `PREFLIGHT_PASS` 校验的都是 rev1 的段落
  （实测见 `B47-measurement.md`，18/22 个 WP 受影响，已立任务 #38）。
  `forbidden_paths` 明禁 `wrappers/*.sh`，不在本 WP 范围。编排者的复核未依赖该门禁。

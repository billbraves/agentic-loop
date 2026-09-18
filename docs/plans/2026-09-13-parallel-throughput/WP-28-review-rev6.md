# WP-28 rev6 独立复核

> 复核者 claude（编排者，独立复核）| 2026-09-18 | 被复核 commit `361b3ad`（base `2923255`）
> brief `WP-28-brief-rev6.md` sha256 `ee57a96c5f15157e70817ea9e4a99b520a214b3be874e7ae2e35e045229335fd`

## 结论

**ACCEPT**（编排者初判）—— 合入仍须 codex 第二签名（`consult.decision=ACCEPT`）+ 用户明确批准。

理由一句话：B54 的失败类**不再存在**（载具不再写受保护制品），而承重性一分未掉
（撤销 B49 fix 两条仍转红），且把 B54 的形状本身变成了机械可判 —— 我把 B54 重新植入，
用例转红。

## 我自己攻的五条（执行者未见过，全在一次性 `git archive` 树上跑，不动交付树）

探针 `/Users/admin/.claude/jobs/8a8bf01e/tmp/verify-rev6.py`，按判据的组成步骤生成：

| # | 变异 | 结果 | 判读 |
|---|------|------|------|
| O0 | 原样交付 | `32 passed` | 基线 |
| O1 | 撤销 B49 fix（`newline=""` → `read_text`） | `2 failed`（`-k t0`） | **承重性保留**：换载具没有以牺牲杀伤力为代价 |
| O2 | 删掉 no-op guard | `2 passed` | 预期绿 —— guard 只在变异本身是恒等时才承重，见 O5 |
| O3 | **把 B54 形状重新植入**（载具改回写真实文件） | `2 failed`（`-k t0`） | **决定性**：「真实模板字节前后一致」断言真的挡得住 B54 |
| O4 | 常量与模板脱同步 | `7 failed / 25 passed` | 同步要求承重（含三条 harmless-green 连带转红） |
| O5 | 把 `_crlf_rewrap_bytes` 改成恒等 | `2 failed`（`-k t0`） | no-op guard 在其真正的触发条件下承重 |

O2 与 O5 是一对：单看 O2 会以为 guard 不承重，O5 说明它承的是「变异退化成恒等」那一面。
这正是 guard 存在的理由 —— 记忆 `mutation-must-assert-it-changed-something` 的场景。

O3 是本轮的核心：rev5 的缺陷不是「恢复写得不够稳」，而是「载具会写它要保护的东西」。
新断言把这条约束从代码走查提升为用例，所以同一形状的回归会被自动挡下，
而不是靠下一个复核者眼力好。

## 两个标的逐项核

### 标的 1 —— B54

| 要求 | 实测 |
|------|------|
| M-T0/M-T0b 改为变异临时副本 | 通过（`tmp_path` fixture，`_copy_bytes_to_tmp`） |
| 判据本体零改动 | 通过：`_read_text_preserving_newlines` / `_check_both` / `_inv_n_codes` / `_mutate_both` / `_crlf_rewrap_bytes` / `_classify_body_diff` / `_extract_body` 逐个函数体 sha 前后一致 |
| `_mutate_on_disk` 已删除 | 通过；`from contextlib import contextmanager` 一并移除（已无使用者） |
| 全仓无对受保护常量的写入调用 | 通过：`write_bytes` / `write_text` / `open(...,"w")` / `unlink` / `rename` 全仓零命中 |
| no-op guard 保留（断在副本上） | 通过，且 O5 证明其承重 |
| `_crlf_rewrap_bytes` 先归一再改 | 通过（零 diff） |
| 「真实模板字节前后一致」断言 | 通过，两条用例各含；起点值用例内 `read_bytes()` 自采，**无硬编码 sha256** |
| 撤销 fix 转红实测 | 通过（执行者已贴；我独立复现 = O1） |
| 恢复后无残留 | 通过：交付树 `git status --porcelain` 空，模板 sha 仍 `bf2cb285…` |

### 标的 2 —— oracle 第 4 项

| 要求 | 实测 |
|------|------|
| 两份模板末尾追加两行 | 通过，diff 各 `+2`，文本与 brief 逐字节相同（缩进 3 空格） |
| 第 4 项共 6 行 | 通过 |
| 两份逐字节一致 | `cmp` IDENTICAL；两份 sha256 均 `bf2cb2858e37c53202259c830be601c074f0e920d8e1d3ea91b59fdb701595e5`（与冻结前我在副本树预算的值一致） |
| `FROZEN_BODY_ACCEPTANCE` 同步 | 通过，追加两个字面量；`test_invn_positive_control_clean_template` 绿 |
| 段内其余 + Re-freeze 段零改动 | 通过（diff 只有那两行） |

## 范围与零回归

- 改动文件恰为 allowed_paths 三项，无第四个。
- `contract_render.py` / `init_cmd.py` / `pyproject.toml` / `AGENTS.md` / `CLAUDE.md` 零 diff；
  `CONTRACT_TEMPLATE_VERSION` 仍 `"6"`。
- 主区未被跨 worktree 写入（主区 dirty 仅本会话之外的既有 6 项 + 2 项 untracked，与本 WP 无关）。
- 无 merge / push / 切分支；HEAD 在 `feature/wp28-norms-into-template`。
- 零回归（编排者独立复跑）：
  - 目标文件 `32 passed`
  - 全量 `4 failed / 631 passed / 4 skipped`，4 条全在
    `tests/test_finalize_merge_triple_sign.py`（既有环境红）
  - 算术：`def test_` 全仓 514→514，目标文件 31→31，**用例名集合逐条相同**（`diff` 空），
    故 passed 不变 = 631。这是「passed 未变」可信的机械依据，不是眼估。
- 三条已声明的边界逃逸仍 GREEN（我自撰探针实测 codes 均 `[]`）：
  E1 整档注释外包 / E2 BOF 未闭合 `<!--` / E3 `## 附注` 内未闭合围栏。
  四条 harmless-green 用例仍绿。

## 我自己漏了什么 / 遗留

1. **3.13 / 3.14 未验**：两个环境未装 pytest（执行者已如实报告）。与 rev5 同样的限制，
   本轮改动不涉及版本相关 API（`tmp_path` 是 pytest 内建 fixture），风险低但**未实测**。
2. **B52 仍在**（任务 #42）：`SECTION_BODY_TRUNCATED` 归因过宽，本轮显式出范围，未动。
3. **B47 仍在**（任务 #38）：本轮 `PREFLIGHT_PASS` 里的段落门禁读的是 `WP-28-brief.md`
   而非 rev6，rev6 的三个必需段落由我独立核，不是门禁核的。
4. **O2 的形状值得记一笔**：一条 guard 在「删掉它仍全绿」下看似不承重，
   实际承的是另一维度（变异退化）。只做「删掉看是否转红」的承重性检查会误杀这类 guard，
   需要同时构造它真正的触发条件。

## 第二签名（codex，2026-09-18）

`consult.decision = ACCEPT`，无阻断项（`WP-28-consult-codex-rev6-verdict.json`，
sha256 `cdf73f3a…`）。六条 evidence 与编排者独立结论一致：变异只写 `tmp_path` 副本、
判据经 `_read_text_preserving_newlines(copy_path)` 重读、no-op guard 与
`_crlf_rewrap_bytes()`/witness 断言未削弱、真实模板字节运行时快照对比而非硬编码
sha256、oracle 两行三处一致、改动仅三个 allowed_paths。

一条 non-blocking：末尾的前后字节比较无法侦测「中途写入真实模板后又成功还原」的瞬时
写入，rev5 那类形状理论上可绕过该断言。编排者交叉核验：本轮载具代码已完全取消对真实
路径的写入（全仓 grep `write_bytes`/`write_text`/`open(...,"w")` 指向
`TEMPLATE_PACKAGED`/`TEMPLATE_DOCS` 为 NONE），静态写入面补足了这一点；该条与本文档
遗留项同源，记入 follow-up 而非本轮阻断。

**合入门禁**：双签名齐（编排者 ACCEPT + codex ACCEPT）。`state` 仍为
`READY_FOR_REVIEW`——**尚未获得用户对合入的明确批准**，故未进 `APPROVED_FOR_MERGE`、
未执行 `git merge --no-ff`、未 `agentic finalize`。

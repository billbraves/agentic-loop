# 2026-09-16 /context 清理前交接（会话 8a8bf01e）

> 用途：本文件是 `/context` 清理后**唯一**的任务恢复依据。清理后新会话读本文件 +
> 三份 `WP-2{5,6,7}.status.json` 即可精确接续，不依赖任何对话记忆。
> 结论：**SAFE_TO_CLEAR** —— 无在跑任务、无未提交的活跃任务改动、下一步可从追踪文件重建。

## 1. 一句话现状

WP-26 rev2 已由编排者判 ACCEPT 并完成加固补丁实测（HEAD `16bfdf3`），
**卡在 codex 复签 + 用户批准**两道门；WP-25 / WP-27 的 rev2 brief 均已冻结但**尚未派发**，
按既定顺序约束排在 WP-26 合入之后。全程未 merge、未 push、未 release。

## 2. 三个 WP 的精确状态

| WP | state | review | consult | worktree HEAD | 下一步 |
|----|-------|--------|---------|---------------|--------|
| WP-25 | `CHANGES_REQUESTED` | REWORK (B20) | — | `wp25-protocol-disciplines` @ `359cb1a` | rev2 brief 已冻结且已自检修缺段（B23），**待派发** |
| WP-26 | `READY_FOR_REVIEW` | **ACCEPT** | REWORK（阻塞级别已被编排者实测证伪，B24） | `wp26-brief-source-of-truth` @ `16bfdf3` | ① codex 对 `16bfdf3` 复签 ② 用户批准合入 |
| WP-27 | `CHANGES_REQUESTED` | REWORK | REWORK | `wp27-preflight-status-source` @ `a3264c0` | rev2 brief 已冻结，**待派发**（排 WP-26 之后） |

三份 status JSON 均 `STATUS_VALID`；三个 worktree 均 clean（`git status --porcelain` 空）。

## 3. WP-26 的合并门（逐项）

`WP-26.status.json` 的 `review.merge_gate` 就是权威记录：

1. ✅ 加固补丁已落地 `16bfdf3` 并由编排者独立重测通过
2. ⏳ **codex 对加固后的 `16bfdf3` 复签** —— 未完成
3. ⏳ **用户明确批准合入** —— 未取得

`state` 故意停在 `READY_FOR_REVIEW`，**未**置 `APPROVED_FOR_MERGE`。
编排者不得自签自批：本轮 B21 正是编排者一审漏判、由第二签名捕获。

### 加固补丁 `16bfdf3` 实测数字（`evidence.hardening_rev2`）

- targeted `tests/test_dispatch_lint_brief_source.py`：**23 passed** @ 3.11 / 3.13 / 3.14（加固前 22）
- 全量 3.11：**4 failed, 620 passed, 4 skipped** —— 4 条失败全为 `tests/test_finalize_merge_triple_sign.py`
  既有失败（`git checkout -q main` CalledProcessError），与 rev2 基线 `359cb1a` 同一失败集；
  passed 由 619 增至 620 正是新增的那 1 条。**不要修这 4 条既有失败。**
- 两条反向探针都做过且都还原为零 diff：
  - 把 codex 被拒判据 `len(stderr.splitlines())==1` 塞回 helper → `1 failed, 13 passed`，
    失败点恰为新增的 `test_multi_error_continuation_keeps_single_token`；
  - 在 `copytree` scratch 副本上让 `fail()` 向 stdout 泄一行 → 命中 `stdout must be empty`，
    证明该不变量承重、非装饰。

## 4. 本会话新登记的两条缺陷（已在 `WP-08-candidate.md`，共 21 节）

- **B23**：冻结者自身漏掉门禁锚点段 —— 我冻结的 `WP-25-brief-rev2.md` 缺
  `## Allowed and forbidden paths`，活树门禁判据会拒收；而 B16 掩盖了它（门禁读固定名的 rev1 文件返 PASS）。
  已修（sha256 → `9d19fbe70e2f5b9dbbad757d18f9911777a7c7c8486ad02a33658bbb62aea66b`）并折进任务 #23。
- **B24**：第二签名诊断正确、但其**提议的判据被实测证伪**。处置 = 取其关切、弃其形式，
  并把证伪实测留痕 + 在测试 docstring 记录拒用理由 + 加反回归测试防后人重新采纳。
  已同步为记忆 `verify-the-remedy-not-just-the-finding`。

## 5. 清理后的立即下一步（按序）

1. 用 `/Users/admin/.claude/jobs/8a8bf01e/tmp/consult/run_consult.py` 派发 codex 对 `16bfdf3` 复签
   （**必须** import 被审树自己的 `ReviewContract` / `CodexAdapter` / `VERDICT_SCHEMA` / `resolve_role_binding`——B14：
   不用别棵树的代码去判这棵树；`--output-schema` 解析失败属常态，原文逐字留痕即可）。
2. 复签 ACCEPT 后，**带着门禁三项去问用户**要合入批准。未获批准前不得 merge。
3. 获批合入后按 `agentic finalize` 盖章，再依 `dispatch_ordering_constraint` 派发 WP-27 rev2，最后 WP-25 rev2。

## 6. 环境句柄

- 锁：`.agentic/locks/wp/2026-09-13-parallel-throughput__WP-2{5,6,7}`，owner 均为
  `claude-8a8bf01e`（本会话）。清理后新会话是**同一会话延续**，可直接 `--takeover`（过 TTL）
  或 `--force-takeover`（用户指示交接）。
- 未提交的主区改动**与本任务无关**，不必也不应在本任务里处理：
  `.agentic/config.toml`（会话外被改为本地 kiro 网关）、`AGENTS.md`、`CLAUDE.md`、
  `docs/agentic/OPERATING_MODEL.md`、`docs/plans/2026-09-14-codex-verdict-contract/`、`uv.lock`。
- 派发执行者的形态：`env -u OPENAI_BASE_URL -u OPENAI_API_KEY kimi --afk --config-file ~/.kimi/deepseek.toml -p '<prompt>'`
- 门禁自跑形态：`bash src/agentic_loop/wrappers/dispatch_lint.sh <status.json>`
  （**不要**用 `agentic dispatch-lint` 自证 —— B14：那是落后活树的冻结副本）
- 跨版本形态：`PYTHONPATH=src uv run --quiet --python 3.13|3.14 --with pytest --no-project python -m pytest <targeted> -q`

## 7. 待办总览（编排者自身敞开项，非本次阻塞）

B12（#11）、B14 自检（#14）、B22 preflight 9 次 open（#27）、
门禁按 blast radius 分道（#22）、学习回边机械化（#23，含 B23）、
第 3 次 re-freeze 强制复核计划（#24）、存量 6 个 APPROVED 未派发 WP 重估（#25）、
清理 4 个已合入 worktree（#26）、A19+A23（#2）、A26（#3）。

# WP-21 rev2 咨询记录（codex）

> 触发时间 2026-09-15 ｜ 提问者 claude（编排者）｜ 咨询者 codex（provider: kirogpt）
> 依 `CLAUDE.md`「record its question and recommendation in the iteration directory」落盘。
> 原始 prompt：`/Users/admin/.claude/jobs/8a8bf01e/tmp/wp21r2-consult-prompt.txt`
> 原始日志：`/Users/admin/.claude/jobs/8a8bf01e/tmp/wp21r2-consult.log`（332KB）

## 触发理由

WP-21 rev1 的 A29 characterization test 被编排者变异测试判定为**空验证**（缺陷 A35），
而该缺陷由编排者自己的 rev1 Brief 逐字规定的断言造成。rev2 是编排者对自己缺陷的返工，
**不能自审自过**，故请独立审核者复核 rev2 是否真正具备区分力。

## 结论：本次咨询**未产出正式裁定**（进程异常终止）

codex **没有**输出 `[VERDICT]` / `[FINDINGS]` / `[RATIONALE]` 任何一个正式区块。
日志逐行核验（行首锚定匹配）：**0 个正式标记**。进程在最后一个 `codex` 空回合后
因 `codex_models_manager` 的 `stream disconnected before completion` 结束，
`tokens used 5,928`。

> ⚠️ **本记录不得被当作 ACCEPT 使用。** 编排者第一次提取时曾把 offset 248447 处的
> `[VERDICT] ACCEPT` 误读为 codex 的裁定——那实际是 codex 用 `nl -ba` 打印的**文档正文**
> （WP-08-candidate.md 第 1728 行）。这与 A31/A35/B8 同族：**观测通道选错**。
> 正确判据是**行首锚定**且排除 `nl` 行号前缀，而非全文 `grep`。

codex 最后一个叙述性回合（非裁定）陈述了倾向：

> 结论趋向明确：实现没有 P0/P1 功能回归，rev2 能杀死指定两种 fail-open 变异；
> 但有两处需要如实分级，一是负向用例没有绑定「失败来源」，二是 shell 注释对所有
> `&&`/`||` 位置作了过宽概括。

**叙述性回合不是裁定。** 但它点名的两处，编排者已独立实测复核如下。

## 编排者对 codex 两处发现的独立复核

### 发现 1（成立，P2，非阻断）：负向用例未绑定失败来源

codex 指出：负向运行只断言 `rc != 0` 且输出无 `FINALIZE_OK`，**没有**断言 stderr
确实含注入的 `RuntimeError`，因此形式上不能排除「影子环境在判据之前的某一步失败」
这一**新的**空过通道。

编排者实测（真实临时仓 + 影子包，`probe_a35_source.py`）：

```
rc = 1
stderr: RuntimeError: injected broken predicate (WP-21 A29 hardening)
'injected broken predicate' in stderr: True
```

**定性**：失败来源**确实**是判据，rev2 用例的结论是对的；但该事实**没有被断言锁住**。
用例已有的 `probe` 前提断言（第 62 行 `assert "injected broken predicate" in probe.stderr`）
只证明影子包本身会抛，**不证明** finalize 那一次运行死在判据上。

**处置**：**采纳为 P2 改进项，不阻断 rev2**。理由：
1. 现有断言配上正面对照（`control` 必达 `FINALIZE_OK`）已排除「更早一步失败」——
   同一 status、同一仓，唯一变量是影子包，正面对照走到终点即证明前置步骤都通得过。
2. 加一行 `assert "injected broken predicate" in res.stderr` 是纯增益，但这是 rev2
   已冻结 Brief 之外的新要求，**不能在验收阶段临时扩权**（那等于用返工绕过范围冻结）。
3. 记入 A35 的「后续加固」，随下一次触及该文件的 WP 一并做。

### 发现 2（成立，P2，注释方向写反了）：`&&`/`||` 的概括过宽且指错方向

`finalize_merge.sh` 的 A29 注释写「Never move it into an `if` condition or after
`&&`/`||`」。编排者实测三种位置（`set -euo pipefail`）：

| 形态 | rc | 语义 |
|------|:--:|------|
| `x=$(crash)`（现行） | 7 | **fail-closed** ✅ |
| `x=$(crash) && true`（赋值在 `&&` **左**） | 0 | **fail-open** ❌ |
| `true && x=$(crash)`（赋值在 `&&` **右**） | 7 | fail-closed ✅ |
| `x=$(crash) \|\| echo false`（赋值在 `\|\|` **左**） | 0 | **fail-open** ❌ |

**注释说的「after `&&`/`||`」恰好是安全的那一侧**（右操作数）；真正危险的是
**位于 `&&`/`||` 之前**（左操作数），因为那时赋值成为 AND/OR-list 的一部分，
`set -e` 对其被抑制。注释把方向说反了。

**额外实测（编排者主动扩测，超出 rev2 Brief 指定的两种变异）**：把赋值改成
`in_worktree=$(...) && true`（变异 D，左操作数形态），rev2 用例**变红**：

```
FAILED test_finalize_fails_closed_when_predicate_raises
  - AssertionError: (0, 'FINALIZE_OK merged_commit=565d01b...')
```

即 rev2 用例的区分力**超出**Brief 指定的两种变异，第三种 fail-open 形态也能抓住。
变异已还原，`finalize_merge.sh` 相对 `6995873` 仍为 0 行 diff，工作树干净。

**处置**：**采纳为 P2 文档修正项，不阻断 rev2**。注释方向写反属编排者 rev1 Brief
的遗留（那 6 行注释由 rev1 Brief 规定、rev1 已验收），不是执行者本轮的问题；
且注释写反**不影响**代码正确性（代码是安全形态），也不影响用例区分力（实测能抓住）。
修正随下一次触及该文件的 WP 一并做。

## 未获独立审核的部分（如实申报）

本次咨询没有正式裁定，因此以下问题**没有**独立审核者的答复：

1. rev2 是否整体可 ACCEPT（只有编排者自己的核验，无第二方签字）
2. 编排者提的问题 6：A31 / A35 / A26-补充 / B8 这一族「弱观测通道」缺陷
   是否指示**流程级防线缺失**——codex 的最后动作正是去读 A26 原始记录以判断
   「这三类误判是否确属同一流程根因」，**但没来得及输出结论**
3. codex 自述目标测试因只读 sandbox 无法创建临时文件、3.13/3.14 未装 pytest
   而未能复跑；它明确表示不把环境失败误判成代码失败

**对 WP-21 终态的影响**：本 WP 的 status 是 v2 schema，`state=APPROVED_FOR_MERGE`
及之后要求 `consult.decision == ACCEPT`（`validate_wp_status.py:479-491`）。
本次咨询未产出 ACCEPT，因此**不得**推进到 APPROVED_FOR_MERGE。需重跑咨询取得
正式裁定，或走 `_override_is_legal` 的合规 override 路径（须用户授权）。

## 采纳决定（编排者）

| codex 条目 | 处置 |
|-----------|------|
| 发现 1：负向用例未绑定失败来源 | **采纳为 P2**，记入 A35 后续加固；不阻断 rev2（正面对照已排除更早失败） |
| 发现 2：`&&`/`||` 概括过宽且方向写反 | **采纳为 P2**，记入 A29 注释修正；代码本身安全，用例实测能抓住第三种形态 |
| 「无 P0/P1 功能回归、能杀死两种变异」 | 与编排者独立核验一致，但**不作为裁定**引用 |
| 问题 6（弱观测通道是否流程级缺陷） | **未获答复**，仍待独立审核 |

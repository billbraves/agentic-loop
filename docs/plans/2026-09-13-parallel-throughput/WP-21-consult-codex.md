# WP-21 rev2 咨询记录（codex）

> 触发时间 2026-09-15 ｜ 提问者 claude（编排者）｜ 咨询者 codex（provider: kirogpt）
> 依 `CLAUDE.md`「record its question and recommendation in the iteration directory」落盘。
> 原始 prompt：`/Users/admin/.claude/jobs/8a8bf01e/tmp/wp21r2-consult-prompt.txt`
> 原始日志：`/Users/admin/.claude/jobs/8a8bf01e/tmp/wp21r2-consult.log`（332KB）

## 触发理由

WP-21 rev1 的 A29 characterization test 被编排者变异测试判定为**空验证**（缺陷 A35），
而该缺陷由编排者自己的 rev1 Brief 逐字规定的断言造成。rev2 是编排者对自己缺陷的返工，
**不能自审自过**，故请独立审核者复核 rev2 是否真正具备区分力。

## 结论：**ACCEPT**（第二轮取得，P0=0 / P1=0 / P2=3）

裁定文件：`WP-21-consult-codex-verdict.json`（结构化输出，非日志抓取）

第一轮咨询未产出裁定（详见下节「第一轮：进程异常终止」）。第二轮改用
`codex exec --output-schema <schema> -o <answer-file>` ——即 `adapters/codex.py:120-145`
本来就采用的形式——裁定落进只含信号的独立文件，通道问题根治（缺陷 B9 第 3 条防线）。
配合把提问收窄到「只读三处」，日志从 332KB 降到 19KB，未再中断。

**`[RATIONALE]`（原文）**：

> rev2 已具备实质区分力：status 是可成功 finalize 的真实 fixture，正面对照确认共同
> 前置条件可达 `FINALIZE_OK`，独立 probe 验证影子模块确实抛出目标异常，且三类代表性
> fail-open 变异均能使测试转红。当前未发现可让原实现与已知禁止变异同时通过的现实
> 空验证通道。负向运行未直接断言目标 `RuntimeError` 仍留下未来退化时的理论空过可能，
> 但结合当前 stderr 实测、probe 和变异证据，不构成当前正确性的阻断。
> `finalize_merge.sh` 的注释确有方向性错误：赋值位于 `&&`/`||` 左操作数会抑制 `set -e`
> 并可能 fail-open；位于右操作数通常仍是列表最后命令，失败会触发退出，属于 fail-closed。
> 该问题仅影响维护指导，未改变当前可执行行为。

### P2-1：负向运行未绑定失败来源

codex 补充了编排者没说透的一点：**正面对照只证明「无注入时共同路径可达终点」，
不能严格证明「带注入的负向运行必然死于目标 predicate」**；`probe` 断言也只独立
证明注入模块可用。若将来出现「注入环境特有的更早失败」，用例仍可能空过。

建议：加 `assert "injected broken predicate" in res.stderr`。维持 P2，
因当前实测该标记确实出现，且代表性变异均被捕获。

**编排者处置**：**采纳**，与编排者独立判断一致，记入 A35 后续加固。

### P2-2：`&&`/`||` 注释方向写反

codex 独立确认了编排者的实测结论，并把口径说得更准：危险的是「让赋值成为
AND/OR 列表中**非末尾**的左操作数」；放在右操作数且作为列表末尾命令时，
predicate 非零仍触发 `set -e`，属 fail-closed。

**编排者处置**：**采纳**，记入 A29 注释修正。

### P2-3：流程级缺口——评审验证了测试结果，没验证 oracle

> A31、A35 与 B8 共同暴露流程级缺口：评审验证了测试结果，却没有系统验证测试所用
> oracle 是否真正观察到目标事实。

建议的最小「oracle 校验」三项，纳入安全性/负向测试的 DoD：

1. 同 fixture 的**正向可达性对照**
2. 负向运行的**原因特异 witness**（异常标记、状态或精确事件）
3. 至少一个**代表性禁止变异必须使测试转红**

评审时记录这三项证据，避免仅凭通用非零 rc、输出 tail 或错误基线作结论。

**编排者处置**：**全部采纳**。这正是编排者提问 6 想要的答复，且比编排者自己在 B9 里
写的四条防线更可操作——B9 的表述是「否定式断言配正面对照」（只对应第 1 项），
codex 的第 2 项「原因特异 witness」是编排者漏掉的一环：正面对照证明的是**前置可达**，
witness 证明的是**失败归因**，两者不能互相替代。已回填进 B9。

### 一处形式偏差（记录备查，不影响裁定）

codex 输出的 `findings` 是**按 severity 分键的对象**（`{"P0":[],"P1":[],"P2":[…]}`），
而给定 schema 声明的是**数组**（每项含 `severity`/`summary`）。内容完整、分级清楚，
不影响采信；但说明 `--output-schema` 在本 provider 下是**软约束**，
消费方不能假定严格贴合。若日后由 `adapters/codex.py` 的 `_parse_verdict` 消费，
需确认它能容忍这种形状（否则会在解析处炸）。

---

## 第一轮：进程异常终止，未产出裁定

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

> 以上三项**已在第二轮全部获得答复**（问题 6 的答复即 P2-3）。
> 第一轮 codex 自述目标测试因只读 sandbox 无法创建临时文件、3.13/3.14 未装 pytest
> 而未能复跑；它明确表示不把环境失败误判成代码失败——这一点两轮一致，
> 故两轮的测试证据均来自编排者的三解释器实测。

## 采纳决定（编排者，汇总两轮）

| codex 条目 | 处置 |
|-----------|------|
| `[VERDICT] ACCEPT`（P0=0 / P1=0） | **采信**。与编排者独立核验一致，双方签字齐备 |
| P2-1：负向运行未绑定失败来源 | **采纳**，记入 A35 后续加固；不阻断 rev2 |
| P2-2：`&&`/`||` 注释方向写反 | **采纳**，记入 A29 注释修正；代码本身安全 |
| P2-3：oracle 校验三项进 DoD | **全部采纳**，回填进 B9；其中「原因特异 witness」是编排者漏掉的一环 |
| `findings` 形状偏离 schema | **记录备查**，不影响采信；提示 `--output-schema` 是软约束 |

## 对 WP-21 终态的影响（更新）

第一轮记录曾写「不得推进到 APPROVED_FOR_MERGE」——**该限制已解除**：
第二轮取得 `consult.decision = ACCEPT`，满足 `validate_wp_status.py:479-491`。

**但合并仍需用户明示批准**（`CLAUDE.md`：Do not merge or release without the
required user approval）。截至本记录写成，**未获任何用户批准，未合并**。

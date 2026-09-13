# WP-01: 门输出压成摘要行

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

把质量门的输出从「逐行 PLAN + 原始 pytest stdout」压成一行摘要 + 按需展开，
让并行 N 路时 agent 读门输出的 token 成本降一个数量级，且**判定结果一字不变**。

## 背景

并行度越高，门输出的噪音越是瓶颈：现在跑一次 `agentic quality-gate` 会吐
`QUALITY_GATE_PLAN:` 逐行加上 pytest 完整 stdout，5 路并行就是 5 倍。
lobehub 的 `.agents/scripts/check/report.ts` 是同一问题的成熟解法，其注释明确写
"compact and colorless so agents burn minimal tokens reading it"，可直接借鉴形态：

- 摘要行只提**实际跑了**的检查，没跑的不提；
- 失败才展开细节，成功只留计数；
- 大块内容（此处是完整 plan 与失败输出）写到文件里，只给路径。

## 范围

**allowed_paths**
- `src/agentic_loop/gate/`
- `tests/test_gate_report*.py`

**forbidden_paths**
- `.env`
- `.context/`
- `src/agentic_loop/wrappers/`（wrapper 的输出层改造属 WP-02 的连带范围，本 WP 不碰）
- 其余一切未在 allowed 列出的路径

> 注意：本 WP 与 WP-02 同属 `lane-gate`，**串行执行**，不得与 WP-02 并发。
> 两者都碰 `gate/`，并发会撞车。

## 输入

- 依赖的上游 WP 产出：无（本 WP 是 `lane-gate` 的头）
- 参考：`/tmp/lobehub_study/.agents/scripts/check/report.ts`（形态参考，非照抄；
  该仓是 TS，本仓是 Python，只借鉴「摘要行 + 按需展开 + 大块落文件」三条原则）
- 现状代码：`src/agentic_loop/gate/__init__.py` 的 `gate_log` / `gate_warn`

## 交付物清单

1. `src/agentic_loop/gate/` 下的报告层函数：接收结构化的门结果，输出摘要行。
   摘要行形态（参考，实现可微调）：
   `✓ 12 files · scope clean · tests 34 passed` / `✗ 12 files · scope 1 violation · tests failed`
2. 完整 plan 与失败详情写入文件，摘要行给出路径。
3. `tests/test_gate_report*.py`：characterization test（见 DoD）+ 新行为测试。

## 完成定义（DoD）

- [ ] **characterization test 先行**：改造前先固化现有门的**判定结果**
      （PASS/FAIL 字符串与退出码），证明压缩输出后判定完全未变。
      这是本 WP 最硬的一条——输出层重构绝不允许改变任何判定。
- [ ] 摘要行只包含实际执行的检查项，未执行的不出现
- [ ] 成功路径不输出任何逐条明细
- [ ] 失败路径给出足以定位的信息（文件:行 / 命令 / 退出码）
- [ ] 大块内容落文件并在摘要行给出路径
- [ ] `python3 -m pytest tests -q` 全绿
- [ ] 无 forbidden_paths 写入
- [ ] 无生产 DB 写入、无网络、无推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **`gate_log` / `gate_warn` 可能有其他调用方。** 改签名前先
   `grep -rn "gate_log\|gate_warn" src/ tests/` 确认全部调用点，别只改定义。
2. **退出码是契约的一部分。** `quality-gate.sh` 的调用方依赖 rc 0/2/64 以及
   pytest 的 rc 4/5 跳过语义。压缩输出不得触碰任何退出码路径。
3. **不要顺手改判定逻辑。** 看到 fail-closed 分支觉得可以简化时，记下来，
   写进执行报告的 `[CONCERNS]`，不在本 WP 动手。
4. **本仓 Python 兼容 >= 3.9**，不要用 3.10+ 的语法（`match`、`X | Y` 类型注解
   在运行时求值的位置）。现有代码用 `from __future__ import annotations` 规避，
   跟随现有写法。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3 -m pytest tests -q` 全量绿（`.agentic/config.toml` 的
`[[quality_gate.rule]]` 对 `src/agentic_loop/**` 与 `tests/**` 均触发全量）。
各 WP 特有的 characterization / 反向测试要求见上文 DoD。

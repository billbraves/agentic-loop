# WP-09: 让 `agentic init` 出来的默认配置过得了自己的门

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

修掉 `agentic init` 默认配置在两个独立维度上的开箱即坏（gate 形式读不到 / 门限
永久拒绝），并把编排者本轮已手工做过的 `.agentic/config.toml` 迁移正式纳入一个
WP 的 scope。

## 背景

缺陷 A1 与 A3（`WP-08-candidate.md` §A1 §A3）。两者同在 `init_cmd.py` 的同一段
配置模板里，同属「默认配置过不了自己的门」，合成一个 WP。

**A1 —— gate 形式读不到。** `init_cmd.py:55-59` 吐的示例是

```toml
[quality_gate]
# [[quality_gate.rule]]
# match = "src/**"
# run   = ["<your test command>"]
```

而 `resolve_paths.get_gates()`（`resolve_paths.py:253-270`）只读统一的
`[[gate]]` 数组，且 fail-closed 地丢掉 `kind`/`stage` 不在合法枚举内的条目；
`quality-gate.sh` 经它取规则。`docs/QUICKSTART.zh-CN.md:209` 确认 `[[gate]]`
（`kind="command"`, `stage="pre_review"`）是正式形式。
照 init 模板填规则的结果是
`QUALITY_GATE_FAIL: [[gate]] (kind=command, stage=pre_review) is absent or
defines no rules`——新用户第一次跑门就撞墙，且错误信息不提示「你写的是旧形式」。

**A3 —— 默认门限与默认 roles 自相矛盾。** 同一份模板：
`init_cmd.py:38-53` 把 `identity_model = "deepseek-v4-pro"` 声明为「独立性评级
唯一依据」并让 developer/reviewer/consultant 三签全绑该 provider；
第 65-66 行却写 `min_independence = "strong"`。而 `independence.evaluate()` 的
strong 要求两个 engine-observed model id **不同**——三签同 id 最高只能评到 weak。
于是默认配置的合并门永久拒绝。

本仓 `.agentic/config.toml:56-59` 已经手写了这条警告并把门限降到 `weak`
（「若这里留 strong，合并门会永久拒绝——不是框架有 bug，是配置自相矛盾」），
说明踩过；但 init 模板没跟上，下一个新项目照样撞。

**编排者的既有改动。** 本轮编排者已在主区把 `.agentic/config.toml` 从
`[[quality_gate.rule]]` 迁到 `[[gate]]` / `[[gate.rule]]`，并把测试命令从
`python3` 改成 `python3.11`（本机 `python3` 是 3.14 且没装 pytest）。
用户 2026-09-13 裁定把该改动正式纳入本 WP 的 scope，所以 `.agentic/config.toml`
在 allowed_paths 里。

> **⚠️ 交接注意（读到这里先看清两件事）**
>
> **(1) 迁移已由编排者提交。** 该改动已随本 WP 的冻结提交进入
> `plan/2026-09-13-parallel-throughput`，所以你的 worktree 里拿到的
> `.agentic/config.toml` **已经是迁移后的版本**。交付物第 4 项因此降级为
> **核对**而非重做：确认内容与该项描述一致即可，不要重新迁移一遍。
> 若发现不一致，以第 4 项的描述为准并在报告里说明差异。
>
> **(2) 改这个文件不会影响门自己的行为——这是个反直觉的陷阱。**
> `resolve_paths.get_gates()` 读的是 `main_repo()/.agentic/config.toml`，即
> **主区的文件系统副本（含未提交改动）**，不是你 worktree 里的那一份，也不是
> 任何已提交版本。实测：从副 worktree 调 `get_gates()` 拿到的是主区当前内容。
> 所以你在 worktree 里改 `.agentic/config.toml` 后，`agentic quality-gate`
> **仍然按主区那份跑**——你看不到自己的改动生效。DoD 里「实跑 quality-gate 确认
> 规则被正确读到」这一条，验的是主区那份仍然可用，不是你的改动。
> 想验证自己的改动，就直接对文件内容做断言（测试里读文件、解析 TOML），
> 不要靠跑门来验。**这一点本身就是个候选缺陷**（配置的事实源与 WP 隔离边界
> 不一致）；发现别的相关表现请写进 `[CONCERNS]`，不要顺手改 `resolve_paths`
> 的根解析逻辑（那是 INV-4，牵连面远超本 WP）。

## 范围

**allowed_paths**
- `src/agentic_loop/init_cmd.py`
- `src/agentic_loop/resolve_paths.py`
- `.agentic/config.toml`
- `tests/test_init_gate_form.py`

**forbidden_paths**
- `.env`
- `.context/`
- `src/agentic_loop/independence.py`（A0 的修复属 WP-08，本 WP 不碰评级逻辑）
- `src/agentic_loop/gate/`
- `src/agentic_loop/wrappers/`
- `src/agentic_loop/templates/STATUS.json.tmpl`（属 WP-10 / WP-14）
- 其余一切未在 allowed 列出的路径

## 输入

- 依赖的上游 WP 产出：无（`lane-config` 独占一条 lane，与任何既有 lane 不重叠）
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §A1 §A3
- 现状代码：`init_cmd.py:35-70`（配置模板全段）；
  `resolve_paths.py:245-275`（`get_gates` 与枚举 fail-closed）；
  `.agentic/config.toml:56-59`（本仓已手写的 A3 警告，可作注释措辞参考）
- 正式形式的权威说明：`docs/QUICKSTART.zh-CN.md:209`

## 交付物清单

**A1 —— init 吐正式形式**

1. `init_cmd.py` 的配置模板改吐 `[[gate]]` / `[[gate.rule]]`，
   带 `kind = "command"` 与 `stage = "pre_review"`，示例仍保持注释状态
   （init 出来的配置不该自带一条会跑的规则）。
2. `resolve_paths.py` 对残留的 `[[quality_gate.rule]]` 给一条明确的**迁移提示**，
   而不是当作「没有规则」静默通过到 fail-closed。
   > 提示的投递方式由你判断：`get_gates()` 是纯读取函数，往里塞 print 会污染
   > 所有调用方。可选做法包括让它额外暴露一个「检测到旧形式」的查询函数，
   > 由 wrapper 的错误路径去调用并附加提示。**约束**：`get_gates()` 本身的
   > 返回值语义与 fail-closed 行为一字不改；提示只能是**附加**信息。
   > 若你判断在不改 `get_gates()` 签名的前提下无法干净实现，只做第 1 项，
   > 并把方案写进 `[CONCERNS]`——A1 的硬要求是第 1 项。

**A3 —— 默认门限自洽**

3. `init_cmd.py` 的 `min_independence` 默认值与默认 roles 绑定保持自洽：
   默认三签同 provider，所以默认值应吐 `weak`，并在注释里写明
   「若改成 `strong`，必须先把三签拆到不同 `identity_model`，否则合并门永久拒绝」。
   措辞可参考本仓 `.agentic/config.toml:56-59` 已有的那段。
   **不是**「把警告写进注释就算了」——默认值本身必须自洽。

**本仓 config 迁移**

4. **核对**（非重做）`.agentic/config.toml` 已迁到 `[[gate]]` / `[[gate.rule]]`：
   两条规则（`src/agentic_loop/**` 与 `tests/**`）的 `run` 是
   `python3.11 -m pytest tests -q`；注释里保留了三个要点——规则「首条命中者胜」、
   `AGENTIC_PYTHON` 管不到 `rule.run` 里的命令、以及为什么命令写 `python3.11`。
   一致就在报告里记一句「已核对，无需改动」；不一致才动手，并说明差异。
   > 见上文交接注意 (1)：迁移已由编排者提交，你拿到的就是迁移后的版本。

## 完成定义（DoD）

- [ ] **正向测试（本 WP 最硬的一条）**：`agentic init` 到一个临时目录，
      把生成的 `.agentic/config.toml` 喂给 `resolve_paths.get_gates()`，
      断言能读到 `[[gate]]` 结构（示例规则注释掉时读到的是「有 gate 无 rule」，
      取消注释后读到规则）——即**证明 init 的产物与引擎的读取口径一致**。
      这条把 A1 从「靠人记得」变成机器可验。
- [ ] 正向测试：`agentic init` 生成的 `min_independence` 与默认 roles 自洽——
      断言默认值不是 `strong`（或：若三签 identity_model 相同则断言不是 `strong`）
- [ ] 反向测试：一份只有 `[[quality_gate.rule]]` 的旧配置 → `get_gates()` 仍返回
      `[]`（fail-closed 行为不变），且**能拿到迁移提示**（若做了第 2 项）
- [ ] 反向测试：`kind` 或 `stage` 为非法枚举值的 `[[gate]]` 条目仍被丢弃
      （证明没有顺手放宽枚举校验）
- [ ] `.agentic/config.toml` 已核对为 `[[gate]]` 形式：**用读文件 + 解析 TOML 的断言**
      验证，不要靠跑 `agentic quality-gate` 验（见交接注意 (2)：门读主区那份，
      看不到你 worktree 里的改动）。另跑一次 quality-gate 只为确认主区那份仍可用
      （不报 `[[gate]] ... is absent or defines no rules`）
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
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

1. **`.agentic/config.toml` 是本仓质量门的事实源，而门读的是主区那一份。**
   所以两件事同时成立：(a) 你在 worktree 里改它，门不会按你的版本跑
   （交接注意 (2)）；(b) 这份文件一旦真的写坏，**所有** WP 的验收都会失去意义。
   因此第 4 项定为「核对」——除非发现真实不一致，否则不要动它。
2. **不要动 `min_independence` 以外的 `[review_policy]` 语义，
   更不要碰 `independence.py`。** A0（双签独立性死锁）是 WP-08 的范围。
   本 WP 只让 **init 模板的默认值**自洽；**本仓已有的 `weak` 不要改**。
3. `resolve_paths.get_gates()` 的 fail-closed 是刻意的（非法枚举直接丢弃，
   绝不猜一个合法值）。加迁移提示不得削弱这一点。
4. `init_cmd.py` 的模板是给**新项目**用的。改它时想清楚「新项目开箱应该是什么样」，
   不要把本仓的特殊情况（`python3.11`）写进通用模板——那是本仓 config 的事，
   通用模板里该是占位符。
5. **本仓 Python 兼容 >= 3.9**，跟随现有 `from __future__ import annotations` 写法。
6. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
   跑全量测试时**不要设** `AGENTIC_PYTHON`（见 §B3，会打穿测试自带的 `python3` stub
   制造假失败）。
7. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的正向 / 反向测试要求见上文 DoD。

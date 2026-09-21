# WP-03: plan 加依赖图与 lane，算就绪集

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

让 plan 文件能表达「谁等谁」和「谁归哪条 lane」，并提供
`agentic plan lanes <plan.status.json>` 算出此刻可立即并行开工的 WP 集合——
把并行判断从人脑挪进机器。

## 背景

`plan_cmd.py` 的模块 docstring 写着「Sequential WPs work on that one branch; only
parallel lanes that genuinely need concurrent execution get separate branches」。
默认路径是串行，并行需人工声明。但 `work_packages` 只是个字符串列表
（`PLAN.json.tmpl`），没有任何字段能表达依赖或 lane 归属，所以没有东西能告诉
编排者「WP-03 和 WP-05 无依赖、可同开」。人脑每次重新判断，一累就默认串行。

这是本迭代的**地基 WP**：WP-05（分批收敛）和 WP-06（worktree 隔离）都依赖
lane 概念存在。

## 范围

**allowed_paths**
- `src/agentic_loop/plan_cmd.py`
- `src/agentic_loop/templates/PLAN.json.tmpl`
- `tests/test_plan*.py`

**forbidden_paths**
- `.env`
- `.context/`
- `src/agentic_loop/wrappers/`
- 其余一切未在 allowed 列出的路径

> 注意：本 WP 与 WP-05 同属 `lane-plan`，**串行执行**，不得与 WP-05 并发。
> 两者都改 `plan_cmd.py`。本 WP 可与 WP-01 并行（不同 lane，scope 无交集）。

## 输入

- 依赖的上游 WP 产出：无（本 WP 是 `lane-plan` 的头，也是整个迭代的地基）
- 依赖关系的权威声明：`PLAN.md` §5 的依赖图
- 现状代码：`plan_cmd.py` 第 76–82 行 `REQUIRED_TOP_LEVEL`、
  第 151–155 行 `work_packages` 校验、第 252 行 `_status_git_paths`、
  第 417 行 `cmd_check`

## 交付物清单

1. **schema 升级，双形兼容。** `work_packages` 同时接受两种形态：
   - 旧：`["WP-01", "WP-02"]`（纯字符串，必须继续通过校验）
   - 新：`[{"id": "WP-01", "lane": "lane-gate", "depends_on": []}, ...]`
   `lane` 与 `depends_on` 均可选；缺省时 `lane` 归入默认 lane、`depends_on` 为空。
2. **`agentic plan lanes <plan.status.json>`**：读 plan + 各 WP 的实际 state，
   输出三类分组——
   - `READY`：依赖全部 MERGED（或无依赖）且自身未完成 → 可立即开工
   - `BLOCKED`：有依赖未完成 → 列出在等谁
   - `DONE`：自身已 MERGED
   同 lane 内即使都 READY 也只能取一个（同 lane 串行是 lane 的定义）——
   输出需体现这一点。
3. **拓扑校验**：依赖成环、`depends_on` 指向不存在的 WP、跨 lane 依赖形成的
   死锁，都要在 `plan check` 与 `plan lanes` 里报错而非静默。
4. `tests/test_plan*.py`：见 DoD。

## 完成定义（DoD）

- [ ] **旧格式 plan 文件校验不回归**：现有 `tests/test_plan.py` 全部继续通过，
      一个都不许改断言来「适配」新 schema。这是双形兼容的证明。
- [ ] 新格式 plan 文件校验通过，`lane`/`depends_on` 缺省有明确默认值
- [ ] `plan lanes` 的就绪计算是**纯函数**：无 IO、无隐式 `now()`，
      WP 状态从参数传入（全局规范 §5.8）
- [ ] 成环检测有反向测试（构造环，断言报错）
- [ ] `depends_on` 指向不存在 WP 有反向测试
- [ ] 三处消费点（`validate` / `_status_git_paths` / `cmd_check`）全部适配双形，
      漏改任一处旧文件会炸——需有测试覆盖每一处
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

1. **`validate()` 对未知顶层字段是硬拒绝的**（第 118–120 行
   `unknown top-level fields`）。若打算加顶层 `lanes` 字段，必须同时把它加进
   `OPTIONAL_TOP_LEVEL`，否则所有新格式文件全部校验失败。
   本 WP 的设计是把 lane 放在 `work_packages` 的元素里，不加顶层字段——
   如果你认为顶层更合适，先在报告里提出，不要自行改设计。
2. **`_status_git_paths` 第 252 行直接 `for wp_id in data.get("work_packages", [])`**，
   对象数组下 `wp_id` 会变成 dict，后续 `_candidate_paths(rel_iter, wp_id)` 会静默
   拼出错误路径而不报错——这是最容易漏的一处。
3. **`cmd_check` 第 417 行同理**。
4. **PLAN.json.tmpl 是 `agentic init` 的产物模板**，改它会影响所有新项目脚手架。
   保持默认渲染出的是**旧格式**（纯字符串数组），新格式作为可选升级，
   不强制存量项目迁移。
5. **本仓 Python 兼容 >= 3.9**，跟随现有 `from __future__ import annotations` 写法。
6. **不要在本 WP 里实现分批收敛**。lane 概念落地即止，`plan merge --lane` 是
   WP-05 的事。越界实现会和 WP-05 撞车。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3 -m pytest tests -q` 全量绿（`.agentic/config.toml` 的
`[[quality_gate.rule]]` 对 `src/agentic_loop/**` 与 `tests/**` 均触发全量）。
各 WP 特有的 characterization / 反向测试要求见上文 DoD。

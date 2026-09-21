# WP-10: 状态模板默认值改成可派发状态

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

让「照模板冻结一个 WP」直接产出可派发的状态文件，不必再补一次
`DRAFT→APPROVED` 提交——那次提交会撞上「状态文件只允许提交两次」的纪律。

## 背景

缺陷 A2（`WP-08-candidate.md` §A2）。三方证据锁死了一个无出路的三角：

- `src/agentic_loop/templates/STATUS.json.tmpl:7` 与其 scaffold 副本
  `docs/agentic/templates/STATUS.json:7` 都是 `"state": "DRAFT"`（两份内容当前逐字节相同，
  由 `init_cmd.py:108` 的 `("STATUS.json.tmpl", "docs/agentic/templates/STATUS.json", 0o644)` 拷贝）。
- `preflight.sh:56-67` 的可执行状态集是
  `APPROVED|DISPATCHED|IMPLEMENTING|CHANGES_REQUESTED`——`DRAFT` 不在其中。
- preflight 读的是**副 worktree 已提交的副本**（见 §C3），所以「主区工作区里改成
  APPROVED」不算，必须提交。

于是照模板走的路径是：freeze 提交（DRAFT）→ preflight 报
`state DRAFT is not executable` → 补一个 DRAFT→APPROVED 提交 → 那是状态文件的
第三次提交 → `agentic plan lint` 判 DIRTY（只允许 freeze + finalize 两次）。
本轮实测被迫用 `git commit --amend` 把冻结提交本身改成 `APPROVED` 才走通，
即：**框架的默认模板走不通框架自己的纪律。**

`validate_wp_status.py:458` 的 `active_states = STATES - {"DRAFT", "APPROVED"}`
说明 `APPROVED` 与 `DRAFT` 同属「不要求 base_commit / branch / worktree / executor」
的宽松档，所以把默认值改成 `APPROVED` 不会让模板本身变成非法状态文件。

## 范围

**allowed_paths**
- `src/agentic_loop/templates/STATUS.json.tmpl`
- `docs/agentic/templates/STATUS.json`
- `tests/test_init_contract.py`
- `tests/test_status_template_dispatchable.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`
- `src/agentic_loop/validate_wp_status.py`（**尤其禁止**：不得改状态集或
  `active_states` 来"解决"，本 WP 只动模板默认值）
- `src/agentic_loop/wrappers/`（不得改 preflight 的可执行状态集）
- `src/agentic_loop/plan_cmd.py`（不得放宽 `plan lint` 的两次提交纪律）
- 其余一切未在 allowed 列出的路径

## 输入

- 依赖的上游 WP 产出：无（本 WP 是 `lane-template` 的头）
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §A2
- 现状代码：上述两个模板文件；`init_cmd.py:103-111` 的 scaffold 映射；
  `validate_wp_status.py:458`；`preflight.sh:56-67`

## 交付物清单

1. 两个模板的 `state` 默认值从 `"DRAFT"` 改为 `"APPROVED"`。
   **两份都要改**，且改完必须仍逐字节相同（`init_cmd.py` 是直接拷贝，
   两份分叉会让 scaffold 出来的东西与包内模板不一致）。
2. 模板里就地加一条注释性说明，讲明为什么默认不是 `DRAFT`。
   > JSON 不支持注释。用一个显式字段承载，例如在文件里加
   > `"_note"` 之类的说明键，或者写进同目录的 `WORK_PACKAGE.md` /
   > `docs/agentic/OPERATING_MODEL.md`。**选哪种由你判断**，但必须先确认
   > `validate_wp_status.py` 不会因为多出的键报 STATUS_INVALID
   > （跑一次校验器验证，不要只读代码推断）。若加键会被拒，就只改默认值 +
   > 写文档，并在 `[CONCERNS]` 说明。
3. `tests/test_init_contract.py` 的两处断言随之更新：
   `test_init_scaffolds_reference_templates` 第 70 行断言
   `data["state"] == "DRAFT"`，须改为 `"APPROVED"`。
   **注意同一函数里第 83 行的 `assert data["state"] == "DRAFT"` 属于
   `test_init_scaffolds_plan_template`，那是 PLAN 模板（`PLAN.json.tmpl:5`），
   计划级状态机是 `DRAFT -> ACTIVE -> READY_TO_MERGE -> MERGED`，与本 WP 无关，
   不要改。** 只改 WP status 那一处。
4. `tests/test_status_template_dispatchable.py`：见 DoD。

## 完成定义（DoD）

- [ ] **正向测试（本 WP 最硬的一条）**：把包内模板原封不动喂给
      `validate_wp_status.py`，断言 STATUS_VALID；再断言其 `state` 落在
      `preflight.sh` 的可执行状态集内。
      这条测试的意义是把「模板必须可直接派发」变成机器可验的契约，
      而不是又一次靠人记得。可执行状态集来自 shell 脚本，
      测试里可以硬编码这四个状态并在注释里指明来源行号（`preflight.sh:56-67`），
      也可以从脚本里 grep 出来——**优先后者**，硬编码会再次漂移。
- [ ] 反向测试：`DRAFT` 状态的 status 文件仍然被 preflight 判为不可执行
      （证明本 WP 没有顺手放宽状态集）
- [ ] 两份模板改完逐字节相同（测试里断言，或至少在报告里给出 `diff` 结果）
- [ ] `tests/test_init_contract.py` 的 PLAN 模板断言未被改动
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

1. **不要改 `validate_wp_status.py` 的 `STATES` 或 `active_states`。**
   A2 的修法有两个方向（改模板默认值 / 在 lint 侧放行一次
   `DRAFT→APPROVED` 转换提交），本 WP 冻结的是**前者**。
   若你认为后者更好，写进 `[CONCERNS]`，不要动手。
2. **`DRAFT` 这个状态本身要保留。** 它对「还在规划、尚未冻结」的 WP 有意义，
   本 WP 只改模板的默认起点，不是废除该状态。
3. 两份模板由 `init_cmd.py` 拷贝而非生成，别只改一份。
4. **本仓 Python 兼容 >= 3.9**，跟随现有 `from __future__ import annotations` 写法。
5. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
   注意 `AGENTIC_PYTHON` 只影响 wrapper 自身调用，且跑全量测试时**不要设置**
   （见 §B3，它会打穿 `test_init_githooks.py` 自带的 `python3` stub 制造假失败）。
6. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的正向/反向测试要求见上文 DoD。

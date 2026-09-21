# WP-14: 把 `evidence.tests` 的结构要求写到人能看见的地方

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

让填 status 的人在**填之前**就知道 `evidence.tests` 每条必须是带 `exit_code` 的对象，
而不是提交后被校验器打回来才知道。

## 背景

缺陷 C2（`WP-08-candidate.md` §C2）。`validate_wp_status.py:471-476` 的实际要求是：

```python
tests = data.get("evidence", {}).get("tests")
if not isinstance(tests, list) or not tests:
    fail(errors, f"evidence.tests must not be empty in state {state}")
elif any(not isinstance(item, dict) or item.get("exit_code") is None for item in tests):
    fail(errors, "each evidence.tests entry requires an exit_code")
```

而模板里 `evidence` 只有一个空数组 `{"tests": []}`，**没有任何形状线索**。
本轮编排者先写成字符串列表，撞了
`STATUS_INVALID: each evidence.tests entry requires an exit_code` 才知道。

**准确口径（写文档时不要写错）**：校验器硬性要求的只有两条——
每条是 `dict`、且 `exit_code` 不为 `None`；而且这个检查**只在**
`state ∈ {READY_FOR_REVIEW, APPROVED_FOR_MERGE, MERGED, RELEASED}` 时触发。
`name` / `command` / `note` 是本仓实际使用的惯例字段，**不是校验器要求**。
文档要把「硬性要求」与「惯例」分开讲，不要把惯例说成必填，
否则下一个读者会以为少写 `note` 会被拒。

这是 C 类（契约与模板不一致）而非 A 类：它不会让默认配置跑不起来，
只是把一条只存在于校验器里的规则留给每个人各撞一次。

## 范围

**allowed_paths**
- `src/agentic_loop/templates/STATUS.json.tmpl`
- `docs/agentic/templates/STATUS.json`
- `docs/QUICKSTART.zh-CN.md`
- `tests/test_status_template_evidence_shape.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`
- `src/agentic_loop/validate_wp_status.py`（**尤其禁止**：本 WP 是纯文档/模板，
  不得放宽或改动校验规则）
- `src/agentic_loop/wrappers/`
- 其余一切未在 allowed 列出的路径

> 本 WP 属 `lane-template`，排在 WP-10 之后**串行**：两者同碰
> `STATUS.json.tmpl` 与 `docs/agentic/templates/STATUS.json`，并发必撞。
> 不得与 WP-10 并发。

## 输入

- 依赖的上游 WP 产出：**WP-10 必须先 MERGED**（同碰两个模板文件）。
  注意 WP-10 会把模板的 `state` 默认值从 `DRAFT` 改成 `APPROVED`，
  你拿到的模板已经是改过的版本，不要回退它。
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §C2
- 现状代码：`validate_wp_status.py:468-476`（真实要求与触发条件）
- 现状文档：`docs/QUICKSTART.zh-CN.md:317` 已提到终态需要 `evidence.tests`，
  但没讲结构——这是最自然的落点

## 交付物清单

1. 两个模板的 `evidence` 块给出一条**形状示例**，含 `name`/`command`/`exit_code`/`note`
   四个字段，并让读者看出 `exit_code` 是硬性要求、其余是惯例。
   > JSON 不支持注释，且 `evidence.tests` 非空会在终态被校验。
   > 所以「示例」怎么放需要你判断：可以放一条示例条目并在同目录文档里说明，
   > 也可以用一个显式说明键承载。**两个约束必须同时满足**：
   > (a) 模板本身喂给 `validate_wp_status.py` 仍是 STATUS_VALID；
   > (b) 照模板填的人不会把示例条目当成真实证据交上去。
   > 先跑一次校验器验证，不要只读代码推断。若两个约束无法同时满足，
   > 就只改文档（第 3 项），并在 `[CONCERNS]` 说明理由。
2. 两份模板改完必须逐字节相同（`init_cmd.py:108` 是直接拷贝，分叉会让
   scaffold 出来的东西与包内模板不一致）。
3. `docs/QUICKSTART.zh-CN.md` 在现有第 317 行附近补上结构说明：
   每条是对象、`exit_code` 必填、只在终态校验、`name`/`command`/`note` 是惯例。
4. `tests/test_status_template_evidence_shape.py`：见 DoD。

## 完成定义（DoD）

- [ ] **正向测试**：包内模板原封不动喂给 `validate_wp_status.py` → STATUS_VALID
      （与 WP-10 的同名要求一致；本 WP 改了 evidence 块，必须重新证明这条仍成立）
- [ ] **反向测试（本 WP 的硬要求）**：一个 `state=READY_FOR_REVIEW` 且
      `evidence.tests` 为字符串列表的 status → 断言 STATUS_INVALID 且报错含
      `requires an exit_code`。这条把 C2 踩到的那个坑变成机器可验的回归护栏，
      免得下次有人「简化」模板时又把形状线索删掉。
- [ ] 反向测试：`evidence.tests` 为空列表且 `state=READY_FOR_REVIEW` → STATUS_INVALID
      （证明没有因为往模板里塞示例而放宽非空要求）
- [ ] 两份模板逐字节相同（测试里断言，或至少在报告里给出 `diff` 结果）
- [ ] 未改动 `validate_wp_status.py`
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

1. **不要把校验规则改松。** C2 的问题是「规则没写在人看得见的地方」，
   不是「规则太严」。`exit_code` 必填是对的——没有退出码的测试证据等于没有证据。
2. **不要把示例写成看起来像真证据的东西。** 模板里的示例若长得像一条真实测试记录，
   下一个人会连同示例一起提交，那比没有示例更糟。用明显的占位措辞。
3. 两份模板由 `init_cmd.py` 拷贝而非生成，别只改一份。
4. 本 WP 是纯文档/模板改动，**不应该产生任何行为变化**。
   若你发现必须改代码才能达成目标，停手并在 `[CONCERNS]` 说明。
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

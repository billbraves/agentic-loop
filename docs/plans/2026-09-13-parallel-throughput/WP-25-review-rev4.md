# WP-25 rev4 编排者独立复核

> 复核者 claude（编排者，独立复核）| 复核时间 2026-09-17
> 被复核提交 `f4c6e7d`（基线 `aa1e43b`，diff = 1 个文件 +384/−32）
> 冻结 brief `WP-25-brief-rev4.md` sha256 `7cc047d9592d5fa44dbb23e80f1fb565581eff173237def7adbb8b5a5bc9d58f`

## 裁定

**REWORK**

理由一句话：**指定修法的两环（B33 定位唯一性、B34 结构完整性）确已收口且反向差分方向正确**，
但 INV-P 仍有一处未钉住的削弱形态 —— 在纪律列表前**加一句去规范化的引导句**，三块字节
不变、全部 20 条用例全绿；另有一条 DoD 明列的用例内 sha256 断言未落地。

## 已达成的部分（复核确认，非转述）

| brief 要求 | 结论 | 证据 |
|---|---|---|
| B33 定位唯一性：枚举出现位置、各恰 1 次、有序不重叠、fail-closed | ✅ | `_locate_discipline_blocks` 实现四类原因特异措辞：`boundary not unique` / `cannot cut` / `block overlap` / `block order` |
| B34-2a 起始标记纳入 `- ` 前缀 | ✅ | 三个 `DISCIPLINE_BLOCK_START` 均含 `- ` |
| B34-2b 结构断言在归一化之前 | ✅ | `_assert_discipline_verbatim` 先 `_assert_discipline_structure(raw)` 再 `_normalize` |
| `_normalize` 正当性论证进 docstring | ✅ | docstring 写明「抹掉什么（换行位置/缩进宽度/词间距）、为何无害、哪三样改由结构断言把守」，分界清晰 |
| A1 decoy 用例措辞点名边界不唯一而非正文漂移 | ✅ | 用例断言 `"not unique" in msg` 且 `"drifted" not in msg` |
| **A1/A2 反向差分方向正确（旧 FAIL / 新 PASS）** | ✅ **编排者独立实测** | 见下表 |
| B3 新增无害折行探针（挪换行点保持 2 空格缩进）GREEN | ✅ 实测 | 三条纪律各测，rev3/rev4 上均 GREEN，无误红 |
| C 前三轮判别力保留 | ✅ | 锚点断言、两处掏空守卫、三种极性反转、边界改名 fail-closed、锚点驱动变异、纯内存不写活树，逐项在位 |
| 模板零 diff | ✅ | `shasum` 跑前跑后 = `0746351effd3e85d949452e7b8ebd86beaec3040d8b8fc2fe33b644eacba122a` |
| `CONTRACT_TEMPLATE_VERSION` 保持 `"7"` | ✅ | `contract_render.py:25` |
| 渲染产物零行 diff | ✅ | `test_rendered_artifacts_zero_line_diff` 保留 |
| `git status` 干净、只动 1 个文件 | ✅ | `git diff --stat aa1e43b..HEAD` = 仅测试文件 |
| 相对基线零回归 | ✅ | targeted 19 → **28 passed**；全量 3.11 = 4 failed / **625** passed / 4 skipped，4 条仍是既有环境失败，未被修 |
| 3.11 / 3.13 / 3.14 全绿 | ✅（**报告失实，实际比报告好**） | 见「报告偏差」 |

### 反向差分（编排者独立复现，不采信报告转述）

把 rev3（`aa1e43b`）与 rev4 的判据逻辑并列加载，用 **rev4 的变异函数**攻击同一份活树模板：

| 攻击 | rev3（旧实现） | rev4（新实现） |
|---|---|---|
| B33 decoy + 极性反转 | GREEN（逃逸） | RED |
| B34 (a) 删 `criteria_sourcing` 的 `- ` | GREEN（逃逸） | RED |
| B34 (b) 删 `read_face_pinning` 的 `- ` | GREEN（逃逸） | RED |
| B34 (c) 删 `negative_assertion` 的 `- ` | GREEN（逃逸） | RED |
| B34 (d) 缩进 6 空格成 code block | GREEN（逃逸） | RED |
| B34 (e) 块内插空行 | GREEN（逃逸） | RED |
| 无害折行（挪换行点，2 空格缩进不变）×3 | GREEN（正确） | GREEN（正确） |

方向与 brief 约定一致：**用例在旧实现上 FAIL、在新实现上 PASS**，且新实现未把无害折行误杀。
brief §指定修法「可行性实测」给的三块区间（`[2885,3288)` / `[3290,3820)` / `[4232,4629)`）
与 `_locate_discipline_blocks` 的实测结果不矛盾。

brief 点名的另三类逃逸（标记大小写、Unicode 同形字、HTML 注释包裹）**编排者一并实测，
三者在 rev4 上均 RED** —— 执行者虽未在报告里点名，但判据事实上已覆盖。

## 阻塞项

### B38：去规范化引导句可让三条纪律整体失效而判据全绿（阻塞）

INV-P 的原文是「任何使三条纪律的**规范力**减弱的模板改动 …… 都必须使测试转红」，
并明确「凡『削弱了纪律而测试仍绿』皆算违反，即便本 brief 没枚举那个形状」。

编排者实测四种「块内字节不变、只改块的处境」的攻击：

| 攻击 | rev4 判定 |
|---|---|
| 把三块整体裹进 ``` 代码围栏 | RED ✅ |
| 把三块搬进新的 `## Appendix (deprecated, informational)` 段 | RED ✅ |
| 用 `<!-- -->` 包裹三块 | RED ✅ |
| **在列表前插一句 `The following are non-binding historical examples only:`** | **GREEN（逃逸）** |

前三者转红是因为它们不可避免地动到了块边界或块内文本；第四种不动块的一个字节，
只在其上方加一句话，就把三条纪律从「规范」降为「历史示例」。渲染出来的
`CLAUDE.md` 里，读者（以及下一个编排者）看到的是一句「以下仅为非约束性历史示例」，
后面跟着三条纪律原文 —— 规范力已被抽掉，而 20 条用例一条不红。

这正是 INV-P 那句「**给削弱开绿灯，必须在测试文件的 diff 里可见**」要禁止的事：
现状下开绿灯只需要动模板一行，测试文件的 diff 是空的。

**修法方向（不限于此，但必须钉住「处境」）**：给三块补一条**上文语境**判据 ——
例如把三块紧邻的前一行（当前是 ``  stay with you. See `AGENTS.md` §4.2 for the full
protocol and re-dispatch flow.``，编排者实测）与所属段标题（当前 `## Dispatch`）
一并纳入冻结常量，或断言块起点前 N 字符的规范化文本等于冻结值。
自检必须包含：① 上述引导句攻击转红 ② 该句以外的无关段落编辑仍 GREEN
（不得把 `test_verbatim_pinning_ignores_edits_outside_disciplines` 反踩成误红）。

### B39：DoD 明列的「用例内断言模板 sha256」未落地（阻塞，但工作量极小）

brief §D 卫生第一条：

> 跑完 `git status` 干净；`CLAUDE.md.tmpl` sha256 与跑前逐字节相同
> （`0746351e…`），**且用例内断言之**。

实测：`grep -n 'sha256\|hashlib' tests/test_orchestrator_protocol_disciplines.py`
只命中一条注释（`:96`「deliberately verbatim text — not sha256」），**没有任何用例
断言模板的 sha256 或字节同一性**。执行者用 shell `shasum` 在报告里给了跑前跑后一致，
这满足「跑完一致」但不满足「用例内断言之」。

注意这条与 `:96` 的注释不冲突：注释说的是「不用 sha256 常量替代逐字正文比较」（正确，
那是判别力问题）；DoD 要的是**另一件事** —— 一条卫生用例，证明测试自身没有写活树模板
（WP-26 的 `live_before` 逐字节自比是同型做法，本 WP 可照抄）。

## 报告偏差（非代码缺陷，但须纠正）

报告称：

> python3.13 / python3.14 均无 pytest 模块，无法跑 targeted（避免联网安装/污染环境外）。

不成立。brief §E 要求 3.11/3.13/3.14 全绿，本仓的标准跑法是
`uv run --quiet --python 3.1X --with pytest --no-project python -m pytest`（`--no-project`
不污染环境，不改本机解释器）。编排者按此实测：

```
3.13 → 28 passed
3.14 → 28 passed
```

即该 DoD 项**实际满足**，报告低估了自己的成绩。与 WP-26 rev4 是同一处执行习惯问题
（裸 `python3.13`），两个 WP 的返工提示里都要写明正确形态。

## 合并门（三项，当前一项不成立）

1. 编排者独立复核 = **REWORK**（B38/B39）
2. codex 第二签名 —— 未取，本轮不必取（一审已 REWORK）
3. 用户批准 —— 未取，且现在不应取

## 给 rev5 的范围提示（编排者备忘）

rev4 是 WP-25 的第 3 次 re-freeze，已按任务 #24 做过停手复核；rev5 将是**第 4 次**。
诚实记录一句：B38 不是执行者的实现缺陷 —— 执行者严格照 brief 的「指定修法」三项做完，
两环确已收口。B38 是**编排者的 brief 缺陷**：INV-P 写得足够宽（宽到覆盖 B38），
但「指定修法」只枚举了定位与结构两类，没有把「处境/语境」列为第三类，
于是执行者按修法清单收工是合理的。这与 WP-26 §B35 是同一个病：
**不变式写宽了，修法清单却按已知形状收窄，执行者照清单做就够不着不变式。**
rev5 的 brief 必须把自检的变异集**按 INV-P 的组成维度生成**（内容 / 极性 / 结构 /
定位 / 处境 / 同形新增），而不是按已发现的缺陷编号列举 —— 这正是任务 #36 的内容，
建议在冻结 rev5 之前先把任务 #36 落成规范条目。

# WP-25 rev4: 纪律锁的**定位唯一性**与**结构完整性**（INV-P 一次性收口）

> 冻结日期 2026-09-17 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 前序：rev1（B20 返工前）→ rev2 `284e223`（B20）→ rev3 `aa1e43b`（B28）。
> 本 rev 是**第 3 次 re-freeze**，已按任务 #24 规则完成停手复核计划，裁定见
> `WP-25-plan-review-before-rev4.md`（用户已批准 §5 的「两环一并收口」）。

## 目标（一句话）

关掉逐字锁的两处非内容面逃逸：切块**定位不唯一**（可插 decoy 块）与
空白归一化**吞掉结构**（删列表前缀 / 插空行 / 缩进成 code block 全绿）。

## 本 rev 的验收标的是不变式，不是缺陷编号

**这是本 rev 与前三轮最根本的差别，务必按不变式实现与自检，不要只盯 B33/B34 两个编号。**

> **INV-P（纪律锁定不变式）**：任何使三条纪律的**规范力**减弱的模板改动 —— 无论通过
> 删正文、改极性、改措辞、改结构、改定位，还是**新增同形正文** —— 都必须使测试转红，
> 且转红只能通过修改测试文件里的冻结常量来解除。
> 即：**给削弱开绿灯，必须在测试文件的 diff 里可见。**

三轮的失败点（B20 锚点粒度 / B28 语义极性 / B33 定位唯一性 / B34 结构完整性）是
**同一条链的四环**。rev4 收口后两环，但**判据按 INV-P 写**：凡「削弱了纪律而测试仍绿」
皆算违反，即便它不叫 B33/B34、即便本 brief 没枚举那个形状。
若你在实现中发现第三类非内容面逃逸（例如标记大小写、Unicode 同形字、HTML 注释包裹），
一并钉住并在报告里点名；不要因为 brief 没列就放过。

## Allowed and forbidden paths

**allowed_paths**（本 rev 只准动 1 个文件）:

- `tests/test_orchestrator_protocol_disciplines.py`

**forbidden_paths**:

- `src/agentic_loop/templates/CLAUDE.md.tmpl` —— **零 diff**。措辞已三轮核验通过。
  判据的职责是钉住被判对象，不是让被判对象适配判据。
  若你认为必须改模板才能锁住，说明判据设计错了，回到本 brief 的「指定修法」。
  当前 sha256 = `0746351effd3e85d949452e7b8ebd86beaec3040d8b8fc2fe33b644eacba122a`（跑前跑后须一致）。
- `src/agentic_loop/contract_render.py` —— `CONTRACT_TEMPLATE_VERSION` 已是 `"7"`，**不要再 bump**
- `CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md` —— 渲染产物，**零行 diff**
- `src/agentic_loop/templates/` 下其余全部 `.tmpl`
- `src/agentic_loop/wrappers/` 下全部 `.sh`
- `src/agentic_loop/validate_wp_status.py`、`gate/__init__.py`、`redispatch.py`
- `tests/test_finalize_merge_triple_sign.py` —— 那 4 条是既有环境失败，**不要修**
- `docs/plans/`（含本 brief 自身）、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## 输入

- 被审树：worktree `/Users/admin/vibe/wp25-protocol-disciplines`，分支
  `feature/wp25-protocol-disciplines`，HEAD `aa1e43b`（在其上叠加，**不要** reset）。
- 缺口位置（编排者本轮实测确证，非转述）：
  - **B33 定位不唯一** —— `tests/test_orchestrator_protocol_disciplines.py:151-166`
    （`_cut_discipline_block`）：`si = text.index(start)` 取**首个**出现点，
    `ei = text.index(end, si)` 取其后首个 end，**从未断言标记唯一**。
    实测：把真实 `criteria_sourcing` 块的 `may only` 改为 `may also`（极性反转），
    并在其前插入 `- ` + 原块 + 其 end marker 作 decoy →
    `_assert_discipline_verbatim` **GREEN**、`_assert_discipline_anchors` **GREEN**，
    而攻击后模板里真实纪律确实写着 `may also`。基线（未攻击）三条全绿，正向可达。
  - **B34 归一化吞掉结构** —— 同文件 `:145-149`（`_normalize`）与 `:80-92`（两个 marker 字典）：
    起始标记只取 `**Criteria sourcing.**` 等，**排除了 Markdown 列表前缀 `- `**；
    而 `_normalize = " ".join(text.split())` 抹除全部空白结构。
    实测五种形状全部 `verbatim=GREEN` 且 `anchors=GREEN`：
    ① 删 `criteria_sourcing` 的 `- ` ② 删 `read_face_pinning` 的 ③ 删 `negative_assertion` 的
    ④ 把块内一句缩进 6 空格变成 code block ⑤ 块内插空行。
    第 ④ 项最严重：缩进成 code block 后那段规则渲染出来**不再是纪律正文**。

## 指定修法（编排者已实测可实施，不要另起炉灶）

### 1. 定位唯一性（治 B33）

切块前**枚举** start / end 标记的全部出现位置，各自要求**恰好 1 次**；
并校验三块按预期顺序、互不重叠。任一条不成立 → 判红（fail-closed），
失败措辞须点明「边界不唯一」/「块重叠」/「块顺序错」三者中的哪一种。

**可行性实测**（活树模板 `0746351e…`，你不必复测但不得与之矛盾）：

| discipline | start 出现次数 | end 出现次数 | 区间 |
|---|---|---|---|
| `criteria_sourcing` | 1 | 1 | `[2885, 3288)` |
| `read_face_pinning` | 1 | 1 | `[3290, 3820)` |
| `negative_assertion` | 1 | 1 | `[4232, 4629)` |

三块有序不重叠。**故本修法在当前模板上不会误红。**

### 2. 结构完整性（治 B34）

**2a. 起始标记纳入完整列表前缀。** 改为：

- `criteria_sourcing` → `- **Criteria sourcing.**`
- `read_face_pinning` → `- **Read-face pinning.**`
- `negative_assertion` → `- Every negative assertion`

**可行性实测**：三者在活树模板中**各恰 1 次出现**，作为标记不引入歧义。

**2b. 增加结构断言，不要靠归一化把守结构。** 保留空白归一化（它治 B10 折行误红，仍需要），
但在归一化**之前**对原始块文本增加结构判据，至少拒绝：
- 块内新增空行/空段（当前三块内部均无空行）
- 块内出现 code block 归属的缩进（≥4 空格的续行；当前三块续行均为 2 空格缩进）
- 列表前缀被删（由 2a 的标记本身覆盖，但仍应有独立用例证明）

具体判据形态不限，选定后在 docstring 里写清「哪些结构变化由结构断言把守、
哪些折行差异由归一化吸收」的分界。

### 3. `_normalize` 的正当性论证进 docstring（治根因）

`_normalize` 是 rev1 为治 B10 引入的**解药**，三轮 brief 都写成「必须的一步」，
却从未论证它抹掉的东西是否都无害。它实际抹掉：列表前缀相对正文的位置关系、
空行分段、缩进层级（code block 归属）—— 三样都承载语义。

docstring 必须写出：**它抹掉什么、为什么被抹掉的那些无害、
哪些结构变化改由第 2 项的结构断言把守。** 只写「少了它会误红」不算论证。

## Acceptance tests

**A. 两环各自的正面钉死（本 rev 核心判据，必须用变异差分，不许读代码确认）**

1. **decoy 变异必须转红**（治 B33）：在真实块前复制一份**完好**的冻结块（含其 end marker），
   再反转真实块的极性（如 `may only` → `may also`），断言判据转红，
   且失败措辞点明**边界不唯一**（不是「正文漂移」—— 若措辞是后者，说明你钉的是内容不是定位）。
   **反向差分（注意方向，别写反）**：这条用例断言的是「判据必须转红」。
   把 `_cut_discipline_block` 回退成 `aa1e43b` 的版本（不加唯一性检查）后，
   被攻击的模板上判据仍 GREEN，于是**这条用例本身失败**（它要的红没出现）；
   换回 rev4 版本后**这条用例通过**。
   即：**用例在旧实现上 FAIL、在新实现上 PASS。** 报告里给出这两次实测输出。
   （若你测出的是「旧实现上也 PASS」，说明用例没真正依赖新增的唯一性约束，判据无效，须重做。）
2. **五种结构变异必须各自转红**（治 B34），措辞互不相同或至少能区分原因：
   - (a) 删 `criteria_sourcing` 的 `- ` 前缀
   - (b) 删 `read_face_pinning` 的 `- ` 前缀
   - (c) 删 `negative_assertion` 的 `- ` 前缀
   - (d) 把块内一句缩进 6 空格变成 code block
   - (e) 块内插一个空行
   **反向差分（同一方向约定）**：五条用例各自断言「判据必须转红」。
   把标记字典与归一化/结构判据回退成 `aa1e43b` 的版本后，五种攻击下判据仍 GREEN
   （复现编排者实测），于是**五条用例全部失败**；换回 rev4 版本后**五条全部通过**。
   即：**用例在旧实现上 FAIL、在新实现上 PASS。** 报告给出这两次实测输出。
   > 若某一条你判断不该转红（例如你认为 (e) 属无害排版），**不得自行放宽**，
   > 应 BLOCKED 上报并给出论证。编排者的判断是五条全属结构性削弱。

**B. 无害编辑不误红的反向探针（防为修两环而反踩 B10，必须扩充）**

1. 纯重新折行 GREEN（rev3 已有 `test_verbatim_pinning_survives_pure_rewrap`，保留）
2. 三条纪律之外的编辑 GREEN（rev3 已有 `test_verbatim_pinning_ignores_edits_outside_disciplines`，保留）
3. **新增**：把某条纪律的续行折行位置改变（2 空格缩进保持不变，只挪换行点）→ GREEN。
   这条是 2b 的边界证明：结构断言必须能区分「换行点变了」（无害）与
   「缩进层级变了 / 多了空行」（有害）。

**C. 前三轮判别力全部保留（回归即驳回）**

| 行为 | 来源 |
|---|---|
| 锚点断言（`DISCIPLINE_ANCHORS` 三条） | rev2 (B20) |
| 掏空守卫两处各自独立转红、措辞互不相同 | rev2 (B20) |
| 三种极性反转形状各自转红：带否定词 / 不带否定词 / 只删限定词 | rev3 (B28) |
| 切块失败（边界标记改名）判红，fail-closed | rev3 |
| 变异构造由锚点/被锁文本驱动，不锚在非锚点措辞上 | rev3 (B27) |
| 纯内存变换，**不写活树模板** | rev3 (C2) |

**D. 卫生**

- 跑完 `git status` 干净；`CLAUDE.md.tmpl` sha256 与跑前逐字节相同
  （`0746351effd3e85d949452e7b8ebd86beaec3040d8b8fc2fe33b644eacba122a`），且用例内断言之。
- 三份渲染产物零行 diff（rev3 已有 `test_rendered_artifacts_zero_line_diff`，保留）。
- 每条负面断言带 oracle 三项：① 正向可达控制 ② 原因特异 witness（给出打印点 `file:line`）
  ③ 能转红的变异（纯内存，无需还原）。
- **不许「rc != 0」/「assert 抛了异常」式真空断言** —— 必须断言精确措辞或精确原因。

**E. 门禁与回归**

- 3.11 / 3.13 / 3.14 全绿。
- 相对基线零回归。基线（HEAD `aa1e43b`，编排者本轮实测）：
  - targeted `tests/test_orchestrator_protocol_disciplines.py` = **19 passed**
  - 全量 `PYTHONPATH=src python3.11 -m pytest tests -q` = **4 failed / 616 passed / 4 skipped**，
    4 条全在 `tests/test_finalize_merge_triple_sign.py`，原因是本机
    `git init.defaultBranch=master` 与 fixture 的 `git checkout main` 冲突（台账 §B31 第一段）。**不要修。**
  - 另有 1 条**只在 `uv run` 下**复现（`test_init_githooks.py::test_prepush_hook_targets_current_worktree_status_in_linked_worktree`），
    是台账 §B31 本体、已另立任务 #31，**不在本 WP 范围**。本 WP 的 3.13/3.14 只跑 targeted 用例，不会撞上。
- 测试文件跑前 sha256 = `727caa2133d8ad0830e0c107420dd2b0df5a0657cecd477c8b4dfab6c01d7e99`（供你确认起点一致）。

## Completion definition

- [ ] 切块前枚举 start/end 全部出现位置，各恰 1 次；三块有序不重叠；不成立则判红且措辞点明原因类别
- [ ] 起始标记纳入完整列表前缀（`- **Criteria sourcing.**` / `- **Read-face pinning.**` / `- Every negative assertion`）
- [ ] 归一化之前增加结构断言（拒空行、拒 code block 缩进、拒删前缀），docstring 写清与归一化的分界
- [ ] `_normalize` docstring 论证它抹掉什么、为什么无害、哪些改由结构断言把守
- [ ] A1 decoy 变异用例转红且措辞点明「边界不唯一」；反向差分方向正确（旧实现上该用例 FAIL、新实现上 PASS），报告含两次实测输出
- [ ] A2 五种结构变异用例各自转红；反向差分方向正确（旧实现上五条全 FAIL、新实现上全 PASS），报告含两次实测输出
- [ ] B 三条无害探针全绿（含新增的「只挪换行点」）
- [ ] C 前三轮六项判别力全部保留且仍绿
- [ ] 每条负面断言带 oracle 三项，无真空断言
- [ ] `CLAUDE.md.tmpl` 零 diff 且 sha256 跑前跑后一致，用例内已断言
- [ ] `CONTRACT_TEMPLATE_VERSION` 保持 `"7"`
- [ ] 三份渲染产物零行 diff
- [ ] 跑完工作树干净
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（19 passed 只增不减；那 4 条既有失败不要修）
- [ ] 无 forbidden_paths 写入、无跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

| 维度 | 取值 |
|---|---|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要改模板**。`CLAUDE.md.tmpl` 是 forbidden，三轮措辞已核验通过。
2. **不要把 A1/A2 写成「读代码确认标记只出现一次」。** 三轮都栽在「约束强度不足」上：
   静态确认阻止不了未来重新引入，只有差分变异能。
3. **不要为修结构面而砍掉归一化。** 归一化治 B10（折行误红），砍了会反踩。
   正确做法是「归一化吸收折行 + 结构断言把守结构」两层分工，B3 探针就是这条分界的证明。
4. **不要只盯 B33/B34 两个编号。** 判据是 INV-P，凡「削弱纪律而测试仍绿」皆在范围内。
5. **不要用 sha256 常量代替逐字文本**（rev3 已定的设计要求）：两者判别力相同，
   但 sha256 让「给削弱开绿灯」在 diff 里隐形。
6. **不要写活树模板**（rev3 C2 已收口）。纯内存变换即可，判别力实测等价。
7. **不要用 `agentic <sub>` 自证**（B14：冻结副本）。用 `PYTHONPATH=src python3.11 -m pytest`。
8. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。
9. **既有失败不是你引入的**（4 条 defaultBranch 冲突 + 1 条只在 `uv run` 下现形的 B31 本体），
   不要顺手修。
10. **反向差分的方向别写反。** 变异用例断言的是「判据转红」，所以在**旧实现**上
    这条用例应当 **FAIL**（它要的红没出现），在**新实现**上 **PASS**。
    WP-27 曾因把这个方向写反而返工一轮，不要重踩。
11. **本 WP 已是第 3 次 re-freeze。** 范围已被编排者刻意压到 1 个文件、2 个环。
    不要扩（模板、流程固化、`contract_render.py` 都在范围外），也不要缩
    （两环必须一并收口，只修一条则另一条仍在，会招来第 4 次）。

### 口径权威源引用

- B33 / B34 实测记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B33 / §B34
- B28 / B27 / B20 记录：同上 §B28 / §B27 / §B20
- 第 3 次 re-freeze 停手复核裁定：`WP-25-plan-review-before-rev4.md`（用户已批准）
- rev3 第二签名判词（逐字转录）：`WP-25-consult-codex-rev3.md`
- rev3 冻结 brief：`WP-25-brief-rev3.md`
- rev3 的实现与用例：commit `aa1e43b`（工作树 `/Users/admin/vibe/wp25-protocol-disciplines`）
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
- 相关教训：`mem:verbatim-lock-needs-unique-anchor`、`mem:normalization-must-justify-what-it-erases`、
  `mem:mutation-set-follows-criterion-structure`

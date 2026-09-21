# WP-25 rev3: 三条编排者纪律的判据必须钉住**极性**，不只是钉住词组在场（B28 返工）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> **rev1 已交付并被驳回**（`359cb1a`，缺陷 B20）；**rev2 已交付并被驳回**（`284e223`，缺陷 B28，
> 第二签名发现、编排者撤回自评 ACCEPT）。
> 本 rev **只**修 B28 与 B27，rev1/rev2 的其余部分全部保留、不得推翻重写。

## 目标（一句话）

rev2 把锚点从标签词补到了可操作子句（B20 修法正确、方向对），但锚点仍是**存在性**判据：
保留全部六个锚点短语、把纪律改成**语义相反**的规则，十条用例全绿。
本 rev 把三条纪律的判据换成**逐字锁定（verbatim pinning）**，使任何极性反转或语义削弱必定转红。

## rev1 + rev2 的哪些部分已通过核验（**不要动**）

编排者与 codex 两轮独立核验通过，返工时必须原样保留：

| 项 | 状态 |
|---|---|
| 三条纪律写进 `CLAUDE.md.tmpl`，语义齐全、措辞正确 | 通过，**不必也不应改模板措辞** |
| `:31` / `:36` 两处 `agentic <sub>` 示例的冻结副本告警 | 通过 |
| `CONTRACT_TEMPLATE_VERSION` = `"7"` | 通过（**不要再 bump**） |
| 三份渲染产物零行 diff | 通过 |
| rev2 的锚点补到可操作子句（`flip exactly one input` 等六个短语） | 通过，**保留**，本 rev 是**叠加**判据而非替换 |
| rev2 的掏空守卫用例（B20 两处删除必转红） | 通过，**保留** |
| 变异还原字节一致 + `try/finally` 恢复 | 做法通过，但见交付物 3（改为不写活树） |
| 3.11 / 3.13 / 3.14 全绿 | 通过 |

> ⚠️ 本 rev 的 diff 应当**只动 `tests/test_orchestrator_protocol_disciplines.py`**。
> 模板措辞已两轮核验通过，本 rev 不需要改它。

## B28 实测（编排者已两级复现，执行者不必重做，但**不得与之矛盾**）

保留 `DISCIPLINE_ANCHORS` 全部六个短语不动，只把纪律 2 的正文改成语义相反：

```
use a differential pair instead: do not hold everything else constant,
do not flip exactly one input, and never require the red/green verdict to flip with it.
```

→ 六个锚点**全部在场**，`_assert_discipline_anchors` 对两条纪律**均 GREEN**；
掏空守卫的正则仍匹配、仍转红、witness 仍特异。活树级：整文件 `pytest` → **10 passed**。
一份指导「不要只翻一个输入、不要要求红绿随之翻转」的纪律，被全部用例判为合规。

**根因**：`X in text` 这个判据形状，无论 X 取多细，只能回答「词组在不在」，
永远回答不了「这句话是在要求它还是在禁止它」。

## 三条已被编排者实测**排除**的修法（不要走，走了会被驳回）

本 rev 冻结前编排者实测了四种候选判据。**前三种已排除，第四种是本 rev 指定的修法。**

### ✗ 修法 A：把锚点写长（整句/整从句锚点）

已在 B28 台账中排除：模板正文折行，整句在原文里不逐字存在（需先归一化空白）；
且一次**无害子句重排**（`flip exactly one input while holding everything else constant`）
就让整句锚点失配、而短语锚点全部保留 —— **反踩 B10**（断言与措辞耦合 → 误红）。

### ✗ 修法 B：否定词扫描（锚点邻域出现 not/never/no 则判红）

编排者实测排除。原文**合法地**含有 `cannot`（纪律 2）、`never`（纪律 1）、`not`（纪律 3），
基线本身就有否定词，无法用「出现否定词」做判据。改成「冻结否定词轮廓、轮廓变化则红」后：

- 能抓住 B28 那个**带否定词**的反转（轮廓 `('cannot',)` → `('cannot','never','not','not')`）；
- 但**放过**不加否定词的反转：`a wording assertion is sufficient: you may hold everything
  else constant, …, and treat the red/green verdict as free to flip with it.` → **完全无信号，GREEN**；
- 且**误红**无害补充：给纪律 3 加一句 `and that no stale alias survives` → 轮廓变化 → 假红。

即：漏抓 + 误红两头都有，判据不可用。

### ✗ 修法 C：禁忌削弱短语表（黑名单）

编排者实测排除。冻结一张 `is sufficient` / `you may assume` / `need not` / `do not flip` 等
12 条禁忌短语表，对 B28 反转、B20 掏空、否定词反转、`retype` 反转**四种都能抓**，
三条无害编辑也都不误红 —— 看起来可用。但对**改写措辞绕过词表**的反转：

| 反转 | 判据 |
|---|---|
| `a wording assertion suffices; hold …`（把 `is sufficient` 换成 `suffices`） | **GREEN 逃逸** |
| `At your discretion, verify that every consumer channel …` | **GREEN 逃逸** |
| `Where practical, a pass/fail judgement may be made …` | **GREEN 逃逸** |
| 只删掉一个词 `only`：`may only be made` → `may be made` | **GREEN 逃逸** |

**五个反转里四个逃逸**。这就是 B28 的同一形状又高一层：黑名单枚举「坏的说法」，
而坏的说法可以无限改写。**不要提交任何基于禁忌词/否定词枚举的判据。**

### ✓ 修法 D（本 rev 指定）：逐字锁定三条纪律的**正文块**

判据形状从「某短语在不在」换成「这一整块的**规范化正文**逐字等于冻结值」：

1. 用块自身的边界标记切出三条纪律的正文块（例如
   `**Criteria sourcing.**` 到 `- **Read-face pinning`；
   `**Read-face pinning.**` 到 `- Use the $consultant`；
   `Every negative assertion` 到 `- Return only`）；
2. 对切出的块做**空白归一化**（`' '.join(text.split())`）—— 这一步是 B10 的解药：
   纯折行/重排版不算改动；
3. 断言归一化后的块**逐字等于**测试文件里冻结的期望文本。

**编排者实测（九个反转零逃逸，三类无害编辑零误红）**：

| 变换 | 判据 |
|---|---|
| M1 B28 自己那个带否定词的反转 | RED `negative_assertion` |
| M2 不加否定词的反转（`is sufficient` / `free to flip`） | RED `negative_assertion` |
| M3 rev-N 从句削弱成 `you may assume … does)` | RED `read_face_pinning` |
| M4 B20 的掏空（压成口号） | RED `negative_assertion` |
| A1 `a wording assertion suffices;`（绕开词表） | RED `negative_assertion` |
| A2 `At your discretion, verify …` | RED `read_face_pinning` |
| A3 `Where practical, a pass/fail judgement …` | RED `criteria_sourcing` |
| A4 只删一个词 `only` | RED `criteria_sourcing` |
| A5 `Never retype` → `Retype` | RED `criteria_sourcing` |
| **逃逸数** | **0** |
| I1 纯重新折行（3 行 → 4 行） | GREEN ✅ |
| I2 三条纪律**之外**的编辑（改标题、加无关 bullet） | GREEN ✅ |
| fail-closed：块标记本身被改名（切不出块） | RED ✅（不是静默 GREEN） |

**已知性质，必须在用例 docstring 里如实写明，不得隐瞒**：
块**内部**的无害子句重排（`flip exactly one input while holding everything else constant`）
**会转红**。这是判据的**设计取舍**而非缺陷 —— 三条纪律是协议正文，
改它的措辞本就应当是一次显式、被看见的决定。误红的代价是「改措辞要同步改期望值」，
漏抓的代价是「反转后的纪律被判合规」；本 WP 两轮返工都栽在后者，故取前者。

**为什么用逐字文本而不是 sha256**：编排者实测两者**判别力完全相同**（同样九抓零逃、同样不误红）。
但逐字文本有一个 sha256 没有的性质：**想给反转开绿灯，必须把反转后的纪律原文写进测试文件**，
在 diff 里明晃晃地被看见；而改一串 sha256 常量在 diff 里看不出改了什么语义。
**必须用逐字文本，不要用 sha256 常量。**

## Allowed and forbidden paths

**allowed_paths**

- `tests/test_orchestrator_protocol_disciplines.py`

**forbidden_paths**

- `src/agentic_loop/templates/CLAUDE.md.tmpl` —— 措辞已两轮核验通过；本 rev 只改判据，
  **不改被判对象**。（rev2 曾允许"必要时可改"，rev3 收紧为禁止：若你认为必须改模板才能锁住，
  说明判据设计错了，回到修法 D。）
- `src/agentic_loop/contract_render.py` —— 版本已是 `"7"`，**不要再 bump**
- `CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md` —— 渲染产物，**零行 diff**
- `src/agentic_loop/templates/` 下其余全部 `.tmpl`
- `src/agentic_loop/wrappers/` 下全部 `.sh`
- `src/agentic_loop/validate_wp_status.py`、`gate/__init__.py`、`redispatch.py`
- `docs/plans/`（含本 brief 自身）、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## 交付物清单

1. **逐字锁定判据**：按修法 D 切出三条纪律正文块、空白归一化、断言逐字等于冻结期望文本。
   期望文本以**多行字符串常量**形式写在测试文件里（人可读、diff 可见），**不得用 sha256 常量**。
   切块失败（找不到边界标记）必须**判红**，不得静默跳过（fail-closed）。
2. **极性反转变异用例**：至少覆盖三种形状，各自独立转红且失败措辞互不相同：
   - (a) 带否定词的反转（B28 原样：`do not flip exactly one input` …）；
   - (b) **不加否定词**的反转（`a wording assertion suffices` 或 `At your discretion,` 之类）；
   - (c) **只删一个限定词**的削弱（`may only be made` → `may be made`）。
   这三种正是修法 B/C 各自漏抓的形状，用例必须证明修法 D 抓得住。
3. **rev2 的锚点断言与掏空守卫全部保留**。本 rev 是叠加，不是替换。
   但守卫用例**不得再写活树模板**：改为纯内存变换（对读入的文本做替换后直接喂判据函数），
   见下方 B27/C2。编排者实测：纯内存变体判别力与写活树完全等价。
4. **无害编辑不误红的反向探针**：至少两条 — 纯重新折行必须 GREEN；
   三条纪律之外的编辑必须 GREEN。（这是防止本 rev 为修 B28 而反踩 B10 的保险。）
5. 每条负面断言仍带 oracle 三项。

## 附带修掉的 B27 / C2（第二签名升级为阻塞）

rev2 的掏空守卫用例有两个问题，本 rev 一并收口：

- **B27**：变异构造正则 `_EVISCERATION_2_RE` / `_EVISCERATION_3_RE` 锚在**非锚点措辞**上
  （`use a differential pair instead:` / `When a frozen artifact is renamed`）。
  变异构造应当由**锚点本身**驱动 —— 变异要删的就是锚点所钉的那段，
  两者锚在不同措辞上时，措辞一动就误红。第二签名把它从"非阻塞"升级为阻塞：
  **误红本身就是 B10 要禁的东西**。
- **C2 / 活树写入**：`CLAUDE_TMPL.write_text(...)` 直写活树模板（虽有 `try/finally` + sha256 核验）。
  取消。理由是编排者实测的、比"并行竞态"更强的一条：纯内存变体**判别力完全等价**
  （两条纪律都红、witness 都特异），而同仓另有 3 个测试读同一模板，
  写 tracked 文件是净损失。（注：codex 提的 `pytest -n` 竞态论据，编排者实测
  **xdist 当前未安装、也无 `-n`/addopts 配置**，该竞态当前不成立；结论仍采纳，但理由换成上面这条。）

## Acceptance tests

- **B28 反转必须转红**：三种极性反转形状（带否定词 / 不带否定词 / 只删限定词）
  各自在一条用例里正面断言转红，失败措辞互不相同（原因特异）。
- **B20 掏空仍必转红**：rev2 的两处掏空各自独立转红，措辞互不相同（保留 rev2 已通过的性质）。
- **反向探针必须绿**：纯重新折行 GREEN；三条纪律之外的编辑 GREEN。
- **fail-closed**：块边界标记被改名时判红，不得静默通过。
- **不得写活树模板**：跑完 `git status` 干净，且模板 sha256 与跑前一致
  （用例内不写活树；这条核验是防回归，不是允许写了再还原）。
- rev1 + rev2 已有的十条断言全部保留且仍绿。
- oracle 三项：
  1. 同一 fixture 上的正向可达控制（沿用 `test_template_carries_control_anchor`）；
  2. 原因特异 witness，给出打印点 `file:line`；
  3. 能转红的 forbidden 变异，跑完不留痕（纯内存，无需还原）。
- 3.11 / 3.13 / 3.14 全绿。
- 相对基线零回归。基线见 status JSON 的 `evidence.baseline`。
  **已知既有失败，不要修**（编排者在 rev2 的 HEAD `284e223` 上实测）：
  - 用 brief 指定的基线命令 `PYTHONPATH=src python3.11 -m pytest tests -q` 跑，结果是
    **4 failed / 607 passed / 4 skipped**，4 条全在 `tests/test_finalize_merge_triple_sign.py`，
    原因是本机 `git init.defaultBranch=master` 与 fixture 的 `git checkout main` 冲突（台账 §B31 第一段）。
  - 另有 1 条**只在 `uv run` 下**复现：
    `tests/test_init_githooks.py::test_prepush_hook_targets_current_worktree_status_in_linked_worktree`。
    `uv run` 会把 `.venv/bin` 放进 PATH，钩子子进程里的 `python3` 因此能 import 到框架，
    才触发 `pre-push.tmpl` 丢弃 `repo_root` 的真缺陷（台账 §B31 本体）。裸 `python3.11` 下它是绿的。
    这是真缺陷、已另立任务，**不在本 WP 范围**。
  - 本 WP 的 3.13 / 3.14 走 `uv run` 但只跑 targeted 用例（不含 `test_init_githooks.py`），不会撞上它。

## Completion definition

- [ ] 三条纪律正文块逐字锁定（多行字符串常量，非 sha256），切块失败判红
- [ ] 三种极性反转形状各有用例、各自转红、措辞互不相同
- [ ] rev2 的锚点断言与掏空守卫全部保留且仍绿
- [ ] 掏空守卫改为纯内存变换，**不再写活树模板**
- [ ] 变异构造由锚点/被锁文本驱动，不再锚在非锚点措辞上（B27）
- [ ] 两条以上无害编辑反向探针为绿（防反踩 B10）
- [ ] 块内部子句重排会红这一取舍已在 docstring 如实写明
- [ ] `CONTRACT_TEMPLATE_VERSION` 保持 `"7"`，未再 bump
- [ ] `CLAUDE.md.tmpl` **零改动**（本 rev 它是 forbidden）
- [ ] 三份渲染产物 diff 零行
- [ ] 跑完工作树干净、模板 sha256 与跑前一致
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（上列 5 条既有失败除外，不要修）
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

1. **不要走修法 A/B/C**。三种都已被编排者实测排除，实测数据在上文表格里。
   特别是：**任何基于禁忌词表/否定词枚举的判据都会被改写措辞绕过**（实测 5 个反转 4 个逃逸）
2. **不要改模板措辞**。本 rev 模板是 forbidden_paths。判据的职责是钉住被判对象，
   不是让被判对象来适配判据。
3. **不要用 sha256 常量代替逐字文本**。两者判别力相同，但 sha256 让"给反转开绿灯"
   在 diff 里隐形。这条是本 rev 的明确设计要求。
4. **归一化空白是必须的一步**，不是可选优化 —— 少了它就会因折行误红（反踩 B10）。
5. **不要把活树模板留在变异态，也不要写它**。纯内存变换即可，判别力实测等价。
6. **不要用 `agentic <sub>` 自证**（B14：冻结副本）。用 `PYTHONPATH=src python3.11 -m pytest`。
7. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。
8. **既有失败不是你引入的**（4 条 defaultBranch 冲突 + 1 条只在 `uv run` 下现形的 B31 本体），
   不要顺手修，那超出本 WP 范围。基线口径见 Acceptance tests 末条。

### 口径权威源引用

- B28 实测记录（含修法 A 的排除）：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B28
- B27 记录：同上 §B27
- B20 记录：同上 §B20
- 修法 B/C/D 的实测对照：本 brief「三条已被排除的修法」节（编排者 2026-09-16 实测）
- rev2 的实现与用例：commit `284e223`（工作树 `/Users/admin/vibe/wp25-protocol-disciplines`）
- rev2 冻结 brief：`docs/plans/2026-09-13-parallel-throughput/WP-25-brief-rev2.md`
- 第二签名判词：`docs/plans/2026-09-13-parallel-throughput/WP-25-consult-codex-rev.md`
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
- 既有失败的归因：台账 §B31

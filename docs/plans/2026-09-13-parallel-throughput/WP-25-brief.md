# WP-25: 把「冻结前自检 / 判据来源 / 读取面」三条编排者纪律写进契约模板（B11 + B14 + B16 + B17）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。

## 目标（一句话）

本迭代连续出现四个**编排者自身**的缺陷（B11、B14、B16、B17），共同根因是
「判据的通道变了，判据本身没变」；把已实测出的三条纪律写进
`src/agentic_loop/templates/CLAUDE.md.tmpl`，并按机制 bump `CONTRACT_TEMPLATE_VERSION`，
使其成为每个项目渲染出的常驻协议，而不是只活在某一轮对话里。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

四个缺陷都已在 `WP-08-candidate.md` 登记并附实测证据：

| 缺陷 | 判据读错了什么 | 实测证据 |
|---|---|---|
| B11 | 抄出来的判据**副本**（副本自造措辞被写成必达断言） | `dispatch_lint.sh:86/:98` 打印同一句；改标题/清段体两种变异 stderr 逐字节相同 |
| B14 | **冻结副本的代码**（`agentic` 不是 editable） | `diff -rq` 差异：`finalize_merge.sh` 26 行、`preflight.sh` 23 行、`gate/__init__.py` 191 行；`gate/report.py` 副本里不存在 |
| B16 | **固定命名的 brief**（`evidence.brief.path` 从不被读） | `evidence.brief.path` 改指不存在文件仍 `DISPATCH_LINT_PASS rc=0`；仅换 `work_package_id` 立刻 `FAIL rc=2` |
| B17 | **工作树快照的 status**（不是主仓 live） | 只改工作树副本 `state=BLOCKED` 即 `PREFLIGHT_FAIL`，主仓副本恒为 `DRAFT` 从不参与 |

**当前模板自身正在示范踩坑的形态**（这是本 WP 的直接动因）：
`CLAUDE.md.tmpl:31` 写 `agentic preflight <status.json>`，
`:36` 写 `$health_check_cmd <status.json> …`（渲染为 `agentic health …`）。
即协议在教编排者去调那份落后活树上百行的冻结副本。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/templates/CLAUDE.md.tmpl`
  - `src/agentic_loop/contract_render.py`（**仅**为 bump `CONTRACT_TEMPLATE_VERSION`）
  - `tests/test_contract_render.py`（如版本断言需随之更新）
  - `tests/test_orchestrator_protocol_disciplines.py`（新建，锁本 WP 的三条纪律）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md`
    —— 这三份是**渲染产物**，不是源；直接改它们会被 contract drift 判出，
    且下一次渲染即被覆盖。**零行 diff**
  - `src/agentic_loop/templates/` 下其余全部 `.tmpl`
  - `src/agentic_loop/wrappers/` 下全部 `.sh`（本 WP 不修 B14/B16/B17 本体）
  - `src/agentic_loop/validate_wp_status.py`、`gate/__init__.py`、`redispatch.py`
  - `docs/plans/`（含本 brief 自身）、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ **改源不改产物**：`CLAUDE.md` 是 `CLAUDE.md.tmpl` 渲染出来的。
> 只改模板 + bump 版本；产物的重新渲染由编排者在验收后按机制执行。

## 交付物清单

1. `CLAUDE.md.tmpl` 的 `## Dispatch` / `## Review` 段落新增三条纪律
   （措辞可自行打磨，语义必须齐全）：

   **纪律 1 · 判据只能来自权威源本体，不得用副本或retype**
   需要判断「某文件过不过某 gate」时，必须从真脚本原文切片/直接调用真脚本；
   禁止把判据抄进临时脚本再跑。副本可能自造措辞，据此写成的必达断言会误导
   执行者和第二签名（B11 实际发生：codex 被误导给出不可达修法）。

   **纪律 2 · 负面断言须给出打印点 `file:line`；同措辞两路径改用差分对**
   任何「应当报错」的断言都要指出该措辞在权威源里的打印位置。
   若权威源对两种不同原因打印同一句话，措辞断言钉不住判据，
   必须改用**差分对**：其余全部恒定，只翻一个输入，断言红绿随之翻转。

   **纪律 3 · 读取面必须钉在权威位置**
   - 代码判据：直跑活树脚本（`PYTHONPATH=src bash src/agentic_loop/wrappers/<x>.sh`），
     不得用 `agentic <sub>` 作为验收证据（B14：那是冻结副本）；
   - status / brief：一律用**主仓**路径，工作树里的同名文件是历史快照
     （B17 / B16）；
   - 冻结产物换了文件名（`-revN`）时，必须核验消费该产物的通道是否跟着走
     （B16：门禁按固定命名读，rev 冻结不在 lint 面内）。

2. `CLAUDE.md.tmpl:31` 与 `:36` 的命令示例改为活树形态，或就地加显式告警说明
   `agentic <sub>` 可能是冻结副本、不可作为验收证据。**二者择一，须自洽**。
3. `CONTRACT_TEMPLATE_VERSION` 由 `"6"` bump 到 `"7"`。
4. 新测试 `tests/test_orchestrator_protocol_disciplines.py`，锁住：
   - 模板中三条纪律各自的**语义锚点**存在（不是锁死整段措辞，避免脆断言）；
   - `CONTRACT_TEMPLATE_VERSION == "7"`；
   - 渲染产物里三条纪律都出现（即渲染路径确实带上了它们）；
   - 三份渲染产物（`CLAUDE.md` / `AGENTS.md` / `OPERATING_MODEL.md`）的 diff 为零行
     —— 证明本 WP 只改源、未手改产物。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/templates/CLAUDE.md.tmpl`
- `src/agentic_loop/contract_render.py` (version bump only)
- `tests/test_contract_render.py` (only if its version assertion must follow)
- `tests/test_orchestrator_protocol_disciplines.py` (new)

**forbidden_paths**

- `CLAUDE.md`, `AGENTS.md`, `docs/agentic/OPERATING_MODEL.md` — rendered
  artifacts, not sources; **zero-line diff**
- every other `.tmpl` under `src/agentic_loop/templates/`
- every `.sh` under `src/agentic_loop/wrappers/` (this WP does not fix the
  B14/B16/B17 bodies)
- `src/agentic_loop/validate_wp_status.py`, `gate/__init__.py`, `redispatch.py`
- `docs/plans/` (including this brief), `.agentic/config.toml`,
  `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

- The new test asserts a semantic anchor for each of the three disciplines in
  `CLAUDE.md.tmpl` — anchors, not whole-paragraph string equality, so wording
  can be improved without breaking the test.
- The new test asserts `CONTRACT_TEMPLATE_VERSION == "7"`.
- The new test renders the contract and asserts all three disciplines appear in
  the rendered output, proving the render path carries them.
- The new test asserts the three rendered artifacts have a zero-line diff in
  this commit, proving only sources changed.
- Each negative assertion in the new test carries the oracle three items:
  1. positive reachability control on the same fixture;
  2. a cause-specific witness; if two causes print the same message, use a
     differential pair instead of asserting on wording;
  3. a representative forbidden mutation that turns the test red — e.g. delete
     one discipline anchor from the template and show the test goes red, then
     restore.
- `tests/test_contract_render.py` and `tests/test_init_contract.py` stay green
  (they already guard the version stamp).
- Green on 3.11, 3.13 and 3.14.
- Zero regression against the baseline recorded in this WP's status JSON.

## Completion definition

- [ ] 三条纪律写进 `CLAUDE.md.tmpl`，语义齐全
- [ ] `:31` / `:36` 的 `agentic <sub>` 示例已改为活树形态或已加显式告警，且自洽
- [ ] `CONTRACT_TEMPLATE_VERSION` = `"7"`
- [ ] 新测试锁住三条纪律语义锚点 + 版本 + 渲染带上 + 产物零行 diff
- [ ] 新测试每条负面断言都带 oracle 三项，含一个能转红的 forbidden 变异
- [ ] `CLAUDE.md` / `AGENTS.md` / `OPERATING_MODEL.md` diff **零行**
- [ ] `tests/test_contract_render.py`、`tests/test_init_contract.py` 全绿
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（基线见 status JSON 的 `evidence.baseline`；
      其中 `tests/test_finalize_merge_triple_sign.py` 的 4 条是既有失败，**不要修**）
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

1. **不要改渲染产物**。`CLAUDE.md` 等三份是 `.tmpl` 渲染出来的；手改会被
   contract drift 判出，且下次渲染即覆盖。本 WP 只改源 + bump 版本。
2. **版本 bump 是机制要求**，不是可选项。改了模板文本不 bump，
   已渲染的项目不会更新，纪律就只活在仓库里、不进任何项目。
3. **语义锚点，不要锁死整段措辞**。锁死会让后续任何措辞打磨都变成"回归"，
   这类脆断言本身就是本迭代反复吃亏的东西。
4. **不要顺手修 B14/B16/B17 本体**。那三个各有独立 WP（任务 #14 / #18 / #19），
   本 WP 只把纪律写进协议。越界改 wrapper 会被驳回。
5. **不要用 `agentic <sub>` 自证**。本 WP 的主题就是这条；用它自证会很讽刺地
   跑到冻结副本上（`gate/report.py` 在副本里根本不存在）。
   用 `PYTHONPATH=src python3.11 -m pytest …`。
6. **冻结输入在主仓**：Brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。

### 口径权威源引用

- 契约渲染机制与版本戳：`src/agentic_loop/contract_render.py`
  （`CONTRACT_TEMPLATE_VERSION`、`stamp()`）
- 现有版本守卫用例：`tests/test_contract_render.py`、`tests/test_init_contract.py`
- 四个缺陷的实测记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md`
  的 §B11 / §B14（含 2026-09-16 补充实测与回查结果）/ §B16 / §B17
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`（WP-24 rev1 已写入）

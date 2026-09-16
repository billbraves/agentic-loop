# WP-25 rev2: 三条编排者纪律的语义锚点必须钉在**可操作子句**上（B20 返工）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> **rev1 已交付并被驳回**（commit `359cb1a`，判定 REWORK，缺陷 B20）。
> 本 rev **只**修 B20，rev1 的其余部分全部保留、不得推翻重写。

## 目标（一句话）

rev1 把三条纪律写进了 `CLAUDE.md.tmpl` 且方向正确，但它的守卫用例只钉住了
纪律的**标签词**，没钉住纪律的**做法**：保留六个锚点字串不动，把「差分对怎么做」
压成一句口号、把「rev 改名须核消费通道」整段删掉，九条用例仍然全绿。
本 rev 把锚点移到可操作子句上，使被掏空 how 的模板必定转红。

## rev1 的哪些部分已通过核验（**不要动**）

编排者与 codex 独立核验通过，返工时必须原样保留：

| 项 | 状态 |
|---|---|
| 三条纪律写进 `CLAUDE.md.tmpl`，语义齐全 | 通过，措辞不必改 |
| `:31` / `:36` 两处 `agentic <sub>` 示例就地加冻结副本告警 | 通过，二选一已自洽 |
| `CONTRACT_TEMPLATE_VERSION` = `"7"` | 通过（codex 已核对提交两侧 6→7） |
| 三份渲染产物零行 diff | 通过 |
| 两处锚点变异失败措辞互不相同（原因特异） | 通过 |
| 变异还原字节一致（sha256 `0746351e…acba122a`） | 通过 |
| 3.11 / 3.13 / 3.14 全绿；全量 `4 failed, 606 passed, 4 skipped` | 通过（基线 597，+9 == 新增用例数） |

> ⚠️ 本 rev 的 diff 应当**很小**：预期只动 `tests/test_orchestrator_protocol_disciplines.py`。
> 若你发现必须改模板措辞才能补锚点，可以改，但要说明为什么 rev1 的措辞钉不住。

## B20 实测（编排者已复现，执行者不必重做，但**不得与之矛盾**）

保留 `DISCIPLINE_ANCHORS` 全部六个字串，只做两处删除：

1. 纪律 2 的方法整句
   `use a differential pair instead: hold everything else constant, flip exactly one input, and require the red/green verdict to flip with it.`
   → `use a differential pair instead.`
2. 纪律 3 的 rev 改名子句整段删除
   `When a frozen artifact is renamed (-revN), verify that every consumer channel follows the new name (a gate that reads a fixed filename does not).`

→ `PYTHONPATH=src python3.11 -m pytest tests/test_orchestrator_protocol_disciplines.py -q` = **9 passed**。

即锚点钉的是纪律的名字，不是纪律的做法。

## 范围

- **allowed_paths**：
  - `tests/test_orchestrator_protocol_disciplines.py`
  - `src/agentic_loop/templates/CLAUDE.md.tmpl`（**仅**在补锚点确实需要调整措辞时；
    改了必须说明理由，且三份渲染产物仍须零行 diff）
- **forbidden_paths**：
  - `src/agentic_loop/contract_render.py` —— 版本已是 `"7"`，**不要再 bump**
    （rev1 已交付该 bump，rev2 是同一次交付的返工，不是第二次模板变更）
  - `CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md` —— 渲染产物，**零行 diff**
  - `src/agentic_loop/templates/` 下其余全部 `.tmpl`
  - `src/agentic_loop/wrappers/` 下全部 `.sh`
  - `src/agentic_loop/validate_wp_status.py`、`gate/__init__.py`、`redispatch.py`
  - `docs/plans/`（含本 brief 自身）、`.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## 交付物清单

1. `DISCIPLINE_ANCHORS`（或等价结构）补上钉住**可操作子句**的锚点：
   - **纪律 2 的差分对方法**：至少覆盖「恒定其余」「只翻一个输入」「红绿随之翻转」
     这三层里能唯一定位该方法的短语（例如 `flip exactly one input` 与
     `verdict to` / `flip with it` 之类）；
   - **纪律 3 的 rev 改名消费通道核验**：至少覆盖 `-revN` 改名与「消费该产物的通道
     必须跟着走」这层语义（例如 `consumer channel` 与 `fixed filename`）。
   仍用**短语锚点**，不得锁整段措辞（否则反向踩 B10 的脆断言）。
2. 一条**掏空守卫**用例：直接复现 B20 的两处删除（保留所有原锚点字串），
   断言用例转红。这条是本 rev 的核心，必须存在。
3. 每条负面断言仍带 oracle 三项。

## Acceptance tests

- **B20 反转必须成立**：把 rev1 的两处「掏空 how」变换应用到模板上，
  新的锚点断言必须 FAIL（rev1 下它们 PASS）。这是本 rev 的判据本体，
  必须在一条用例里正面断言，不能只靠人工变异证明。
- 掏空守卫用例须**逐处独立**：只掏纪律 2 的方法 → 红；只掏纪律 3 的 rev 子句 → 红。
  两处各自的失败措辞必须**互不相同**（原因特异；同措辞则改用差分对）。
- rev1 已有的九条断言全部保留且仍绿。
- 变异用例必须**还原并核验字节一致**，跑完工作树干净。
  若变异对象是模板本身，参考 WP-27 的做法把它复制到 scratch 目录再变异，
  或用 `try/finally` 恢复后断言 sha256 一致 —— **不要**把活树模板留在变异态。
- oracle 三项：
  1. 同一 fixture 上的正向可达控制（沿用 rev1 的 `test_template_carries_control_anchor`）；
  2. 原因特异 witness，并给出打印点 `file:line`；
  3. 一个能转红的 forbidden 变异，跑完还原并确认字节一致。
- 3.11 / 3.13 / 3.14 全绿。
- 相对基线零回归（基线见 status JSON 的 `evidence.baseline`；
  `tests/test_finalize_merge_triple_sign.py` 的 4 条是既有失败，**不要修**）。

## Completion definition

- [ ] 锚点已移到/补到可操作子句上，纪律 2 的方法与纪律 3 的 rev 子句各有锚点
- [ ] 掏空守卫用例存在，且两处掏空各自独立转红、失败措辞互不相同
- [ ] rev1 的九条断言全部保留且仍绿
- [ ] 锚点仍是短语级，未锁整段措辞
- [ ] `CONTRACT_TEMPLATE_VERSION` 保持 `"7"`，**未再 bump**
- [ ] 三份渲染产物 diff **零行**
- [ ] 变异跑完已还原且字节一致，工作树干净
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归
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

1. **不要重写 rev1**。rev1 方向正确、模板措辞已通过核验，本 rev 只补钉不住的那一层。
   推翻重写会把已通过的部分重新置于风险中，且会被驳回。
2. **不要再 bump 版本**。`"7"` 已是 rev1 的交付内容；rev2 是同一次交付的返工。
3. **锚点别锁整段**。锁死整段会让后续措辞打磨变成"回归"，那是 B10 的坑，
   本 rev 不能为了修 B20 去踩 B10。判断标准：假想有人把这段压成口号，锚点还在不在。
4. **变异别把活树留脏**。参考 WP-27 `test_bare_status_assignment_reverts_to_worktree`
   的 scratch copytree 做法（原脚本零改动），优于 WP-26 的原地改写。
5. **不要用 `agentic <sub>` 自证**（B14：冻结副本）。用 `PYTHONPATH=src python3.11 -m pytest`。
6. **冻结输入在主仓**：本 brief 与 status 都在 `/Users/admin/vibe/agentic_loop/` 下；
   工作树里 `docs/plans/` 是历史快照，不可作判据（B16/B17）。

### 口径权威源引用

- B20 实测记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B20
- rev1 的实现与用例：commit `359cb1a`（工作树 `/Users/admin/vibe/wp25-protocol-disciplines`）
- rev1 冻结 brief：`docs/plans/2026-09-13-parallel-throughput/WP-25-brief.md`
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
- 变异不留脏的参考实现：WP-27 `tests/test_preflight_status_source.py::test_bare_status_assignment_reverts_to_worktree`

# WP-20: 先封 bootstrap 的 strong 上限，再给 developer 绑异构 provider（A9 → A5，解开 A0）

> 冻结日期 2026-09-14 | 编排者 claude（claude-code, kiroopus） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `git.base_branch`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）

按**严格顺序**先给 bootstrap 路径封上 `strong` 上限（A9），再给 `developer`
角色绑定异构 provider（A5），使双签合并门在正常路径上首次可满足（A0 解开）——
不引入任何「执行者可自我重现」的代理事实（A11/A16 的教训）。

## 为什么顺序不能反（本 WP 的核心约束）

编排者已实证（2026-09-14，纯内存构造，未改 config）：

```
A5 现场（developer 无 binding -> implementer_id=None）
  level = none    meets weak = False           ← A0 现场

A5 修后（developer 绑 provider -> implementer 带 model）
  level = strong  meets weak = True  meets strong = True   ← A9 当场被触发
```

即：**A5 一解开，A9 立刻从「理论缺陷」变成「每次 gate 都走的实际路径」**。
`independence.py:132-139` 的现场是——

```python
if _different_model(consultant_id, compare_against):
    ...
    if bootstrap:
        reasons.append("level=strong-attested: reviewer=orchestrator, attested not engine-proven")
    return "strong", reasons          # ← bootstrap 分支只加了一句 reason，仍然返回 strong
```

`if bootstrap:` 只追加一句自述文本，随后**无条件** `return "strong"`。
于是 reviewer 维度明明「attested not engine-proven」（reason 里自己承认了），
评级却给到最高档并通过 `min_independence="strong"`。

**若先做 A5 再做 A9**，中间态是「双签门放行，但放行依据是一个语义上不成立的
strong」——比 A0 锁死更坏：门看起来通了，实际上没有任何 engine 证明过 reviewer 维度。
故本 WP 内部两步的提交顺序也须是 A9 在前。

## 与 A16 的关系（为什么本 WP 是唯一正路）

用户 2026-09-14 裁定 A16 走**修法 3**：承认 proof 路线不通，独立性证明整体移交 A5。
WP-17（A11，git author 可自我声明）与 WP-18（A16，engine 观测值可被被观测方
自我重现）两次失败指向同一件事——**任何「代理事实」都能被它想证明的那一方
重现或声明**。而「两个不同厂商的模型」这个事实执行者无法自我伪造：它由 engine
在自己的进程里从 `[providers]` 配置解析 binding 得出，`status.json` 里没有对应
可写字段，执行者也不经手该解析。

故本 WP **不新增任何判据**，只做两件事：给已有的 degraded 路径补上语义正确的
上限，再把它的前提（implementer 的 model 可观测）在配置层配齐。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/independence.py`（**仅** A9 的 strong 上限，见下）
  - `.agentic/config.toml`（**仅** `[roles].developer` 与新增 `[providers.<name>]`）
  - `tests/test_independence_bootstrap_strong_cap.py`（新建）
  - `tests/test_role_binding_developer.py`（新建）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/gate/__init__.py`（`_resolve_implementer_identity` 已由 WP-08 修好，**不要动**）
  - `src/agentic_loop/validate_wp_status.py`（A14/A15 的面，另立 WP）
  - `src/agentic_loop/adapters/`（A16 修法 3 = 不再走 proof，**不要**改 `DispatchProof` 或 kimi adapter）
  - `src/agentic_loop/redispatch.py`
  - `src/agentic_loop/wrappers/`（A4/A7/A12/A13 = WP-19 的面）
  - `docs/`（本 brief 与 status 由编排者维护）
  - `.env`、`.context/`、`.agentic/locks/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ `independence.py` 在白名单里**只为 A9 一处上限**。该文件同时含 WP-18 的
> `weak-dispatched` 判据（未合并，且按 A16 修法 3 已不再是正路）——
> **不要删除、不要修改、也不要为它补测试**，它的去向由编排者另行处置。

## 输入

- 依赖的上游 WP 产出：
  - **WP-08**（已合并 `ee74473`）：`_should_populate_implementer` 已放宽到
    `N/A` 或 `ACCEPT`，`_resolve_implementer_identity` 已从 binding 取 model。
    **本 WP 依赖这两处，且不得改动它们。**
- 参考文档：
  - `WP-08-candidate.md` §A9（strong 上限）、§A5（provider 绑定）、§A0（双签门不可满足）、§A16（proof 路线作废的裁定）
  - `.agentic/config.toml` 现有 `[providers.kiroopus]` / `[providers.kirogpt]` 的字段形态（照抄结构，别另造）
  - 全局规范 §5.3（口径单一权威）、§5.8（纯函数优先）

## 交付物清单

### 第一步：A9 —— bootstrap 封 strong 上限（必须先提交）

- [ ] `independence.py` 的 `_different_model` 分支：`bootstrap` 为 True 时
      **返回 `weak` 而非 `strong`**。reason 措辞须如实说明降级原因
      （现有 `level=strong-attested` 那句自述「attested not engine-proven」
      正是降级的理由，改为 `level=weak-attested-models-differ` 一类，
      **不要**保留 `strong-attested` 这个自相矛盾的标签）。
- [ ] 非 bootstrap 路径（`reviewer_id` 非 None，即 reviewer 身份真被 engine 观测到）
      **行为完全不变**，仍可评 `strong`。这是本步的回归边界。
- [ ] `evaluate()` 保持纯函数（无 I/O、时间从参数传入）。现有测试里有 AST
      禁用符号检查，别引入 `os`/`subprocess`/`open`/`Path`。
- [ ] `INDEPENDENCE_LEVELS` 与 `_LEVEL_RANK` **不得改动**（口径单一权威）。
- [ ] `tests/test_independence_bootstrap_strong_cap.py`：
      - bootstrap + degraded + model 不同 → `weak`，且 `meets_threshold(lvl,"strong")` 为 **False**
      - bootstrap + true bootstrap（`implementer_id=None`）+ 有效 attestation → 仍 `weak`（不受本改动影响）
      - **非** bootstrap + model 不同 → 仍 `strong`（回归保护，这条不能被放宽）
      - characterization：改动前后 reasons 列表逐字对照，只允许 strong 那一句变化

### 第二步：A5 —— 给 developer 绑异构 provider（A9 提交之后）

- [ ] `.agentic/config.toml` 新增一个 provider 段，字段结构照抄现有
      `[providers.kirogpt]`（`openai_base_url` / `api_key_env` /
      `identity_model` / `[providers.<name>.selectors]`）。
      `identity_model` 填 kimi 的 canonical 模型名。
- [ ] `[roles].developer` 由 `"kimi"` 改为 `{ adapter = "kimi", provider = "<新段名>" }`。
- [ ] 删除 `[roles]` 段里那条已过时的注释（"绑了也不影响评级……
      `_model_known()` 恒 False"）——WP-08 已把它修好，注释现在是错的，
      留着会误导下一个人。改成如实描述当前行为。
- [ ] **不要**改 `identity_model` 之外的既有 provider 字段，不要动
      `kiroopus`/`kirogpt` 两段。
- [ ] `tests/test_role_binding_developer.py`：
      - `resolve_role_binding("developer")` 返回的 binding 非 None 且
        `identity_model` 非空
      - 该 binding 的 `identity_model` 与 consultant 的**不相同**（异构前提）
      - 用真实配置跑通「A5 现场 → 修后」的对照：`implementer_id` 可构造出
        带 model 的 `AgentIdentity`
      - 端到端：`evaluate()` 在 degraded 路径拿到 `weak`（**不是** `strong`，
        因为第一步已封顶），且 `meets_threshold(lvl,"weak")` 为 True

### 第三步：验证 A0 确实解开

- [ ] 用真实配置复现编排者的对照实验，并把结果写进 `[CONCERNS]` 或报告：
      `none`（A5 前）→ `weak`（A5 后），且 `strong` **不可达**。
- [ ] **不要**为此改动 `min_independence` 的配置值。若本仓 `[review_policy]`
      的 `min_independence` 当前是 `"strong"`，那么封顶后 gate 仍会拒——
      **这是正确的 fail-closed，不是缺陷**。阈值该配多少是编排者/用户的产品决策，
      执行者在 `[CONCERNS]` 里如实指出即可，**不得自行下调**。

## 派发前置（编排者须先处置，非执行者事项）

冻结时主区 `.agentic/config.toml` 存在**未提交改动**（把 provider 从 deepseek
换成 kiroopus/kirogpt 的本地配置调整，早于本 WP 且与本 WP 无关）。本 WP 的
第二步要改同一个文件，若带着这批未提交改动开 worktree，执行者的 diff 会混入
编排者的改动，验收时无法分辨谁改了什么。

**派发前编排者须先做其一**：把那批改动提交（或 stash），使 worktree 起点干净；
或确认 worktree 基线不含它们并在 `git.base_commit` 里锚定。
执行者**不负责**处置这批改动，看到时在 `[CONCERNS]` 里报告即可，不要提交它们。

## 完成定义（DoD）

- [ ] 交付物逐项就绪，A9 与 A5 各有失败→通过的测试
- [ ] **提交顺序**：A9 的提交在 A5 的提交之前（`git log` 可见），不得合并为一个提交
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线**零回归**
      （基线预存 4 个 `test_finalize_merge_triple_sign.py` 失败，fixture 在无
      `main` 分支的临时仓跑 `git checkout main`，与本 WP 无关，**不要修**，见缺陷 B7）
- [ ] 按缺陷 B7：用 `PYTHONPATH=src python3.11 -m pytest` 直接跑工作树代码，
      **不要**用 `agentic quality-gate` 自证（那会跑到另一个仓的快照）
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 不 merge、不 push、不切生产分支
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

> `.agentic/config.toml` 是本仓配置而非生产配置，改它不构成 production_writes。
> 但它影响所有后续 gate 调用，故改动面严格限定在 `[roles].developer` 与
> 新增 provider 段，其余一字不动。

## 附注

### 已知陷阱

1. **顺序是硬要求，不是建议**。A5 先落地会造出「门通了但依据不成立」的中间态，
   比 A0 锁死更坏。两步必须是两个提交，且 A9 在前。
2. **只封 bootstrap，别封非 bootstrap**。`reviewer_id` 非 None 时 reviewer
   身份真被 engine 观测到了，`strong` 是成立的。把它一起封掉是过度收紧，会被驳回。
3. **`strong-attested` 这个标签本身自相矛盾**，别保留。「attested」意味着
   自述而非 engine 证明，那就不该是 strong。改 reason 措辞时如实写降级理由。
4. **不要碰 `min_independence`**。封顶后若 gate 仍拒，那是正确的 fail-closed；
   下调阈值是产品决策，执行者越权。在 `[CONCERNS]` 里报告即可。
5. **不要动 WP-18 的 `weak-dispatched` 判据**。按 A16 修法 3 它已不是正路，
   但它的删除/保留由编排者处置，不在本 WP 范围。看到了别顺手清理。
6. **不要动 `gate/__init__.py`**。`_resolve_implementer_identity` 已由 WP-08
   修好（从 binding 取 model，取不到就返 None 落回弱路径），本 WP 只需在配置层
   把 binding 配上。改它等于返工已验收的 WP-08。
7. **`[roles]` 段那条过时注释必须改**。它现在断言「绑了也不影响评级」，
   而本 WP 正是要证明绑了就有影响。留着错注释比没注释更坏。
8. **不要新增任何代理事实类判据**。A11/A16 两次失败的根因就是代理事实可被
   被证明方自我重现。本 WP 不新增判据，只补上限 + 配齐前提。

### 口径权威源引用

- 独立性级别表：`independence.py` 的 `INDEPENDENCE_LEVELS` / `_LEVEL_RANK`（既有唯一权威，**不得改动**）
- 阈值比较：`independence.meets_threshold()`（既有唯一权威，不另造）
- implementer 身份解析：`gate/__init__.py:_resolve_implementer_identity`（WP-08 既有唯一权威，**forbidden**）
- provider binding 构造：`provider_binding.build_binding()`（既有唯一权威，不另造）

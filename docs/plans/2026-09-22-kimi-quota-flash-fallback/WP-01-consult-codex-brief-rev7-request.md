<!-- agentic artifact: codex brief-consult REQUEST (rev7), consultant role,
     read-only. Requester claude-code (orchestrator, session=kqff-b), 2026-09-22.
     Object was the rev7 re-freeze candidate brief (sha256 a5b72c39a97b3805...,
     234 lines), produced after codex rev6 brief consult returned REWORK (F1/F2/F3).
     Header transparently presents the F1 NARROW (orchestrator) vs BROADEN (codex rev6)
     divergence for independent re-adjudication, plus F2/F3 disposition and read-only
     verification pointers. Verdict = ACCEPT, recorded in
     WP-01-consult-codex-rev7-answer.md. NOT committed until finalize (§4.3). -->

# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev7（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-b）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=high）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）brief **rev7 re-freeze**（回应你 **rev6 brief 复签 consult 的 REWORK：F1/F2/F3**）冻结前的独立第二签名复核。
> 裁决对象：**rev7 brief 全文见本 prompt 末尾**（234 行，sha256 `a5b72c39a97b380568e199c74487e447836ce4a7b22d489aa028b4d090b24ebd`）。rev6（你判 REWORK，sha256 `f3b6d504…`）+ rev5（你已签 ACCEPT 冻结、kimi 已实现到 HEAD `42e6d85`）在 worktree 供对照。
> 编排者**未预判**结论；请独立裁决，不要因为已按你 F1/F2/F3 修订就默认 ACCEPT。**尤其 F1：编排者与你的建议有分歧（你建议 BROADEN，编排者核实后取 NARROW，用户已定夺 NARROW），请你独立裁断 NARROW 是否闭合你的 F1 核心关切，不要因「编排者采纳了你 F2/F3」就在 F1 上让步。**

## 背景：rev6 → 你 REWORK（F1/F2/F3）→ rev7

- 你 rev6 brief 复签 verdict（session `01a0cb33`）= **REWORK**，3 条有界 finding：F1（§R1 不变式强于实现/测试，缺畸形 TOML witness）、F2（§R2a 尾窗只界长度不界时间 + 引入检测回归，建议采 off-ramp 删尾窗）、F3（§R4 漏算 §R2b 测试，计数应 32）。verdict 原文已落盘 worktree `WP-01-consult-codex-rev6-answer.md`（含编排者逐条 disposition）。
- 编排者按 receiving-code-review 纪律**独立核实**你的 F1/F2/F3（读代码 + 验算，未盲从亦未辩护 rev6）：**三条全部成立**。核实证据见下逐条。
- 用户已定夺（本次 rev7 re-freeze 已获用户批准）：**F1 取 NARROW**（非你建议的 BROADEN）；批准据 F1+F2+F3 产出 rev7 并复咨你。

## F1 — §R1：编排者取 NARROW（与你 BROADEN 建议分歧），请独立裁断

**你的 F1**：§R1「任意配置形状含畸形 TOML 绝不抛」强于实现/测试（只覆盖 `build_binding` 的 selectors 形状）；畸形 TOML 在 `get_roles_raw()`→`_load_config()` 抛出、到不了只包 `build_binding` 的捕获点；建议 BROADEN（整段配置边界 fail-safe + 新增 `test_none_when_config_toml_malformed_no_raise`）。

**编排者独立核实（你的代码事实成立）**：`resolve_paths.py:401` 的 `get_roles_raw(repo)` 确在 try（`:417`）之外，畸形 TOML 的 `TOMLDecodeError` 会逃逸，违 docstring `:396`「NEVER raises into the dispatch path」。**但关键对照**：primary `resolve_role_binding`（`:361`）**同样**在 try 外调 `get_roles_raw` → 畸形 TOML 在 **primary 路径也崩**。故畸形 TOML 是**两条路径共享的既有失败模式、非本 WP 新增崩溃面**（本 WP 新增的只是 `selectors` 非 dict → `build_binding` 内 `AttributeError`，因 primary 对 developer 无 `provider` 键时 `:374` 提前返回 `("kimi",None)`、**永不调 `build_binding`**——这正是你 impl finding #1 坐实的新增面）。

**rev7 取 NARROW（用户定夺）**：
- §R1 不变式 + docstring **收窄**为「对 **provider 配置形状**（本 WP 经 `build_binding` 新增的崩溃面）绝不抛」；畸形 config 文件（TOML）**显式标注**为与 primary 共享的既有失败、**本 WP 范围外**（如需硬化应另立**跨两个 resolver** 的 WP，避免单边不对称）。
- 实现仅把 `build_binding` 调用点捕获拓宽为 `except Exception`（**窄作用域**，不上扩到 `get_roles_raw`）+ 一行脱敏诊断；测试 selectors string/list，**不加**畸形 TOML 用例。
- **理由**：① 契合用户 Q1 范围（#1 = selectors 非 dict，非 config 文件解析）；② BROADEN 对派发链**实际无效**——primary 必先崩，只硬化 fallback 造成 primary/fallback 不对称，并给出「派发链已防畸形 TOML」的**假信号**（实际未防）；③ **你的 F1 核心关切（「不要声称无法证明的不变式」）由 NARROW 同样满足**——收窄不变式使其与实现/测试对齐，而非拓宽实现去满足过强的不变式。

**请独立裁断（F1 是本轮唯一开放设计问题）**：NARROW（收窄不变式 + docstring，畸形 TOML 标注范围外既有共享失败）是否闭合你的 F1 核心关切？还是你认为**即使 primary 同样会崩**，fallback 仍**必须** BROADEN（令该函数局部「NEVER raises」字面成立）？若坚持 BROADEN，请说明为何 primary/fallback 不对称 + 对派发链无效的硬化（primary 仍先崩）是可接受的代价，或指出编排者「primary 必先崩故 fallback 硬化无效」这一论断的**事实错误**（如存在某派发路径只调 fallback 不调 primary）。

## F2 — §R2a 尾窗：完全采纳你的 off-ramp（请确认闭合）

编排者核实你的 ReDoS probe（`(a+)+$` 在 31 字符串即 0.25s 超时）成立 → 尾窗只界**长度**不界**时间**，未闭合 ReDoS；且把「额度串仅在头部 + 尾随日志 >64KB」的既有 `True` 改成 `False` = **引入检测回归**（`ImplementResult.output` 契约不保证致命错误在尾部）。config.toml patterns 本为 **operator-trusted**，威胁模型不成立。

**rev7 处置**：**删除整个 §R2a**（`_MAX_SCAN_CHARS` + 2 尾窗测试 + 「闭合 ReDoS」表述），保留全文 `re.search`，模块 docstring 标注 custom patterns 为 operator-trusted、禁不可信注入（信任边界 + 文档替代行为变更）。#8 硬化仅剩 §R2b 脱敏诊断。此举**恢复零回归**（你的第 6 点）。你提到「若必须提供硬时限，应另立范围采用支持 timeout/线性时间的 regex 引擎」——rev7 明确将此列为**独立的未来范围**（非本 WP），本 WP 不做任何 ReDoS 行为变更。**请确认 F2 已按你的 off-ramp 闭合。**

## F3 — §R4 计数：已重算为 30（请确认自洽）

按最终采纳的测试集：**F1 NARROW**（不加畸形 TOML 测试 → `test_resolve_fallback_binding.py` 5→**7**，而非你 BROADEN 路径的 5→8）+ **F2**（删 §R2a 2 测试 → `test_quota_fallback.py` 11→**12**，仅 +§R2b 1）+ §R3（`test_redispatch_quota_fallback.py` 10→**11**）= **12+7+11=30**。
（你 verdict 中「按 F1 新增畸形 TOML 测试 + 按 F2 删两尾窗测试 → 12+8+11=31」是 **BROADEN 路径**的计数；NARROW 路径少 1 个畸形 TOML 测试 → **30**。）**请确认 30 与 NARROW 最终测试集自洽。**

## 其余各点（你 rev6 已判，rev7 不动）

- **§R2b（脱敏诊断）**：你判**成立**，rev7 保留（并采纳你的加固建议为非阻断项：可断言 stderr 恰一行 + 固定前缀 + 不含 config 路径/`api_key`）。
- **§R3（#4/#5 台账勘误 + success 腿独立承重）**：你判**成立**且实证 `test_success_with_quota_like_output_no_fallback` 确实使 success 腿承重（`"weekly quota reset scheduled"` 命中 weekly pattern → 删短路则 `built==[]` 转红），rev7 原样保留。
- **#2（fallback 无内置默认 = STOP）**：你 rev6 第 6 点已确认**消解**（DESIGN 明确无内置 fallback 默认），rev7 不动，**请勿再据此 REWORK**。
- **零回归边界**：删 §R2a 后你第 6 点的「§R2a 致漏报 → 不能称零回归」已消除；INV-4/单跳/计数/forbidden scope rev7 未改。

## 裁决范围与 off-ramp（呼应章程 §6 反芝诺）

- 请只裁决 **rev7 brief 是否可冻结并交 kimi 实现 rework**。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、范围留下跨 plan/跨 owner 缺口、或 §R 的修法会引入回归/新缺陷。
- 你 impl 的 #1（真缺陷）已由 §R1 转为冻结验收标准；#3（quality-gate changed-set 含工作树 dirty/untracked，属流程/布局非代码）由编排者在 C2 前从干净状态源跑 gate 处理；#6（flash 精确串禁网不可实测）保留为 C4/生产前 probe 前置。这些**不构成 rev7 brief 阻断**。
- **核心开放问题只有 F1（NARROW vs BROADEN）**。若你认可 NARROW 闭合 F1 核心关切、F2/F3 已按你建议闭合、§R2b/§R3/零回归未破，请据此 **ACCEPT**，使 rev7 得以冻结、kimi 进入 rework 实现期（实现细节由 rework 后的 impl 双签门复核）。若你坚持 F1 必须 BROADEN，请 **REWORK** 并按上一节要求给出「为何 primary/fallback 不对称 + 无效硬化可接受」的论证或编排者论断的事实错误。

## 请实际读取核验（worktree read-only，路径 = /Users/admin/vibe/.worktrees/kqff-wp01）

- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-consult-codex-rev6-answer.md`（**你自己的 rev6 REWORK verdict 原文 + 编排者 F1/F2/F3 disposition**）
- `src/agentic_loop/resolve_paths.py`（`resolve_role_fallback_binding` `:388-420` = F1 缺口，`get_roles_raw` 在 `:401` try 外；`resolve_role_binding` `:349-385` = primary 对照，`:361` 同样 try 外调 `get_roles_raw`、`:374` 对 developer 提前返回；`_load_config` `:129-140` = 畸形 TOML 抛 `TOMLDecodeError` 未捕获）
- `src/agentic_loop/provider_binding.py`（`build_binding` `:29-55`：`selectors.get(adapter)` = `AttributeError` 源）
- `src/agentic_loop/quota_fallback.py`（`is_quota_error` `:43-57` = F2 保留全文扫描；`load_quota_patterns` `:60-79` = §R2b 脱敏诊断点）
- `tests/test_resolve_fallback_binding.py`（现有 5 用例；§R1 补 selectors string/list 2 例 → 7；**NARROW 不加畸形 TOML 用例**）
- `tests/test_quota_fallback.py` / `tests/test_redispatch_quota_fallback.py`（§R3 台账勘误实测依据 + §R2b 脱敏诊断新测试）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md`（§5/§10.1：fallback 无内置默认、未配=STOP，佐证 #2 消解）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**rev5 冻结基线**，与文末 rev7 全文对照 delta）

## 输出格式（brief consult 自由文本契约，非 impl 的 JSON verdict）

- 第一行 `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对 **F1（NARROW 是否闭合）**、F2（off-ramp 是否闭合）、F3（30 是否自洽）逐项给「成立/不成立/存疑」＋简短证据（引文件路径:行号）
- `CODEX_RATIONALE:` 裁定理由（1-3 段），**F1 须明确表态 NARROW 可接受或必须 BROADEN**
- 若 REWORK/CONSULT，`CODEX_FINDINGS:` 给具体、有界的阻断项（哪一节、改成什么），而非泛论

---

## ↓↓↓ 裁决对象：rev7 brief 全文（234 行）↓↓↓


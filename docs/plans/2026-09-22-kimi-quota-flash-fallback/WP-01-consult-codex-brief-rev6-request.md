<!-- agentic artifact: codex brief-consult REQUEST (rev6), consultant role,
     read-only. Requester claude-code (orchestrator, session=kqff-b), 2026-09-22.
     Object was rev6 brief (sha256 f3b6d504..., 229 lines). Verdict recorded in
     WP-01-consult-codex-rev6-answer.md. NOT committed until finalize (§4.3). -->

# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev6（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-b）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=high）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）brief **rev6 re-freeze**（回应你实现后双签 consult 的 REWORK）冻结前的独立第二签名复核。
> 裁决对象：**rev6 brief 全文见本 prompt 末尾**（229 行，sha256 `f3b6d5044d351281efaff9d092fdb24df9560638b129dbd1b38c8c8a93ec7c13`）。rev5（你已签 ACCEPT 冻结、kimi 已实现到 HEAD `42e6d85`）在 worktree 供对照。
> 编排者**未预判**结论；请独立裁决，不要因为已按你 findings 修订就默认 ACCEPT。若仍有 brief 级阻断项，请 REWORK 并给具体有界 finding。

## 背景：这不是常规 brief 冻结，而是「实现后双签 REWORK → re-freeze」

- kimi 已按 rev5 实现 WP-01（HEAD `42e6d85`，5 提交，7 allowed 文件，+619/-2）。实现后双签：**review=ACCEPT（编排者）/ consult=REWORK（你，session `01a0c9dd`，8 findings）** → 双签未凑齐。
- 编排者逐条独立复核你的 8 findings（未盲从、亦未辩护自己的 ACCEPT），裁定已落盘 worktree `WP-01-consult-codex-impl-rev1-answer.md`（含你的原始 JSON verdict + 编排者 ADJUDICATION）。
- 用户已定夺（本次 re-freeze 已获用户批准，满足 brief Re-freeze 规则「第 3 次及以后须经用户批准」）：
  - **Q1**：派 kimi rework 修 **#1**（真缺陷）+ 一并硬化 **#8**。
  - **Q2**：批准 brief re-freeze rev5→rev6 修正 **#4/#5** oracle 台账 + 折入 #1/#8 rework 验收标准，经你 brief consult 复签后重新冻结。
- rev6 = 据此产出的 re-freeze：新增权威 `## Rework rev6 闭环 spec`（§R1 #1 fail-safe 拓宽 / §R2 #8 硬化 / §R3 #4#5 台账勘误+新承重测试 / §R4 计数与提交），并就地更正 §3 与承重映射表 INV-1/INV-3/INV-5 的错误台账。

## ⚠️ 关于你 impl finding #2（编排者 consult prompt 措辞错误，rev6 不采纳，请勿据此再 REWORK）

你在 impl REWORK 的 finding #2 判「缺省 fallback provider 未回落内置默认」为 major，并引用了「本次请求中的最新硬约束」。**那是编排者上一轮 impl-consult prompt §1 的措辞错误**：编排者误写「fallback provider 缺省回落内置默认」。事实以**冻结 brief + DESIGN 为准**：

- **只有 quota patterns 有内置默认（`DEFAULT_QUOTA_PATTERNS`）**；**fallback provider 没有内置默认**——未配 `fallback_provider` → `resolve_role_fallback_binding` 返回 None → 额度失败即 STOP（零回归，正是设计意图；见 rev5/rev6 brief 交付物清单 resolve_paths 项 + DESIGN §5/§10.1）。
- 故 kimi 的实现（未配 fallback = None = STOP）**正确**，rev6 **不新增**任何 fallback provider 内置默认。编排者已更正 consult prompt 措辞。
- **请将 finding #2 视为已消解（对冻结 brief 不成立），不要因「无内置默认」再判 REWORK。** 若你认为「未配 fallback 即 STOP」这一设计本身有问题，请明确以 brief/DESIGN 级设计异议提出（而非以编排者 prompt 措辞为据）。

## 请复核 rev6 的这些点（brief 级，非实现级——rework 实现尚未发生）

1. **§R1（#1 fail-safe 拓宽）是否闭合你 impl finding #1**：你实证 `resolve_role_fallback_binding` 只 `except ProviderConfigError`，漏 `build_binding` 对 `selectors` 非 dict 抛的 `AttributeError`（编排者独立 probe 亦坐实：string-selectors → fallback 抛 AttributeError，而同配置 primary `resolve_role_binding` 返回 `("kimi",None)` 不受影响 = 本 WP 新增崩溃面）。rev6 §R1 要求拓宽为 `except Exception`（或整段 try）→ None，并补 `test_none_when_selectors_is_string_no_raise` / `test_none_when_selectors_is_list_no_raise`。**这是否足以让 docstring「NEVER raises into the dispatch path」字面成立？拓宽到 `except Exception` 是否有你担心的过度吞噬风险（掩盖真正的编程错误），需要在 spec 里加约束（如仅吞已知形状 / 保留脱敏诊断）吗？**
2. **§R2a（#8 ReDoS 尾窗限界）设计是否成立、是否引入检测回归**：这是编排者对你 minor finding #8a 的**新设计决策**，最需要你独立审视。方案：`is_quota_error` 由全文 `re.search` 改为扫 `output[-_MAX_SCAN_CHARS:]`（尾窗，默认 65536），理由是派发致命/额度信息在输出尾部，尾窗限界最坏正则工作量。**取舍：>64KB 输出中仅出现于被丢弃头部的额度串会漏检。你认可这个取舍吗？还是尾窗构成不可接受的检测回归（应改：全文扫描 + 别的 ReDoS 缓解，如更宽松的长度上限 / 仅对 config 覆盖 patterns 限复杂度 / 预编译）？** 若你认为 #8a 作为 minor 非阻断项**根本不该引入行为变更**，请直说——编排者可降级为「仅文档标注 config patterns 为 operator-trusted，不改扫描」。
3. **§R2b（#8 脱敏诊断）**：`load_quota_patterns` 回落 DEFAULT 前打印一行仅含异常类名（`type(exc).__name__`）的 stderr 诊断（绝不含 config 原文/路径/密钥）。是否满足你 finding #8b「静默吞配置故障缺诊断」？脱敏边界（只打类名）够吗？
4. **§R3（#4/#5 台账勘误）事实是否正确**：编排者实测坐实——(#4) 删裸词 `\bquota\b` 后 `test_matches_english_quota_terms`（`"quota exceeded for this key"`）仍绿（被语境正则 `(balance|credit|…|quota|…)\W{0,20}(insufficient|exceeded|…)` 命中），真正承重裸词是 `额度`（删之 `test_matches_chinese_quota_terms` 的 `"错误：账户额度不足"` 转红）；(#5) `test_success_no_fallback` 输出 `"done"` 非额度串，删短路仍绿（等价 witness），仅 dry_run 腿承重。rev6 更正台账 + 新增 `test_success_with_quota_like_output_no_fallback`（成功但输出含额度词 → 短路优先不回退；删短路则转红）使 success 腿独立承重。**这两处勘误是否与你 impl findings #4/#5 一致？新测试是否真的让 success 腿承重？**
5. **§R4 计数**：`test_quota_fallback.py` 11→13、`test_resolve_fallback_binding.py` 5→7、`test_redispatch_quota_fallback.py` 10→11，合计新增 26→31。是否与 §R1/§R2/§R3 新增用例数自洽？
6. **零回归边界未破**：rev6 未改 INV-4（主档 `developer` binding 仍 `("kimi",None)`）、未改 `redispatch.py`/`config.toml`（§R 明确本轮不动）、未碰 forbidden_paths；#7（你确认的零回归）rev6 不动。

## 裁决范围与 off-ramp（呼应章程 §6 反芝诺）

- 请只裁决 **rev6 brief 是否可冻结并交 kimi 实现 rework**。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、范围留下跨 plan/跨 owner 缺口、或 §R 的修法会引入回归/新缺陷。
- 你 impl 的 #1（真缺陷）已由 §R1 转为冻结验收标准；#3（quality-gate changed-set 含工作树 dirty/untracked，属流程/布局非代码）由编排者在 C2 前从干净状态源跑 gate 处理，不属 brief/kimi rework；#6（flash 精确串禁网不可实测）保留为 C4/生产前 probe 前置。这些**不构成 rev6 brief 阻断**。
- 若 §R1-§R4 sound、#4/#5 勘误事实正确、#2 已按上述消解，请据此 ACCEPT，使 rev6 得以冻结、kimi 进入 rework 实现期（实现细节由 rework 后的 impl 双签门复核）。若 §R2a 尾窗取舍你认为不可接受，请 REWORK 并给出你认可的替代缓解（有界、具体）。

## 请实际读取核验（worktree read-only，路径 = /Users/admin/vibe/.worktrees/kqff-wp01）

- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-consult-codex-impl-rev1-answer.md`（**你自己的 impl REWORK verdict 原文 + 编排者 ADJUDICATION**，8 findings 对照）
- `src/agentic_loop/resolve_paths.py`（`resolve_role_fallback_binding` L388-420 = #1 缺口；`resolve_role_binding` L349-385 = primary 对照）
- `src/agentic_loop/provider_binding.py`（`build_binding` L29-55：`selectors.get(adapter)` = AttributeError 源）
- `src/agentic_loop/quota_fallback.py`（`is_quota_error` L43-57 = #8a；`load_quota_patterns` L60-79 = #8b）
- `tests/test_resolve_fallback_binding.py`（现有 5 用例；#1 测试盲区：只覆盖缺字段 ProviderConfigError，未覆盖 selectors 非 dict）
- `tests/test_quota_fallback.py` / `tests/test_redispatch_quota_fallback.py`（#4/#5 台账勘误的实测依据：`test_matches_english_quota_terms`/`test_matches_chinese_quota_terms`/`test_success_no_fallback`/`test_dry_run_does_not_fallback_even_on_quota_output`）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md`（§5/§10.1：fallback provider 无内置默认、未配=STOP 的设计依据，佐证 #2 消解）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**rev5 冻结基线**，与文末 rev6 全文对照 delta）

## 输出格式（brief consult 自由文本契约，非 impl 的 JSON verdict）

- 第一行 `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对上列 6 点逐项给「成立/不成立/存疑」＋简短证据（引文件路径:行号）
- `CODEX_RATIONALE:` 裁定理由（1-3 段）
- 若 REWORK/CONSULT，`CODEX_FINDINGS:` 给具体、有界的阻断项（哪一节、改成什么），而非泛论

---

## ↓↓↓ 裁决对象：rev6 brief 全文（229 行）↓↓↓


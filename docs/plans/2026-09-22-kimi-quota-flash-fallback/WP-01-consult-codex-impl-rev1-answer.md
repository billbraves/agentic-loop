# WP-01 codex 实现后双签 consult — 第二签名（impl rev1）

> 顾问：codex-cli（provider kirogpt / gpt-5.6-sol / reasoning=high / --sandbox read-only）
> session `01a0c9dd-212f-7e41-a3f9-9027aa102acc` | CODEX_EXIT=0 | 记录 2026-09-22T16:34:42Z
> 坐标：base `f89d36c` → HEAD `42e6d85`；worktree `/Users/admin/vibe/.worktrees/kqff-wp01`
> prompt = 请求头（WP-01-consult-codex-impl-rev1-request.md）+ 703 行 delivery diff（git f89d36c...42e6d85 可复现）
> **裁决：REWORK** —— 双签未凑齐（review=ACCEPT / consult=REWORK）。codex 原始 JSON verdict：

```json
{
  "decision": "REWORK",
  "rationale": "独立只读核验 base f89d36cedb9b0c79d9574511329e8b83cd6c86f3 → HEAD 42e6d85f6c6751c754b1985a1a1ff580e7099e68：确为 5 个提交、7 个 allowed 文件、619 insertions/2 deletions；按要求未运行 pytest。INV-4/INV-5 主控制流成立：只读解析得到 resolve_role_binding(\"developer\") == (\"kimi\", None)；.agentic/config.toml:31-36 的 [providers.kirogpt] 在 diff 中全为 context；redispatch.py:435-453 的 circuit-breaker 位于 fallback 解析/派发（538-543）之前；wrapper 在 redispatch.py:285-303 只进行一次 fallback 派发，最终成功后仅由 redispatch.py:564-574 写一次 count+1。然而存在未闭环的硬约束：resolve_role_fallback_binding 并非对所有非法 provider 配置 fail-safe，且缺省 fallback provider 没有内置默认；当前 quality-gate 也没有有效绿证据。因此不能给第二签名 ACCEPT。",
  "findings": [
    {
      "severity": "major",
      "title": "INV-3 对非法 provider 配置并非一律 None 不抛",
      "detail": "resolve_role_fallback_binding 仅捕获 build_binding 抛出的 ProviderConfigError。provider_cfg.selectors 若为字符串，build_binding 在 selectors.get(adapter) 抛 AttributeError；整个 TOML 畸形时，异常更早从 get_roles_raw/_load_config 逸出。只读内存探针分别得到 ValueError 与 AttributeError，违反函数文档和 brief 的“provider 段非法 → None，绝不抛到派发主链”。需扩充形状校验或覆盖完整解析/构造边界，并增加 malformed TOML、selectors 非 dict 等负例。",
      "evidence": "src/agentic_loop/resolve_paths.py:400-420；src/agentic_loop/resolve_paths.py:129-140；src/agentic_loop/provider_binding.py:29-33；docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:69,152"
    },
    {
      "severity": "major",
      "title": "缺省 fallback provider 未回落内置默认",
      "detail": "最新硬约束要求 quota patterns 与 fallback provider 均可由 config 覆盖，缺省时 fail-safe 回落内置默认。实现只有 DEFAULT_QUOTA_PATTERNS；fallback_provider 缺失、role 非 dict 或 provider 段缺失时直接返回 None，主链随即不重试。虽然 frozen brief 把“未配置即 STOP”作为零回归行为，但它低于本次请求中的最新硬约束，需实现内置 fallback 默认或由产品方明确撤销该硬约束后重新冻结。",
      "evidence": "src/agentic_loop/quota_fallback.py:20-39,61-79；src/agentic_loop/resolve_paths.py:403-414；src/agentic_loop/redispatch.py:290-292；.agentic/config.toml:38-46,57"
    },
    {
      "severity": "major",
      "title": "quality-gate 当前未闭环，finalize 不会自动使现有 feature worktree 有效转绿",
      "detail": "失败确实不是 7 个代码文件的缺陷，而是 gate 把工作树 dirty/untracked 文件也加入 changed set：当前有修改的 WP-01.status.json 和未跟踪的 WP-01-impl-report-rev1.md，二者均不在 allowed_paths。仅在另一 worktree 提交 finalize status 不会清除本 feature worktree 的 dirty/untracked 状态；即使最终在干净 integration checkout 上得到 post-finalize PASS，也发生得太晚且 changed code 可能为空，不能替代 brief 要求的 pre-review quality-gate。C2 前需从干净、正确状态源运行 gate并记录真实绿证据，或修正控制面文件布局。",
      "evidence": "src/agentic_loop/wrappers/quality-gate.sh:39-46,74-83；docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:78-84；当前 git status：M docs/plans/.../WP-01.status.json，?? docs/plans/.../WP-01-impl-report-rev1.md"
    },
    {
      "severity": "minor",
      "title": "Q1：等价正向 witness 可接受，但 frozen 映射需 erratum",
      "detail": "对现有英文 fixture，“quota exceeded for this key”同时命中反向语境 pattern quota→exceeded，所以删除独立的 \\bquota\\b 确实不转红；删除“额度”使中文正例转红，可以作为“删除某个正向 pattern”这一变异方向的等价 witness。结论：需 re-freeze erratum，把精确预期改为删除“额度”等具有唯一 witness 的 pattern；本项本身不是实现阻断，但不能保留事实错误的 oracle 台账。",
      "evidence": "src/agentic_loop/quota_fallback.py:23-27；tests/test_quota_fallback.py:13-25；docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:133-136,148-151"
    },
    {
      "severity": "minor",
      "title": "Q2：当前 success fixture 等价，但 success 短路没有独立承重",
      "detail": "删除 dry_run/result.dispatched 短路后，现有 success fixture 输出“done”，会在 not is_quota_error 分支返回相同结果，因此不会转红；dry_run 的 quota fixture会转红。实现本身在 redispatch.py:286 正确保障成功不回退，但“成功输出永远不含 quota 文本”不是类型契约，可用 dispatched=True、output=\"quota exceeded\" 的 stub 直接承重。结论：需 re-freeze erratum，将现有映射改为“dry_run 红；当前 success fixture 等价”，并建议补充 quota-like successful output 用例；本项单独不构成代码阻断。",
      "evidence": "src/agentic_loop/redispatch.py:285-289；tests/test_redispatch_quota_fallback.py:49-59,99-108；docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:137,154"
    },
    {
      "severity": "minor",
      "title": "flash model id/selector 必须在启用前做受控实测",
      "detail": "仓内只证明 v4-pro 的命名规律，没有独立来源证明 deepseek-v4-flash/deepseek/v4-flash 是当前 DeepSeek API 与 kimi 注册表接受的精确字符串；现有测试只是复述配置字面值。禁网 WP 下可作为残余风险，但配置合入即启用 fallback，因此在 merge/生产启用前必须用非生产凭据执行一次最小 probe，并把实际 id/selector 与结果纳入证据；失败则先修正配置和断言。",
      "evidence": ".agentic/config.toml:38-46；docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md:229-235；docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:109；src/agentic_loop/init_cmd.py:42-46"
    },
    {
      "severity": "note",
      "title": "Q5/Q6 其余零回归、单跳与日志边界成立",
      "detail": "主 binding 仍为 (kimi, None)，fallback identity 不进入 independence；[providers.kirogpt] 无增删。已列举的 role 非 dict、缺 fallback_provider、provider 缺失、缺 anthropic_base_url 路径均返回 None。单跳 wrapper 不写 status/锁/count，flash 再失败只返回；count 仅最终成功后 +1。REDISPATCH_QUOTA_FALLBACK 仅打印 provider 名，不打印 key；fallback output 经既有 KimiAdapter redact_env_value 处理。DESIGN 明确 probe 硬耗尽为范围外，故 probe 先 STOP 不是本 WP 回归。",
      "evidence": ".agentic/config.toml:31-36,55-59；src/agentic_loop/resolve_paths.py:349-385；src/agentic_loop/redispatch.py:285-303,435-453,538-576；src/agentic_loop/adapters/kimi.py:107-110,128-136；docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md:159-169"
    },
    {
      "severity": "minor",
      "title": "自定义正则存在配置级 ReDoS 风险，宽异常捕获可接受但缺诊断",
      "detail": "默认 patterns 以短 alternation 和有界跨度为主，未见明显灾难性回溯；但 config 可提供任意 Python regex，is_quota_error 对完整 output 直接 re.search，误配如嵌套量词可阻塞 redispatch。配置属于受信任项目输入，暂不作为本次 blocker，建议后续限制扫描尾部长度并在加载时验证/记录坏 pattern。load_quota_patterns 的 except Exception 会吞 PermissionError、解析错误乃至内部缺陷；为保持派发 fail-safe 可以接受，但至少应输出脱敏诊断，避免静默隐藏配置故障。",
      "evidence": "src/agentic_loop/quota_fallback.py:20-39,42-57,61-79"
    }
  ]
}
```

---

## 编排者对 codex 8 findings 的独立复核裁定（claude/Reviewer，不信 chat、亲验）

> 双签结果：**review=ACCEPT（编排者，不完整）/ consult=REWORK（codex）→ 未凑齐**。
> codex REWORK 由 finding #1 单独成立（下述），与 #2（我 prompt 错误）无关。

- **#1 [major] 成立 —— 真缺陷，我的 C1 ACCEPT 漏了它。** 我独立 probe 坐实：`selectors` 误配为字符串时
  `resolve_role_fallback_binding` 抛 `AttributeError`（`build_binding` L32 `selectors.get` 而 `except` 只接
  `ProviderConfigError`），而 primary `resolve_role_binding` 同配置返回 `('kimi', None)` 不受影响 → 这是**新增崩溃面**，
  违反 docstring「NEVER raises」+ **冻结 brief L69「provider 段…非法 → None，绝不抛到派发主链」** + INV-3。
  malformed-TOML 一例 primary 也抛（预存、非本 WP 回归）。现有 `test_none_when_provider_cfg_invalid_no_raise`
  只覆盖 missing-anthropic_base_url（ProviderConfigError），未覆盖 selectors 非 dict 形状 → 测试盲区。
  **裁定：需 kimi rework** —— 拓宽 fail-safe（selectors 非 dict / 任意 build_binding 异常 → None）+ 补形状负例。
- **#2 [major] 不成立 —— 是我 consult prompt §1 的措辞错误，非实现缺陷。** 冻结 brief L69/L131 + DESIGN L113/L141
  明确「未配 fallback_provider → None → 额度失败即 STOP」，**只有 quota patterns 有内置默认（DEFAULT_QUOTA_PATTERNS），
  fallback provider 没有**（未配=STOP=零回归，正是设计意图）。我 prompt 写「fallback provider 缺省回落内置默认」是错的，
  codex 被误导。**裁定：实现正确，无需改；我更正 consult prompt。**
- **#3 [major] 成立 —— 流程/布局缺口，非代码缺陷。** quality-gate.sh L41-46 的 changed set 含未暂存 dirty + untracked，
  故编排者回填的 `M status.json` + `?? report/review` 触发 "changed path outside allowed scope"；7 个代码文件本身全绿。
  codex 更尖锐指出：在别的 checkout 提交 finalize status 不会清掉**本 feature worktree** 的 dirty。**裁定：C2 前须从干净状态源
  跑 gate 并记真实绿证据，或按方案1 等价变通。**
- **#4/#5 [minor] 成立（文档级）。** codex 确认我 #2a/#2b 判断（等价 witness 可接受、非代码阻断），但冻结 brief 承重映射表
  存在**事实错误的 oracle 台账**（「删 \bquota\b→红」实为不红；「success/dry_run 红」实为仅 dry_run 红）。**裁定：需 re-freeze
  erratum 修正映射表**（brief L25：rev≥3 需用户批准）。
- **#6 [minor] 成立（残余风险）。** flash 精确串禁网不可实测；config 合入即启用 fallback，故 merge/生产启用前须用非生产凭据
  做一次最小 probe 核实 id/selector。**裁定：作为 C4/生产前的显式前置，非本 WP 代码阻断。**
- **#7 [note] 确认零回归。** 主 binding 仍 (kimi,None)、kirogpt 无增删、单跳不写 status/锁/count、日志只打 provider 名不打 key、
  fallback output 经 redact_env_value → 与我 C1 复核一致。
- **#8 [minor] 硬化建议（非阻断）。** config 可注入任意 regex → is_quota_error 对全文 re.search 有配置级 ReDoS 面；
  load_quota_patterns 的 except Exception 静默吞配置故障、缺脱敏诊断。**裁定：与 #1 同属 fail-safe 主题，可在 rework 一并硬化。**

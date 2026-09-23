# WP-01 kimi 额度回退 deepseek-flash — brief 第二签名咨询请求 rev1（codex，read-only）

> 请求者 claude-code（编排者，session=kqff-a3）｜2026-09-22｜咨询者 codex（consultant, gpt-5.6-sol via kirogpt，read-only sandbox，reasoning_effort=medium）
> 用途：WP-01（kimi 套餐额度不足时自动单跳回退 `deepseek-v4-flash`，配置驱动、零回归）**brief 冻结（DRAFT→APPROVED）前**的独立第二签名。
> 按章程 §3.2/§0.1，本 WP 非信任根（不碰 independence/gate/adapters/kimi.py），consult 非强制；但派发路径较敏感（`redispatch.py:main()` 是全框架唯一派发入口的接线点），DESIGN §10.3 与 IMPLEMENTATION-PLAN Task A4 建议过一次低成本 codex consult。
> 编排者**未预判**结论；请独立裁决，不要因为 brief 由编排者起草就默认 ACCEPT。

## 你要裁决什么

对内联的 **WP-01 brief**（`docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`，一份**设计规格 + TDD 验收标的**）给出 `ACCEPT` / `REWORK`（含具体阻断项）/ `CONSULT`。

**核心裁决问题**：这份 brief 的**范围（7 allowed / 11 forbidden）＋不变式（主档零回归、单跳到底、fail-safe 模式加载、正向命中才回退、计数不双计）＋oracle 四证据**，是否**足以强制**执行者产出一个**真正零回归、单跳到底、不掩盖真实错误**的额度回退能力——而不是引入下面的隐患：

- **隐患 A**（主档语义漂移）：`developer` 由裸 string 改 dict 后，`resolve_role_binding("developer")` 若不再返回 `("kimi", None)`，会连带影响独立性评级（`independence.py` 用 `executor.tool` + `identity_model`）与 `KimiAdapter` 的注入路径（binding 非空即触发 `_temp_config`），最终把主派发路径从「原生 kimi 全局默认」漂到「DeepSeek flash 注入」。
- **隐患 B**（掩盖真实错误）：若 `is_quota_error` 的默认模式清单过宽（如把 `error` / `failed` / `429` 之外的 HTTP 码也当额度），普通失败会被误判为额度问题而触发 flash 重派，掩盖真错误（违反 AGENTS.md §7「不得弱化/隐藏失败」）。
- **隐患 C**（无限重试/三跳）：若 `_dispatch_with_quota_fallback` 在 flash 也额度失败时**再**回退到主档或另一档，就变成多跳链，违反 DESIGN §2 用户决策「单跳 kimi→flash；flash 也额度失败 → REDISPATCH_STOP 交人工」。
- **隐患 D**（计数双计/绕过 circuit-breaker）：若回退路径额外 +1 `redispatch_count`，或绕过 `REDISPATCH_MAX` 检查，会让「一次额度回退」被当作「一次 rework 重派」计入熔断，导致后续正常 rework 提前熔断。
- **隐患 E**（密钥泄漏）：若 `is_quota_error` 或日志在**未脱敏**的输出上跑，或 `load_quota_patterns` 的 fail-safe 回落把 config 解析异常连同密钥片段一起抛进主链，会违反 AGENTS.md §6 密钥边界。

你拥有本 worktree（`/Users/admin/vibe/.worktrees/kqff`）read-only 访问，请**实际读取**被引用文件核验：

- `docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md` §2/§3/§4/§5/§6/§7/§8/§10/§11（用户决策、现状、架构、数据流、错误处理、config、测试计划、待确认、范围外）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md` Phase B（B1-B6 完整 TDD 代码与预期输出）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md`（**裁决对象**）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json`（scope/risk/evidence.brief）
- `docs/plans/2026-09-22-kimi-quota-flash-fallback/HANDOFF.md`（环境/纪律提醒）
- `src/agentic_loop/redispatch.py`（`_dispatch` / `main()` 现状；确认唯一派发入口)
- `src/agentic_loop/resolve_paths.py`（`resolve_role_binding` / `get_roles_raw` / `_first_candidate` / `get_providers` / `_load_config` / `main_repo` 是否为既有符号）
- `src/agentic_loop/adapters/kimi.py`（`_temp_config` / `_run` / `redact_env_value` 现状，确认不需改）
- `src/agentic_loop/provider_binding.py`（`build_binding` / `ProviderBinding` / `ProviderConfigError`）
- `src/agentic_loop/independence.py`（**只读核验**：确认 developer 切 flash 是否真不影响评级；本 WP forbidden 改此文件）
- `.agentic/config.toml`（当前 `[roles] developer` 形态、`[providers.kirogpt]`/`[providers.kiroopus]` 段结构参考）

## 请逐项复核（给「充分/不充分/部分」＋证据）

1. **主档零回归（隐患 A）是否被 brief 强制**：
   - brief 「附注.已知陷阱」明写「`developer` 由裸 string 改 dict 后，`resolve_role_binding("developer")` 仍须返回 `("kimi", None)`」；
   - IMPLEMENTATION-PLAN B5 Step 3 `test_project_config_primary_developer_stays_native` 直接断言 `adapter_name == "kimi"` 且 `binding is None`；
   - 对照 `src/agentic_loop/resolve_paths.py:resolve_role_binding` 与 `_first_candidate`：dict 形态无 `provider` 键时，是否**确实**返回 `(adapter, None)`？此断言是否**足以**封堵隐患 A？若不足，缺什么？

2. **正向命中才回退（隐患 B）是否被 brief 强制**：
   - brief Acceptance tests §1 要求「`is_quota_error("quota exceeded") → True` 的同时，`is_quota_error("ModuleNotFoundError") → False`」；
   - IMPLEMENTATION-PLAN B1 Step 1 `test_negative_cases_return_false` 覆盖 `ModuleNotFoundError` / `AssertionError` / `PROBE_OK` / `""`；
   - DEFAULT_QUOTA_PATTERNS（DESIGN §4.1）覆盖中英常见额度措辞 + HTTP 429/402，是否有**过宽**风险（如 `exceeded` 会命中 `test count exceeded`、`rate.?limit` 会命中普通限速日志）？brief 是否要求执行者对此做**边界负例**断言？若不足，缺什么？

3. **单跳到底（隐患 C）是否被 brief 强制**：
   - brief Acceptance tests §2 要求「单跳 flash 也额度失败时**不再三跳**（`fb.calls == 1`、日志 `single-hop exhausted -> STOP`）」；
   - IMPLEMENTATION-PLAN B4 Step 1 `test_single_hop_flash_also_quota_fails` 断言 `fb.calls == 1`；
   - 对照 `_dispatch_with_quota_fallback` 实现草案（IMPLEMENTATION-PLAN B4 Step 3-4）：flash 失败后是否**只**返回 `(fb_result, provider_name)` 而**不**再递归/循环？brief 是否漏了「不得引入多档回退链」的显式负面约束？

4. **计数不双计（隐患 D）是否被 brief 强制**：
   - brief 「附注.已知陷阱」明写「**不要**为回退额外增加 `redispatch_count`：计数语义由 `main()` 在最终成功后 +1」；
   - DESIGN §5 步骤 7 明写「回退是「换 provider 重派」，**不额外 +1、不绕开 circuit-breaker**」；
   - 但 IMPLEMENTATION-PLAN B4 wrapper 函数**没有**直接的计数断言（wrapper 不写 status，计数逻辑仍在 `main()` 里），仅靠 brief 文字约束 + C1 独立复核。这是否**足够**？是否需要在 B5 Step 3 追加一条断言，如「mock `main()` 的计数写入路径，验证回退成功时 `redispatch_count` 只 +1」？

5. **密钥安全（隐患 E）是否被 brief 强制**：
   - brief 「附注.已知陷阱」未直接提及密钥脱敏；
   - DESIGN §6 明写「`is_quota_error` 与所有日志均跑在已脱敏输出上，不回显 key」，但脱敏发生在 `KimiAdapter._run` 内（既有），wrapper 消费的是 `ImplementResult.output`（已脱敏）；
   - brief 是否**需要**显式加一条不变式：「`is_quota_error` 与 `_dispatch_with_quota_fallback` 的日志**只**消费 `ImplementResult.output`（已脱敏），不得直接调 adapter 的原始 stdout/stderr」？若不加，执行者是否可能引入未脱敏路径？

6. **oracle 四证据是否按判据组成步骤生成**：
   - brief Acceptance tests §4 明写「变异集按判据自身的组成步骤生成，不得按已知缺陷清单枚举」，并具体化到「变异施于源文件字节（不是内存对象）」「config-driven 判据的变异施于 `tmp_path` 下的临时副本」「主档零回归判据的变异施于活树 `.agentic/config.toml`（B5 提交后的最终形态），变异后必须逐字节还原并 `git diff` 空输出核验」；
   - 这是否满足章程对「不变式为标的、台账为破口」的要求？变异面是否覆盖 brief 列出的全部 5 个不变式（主档零回归、单跳、fail-safe 模式加载、正向命中、计数不双计）？

7. **范围（allowed/forbidden）是否精确**：
   - allowed_paths 7 项（3 源 + 3 测试 + 1 config）与 IMPLEMENTATION-PLAN §File Structure 完全对齐；
   - forbidden_paths 11 项含 `independence.py` / `gate/` / `adapters/kimi.py` / `uv.lock` / `templates/` / 章程契约文件 / 锁与凭据路径；
   - 是否有**遗漏**的 forbidden（如 `docs/plans/2026-09-22-framework-hardening/` 防止跨 plan 污染、`src/agentic_loop/wrappers/` 防止绕过 wrapper 层）？是否有 allowed 过宽（如 `src/agentic_loop/resolve_paths.py` 是全文件允许，但只应新增函数，不改既有 `resolve_role_binding`）？

## 输出格式

请以自然语言作答（本 provider 下 `--output-schema` 为软约束），但须包含明确区块：

- `CODEX_DECISION: ACCEPT|REWORK|CONSULT`
- 对上述 7 项各给「充分/不充分/部分」＋简短证据（引文件路径:行号或 brief 章节）
- `CODEX_RATIONALE:` 裁定理由（1-3 段）
- 若 REWORK，`CODEX_FINDINGS:` 给**具体、有界**的阻断项（brief 哪一节、改成什么），而非泛论

**反芝诺 off-ramp（呼应章程 §6）**：若你认为剩余问题已属**可由执行者在实现期解决、并由 WP-01 的 post-implementation 双签门（`agentic gate`）复核**的实现细节，而非 **brief 级阻断项**，请据此 `ACCEPT` 并在 RATIONALE 注明，避免 brief 陷入无限细化。brief 级阻断项仅指：不变式本身错误/空洞、负面约束漏掉某条可伪造/可漂移路径、oracle 四证据不足以证承重、或范围留下跨 plan/跨 owner 缺口。

# WP-01: kimi 额度不足自动回退 deepseek-flash（单跳，配置驱动）

> 冻结日期 2026-09-22 | 编排者 claude-code (orchestrator, session=kqff-a3) | 执行者 kimi (developer)。
> 所属 Plan：PLAN-01（集成到 `plan/2026-09-22-kimi-quota-flash-fallback`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（规则见「Re-freeze 规则」一节）。

## Re-freeze 规则（编排者冻结前自检）

- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。
- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。

## 目标（一句话）

让 `agentic redispatch` 派发 developer 时，若原生 kimi 派发失败且输出命中额度模式，自动用配置的 `fallback_provider` 重派一次（单跳），失败即 STOP；对现有裸 kimi 配置零回归，主档 binding 与独立性评级语义完全不变。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/quota_fallback.py` — Create：纯函数额度检测 + 模式加载
  - `src/agentic_loop/resolve_paths.py` — Modify：新增 `resolve_role_fallback_binding`
  - `src/agentic_loop/redispatch.py` — Modify：新增 `_dispatch_with_quota_fallback` + `main()` 接入
  - `.agentic/config.toml` — Modify：追加 `[providers.deepseekflash]` + `[roles] developer` 加 `fallback_provider`
  - `tests/test_quota_fallback.py` — Create：`is_quota_error` / `load_quota_patterns` 单测
  - `tests/test_resolve_fallback_binding.py` — Create：`resolve_role_fallback_binding` 单测（含零回归负例）
  - `tests/test_redispatch_quota_fallback.py` — Create：派发回退编排单测（stub adapter，无真实 kimi/网络）

- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/independence.py` — 独立性评级不受本 WP 影响
  - `src/agentic_loop/gate/` — 双签门禁不属本 WP 范围
  - `src/agentic_loop/adapters/kimi.py` — 既有 `_temp_config` 注入机制已够用，不改 adapter
  - `uv.lock` — 无依赖变更
  - `docs/agentic/OPERATING_MODEL.md` — 章程不改
  - `AGENTS.md`
  - `CLAUDE.md`
  - `src/agentic_loop/templates/` — 模板不改（DESIGN §11 明确范围外）
  - `.agentic/locks/`
  - `.env`
  - `.context/`

- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入；本 WP 无跨 owner 文件。

## 输入

- 依赖的上游 WP 产出：无（本 plan 单 WP，base 直接是 `main` 7c318f4）。
- 参考文档（**权威源**，按文件读，不凭记忆替代）：
  - `docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md` §4-§8（架构、组件、数据流、错误处理与安全边界、config、测试计划）
  - `docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md` Phase B（B1-B6，含每步完整代码、命令、预期输出）
  - `docs/plans/2026-09-22-kimi-quota-flash-fallback/HANDOFF.md`（环境/纪律提醒）

## 交付物清单

- [ ] `src/agentic_loop/quota_fallback.py`（B1+B2）— 纯函数 `is_quota_error(output, patterns=None)` + `load_quota_patterns(repo=None)`；`DEFAULT_QUOTA_PATTERNS` 覆盖中英常见额度措辞与 HTTP 429/402；坏正则跳过而非崩溃；无 I/O 副作用（除 `load_quota_patterns` 读 config）。
- [ ] `src/agentic_loop/resolve_paths.py`（B3）— 新增 `resolve_role_fallback_binding(role, repo=None)`：读 `roles.<role>` 字典的**可选** `fallback_provider` 键 → 复用 `build_binding`；键缺失/role 非 dict/provider 段缺失或非法 → 返回 `None`（零回归，绝不抛到派发主链）。
- [ ] `src/agentic_loop/redispatch.py`（B4+B5）— 新增 `_dispatch_with_quota_fallback(adapter, worktree, brief, prompt, dry_run, *, fallback_binding=None, fallback_factory=None, quota_patterns=None) -> tuple[ImplementResult, str | None]`；`main()` 派发点改调本函数；成功/dry_run/非额度失败/未配回退 → 不触发回退；额度失败且配了回退 → 构造 flash `KimiAdapter` 重派一次；flash 也额度失败 → 单跳到底 STOP。
- [ ] `.agentic/config.toml`（B5）— `[providers.deepseekflash]`（anthropic_base_url / api_key_env / identity_model + selectors.kimi）；`[roles] developer` 由裸 string 改 `{ adapter = "kimi", fallback_provider = "deepseekflash" }`。
- [ ] `tests/test_quota_fallback.py`（B1+B2）— 中/英/数字码各取样正向命中；负向：普通报错/成功输出/空串；`load_quota_patterns` config 覆盖生效 + 缺省/坏配置回落默认（fail-safe）。
- [ ] `tests/test_resolve_fallback_binding.py`（B3）— 正向 flash binding 解析；负向：role 非 dict / 无 fallback_provider / provider 段缺失 / provider 配置非法（均返回 None，不抛异常）。
- [ ] `tests/test_redispatch_quota_fallback.py`（B4+B5）— 成功不回退；非额度失败不回退；额度失败重派 flash 成功；额度失败未配回退即 STOP；单跳 flash 也额度失败即 STOP；dry_run 直通；主档 `resolve_role_binding("developer")` 仍返回 `("kimi", None)`（评级语义零回归）；项目 config 解析出 flash fallback。

## 完成定义（DoD）

- [ ] 交付物逐项就绪（7 个文件，与 allowed_paths 一一对应）
- [ ] `agentic quality-gate docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json` 全绿
- [ ] 全量测试 `env -u AGENTIC_PYTHON PYTHONPATH=src python3.11 -m pytest tests -q` 仅 4 个**预存** `test_finalize_merge_triple_sign.py` 失败（基线，main 被 sibling worktree 占用所致），其余全绿，新增 ~19 个用例通过；任何**新增**失败视为回归，必须修复
- [ ] 范围守卫 `git diff main...HEAD -- src/agentic_loop/independence.py src/agentic_loop/gate/ src/agentic_loop/adapters/kimi.py uv.lock` 空输出（零改动）
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范（B1-B5 各一次 feat 提交，显式路径；status 的工作树累积不单独提交，按章程 §4.3 只在 freeze/finalize 提交）

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

> 若需偏离默认（如生产写入），须编排者 + 独立顾问双重审核并在此记录授权原因。
> 本 WP 单测全部用 stub adapter / tmp_path fixture 覆盖，**绝不**调真实 kimi CLI 或 DeepSeek API。
> 派发本 WP 时若 kimi 原生套餐已耗尽，按 DESIGN §10.1 用 `deepseek-v4-flash` 的手动 `--config-file` 派发（用户已授权 flash 优先），此时不依赖本 WP 自身的回退能力。

## 附注

- **已知陷阱**：
  - 运行测试**必须** `env -u AGENTIC_PYTHON`，否则 AGENTIC_PYTHON 泄漏进 `test_gate_runner_shell` 子进程绕过 python3 stub → 假失败（HANDOFF 环境提醒）。
  - `python3.11` 是 /opt/homebrew 版本，**无 agentic_loop 包**；模块校验/测试都要 `PYTHONPATH=src`（`docs/KNOWN-ISSUE-bare-python3.md`）。
  - `developer` 由裸 string 改 dict 后，`resolve_role_binding("developer")` 仍须返回 `("kimi", None)`（无 `provider` 键 → 主档零注入），**否则评级语义会变**——本 WP 显式断言此不变式。
  - `_dispatch_with_quota_fallback` 内的 `fallback_factory` 默认构造 `KimiAdapter(kimi_bin=os.environ.get("KIMI_BIN", "kimi"), binding=b)`；测试须用 stub factory 注入，避免真实 kimi 调用。
  - **不要**为回退额外增加 `redispatch_count`：计数语义由 `main()` 在最终成功后 +1；回退是「换 provider 重派」而非 rework（DESIGN §5 步骤 7）。
  - flash `identity_model` / `selectors.kimi` 精确串实现前须核实（DESIGN §10.1）；如与 `deepseek-v4-flash` / `deepseek/v4-flash` 有出入，按实测更新 `.agentic/config.toml` 并同步更新 `tests/test_redispatch_quota_fallback.py::test_project_config_resolves_flash_fallback` 的断言字面值。
- **口径权威源引用**：
  - `src/agentic_loop/redispatch.py:_dispatch` — 全框架唯一派发入口（DESIGN §3 已核实）
  - `src/agentic_loop/adapters/kimi.py:_temp_config` — 既有 flash 注入机制，**不改**（DESIGN §3）
  - `src/agentic_loop/resolve_paths.py:resolve_role_binding` — 对称参考点（DESIGN §4.2）
  - `.agentic/config.toml [roles] developer` — 主档语义零回归的判据源

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。

每一份 WP 的每条负面断言都必须提供 oracle 校验四项证据：

1. **正向可达性对照**：在同一 fixture 上做一次不带注入/变异的正向运行，必须到达终点，证明前置条件确实可达终点。
   - 本 WP 具体化：`is_quota_error("quota exceeded")` → True 的同时，`is_quota_error("ModuleNotFoundError")` → False；`_dispatch_with_quota_fallback` 在 primary 成功路径**不**构造回退 adapter（`built == []` 且 `prov is None`），在 primary 额度失败路径**恰好**重派一次（`fb.calls == 1`）。

2. **原因特异 witness**：负向运行必须给出原因特异的 witness（异常标记、状态或精确事件），证明失败被正确归因。
   - 本 WP 具体化：非额度失败**不**触发回退（`res.dispatched is False`、`prov is None`、`built == []`）；未配 fallback 时**原样返回**失败（`res.dispatched is False`、`prov is None`，日志 `quota detected but no fallback_provider configured`）；单跳 flash 也额度失败时**不再三跳**（`fb.calls == 1`、日志 `single-hop exhausted -> STOP`）；`dry_run` 直通不回退（`prov is None`、`built == []`）。

3. **代表性禁止变异转红**：至少一个代表性禁止变异（如改掉锚点标题、删去关键守卫）必须使测试转红。
   - 本 WP 具体化：把 `is_quota_error` 的额度判定改成恒 False → `test_quota_failure_retries_with_flash_success` 必须转红；把 `resolve_role_fallback_binding` 的 `try/except ProviderConfigError` 删掉 → `test_none_when_provider_cfg_invalid_no_raise` 必须转红（未吞异常）；把 `_dispatch_with_quota_fallback` 内的 `if dry_run or result.dispatched: return result, None` 短路删掉 → `test_success_no_fallback` / `test_dry_run_does_not_fallback_even_on_quota_output` 必须转红；把 `is_quota_error` 前的 `if not output: return False` 删掉 → `test_negative_cases_return_false::"" 空串` 用例转红。

4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。变异必须施加于判据真实的输入面（文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示。判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。同类输入面的等价载体（如临时副本）满足本项；若变异会写到被判据保护的制品本身，须优先选用不写该制品的等价载体。
   - 本 WP 具体化：变异施于 `src/agentic_loop/quota_fallback.py` / `resolve_paths.py` / `redispatch.py` 源文件字节（不是内存对象）；每条断言都由「还原 → 转红」双向验证；config-driven 判据（`load_quota_patterns` / `resolve_role_fallback_binding`）的变异施于 `tmp_path` 下的 `.agentic/config.toml` 临时副本，不改活树配置；主档零回归判据（`test_project_config_primary_developer_stays_native`）的变异施于活树 `.agentic/config.toml`（B5 提交后的最终形态），变异后必须逐字节还原并 `git diff` 空输出核验。

注意：第 1 项证明「前置可达」，第 2 项证明「失败归因」，**两者不能互相替代**——「无注入时能到终点」并不排除「带注入时死在别处」。

## Allowed and forbidden paths

本段与上文「范围」一节中的 allowed_paths / forbidden_paths 完全同义，非另一份口径：只能改 allowed_paths 白名单内的 7 个路径（3 源 + 3 测试 + 1 config），绝不能碰 forbidden_paths 黑名单（`independence.py` / `gate/` / `adapters/kimi.py` / `uv.lock` / 章程与契约文件 / `templates/` / 锁与凭据路径）；owner 边界对齐 CODEOWNERS，不跨 owner 写入。

范围守卫命令（B6 Step 2）：

```
git -C /Users/admin/vibe/.worktrees/kqff-wp01 diff --stat main...HEAD
git -C /Users/admin/vibe/.worktrees/kqff-wp01 diff main...HEAD -- \
  src/agentic_loop/independence.py src/agentic_loop/gate/ \
  src/agentic_loop/adapters/kimi.py uv.lock
```

第一条只列出 7 个允许文件；第二条**空输出**（#38 边界与信任根评级未触）。

## Completion definition

本段与上文「完成定义（DoD）」一节同义，非另一份口径：交付物逐项就绪（7 个文件）、验收测试全绿（focused 3 测试文件 + 全量 pytest 仅 4 预存失败）、范围守卫空输出（forbidden_paths 零改动）、`agentic quality-gate` 全绿、无生产写入/网络/通知/推送，commit message 符合规范（B1-B5 各一次 feat 提交，显式路径；status 的工作树累积不单独提交）。

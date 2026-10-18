# WP-02: kimi 注入所需的 base URL 必须在 binding 构造期 fail-closed

> 冻结日期 2026-10-18 | 编排者 claude-code | 执行者 待定。
> 所属 Plan：PLAN-01（集成到 `plan/2026-10-18-provider-binding-validation`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze。

## 目标（一句话）

`build_binding(adapter="kimi")` 必须校验 kimi 适配器**真正会用到**的
`openai_base_url`，缺失时 fail-closed 抛 `ProviderConfigError`；适配器不得
再用 `anthropic_base_url` 兜底，从而杜绝「anthropic 端点被写进
`openai_legacy` provider 块」这种静默坏配置。

## 不变式（验收标的）

1. **校验字段 == 使用字段**：kimi 注入路径读取的 base URL 字段，必须在
   binding 构造期就被校验存在。
2. **无静默回退**：kimi 适配器写出的配置里，`base_url` 只可能来自
   `openai_base_url`；任何 `providers.*` 缺该字段的情形必须在派工前失败，
   而不是在派工后以远端错误的形式暴露。

背景：现有 kimi 修复（`fix/tool-fixes-2026-10-14`）把 provider 块改为
`type = "openai_legacy"` + `openai_base_url`，但取 URL 写成
`getattr(b, "openai_base_url", None) or b.anthropic_base_url`；
而 `provider_binding.py` 只对 kimi 校验 `anthropic_base_url`。两者错位，
使得只声明 anthropic 的配置（本仓 `providers.deepseekflash` 正是如此）
产出一个 `base_url = "https://api.deepseek.com/anthropic"` 的
`openai_legacy` 块。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/provider_binding.py`
  - `src/agentic_loop/adapters/kimi.py`
  - `tests/test_provider_binding.py`
  - `tests/test_adapter_injection.py`
  - `tests/test_resolve_fallback_binding.py`（re-freeze r1 追加，见附注陷阱 4）
  - `tests/test_redispatch_quota_fallback.py`（re-freeze r2 追加，见附注陷阱 5）
  - `.agentic/config.toml`
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/gate/**`
  - `src/agentic_loop/wrappers/**`
  - `src/agentic_loop/contract_render.py`
  - `AGENTS.md`、`CLAUDE.md`、`docs/agentic/OPERATING_MODEL.md`
    （除非 contract checksum 真的变了，见附注）
- **owner 边界**：引擎侧配置校验，不跨 owner。

## 输入

- 依赖的上游 WP 产出：WP-01（基线转绿）——否则「全套全绿」不可判读
- 依赖的既有提交：`fix/tool-fixes-2026-10-14` 的 kimi 修复
- 参考文档：`src/agentic_loop/provider_binding.py`、`adapters/kimi.py:_temp_config`

## 交付物清单

- [ ] `src/agentic_loop/provider_binding.py` — kimi 校验 `openai_base_url`
- [ ] `src/agentic_loop/adapters/kimi.py` — 去掉 `or b.anthropic_base_url` 兜底
- [ ] `.agentic/config.toml` — `providers.deepseekflash` 补 `openai_base_url`
- [ ] `tests/` — 锁定测试（见 Acceptance tests）

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] `python3.11 -m pytest tests -q` 无新增失败（对照 WP-01 后的基线）
- [ ] `agentic contract check` 三个文件仍 IN_SYNC
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

- **已知陷阱 1（改既有断言的正当性）**：`tests/test_resolve_fallback_binding.py`
  的注释写着「缺 anthropic_base_url（kimi 必需）」。若 kimi 改为要求
  `openai_base_url`，该注释与校验的语义要一并校准。修改既有断言时必须在
  commit message 里写明为什么原断言编码的是错误行为。
- **已知陷阱 2（config 改动是否牵动 contract）**：已实测
  `expected_checksum` 不读取 `[providers.*]`（改动前后均为 `c2ab3c3bb360dadc`），
  因此补 `openai_base_url` **不应**改变 contract checksum。若实测发现变了，
  停下来报告，不要顺手重渲契约。
- **已知陷阱 3（不要扩大成配置来源问题）**：本 WP 只解决「校验字段与使用
  字段错位」。quality-gate 的分支配置预览、gate 的 brief 硬编码路径均不在此。
- **已知陷阱 4（re-freeze r1 追加路径的理由）**：`tests/test_resolve_fallback_binding.py`
  的 `FLASH_CFG` 夹具就是「只声明 anthropic_base_url」这一历史形态；kimi 改判
  `openai_base_url` 后它会被 fail-closed 拒绝，`test_resolves_flash_binding` 转红。
  该夹具本身编码的正是被修复的错误前提，属于必须一并校准的既有断言，
  故将其纳入 allowed_paths。校准方向：补声明 `openai_base_url`，
  **不放宽**校验去迁就旧夹具。
- **已知陷阱 5（re-freeze r2 追加路径的理由）**：`tests/test_redispatch_quota_fallback.py`
  的 `_flash_binding()` 手工构造 `ProviderBinding(openai_base_url=None)`，同样编码了
  旧前提；适配器改为 fail-loud 后 `test_kimi_bound_detail_redacts_api_key` 与
  `test_probe_injection_binding_modes[bound]` 转红。校准方向：给夹具补
  `openai_base_url`，**不放宽**适配器守卫。
- 口径权威源引用：`src/agentic_loop/provider_binding.py:48-55`（现有校验）、
  `src/agentic_loop/adapters/kimi.py:61`（现有取 URL 逻辑）。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」同义，非另一份口径。

必测用例：

1. `build_binding(adapter="kimi")` 在 provider 段只声明 `anthropic_base_url`
   时抛 `ProviderConfigError`，且错误消息不回显 key 值。
2. `build_binding(adapter="kimi")` 在声明了 `openai_base_url` 时成功，且
   `b.openai_base_url` 为声明值（正向可达性对照）。
3. 适配器 `_temp_config()` 产出的文本中，`base_url` 等于 `openai_base_url`，
   且**不含** anthropic 端点字符串（原因特异 witness）。

每个负面断言须提供四项证据：

1. **正向可达性对照**：同 fixture 不注入缺失时不抛异常，证明构造路径可达。
2. **原因特异 witness**：缺失时抛 `ProviderConfigError` 而非其他异常，
   且消息指向缺失字段。
3. **代表性禁止变异转红**：把 kimi 从校验集合中移除（恢复原状）后，
   用例 1 必须转红。
4. **变异集按判据自身组成步骤生成**：变异施加在真实输入面
   （传入的 `provider_cfg` 字典 / 生成的 TOML 文件字节），不得只改内存表示。

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径：只能改
`src/agentic_loop/provider_binding.py`、`src/agentic_loop/adapters/kimi.py`、
`tests/test_provider_binding.py`、`tests/test_adapter_injection.py`、
`tests/test_resolve_fallback_binding.py`、`tests/test_redispatch_quota_fallback.py`、
`.agentic/config.toml`；绝不能碰 `src/agentic_loop/gate/**`、
`src/agentic_loop/wrappers/**`、`src/agentic_loop/contract_render.py` 及三份契约文件。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径：交付物就绪、全套无新增失败、
`agentic contract check` IN_SYNC、无 forbidden_paths 写入、
无生产写入/网络/通知/推送、commit message 符合规范。

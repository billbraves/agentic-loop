# 修复清单：DeepSeek 注入缺 `wire_api=responses`（并纠正 Quick-Start 兼容性注记）

> 状态：已修复 · 落地版本 0.8.3 · 基线 0.8.2 (`71e11ca`)
> 作者：实操核实后整理（本清单可脱离对话独立执行）

## 0. 一句话

Quick-Start §1.2 的兼容性注记断言 codex ≥ 0.147「无需 workaround」是**错的**：
能跑通的独立 codex profile 恰恰**显式声明了** `wire_api = "responses"`，而
adapter 的 inline 注入**没有注入这一项**。清单要做两件事——**补注入** +
**纠正注记**。

---

## 1. 证据（为什么注记不准确）

### 1.1 能跑通的独立配置用了 workaround

`~/.codex/config.toml:137-141`（standalone DeepSeek profile，实测可用）：

```toml
[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
env_key = "DEEPSEEK_API_KEY"
wire_api = "responses"          # ← 显式声明，正是「workaround」本身
```

### 1.2 adapter 的 inline 注入丢了这一项

`src/agentic_loop/adapters/codex.py:64-75`（`_build_injection_flags`）：

```python
return [
    "-c", f"model_provider={b.provider}",
    "-c", f"model_providers.{b.provider}.name={b.provider}",
    "-c", f"model_providers.{b.provider}.base_url={b.openai_base_url}",
    "-c", f"model_providers.{b.provider}.env_key={b.api_key_env}",
    "-m", b.cli_selector,
]
```

对一个**新建的 inline provider**，codex 不会自动把 wire 协议设成 responses；
它取决于 CLI 默认。独立配置之所以要显式写 `wire_api="responses"`，就说明这个
默认**不可信**。注入路径少了它 → codex 0.147 可能报错或行为不定。

### 1.3 官方 models.json 只保证 flash 优先

`~/.codex/models.json`：`deepseek-v4-pro` 与 `deepseek-v4-flash` 均
`minimal_client_version: 0.144.0`、`supported_in_api: true`。responses API
档的官方优先保证是 **flash**（priority 1）；pro 是 priority 2。但 curl 实测
`model=deepseek-v4-pro` 走 `/v1/responses` 是 HTTP 200 正常返回——所以准确说法是
「flash 官方优先保证、pro 可用但承诺优先级较低」，而不是「pro 跑不通」。

---

## 2. 要改的三处

### 2.1 【代码】adapter 注入 `wire_api`

**文件**：`src/agentic_loop/adapters/codex.py`
**函数**：`_build_injection_flags`（第 64-75 行）
**改法**：在 `-m` 之前加一行 `-c`：

```python
        "-c", f"model_providers.{b.provider}.wire_api=responses",
```

> 注意：这里 wire_api 目前是**硬编码 `responses`**。若要严谨，应从
> `provider_cfg` 读（见 §3 可选项），但 DeepSeek 场景固定 responses，
> 硬编码可接受，作为最小修复先落地。

**注**：0.1.0 时代的 legacy 副本在 **baofu-monorepo**（
`/Users/admin/.hermes/baofu-monorepo/packages/agentic-loop.legacy-0.1.0/.../codex.py`），
**不在本仓**（本仓已无 `packages/`）。它是纯归档、不被引用，无需跟改。

### 2.2 【文档】纠正 Quick-Start 注记

**文件**：`docs/QUICKSTART.zh-CN.md`（第 121-123 行）
**现状（错）**：

> codex ≥ 0.147 只走 Responses API（`/v1/responses`），DeepSeek 已支持，无需 workaround。

**改成（对）**：

> codex ≥ 0.147 走 Responses API（`/v1/responses`）。DeepSeek 的 `/v1` 确实
> 挂了该端点，但 **codex 对 inline/自定义 provider 不会自动选 responses 协议**——
> 必须显式设 `wire_api = "responses"`（独立 profile 在 config 里写，adapter
> 注入时用 `-c model_providers.<name>.wire_api=responses`）。responses 档官方
> 只保证 `deepseek-v4-flash` 稳定，`-pro` 为凑合档。

### 2.3 【测试】覆盖注入含 wire_api

**文件**：codex adapter 的单测（`tests/` 下，找 `_build_injection_flags` 或
`probe_injection` 的用例）。
**加断言**：`-c model_providers.<provider>.wire_api=responses` 出现在 argv 中。
若已有 real-injection probe（`probe_injection`），本地跑一次确认 exit 0 +
命中 `DEEPSEEK_PROBE_OK`。

---

## 3. 可选（更严谨，非必须）

把 wire_api 变成可配置而非硬编码：
- `provider_binding.py`：`ProviderBinding` 加字段 `openai_wire_api: str = "responses"`，
  `build_binding` 从 `provider_cfg.get("openai_wire_api", "responses")` 读。
- adapter 用 `b.openai_wire_api` 而非字面量。
- config schema（`config.toml` 的 `[providers.deepseek]` 段）允许覆盖。

DeepSeek 单一场景下不值当；多 provider 才需要。**先做 §2 最小修复**。

---

## 4. 验收

- [ ] `_build_injection_flags` 输出含 `wire_api=responses`
- [ ] `probe_injection()` 本地 exit 0 且命中 sentinel（需 `DEEPSEEK_API_KEY`）
- [ ] Quick-Start §1.2 注记已纠正，不再出现「无需 workaround」
- [ ] 单测断言新增并通过
- [ ] CHANGELOG 0.8.3 记一条：codex inline 注入补 `wire_api=responses`
- [ ] （可选）legacy 副本对齐或标 TODO

---

## 5. 关键行号速查

| 内容 | 路径 | 行 |
|---|---|---|
| 独立 profile 的 wire_api（正确范本） | `~/.codex/config.toml` | 137-141 |
| 现役注入（缺 wire_api） | `src/agentic_loop/adapters/codex.py` | 64-75 |
| legacy 注入（baofu-monorepo，归档不引用） | `baofu-monorepo/packages/agentic-loop.legacy-0.1.0/.../codex.py` | 64-74 |
| 错误注记 | `docs/QUICKSTART.zh-CN.md` | 121-123 |
| ProviderBinding 字段 | `src/agentic_loop/provider_binding.py` | 14-64 |
| models.json（flash 稳定/pro 凑合） | `~/.codex/models.json` | 全文 |

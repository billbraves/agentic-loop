# 交接：禁工具收尾 turn 改走直连 Responses API

状态：**改动已可用但未提交、未完成端到端验证**。最后一次门禁实跑仍在进行中。

## 1. 要解决的问题

多 chunk 评审的**禁工具收尾 turn**（`tools_forbidden=True`）永远无法通过协议校验，
导致 `agentic gate` 的第二签**永远取不到**：

```
GATE_FAIL: codex review failed: codex final-message protocol mismatch:
           tool-free turn emitted a tool or unknown item
```

两次运行日志**逐字节相同**（sha256 `077bfb45...`，相隔 8 小时），是确定性失败，不是抖动。

## 2. 根因（已实测确认，不是推测）

`web_search` 是 **codex CLI 客户端注入**的，不是 provider 服务端行为。

证据：直接以 `tools: []` 调 DeepSeek `/v1/responses`，**即使提示明确要求联网搜索**，
输出也只有 `reasoning` + `message`，没有任何工具项：

```bash
curl -s https://api.deepseek.com/v1/responses \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro","input":"Search the web for the current stable version of ripgrep and report it.","tools":[],"stream":false}'
# -> output 项类型: ['reasoning', 'message']
```

而经 codex CLI 时，同样的提示必然产出 `web_search` 项。

### 所有 codex 侧开关都无效（逐个实测过）

| 尝试 | 结果 |
|---|---|
| `--disable web_search` | 无效 |
| `--disable web_search_request` / `standalone_web_search` / `web_search_cached` / `search_tool` | 无效 |
| `-c tools.web_search=false` | 无效 |
| `-c model_providers.<p>.omit_tools_from=["web_search"]` | **无效，且 web_search 反而更多** |
| `-c model_providers.<p>.supports_standalone_web_search=false` | turn 直接 `turn.failed` |

结论：走 codex CLI 的收尾 turn 无法兑现"禁工具"契约。

## 3. 已做的修复

`_direct_tool_free_verdict()`（`src/agentic_loop/adapters/codex.py`）：禁工具 turn 绕过
CLI，直接调 provider 的 Responses API，请求里 `tools` 恒为**空数组** —— 真正兑现契约，
而不是事后校验一个已被污染的流。**校验侧一行未放宽**：直连路径同样对任何非
`reasoning`/`message` 项、非 `completed` 状态、多个 `output_text` 一律 fail-closed。

接入点：`review()` 里两个 `tools_forbidden=True` 站点（同 thread 收尾 + 结构归一化）。

### 关键设计：默认关闭，由调用方显式开启

`CodexAdapter(binding=..., direct_finalization=True)`，`gate/__init__.py` 里显式打开。

**不要改成"环境里有密钥就自动启用"**。我先写成那样，踩了坑：既有单测用假 binding
打桩 codex CLI 的 JSONL 协议（它们校验的正是 tool-free 流 fail-closed，是必须保留的
真守卫），自动启用会把它们劫持成真实 HTTP 并拿到 401 —— 一次跑出 **66 项失败**。
默认关闭后，测试确定性走 CLI 路径。

## 4. 走过的两条错路（不要重复）

1. **以为是输出预算不足**。给 `_build_injection_flags` 加 `-c output_token_limit=64000`。
   实测：上限确实生效（`output_tokens` 从 8811 涨到 **77919**，其中 reasoning 77450），
   但模型把预算全烧在推理上，`web_search` 反而更频繁。**已完全回退。**
2. **以为 `omit_tools_from` 能关掉工具**。实测加了之后 `web_search` 项变多。**已回退。**

## 5. 当前卡点（下一个 agent 从这里接）

第一次实跑直连后，`web_search` 违约**消失了**（修复方向正确），但换成：

```
GATE_FAIL: direct tool-free finalization did not complete: status='incomplete'
```

即撞上 `max_output_tokens`。已把 `_DIRECT_MAX_OUTPUT_TOKENS` 从 16000 提到 **96000**、
超时提到 1800s，并让报错带上 `incomplete_details.reason` 以便区分原因。

**96000 预算的实跑已出结果，仍然失败**：

```
GATE_FAIL: codex review failed: direct tool-free finalization did not complete:
           status='incomplete' reason='max_output_tokens'
```

这个结果很有价值，它**排除了"继续加预算"这条路**：预算从 16000 提到 96000，模型依然把
它吃满。结合早先的实测（CLI 路径下 `output_tokens=77919` 而 `reasoning=77450`，即 97%
是推理），可以判定：**这个模型在收尾场景会把给它的任何输出预算都用于推理**，加预算只是
抬高天花板，不会让它收敛。

### 已实测的探针结果（直连 /v1/responses，非推测）

| 场景 | input | output | reasoning | status |
|---|---|---|---|---|
| 小输入（一句话评审） | 168 | 628 | 543 | completed |
| 收尾级输入（10 份 chunk 裁决，~4KB） | 1224 | 436 | 383 | completed |
| `reasoning.effort=low`（小输入） | 168 | 1253 | 1199 | completed |
| **真实门禁收尾** | **46656** | **96000 吃满** | — | **incomplete** |

三条可靠结论：

1. **加预算已证伪**。16000 -> 96000 都是 `max_output_tokens`。
2. **`reasoning.effort=low` 不可用**。参数被接受，但推理量从 543 **涨到** 1199，方向相反。
3. **输入规模不是直接原因**。~4KB 的收尾级输入只用 436 output token 就完成，比一句话
   输入还少。我原先"输入越大推理越长"的假设**被这条实测推翻了**，别再沿用。

真实收尾的 input 是 **46656** token，比我能复现的探针高 38 倍。**失败只在这个量级出现**，
我没能在小样本上复现它 —— 这是交接时最大的未知。

### 下一步（按优先级）

1. **先复现，再修**。用真实的收尾 prompt（`prompt-2.md`，由 `review()` 写在临时 workdir，
   可临时改 adapter 保留该目录）直接打 `/v1/responses`，确认是否稳定 `incomplete`。
   在 46656 token 这个量级上复现出来，才谈得上判断修法。不要基于小样本推断。

2. **查 provider 在长 input 下的输出行为**。同一 prompt 逐步截短（46656 -> 24k -> 12k -> 6k），
   找出 `incomplete` 的临界点。这能区分"长 input 触发失控推理"与"某段特定内容触发失控"。

3. **考虑让收尾不再依赖模型**（最彻底）。如果每个 chunk 的输出已是严格 schema，最终裁决
   完全可以在 adapter 里用纯代码合并（取最严 decision + findings 并集）。这样既绕开
   `max_output_tokens`，也消灭了"禁工具 turn"这整个问题类别 —— 不需要模型，就不需要
   禁工具契约。代价是失去"模型再读一遍全局"的那层判断，需要先确认门禁语义上能否接受。

## 6. 尚未处理的问题

- **直连只覆盖禁工具 turn**。初审 chunk 仍走 codex CLI（那里允许工具，不受影响）。
- **只对 DeepSeek 的 Responses API 实测过**。其他 provider 的 `/responses` 兼容性未验证；
  `openai_base_url` 拼 `/responses` 的假设需要在换 provider 时复核。
- **`_DIRECT_MAX_OUTPUT_TOKENS` 是经验值且已被证伪**（96000 仍撞上限）。不要沿着调大
  常量的方向走，见"下一步"。
- **直连路径没有传递 reasoning effort**。CLI 路径有 `-c model_reasoning_effort=<effort>`，
  `_direct_tool_free_verdict` 的请求体里没有对应参数。`review()` 拿到的 `effort` 参数
  在直连分支上被丢弃了 —— 这是一个明确的不一致，很可能与推理无界膨胀直接相关，建议
  优先排查。
- **CLI 回退路径仍在**（无 binding 时），但它已知无法通过禁工具校验。要么明确标注它
  只用于测试打桩，要么删掉 —— 留着容易让人误以为它是可用的生产回退。
- `codex final-message protocol mismatch` 的校验逻辑（`_validated_final_message`）**没动**，
  也不该为了通过而放宽它。

## 7. 参考数据

- 失败 turn 的真实事件序列（`tools_forbidden=True`）：
  `thread.started, item.completed(error), turn.started, error, item.started(web_search),
   item.completed(web_search), item.started(web_search), item.completed(web_search),
   item.completed(agent_message), turn.completed`
- 那次 usage：`output_tokens=77919, reasoning_output_tokens=77450, input_tokens=46656`
- 流级 error：`Reconnecting... 1/5 (stream disconnected before completion:
  Incomplete response returned, reason: max_output_tokens)`
- 常驻告警（良性）：`Model metadata for deepseek-v4-pro not found. Defaulting to
  fallback metadata` —— 成功的运行里也有，不是失败原因。
- 10 个 chunk 的裁决合计约 14.6KB（~4.9k token），这是收尾需要汇总的输入规模。

# WP-15 (rev2): `max_context_size` 随 provider 配置走，不再硬编码 DeepSeek 的 768K

> 冻结日期 2026-09-14 ｜ 编排者 Claude ｜ 执行者 kimi
> 冻结后执行期间不得修改。修订走 re-freeze（rev3）。
>
> **rev2 变更**（依 codex 咨询结论，见
> `WP-15-consult-codex.md`）：
> 1. **删除「A5 修法 1 前置」定位**。codex 的 P0 指出 `identity_model` 是可伪造的
>    TOML 声明而非 engine-observed identity，A6 修完也不足以让 A5 修法 1 变安全；
>    且用户已裁定 A5 走修法 2。本 WP 收窄为**独立的 context-size 透传修复**。
> 2. 交付物 1 从 `max_context_size: int = 786432` 改为
>    `int | None = None` + renderer 侧**命名的** legacy fallback，
>    避免把「未声明」伪装成「provider 声明了 768K」。
> 3. DoD 补 `bool` 反例（`bool` 是 `int` 子类）与 TOML 解析断言。

## 目标（一句话）

让 kimi 的临时配置模板从 provider 配置读取 `max_context_size`，
使绑定 provider 不再静默压缩实际后端的上下文窗口。

## 背景

`src/agentic_loop/adapters/kimi.py:63` 在临时配置模板里写死：

```python
f'max_context_size = 786432\n'
```

786432 = 768K，是当初为 DeepSeek 端点选的值（同一函数 docstring `:51`
与注释 `:54` 至今仍写 DeepSeek）。该值无参数、无配置项、不读 provider 配置。

本仓 developer 的实际后端是 codingplan/k3，真实窗口 1048576（1M）。
一旦 `developer` 绑上 provider，`kimi.py:107` 便以该临时配置启动 kimi，
768K 覆盖 1M —— **静默损失约 25% 可用上下文，无任何告警**。

绕不开：绑定路径上 `:107`（派发）与 `:171`（注入探针）都只经
`_temp_config()`，不存在「绑定但不套用该模板」的路径。

**为何现在做**：这是一处独立缺陷——只要有人给 `developer`（或任何 kimi 角色）
绑 provider，窗口就被静默压到 768K。修它本身就有价值，与 A5 的解法选择无关。

**本 WP 与 A5 的关系（rev2 修正）**：rev1 曾把本 WP 定位为「A5 修法 1 的前置」。
该定位**已作废**。codex 咨询（`WP-15-consult-codex.md`）指出 A5 修法 1
（给 developer 绑 provider 以打开 degraded 路径）另有三项独立阻断条件，
修完 A6 一条也没解决：

| 阻断条件 | 依据 |
|---------|------|
| `identity_model` 来自可手改 TOML，非 engine-observed，可伪造独立性证据 | `provider_binding.py` `build_binding()`；`kimi.py:45-47` `identity()` |
| `--config-file` 独立加载完整配置，不与 `~/.kimi/config.toml` 合并，丢 `default_thinking` / `capabilities` / hooks / MCP 等 | `kimi.py:49-64` `_temp_config()` 只输出 provider/model |
| 模板硬编码 `type = "anthropic"`，本机 K3 实为 `type = "kimi"` + OAuth | `kimi.py:56-63`；`~/.kimi/config.toml:70-75` |

且**用户已裁定 A5 走修法 2**（新开 WP 扩展评级准则），修法 1 不再是首选。
故本 WP **不承担**任何 A5 解锁责任，也不得在实现或报告里声称解锁了 A5。

缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §A6
咨询记录：`docs/plans/2026-09-13-parallel-throughput/WP-15-consult-codex.md`

## 范围

**allowed_paths**
- `src/agentic_loop/provider_binding.py`
- `src/agentic_loop/adapters/kimi.py`
- `tests/test_provider_binding.py`
- `tests/test_adapter_injection.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`（**尤其禁止**：本 WP 只改代码，配置由用户改；
  不得顺手给 developer 加绑定，也不得动 `min_independence`）
- `src/agentic_loop/wrappers/`
- `src/agentic_loop/independence.py`（WP-08 刚改完，勿碰）
- `src/agentic_loop/gate/`
- 其余一切未在 allowed 列出的路径

## 输入

- 依赖的上游 WP 产出：无（可与 A4/A5 其余修法并行）
- 现状代码：`provider_binding.py` 的 `ProviderBinding` 与 `build_binding()`；
  `adapters/kimi.py:49-75` 的 `_temp_config()`
- 现有测试挂载点：`tests/test_adapter_injection.py:122`
  （`test_kimi_temp_config_contains_key_and_is_0600` 已在测该 context manager）

## 交付物清单

1. `ProviderBinding` 增字段，**类型 `int | None`、默认 `None`**：
   `max_context_size: int | None = None`。`build_binding()` 从
   `provider_cfg.get("max_context_size")` 读取；provider 未声明时保持 `None`。
   > **为何必须带默认值**：`ProviderBinding` 是 frozen dataclass，
   > 加一个无默认值的字段会破坏所有现有构造点——包括
   > `tests/test_adapter_injection.py` 的共享工厂 `mk_binding()`（:124 等处
   > 使用），而那些文件不全在本 WP 的 allowed_paths 内。带默认值即零破坏、
   > 零回归，且不必触碰任何既有构造点。**不要改 `mk_binding()` 的签名。**
   >
   > **为何默认是 `None` 而不是 `786432`**（rev2 依 codex P2 改）：
   > `max_context_size` 是 Kimi 的 **model 属性**，不是 provider 的身份属性。
   > 把 `786432` 放进 dataclass 默认值，会让「provider 没声明」与
   > 「provider 声明了 768K」在 binding 上**无法区分**——等于替用户凭空作出一个
   > 它从未作过的声明。`None` 如实表示「未声明」，回退值的选择落在 renderer 侧，
   > 可被命名、可被单独测试。
2. `adapters/kimi.py:_temp_config()` 的模板改为读 `b.max_context_size`，
   删除内联字面量 786432。**`None` 时使用一个命名的模块级常量**，例如
   `_LEGACY_MAX_CONTEXT_SIZE = 786432`，旁边注明它是为既有 DeepSeek 配置
   保零回归的**兼容回退值，而非推荐值**。
   > **该行不可省略**：Kimi 配置模型的 `LLMModel.max_context_size` 是必填项，
   > 模板不输出该行会让 kimi 拒绝加载配置。所以「未声明就不输出」不是可选方案，
   > 必须落到一个显式的、被命名的回退常量上。
3. 校验：`max_context_size` 若出现但不是正整数，按本仓既有风格 fail-closed
   抛 `ProviderConfigError`，消息**绝不含 key 值**（照 `build_binding()`
   现有五处报错的写法）。
   > **必须显式拒绝 `bool`**（rev2 依 codex P2 增）：Python 里 `bool` 是 `int`
   > 的子类，只写 `isinstance(value, int) and value > 0` 会让 `True` 当成 `1`
   > 静默通过，产出 `max_context_size = 1` 这种荒谬配置。判定里要先挡 `bool`，
   > 例如 `isinstance(value, bool) or not isinstance(value, int)` 即拒绝。
4. 顺手修正 `_temp_config()` 的 docstring `:51` 与注释 `:54` —— 二者仍称
   DeepSeek，与已泛化的 provider 层不符。
5. 测试：见 DoD。

**不要做的事**

- 不要改 `.agentic/config.toml`（配置属用户决策，且是本 WP 的 forbidden path）
- 不要动 `identity_model` / `cli_selector` / `api_key_env` 的既有语义
- 不要把 key 写进任何报错、日志或测试固件
- `_PROBE_PROMPT` / `_SENTINEL` 仍是 `DEEPSEEK_PROBE_OK`（`kimi.py:165-166`，
  `claude.py:123-124`，`codex.py:83-84`）。**属同类遗留但不影响正确性，
  本 WP 不改**，如你认为该改，记进 `[CONCERNS]`。
- `claude.py` / `codex.py` 不写临时配置，没有同样的硬编码，**不要顺手改它们**

## 完成定义（DoD）

- [ ] **characterization test 先行**：先固化「provider 配置未声明
      `max_context_size` 时，生成的模板与改动前逐字相同」，
      证明本改动对既有配置零回归。**逐字比对整份模板文本**（不是只查
      `max_context_size` 一行），这样字段顺序、空行、缩进的意外变化也会被抓住
- [ ] 正向测试：provider 声明 `max_context_size = 1048576` 时，
      `_temp_config()` 产出的 TOML 含 `max_context_size = 1048576`，
      且不含 786432
- [ ] **模板必须是合法 TOML 且解析后字段值正确**（rev2 依 codex P2 增）：
      用 `tomllib`（3.11+）/ `tomli` 实际 parse 生成的文件，断言
      `parsed["models"][<selector>]["max_context_size"] == <期望值>`。
      不接受只做子串断言——现有
      `tests/test_injection_probe.py:80-93` 的假 kimi 只 grep argv 里有没有
      `--config-file`，既不读 TOML 也不验字段，证明不了配置真的可用
- [ ] 反向测试：`max_context_size` 为 0 / 负数 / 非整数 / 字符串时
      fail-closed 抛 `ProviderConfigError`，且**报错文本不含 key 值**
- [ ] **反向测试必须含 `True` 与 `False` 两个 bool 反例**（rev2 依 codex P2 增）：
      `bool` 是 `int` 子类，漏了这条 `True` 会被当 `1` 静默接受
- [ ] `ProviderBinding` 仍是 frozen dataclass（现有
      `tests/test_provider_binding.py:35` 已断言不可变，勿破）
- [ ] `mk_binding()`（`tests/test_adapter_injection.py`）的签名与既有调用点
      **一处未改**，靠 dataclass 默认值实现零破坏
- [ ] **legacy 回退值有名字**：`786432` 在 `src/` 下只出现在那一个命名常量的
      定义行；`_temp_config()` 的模板 f-string 里不再有裸字面量。
      改动前 `src/` 下唯一一处是 `adapters/kimi.py:63`（模板内）；
      改动后仍应只有一处，但**位置必须是常量定义行、不在模板里**
- [ ] **报告里不得声称解锁了 A5 或 A0**（rev2 增）：本 WP 是独立的 context-size
      透传修复；A5 另有三项阻断条件，见「背景」一节的表
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
- [ ] 无 forbidden_paths 写入（特别确认没碰 `.agentic/config.toml`）
- [ ] 无生产 DB 写入、无网络、无推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **临时配置里有 API key 明文**（`kimi.py:53,59`，文件 0600 后即删）。
   测试断言模板内容时**绝不可把 key 写进固件或断言消息**；
   现有 `test_kimi_temp_config_contains_key_and_is_0600` 的做法是范例，照它写。
2. legacy 回退值 786432 是**零回归要求**，不是推荐值。
   不要因为「1M 更好」就把它改成 1048576 —— 那会静默放大所有未声明该项的
   既有 provider。命名常量旁边要写清这一点。
3. `build_binding()` 现有五处 fail-closed 报错的措辞刻意脱敏，保持该风格。
4. **本仓 `requires-python = ">=3.9"`**（`pyproject.toml:8`），
   `provider_binding.py:1` 已有 `from __future__ import annotations`，
   所以 `int | None` 注解可直接写。
   > **测试里解析 TOML 不要自己写 import fallback**：仓内已有
   > `src/agentic_loop/resolve_paths.py:120` 的 `_tomllib()`
   > （3.11+ 用 `tomllib`，否则退 `tomli`），复用它。
5. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
6. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。
7. 本 WP 是纯粹的配置透传，**不改变任何独立性评级逻辑**。
   若你发现改动会影响 `identity()` 或评级，停下并记进 `[CONCERNS]`。
8. **本 WP 不是 A5 或 A0 的解法**（rev2 增）。codex 咨询已确认 A5 修法 1
   另有三项阻断条件（可伪造的 `identity_model`、`--config-file` 替换整份配置、
   `type="anthropic"` 硬编码），本 WP 一条也不解决，且用户已裁定 A5 走修法 2。
   不要在实现、注释或报告里写「解锁 degraded」「解开合并死锁」之类的话。
9. `_temp_config()` 产出的是**完整 Kimi 配置而非覆盖片段**（`--config-file`
   独立加载，不与 `~/.kimi/config.toml` 合并），因此绑定 provider 还会丢
   `default_thinking`、模型 `capabilities`、hooks、MCP 等全局项。
   **这是 A5 的问题，不在本 WP 范围内**——本 WP 只修 `max_context_size` 一项。
   如你想顺手补其他字段，**停下**，记进 `[CONCERNS]`。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的 characterization / 反向测试要求见上文 DoD。

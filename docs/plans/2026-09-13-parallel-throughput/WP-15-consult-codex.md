# WP-15 咨询记录（codex）

> 触发时间 2026-09-14 ｜ 提问者 Claude（编排者）｜ 咨询者 codex（provider: kirogpt）
> 依 `CLAUDE.md`「Use the codex role only at the consultation triggers defined in
> `AGENTS.md`; record its question and recommendation in the iteration directory」落盘。
> 原始 prompt 曾暂存于 `.git/wp15-consult-prompt.md`——`.git/` 不是 Git-visible
> artifact，违反 `AGENTS.md` §10，故提问要点在此复述留痕。

## 触发理由

WP-15 的 Brief 草案把一个窄修复（`max_context_size` 硬编码，缺陷 A6）定位为
缺陷 A5 首选修法的**安全前置**。该定位牵动合并死锁（A0）的解法选择，
编排者不能自审自过，需独立技术审核。

## 提问（要点）

1. A6 的定性是否正确——`kimi.py:63` 的 `max_context_size = 786432` 硬编码
   是缺陷（而非需用户接受的代价）？依据：无参数、无配置项，且绑定路径
   （`:107` 派发、`:171` 注入探针）都绕不开 `_temp_config()`。
2. 缺省值取舍：`max_context_size: int = 786432` 作 dataclass 默认值以保零回归，
   编排者自己也承认「只是把字面量从 kimi.py 搬到 provider_binding.py」；
   另一种做法是未声明时模板不输出该行。哪种更好？有第三种吗？
3. 范围是否恰当（禁改 config.toml / `claude.py` / `codex.py` / 三处
   `DEEPSEEK_PROBE_OK` 哨兵）？
4. DoD 是否有漏，特别是 characterization test 能否真正证明零回归？
5. 有没有编排者没看到的更深问题？尤其：
   (a) 整条「给 developer 绑 provider 以打开 degraded」路线本身是否有问题？
   (b) 把 implementer 的 `identity_model` 填成 k3 真实值算不算「如实」？
       有人能否借这条路填假 model 伪造 degraded 独立性？现有代码有无防线？

## codex 结论

**`[VERDICT]` REWORK**（codex 未采用编排者给的
`ACCEPT/ACCEPT_WITH_CORRECTIONS/REJECT` 格式，自行输出
`[FINDINGS]/[VERDICT]/[RATIONALE]`）。

### P0 / 阻断：`identity_model` 是可伪造的配置声明，不是 engine-observed identity

`build_binding()` 直接读取 TOML 的 `identity_model`，`KimiAdapter.identity()`
原样返回；注入探针只验证进程能通过指定配置返回 sentinel，**完全不验证实际模型**。
故任意人可把 provider 真实路由指向模型 A、却声明模型 B，从而打开 WP-08 的
degraded 路径或制造「不同模型」评级。

→ `WP-15-brief.md:29-32` 不应宣称本 WP 足以解锁 A5 修法 1。A5 必须继续阻断，
直到身份来源被降格为「配置声明」或增加由可信网关/响应元数据证明的身份机制。

**这直接回答了第 5(b) 问：现有代码没有防线。**

### P1 / 阻断 A5：临时文件是完整 Kimi 配置，不是覆盖片段

`_temp_config()` 只输出 provider/model，而 `--config-file` 会**独立加载**该文件，
不与 `~/.kimi/config.toml` 合并。丢失的远不止上下文窗口：`default_thinking`、
模型 `capabilities`、loop-control、hooks、MCP 等全局配置一并丢失。
WP-15 只修窗口，仍不能证明绑定前后执行语义等价。

### P1：provider 类型硬编码 `anthropic`，未证明适用于 codingplan/K3

`kimi.py:56-63` 固定生成 `type = "anthropic"` 并要求 `anthropic_base_url`，
但本机 K3 是 Kimi CLI 的 `type = "kimi"` managed provider，走 Kimi 协议 + OAuth。
新增 `max_context_size` 无法消除协议、认证和路由改变的风险。
WP-15 可作为独立 A6 修复执行，但**必须删除「完成后 A5 修法 1 即安全」的暗示**。

### P2：区分「显式配置值」与「兼容回退值」

`max_context_size` 是 Kimi 的 model 属性，不是 provider 身份属性；
直接设 `ProviderBinding.max_context_size = 786432` 会把「未声明」伪装成
「provider 声明了 768K」。更清晰的契约是 `max_context_size: int | None = None`，
由 Kimi renderer 在 `None` 时使用**命名的** legacy fallback `786432`。
不能直接省略模板字段——Kimi 的 `LLMModel.max_context_size` 是必填项。

### P2：校验和 DoD 缺少 Python `bool` 反例

`bool` 是 `int` 的子类；若实现只写 `isinstance(value, int) and value > 0`，
`True` 会被当作 `1` 接受。应明确拒绝 `True`/`False` 并加测试。

### P2：现有测试不足以证明真实兼容性或身份真实性

`tests/test_injection_probe.py:80-93` 的假 kimi 只检查 argv 是否出现
`--config-file`，不读 TOML，也不验证 provider、model、context。
rev2 应增加：默认模板逐字 characterization、自定义 1M 输出、
所有非法值（含 bool）、TOML 解析，以及使用固定支持版本 Kimi 配置模型的
离线解析测试。网络仍可保持禁止。

### 对编排者的一处纠正

`CLAUDE_CODE_EFFORT_LEVEL` 在 kimi 侧未发现支持，不应把它当作本 WP 必须透传的
字段；真正已确认缺失的语义是 thinking/capabilities 等完整配置项。

### `[RATIONALE]`（摘）

> A6 的核心判断成立：硬编码 768K 应改为可配置，并保留旧配置的兼容回退；
> 但当前 Brief 把这个窄修复错误提升成了 A5 的安全前置。它既未解决完整临时配置
> 替换造成的行为漂移，也未解决 `identity_model` 来自可编辑 TOML、可伪造独立性
> 证据的信任边界。

codex 声明本次严格只读、未修改任何文件；目标 pytest 因沙箱无可用临时目录
未能启动，不属于测试失败。

## 编排者独立核实

以下为编排者不依赖 codex 报告、直接读 `~/.kimi/config.toml` 得到的硬证据，
证实其 P1 两条的事实前提：

| 事实 | 位置 |
|------|------|
| `default_thinking = true` 是全局项 | `~/.kimi/config.toml:2` |
| `[models."kimi-code/k3"]` 的 `max_context_size = 1048576` | `:49` |
| 同模型 `capabilities = ["thinking", "video_in", "image_in"]` | `:50` |
| 本机 K3 provider 是 `type = "kimi"`，非 `anthropic` | `:70-71` |
| 该 provider 走 OAuth | `:75` |
| 另有 `[loop_control]` / `[background]` / `[notifications]` / `[mcp.client]` 与 13 个 `[[hooks]]` | `:79` 起 |

`tests/test_injection_probe.py:80-93` 的假 kimi 只 grep argv 里的
`--config-file`——已核实，属实。

**未能独立验证**：「`--config-file` 独立加载、不与全局配置合并」这一机制。
`kimi --version` 与 `kimi --help` 因 auto mode 安全分类器
（上游 `claude-sonnet-5` 超时）无法执行，该机制目前只有 codex 的核实作为依据。

## 采纳决定（编排者）

| codex 条目 | 处置 |
|-----------|------|
| P0 身份可伪造 | **采纳**。删除 WP-15 的「A5 修法 1 前置」定位；A5 修法 1 降级 |
| P1 完整配置替换 | **采纳**。记为 A5 的独立阻断条件，不由 WP-15 承担 |
| P1 `type="anthropic"` 硬编码 | **采纳**。同上，记为 A5 阻断条件 |
| P2 `int \| None` + 命名 fallback | **采纳**，改写交付物 1 |
| P2 `bool` 反例 | **采纳**，补进 DoD 反向测试 |
| P2 测试设计不足 | **部分采纳**：TOML 解析断言与 bool 反例纳入 rev2；「固定支持版本 Kimi 配置模型离线解析」超出本 WP 范围，记为后续项 |
| `CLAUDE_CODE_EFFORT_LEVEL` 纠正 | **采纳**，不列为本 WP 透传字段 |

## 对 A5 的影响（用户已裁定）

codex 的 P0 打穿了 A5 修法 1 的前提：那条路本质是**让合并门去读一个用户可手改的
TOML 字符串**，与 WP-08 存在的理由（不许自证）是同一类问题，只换了个字段。

编排者向用户提出三个选项，**用户裁定走修法 2**——新开 WP 扩展评级准则，
让 orchestrator-as-reviewer 的诚实 `ACCEPT` 有一条既不靠自证 attestation、
也不靠可伪造 `identity_model` 的通路。

修法 1（给 developer 绑 provider）不再作为首选；其三项阻断条件
（协议兼容、完整配置等价、可信模型身份）记录在案，供日后重启该路线时参考。

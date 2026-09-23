# 设计：kimi 额度不足自动回退 deepseek-flash

> 日期 2026-09-22 | 编排者 claude（orchestrator）| 状态：设计已与用户逐节确认，待转 writing-plans
> 交付路径：新 iteration + 新 plan + 单 WP，走完整「冻结 → 派发 kimi → 评审 → gate → merge」流程。
> 本文件是设计依据（spec），不是 WP brief；brief 在实现计划阶段由模板另起。

## 1. 问题与目标

`agentic redispatch` 派发 developer（kimi）时，当前配置 `roles.developer = "kimi"`
不绑 provider（`binding=None`），kimi 走自己的全局默认模型（kimi-for-coding），
吃 **kimi 套餐额度**。套餐耗尽时派发失败，`agentic redispatch` 直接
`REDISPATCH_STOP`，需人工介入切换模型。

**目标**：让框架在检测到 kimi 套餐额度不足时，**自动**改用 DeepSeek flash 档
（`deepseek-v4-flash`，v4-pro 的兄弟档、更廉价）重派一次，无需人工。全自动、
配置驱动、对现有裸 kimi 配置零回归。

**非目标**：不改 kimi CLI 本身；不做持久全局配置改写；不引入多档回退链
（kimi→flash 单跳到底）；不覆盖「probe 都因额度失败」的硬耗尽场景（见 §6 已知边界）。

## 2. 用户决策（brainstorming 逐问厘清，均为已确认事实）

| 维度 | 决策 |
|------|------|
| 检测信号 | 派发/probe **非零退出 + 输出含额度提示**；按**正向模式匹配**判定（命中额度关键词/正则才触发，普通失败不触发） |
| 落点层级 | **框架代码自动回退**（redispatch/adapter 层），配置驱动、全自动、无需人工 |
| 控制流 | **派发失败后重试**：先用原生 kimi 派发，失败且命中额度模式 → 换 flash binding **重派一次** |
| 回退链 | **单跳 kimi→flash**；flash 也额度失败 → `REDISPATCH_STOP` 交人工（不计数、不固化 v4-pro 档） |
| 实现方案 | **方案 1**：redispatch 层重试 + 配置 `fallback_provider` + 纯函数 `quota_fallback.py` + probe 语义保持不变 |

> 备注：用户此前提过的「flash 优先、>2 次异常回退 v4-pro」规则**仅属于 WP-01 手动派发的模型选择**，
> 经确认**不固化进本框架能力**（本能力是单跳）。

## 3. 现状（探索结论，实现前的事实基线）

- **唯一派发入口**：全框架仅 `src/agentic_loop/redispatch.py` 的 `_dispatch()` 调
  `adapter.implement()`。回退逻辑落点唯一。
- **developer 当前不绑 provider**：`.agentic/config.toml` `[roles] developer = "kimi"`
  → `resolve_role_binding("developer")` 返回 `("kimi", None)` → `KimiAdapter(binding=None)`
  → `implement()` 走 `kimi --afk --print -w <wt> -p <prompt>`（原生全局默认模型）。
- **flash 注入机制已存在**：`KimiAdapter._temp_config()` 在 `binding` 非空时生成 0600
  临时 TOML（DeepSeek anthropic 兼容 provider + model 段），派发命令变为
  `kimi --afk --print --config-file <tmp> --model <cli_selector> -w <wt> -p <prompt>`；
  `_run()` 对输出做 `redact_env_value(output, api_key_env)` 脱敏。**无需改 adapter 注入逻辑**。
- **provider 配置模板**：`init_cmd.py` `DEFAULT_CONFIG` 给出 DeepSeek provider 段标准形状
  （`anthropic_base_url = "https://api.deepseek.com/anthropic"`、`api_key_env = "DEEPSEEK_API_KEY"`、
  `identity_model`、`[providers.<name>.selectors] kimi = "deepseek/v4-pro"`）。
- **probe 门**：`redispatch.main()` 在派发前跑 `_resolve_developer(get_roles(), probe=True)`
  → `adapter.probe_injection()`（binding=None 时即 `kimi -p "reply PROBE_OK"`）；失败
  → `ProbeFailedError` → `REDISPATCH_STOP`。**本设计保持 probe 门语义不变**（尊重「派发失败后重试」决策）。
- **零回归挂载点**：`resolve_role_binding` 读 `roles.<role>`；dict 形态可带 `provider`。
  新增**可选** `fallback_provider` 键不影响既有解析路径。

## 4. 架构与组件（三层各司其职）

### 4.1 `src/agentic_loop/quota_fallback.py`（新增，纯函数，无 I/O 副作用）

```python
# codex consult rev1 finding #1：默认清单必须**语境化**（额度/账户/API 限制上下文），
# 不得保留 `insufficient`/`balance`/`credit`/`exceeded`/`billing`/`rate.?limit` 等无上下文
# 单词的裸匹配——否则会误判 `test count exceeded` / `insufficient permissions` /
# `billing module failed` / `credit card processor error` 等普通错误为额度失败，触发
# flash 重派而掩盖真实错误（违反 AGENTS.md §7）。B1 TDD 必须为每条歧义边界写负例。
DEFAULT_QUOTA_PATTERNS: tuple[str, ...] = (
    # 中文：语义明确，保留裸匹配
    r"额度", r"配额", r"套餐", r"余额不足",
    # 英文：quota 语义明确，保留裸匹配
    r"\bquota\b",
    # 英文：ambiguous 形容词/动词必须与账户/额度名词共现（前后近距）
    r"(insufficient|exceeded|exhausted|depleted|out of|no remaining|used up|not enough)\W{0,10}(balance|credit|credits|funds|quota|allowance|budget|subscription)",
    r"(balance|credit|credits|funds|quota|allowance|budget|subscription)\W{0,20}(insufficient|exceeded|exhausted|depleted|too low|not enough|used up|out of|empty|zero)",
    # HTTP 状态码：429/402 需与额度/付费语境共现，避免命中端口号/行数
    r"\b429\b.{0,80}(too many requests|rate.?limit|quota|usage)",
    r"(too many requests|rate.?limit).{0,80}\b429\b",
    r"\b402\b.{0,80}(payment|billing|quota|balance|credit|subscription)",
    r"(payment|billing).{0,20}\b402\b",
    # 明确的付费/订阅/限速短语
    r"payment\s+required",
    r"too\s+many\s+requests",
    r"rate.?limit\s+(exceeded|reached|hit|exhausted)",
    r"(subscription|payment)\s+(expired|overdue|failed|required)",
    r"weekly.{0,15}(usage|quota|limit).{0,25}(reached|exceeded|reset)",
    r"daily.{0,15}(usage|quota|limit).{0,25}(reached|exceeded|reset)",
)

def is_quota_error(output: str, patterns: Sequence[str] | None = None) -> bool:
    """纯字符串判定：output 命中任一额度模式（大小写不敏感）即 True。
    空输出 / 普通错误 / 成功输出一律 False（正向命中才触发，避免误判）。
    歧义边界（B1 TDD 必测负例）：
      - 'test count exceeded' -> False（`exceeded` 无账户上下文）
      - 'insufficient permissions' -> False（`insufficient` 无账户上下文）
      - 'billing module failed' -> False（`billing` 单独不匹配）
      - 'credit card processor returned error' -> False（`credit` 无耗尽语境）
      - 'AssertionError: rate_limit should be 5' -> False（`rate_limit` 无 exceeded/reached）
    """

def load_quota_patterns(repo: Path | None = None) -> tuple[str, ...]:
    """读可选 [quota_fallback] patterns；缺省/解析失败回落 DEFAULT_QUOTA_PATTERNS（fail-safe）。"""
```

- 纯函数、可单测；`is_quota_error` 跑在**已脱敏**的 `ImplementResult.output` 上，不回显 key。
- 模式清单可被项目配置覆盖，默认清单覆盖中英常见额度措辞。

### 4.2 `src/agentic_loop/resolve_paths.py` 新增 `resolve_role_fallback_binding`

```python
def resolve_role_fallback_binding(role: str, repo: Path | None = None) -> ProviderBinding | None:
    """读 roles.<role> 字典的可选 fallback_provider 键 → 复用 build_binding 构造回退 binding。
    键缺失 / role 非 dict / provider 段缺失或非法 → 返回 None（零回归，绝不抛到派发主链）。"""
```

- 与既有 `resolve_role_binding` 对称；只多认一个可选键。
- 返回 `None` 表示「未配置回退」，调用方据此保持原行为（额度失败即 STOP）。

### 4.3 `src/agentic_loop/redispatch.py` 新增 `_dispatch_with_quota_fallback`

```python
def _dispatch_with_quota_fallback(adapter, worktree, brief, prompt, dry_run,
                                  roles_config) -> tuple[ImplementResult, str | None]:
    """先派发当前 adapter；若失败且 is_quota_error(output)：
       解析 developer 的 fallback binding → 构造 flash KimiAdapter → 重派一次。
       返回 (最终 result, 实际生效的 fallback provider 名 or None)。
       单跳：flash 也额度失败则原样返回失败 result（由 main() 打 REDISPATCH_STOP）。"""
```

- 回退 adapter 构造复用 `_resolve_developer` 的 registry 模式（`KimiAdapter(kimi_bin=..., binding=flash)`），便于测试注入 stub。
- `main()` 在 `_dispatch(...)` 处改调本函数；据返回的 provider 名打日志（如
  `REDISPATCH_QUOTA_FALLBACK: provider=deepseekflash`）。

## 5. 数据流（单次 `agentic redispatch <status>` 内）

1. 校验 status → circuit-breaker（`redispatch_count >= REDISPATCH_MAX` 即 STOP，**不变**）。
2. **probe 门（不变）**：原生 kimi probe 必须通过才继续；非额度原因失败 → `REDISPATCH_STOP`。
3. **heartbeat 门（不变）**：`HEARTBEAT_OK` 才继续。
4. 构造 continuation prompt（不变）。
5. **派发 = `_dispatch_with_quota_fallback`**：
   - a. 用当前 adapter（binding=None=原生 kimi）`implement()`；
   - b. 若 `result.dispatched` 为真 → 成功，返回（provider=None）；
   - c. 若失败且 `is_quota_error(result.output)` 为假 → 原样返回失败（**行为不变**，不掩盖真实错误）；
   - d. 若失败且命中额度模式：
     - `resolve_role_fallback_binding("developer")` → None ⇒ 无回退配置 → 返回失败（STOP）；
     - 非 None ⇒ 构造 flash `KimiAdapter` → `implement()` **重派一次** → 返回（provider=flash 名）；
     - flash 仍额度失败 ⇒ **单跳到底**，返回失败 result（STOP，交人工）。
6. `dry_run` 分支不变（只打印命令形态）。
7. **计数语义不变**：`redispatch_count` 仅在主派发链最终成功后 +1。回退是「换 provider 重派」，
   **不额外 +1、不绕开 circuit-breaker**（circuit-breaker 计的是 rework 重派次数，非 provider 切换）。

## 6. 错误处理与安全边界

- **正向命中才回退**：仅命中额度模式才切 flash；普通失败/编译错误/测试失败照旧 STOP
  —— 不掩盖真实错误（守 AGENTS.md §7「不得弱化/隐藏失败」）。
- **单跳、无无限重试**：kimi→flash 一跳；flash 额度失败即 `REDISPATCH_STOP`，日志清晰交人工。
- **密钥安全**（AGENTS.md §6）：flash binding 用 `api_key_env = "DEEPSEEK_API_KEY"`，
  **绝不落盘明文**；`KimiAdapter._run` 已对输出 `redact_env_value` 脱敏；`is_quota_error`
  与所有日志均跑在已脱敏输出上，不回显 key。临时 config 0600、用后即删（既有 `_temp_config` 保证）。
  **消费面口径（brief 不变式）**：`is_quota_error` 与 `_dispatch_with_quota_fallback` 的
  日志**只**消费 `ImplementResult.output`（已脱敏），不得直接调 adapter 的原始
  stdout/stderr、不得读 env 值、不得在异常消息里回显 config 内容。
- **独立性评级不受影响**：主档 `developer` 无 `provider` 键 → `resolve_role_binding("developer")`
  返回 `("kimi", None)` → gate 在 `binding is None` 时**不生成** implementer identity
  （`gate/__init__.py:765` 短路，codex rev1 已核实）；无论 `review.decision` 是 `N/A`
  还是 `ACCEPT`，评级路径都不消费 fallback provider 的 `identity_model`。故切 flash
  **不改动信任根/评级语义**。B5 断言测试 `test_project_config_primary_developer_stays_native`
  锁定此不变式（`adapter_name == "kimi"` 且 `binding is None`）。
- **circuit-breaker / 锁 / autonomy 语义不变**：回退发生在已获取 WP 锁、已过 heartbeat、
  已过 circuit-breaker 之后的派发子步骤内，不新增写状态、不动锁、不触网。
- **已知边界（诚实标注）**：若额度**硬耗尽**到连极小的 probe 都失败，probe 门会先 STOP，
  此时不走 flash。这与用户 Q3「派发失败后重试」（而非「probe 预切」）的选择一致。
  将来若要覆盖，可加 probe 额度感知（需 probe 返回输出，属小扩展，本设计范围外）。

## 7. 配置（`.agentic/config.toml`，追加；不删改现有段）

```toml
# kimi 套餐额度不足时的自动回退目标（developer 派发用）。
[providers.deepseekflash]
anthropic_base_url = "https://api.deepseek.com/anthropic"   # kimi 走 anthropic 兼容端
api_key_env        = "DEEPSEEK_API_KEY"                      # 只存 env 名，绝不落盘明文
identity_model     = "deepseek-v4-flash"                     # 待确认精确 id（§10）
[providers.deepseekflash.selectors]
kimi = "deepseek/v4-flash"                                   # 待确认精确 selector（§10）

[roles]
# developer 主档仍是原生 kimi（不绑 provider）；仅新增可选 fallback_provider。
developer = { adapter = "kimi", fallback_provider = "deepseekflash" }

# 可选：覆盖默认额度模式清单（缺省用 quota_fallback.DEFAULT_QUOTA_PATTERNS）。
# [quota_fallback]
# patterns = ["额度", "quota", "insufficient", "429"]
```

- `init_cmd.py` `DEFAULT_CONFIG` 是否同步加入 `fallback_provider` 示例：**范围外**（§11），
  避免改动 init 模板触发 contract drift checksum；本项目配置直接编辑即可。

## 8. 测试计划（TDD；全部用 stub adapter/registry 注入，无真实网络/kimi —— 守 AGENTS.md §6）

- `tests/test_quota_fallback.py`
  - `is_quota_error` 各默认模式**正向**命中（中/英/数字码各取样）；
  - **负向**：普通报错、成功输出、空串、None-ish → False；
  - `load_quota_patterns`：config 覆盖生效；缺省/坏配置回落默认（fail-safe）。
- `tests/test_redispatch_quota_fallback.py`
  - 原生派发**额度失败** → flash 重派**一次**并成功（断言用了 flash binding、provider 名回填）；
  - 原生派发**非额度失败** → **不触发回退**，行为与现状一致（零回归）；
  - 原生额度失败 + flash 也额度失败 → **单跳 STOP**（不再三跳、不无限重试）；
  - **未配** `fallback_provider` → 额度失败即 STOP（零回归）；
  - 回退成功时 `redispatch_count` **只 +1**（不因换 provider 双计）；
  - circuit-breaker（count>=max）仍在回退之前生效；
  - developer 切 flash **不改**独立性评级（断言 implementer identity 语义不变）。
- 回归：`python3.11 -m pytest tests -q` 全绿（§9 / `[[gate]]` 规则）；已知 4 个
  `test_finalize_merge_triple_sign.py` 预存失败（main 被 sibling worktree 占用）为基线，非本改动引入。

## 9. 交付路径与治理（用户选：完整 WP 流程）

- 新建 iteration：`docs/plans/2026-09-22-kimi-quota-flash-fallback/`（本 spec 已置于此）。
- 新建 plan（`PLAN.json` 模板 → `agentic-plan-status/v1`）：集成分支
  `plan/2026-09-22-kimi-quota-flash-fallback`，`target_branch = main`，从最新 `main`（7c318f4）切出。
- 单 WP（`WORK_PACKAGE.md` + `STATUS.json` 模板）：独立 feature 分支 + 独立 worktree
  （`main` 被 `agentic-loop-main-codex-merge` 占用，故必须用 `git worktree add`）。
- allowed_paths：`src/agentic_loop/quota_fallback.py`、`src/agentic_loop/resolve_paths.py`、
  `src/agentic_loop/redispatch.py`、`tests/test_quota_fallback.py`、
  `tests/test_redispatch_quota_fallback.py`、`.agentic/config.toml`。
- forbidden_paths：`src/agentic_loop/independence.py`、`src/agentic_loop/gate/**`、
  `src/agentic_loop/adapters/kimi.py`（注入机制已够用，不改）、`uv.lock`、其它 WP 所有权文件。
- 生命周期：DRAFT →（codex consult，见 §10 待确认是否强制）→ APPROVED → 派发 kimi
  （原生套餐允许则用原生；本 WP 自身不依赖回退能力）→ READY_FOR_REVIEW → 独立评审 →
  `agentic gate`（phase tier 视 plan 定义）→ APPROVED_FOR_MERGE → `merge --no-ff` → `agentic finalize`。
- **不污染现有 plan**：本 iteration 与 `plan/2026-09-22-framework-hardening`（WP-01 在 REWORK#3 中途）完全隔离。
- **push 仍 always_stop**：合并到 main 后的 push 保留人工批准。

## 10. 假设与待确认

1. **flash 精确 model id / kimi selector**：本设计按 v4-pro 命名规律推
   `identity_model = "deepseek-v4-flash"`、`selectors.kimi = "deepseek/v4-flash"`。
   **实现前须对 DeepSeek API / kimi 模型注册表确认精确串**（错误 id 会触发 kimi config 校验拒启动）。
2. **额度错误原文锚定**：用户 convenience 时贴一次真实额度错误原文，把它加进
   `DEFAULT_QUOTA_PATTERNS` 做精确锚定（当前默认清单为通用覆盖，不阻塞实现）。
3. **是否强制 codex consult 才冻结**：本 WP 非信任根（不碰 independence/gate 评级），
   按章程 §3.2 非强制；但派发路径属较敏感引擎面，建议冻结前过一次 codex consult（低成本第二签名）。
   实现计划阶段定夺。

## 11. 范围外（YAGNI，明确不做）

- 多档回退链 / flash→v4-pro 计数回退（用户选单跳）。
- probe 阶段的额度预切（用户选「派发失败后重试」）。
- 持久化改写全局 `~/.kimi/config.toml`（那是 `agentic provider` 的手动职责，本能力是运行时按派发回退）。
- claude/codex adapter 的同类回退（当前只有 kimi 是 developer 且吃套餐额度；泛化留待真实需要）。
- 改 `init_cmd.py` DEFAULT_CONFIG 模板（避免 contract drift；项目配置直接编辑）。

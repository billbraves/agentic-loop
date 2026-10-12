# WP-01: developer 探针失败不得静默降级到 claude

> 冻结日期 2026-10-10 | rev4 | 编排者 claude-code | 执行者 kimi
> 冻结后执行期间只读。修订走 re-freeze(rev5),不原地改。
> 基线 `main` `0ba058d`。设计见同目录 `DESIGN.md`。
> 存档:rev1 `WP-01-brief.rev1.md`、rev2 `WP-01-brief.rev2.md`、
> rev3 `WP-01-brief.rev3.md`(含 rev3 相对 rev2 的变更表)。
> rev4 由第三轮二签 REWORK(`.agentic/wp01-brief-consult-r3-attempt2.answer.md`,
> `CODEX_DECISION: REWORK`,绑定 worktree head `a4bc5d7` / brief rev3
> sha256 `ea608a02`)驱动,逐条关闭其**五项必改**(见 §「rev4 相对 rev3 的变更」)。
> 该轮 r3 attempt 1 已作废(answer 空体、verdict 未写出即耗尽预算),
> 见 receipt 的 `voided_attempts`。
> 配置权威仍是 `main_repo()`,未改全局语义,故本轮仍停在 REWORK 不升 CONSULT。
> **本 brief 尚未获授权实现**:r3 receipt 记 `implementation_authorized: false`、
> `dispatch_authorized: false`、`wp_state_at_dispatch: "DRAFT"`。
> rev4 冻结后须再过一轮二签(r4)才谈派发。

## 目标(一句话)

`_resolve_developer()` 在 developer 首选探针失败时,按失败原因分流到「单跳 flash 回退」
或「STOP 交人」,**绝不**推进到另一个 adapter 把 developer 静默换成 claude;
且探针原始输出只在内存里参与额度判定,不进 reasons / 异常 / 日志 / status。

## rev4 相对 rev3 的变更(五项必改的关闭方式)

> rev3 相对 rev2 的变更表见存档 `WP-01-brief.rev3.md`。

| r3 必改项 | 关闭方式 | 落点 |
|---|---|---|
| 1. 增加 `INV-P2b`:额度输出且 `fallback_binding=None` 时抛 `ProbeFailedError`,Claude 工厂/探针计数均为 0;绑定 mutation 将该 STOP 分支精确替换为返回 Claude | F6 把「额度命中但未配 fallback」从「视同非额度失败」**拆成自己的具名分支**,冻结独立异常文案 `probe failed: quota, no fallback`;新增 **INV-P2b** + **M-P2b** 绑在该 raise 上 | §F6;INV-P2b |
| 2. 重写 M-P8:冻结完整可直接施加的 import/表达式,测试 monkeypatch 实际 lookup namespace,去掉不存在的 `_first_of`;签名断言改为参数名、顺序、keyword-only kind 与无 `*args/**kwargs` 的精确断言 | M-P8 冻结为**两段式逐字替换**(恢复模块级 `from agentic_loop.resolve_paths import get_roles` + 表达式改用 `get_roles().get("developer")[0]`);INV-P8 的 monkeypatch 目标改为 `agentic_loop.redispatch.get_roles`(`raising=False`,已实测可用);签名断言改为 `inspect.signature` 的有序 `(name, kind)` 列表精确相等 | INV-P8 / M-P8 |
| 3. 增加 native detail 零外流不变式:`binding=None`、native stdout 含哨兵时,异常、`reasons`、stdout/stderr 均不得含原文;绑定只泄露 native 输出的明确 mutation | 新增 **INV-P6c**(真实 `KimiAdapter(binding=None)` + stub `subprocess.run`)+ **M-P6c**(在探针调用行后插入 `if binding is None: reasons.append(probe_output)`,条件泄露,故 INV-P6 恒绿、仅 INV-P6c 转红) | §F7;INV-P6c |
| 4. 将 M-P4 的唯一承重 oracle 改为新增的 base-inheriting exact-bool 测试;既有十条列为 must-stay-green | M-P4 承重测试改为 `test_base_default_probe_injection_returns_exact_bool`;`tests/test_injection_probe.py` 既有 10 条**降级**进「必须保持绿集合」 | INV-P4;§必须保持绿集合 |
| 5. 在 DoD 写明 mutation 顺序 | DoD 新增「变异施加顺序(强制)」五步法:先实现并全绿 → 验证原表达式存在 → 施加单条变异 → 确认具名测试转红 → 恢复源文件再下一条 | §DoD |
| (建议项,采纳)`M-P1c`/`INV-P1c` 改名以免误导「承重不变式」计数 | 全量改名为 **`CHAR-P1c`**,并在 DoD 与计数口径里单列「characterization 前提」,不计入带变异的承重不变式 | CHAR-P1c;§DoD |
| (编排者 rev4 自补)「不换 adapter」此前只是**偶然**成立:flash 回退若写 `registry["kimi"](fallback_binding)`,在首选非 kimi 时本身就是跨 adapter 换派 | F6 冻结 flash 构造为 `registry[adapter_name](fallback_binding)`;新增 **INV-P2c** + **M-P2c** 用非 kimi 首选把「同一 registry key」钉成结构性事实 | §F6;INV-P2c |

## 范围

`allowed_paths`
- `src/agentic_loop/redispatch.py`
- `src/agentic_loop/adapters/base.py`
- `src/agentic_loop/adapters/kimi.py`
- `tests/test_redispatch_quota_fallback.py`
- `tests/test_injection_probe.py`

`forbidden_paths`
- `src/agentic_loop/resolve_paths.py`(`DEFAULT_ROLES` 展平是无害设计,见 DESIGN §2;
  本 WP 的配置权威问题一律在 `redispatch.py` 内显式穿 `repo` 解决,**不动解析器**)
- `src/agentic_loop/quota_fallback.py`(判定逻辑复用,不改)
- `src/agentic_loop/bootstrap_cmd.py`(F1 的加法设计正是为了让它零改动)
- `src/agentic_loop/adapters/claude.py`、`adapters/codex.py`
- `.agentic/config.toml`(rev2 起禁写:rev1 的 F4 已删除)
- `src/agentic_loop/secret_redaction.py`(复用 `redact_env_value`,不改)
- `uv.lock`(本仓当前**未跟踪**此文件,列入即禁止新建)、
  `docs/plans/2026-09-*/**`、其他任何路径

> 若实现中发现**必须**改 `resolve_paths.py` 才能完成 F5,**立即 BLOCKED 上报**,
> 不得自行扩范围 —— 那等于改配置权威语义,须升 CONSULT。

## 输入

- `DESIGN.md` §1 缺陷、§2 非缺陷(勿"顺手修")、§3 四条取向
  (rev2 冻结前编排者已修正两处:§3 R3 的实现处数由「5 处」改为**四处定义**
  `adapters/base.py:193` / `kimi.py:168` / `claude.py:126` / `codex.py:199`
  + 唯一独立生产调用方 `bootstrap_cmd.py:88-92`;§3 R4 标注为**已移出本 WP**。
  `DESIGN.md` 不在 `allowed_paths`,执行者零改动)
- 二签 r1 全文:`.agentic/probe-wp01-brief-consult.answer.md`(rev2 八项必改来源)
- 二签 r2 全文:`.agentic/wp01-brief-consult-r2.answer.md`(**本 rev 四项必改来源**)
- `quota_fallback.py`:`is_quota_error(output, patterns=None)`、
  `load_quota_patterns(repo)` 已就位,**直接复用,不要新写判定**
- `resolve_role_binding(role, repo=None)` / `resolve_role_fallback_binding(role, repo=None)`
  均已接受 `repo`,**调用方传参即可**,不需改解析器
- `secret_redaction.redact_env_value(text, api_key_env)` 已就位

## 功能点

**F1 探针交出输出(加法,不改 bool 签名,默认实现不得递归)**
在 `adapters/base.py` 新增 `probe_injection_detail(self) -> tuple[bool, str]`。
默认实现必须**自己**完成判定,**绝不**回调 `self.probe_injection()`:
`_binding is None` → `return (self.probe(), "")`;否则保持现默认的 fail-closed
语义(`raise NotImplementedError(...)`,文案可沿用)。
`probe_injection()` 改为 `return self.probe_injection_detail()[0]`。
> 陷阱:若默认 detail 回调 `probe_injection()`,而 `probe_injection()` 又委托
> detail,则无限递归 —— 二签 r1 Q9 明确点出。必须写成非递归。
`claude.py` / `codex.py` 不改,继承 base 默认,bool 契约不变。

**F2 kimi 两条真实 detail 路径都要交出真实输出**
`adapters/kimi.py` 覆写 `probe_injection_detail()`,两条路径都返回**真实**输出:
- `_binding is None`(原生 kimi):不得只 `return (self.probe(), "")`。必须真跑
  原生探针命令 `[self._kimi_bin, "-p", "reply PROBE_OK"]` 并返回其 stdout,
  `ok = (proc.returncode == 0 and "PROBE_OK" in out)`;
  否则生产原生 kimi 永远认不出额度文本 —— 二签 r1 Q1 第二条逃逸。
- `_binding` 非空(provider 绑定):跑注入探针
  `[self._kimi_bin, "--config-file", cfg, "--model", self._binding.cli_selector,
  "-p", self._PROBE_PROMPT]`,`ok = (proc.returncode == 0 and self._SENTINEL in out)`。
两条路径的脱敏按 F7 的**分路政策**处理(不是"都脱敏")。
`OSError` 分支返回 `(False, "")`。

**F3 不触碰主 binding 评级(范围已校正为"被审 checkout 配置不变式")**
`resolve_paths.py` 在 `forbidden_paths`,解析器语义由构造保证不变。
`test_project_config_primary_developer_stays_native`(断言
`resolve_role_binding("developer", repo=REPO) == ("kimi", None)`,`REPO` 是本
checkout)必须保持绿。
**但必须如实记账**:该断言只是**被审 checkout 的配置不变式**,不是生产零回归。
编排者 2026-10-09 实测的生产权威(`main_repo()` = `/Users/admin/vibe/agentic_loop`)结果是
主 binding = `deepseekflash`(`identity_model=deepseek-flash`)、fallback = `None`;
被审 checkout 结果相反(主 = `None`、fallback = `deepseekflash`,
`identity_model=deepseek-v4-flash`)。两边 `config.toml` 内容不同,不是解析器 bug。
本 WP **不改任何 config.toml**,也不试图统一两边;执行报告须复述这一实测事实,
不得把 checkout 断言写成"生产不回归"。

**F4(rev1)已删除**
rev1 的 `.agentic/config.toml` 规范化与本 WP 的行为目标无关,且生产 config 不读
被审 checkout 的值,属另一目的。二签 r1 Q7 建议移出,rev2 采纳:`config.toml`
进 `forbidden_paths`,`test_project_config_resolves_flash_fallback` 的断言
**保持 checkout 现值不动**(`identity_model == "deepseek-v4-flash"`、
`cli_selector == "deepseek/v4-flash"`),列入「必须保持绿集合」。

**F5 单一配置权威:删 `roles_config`,显式穿 `repo`,一处取数**
**签名改为**:`_resolve_developer(*, repo: Path, registry: dict[str, Any] | None = None,
probe: bool = True) -> tuple[Adapter, list[str], bool]`。

- **删除 `roles_config` 形参**(二签 r2 Q4 首选项)。它来自展平后的 `get_roles()`,
  与 `get_roles_raw()` 驱动的 binding 是两个配置视图,保留形参就留着重新分叉的口子。
  adapter 名与 binding 必须出自**同一次**解析:
  `adapter_name, binding = resolve_role_binding("developer", repo=repo)`。
- `fallback_binding = resolve_role_fallback_binding("developer", repo=repo)`
- `quota_patterns = load_quota_patterns(repo)`
- **连带面(已全仓检索确认封闭,共四处)**:
  - 定义 `redispatch.py:126`
  - `main()` `:480` `adapter, _ = _resolve_developer(get_roles(), probe=True)`
    → `adapter, _, fb = _resolve_developer(repo=repo_root, probe=True)`
  - `main()` `:532` `adapter, _ = _resolve_developer(get_roles(), probe=False)`
    → `adapter, _, fb = _resolve_developer(repo=repo_root, probe=False)`
    (**legacy `PROBE_CMD` 路径专属**,见 DoD 的定向覆盖要求)
  - `tests/test_redispatch_quota_fallback.py:234` 的 monkeypatch
    `lambda roles, probe=True: (_StubDev(), [])`
    → `lambda *, repo, registry=None, probe=True: (_StubDev(), [], False)`
- `get_roles` 在 `redispatch.py` 删后只剩 `:35` 的 import 成为死引用,**一并删除**
  (全仓检索:redispatch 内除 import 外仅 `:480` / `:532` 两处调用)。
  `resolve_paths.get_roles` 本身不动(仍被其他模块使用)。
- `repo_root = main_repo()` 已在 `main()` 现有行内,权威保持 `main_repo()`。

**F6 单一首选 + 原因分流 + 回退状态贯通**
`_resolve_developer()` 按 F5 取到唯一首选后探针:
- 探针通过 → 原样返回,`fallback_applied = False`。
- 探针失败且 `is_quota_error(probe_output, quota_patterns)` 为真且
  `fallback_binding` 非空 → 用 `fallback_binding` 构造 flash adapter 返回,
  `fallback_applied = True`。**构造表达式冻结为**
  `registry[adapter_name](fallback_binding)` —— 见下方「同一 registry key」。
- 探针失败且命中额度但 `fallback_binding is None` → **独立具名 STOP 分支**,
  `raise ProbeFailedError("probe failed: quota, no fallback")`。
  rev3 把它写成「视同非额度失败」,实现上会与非额度分支共用同一个 raise,
  于是「额度命中 + 无 fallback」没有自己的承重位点:实现可在这一支改派 claude
  而通过 rev3 全部不变式与变异(二签 r3 Q2/Q9 判定的决定性漏面)。
  本 rev 把它拆成**自己的 raise 语句**,由 INV-P2b / M-P2b 直接锁定。
  > 文案 `probe failed: quota, no fallback` 只含固定类别词,不含探针输出,
  > 不违反 F7;INV-P6 的哨兵断言针对探针输出原文,与本文案无交集。
- 其余一切失败(含 `adapter_name` 不在 registry)→ `raise ProbeFailedError`。

**同一 registry key(rev4 新增的结构性约束)**
flash 回退**必须**用 `registry[adapter_name](fallback_binding)` 构造,
**不得**写成 `registry["kimi"](fallback_binding)`。rev3 之前「不换 adapter」在
flash 支上只是**偶然**成立 —— 因为生产首选恰好是 kimi;一旦 `roles.developer`
首选改成别的 adapter,硬编码 `"kimi"` 本身就是一次静默跨 adapter 换派,
正是本 WP 唯一目标所禁止的。该约束由 INV-P2c / M-P2c 用**非 kimi 首选**钉死。

**删除**三段跨 adapter 逻辑:`:165-171` 的候选循环与其中的 `continue`、
`:178` 的「all configured ... falling back to built-in kimi」、
`:159-165` 候选为空分支的 `registry["kimi"](binding)` 兜底。
删除后函数体内**不存在任何候选循环**,只有一个 `adapter_name`。
**返回值扩为三元**:`(adapter, reasons, fallback_applied: bool)`。
`main()` 在 `fallback_applied is True` 时,给
`_dispatch_with_quota_fallback(...)` 传 `fallback_binding=None`,
使"探针阶段已跳 flash"后不可能再 flash→flash(二签 r1 Q1 第三条逃逸、`:538-543`)。

**F7 探针原始输出禁止外流(分路脱敏政策)**
原始探针输出的**唯一**用途是在内存里喂 `is_quota_error()`。
- `reasons` / `ProbeFailedError` 文案 / stdout / stderr / status 只允许写**固定类别**
  (如 `probe failed: quota` / `probe failed: other` / `unknown developer adapter`),
  **不得**拼接探针输出、config 原文或 env 值。
- **bound 路径(`_binding` 非空)**:返回前必须
  `out = redact_env_value(out, self._binding.api_key_env)`。这是硬性不变式,
  由 INV-P6b 直接 oracle 锁定。
- **native 路径(`_binding is None`)的安全语义(取二签 r2 Q6 选项 (a))**:
  原生 kimi 没有本仓已知的 `api_key_env`。编排者 2026-10-09 实测了两件**不同**的事,
  执行者不得混用:
  - `_run(..., redact_env=None)` **跳过**脱敏 —— 因为 `kimi.py:129` 是 `if redact_env:`
    守卫,`None` 为假即原样返回 `proc.stdout`;
  - `redact_env_value(text, None)` **不是原样返回,而是抛 `TypeError`** ——
    其签名为 `(text: str, api_key_env: str)`,实现首行 `os.environ.get(api_key_env)`
    对 `None` 抛 `TypeError: str expected, not NoneType`(实测)。
    故**严禁**写成 `redact_env_value(out, self._binding.api_key_env if self._binding else None)`
    这类统一调用,native 分支会直接崩。native 分支必须**不调用** `redact_env_value`。

  因此:
  - 该 detail 字符串被声明为 **resolver 内部敏感值**,`_resolve_developer()` 内
    除喂 `is_quota_error()` 外**零外流**(由 INV-P6 锁定);
  - **不得**在代码注释、docstring 或执行报告中声称"adapter 已对原生 kimi 凭证脱敏"
    —— 本 WP 不知道原生凭证 env 名,声称即是假陈述;
  - rev2 的措辞「按现有 `_run` 的脱敏约定处理,不得裸返回」**作废**:
    `_run(..., redact_env=None)` 本身就是裸返回,该要求不可执行。
  - 若未来要真脱敏原生路径,须先确定原生 credential env 名与算法,属另一 WP。

## 承重不变式与必须转红的变异

每条不变式绑一个具名 source mutation。**报告须逐条记录「施加变异 → 实测转红」**,
含命令与输出;变异后须先断言被变异的源文件确实与原文不同(避免空变异读成绿)。
变异一律施加在**生产源文件**上,不得改测试自己的 stub 来制造红。

**每条 M-* 以四元组冻结(二签 r2 必改项 4)**:目标函数 / 原表达式(预期实现中逐字
存在的片段)/ 变异表达式(逐字替换为)/ 唯一承重测试。执行者**不得**自行选择变异
位点或措辞;若预期实现里找不到所列原表达式,**立即 BLOCKED 上报**,不得近似施加。

- **INV-P1「探针失败不得换 adapter」**
  测试:`registry` 注入 `kimi`(探针恒失败,输出为**非额度**文本如 `compile error`)
  与 `claude`(探针恒成功、工厂与探针均带计数的 stub);
  `fallback_binding` 为 `None`;断言抛 `ProbeFailedError`
  **且 claude stub 的工厂与探针调用计数均为 0**。
  - **M-P1** 目标函数:`redispatch._resolve_developer`
    原表达式:`raise ProbeFailedError("probe failed: other")`
    变异表达式:`return registry["claude"](None), reasons, False`
    承重测试:`test_probe_failure_never_builds_claude`(INV-P1)
  > 该变异在「无候选循环、唯一首选」实现上**确定存在位点**(非额度失败的 raise 分支),
  > 不依赖已被删除的 `continue` 结构 —— 修正 rev2 M-P1 的不可施加问题。

- **INV-P1b「未知 adapter 名不得换 adapter」**
  测试:让 `resolve_role_binding` 返回 registry 里不存在的名字(monkeypatch 解析器
  返回值,**不改 config 文件**),registry 里仍放带计数的 `claude` stub;
  断言抛 `ProbeFailedError` 且 claude 计数为 0。
  - **M-P1b** 目标函数:`redispatch._resolve_developer`
    原表达式:`raise ProbeFailedError("unknown developer adapter")`
    变异表达式:`return registry["claude"](None), reasons, False`
    承重测试:`test_unknown_adapter_never_builds_claude`(INV-P1b)

- **CHAR-P1c「空配置折叠事实的锁定测试」(rev3 重写;rev4 改名)**
  > **计数口径**:本条是 **characterization 前提**,不是带变异的承重不变式。
  > 改名即为避免「N 条承重不变式」把它算进去(二签 r3 Q4 建议项)。
  rev2 的「候选为空 → STOP」是**生产不可达分支**:编排者 2026-10-09 实测,
  `resolve_role_binding("developer", repo=d)` 在五种退化配置下
  (无 `.agentic/config.toml`、`[roles]` 为空、`developer = []`、`developer = ""`、
  developer 缺项而其他 role 存在)**一律**返回 `("kimi", None)`,
  `resolve_role_fallback_binding` 一律 `None` —— 因为
  `resolve_paths.py:364-367` 的 `_first_candidate(DEFAULT_ROLES.get(role)) or "claude"`
  把缺项/空值折叠成内建默认。F5 把 `resolve_role_binding()` 定为唯一权威后,
  `_resolve_developer()` **永远**拿到非空 `adapter_name`,"候选为空"不可触达。
  因此本不变式**不再测 STOP 分支**,改为锁定折叠事实本身:
  测试:对一个 `tmp_path` 下的空配置仓,断言
  `resolve_role_binding("developer", repo=tmp) == ("kimi", None)`
  且 `resolve_role_fallback_binding("developer", repo=tmp) is None`。
  - **变异绑定:无**(本 characterization 前提是**只读事实锁定**,不绑生产变异)
    理由:它锁定的是 `resolve_paths.py`(**forbidden**)的既有行为,
    本 WP 不改该文件,故无可施加的本 WP 变异。
    作用:若将来有人改掉折叠语义,本测试会红,迫使重审 `_resolve_developer()`
    的"adapter_name 恒非空"前提。
  > **产品决策(冻结)**:"原始空配置必须 STOP 而不是默认 Kimi"**不在本 WP 范围**。
  > 要那个语义必须改 `resolve_paths.py`(forbidden),属升 CONSULT 的范围扩大,
  > 不得在本 WP 内绕道实现(二签 r2 Q8 要求 rev3 先澄清此点)。

- **INV-P2「额度失败走单跳 flash,而非 claude」**
  测试:`kimi` 探针失败且输出含额度措辞(用 `DEFAULT_QUOTA_PATTERNS` 能命中的字面
  文本,如 `insufficient balance`);`fallback_binding` 为 flash binding;
  断言返回 adapter 的 binding `provider == "deepseekflash"`、
  `fallback_applied is True`、claude stub 计数为 0。
  - **M-P2** 目标函数:`redispatch._resolve_developer`
    原表达式:`is_quota_error(probe_output, quota_patterns)`
    变异表达式:`False`
    承重测试:`test_quota_failure_routes_to_flash`(INV-P2)

- **INV-P2b「额度命中但无 fallback 必须 STOP,不得换 claude」(rev4 新增,关闭 r3 决定性漏面)**
  二签 r3 Q2 给出的漏网实现:在「额度命中 + 无 fallback」支上
  `return registry["claude"](None), reasons, False`,它能同时通过 rev3 的
  INV-P1/P2/P3/P5/P6/P7/P8/P9 与全部既列 mutation —— 因为 rev3 的 INV-P2
  只测 `fallback_binding` **非空**的那一半(rev3 `:232`),
  而 rev3 F6 又把本支与非额度支合并成同一个 raise,没有独立承重位点。
  测试:`kimi` 探针失败且输出含额度措辞(同 INV-P2 的 `insufficient balance`);
  **`fallback_binding` 为 `None`**(monkeypatch `resolve_role_fallback_binding`
  返回 `None`);registry 里 `claude` 为工厂与探针均带计数的 stub;
  断言抛 `ProbeFailedError`、异常文案等于 `probe failed: quota, no fallback`、
  **且 claude stub 的工厂与探针调用计数均为 0**。
  - **M-P2b** 目标函数:`redispatch._resolve_developer`
    原表达式:`raise ProbeFailedError("probe failed: quota, no fallback")`
    变异表达式:`return registry["claude"](None), reasons, False`
    承重测试:`test_quota_without_fallback_never_builds_claude`(INV-P2b)
  > 本条与 M-P1 的变异表达式逐字相同但**位点不同**(额度支的 raise vs
  > 非额度支的 raise),须分别施加、分别记红,不得合并记账 —— 同 M-P2/M-P3 的处理。

- **INV-P2c「flash 回退必须用同一个 registry key」(rev4 新增)**
  动机见 F6「同一 registry key」:若实现把 flash 构造写成 `registry["kimi"](...)`,
  在首选非 kimi 时这本身就是静默换 adapter,而所有以 kimi 为首选的测试都查不出来。
  测试:monkeypatch `resolve_role_binding` 返回 `("codex", binding)`
  (**非 kimi 首选**);registry 里 `codex` 为探针恒失败(输出额度措辞)、
  工厂带计数的 stub,`kimi` 亦为工厂带计数的 stub;`fallback_binding` 为 flash binding;
  断言:返回 adapter 由 **`codex` 工厂**构造(codex 工厂计数 1、
  **`kimi` 工厂计数 0**)、该工厂收到的实参 **is** `fallback_binding`、
  `fallback_applied is True`。
  - **M-P2c** 目标函数:`redispatch._resolve_developer`
    原表达式:`registry[adapter_name](fallback_binding)`
    变异表达式:`registry["kimi"](fallback_binding)`
    承重测试:`test_flash_fallback_uses_same_registry_key`(INV-P2c)
  > 该变异在以 kimi 为首选的 INV-P2 里**不会**转红(两者等价),
  > 这正是必须用非 kimi 首选单独立一条的原因。

- **INV-P3「探针输出确实被消费者读到」**
  测试:仅改 kimi stub 的探针**输出**(额度文本 ↔ 非额度文本)而不改其 ok 值,
  断言两次得到不同结局(flash adapter / `ProbeFailedError`)。
  - **M-P3** 目标函数:`redispatch._resolve_developer`
    原表达式:`is_quota_error(probe_output, quota_patterns)`
    变异表达式:`is_quota_error("", quota_patterns)`
    承重测试:`test_probe_output_is_read_by_consumer`(INV-P3)
  > 变异点必须在 `_resolve_developer()` 这个**消费者**处,不得挂在
  > `KimiAdapter.probe_injection_detail()` 上:本测试用自定义 stub,
  > 变异生产 kimi 碰不到被执行路径,会变成空变异。
  > M-P2 与 M-P3 变异同一行但**不同面**(谓词恒假 vs 入参置空),须分别施加、分别记账。

- **INV-P7「真实 kimi 两条 detail 路径都交出真实输出」**
  测试:用**真实** `KimiAdapter` + monkeypatch `subprocess.run`(不许真发网络),
  分别在 `binding=None` 与 `binding` 非空下调用 `probe_injection_detail()`,
  断言返回的输出字符串确实包含被 stub 的 stdout 内容(不是 `""`)。
  - **M-P7** 目标函数:`KimiAdapter.probe_injection_detail`
    原表达式(native 分支):`return (proc.returncode == 0 and "PROBE_OK" in out, out)`
    变异表达式:`return (self.probe(), "")`
    承重测试:`test_kimi_detail_native_returns_real_output`(INV-P7 的 native 半)

- **INV-P4「bool 契约零回归」(rev4 改绑承重 oracle)**
  **承重 oracle 是新增的「只继承 base」测试**,名为
  `test_base_default_probe_injection_returns_exact_bool`,置于
  `tests/test_injection_probe.py`:在测试文件内定义一个**只继承 `Adapter`、
  不覆写 `probe_injection` 也不覆写 `probe_injection_detail`** 的最小子类
  (须实现四个抽象方法 `capabilities` / `identity` / `probe` / `review`,
  已实测 `Adapter.__abstractmethods__` 恰为这四个),其 `_binding` 为 `None`
  (base 默认即 `getattr(self, "_binding", None) is None`,已实测可构造);
  令其 `probe()` 分别返回 `True` 与 `False`,两次断言
  `probe_injection() is True` / `probe_injection() is False` —— **`is` 精确比较**,
  元组一律不是 `True`/`False`,故 M-P4 的「返回整个元组」必红。
  - **M-P4** 目标函数:`Adapter.probe_injection`(`adapters/base.py`)
    原表达式:`return self.probe_injection_detail()[0]`
    变异表达式:`return self.probe_injection_detail()`
    承重测试:`test_base_default_probe_injection_returns_exact_bool`(INV-P4)
  > **rev4 改绑原因**(二签 r3 Q9 第三条):Claude、Codex、Kimi 三个 adapter
  > **当前都覆写 `probe_injection()`**(`claude.py:126`、`codex.py:199`、
  > `kimi.py:168`),F1 实现后它们会改成覆写 `probe_injection_detail()`;
  > `tests/test_injection_probe.py` 既有 10 条断言(`:50/61/70/77/93/103/112/127/137/144`)
  > 打的是这三个覆写子类,**不可靠地**杀死 base 的变异。本 rev 把既有 10 条
  > **降级进「必须保持绿集合」**,承重红证只认上面那条新增测试。
  > `tests/test_bootstrap.py:94-109` 只断 `rc != 0`(三个 adapter 全失败,
  > kimi 返真值元组它仍绿)、`tests/test_codex_gate_capability_merge.py:368-377`
  > 调 `probe_injection()` 但从不断 `ok` —— 同样只在「必须保持绿集合」,
  > 不得当作 M-P4 的红证来源(二签 r1 Q6;memory「negative assertions need a
  > mutation self-check」、「deleting a guard is not a load-bearing test」)。
  > 施加 M-P4 时须同时核对 `tests/test_injection_probe.py` 的既有 10 条
  > **是否也转红**:它们转红不构成红证,但**不转红亦不构成失败**;唯一判据是
  > 上述新增测试转红。

- **INV-P5「探针已跳 flash 后不得再 flash→flash」**
  测试:`_resolve_developer` 返回 `fallback_applied=True` 的路径进 `main()`
  (装配测试),断言传给 `_dispatch_with_quota_fallback` 的
  `fallback_binding is None`;并覆盖
  `_resolve_developer → main → _dispatch_with_quota_fallback` 全链
  (二签 r1 Q9 第四条:当前无测试覆盖该连线)。
  - **M-P5** 目标函数:`redispatch.main`
    原表达式:`fallback_binding=None if fallback_applied else fallback_binding`
    变异表达式:`fallback_binding=fallback_binding`
    承重测试:`test_probe_stage_flash_disables_dispatch_flash`(INV-P5)

- **INV-P6「探针原始输出不外流」**
  测试:让 kimi 探针 stdout 同时含 (a) 一个密钥哨兵值(通过
  `binding.api_key_env` 指向的 env 注入)、(b) 端点 URL、(c) 错误体文本;
  走完 `_resolve_developer()` 的失败分流,断言**所有可观测输出**
  (`ProbeFailedError` 文案、`reasons`、捕获的 stdout/stderr)
  均不含哨兵值、不含该端点原文、不含探针输出片段。
  - **M-P6** 目标函数:`redispatch._resolve_developer`
    原表达式:`raise ProbeFailedError("probe failed: other")`
    变异表达式:`raise ProbeFailedError(f"probe failed: other: {probe_output}")`
    承重测试:`test_probe_output_never_egresses`(INV-P6)
  > rev2 的「拼进 reasons 或异常」是执行者可自由选择的描述,不是冻结变异 ——
  > 二签 r2 Q9 第三条。本 rev 冻结为上述唯一异常文案替换。

- **INV-P6b「bound detail 返回值本身不含密钥」(rev3 新增直接 oracle)**
  rev2 的 M-P6b 不保证转红:去掉脱敏后,未脱敏密钥可能只存在于 detail 返回值与
  `_resolve_developer()` 内存中,而 resolver 仍只输出固定类别,于是 INV-P6 全绿
  (二签 r2 Q6)。本不变式补上直接 oracle:
  测试:构造真实 `KimiAdapter(binding=<flash binding>)`,`monkeypatch.setenv`
  使 `binding.api_key_env` 指向哨兵密钥值,monkeypatch `subprocess.run` 让
  stdout **包含该哨兵密钥值**;调用 `probe_injection_detail()`,
  断言**返回的 detail 字符串**不含该哨兵值(且为证明非空变异,
  同时断言 detail 含 stdout 里的另一段非密钥文本)。
  - **M-P6b** 目标函数:`KimiAdapter.probe_injection_detail`
    原表达式(bound 分支):`out = redact_env_value(out, self._binding.api_key_env)`
    变异表达式:`out = out`
    承重测试:`test_kimi_bound_detail_redacts_api_key`(INV-P6b)

- **INV-P6c「native detail 零外流」(rev4 新增,关闭 r3 必改项 3)**
  二签 r3 Q7:native 路径**确实不脱敏**(`_run(..., redact_env=None)` 走
  `if redact_env:` 守卫直接跳过替换,`kimi.py:125`),而 rev3 的 INV-P6 只用
  `binding.api_key_env` 注入哨兵,**实质只覆盖 bound 路径**。实现完全可以
  「仅当 `binding is None` 时把 `probe_output` 拼进 `reasons`」而 INV-P6 全绿。
  本不变式给 native 路径单独立 oracle:
  测试:monkeypatch `redispatch.resolve_role_binding` 返回
  `("kimi", None)`(**native,binding 为 `None`**),monkeypatch
  `subprocess.run` 让 kimi 探针 **stdout 含一个 native 专属哨兵串**
  (与 INV-P6/P6b 的密钥哨兵**取不同字面值**,避免两条测试互相顶替)
  且不含 `PROBE_OK`(使探针失败),quota patterns 不命中该文本(走非额度支);
  捕获 `ProbeFailedError` 后断言:异常文案、`reasons` 全部元素、
  capsys 捕获的 stdout 与 stderr **均不含该 native 哨兵串**;
  并断言异常文案**等于**固定类别文案 `probe failed: other`(证明不是空串假过)。
  - **M-P6c** 目标函数:`redispatch._resolve_developer`
    原表达式:`ok, probe_output = adapter.probe_injection_detail()`
    变异表达式:`ok, probe_output = adapter.probe_injection_detail()
    if binding is None: reasons.append(probe_output)`
    承重测试:`test_native_probe_output_never_egresses`(INV-P6c)
  > **为何必须是条件泄漏**:M-P6 已占住「异常文案拼接」这个位点
  > (`raise ProbeFailedError(f"probe failed: other: {probe_output}")`),
  > 无条件泄漏会让 INV-P6 与 INV-P6c 同时转红,无法区分是哪条在承重。
  > 本变异用 `if binding is None:` 守住,只在 native 路径泄漏,
  > 故 **INV-P6 保持绿、仅 INV-P6c 转红** —— 这正是「native 专属 oracle」的证明。
  > 执行者施加本变异后须同时记录 INV-P6 **仍为绿**,作为位点区分的证据。
  > **政策不变**(见 §附注):native detail 是 resolver 内存内的敏感值,
  > **零外流**是其安全边界;**不得**在代码注释、docstring 或报告里声称
  > adapter 已对未知 native credential 脱敏 —— 它没有。

- **INV-P8「`roles_config` 来源已消失:冲突输入不能影响选择」(rev4 重写变异)**
  测试 `test_flattened_roles_cannot_select_adapter`:
  - `monkeypatch.setattr("agentic_loop.redispatch.resolve_role_binding",
    lambda role, *, repo=None: ("kimi", binding))`;
  - `monkeypatch.setattr("agentic_loop.redispatch.get_roles",
    lambda *a, **k: {"developer": ["claude"]}, raising=False)`
    —— **`raising=False` 是必需的**:F5 要求删掉 `redispatch.py:35` 的
    `from agentic_loop.resolve_paths import get_roles`,正确实现里
    `redispatch.get_roles` **不存在**,不加该参数 monkeypatch 会直接
    `AttributeError` 而非得到冲突输入(memory「your own probe needs a no-op guard」);
  - **patch 的命名空间必须是 `agentic_loop.redispatch.get_roles`**,
    不是 `agentic_loop.resolve_paths.get_roles`:M-P8 在 `redispatch` 模块里
    以模块全局名调用,patch 源模块对已绑定的别名无效(二签 r3 Q3);
  - registry 里 `claude`、`kimi` 都是工厂带计数的 stub;
  - 断言:`kimi` 工厂计数 1、**`claude` 工厂计数 0**、返回 adapter 是 kimi stub。

  **签名精确断言**(同一测试内,二签 r3 Q5:只断「不含 `roles_config`」挡不住
  实现再加 `roles` / `*args` / `**kwargs`):
  ```python
  sig = inspect.signature(redispatch._resolve_developer)
  assert [(n, p.kind) for n, p in sig.parameters.items()] == [
      ("repo", inspect.Parameter.KEYWORD_ONLY),
      ("registry", inspect.Parameter.KEYWORD_ONLY),
      ("probe", inspect.Parameter.KEYWORD_ONLY),
  ]
  ```
  —— **有序列表相等**,因此参数名、顺序、kind 三者全锁;任何新增形参、
  任何 `VAR_POSITIONAL`(`*args`)或 `VAR_KEYWORD`(`**kwargs`)都会让列表不等而转红,
  无需再单写一条 varargs 断言(但执行者若愿加
  `assert not any(p.kind in (inspect.Parameter.VAR_POSITIONAL,
  inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values())` 作冗余,允许)。

  - **M-P8** 目标函数:`redispatch._resolve_developer`
    变异分**两步**,**均为逐字替换,执行者不得自选位置或措辞**:

    **步 1(恢复 import)**:在 `redispatch.py` 模块级 import 块里,
    紧跟
    `from agentic_loop.resolve_paths import resolve_role_fallback_binding`
    之后**新增一行**:
    `from agentic_loop.resolve_paths import get_roles`
    (F5 删除的就是这一行,原在 `:35`;恢复到末尾是为了位置唯一、可机械定位)

    **步 2(改选择表达式)**:
    原表达式:`adapter_name, binding = resolve_role_binding("developer", repo=repo)`
    变异表达式(两行):
    ```python
    adapter_name = get_roles(repo).get("developer")[0]
    _, binding = resolve_role_binding("developer", repo=repo)
    ```
    承重测试:`test_flattened_roles_cannot_select_adapter`(INV-P8)

  > **去掉 `_first_of`**:二签 r3 Q3 查实仓内无此函数,只有
  > `resolve_paths._first_candidate`(`:334`,且该文件在 `forbidden_paths`)。
  > rev3 要求执行者自行实现辅助,与「执行者不得自选变异措辞」自相矛盾。
  > 本 rev 直接用 `[0]` 下标:已实测 `get_roles()` 对 `developer` 返回
  > `['kimi', 'claude']`(list),`[0]` 即展平后的首选名,无需辅助函数。
  > **变异后期望行为**:`adapter_name` 变成 `"claude"`,于是构造
  > `registry["claude"](binding)` —— claude 工厂计数由 0 变 1,INV-P8 必红。
  > 执行者须先核对「变异后源文件确有不同」(两步都要),再跑承重测试。
  > **本条只能证伪它所冻结的这一个展平入口**:实现若经另一个展平配置入口
  > 恢复双权威,INV-P8 仍可能绿(二签 r3 Q10)。因此 INV-P9(同一 `repo`)
  > 与 F5 的 diff review 是本条的必要补充,不得以 INV-P8 绿替代 diff review。

- **INV-P9「binding / fallback / quota patterns 收到同一个 `repo`」(rev3 新增)**
  测试:用 spy 包住 `redispatch.resolve_role_binding`、
  `redispatch.resolve_role_fallback_binding`、`redispatch.load_quota_patterns`,
  记录每次收到的 `repo` 实参;以 `repo=tmp_path` 调用 `_resolve_developer`,
  断言三次记录**全部等于** `tmp_path`(不是 `None`、不是 `main_repo()`)。
  - **M-P9** 目标函数:`redispatch._resolve_developer`
    原表达式:`resolve_role_fallback_binding("developer", repo=repo)`
    变异表达式:`resolve_role_fallback_binding("developer")`
    承重测试:`test_all_config_reads_share_one_repo`(INV-P9)
  > 这正是现状缺陷:`main():538` 的 `resolve_role_fallback_binding("developer")`
  > 不传 `repo`,而 `:542` 的 `load_quota_patterns(repo_root)` 传了 —— 两个权威视图。

**必须保持绿集合**(防止 INV-P1 系列的收紧过度杀伤合法路径):
- `test_project_config_primary_developer_stays_native`
- `test_project_config_resolves_flash_fallback`(**断言不动**,见 F4)
- `tests/test_bootstrap.py`(全文件,含 `:94-109`)
- `tests/test_codex_gate_capability_merge.py`(全文件,含 `:368-377`)
- `_resolve_developer(..., probe=False)` 的既有行为(不探针时直接返回首选)
- 配置首选探针**通过**时的正常路径
- `tests/test_injection_probe.py` 既有 10 条断言(新增那条是增量,不替换)

## 交付物清单

- `src/agentic_loop/adapters/base.py`:新增非递归 `probe_injection_detail`,
  `probe_injection` 委托
- `src/agentic_loop/adapters/kimi.py`:覆写 `probe_injection_detail`,
  两条路径真实输出 + bound 路径脱敏
- `src/agentic_loop/redispatch.py`:`_resolve_developer` **删 `roles_config`**
  + 必填 `repo` + 单一权威 + 单一首选 + 原因分流 + 三元返回;
  `main()` 两处调用与 `fallback_binding` 贯通;删除死 `get_roles` import
- `tests/test_redispatch_quota_fallback.py`:
  INV-P1/P1b/P2/P2b/P2c/P3/P5/P6/P6b/P6c/P7/P8/P9 测试 + `CHAR-P1c`
  + 三元返回与新签名的 stub 同步
- `tests/test_injection_probe.py`:继承默认的精确 bool 断言
- 执行报告(§C 格式),含逐条变异红证 + F3 的生产/checkout 实测事实复述

## 完成定义(DoD)

- [ ] F1、F2、F3、F5、F6、F7 逐项实现(F4 已删除,`config.toml` 零改动)
- [ ] INV-P1/P1b/P2/P2b/P2c/P3/P4/P5/P6/P6b/P6c/P7/P8/P9 各有测试,
      且**各自绑定的变异实测转红**
      (报告逐条记录命令与结果;先证"变异后源文件确有不同")。
      **`CHAR-P1c` 例外**:它是 characterization 前提(只读事实锁定),
      无绑定变异(见该条说明),只需测试绿,**不计入带变异的承重不变式计数**
- [ ] 每条变异记账须含四元组对应关系:目标函数 / 原表达式 / 变异表达式 / 承重测试;
      凡预期实现中找不到所列原表达式的,报 BLOCKED 而非近似施加
- [ ] **变异施加顺序(强制五步法)**。本 WP 的全部变异都是对**完成后的实现**施加的
      反向证明,不是对当前缺陷态的检查。执行者必须严格按下列顺序:
      1. **先把 F1/F2/F3/F5/F6/F7 实现完,跑到全量绿**(含「必须保持绿集合」)。
         此前**不得**去核对任何变异的原表达式——当前代码里本来就没有它们
         (例如 `probe_injection_detail` 尚不存在、`_resolve_developer` 还带
         `roles_config`),此时检查锚点只会得到必然失配,从而报出**无谓的 BLOCKED**
         (二签 r3 Q8)。
      2. 对单条变异,先在源文件里**定位并确认「原表达式」逐字存在**;
         找不到才报 BLOCKED,且须附当前实际代码片段证明不是本步顺序错误。
      3. **只施加这一条变异**,并先证「变异后源文件确有不同」
         (如 `git diff --stat` 非空),杜绝空替换假绿。
      4. 运行该条**具名的唯一承重测试**,确认转红;记录命令与输出。
         非承重测试的连带红/绿按各条说明单独记录,**不得**充当红证。
      5. **恢复源文件**(如 `git checkout -- <file>`)并确认回到全绿,
         再进行下一条。**禁止多条变异同时在身**——叠加后无法区分是哪条在承重。
- [ ] 「必须保持绿集合」全部七项全绿
- [ ] **legacy `PROBE_CMD` 路径(`main():532`)有定向测试覆盖三元解包**
      (二签 r2 Q3/Q10:该路径只在 legacy 分支运行,漏改会在生产运行时才崩)
- [ ] `bootstrap_cmd.py`、`adapters/claude.py`、`adapters/codex.py`、
      `resolve_paths.py`、`quota_fallback.py`、`secret_redaction.py`、
      `.agentic/config.toml` diff 均为空
- [ ] 全量:`env -u AGENTIC_PYTHON GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch
      GIT_CONFIG_VALUE_0=main PYTHONPATH=src python3.11 -m pytest tests -q` 全绿,
      通过数 ≥ 本 WP base commit 实测基线。该基线由编排者 2026-10-09 在
      `715232d` 实测为 **807 passed, 4 skipped**(命令同上);`715232d` 相对
      base commit `0ba058d` 为 **doc-only**(`git diff --name-only 0ba058d..715232d`
      全在 `docs/`,已实测),故该数字在 `0ba058d` 同样成立。本 worktree
      `--collect-only` 为 811 collected(= 807 + 4,已实测)。执行者须在自己的
      worktree 复测该命令并记录实际数字,**不得从别的 WP brief 抄数字**
- [ ] **无测试退化**(二签 r3 Q9:通过数门禁单独不足 —— 新增测试会抵消被删旧测试)。
      报告须附 `git diff --stat` 与测试文件 diff review,逐条说明
      **被删除或被改弱的既有测试断言**;「必须保持绿集合」七项按名逐一记录结果。
      既有断言的删除/放宽**一律报 BLOCKED**,不得以「全量通过数未降」为由自行放行
- [ ] 无 `forbidden_paths` 写入
- [ ] 无生产 DB 写入、无网络(测试全用 stub,不得真打 DeepSeek/kimi)、无推送
- [ ] commit message 规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注:已知陷阱

1. **测试环境**:必须 `env -u AGENTIC_PYTHON`,否则 `AGENTIC_PYTHON` 漏进子进程
   shell 绕过 python3 stub 产生假失败;`python3.11` 无 agentic_loop,须 `PYTHONPATH=src`;
   临时仓缺 `main` 分支会让 4 个三签测试假失败,用进程级
   `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch GIT_CONFIG_VALUE_0=main` 消除。
   **不要改 git config。**
2. **口径权威源**:额度判定只有 `quota_fallback.py` 一份,禁止在 redispatch 里
   写第二份可执行判定(规范 §5.3)。
3. **评级不变式**:别"顺手"给被审 checkout 的 `roles.developer` 绑 `provider` ——
   那会把独立性评级从 weak-attested 翻成 degraded-weak。DESIGN §2 已说明;
   `config.toml` 整体在 `forbidden_paths`。
4. **纯函数优先**:`probe_injection_detail` 的输出口不要夹带 `now()`;它本身必须
   跑子进程(这是它的职责),但不得写文件、不得读 config。
5. **脱敏**:见 F7 的**分路政策** —— bound 路径硬性脱敏(INV-P6b 直接锁定);
   native 路径声明为 resolver 内部敏感值、零外流,**不得声称已脱敏**。
6. **递归**:F1 的默认实现绝不能回调 `probe_injection()`。
7. **配置权威**:`main_repo()` 是权威,不得改成"当前 worktree 配置是生产权威" ——
   那是语义变更,须 CONSULT,不在本 WP 授权内。
8. **冲突预告**:`wip/kimi-managed-k3-oauth` `1aa97e3` 也改 `probe_injection()`。
   本 WP 不管它;若后续并入由那一侧和解。
9. **空配置折叠是既有事实,不是本 WP 的缺陷**:见 `CHAR-P1c`。实测五种退化配置
   一律折叠为 `("kimi", None)`。本 WP 依赖"`adapter_name` 恒非空"这一前提,
   并用 `CHAR-P1c` 把该前提钉成测试;**不得**为了"空配置 STOP"去改 `resolve_paths.py`。
10. **M-P2 与 M-P3 变异同一行不同面**:一个把谓词置假,一个把入参置空。
    两条都要单独施加、单独记红,不得合并记账。

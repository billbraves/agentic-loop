# WP-01: developer 探针失败不得静默降级到 claude

> 冻结日期 2026-10-09 | rev3 | 编排者 claude-code | 执行者 kimi
> 冻结后执行期间只读。修订走 re-freeze(rev4),不原地改。
> 基线 `main` `0ba058d`。设计见同目录 `DESIGN.md`。
> 存档:rev1 `WP-01-brief.rev1.md`、rev2 `WP-01-brief.rev2.md`。
> rev3 由第二轮二签 REWORK(`.agentic/wp01-brief-consult-r2.answer.md`,
> `CODEX_DECISION: REWORK`,绑定 checkout `715232d` / brief rev2)驱动,
> 逐条关闭其**四项必改**(见 §「rev3 相对 rev2 的变更」)。
> 配置权威仍是 `main_repo()`,未改全局语义,故本轮仍停在 REWORK 不升 CONSULT。

## 目标(一句话)

`_resolve_developer()` 在 developer 首选探针失败时,按失败原因分流到「单跳 flash 回退」
或「STOP 交人」,**绝不**推进到另一个 adapter 把 developer 静默换成 claude;
且探针原始输出只在内存里参与额度判定,不进 reasons / 异常 / 日志 / status。

## rev3 相对 rev2 的变更(四项必改的关闭方式)

| r2 必改项 | 关闭方式 | 落点 |
|---|---|---|
| 1. 重写 INV-P1/M-P1、INV-P1c/M-P1c,使变异适用于「无候选循环、唯一首选」的预期实现;并明确承认空配置会折叠成默认 Kimi | M-P1 改为**在预期实现上确定存在**的源替换(把失败分支的 `raise` 换成构造 `registry["claude"](None)` 返回);INV-P1c **重写为「空配置折叠事实的锁定测试」**,不再测生产不可达分支 | §承重不变式 INV-P1 / INV-P1c;§附注 9 |
| 2. F5 加冲突来源测试或删 `roles_config`;并证明 binding/fallback/quota 收到同一 `repo` | **删 `roles_config`**(Codex 首选项),签名改 `_resolve_developer(*, repo, registry=None, probe=True)`;另加 INV-P8 冲突来源测试 + INV-P9 同一 `repo` spy | §F5;INV-P8 / INV-P9 |
| 3. M-P6b 加直接 detail 脱敏 oracle;明确 native `binding=None` 的安全语义 | 新增 INV-P6b(真实 bound `KimiAdapter.probe_injection_detail()` 直接 oracle);native 政策取 Codex 选项 (a):**resolver 内部敏感值、零外流,不声称已脱敏** | §F7;INV-P6b |
| 4. 所有 mutation 冻结成可机械复现的明确源替换 | 每条 M-* 统一写成**四元组**:目标函数 / 原表达式(逐字) / 变异表达式(逐字) / 唯一承重测试 | §承重不变式全节 |

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
  `fallback_applied = True`。
- 探针失败且命中额度但**未配** `fallback_provider` → 视同非额度失败,`raise`。
- 其余一切失败(含 `adapter_name` 不在 registry)→ `raise ProbeFailedError`。
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

- **INV-P1c「空配置折叠事实的锁定测试」(rev3 重写)**
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
  - **M-P1c** 目标函数:**无**(本不变式是**只读事实锁定**,不绑生产变异)
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

- **INV-P4「bool 契约零回归」**
  **承重 oracle 是 `tests/test_injection_probe.py`** —— 它有 10 条
  `probe_injection() is True` / `is False` 精确 bool 断言
  (`:50/61/70/77/93/103/112/127/137/144`)。另加一条**继承默认**的精确 bool 断言:
  对一个只继承 base、不覆写 detail 的 adapter,`binding=None` 时断言
  `probe_injection() is True`/`is False` 与底层 `probe()` 一致。
  - **M-P4** 目标函数:`Adapter.probe_injection`(`adapters/base.py`)
    原表达式:`return self.probe_injection_detail()[0]`
    变异表达式:`return self.probe_injection_detail()`
    承重测试:`tests/test_injection_probe.py`(既有 10 条断言)
  > `tests/test_bootstrap.py:94-109` 只断 `rc != 0`(三个 adapter 全失败,
  > kimi 返真值元组它仍绿)、`tests/test_codex_gate_capability_merge.py:368-377`
  > 调 `probe_injection()` 但从不断 `ok` —— 二者**降级为「必须保持绿集合」**,
  > 不得当作 M-P4 的红证来源(二签 r1 Q6;memory「negative assertions need a
  > mutation self-check」)。

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

- **INV-P8「`roles_config` 来源已消失:冲突输入不能影响选择」(rev3 新增)**
  测试:monkeypatch `redispatch.resolve_role_binding` 返回 `("kimi", binding)`;
  同时(若实现仍以任何方式读取展平 roles)monkeypatch
  `resolve_paths.get_roles` 返回 `{"developer": ["claude"]}`;
  registry 里 claude 为带计数 stub。断言只构造 Kimi、**claude 工厂计数为 0**。
  另断言 `_resolve_developer` 的签名不含 `roles_config`
  (`inspect.signature` 参数名集合断言,锁死形参删除)。
  - **M-P8** 目标函数:`redispatch._resolve_developer`
    原表达式:`adapter_name, binding = resolve_role_binding("developer", repo=repo)`
    变异表达式:`adapter_name, binding = (_first_of(get_roles().get("developer")),
    resolve_role_binding("developer", repo=repo)[1])`
    承重测试:`test_flattened_roles_cannot_select_adapter`(INV-P8)
  > 变异表达式需要重新 import `get_roles` 与一个取首项辅助;执行者按此逐字构造,
  > 若无法构造出"从展平 roles 取名"的等价变异,**BLOCKED 上报**,不得跳过本条。

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
  INV-P1/P1b/P1c/P2/P3/P5/P6/P6b/P7/P8/P9 测试 + 三元返回与新签名的 stub 同步
- `tests/test_injection_probe.py`:继承默认的精确 bool 断言
- 执行报告(§C 格式),含逐条变异红证 + F3 的生产/checkout 实测事实复述

## 完成定义(DoD)

- [ ] F1、F2、F3、F5、F6、F7 逐项实现(F4 已删除,`config.toml` 零改动)
- [ ] INV-P1/P1b/P2/P3/P4/P5/P6/P6b/P7/P8/P9 各有测试,且**各自绑定的变异实测转红**
      (报告逐条记录命令与结果;先证"变异后源文件确有不同")。
      **INV-P1c 例外**:它是只读事实锁定,无绑定变异(见该条说明),只需测试绿
- [ ] 每条变异记账须含四元组对应关系:目标函数 / 原表达式 / 变异表达式 / 承重测试;
      凡预期实现中找不到所列原表达式的,报 BLOCKED 而非近似施加
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
9. **空配置折叠是既有事实,不是本 WP 的缺陷**:见 INV-P1c。实测五种退化配置
   一律折叠为 `("kimi", None)`。本 WP 依赖"`adapter_name` 恒非空"这一前提,
   并用 INV-P1c 把该前提钉成测试;**不得**为了"空配置 STOP"去改 `resolve_paths.py`。
10. **M-P2 与 M-P3 变异同一行不同面**:一个把谓词置假,一个把入参置空。
    两条都要单独施加、单独记红,不得合并记账。

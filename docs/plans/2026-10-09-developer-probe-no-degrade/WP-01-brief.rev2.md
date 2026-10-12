# WP-01: developer 探针失败不得静默降级到 claude

> 冻结日期 2026-10-09 | rev2 | 编排者 claude-code | 执行者 kimi
> 冻结后执行期间只读。修订走 re-freeze(rev3),不原地改。
> 基线 `main` `0ba058d`。设计见同目录 `DESIGN.md`。rev1 存档见 `WP-01-brief.rev1.md`。
> rev2 由二签 REWORK(`.agentic/probe-wp01-brief-consult.answer.md`,
> `CODEX_DECISION: REWORK`,绑定 checkout `efd893a`)驱动,逐条关闭其八项必改。
> 配置权威仍是 `main_repo()`,未改全局语义,故本轮停在 REWORK 不升 CONSULT。

## 目标(一句话)

`_resolve_developer()` 在 developer 首选探针失败时,按失败原因分流到「单跳 flash 回退」
或「STOP 交人」,**绝不**推进到另一个 adapter 把 developer 静默换成 claude;
且探针原始输出只在内存里参与额度判定,不进 reasons / 异常 / 日志 / status。

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
- `.agentic/config.toml`(**rev2 新增禁写**:rev1 的 F4 已删除,见下)
- `src/agentic_loop/secret_redaction.py`(复用 `redact_env_value`,不改)
- `uv.lock`(本仓当前**未跟踪**此文件,列入即禁止新建)、
  `docs/plans/2026-09-*/**`、其他任何路径

> 若实现中发现**必须**改 `resolve_paths.py` 才能完成 F5,**立即 BLOCKED 上报**,
> 不得自行扩范围 —— 那等于改配置权威语义,须升 CONSULT。

## 输入

- `DESIGN.md` §1 缺陷、§2 非缺陷(勿"顺手修")、§3 四条取向
  (rev2 冻结前编排者已修正两处:§3 R3 的实现处数由「5 处」改为**四处定义**
  `adapters/base.py:193` / `kimi.py:168` / `claude.py:126` / `codex.py:199`
  + 唯一独立生产调用方 `bootstrap_cmd.py:88-92`,二签 Q5 认定原数为笔误;
  §3 R4 标注为**已移出本 WP**。`DESIGN.md` 不在 `allowed_paths`,执行者零改动)
- 二签 REWORK 全文:`.agentic/probe-wp01-brief-consult.answer.md`(八项必改的来源)
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
> detail,则无限递归 —— 二签 Q9 明确点出。必须写成非递归。
`claude.py` / `codex.py` 不改,继承 base 默认,bool 契约不变。

**F2 kimi 两条真实 detail 路径都要交出真实输出**
`adapters/kimi.py` 覆写 `probe_injection_detail()`,两条路径都返回**真实**输出:
- `_binding is None`(原生 kimi):不得只 `return (self.probe(), "")`。必须真跑
  原生探针命令并返回其 stdout(可复用 `probe()` 的命令构造,但要拿到输出),
  否则生产原生 kimi 永远认不出额度文本 —— 二签 Q1 第二条逃逸。
- `_binding` 非空(provider 绑定):跑注入探针,
  `ok = (proc.returncode == 0 and self._SENTINEL in out)`。
两条路径返回前都必须按 F7 脱敏。`OSError` 分支返回 `(False, "")`。

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
rev1 的 `.agentic/config.toml` 规范化(`deepseek-flash` / `kimi = "deepseek-flash"`)
与本 WP 的行为目标无关,且生产 config 不读被审 checkout 的值,属另一目的。
二签 Q7 建议移出,本 rev 采纳:`config.toml` 进 `forbidden_paths`,
`test_project_config_resolves_flash_fallback` 的两条断言**保持 checkout 现值不动**
(`identity_model == "deepseek-v4-flash"`、`cli_selector == "deepseek/v4-flash"`),
列入「必须保持绿集合」。

**F5 单一配置权威:显式穿 `repo`,一处取数**
`_resolve_developer()` 新增**必填**关键字参数 `repo: Path`(或 `*, repo`),
函数体内所有配置读取都用它,且 primary adapter 名与 binding 必须出自**同一次**
解析调用:
- 删掉 `roles_config` 作为 adapter 名来源的用法(它来自展平后的 `get_roles()`,
  与 `get_roles_raw()` 驱动的 binding 可能是两个配置视图 —— 二签 Q9 第二条);
  改为 `adapter_name, binding = resolve_role_binding("developer", repo=repo)`。
  `roles_config` 形参可保留以兼容调用方签名,但**不得**再参与 adapter 选择;
  若保留,须在 docstring 写明它已不参与选择。
- `fallback_binding = resolve_role_fallback_binding("developer", repo=repo)`
- `quota_patterns = load_quota_patterns(repo)`
`main()` 的两个调用点(`probe=True` 与 `probe=False`)都传 `repo=repo_root`
(`repo_root = main_repo()`,已在 `main()` 现有行内),权威保持 `main_repo()`。

**F6 单一首选 + 原因分流 + 回退状态贯通**
`_resolve_developer()` 按 F5 取到唯一首选后探针:
- 探针通过 → 原样返回,`fallback_applied = False`。
- 探针失败且 `is_quota_error(probe_output, quota_patterns)` 为真且
  `fallback_binding` 非空 → 用 `fallback_binding` 构造 flash adapter 返回,
  `fallback_applied = True`。
- 探针失败且命中额度但**未配** `fallback_provider` → 视同非额度失败,`raise`。
- 其余一切失败(含未知 adapter 名、候选为空)→ `raise ProbeFailedError`。
删除「推进到下一个 candidate」(`:169-171` 的 `continue`)与
「all configured ... falling back to built-in kimi」两段跨 adapter 逻辑;
原 `:159-165` 候选为空分支的 `registry["kimi"](binding)` 兜底也一并删除 ——
候选为空只能来自配置错误,语义定为**配置错误 → `raise ProbeFailedError`**,
不内建 kimi 兜底、不碰 claude(二签 Q3 要求本 WP 明确该语义并绑测试)。
**返回值扩为三元**:`(adapter, reasons, fallback_applied: bool)`。
`main()` 两个调用点与 `tests/test_redispatch_quota_fallback.py:234` 的
`_resolve_developer` monkeypatch(以及 `_StubDev` 相关装配)都须同步改为三元;
`main()` 在 `fallback_applied is True` 时,给
`_dispatch_with_quota_fallback(...)` 传 `fallback_binding=None`,
使"探针阶段已跳 flash"后不可能再 flash→flash(二签 Q1 第三条逃逸、`:538-543`)。

**F7 探针原始输出禁止外流**
原始探针输出的**唯一**用途是在内存里喂 `is_quota_error()`。
- `reasons` / `ProbeFailedError` 文案 / stdout / stderr / status 只允许写**固定类别**
  (如 `probe failed: quota` / `probe failed: other` / `unknown developer adapter`
  / `developer candidates empty`),**不得**拼接探针输出、config 原文或 env 值。
- `kimi.probe_injection_detail()` 返回前,两条路径都至少按
  `redact_env_value(out, binding.api_key_env)` 脱敏(`_binding is None` 时若无
  `api_key_env` 可取,则按现有 `_run` 的脱敏约定处理,不得裸返回)。

## 承重不变式与必须转红的变异

每条不变式绑一个具名 source mutation。**报告须逐条记录「施加变异 → 实测转红」**,
含命令与输出;变异后须先断言被变异的源文件确实与原文不同(避免空变异读成绿)。
变异一律施加在**生产源文件**上,不得改测试自己的 stub 来制造红(二签 Q4)。

- **INV-P1「探针失败不得换 adapter」**
  测试:registry 注入 `kimi`(探针恒失败,输出为**非额度**文本如 `compile error`)
  与 `claude`(探针恒成功且会被计数的 stub);断言抛 `ProbeFailedError`
  **且 claude stub 的工厂与探针均未被调用**(计数为 0)。
  变异 M-P1:在 F6 的失败分支后重新加回 `continue` 推进下一候选 → 须转红。

- **INV-P1b「未知 adapter 名不得换 adapter」**
  测试:配置首选是注册表里不存在的名字,registry 里仍放会被计数的 `claude` stub;
  断言抛 `ProbeFailedError` 且 claude 计数为 0。
  变异 M-P1b:把未知名分支的 `raise` 换回 `continue` → 须转红。
  (rev1 的 M-P1 只变异"探针失败后"的 `continue`,够不到 `:169-171`,二签 Q1 第一条。)

- **INV-P1c「候选为空 → 配置错误 STOP」**
  测试:配置给出空候选(或 roles 缺项导致无首选),断言抛 `ProbeFailedError`,
  且既不构造内建 kimi、也不调用 claude stub(两者计数均为 0)。
  变异 M-P1c:把该分支改回 `registry["kimi"](binding)` 兜底返回 → 须转红。

- **INV-P2「额度失败走单跳 flash,而非 claude」**
  测试:`kimi` 探针失败且输出含额度措辞(用 `DEFAULT_QUOTA_PATTERNS` 能命中的字面
  文本,如 `insufficient balance`);断言返回 adapter 的 binding
  `provider == "deepseekflash"`,claude stub 未被调用。
  变异 M-P2:把 `is_quota_error(...)` 调用改为恒 `False` → 须转红。

- **INV-P3「探针输出确实被消费者读到」**
  测试:仅改 kimi stub 的探针**输出**(额度文本 ↔ 非额度文本)而不改其 ok 值,
  断言两次得到不同结局(flash adapter / `ProbeFailedError`)。
  变异 M-P3:**在 `_resolve_developer()` 这个消费者处**,把送进
  `is_quota_error()` 的 `probe_output` 强制改为 `""`(即消费者不再读真实输出)
  → 须转红。
  > 不得把 M-P3 挂在 `KimiAdapter.probe_injection_detail()` 上:本测试用的是
  > 自定义 stub,变异生产 kimi 碰不到被执行路径,会变成空变异(二签 Q4)。

- **INV-P7「真实 kimi 两条 detail 路径都交出真实输出」**
  测试:用**真实** `KimiAdapter` + monkeypatch `subprocess.run`(不许真发网络),
  分别在 `binding=None` 与 `binding` 非空下调用 `probe_injection_detail()`,
  断言返回的输出字符串确实包含被 stub 的 stdout 内容(不是 `""`)。
  变异 M-P7:把 `binding is None` 分支改回 `return (self.probe(), "")`
  (丢弃输出)→ 须转红。

- **INV-P4「bool 契约零回归」**
  **承重 oracle 是 `tests/test_injection_probe.py`** —— 它有 10 条
  `probe_injection() is True` / `is False` 精确 bool 断言
  (`:50/61/70/77/93/103/112/127/137/144`)。另加一条**继承默认**的精确 bool 断言:
  对一个只继承 base、不覆写 detail 的 adapter,`binding=None` 时断言
  `probe_injection() is True`/`is False` 与底层 `probe()` 一致。
  变异 M-P4:把 `probe_injection()` 改成返回整个 tuple → `test_injection_probe.py`
  须转红。
  > `tests/test_bootstrap.py:94-109` 只断 `rc != 0`(三个 adapter 全失败,
  > kimi 返真值元组它仍绿)、`tests/test_codex_gate_capability_merge.py:368-377`
  > 调 `probe_injection()` 但从不断 `ok` —— 二者**降级为「必须保持绿集合」**,
  > 不得当作 M-P4 的红证来源(二签 Q6;memory「negative assertions need a
  > mutation self-check」)。

- **INV-P5「探针已跳 flash 后不得再 flash→flash」**
  测试:`_resolve_developer` 返回 `fallback_applied=True` 的路径进 `main()`
  (或直接测 `main()` 的装配),断言传给 `_dispatch_with_quota_fallback` 的
  `fallback_binding is None`;并补一条装配测试覆盖
  `_resolve_developer → main → _dispatch_with_quota_fallback` 全链
  (二签 Q9 第四条:当前无测试覆盖该连线)。
  变异 M-P5:让 `main()` 无条件传原 `fallback_binding`(忽略 `fallback_applied`)
  → 须转红。

- **INV-P6「探针原始输出不外流」**
  测试:让 kimi 探针 stdout 同时含 (a) 一个密钥哨兵值(通过
  `binding.api_key_env` 指向的 env 注入)、(b) 端点 URL、(c) 错误体文本;
  走完 `_resolve_developer()` 的失败分流,断言**所有可观测输出**
  (`ProbeFailedError` 文案、`reasons`、捕获的 stdout/stderr)
  均不含哨兵值、不含该端点原文、不含探针输出片段。
  变异 M-P6:把探针输出拼进 `reasons` 或异常文案 → 须转红。
  变异 M-P6b:去掉 `kimi.probe_injection_detail()` 的 `redact_env_value` 调用
  → 须转红。

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
  两条路径真实输出 + 脱敏
- `src/agentic_loop/redispatch.py`:`_resolve_developer` 显式 `repo` + 单一权威
  + 单一首选 + 原因分流 + 三元返回;`main()` 两处调用与 `fallback_binding` 贯通
- `tests/test_redispatch_quota_fallback.py`:INV-P1/P1b/P1c/P2/P3/P5/P6/P7 测试
  + 三元返回的 stub 同步
- `tests/test_injection_probe.py`:继承默认的精确 bool 断言
- 执行报告(§C 格式),含逐条变异红证 + F3 的生产/checkout 实测事实复述

## 完成定义(DoD)

- [ ] F1、F2、F3、F5、F6、F7 逐项实现(F4 已删除,`config.toml` 零改动)
- [ ] INV-P1/P1b/P1c/P2/P3/P4/P5/P6/P7 各有测试,且**各自绑定的变异实测转红**
      (报告逐条记录命令与结果;先证"变异后源文件确有不同")
- [ ] 「必须保持绿集合」全部七项全绿
- [ ] `bootstrap_cmd.py`、`adapters/claude.py`、`adapters/codex.py`、
      `resolve_paths.py`、`quota_fallback.py`、`.agentic/config.toml` diff 均为空
- [ ] 全量:`env -u AGENTIC_PYTHON GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch
      GIT_CONFIG_VALUE_0=main PYTHONPATH=src python3.11 -m pytest tests -q` 全绿,
      通过数 ≥ 本 WP base commit 实测基线。该基线由编排者在 base commit `0ba058d`
      实测为 **807 passed, 4 skipped**(2026-10-09,命令同上)。执行者须在自己的
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
   本 rev 已把 `config.toml` 整体列入 `forbidden_paths`。
4. **纯函数优先**:`probe_injection_detail` 的输出口不要夹带 `now()`;它本身必须
   跑子进程(这是它的职责),但不得写文件、不得读 config。
5. **脱敏**:见 F7 与 INV-P6 —— 这是硬性不变式,不再是原则性叮嘱。
6. **递归**:F1 的默认实现绝不能回调 `probe_injection()`。
7. **配置权威**:`main_repo()` 是权威,不得改成"当前 worktree 配置是生产权威" ——
   那是语义变更,须 CONSULT,不在本 WP 授权内。
8. **冲突预告**:`wip/kimi-managed-k3-oauth` `1aa97e3` 也改 `probe_injection()`。
   本 WP 不管它;若后续并入由那一侧和解。

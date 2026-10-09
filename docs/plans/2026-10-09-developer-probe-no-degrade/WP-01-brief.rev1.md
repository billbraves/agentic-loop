# WP-01: developer 探针失败不得静默降级到 claude

> 冻结日期 2026-10-09 | rev1 | 编排者 claude-code | 执行者 kimi
> 冻结后执行期间只读。修订走 re-freeze(rev2),不原地改。
> 基线 `main` `0ba058d`。设计见同目录 `DESIGN.md`。

## 目标(一句话)

`_resolve_developer()` 在 kimi 探针失败时,按失败原因分流到「单跳 flash 回退」或
「STOP 交人」,**绝不**推进到另一个 adapter 把 developer 静默换成 claude。

## 范围

`allowed_paths`
- `src/agentic_loop/redispatch.py`
- `src/agentic_loop/adapters/base.py`
- `src/agentic_loop/adapters/kimi.py`
- `tests/test_redispatch_quota_fallback.py`
- `tests/test_injection_probe.py`
- `.agentic/config.toml`(仅 §F4 两行)

`forbidden_paths`
- `src/agentic_loop/resolve_paths.py`(`DEFAULT_ROLES` 展平是无害设计,见 DESIGN §2)
- `src/agentic_loop/quota_fallback.py`(判定逻辑复用,不改)
- `src/agentic_loop/bootstrap_cmd.py`(R3 的加法设计正是为了让它零改动)
- `src/agentic_loop/adapters/claude.py`、`adapters/codex.py`
- `uv.lock`、`docs/plans/2026-09-*/**`、其他任何路径

## 输入

- `DESIGN.md` §1 缺陷、§2 非缺陷(勿"顺手修")、§3 四条取向
- `quota_fallback.py`:`is_quota_error(output, patterns=None)`、
  `load_quota_patterns(repo)` 已就位,**直接复用,不要新写判定**
- `resolve_role_fallback_binding("developer")` 已就位

## 功能点

**F1 探针交出输出(加法,不改签名)**
在 `adapters/base.py` 新增 `probe_injection_detail(self) -> tuple[bool, str]`,
默认实现沿用现有 `probe_injection()` 的语义(无 binding 时退回 `probe()`,
输出取空串)。`probe_injection()` 改为 `return self.probe_injection_detail()[0]`。
在 `adapters/kimi.py` 覆写 `probe_injection_detail()`,返回
`(proc.returncode == 0 and self._SENTINEL in out, out)`,其中 `out` 为
`proc.stdout or ""`;`OSError` 分支返回 `(False, "")`。
`claude.py` / `codex.py` 不改 —— 它们继承 base 的默认实现,bool 契约不变。

**F2 单一首选 + 原因分流**
`_resolve_developer()` 中:取配置首选 adapter 探针;
- 探针通过 → 原样返回。
- 探针失败且 `is_quota_error(probe_output, load_quota_patterns(repo))` 为真
  → 用 `resolve_role_fallback_binding("developer")` 构造 flash adapter 返回;
  未配 `fallback_provider` 时视同非额度失败(走下一条)。
- 其余一切失败 → `raise ProbeFailedError`,reasons 里写明失败的 adapter 与原因类别。

删除「推进到下一个 candidate」与「all configured ... falling back to built-in kimi」
两段跨 adapter 逻辑。候选表里出现未知 adapter 名时仍 `raise ProbeFailedError`
(不再 `continue`)。

**F3 不触碰主 binding 评级**
`resolve_role_binding("developer")` 的 `("kimi", None)` 返回不变。
`test_project_config_primary_developer_stays_native` 必须保持绿。

**F4 配置规范化**
`.agentic/config.toml` 两行:`identity_model = "deepseek-flash"`、
`[providers.deepseekflash.selectors] kimi = "deepseek-flash"`。
`roles.developer` 行**不动**(仍 `{ adapter = "kimi", fallback_provider = "deepseekflash" }`)。
同步 `tests/test_redispatch_quota_fallback.py::test_project_config_resolves_flash_fallback`
的 `identity_model` / `cli_selector` 两条断言。

## 承重不变式与必须转红的变异

每条不变式绑一个具名 source mutation。**报告须逐条记录「施加变异 → 实测转红」**,
不得只写"测试通过"。变异后须断言被变异的源文件确实与原文不同(避免空变异)。

- **INV-P1「探针失败不得换 adapter」**
  测试:registry 注入 `kimi`(探针恒失败,输出为**非额度**文本如 `compile error`)
  与 `claude`(探针恒成功且会被计数的 stub);断言抛 `ProbeFailedError`
  **且 claude stub 的工厂与探针均未被调用**(计数为 0)。
  变异 M-P1:在 F2 的失败分支后重新加回 `continue` 推进下一候选 → 本测试须转红。

- **INV-P2「额度失败走单跳 flash,而非 claude」**
  测试:`kimi` 探针失败且输出含额度措辞(用 `DEFAULT_QUOTA_PATTERNS` 能命中的字面
  文本,如 `insufficient balance`);断言返回的 adapter 其 binding 的
  `provider == "deepseekflash"`,且 claude stub 未被调用。
  变异 M-P2:把 `is_quota_error(...)` 的调用改为恒 `False` → 本测试须转红。

- **INV-P3「探针输出确实被读到」**
  测试:仅修改 kimi stub 的探针**输出**(额度文本 ↔ 非额度文本)而不改其
  返回的 ok 值,断言两次得到不同结局(flash adapter / `ProbeFailedError`)。
  变异 M-P3:让 `probe_injection_detail()` 的输出元返回空串(保留 ok 元)
  → 本测试须转红。
  (此条针对 memory「a test must detect its consumer's removal」:证明消费者真在读输出,
  而非"坏值恰好没被读到"。)

- **INV-P4「bool 契约零回归」**
  `tests/test_injection_probe.py`、`tests/test_bootstrap.py`、
  `tests/test_codex_gate_capability_merge.py` 中既有的 `probe_injection()`
  bool 断言全部保持绿,且 `bootstrap_cmd.py` diff 为空。
  变异 M-P4:把 `probe_injection()` 改成返回整个 tuple → 上述文件须转红。

**必须保持绿集合**(防止 INV-P1 的收紧过度杀伤合法路径):
- `test_project_config_primary_developer_stays_native`
- `test_project_config_resolves_flash_fallback`(按 F4 更新断言后)
- `_resolve_developer(..., probe=False)` 的既有行为(不探针时直接返回首选)
- 配置首选探针**通过**时的正常路径

## 交付物清单

- `src/agentic_loop/adapters/base.py`:新增 `probe_injection_detail`,
  `probe_injection` 委托
- `src/agentic_loop/adapters/kimi.py`:覆写 `probe_injection_detail`
- `src/agentic_loop/redispatch.py`:`_resolve_developer` 单一首选 + 原因分流
- `tests/test_redispatch_quota_fallback.py`:INV-P1/P2/P3 新测试 + F4 断言同步
- `.agentic/config.toml`:F4 两行
- 执行报告(§C 格式),含逐条变异红证

## 完成定义(DoD)

- [ ] F1–F4 逐项实现
- [ ] INV-P1/P2/P3/P4 各有测试,且**各自绑定的变异实测转红**(报告逐条记录命令与结果)
- [ ] 「必须保持绿集合」四项全绿
- [ ] `bootstrap_cmd.py` 与 `adapters/claude.py` / `adapters/codex.py` diff 为空
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
3. **评级不变式**:别"顺手"给 `roles.developer` 绑 `provider` —— 那会把独立性
   评级从 weak-attested 翻成 degraded-weak。DESIGN §2 已说明。
4. **纯函数优先**:`probe_injection_detail` 的输出口不要夹带 I/O 或 `now()`。
5. **脱敏**:探针输出可能含端点/错误体,流入日志前只走已有脱敏路径,
   绝不打 env 值或 config 原文。
6. **冲突预告**:`wip/kimi-managed-k3-oauth` `1aa97e3` 也改 `probe_injection()`。
   本 WP 不管它;若后续并入由那一侧和解。

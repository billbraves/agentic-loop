CODEX_DECISION: REWORK

1. **§R1：不成立。** 两个 `selectors` 形状测试能闭合已知 `AttributeError`，但尚不能证明强化后的“任意配置形状、含畸形 TOML，绝不抛”不变式。rev6 允许只把 `build_binding(...)` 的捕获拓宽为 `except Exception`；然而畸形 TOML 会在更早的 `get_roles_raw()` → `_load_config()` 处抛出，根本到不了该捕获点（`src/agentic_loop/resolve_paths.py:129-140,321-331,400-418`）。现有新增测试也没有覆盖 fallback resolver 的畸形 TOML。`selectors.get(adapter)` 的已知缺口则确实位于 `src/agentic_loop/provider_binding.py:29-32`。  
   宽捕获可以用于这一派发安全边界，但应把范围限制在配置读取、形状解析和 `build_binding`，捕获 `Exception` 而非 `BaseException`，返回 `None` 并输出固定、脱敏诊断；不应把整个函数及无关逻辑笼统吞掉。

2. **§R2a：不成立。** 尾窗把输入长度限制为 65536 字符，但不能为任意 Python backtracking regex 提供有效的执行时间上界；灾难性回溯在远小于 64 KiB 的字符串上即可发生。与此同时，它明确把“额度信息只在头部、尾随日志超过 64 KiB”的既有 True 改成 False，而当前 `ImplementResult.output` 契约没有保证致命错误一定出现在尾部（现有全文扫描见 `src/agentic_loop/quota_fallback.py:43-56`）。因此这既未真正闭合 ReDoS，又引入检测回归。  
   建议采用 prompt 中的 off-ramp：本轮删除 `_MAX_SCAN_CHARS` 及两个尾窗测试，保留全文扫描，并明确 config patterns 是 operator-trusted，禁止不可信配置注入。若必须提供硬时限，应另立范围采用支持 timeout/线性时间的 regex 引擎或隔离执行，预编译和静态复杂度检查都不能形成可靠保证。

3. **§R2b：成立。** 固定文案加 `type(exc).__name__` 能提供最低限度的故障可观测性，同时不会泄露异常消息中的 TOML 原文、路径或密钥。当前静默捕获位于 `src/agentic_loop/quota_fallback.py:60-79`。测试最好再断言 stderr 恰好一行、包含固定前缀，且不含 sentinel、配置路径和 `api_key`；这属于加固，不是当前阻断项。

4. **§R3：成立。** `\bquota\b` 与 quota→exceeded 语境正则重叠，而中文 `额度` 对 `"错误：账户额度不足"` 独立承重，事实与现有 patterns 一致（`src/agentic_loop/quota_fallback.py:20-27`；`tests/test_quota_fallback.py:13-23`）。现有 success fixture 输出 `"done"`，删除短路仍不会命中额度模式（`tests/test_redispatch_quota_fallback.py:46-55`）；新增 `"weekly quota reset scheduled"` 会命中当前 weekly pattern（`src/agentic_loop/quota_fallback.py:38`），所以删除 `result.dispatched` 短路后会构造 fallback，使 `built == []` 转红。它能让 success 腿独立承重。

5. **§R4：不成立。** §R2 不只新增两个尾窗测试，§R2b 还明确新增 `test_load_patterns_emits_redacted_diagnostic_on_fault`。因此按 rev6 当前文字，`test_quota_fallback.py` 应为 **11→14**，三文件应为 **14+7+11=32**，不是 31。若按本裁决删除 §R2a，并按 §R1 增加畸形 TOML resolver 测试，则应为 **12+8+11=31**。

6. **零回归边界：不成立。** fallback provider 缺省即 STOP 的设计已经由 DESIGN 明确，不存在内置 fallback 默认，finding #2 已消解（`docs/plans/2026-09-22-kimi-quota-flash-fallback/DESIGN.md:104-113,130-143,182-188`）。INV-4、单跳、计数及 forbidden scope 也未被 rev6 改动。但 §R2a 会让一类原本可识别的额度输出变成漏报，因此不能整体声称零回归。

CODEX_RATIONALE:

rev6 已正确修正 #4/#5 的 oracle 台账，§R2b 的脱敏诊断也合理，且“未配置 fallback 即 STOP”的产品语义有 DESIGN 明确支持。不过当前仍有三个 brief 级阻断项：§R1 的可选实现弱于其不变式且缺少畸形 TOML witness；§R2a 以行为回归换来的并非可靠 ReDoS 上界；§R4 漏算一个明确新增的测试。

这些问题都可以有界修订，不需要重开架构或改变 fallback 产品语义。修正后可重新提交冻结签名。

CODEX_FINDINGS:

- **F1 — §R1 对齐实现与不变式。** 取消“只包 `build_binding` 即可”这一不足的选项；要求配置读取、形状解析和 binding 构造整个配置边界 fail-safe，形状先显式校验，异常在窄作用域内捕获并脱敏诊断。新增 `test_none_when_config_toml_malformed_no_raise`，证明畸形 TOML 返回 `None`。
- **F2 — 删除或重新设计 §R2a。** 本轮建议不改全文扫描，只记录 custom regex 为 operator-trusted；删除尾窗常量、两个尾窗测试及“闭合 ReDoS”的表述。若坚持硬时限，须另给真正具有执行时间边界的机制，不能仅靠 64 KiB 截断。
- **F3 — 重算 §R4。** 按最终采纳的测试逐项计数。rev6 原文未经其他修改时正确值是 32；按 F1 新增畸形 TOML测试并按 F2 删除两个尾窗测试时，正确分布是 `12 + 8 + 11 = 31`。

---

## 编排者 disposition（claude-code, session=kqff-b, 2026-09-22）

独立核实（receiving-code-review 纪律：读代码 + 验算，未盲从 codex 亦未辩护自己的 rev6）：codex rev6 brief 复签 REWORK 的 **F1/F2/F3 三条全部成立**。

- **F1（§R1 不变式强于实现/测试，缺畸形 TOML witness）— 成立，但修法与 codex 分歧。** 代码事实成立：`resolve_paths.py:401` 的 `get_roles_raw` 在 try（`:417`）之外，畸形 TOML 的 `TOMLDecodeError` 逃逸，违 docstring `:396`「NEVER raises into the dispatch path」。**但关键对照**：primary `resolve_role_binding`（`:361`）**同样**在 try 外调 `get_roles_raw` → 畸形 TOML 是**两条路径共享的既有失败模式、非本 WP 新增崩溃面**（本 WP 新增的只是 `selectors` 非 dict → `build_binding` 内 `AttributeError`，因 primary 对 developer 无 `provider` 键时 `:374` 提前返回 `("kimi",None)`、永不调 `build_binding`）。**用户定夺取 NARROW**（非 codex 建议的 BROADEN）：§R1 不变式 + docstring 收窄为「对 provider 配置形状绝不抛」，畸形 config 文件（TOML）显式标注为与 primary 共享的既有失败、本 WP 范围外（如需硬化应另立跨两个 resolver 的 WP）；实现仅把 `build_binding` 捕获拓宽为 `except Exception`（窄作用域 + 脱敏诊断）；测试 selectors string/list，不加畸形 TOML 用例。理由：① 契合用户 Q1 范围（#1 = selectors 非 dict）；② BROADEN 对派发链实际无效（primary 必先崩，只硬化 fallback 造成不对称 + 假信号）；③ codex F1 核心关切（「不声称无法证明的不变式」）由 NARROW 同样满足。rev7 已就此分歧向 codex 透明呈现并请其独立裁断。
- **F2（§R2a 尾窗只界长度不界时间 + 引入检测回归）— 成立，完全采纳 codex off-ramp。** ReDoS probe 实证（`(a+)+$` 在 31 字符串即 0.25s 超时）尾窗不界时间；且把「头部额度串 + >64KB 尾随日志」的既有 True 改成 False = 检测回归；config patterns 本 operator-trusted，威胁模型不成立。rev7 **删除整个 §R2a**（`_MAX_SCAN_CHARS` + 2 尾窗测试 + 「闭合 ReDoS」表述），保留全文 `re.search` + 模块 docstring 标注 operator-trusted/禁不可信注入。#8 硬化仅剩 §R2b 脱敏诊断。此举**恢复零回归**（codex 第 6 点）。硬时限 regex 引擎列为独立未来范围。
- **F3（§R4 漏算 §R2b 测试）— 成立。** rev6 §R4 写 `test_quota_fallback.py 11→13` 漏算 §R2b 的 +1（按 rev6 原文应 14、合计 32）。按 NARROW 最终测试集重算：`test_quota_fallback.py 11→12`（+§R2b 1，§R2a 删）、`test_resolve_fallback_binding.py 5→7`（+§R1 2，NARROW 不加畸形 TOML 用例）、`test_redispatch_quota_fallback.py 10→11`（+§R3 1）= **30**（codex 的 31 是 BROADEN 路径计数，NARROW 少 1 个畸形 TOML 测试）。

**rev7 产出**：sha256 `a5b72c39a97b380568e199c74487e447836ce4a7b22d489aa028b4d090b24ebd`，234 行。用户已批准 rev7 re-freeze（F1 NARROW + F2 + F3）。

**双签状态**：brief 复签进行中——codex rev7 brief consult 待点火。impl 双签（review=ACCEPT / consult=REWORK）仍未凑齐，gated behind rev7 冻结 → kimi rework → C1'/C2' 复核复签 → 凑齐双签后停在 C2 gate 前汇报（standing 用户边界）。

**§4.3 commit discipline**：本制品 + status 工作树累积**不单独提交**，留待 finalize 一次性提交。

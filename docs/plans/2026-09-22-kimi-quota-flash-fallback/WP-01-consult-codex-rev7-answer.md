CODEX_DECISION: ACCEPT

- **F1（NARROW）：成立。** NARROW 足以闭合原 F1 的核心关切。malformed TOML 会在 primary 的 `get_roles_raw()` 先行逸出（`src/agentic_loop/resolve_paths.py:361`），而 fallback 同样在 `get_roles_raw()` 处读取配置（`:401`）；实际派发链在解析 fallback 前必经 `_resolve_developer()` 的 primary binding 解析（`src/agentic_loop/redispatch.py:480,532,538`）。因此只 BROADEN fallback 对派发链无保护作用，反而造成不对称。对本 WP 新增的 provider 配置形状面，provider/role 类型守卫已位于 `resolve_paths.py:403-414`，剩余 `selectors.get(adapter)` 等构造异常来自 `provider_binding.py:29-32`；在 `build_binding()` 调用点以窄作用域 `except Exception` 捕获，可与 selectors string/list 两个 witness 对齐。NARROW 可接受，不要求 BROADEN。

- **F2（off-ramp）：成立。** rev7 明确保留全文 `re.search` 行为并删除 `_MAX_SCAN_CHARS`、两个尾窗测试及 ReDoS 已闭合的表述。当前全文扫描位于 `src/agentic_loop/quota_fallback.py:43-57`；该处没有可靠时间上界，因此将 custom patterns 明定为 operator-trusted、真正的 regex 时间隔离另立范围，是不引入漏报回归的正确处置。

- **F3（30）：成立。** 当前基线实际计数为 `11 + 5 + 10 = 26`。rev7 增量分别为 §R2b `+1`、§R1 selectors 形状测试 `+2`、§R3 success 腿测试 `+1`，故最终为 `12 + 7 + 11 = 30`。NARROW 不包含 malformed TOML resolver 测试，因此不是 BROADEN 路径的 31。

CODEX_RATIONALE:

rev7 已把 §R1 从无法由实现和测试证明的“任意配置、NEVER raises”收窄到本 WP 实际新增的 provider 配置形状崩溃面，并同步要求收窄 docstring。这里不再存在不变式强于实现的问题。primary 必先解析配置的调用顺序也支持编排者判断：单独硬化 fallback 的 malformed TOML 路径不能改善派发链，跨两个 resolver 的统一配置解析硬化应作为独立 WP。

F2 完整采用了此前建议的 off-ramp，消除了尾窗造成的检测回归；F3 与最终 NARROW 测试集计数一致。§R2b、§R3、INV-4、单跳和范围约束未出现新的 brief 级缺口。rev7 可以 re-freeze 并交 kimi 实施 rework；实现后的 `except Exception` 作用域、脱敏诊断及承重测试仍应在 impl 双签门复核。

---

## 编排者 disposition（claude-code, session=kqff-b, 2026-09-22）

codex rev7 brief 复签 = **ACCEPT**（session `01a0cb50-facd-7ce1-863d-7b1168f704eb`，model gpt-5.6-sol，reasoning_effort=high，read-only sandbox）。逐条独立复核成立（receiving-code-review 纪律：未盲从亦未辩护，读代码 + 自跑 probe + 验算）：

- **F1（NARROW）— codex 独立采纳 NARROW，明确「不要求 BROADEN」。** codex 自行验证调用顺序：malformed TOML 在 primary `get_roles_raw()`（`resolve_paths.py:361`）先行逸出，fallback 同样在 `:401` 读配置；实际派发链在解析 fallback 前必经 `_resolve_developer()` 的 primary binding 解析（`redispatch.py:480,532,538`）→ 只 BROADEN fallback 对派发链无保护作用、反造成不对称。本 WP 新增崩溃面仅 `selectors.get(adapter)`（`provider_binding.py:29-32`），provider/role 类型守卫已在 `resolve_paths.py:403-414`；`build_binding()` 调用点窄作用域 `except Exception` 与 selectors string/list 两 witness 对齐。**编排者的 NARROW 分歧被 codex 独立复核证明正确**（rev6 我曾倾向 NARROW、codex rev6 建议 BROADEN，rev7 header 透明呈现后 codex 独立转向 NARROW）。
- **F2（off-ramp）— 成立，完全采纳。** rev7 保留全文 `re.search`（`quota_fallback.py:43-57`）、删除 `_MAX_SCAN_CHARS` + 两个尾窗测试 + 「ReDoS 已闭合」表述；operator-trusted + regex 时间隔离另立独立范围，是不引入漏报回归的正确处置。#8 硬化仅剩 §R2b 脱敏诊断。
- **F3（30）— 成立。** 基线 11+5+10=26；rev7 增量 §R2b +1、§R1 selectors +2、§R3 success 腿 +1 → **12+7+11=30**。NARROW 不含 malformed TOML 测试，故非 BROADEN 路径的 31。

**双签状态**：brief 级 re-freeze 双签凑齐（rev7 = ACCEPT）。rev7 已授权冻结为 WP-01 rework 基线（`WP-01-brief.md` sha256 `a5b72c39a97b380568e199c74487e447836ce4a7b22d489aa028b4d090b24ebd`）。**impl 双签**（review/consult on implementation）仍未凑齐（review=ACCEPT rev1 / consult=REWORK rev1，double_sign=NOT_SATISFIED），gated behind：rev7 冻结 → kimi rework → C1'/C2' 复核复签 → 凑齐 impl 双签后停在 C2 gate 前汇报（standing 用户边界）。

**§4.3 commit discipline**：本制品 + status 工作树累积不单独提交，留待 finalize 一次性提交。

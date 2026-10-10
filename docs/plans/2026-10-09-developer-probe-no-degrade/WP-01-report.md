# WP-01 执行报告

> 工作包:WP-01（developer probe 无降级探测）
> 分支:`plan/2026-10-09-developer-probe-no-degrade`
> 基线:807 passed / 4 skipped；终态:838 passed / 4 skipped / 0 failed（净 +31 实例）
> 允许改动文件:5 个（`596 insertions, 63 deletions`），本报告为唯一新增文件。

---

## 1. 变更清单

- `src/agentic_loop/adapters/base.py`（F1）:将 `Adapter.probe_injection` 改为委托
  `probe_injection_detail()[0]`，并新增非递归的默认 `probe_injection_detail()` 返回精确
  bool，使 base 契约不再自递归。
- `src/agentic_loop/adapters/kimi.py`（F2 / F7）:`KimiAdapter.probe_injection_detail()`
  的两条路径（native 无 binding / bound 有 binding）均交出真实输出串，bound 详情串对密钥脱敏，
  且探测全程零外发（不触网、不泄 resolver 内部敏感值）。
- `src/agentic_loop/redispatch.py`（F5 / F6 / D5）:`_resolve_developer` 签名改为
  `repo` / `registry` / `probe` 三个 kw-only 形参并移除 `roles_config`，单一配置权威；
  `_resolve_developer` 单一 primary + reason 派发 + 三元返回（删除 adapter switch）；
  `main()` 的 fallback 取数传入 `repo_root`。
- `tests/test_redispatch_quota_fallback.py`:新增 A/B/C/D 族 17 个测试条目 + CHAR-1
  （五 fixture 参数化），覆盖换派面、零外发、签名语义与配置权威。
- `tests/test_injection_probe.py`:新增 D1（base 继承默认精确 bool 断言），既有 10 条
  保持不动并列入「必须保持绿集合」。

---

## 2. 测试矩阵

共 **18 个测试条目 + CHAR-1**，其中 **8 个双实例参数化条目**；实例总数 26 + 5 = **31**
（净 +31）。

| 族 | 条目 | 测试函数（落点） | 实例数 |
|---|---|---|---|
| A | A1 | `test_no_adapter_switch_on_nonquota_stop` | 2（kimi / codex）|
| A | A2 | `test_no_adapter_switch_on_quota_stop` | 2（kimi / codex）|
| A | A3 | `test_unknown_adapter_builds_nothing` | 1 |
| B | B1 | `test_quota_flash_returns_same_registry_key` | 2（kimi / codex）|
| B | B2 | `test_probe_output_is_read_by_consumer` | 1 |
| B | B3 | `test_probe_stage_flash_disables_dispatch_flash` | 1 |
| B | B4 | `test_fallback_flag_false_on_pass` | 1 |
| B | B5 | `test_probe_false_returns_primary_without_probing` | 1 |
| C | C0 | `test_zero_egress_on_probe_pass` | 2（native / bound）|
| C | C1 | `test_zero_egress_on_quota_flash_return` | 2（native / bound）|
| C | C2 | `test_zero_egress_on_quota_stop` | 2（native / bound）|
| C | C3 | `test_zero_egress_on_nonquota_stop` | 2（native / bound）|
| C | C4 | `test_kimi_bound_detail_redacts_api_key` | 1 |
| D | D1 | `test_base_default_probe_injection_returns_exact_bool` | 1 |
| D | D2 | `test_probe_injection_binding_modes` | 2（native / bound）|
| D | D3 | `test_flattened_roles_cannot_select_adapter` | 1 |
| D | D4 | `test_all_config_reads_share_one_repo` | 1 |
| D | D5 | `test_main_dispatch_fallback_binding_uses_repo_root` | 1 |
| CHAR-1 | — | `test_degenerate_config_resolves_native_kimi_no_fallback` | 5（五 fixture 参数化）|

- A 族:3 条目 / 5 实例；B 族:5 条目 / 6 实例（A/B 合计 8 条目 / 11 实例）。
- C 族:5 条目 / 9 实例（C0×2 / C1×2 / C2×2 / C3×2 / C4）。
- D 族:5 条目 / 6 实例（D1 / D2×2 / D3 / D4 / D5）。
- CHAR-1:1 条目 / 5 实例。
- 净增:18 + CHAR-1 = 31 实例（808 → 838 passed，基线 807 计入 D1 增量与其余新增）。

---

## 3. 20 变异红证

| 变异名 | 承重测试 | 实际转红实例 | 恢复后回绿 |
|---|---|---|---|
| M-A1 | A1 `test_no_adapter_switch_on_nonquota_stop` | `[kimi]` + `[codex]` 两实例均转红 | 回绿 |
| M-A2 | A2 `test_no_adapter_switch_on_quota_stop` | `[kimi]` + `[codex]` 两实例均转红 | 回绿 |
| M-A3 | A3 `test_unknown_adapter_builds_nothing` | 换派面转红 | 回绿 |
| M-A3b | A3 `test_unknown_adapter_builds_nothing` | capsys 外流面转红 | 回绿 |
| M-B1 | B1 `test_quota_flash_returns_same_registry_key` | 仅 `[codex]` 转红；`[kimi]` 等价控制实例保持绿（DoD 例外规则 2）| 回绿 |
| M-B2a | B2 `test_probe_output_is_read_by_consumer` | 转红 | 回绿 |
| M-B2b | B2 `test_probe_output_is_read_by_consumer` | 转红 | 回绿 |
| M-B3 | B3 `test_probe_stage_flash_disables_dispatch_flash` | 转红 | 回绿 |
| M-B4 | B4 `test_fallback_flag_false_on_pass` | 转红 | 回绿 |
| M-B5 | B5 `test_probe_false_returns_primary_without_probing` | 转红 | 回绿 |
| M-C0 | C0 `test_zero_egress_on_probe_pass` | `[native]` + `[bound]` 两实例均转红 | 回绿 |
| M-C1 | C1 `test_zero_egress_on_quota_flash_return` | `[native]` + `[bound]` 两实例均转红 | 回绿 |
| M-C2 | C2 `test_zero_egress_on_quota_stop` | `[native]` + `[bound]` 两实例均转红 | 回绿 |
| M-C3 | C3 `test_zero_egress_on_nonquota_stop` | `[native]` + `[bound]` 两实例均转红 | 回绿 |
| M-C4 | C4 `test_kimi_bound_detail_redacts_api_key` | 转红 | 回绿 |
| M-D1 | D1 `test_base_default_probe_injection_returns_exact_bool` | 转红 | 回绿 |
| M-D2 | D2 `test_probe_injection_binding_modes` | `[native]` 实例转红（`[bound]` 由 C4 间接锁定）| 回绿 |
| M-D3 | D3 `test_flattened_roles_cannot_select_adapter` | 转红 | 回绿 |
| M-D4 | D4 `test_all_config_reads_share_one_repo` | 转红 | 回绿 |
| M-D5 | D5 `test_main_dispatch_fallback_binding_uses_repo_root` | 转红 | 回绿 |

> 每一条变异均恢复原表达式后，其承重测试回绿（逐条核验）。M-B3 曾一度 BLOCKED：冻结锚点
> `fallback_binding=None if fallback_applied else fallback_binding` 被误写成两行重赋值（引入
> 变量 `fb`），已由提交 `7b3c99e` 恢复冻结形式并重新通过。

---

## 4. 必须保持绿集合

| # | 项目 | 结果 |
|---|---|---|
| 1 | `test_project_config_primary_developer_stays_native` | 绿（被审 checkout 配置不变式，见 §5）|
| 2 | `test_project_config_resolves_flash_fallback`（断言未改）| 绿 |
| 3 | `tests/test_bootstrap.py`（整文件）| 绿 |
| 4 | `tests/test_codex_gate_capability_merge.py`（整文件）| 绿 |
| 5 | `_resolve_developer(..., probe=False)` 既有行为 | 绿（行为核验）|
| 6 | 配置 primary 探测 PASS 的正常路径 | 绿（行为核验）|
| 7 | `tests/test_injection_probe.py` 既有 10 条断言（D1 为增量，不替换）| 绿 |

聚合结果:测试文件 26 passed（`test_bootstrap.py` / `test_codex_gate_capability_merge.py` /
`test_injection_probe.py`）+ 4 项行为核验（#1 / #2 / #5 / #6）= 全绿。

---

## 5. F3 照写（不得改写）

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

---

## 6. 遗留风险

- (a) **native kimi 路径的凭据未脱敏**:native 凭据环境变量名未知（属另一 WP 范围），本 WP 未
  对 native kimi 凭据做任何脱敏；F7 仅声明「详情串为 resolver 内部敏感值」，靠 C 族锁定
  零外发。**不宣称已实现 native kimi 凭据脱敏。**
- (b) **生产「source-trusted 单跳 flash」端到端未在本 WP 验证**:测试全部使用 stub，不发
  网络，未对生产 source-trusted single-hop flash 做端到端验证。
- (c) **shell-out-to-git 测试在并发 git 操作下可能假失败**:`test_wp_template_dispatch_lint.py` /
  `test_finalize_merge_triple_sign.py` 在并发 checkout 时编排者观察到 273 个错误；串行重跑后
  838 passed / 0 failed。

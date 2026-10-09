# developer 探针不得静默降级 — 迭代设计

迭代 id：`2026-10-09-developer-probe-no-degrade`
基线：`main` `0ba058d`（kqff 单次收敛后的尖端）

## 1. 问题

`src/agentic_loop/redispatch.py` 的 `_resolve_developer()` 在候选表上循环探针：

```python
for candidate in candidates:            # DEFAULT_ROLES["developer"] == ["kimi", "claude"]
    adapter = factory(binding)
    if probe:
        if adapter.probe_injection():
            return adapter, reasons
        reasons.append(f"developer adapter '{candidate}' probe failed; falling back")
```

kimi 探针失败时,循环推进到 `claude`。后果:

1. **开发者角色被静默替换成 claude**,派发"成功"返回 0,只在 `reasons` 里留一行字符串。
2. **额度回退整条链被旁路**:`is_quota_error` 只在 `_dispatch_with_quota_fallback()`
   里对*派发输出*求值,而派发此刻已经由 claude 执行。探针阶段的额度耗尽永远到不了
   flash 回退。
3. **独立性信任根被破坏**:orchestrator 已是 claude(config.toml:50),
   developer 也变成 claude 即同源自审,而 status 里 `executor.tool` 仍记为 kimi。

缺陷 2 与 `2026-09-22-kimi-quota-flash-fallback/DESIGN.md` §6 已诚实标注的已知边界
是同一处:"若额度硬耗尽到连小探针都失败,probe gate 先 STOP,flash 永不被触达;
覆盖它可加 probe 额度感知(需 probe 返回输出,属小扩展,本设计范围外)"。
本迭代就是补那块扩展 —— 但同时发现实况比 §6 的描述更糟:probe gate **不 STOP**,
而是降级到 claude。

缺陷 1/3 违反 `AGENTS.md` §7「外部服务失败必须换成确定性 fixture,不得以无界
重试(此处为无界换人)掩盖」。

## 2. 非缺陷(已核,不改)

- `resolve_role_binding("developer") == ("kimi", None)` 是**刻意不变式**,
  由 kqff DESIGN §6 锁定、`test_project_config_primary_developer_stays_native` 守护。
  绑 provider 会把评级从 weak-attested 翻成 engine-observable `degraded-weak`。不动。
- `DEFAULT_ROLES` 的 dict→list 展平(`resolve_paths.py:362`)无害:展平后 `kimi` 仍
  排第一,且回退路径独立读 `get_roles_raw()`。此前我曾称其为"整条链真正的断点",
  这个判断是错的,此处记录以免复犯。

## 3. 修复取向

**R1 探针失败不得跨 adapter 推进。** `_resolve_developer` 对 developer 角色
只认配置首选项;探针失败后不试第二个 adapter。

**R2 探针失败按原因分流。**
- 命中 `is_quota_error` → 走既有单跳 flash 回退(`resolve_role_fallback_binding`)。
- 未命中 → `raise ProbeFailedError`,由 `main()` 打 `REDISPATCH_STOP` 交人。

**R3 探针须交出输出,但不得改既有契约。** `probe_injection() -> bool` 有 5 处实现
(`base`/`kimi`/`claude`/`codex` + base 抽象)与一个独立调用方
`bootstrap_cmd._probe_one`(:92)。因此**加法而非改签名**:新增
`probe_injection_detail() -> tuple[bool, str]`,`probe_injection()` 委托给它
取第一元。`bootstrap_cmd` 零改动,4 个现有测试文件的 bool 断言全部继续成立。

**R4 配置规范化。** `identity_model` 由未列出的别名 `deepseek-v4-flash` 改为
`GET /v1/models` 列出的规范 id `deepseek-flash`,selector 同步。两者皆可服务
(已实测 200 + sentinel),故这是规范化而非 bug 修复;`roles.developer` 的
`fallback_provider` 形态不变。

## 4. 范围外

- 第二层 reviewer/consultant 回退(kqff DESIGN §11 已列出;codex OpenAI 协议
  问题 + 独立性评级下调两项风险未解)。
- `wip/kimi-managed-k3-oauth` `1aa97e3` 的并入。该分支也改 `probe_injection()`
  (managed 通道新增一条裸 bool 返回路径),与 R3 接触面重叠;**后落者负责和解**。
- `uv.lock`(历史裁决的禁区,见 `2026-09-13-parallel-throughput/CONVERGENCE-PLAN.md:125`)。

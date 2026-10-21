# WP-01: merge-gate consult 单跳提供商回退（kirogpt gpt-5.6-sol → deepseek-v4-pro）

> 冻结日期 2026-10-21 | 编排者 qoder | 执行者 kimi（Kimi for Coding 主档）。
> 所属 Plan：PLAN-01（集成到 `plan/2026-10-21-consult-llm-failover`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze。

## Re-freeze 规则（编排者冻结前自检）

- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。
- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。

## 目标（一句话）

让 `agentic gate` 的独立 consult 在**基础设施故障**（quota / transport / server）时，
从主档 kirogpt/`gpt-5.6-sol` 自动**单跳**回退到 deepseekpro/`deepseek-v4-pro`，
并如实记录实际服务方；auth/config 与任务失败绝不回退。

## 背景与现状

- consult 由 `src/agentic_loop/gate/__init__.py` 执行：
  `resolve_role_binding("consultant")` → `CodexAdapter(binding=..., direct_finalization=True)`
  → `adapter.review(diff=..., brief=..., contract=..., effort=...)`。
- `.agentic/config.toml` 当前为 `consultant = { adapter = "codex", provider = "kirogpt" }`；
  `kirogpt` = LiteLLM `127.0.0.1:18090/v1` → kiro，`identity_model = "gpt-5.6-sol"`。
- 2026-10-21 实测（编排者，在 `/tmp` 独立执行）：codex 0.159.3 以 inline provider
  直连 `https://api.deepseek.com/v1`、`wire_api=responses`、模型 `deepseek-v4-pro`
  返回 `OK`；`wire_api="chat"` 已被 codex 0.159 移除（启动即报错），不得使用。
- developer 派发已有单跳 failover：`dispatch.run_dispatch` +
  `quota_fallback.classify_failure`，仅 `quota/transport/server` 回退，
  `auth_config/task` 原样报错。consult 侧目前没有回退，codex ChatGPT 额度耗尽时
  只能由编排者人工换 GLM-5.3。
- 用户 2026-10-21 明确要求：consult 也自动换提供商，优先 kiro 的 `gpt-5.6-sol`，
  fallback `deepseek-v4-pro`。

## 不变式（验收标的）

1. **配置可解析**：`.agentic/config.toml` 新增 `[providers.deepseekpro]`
   （`openai_base_url = "https://api.deepseek.com/v1"`、`api_key_env = "DEEPSEEK_API_KEY"`、
   `identity_model = "deepseek-v4-pro"`、`selectors.codex = "deepseek-v4-pro"`），
   并把 `roles.consultant` 改为
   `{ adapter = "codex", provider = "kirogpt", fallback_provider = "deepseekpro" }`。
   `resolve_role_binding("consultant")` 仍返回 kirogpt binding（主档零变化）；
   `resolve_role_fallback_binding("consultant")` 返回 deepseekpro binding。
2. **基础设施故障回退**：当 `adapter.review(...)` 抛错且
   `classify_failure(str(exc), None)` ∈ `{quota, transport, server}`、fallback binding
   存在且其 `api_key_env` 在环境中有值（只判断存在，不回显值）时，恰好发起一次
   fallback 尝试（`CodexAdapter(binding=fallback_binding, direct_finalization=True)`）。
   fallback 成功时 gate 正常输出 `GATE_DECISION` 并写 consult block。
3. **单跳**：fallback 再失败时 gate 失败，错误信息同时给出主档与 fallback 的类别，
   **不得**发起第三次尝试。
4. **不回退**：`auth_config` 或 `task` 类别失败时只调用一次主档即 `GATE_FAIL`，
   错误信息保留原类别；未配置 `fallback_provider` 时同样 fail-closed 并说明
   “no consultant fallback_provider configured”；fallback 凭据缺失时 fail-closed
   并只报环境变量名。
5. **实际身份**：independence 评级必须使用**实际服务该次 consult 的 adapter** 的
   `identity()`；fallback 生效时即以 `deepseek-v4-pro` 参与评级（若评级不达标，
   仍按现有 gate 规则 fail-closed）。
6. **审计落盘**：consult block 新增 `provider`、`model`、`fallback_used` 三个字段
   （主档成功时为 `kirogpt` / `gpt-5.6-sol` / `false`），`reviewed_by` 保持
   `codex-cli`；fallback 生效时 `notes` 与 gate stderr 记录主档失败类别和实际
   服务方；answer artifact 同样记录实际 provider/model/fallback_used。
   **不得**把原始 stderr 全文写入 status（避免凭据/账号信息）。
7. **分类器加固且零回归**：`classify_failure` 能识别直接调用路径的显式
   `HTTP 429` 与 `transport failure`（以及 “requires ..._API_KEY in env” 归为
   auth_config）；既有 QUOTA/TRANSPORT/SERVER/AUTH/TASK 样本结论全部不变。
8. **范围不变**：只改 allowed_paths；不改变 developer dispatch/redispatch、
   adapter 注入形状、wrapper、plan 命令、CLI 子命令。
9. **全量回归**：`python3.11 -m pytest tests -q` 全绿；冻结基线为
   **1112 passed, 4 skipped**（在冻结提交上复跑）。
10. **负向断言的 oracle**：新增测试必须提供正向可达性对照、原因特异 witness、
    至少两个代表性禁止变异转红，且变异施加于真实输入面（stub codex 的实际
    argv/调用次数、status JSON 字节），不能只改内存表示。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/gate/__init__.py`
  - `src/agentic_loop/quota_fallback.py`
  - `.agentic/config.toml`
  - `tests/test_gate_consult_failover.py`
  - `tests/test_quota_failure_classifier.py`
  - `docs/plans/2026-10-21-consult-llm-failover/`
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/dispatch.py`
  - `src/agentic_loop/redispatch.py`
  - `src/agentic_loop/cli.py`
  - `src/agentic_loop/plan_cmd.py`
  - `src/agentic_loop/resolve_paths.py`
  - `src/agentic_loop/provider_binding.py`
  - `src/agentic_loop/adapters/`
  - `src/agentic_loop/wrappers/`
  - `src/agentic_loop/templates/`
  - `AGENTS.md`, `CLAUDE.md`, `docs/agentic/`
  - `.env`, `.context/`, `uv.lock`
- **owner 边界**：只写上述 allowed_paths，不跨 owner 写入。

## 实现提示（非强制结构，行为以不变式为准）

- 在 `gate/__init__.py` 内抽一个可单测的 helper，例如
  `_consult_with_failover(primary_adapter, primary_binding, fallback_binding,
  fallback_factory, review_kwargs, quota_patterns)`，返回
  `(verdict, effective_adapter, provider, model, fallback_used, primary_failure)`。
  `fallback_factory` 默认 `lambda b: CodexAdapter(binding=b, direct_finalization=True)`，
  测试可注入 fake。
- 失败分类用 `quota_fallback.classify_failure(str(exc), None, quota_patterns=...)`；
  项目配额规则用 `load_quota_patterns(repo_root)`（与 dispatch 一致）。
- independence 的 `consultant_identity` 必须来自 effective adapter；当前代码在
  review 之前计算，需要把该段评估移到 review 成功之后（其余
  `is_bootstrap_normal` / attestation 逻辑不变）。
- 把原 `except Exception as exc: raise GateError(f"codex review failed: {exc}")`
  替换为带回退与类别信息的 fail-closed 错误；不要吞掉主档原因。
- `persist_answer` / `write_consult_block` 增加关键字参数以记录实际服务方；
  不要改变 `reviewed_by` 的既有取值。
- 新增测试建议复用 `tests/test_gate_diff_start.py` 的临时 git repo + stub codex
  模式（可复制最小 harness 到新文件），stub 通过 `-c model_provider=<name>` 判断
  主档/回退并按需返回 success / 429 / 401 / 503；测试注入 `DEEPSEEK_API_KEY`
  占位值，断言 stub 实际调用次数与收到的 `-c model_providers.<name>...` argv。

## 输入

- `src/agentic_loop/gate/__init__.py`（consult 调用面与 consult block 写入）。
- `src/agentic_loop/quota_fallback.py`（`classify_failure` / `FALLBACK_CATEGORIES` /
  `load_quota_patterns`）。
- `src/agentic_loop/dispatch.py` 的单跳回退语义（只读参考，不得修改）。
- `tests/test_gate_diff_start.py` 的 gate 端到端 harness（只读参考，不得修改）。
- `.agentic/config.toml` 现有 provider/role 形状。

## 交付物清单

- [ ] `.agentic/config.toml`：`deepseekpro` provider + consultant `fallback_provider`。
- [ ] `src/agentic_loop/gate/__init__.py`：consult 单跳 failover、effective identity、
      审计字段与 answer artifact 记录。
- [ ] `src/agentic_loop/quota_fallback.py`：HTTP 429 / transport failure /
      缺失 API key 的显式分类（不改变既有样本结论）。
- [ ] `tests/test_gate_consult_failover.py`：主档成功、quota 回退成功、auth/task 不回退、
      fallback 再失败单跳、缺凭据、未配置 fallback 的端到端测试。
- [ ] `tests/test_quota_failure_classifier.py`：新增样本的正/负向用例。
- [ ] 测试证据：目标测试 + 全量测试 + 至少两个禁止变异转红记录。

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] `agentic quality-gate <status.json>` 全绿
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无通知、无推送；测试不访问真实 provider/网关
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

> 单测全部使用 stub codex / fake adapter，不访问网络、不调用真实 provider。

## 附注

- 回退判断必须发生在**异常分类之后**；不要把任何异常都当成可回退。
- 不要为了回退而重试主档；主档只尝试一次。
- fallback 也必须走 `direct_finalization=True`，与主档同一评审契约。
- `classify_failure` 的任务证据优先规则不得放宽：pytest/AssertionError 文案即使
  引用 429/503 仍是 `task`。
- 分类器新增正则要避免命中端口号/测试名：HTTP 状态码需带 `http`/`status` 语境。
- 不要修改 `resolve_role_fallback_binding` 的通用语义（它已被 developer 使用）。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Acceptance tests

1. Config resolution: the project config resolves the consultant primary to the
   `kirogpt` binding (`gpt-5.6-sol`) and the consultant fallback to the
   `deepseekpro` binding (`deepseek-v4-pro`), with the primary unchanged.
2. Failover trigger: when `CodexAdapter.review` raises a failure classified as
   `quota`, `transport`, or `server`, and a fallback binding plus its credential
   env var exist, the gate makes exactly one fallback review attempt with
   `CodexAdapter(binding=fallback_binding, direct_finalization=True)`; a
   successful fallback yields the normal `GATE_DECISION` and consult block.
3. Single hop: a failing fallback makes the gate fail with both the primary and
   fallback categories reported; no third attempt is made.
4. No failover: `auth_config` and `task` failures, a missing
   `fallback_provider`, and a missing fallback credential all fail closed after
   exactly one primary attempt, with the environment variable NAME (never its
   value) in the error.
5. Effective identity: independence evaluation uses the identity of the adapter
   that actually served the consult; `consult.provider`, `consult.model`, and
   `consult.fallback_used` record it, and `reviewed_by` stays `codex-cli`.
6. Audit: fallback notes/stderr name the primary failure category and the
   effective provider/model; raw stderr is never written into status; the answer
   artifact records provider/model/fallback_used.
7. Classifier: explicit `HTTP 429`, `transport failure`, and
   “requires ..._API_KEY in env” classify as quota/transport/auth_config
   respectively, while every existing sample’s category is unchanged.
8. Scope: only the allowed paths change.
9. Full suite: `python3.11 -m pytest tests -q` is green at the WP commit.
10. Negative oracles: each new negative assertion has (a) a positive
    reachability control, (b) a cause-specific witness, (c) at least two
    representative forbidden mutations that turn red, and (d) the mutation
    applied to the real surface (stub codex argv/call count, status JSON bytes).

## Allowed and forbidden paths

Only the `allowed_paths` whitelist may change; the `forbidden_paths` blacklist
must never be touched. Owner boundaries follow CODEOWNERS.

## Completion definition

All deliverables complete; acceptance tests green; no forbidden-path or
cross-owner writes; no production writes, real notifications, or pushes; commit
message conforms to repository conventions.

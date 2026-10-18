# 迭代 2026-10-18-provider-binding-validation

> Plan：PLAN-01 | 集成分支 `plan/2026-10-18-provider-binding-validation` | 目标 `main`
> 冻结日期 2026-10-18 | 编排者 claude-code

## 这个迭代解决什么

kimi 适配器现在靠 `getattr(b, "openai_base_url", None) or b.anthropic_base_url`
取注入用的 base URL。当配置只声明 `anthropic_base_url`（本仓
`providers.deepseekflash` 正是如此）时，它会**静默**把 `/anthropic` 端点写进一个
`type = "openai_legacy"` 的 provider 块——产出一个语法合法、语义错误的配置，
故障要到派工时才以 `LLM not set` 之类看不出真因的方式暴露。

缺口是「校验的字段」与「适配器实际使用的字段」不一致。修法是把校验挪到
binding 构造期对**真正会用到的字段**做 fail-closed，并让适配器不再回退。

## 为什么需要 WP-01

`origin/main` 在本机有 4 个既有失败（`test_finalize_merge_triple_sign.py`），
根因是宿主 `init.defaultBranch=master` 而测试硬编码 `main`。基线不绿时，
后续 WP 的「全绿」无法区分真回归与既有失败，所以先用一个最小 WP 把它转绿。

## 基线依赖（重要）

本迭代的集成分支切自 `fix/tool-fixes-2026-10-14`（= `origin/main` + 两个已验证
提交），因为 `openai_base_url` 缺口**只在该 kimi 修复之上才存在**——main 上
kimi 仍走 anthropic 端点，校验是自洽的。

| 依赖分支 | 状态 |
|---|---|
| `fix/tool-fixes-2026-10-14` | 本地已验证（1082 passed 等价于其基线），推送因网络未完成 |

该分支落地到 `main` 后，本迭代分支需 rebase 到 `main` 再收敛。

## Work packages

| WP | 主题 | 状态 |
|---|---|---|
| WP-01 | 固定 triple-sign 测试初始分支，基线转绿 | DRAFT |
| WP-02 | kimi base_url 校验 fail-closed，禁止静默回退 | DRAFT |

## 明确不在本迭代范围

- `agentic quality-gate` 的分支配置预览（`--config-from <ref>` / `--explain`）：
  配置来源的架构问题，另开迭代。
- `agentic gate` 硬编码 `{wp_id}-brief.md`（`gate/__init__.py:979`）：re-freeze
  支持的一部分，另开迭代。
- 旧 plan 分支 `plan/2026-09-22-framework-hardening` 的收尾：已决定弃用归档。

## 收敛方式

全部 WP 到 `MERGED` 后，`agentic plan merge` 单次 `--no-ff` 合入 `main`，
一次推送。不做 N 个独立合并。

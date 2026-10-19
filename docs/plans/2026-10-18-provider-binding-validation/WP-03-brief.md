# WP-03: 表格式 developer 角色必须渲染成 adapter 名，而非 Python repr

> 冻结日期 2026-10-18 | 编排者 claude-code | 执行者 claude-code（代理开发，见 status）。
> 所属 Plan：PLAN-01（集成到 `plan/2026-10-18-provider-binding-validation`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze。

## 目标（一句话）

修好 `build_values` 对表格式角色绑定的处理，使 `$developer_dispatch_hint`
渲染出裸工具名（`kimi`），让 `agentic contract check` 转 IN_SYNC。

> re-freeze r3（codex r2 指出的口径残留）：原文此处写「然后重渲三份契约」。
> 实测修好渲染器后 expected checksum 自己回到文件里已有的 `307a6503bae68e97`，
> `contract diff` 三份全部 unchanged——契约**无需重渲**，重渲反而会把 repr
> 和错误 checksum 烙进去。三份契约已在 re-freeze r1 移入 forbidden_paths。

## 不变式（验收标的）

**契约正文里不得出现任何结构化值的 Python 字面量**；任何合法角色绑定形态
（字符串 / 数组 / 表）都只能渲染成工具名。

现状：`origin/main` 的 `.agentic/config.toml` 把 developer 写成
`developer = { adapter = "kimi", fallback_provider = "deepseekflash" }`。
`build_values` 用 `[developer]` 列表包裹后取 `[0]`，dict 不是 list，于是整个
dict 被 `str()` 成 repr 写进 `$developer_dispatch_hint`，即 AGENTS.md 与
CLAUDE.md 的正文：

    dispatch the developer role (configured tool: {'adapter': 'kimi',
    'fallback_provider': 'deepseekflash'}) into an isolated worktree; ...

这正是 `agentic contract check` 报 CONFIG_DRIFT 的**内容**原因；只把 checksum
改成新值会把这个 repr 永久烙进治理契约。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/contract_render.py`
  - `tests/test_contract_render.py`

  （re-freeze r1：原计划还要重渲 `AGENTS.md`、`CLAUDE.md`、
  `docs/agentic/OPERATING_MODEL.md`。实测修好渲染器后 `contract check`
  直接 IN_SYNC——expected checksum 由 `c2ab3c3bb360dadc` 回到
  `307a6503bae68e97`，正是文件里已有的 stamp。即三份契约本来就是按裸工具名
  渲染的正确产物，漂移纯属渲染器回归所致，故不需要改这三份文件。）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `.agentic/config.toml`（本次不靠改配置绕过）
  - `src/agentic_loop/gate/**`
  - `src/agentic_loop/wrappers/**`
  - `src/agentic_loop/provider_binding.py`
- **owner 边界**：渲染器 + 治理契约，不跨 owner。

## 输入

- 依赖的上游 WP 产出：WP-01（基线绿）、WP-02（已收敛的 provider 校验）
- 参考文档：旧分支提交 `d9822c9` 的归因与做法（D-16）。该分支已弃用
  （tag `archive/plan-2026-09-22-framework-hardening`），此处仅作归因参考；
  实现按当前代码重写并自测，不整体回迁。

## 交付物清单

- [ ] `src/agentic_loop/contract_render.py` — 表格式角色取 adapter 名
- [ ] `tests/test_contract_render.py` — 覆盖三种绑定形态 + 渲染级断言
- [ ] `agentic contract check` 三份全部 IN_SYNC（re-freeze r1：无需重渲，
      契约文件保持原样即达成）

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] `agentic contract check` IN_SYNC（exit 0）
- [ ] 重渲后的契约正文不含 `{'adapter'` / `'provider':` / `'fallback_provider':`
- [ ] `python3.11 -m pytest tests -q` 无新增失败
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

- 已知陷阱 1（re-freeze r3 修正）：`agentic contract diff` 在渲染器修好
  **之前**会把 repr 写进文件，所以绝不能先 apply。原文接着写「顺序必须是先修
  渲染器、再 diff --apply」——codex r2 指出这与 r1 缩窄后的范围冲突：正确做法
  是先修渲染器、再 `contract diff` **只读确认** unchanged，**不执行 apply**，
  因为那时已无差异可应用。契约文件属 forbidden_paths。
- 已知陷阱 2（re-freeze r1 已实证）：**不要先重渲再修渲染器**。修好渲染器后
  `contract diff` 会报三份全部 unchanged——因为文件本来就是对的内容；
  若先 apply 则会把 repr 与错误 checksum 烙进去。本 WP 因此最终未改动任何契约文件。
- 口径权威源引用：`src/agentic_loop/contract_render.py:145-148`（现有
  `primary_developer` 计算）、`src/agentic_loop/contract_cmd.py:85`（checksum 基准）。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」同义，非另一份口径。

1. 三种绑定形态（字符串 / 数组 / 表）分别渲染出裸工具名；空值落到默认。
2. 渲染级断言：表格式 developer 渲染出的 AGENTS.md / CLAUDE.md /
   OPERATING_MODEL.md 正文不含 `{'adapter'`、`'provider':`、
   `'fallback_provider':`。
3. 正向对照：`values["developer"]` 仍为 `kimi (provider: deepseekflash)`，
   防止「把 provider 信息一并抹掉」的假修复。
4. `agentic contract check` exit 0 且三份 IN_SYNC。

负面断言须提供四项证据：正向可达性对照、原因特异 witness、代表性禁止变异
转红（还原 `[developer]` 列表包裹写法）、变异施加于真实输入面（config 字典 /
渲染出的文件字节）。

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径（re-freeze r1 后）：
只能改 `src/agentic_loop/contract_render.py`、`tests/test_contract_render.py`；
绝不能碰 `.agentic/config.toml`、`AGENTS.md`、`CLAUDE.md`、
`docs/agentic/OPERATING_MODEL.md`、`src/agentic_loop/gate/**`、
`src/agentic_loop/wrappers/**`、`src/agentic_loop/provider_binding.py`。
三份契约由禁止改为不得触碰，因为修好渲染器后它们本就无需改动。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径：交付物就绪、
`agentic contract check` IN_SYNC、契约正文无 Python 字面量、全套无新增失败、
无 forbidden_paths 写入、无生产写入/网络/通知/推送。

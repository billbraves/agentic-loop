# WP-29 阶段 1：模板受保护块的「活动渲染」判据 —— 范围界定与可行性裁定（rev4 修订版）

> 冻结日期 2026-09-19 | 执行者 kimi（provider: deepseek）| 本文件是阶段 1 唯一交付物。
> 判定对象：`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
> `docs/agentic/templates/WORK_PACKAGE.md`（下称「两份模板」或「模板」）。
> 阶段 2 不冻结，须在阶段 1 裁定获批准后另行冻结。
> 本文件是 rev1（commit `bd4ac7a`）的**原地修订**：rev3（commit `e493c2a`）重做 §1 / §4 / §5 /
> §0（§2 / §3 已 ACCEPT 保留）；rev4（本轮，在 `e493c2a` 之上）补全 §1 消费面证据——三条主 grep
> 显式排除本交付物与 codex 二签记录、补齐 `load_template` / `_resources_files` 调用点原文、
> 宽口径差集补到完整 17 行、移除全部 U+2026 省略符，保证每个粘贴块可字面重跑。

## 0. 裁定摘要（TL;DR）

**推荐 (c′)：不引 parser、不整份冻结，把承诺边界写进判据说明，并对两个受保护节做逐字节
冻结（envelope 冻结）+ 两份副本逐字节一致；`active_embedding` 明确不承诺，交 `git diff` +
human review。**

一句话理由：本仓**没有** Markdown parser、**没有**权威方言声明（§2）；模板的唯一**非测试运行时**
消费者是 `src/agentic_loop/init_cmd.py:109`，其行为是**逐字节复制**，打包读取路径
`contract_render.load_template → importlib.resources` 只做 `read_text(encoding="utf-8")`，
**不解析 Markdown**（§1 D 类）。因此「活动渲染」这件事在当前消费链下**并未发生**。

四条实测逃逸（E1–E4）**全部不改变受保护节字节**，而是改变块外上下文使受保护节不再「活动」——
这类「active_embedding」攻击在没有权威 parser 的前提下**无法机械拦下**；四条必须保持 GREEN 的
无害编辑（G1–G4）**都不落在受保护节字节跨度内**。方案 (b)（整份逐字节冻结）对 E1–E4 灵敏度 1，
但对 G1–G4 特异性 0（把合法编辑也判红）；方案 (a)（引 parser）除依赖与方言钉版成本外，对 E4
（远距离去规范化句）也无效。故裁定 (c′)：只冻结能机械化、且不会误伤 G1–G4 的那一部分字节
（受保护节 envelope），把「渲染端一定显示为活动文本」这一开放世界语义命题**明确降级为不承诺**。

## 1. 消费链实况

**问题**：两份模板除 `init_cmd.py:109` 外还被谁读取？人算不算消费者？agent 算不算？打包读取
路径是否解析 Markdown？

**证据**（仓库级搜索；三条主 grep 均显式 `--exclude-dir` 排除 `.git` / `__pycache__` /
`.pytest_cache`，并 `--exclude` 排除本交付物自身与 codex 二签记录，理由见下）：

```text
$ grep -rn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
      --exclude=WP-29-scope-decision.md --exclude=WP-28-consult-codex-shape-verdict.json \
      'WORK_PACKAGE\.md\.tmpl' .
./tests/test_wp_template_dispatch_lint.py:23:TEMPLATE_PACKAGED = SRC / "agentic_loop" / "templates" / "WORK_PACKAGE.md.tmpl"
./docs/plans/2026-09-13-parallel-throughput/WP-29.status.json:113:      "WORK_PACKAGE.md.tmpl 仓内唯一消费者 init_cmd.py:109 逐字节复制，不解析 markdown"
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev2.md:46:  - `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev2.md:79:- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` and
./docs/plans/2026-09-13-parallel-throughput/WP-28-plan-review-before-rev3.md:145:3. `WORK_PACKAGE.md.tmpl` 在仓内的**唯一**消费者是 `init_cmd.py:109`
./docs/plans/2026-09-13-parallel-throughput/WP-28-plan-review-before-rev3.md:164:> `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 逐字节相同。
./docs/plans/2026-09-13-parallel-throughput/WP-28-consult-codex-request.md:9:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`，两份须逐字节相同）加入两段冻结文字：
./docs/plans/2026-09-13-parallel-throughput/WP-25.status.json:78:      "src/agentic_loop/templates/WORK_PACKAGE.md.tmpl",
./docs/plans/2026-09-13-parallel-throughput/WP-28-consult-codex-shape.md:113:> **INV-N3（副本同一）**：`docs/agentic/templates/WORK_PACKAGE.md` 与 `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 必须逐字节相同。
./docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md:2105:| `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` | 打包母本（`init_cmd.py:109` 铺开来源） | `FAIL missing 'Acceptance tests'` |
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:30:- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:37:  理由：`WORK_PACKAGE.md.tmpl` 是 `init_cmd._REFERENCE_TEMPLATES` 里的 reference skeleton，
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:40:  编排者已实测：`grep -c '\$' WORK_PACKAGE.md.tmpl` = 0。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:70:- [ ] `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 新增 `## Re-freeze 规则（编排者冻结前自检）`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:142:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
./docs/plans/2026-09-13-parallel-throughput/WP-29-brief.md:27:3. `WORK_PACKAGE.md.tmpl` 在仓内的**唯一**消费者是 `src/agentic_loop/init_cmd.py:109`
./docs/plans/2026-09-13-parallel-throughput/WP-24.report.md:18:src/agentic_loop/templates/WORK_PACKAGE.md.tmpl | 33 +++
./docs/plans/2026-09-13-parallel-throughput/WP-24.status.json:37:      "src/agentic_loop/templates/WORK_PACKAGE.md.tmpl",
./docs/plans/2026-09-13-parallel-throughput/WP-24.status.json:105:      "src/agentic_loop/templates/WORK_PACKAGE.md.tmpl (+33: 同上，与 docs 份 byte-identical)",
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:24:> `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 逐字节相同。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:55:- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:62:  `WORK_PACKAGE.md.tmpl` 是 `init_cmd._REFERENCE_TEMPLATES` 里的 reference skeleton，
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:94:- [ ] `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 模板正文**不改**（rev1 已落两块明文）
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:211:- 全仓无 Markdown parser 依赖、无权威方言声明；`WORK_PACKAGE.md.tmpl` 在仓内唯一消费者是
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:217:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:32:- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:39:  理由：`WORK_PACKAGE.md.tmpl` 是 `init_cmd._REFERENCE_TEMPLATES` 里的 reference skeleton，
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:42:  编排者已实测：`grep -c '\$' WORK_PACKAGE.md.tmpl` = 0。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:72:- [ ] `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` —— 新增 `## Re-freeze 规则（编排者冻结前自检）`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:190:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
./docs/plans/2026-09-13-parallel-throughput/WP-28.status.json:68:      "src/agentic_loop/templates/WORK_PACKAGE.md.tmpl",
./docs/plans/2026-09-13-parallel-throughput/WP-28.status.json:117:      "contract_version_decision": "CONTRACT_TEMPLATE_VERSION 保持 \"6\" 不 bump：WORK_PACKAGE.md.tmpl 是 init_cmd._REFERENCE_TEMPLATES 的 reference skeleton，grep -c '$' = 0 个占位符，不在 contract_render 渲染目标（AGENTS/CLAUDE/OPERATING_MODEL 三份）内",
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev1.md:26:| `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` | 打包母本（`init_cmd.py:109` 铺开来源） | `FAIL missing 'Acceptance tests'` |
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev1.md:45:  - `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`（打包母本）
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev1.md:157:- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` — packaged master template
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief.md:46:  - `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief.md:79:- `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` and
./src/agentic_loop/init_cmd.py:109:    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
```

```text
$ grep -rn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
      --exclude=WP-29-scope-decision.md --exclude=WP-28-consult-codex-shape-verdict.json \
      'docs/agentic/templates/WORK_PACKAGE\.md' .
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev2.md:47:    `docs/agentic/templates/WORK_PACKAGE.md` —— rev1 已定稿，本轮**零行 diff**
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev2.md:80:  `docs/agentic/templates/WORK_PACKAGE.md` — settled in rev1; zero-line diff
./docs/plans/2026-09-13-parallel-throughput/WP-28-plan-review-before-rev3.md:163:> **INV-N3（副本同一）**：`docs/agentic/templates/WORK_PACKAGE.md` 与
./docs/plans/2026-09-13-parallel-throughput/WP-28-consult-codex-request.md:8:往 WP brief 模板（`docs/agentic/templates/WORK_PACKAGE.md` 与
./docs/plans/2026-09-13-parallel-throughput/WP-25-brief-rev4.md:244:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-27-brief-rev2.md:204:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28-consult-codex-shape.md:113:> **INV-N3（副本同一）**：`docs/agentic/templates/WORK_PACKAGE.md` 与 `src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 必须逐字节相同。
./docs/plans/2026-09-13-parallel-throughput/WP-26-brief.md:163:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-27-brief.md:166:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md:2106:| `docs/agentic/templates/WORK_PACKAGE.md` | 项目内被引用的骨架 | `FAIL missing 'Acceptance tests'`（与母本 `diff` 为空） |
./docs/plans/2026-09-13-parallel-throughput/WP-25-plan-review-before-rev4.md:89:   `docs/agentic/templates/WORK_PACKAGE.md` 的 oracle 三项旁边，作为第四项要求。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:5:> 冻结与 re-freeze 的规则见本仓 `docs/agentic/templates/WORK_PACKAGE.md`「Re-freeze 规则」一节。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:31:- `docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:50:- `tests/test_init_contract.py` —— 它引用 `docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:72:- [ ] `docs/agentic/templates/WORK_PACKAGE.md` —— 与上一份**逐字节同一**
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:142:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:210:- oracle 三项（本 WP 新增第 4 项的落点）：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-24.report.md:17:docs/agentic/templates/WORK_PACKAGE.md          | 33 +++
./docs/plans/2026-09-13-parallel-throughput/WP-24.status.json:36:      "docs/agentic/templates/WORK_PACKAGE.md",
./docs/plans/2026-09-13-parallel-throughput/WP-24.status.json:104:      "docs/agentic/templates/WORK_PACKAGE.md (+33: 三个英文锚点段，标注与中文段同义)",
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:5:> 冻结与 re-freeze 的规则见本仓 `docs/agentic/templates/WORK_PACKAGE.md`「Re-freeze 规则」一节。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:23:> **INV-N3（副本同一）**：`docs/agentic/templates/WORK_PACKAGE.md` 与
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:56:- `docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:95:- [ ] `docs/agentic/templates/WORK_PACKAGE.md` —— 同上，与上一份逐字节同一
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:217:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:291:- oracle 三项 + 第 4 项：`docs/agentic/templates/WORK_PACKAGE.md` `## Acceptance tests` 段
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:5:> 冻结与 re-freeze 的规则见本仓 `docs/agentic/templates/WORK_PACKAGE.md`「Re-freeze 规则」一节。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:33:- `docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:52:- `tests/test_init_contract.py` —— 它引用 `docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:74:- [ ] `docs/agentic/templates/WORK_PACKAGE.md` —— 与上一份**逐字节同一**
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:190:`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl`、`docs/agentic/templates/WORK_PACKAGE.md`、
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:263:- oracle 三项（本 WP 新增第 4 项的落点）：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-28.status.json:69:      "docs/agentic/templates/WORK_PACKAGE.md",
./docs/plans/2026-09-13-parallel-throughput/WP-25-brief-rev3.md:260:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-26-brief-rev2.md:204:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev1.md:27:| `docs/agentic/templates/WORK_PACKAGE.md` | 项目内骨架（与母本 `diff` 为空） | `FAIL missing 'Acceptance tests'` |
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev1.md:46:  - `docs/agentic/templates/WORK_PACKAGE.md`（项目内骨架，须与母本保持 `diff` 为空）
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev1.md:158:- `docs/agentic/templates/WORK_PACKAGE.md` — scaffolded skeleton; must stay
./docs/plans/2026-09-13-parallel-throughput/WP-25-brief-rev2.md:159:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
./docs/plans/2026-09-13-parallel-throughput/WP-25-brief.md:174:- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`（WP-24 rev1 已写入）
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief.md:47:    `docs/agentic/templates/WORK_PACKAGE.md` —— rev1 已定稿，本轮**零行 diff**
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief.md:80:  `docs/agentic/templates/WORK_PACKAGE.md` — settled in rev1; zero-line diff
./docs/QUICKSTART.zh-CN.md:230:1. 从 `docs/agentic/templates/WORK_PACKAGE.md` 复制出 brief，冻结目标/范围/DoD。
./AGENTS.md:84:- a tracked brief created from `docs/agentic/templates/WORK_PACKAGE.md`;
./src/agentic_loop/init_cmd.py:109:    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
./src/agentic_loop/templates/AGENTS.md.tmpl:84:- a tracked brief created from `docs/agentic/templates/WORK_PACKAGE.md`;
```

（排除项说明：`WP-29-scope-decision.md` 是本交付物自身，不是模板消费者，排除以消除自指；
`WP-28-consult-codex-shape-verdict.json` 是 codex 二签记录，其 `raw_verbatim` 单行 ~9.5KB
长文仅引用 INV-N3 原文，排除以保持证据可读——该文件属 C 类「agent 阅读」记录，见 C 类。）

**宽口径补充命中**（宽口径 `grep 'WORK_PACKAGE'` 共 96 行命中；减去上面两条主 grep 的并集
79 行（38 + 46 − 5 处重叠）后，差集为下列 17 行。差集由 `comm -23` 求得，命令与完整输出如下）：

```text
$ comm -23 \
      <(grep -rn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
          --exclude=WP-29-scope-decision.md --exclude=WP-28-consult-codex-shape-verdict.json \
          'WORK_PACKAGE' . | sort) \
      <(grep -rn --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
          --exclude=WP-29-scope-decision.md --exclude=WP-28-consult-codex-shape-verdict.json \
          -e 'WORK_PACKAGE\.md\.tmpl' -e 'docs/agentic/templates/WORK_PACKAGE\.md' . | sort -u)
./CHANGELOG.md:328:- **Per-WP reference templates (STATUS.json / WORK_PACKAGE.md).** `agentic init`
./CHANGELOG.md:330:  and `WORK_PACKAGE.md` (a brief skeleton), so an adopting project has a
./CHANGELOG.md:88:  a WP against its plan; also present in the `STATUS.json` and `WORK_PACKAGE.md`
./README.md:70:| `init` | 脚手架 `.agentic/config.toml` + 治理契约（AGENTS.md、CLAUDE.md、docs/agentic/OPERATING_MODEL.md）+ 每 WP 模板（docs/agentic/templates/{STATUS.json,WORK_PACKAGE.md}）+ `.claude/settings.json`（`Bash(agentic *)` allowlist，编排者免审批）+ `docs/plans/` 与 `.agentic/locks/` 骨架。无 `--force` 时拒绝覆盖已存在的受管文件。 |
./docs/QUICKSTART.zh-CN.md:202:#       docs/agentic/OPERATING_MODEL.md + docs/agentic/templates/{STATUS.json,WORK_PACKAGE.md}
./docs/plans/2026-09-13-parallel-throughput/WP-10-brief.md:65:   > `"_note"` 之类的说明键，或者写进同目录的 `WORK_PACKAGE.md` /
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief-rev2.md:158:- oracle 三项规则：本仓 `WORK_PACKAGE.md` 模板（rev1 已写入）+ 缺陷 B9
./docs/plans/2026-09-13-parallel-throughput/WP-24-brief.md:158:- oracle 三项规则：本仓 `WORK_PACKAGE.md` 模板（rev1 已写入）+ 缺陷 B9
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:243:1. **不要 bump `CONTRACT_TEMPLATE_VERSION`。** WORK_PACKAGE 是 reference skeleton，
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev2.md:266:- 契约渲染目标（证 WORK_PACKAGE 不在其中）：`src/agentic_loop/contract_render.py`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:274:2. **不要 bump `CONTRACT_TEMPLATE_VERSION`。** WORK_PACKAGE 是 reference skeleton，0 个占位符。
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief-rev3.md:293:- 契约渲染目标（证 WORK_PACKAGE 不在其中）：`src/agentic_loop/contract_render.py`
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:190:1. **不要 bump `CONTRACT_TEMPLATE_VERSION`。** WORK_PACKAGE 是 reference skeleton，
./docs/plans/2026-09-13-parallel-throughput/WP-28-brief.md:213:- 契约渲染目标（证 WORK_PACKAGE 不在其中）：`src/agentic_loop/contract_render.py`
./docs/plans/2026-09-13-parallel-throughput/WP-29-brief.md:45:1. **消费链实况**：除 `init_cmd.py:109` 外，`WORK_PACKAGE.md` / `.md.tmpl` 还被谁读取？
./tests/test_init_contract.py:62:    brief = tmp_path / "docs" / "agentic" / "templates" / "WORK_PACKAGE.md"
./tests/test_wp_template_dispatch_lint.py:24:TEMPLATE_DOCS = REPO_ROOT / "docs" / "agentic" / "templates" / "WORK_PACKAGE.md"
```

**四类归类**（按消费性质；原始命中行即上文 grep 输出）：

- **A. 运行时复制**（非测试程序执行期读取模板内容）：
  - `src/agentic_loop/init_cmd.py:109` —— `_REFERENCE_TEMPLATES` 元组中唯一把
    `WORK_PACKAGE.md.tmpl` 映射到 `docs/agentic/templates/WORK_PACKAGE.md` 的条目。
  - 复制机制（非 grep 命中，行号级代码核验）：`init_cmd.py:138-152` `_write_asset()` 在
    `:148` 调 `contract_render.load_template(tmpl_name)`，随后 `target.write_text(text, ...)`
    **逐字节写出**；`:253-254` 循环对 `_REFERENCE_TEMPLATES` 逐项调用 `_write_asset`。
  - `load_template` 调用点证据（命令原文 + 完整输出；`--exclude-dir=__pycache__` 排除 `.pyc`
    二进制命中，使输出只含源码行）：

```text
$ grep -rn --exclude-dir=__pycache__ 'load_template' src tests
src/agentic_loop/init_cmd.py:148:    text = contract_render.load_template(tmpl_name)
src/agentic_loop/contract_render.py:12:network, no hidden IO beyond ``load_template`` reading packaged data.
src/agentic_loop/contract_render.py:243:        load_template(name),
src/agentic_loop/contract_render.py:250:def load_template(name):
tests/test_contract_render.py:165:def test_load_template_all_three():
tests/test_contract_render.py:167:        txt = cr.load_template(name)
```

    6 行中生产调用点只有 `init_cmd.py:148`（铺开 reference 模板，含 `WORK_PACKAGE.md.tmpl`，
    逐字节复制）与 `contract_render.py:243`（`render_template` 内部，渲染
    AGENTS/CLAUDE/OPERATING_MODEL 三份契约，用 `string.Template` 替换占位符，不解析 markdown）；
    `:250` 为定义、`:12` 为 docstring、`:165` / `:167` 为测试。**无其它解析调用**。

- **B. 测试验证**（测试用例读取模板以断言内容/结构）：
  - `tests/test_init_contract.py:62`（宽口径补充命中）
  - `tests/test_wp_template_dispatch_lint.py:23`（主 grep）
  - `tests/test_wp_template_dispatch_lint.py:24`（宽口径补充命中）

- **C. 人 / agent 阅读**（文档或治理契约指示人/agent 去读模板）：
  - 主 grep 命中：
    - `AGENTS.md:84` 与 `src/agentic_loop/templates/AGENTS.md.tmpl:84`（治理契约：brief 须从
      `docs/agentic/templates/WORK_PACKAGE.md` 创建）
    - `docs/QUICKSTART.zh-CN.md:230`（快速上手：从模板复制 brief）
    - `docs/plans/` 下多份历史 WP 治理文档（brief / status / review / consult / report）中的
      大量引用（如 `WP-29.status.json:113` 记录本 WP 证据摘要），均为「冻结/阅读模板」的流程
      引用，非运行时读取。
  - 宽口径补充命中（15 行，见上「宽口径补充命中」块）：
    - 非 `docs/plans/` 5 行：`CHANGELOG.md:88` / `:328` / `:330`（变更记录）、`README.md:70`
      （`init` 脚手架说明）、`docs/QUICKSTART.zh-CN.md:202`（快速上手注释）。
    - `docs/plans/` 10 行：`WP-10-brief.md:65`、`WP-24-brief-rev2.md:158`、`WP-24-brief.md:158`、
      `WP-28-brief-rev2.md:243` / `:266`、`WP-28-brief-rev3.md:274` / `:293`、
      `WP-28-brief.md:190` / `:213`、`WP-29-brief.md:45` —— 均为历史 WP 治理文档里对模板 /
      「消费链实况」的引用，非运行时读取。
  - 另：`WP-28-consult-codex-shape-verdict.json:6` 属 C 类「agent 阅读」记录（codex 二签原文
    引用 INV-N3），已在上文 grep 中显式 `--exclude` 排除，理由见「排除项说明」。

- **D. 打包读取**（打包配置把模板作为 package data 纳入 wheel/sdist + 运行时经
  `importlib.resources` 读取）：
  - grep 命中：**零命中**。原因：`pyproject.toml` 用 `*.tmpl` glob、`contract_render.py` 用
    `name`/`tmpl_name` 变量，二者都不含字面 `WORK_PACKAGE` 字符串，故必须改用行号级证据 +
    资源入口 grep。
  - 资源读取入口证据（命令原文 + 完整输出；`_resources_files` 是 `importlib.resources.files`
    在本仓的唯一别名）：

```text
$ grep -rn --exclude-dir=__pycache__ '_resources_files' src
src/agentic_loop/contract_render.py:19:    from importlib.resources import files as _resources_files
src/agentic_loop/contract_render.py:21:    _resources_files = None
src/agentic_loop/contract_render.py:252:    if _resources_files is None:  # pragma: no cover
src/agentic_loop/contract_render.py:254:    resource = _resources_files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_SUBDIR).joinpath(name)
```

    上述 4 行都落在 `contract_render.py`：`:19` import 绑定、`:21` None 回退、`:252` None 守卫、
    `:254` **唯一一次调用**（真正读取 package data），位于 `load_template` 内。故「读取 package
    data 的入口只有 `load_template` 一处」在 `src/` 运行时源码这一搜索面内成立。
  - 行号级证据：
    - `pyproject.toml:24-29` `[tool.hatch.build.targets.wheel]` 的 `artifacts` 含
      `"src/agentic_loop/templates/*.tmpl"`。
    - `contract_render.py:18-19`：`from importlib.resources import files as _resources_files`。
    - `contract_render.py:27-28`：`_TEMPLATE_PACKAGE = "agentic_loop"`、
      `_TEMPLATE_SUBDIR = "templates"`。
    - `contract_render.py:250-255` `load_template(name)`：
      `resource = _resources_files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_SUBDIR).joinpath(name)`
      → `return resource.read_text(encoding="utf-8")`。
  - **D 类结论**：`pyproject.toml` 确实把 `*.tmpl` 纳入 wheel artifacts；运行时读取路径是
    `importlib.resources.files("agentic_loop").joinpath("templates").joinpath(name).read_text(...)`。
    `read_text(encoding="utf-8")` **只做 UTF-8 文本解码并返回字符串，不解析 Markdown、不生成
    AST、不识别注释/围栏/标题/块级结构**。即：打包读取路径**不解析 Markdown**。
  - 未覆盖面申报：`cli.py:25` 也 `import importlib.resources`（别名 `_resources`），但只用于
    `importlib.resources.path()` 定位打包的 wrapper 脚本（`cli.py:119` / `:222`），不读取模板
    package data，故不构成第二处模板读取入口。

**结论**：

- 唯一的**非测试运行时**消费者是 `src/agentic_loop/init_cmd.py:109`，行为是逐字节复制；
  其读取入口 `contract_render.load_template` 只 `read_text`，不解析 Markdown。
- **测试**消费者有两处（`test_init_contract.py:62`、`test_wp_template_dispatch_lint.py:23,24`），
  只断言结构/副本同一，同样不解析 Markdown。
- **人 / agent** 是流程/规范消费者（`AGENTS.md:84` 等指示「从模板复制 brief」），属认知消费，
  不是机械解析。
- **打包读取**把 `*.tmpl` 纳入 wheel，但运行时 `read_text` 不解析 Markdown。
- 因此「谁把模板当作活动 Markdown 结构来解析」的答案是：**没有任何机器路径**。

## 2. 渲染面实况

**问题**：这两份文件事实上会被哪些渲染器渲染？方言各是什么？不一致时以谁为权威？

**实测（本机可核验）**：

```text
$ git remote -v
origin  git@github.com:billbraves/agentic-loop.git (fetch)
origin  git@github.com:billbraves/agentic-loop.git (push)
```

- 仓库 origin 是 **GitLab**（`git@github.com:billbraves/agentic-loop.git`）。
- 本仓**无** `.github` 目录、无静态站点生成器配置（无 `mkdocs.yml` / `docusaurus` /
  `sphinx` / `_config.yml` 等）。
- 全仓**无**任何文档声明权威 Markdown 方言；对 `CommonMark|GFM|方言|dialect` 的 grep
  仅命中无关的「rendering」过程文档，无方言声明。

**推断（网络禁止，无法实测精确版本）**：

- 若在 VCS UI 查看，主要渲染器是 **GitLab Flavored Markdown（GLFM）**——由「origin 是
  GitLab」推断，确切 GLFM 版本/行为无法离线验证。
- 本地编辑器预览通常是 **CommonMark/GFM 变体**——同样是推断，非本机可测。
- 因为**没有任何文档声明权威方言**，所以「不一致时以谁为权威」这个问题在仓内**没有答案**，
  也**不存在**一个权威渲染器。

**结论（实测 + 推断）**：渲染面不存在权威单一渲染器；「以谁为权威」无法回答。这条事实
是裁定不走 parser 路线（方案 a）的关键依据之一。

## 3. 威胁是否真实

**问题**：一个把整份模板注释掉的改动，在当前流程里会被什么拦住？若无本 WP，后果链是什么？

**实测构造**（在 scratch 副本进行，不碰 live tree）：

- scratch 目录：`/tmp/wp29-threat.ZFhIU9`（复制 worktree 内容）。
- 基线：scratch 内 `PYTHONPATH=src python3.11 -m pytest tests/test_wp_template_dispatch_lint.py -q`
  → **7 passed in 1.88s**，exit 0。
- 变异：在**两份模板**（`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
  `docs/agentic/templates/WORK_PACKAGE.md`）的文档**顶部追加 `<!--`**、**底部追加 `-->`**，
  即把整份文档包进 HTML 注释。字节数由 `2889` 变为 `2898`（+9）。
- 变异后重跑同一命令：**7 passed in 1.87s**，exit 0，**判据没有转红**。

**对照 WP-28 判据**：WP-28 rev1（本树）的 `test_wp_template_dispatch_lint.py` 只校验
模板内锚点/受保护块 body 是否逐字节在，**整份外包注释不改变这些 body 的字节**，故 GREEN。

**`dispatch_lint.sh` 是否拦住**（代码核验，未单独跑）：
`src/agentic_loop/wrappers/dispatch_lint.sh:72-74` 的必需节标题为
`Acceptance tests` / `Allowed and forbidden paths` / `Completion definition`；
`:83-94` 用 `re.search(r"^##\s+<heading>\s*$", text, re.MULTILINE)` 找标题，body 判空时
只跳过以 `<!--` **开头**的行。整份外包注释下，标题仍以 `## ` 独立成行、正文行并非
每行都带 `<!--` 前缀，因此**推断其同样不转红**（此为代码审查推断，非威胁测试实测）。

**后果链（若无本 WP）**：

1. 一个把整份模板注释掉的 commit，**没有任何机械测试会转红**（上述实测 + 推断）。
2. 它只能被 **`git diff`** 和 **human/code review** 看到——但 WP 流程的 review 关注点是
   brief/status，模板的「活动性」不在既有判据覆盖面内。
3. 结果：模板可能在字节上仍通过 WP-28 判据，却在渲染端（GitLab/编辑器预览）整体失效，
   后续人/agent 复制模板时拿到一份「被注释掉的骨架」，规范悄然丢失。
4. 因此威胁**真实存在**，且**当前没有任何机械防线**覆盖它。

## 4. 方案对比

**判据实况先声明**（每格「实测」必须说清测的是哪个判据；本仓同一份测试文件在三处形态不同）：

| 判据 | 形态 | 对 E1–E4 / G1–G4 的表现 |
|---|---|---|
| **WP-28 rev1**（本树 `tests/test_wp_template_dispatch_lint.py`，7 passed，无 `FROZEN_BODY`） | 只查段落标题在场 + 两份副本逐字节一致，不看 body 内容 | 本 WP 在 `/tmp` 副本实测：8/8 全 GREEN（灵敏度 0、特异性 1） |
| **WP-28 rev6**（主仓 plan 分支，有 `FROZEN_BODY`） | 两个受保护节 body 逐字节冻结 | 不在本树，**未实测**；按 brief 描述 G1–G4 应 GREEN |
| **(b) 整份模板逐字节冻结**（本 WP 要评估的假设方案） | 完整 76 行逐字节比较 | 本 WP 实测：8/8 全 RED（灵敏度 1、特异性 0） |

- WP-28 rev1 的实测脚本：`/tmp/wp29-wp28rev1-measure.py`（对 `/tmp` 副本施加 E1–E4/G1–G4，
  跑真实 `python3.11 -m pytest tests/test_wp_template_dispatch_lint.py -q`，每格带
  `assert mutated != ORIG` 守卫）。结果：baseline `7 passed`；E1/E2/E3/E4/G1/G2/G3/G4 全部
  `7 passed`（GREEN）。
- (b) 的实测脚本：`/tmp/wp29-optionb-measure.py`（冻结全文 vs 变异后全文的**完整 76 行逐字节
  比较**，`mutated == ORIG` 判 GREEN，否则 RED；每格带 `assert mutated != ORIG` 守卫）。输出：

```text
ORIGINAL bytes = 2889
mutation    bytes     (b) full-file freeze
E1       2898                      RED
E2       2894                      RED
E3       2893                      RED
E4       2951                      RED
G1       2892                      RED
G2       2941                      RED
G3       2895                      RED
G4       2889                      RED
```

（G4 字节长度虽未变 2889，但内容已变，仍判 RED。每个变异都带 `assert 变异后 != 变异前`
守卫，空操作会中止，不会打印假绿。）

**方案对比表**（图例：RED = 判据转红「拦下」；GREEN = 判据转绿「放过」。攻击侧 E 期望 RED，
合法侧 G 期望 GREEN。）

| 变异 | (a) 权威 parser | (b) 整份模板逐字节冻结 | (c) 明文限制 + review | (c′) 受保护 envelope 冻结 + 承诺明文化 + review |
|---|---|---|---|---|
| E1 整份文档外包 `<!-- -->` | RED（推断） | RED（实测） | GREEN 放过（推断） | GREEN 不承诺（推断） |
| E2 文档开头未闭合 `<!--` | RED（推断） | RED（实测） | GREEN 放过（推断） | GREEN 不承诺（推断） |
| E3 `## 附注` 内未闭合围栏 | RED（推断） | RED（实测） | GREEN 放过（推断） | GREEN 不承诺（推断） |
| E4 顶部远距离去规范化句 | GREEN（推断） | RED（实测） | GREEN 放过（推断） | GREEN 不承诺（推断） |
| G1 改占位符 `<这个 WP 要交付什么>` | GREEN（推断） | RED（实测） | GREEN（推断） | GREEN（推断） |
| G2 文末追加无关章节 | GREEN（推断） | RED（实测） | GREEN（推断） | GREEN（推断） |
| G3 改 `## 范围` 正文 | GREEN（推断） | RED（实测） | GREEN（推断） | GREEN（推断） |
| G4 改 `> 冻结日期` 行 | GREEN（推断） | RED（实测） | GREEN（推断） | GREEN（推断） |

**每格判据与实测/推断标注**：

- **(a) 权威 parser**：全列「推断」。本仓无 parser 依赖、本轮禁引依赖，无法实测。行为由其
  判据形状（解析整份文档 → 校验目标 AST 节点是否为活动 heading/paragraph）推出：E1/E2/E3 使
  目标标题落入注释/未闭合注释/代码块，parser 判非活动 → RED；E4 是自然语言矛盾，目标标题
  AST 结构仍有效 → GREEN；G1–G4 不改变目标结构 → GREEN。
- **(b) 整份模板逐字节冻结**：全列「实测」（脚本 `/tmp/wp29-optionb-measure.py`，见上）。
  任何字节改变都 RED，故 E1–E4 全 RED（灵敏度 1）、G1–G4 全 RED（特异性 0）。
- **(c) 明文限制 + review**：全列「推断」。它没有任何机器判据，故攻击侧一律 GREEN（放过，
  全交给 review）、合法侧一律 GREEN（无判据可误伤）。
- **(c′)**：全列「推断」（方案尚未实现，按 §5 判据形状推理）。受保护节 body 逐字节冻结 +
  副本一致只覆盖「受保护节字节跨度内」的编辑：E1–E4 都不改受保护节字节（只改块外上下文使
  其不再活动）→ GREEN，且明确申报为「不承诺覆盖」（交 review）；G1–G4 都不落在受保护节字节
  跨度内 → GREEN。

**成本与判别力**：

- **(a)**：E1/E2/E3 强，但需选方言+版本并钉死，引入依赖与 CI/离线影响面，且**对 E4 无效**。
- **(b)**：灵敏度 1（E1–E4 全拦），但特异性 0（G1–G4 全误伤）。拦的是「文件被改」这个开放
  全集，不是「E1–E4 这四种攻击」这个有界目标。
- **(c)**：零工程成本，但 E1–E4 一条都拦不住，只推给 review。
- **(c′)**：特异性 1（G1–G4 全放行），对受保护节字节篡改有机械覆盖；对 E1–E4 这类
  active-embedding 攻击**诚实申报不覆盖**，交 `git diff` + review。这与「不引 parser、不
  整份冻结、承诺边界明文化」的目标一致。

## 5. 裁定

**推荐 (c′)：不引 parser、不整份冻结、承诺边界明文化 + 受保护 envelope 逐字节冻结 +
两份副本逐字节一致；`active_embedding` 明确不承诺，交 `git diff` + human review。**

判据形状（阶段 2 实现时落地，本阶段只裁定不实现）：

1. `replica_identity`（INV-N3）：`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
   `docs/agentic/templates/WORK_PACKAGE.md` 逐字节一致。
2. `protected_body_identity`：两个受保护节的 body 与冻结常量逐字节相等。
3. **明确不承诺 `active_embedding`**：判据不保证「任意渲染器下受保护节显示为活动文本」。

覆盖率诚实申报（**承诺量词闭合**）：

- 受保护节 body 逐字节冻结**拦的是**「两个受保护节字节跨度内发生字节改变」这一个**闭合输入
  维度**（该维度由冻结常量的精确字节序列界定：任何使该序列 != 常量的编辑都转红）。这是
  「一个精确形状 + 一个闭合维度」的覆盖，**不是**「active-embedding 族」的覆盖。
- 它**不拦** E1–E4 四条（这四条都不改变受保护节字节，而是改变块外上下文使受保护节不再活动）。
  因此 E1–E4 明确申报为**不承诺覆盖**，交 `git diff` + human review（§3 已证这是当前唯一
  防线，且威胁真实）。
- G1–G4 四条全部 GREEN（都不落在受保护节字节跨度内，判据不转红）。这是 (c′) 与 (b) 的本质
  区别：**(b) 特异性 0，把 G1–G4 也判红，故不可作为推荐**。

**已作废且不再作为依据**：编排者复核文档曾提「文首/末哨兵，专拦 E1/E2 这一族」，该推荐已被
编排者自己撤回（`WP-29-review-stage1.md` §7），codex 绕过与编排者探针
`probes/WP-29-sentinel-bypass-probe.py` 实测一致：哨兵只拦「在 sentinel **外侧**追加前后缀」
这一个精确形状，不拦 E1/E2 族。**本裁定不采用哨兵**。

**随 (c′) 一并落地的「已知限制」措辞**（阶段 2 写判据时须注明，此处先给措辞）：

> 本判据仅保证两份模板逐字节一致、且两个受保护节 body 与冻结版本一致；不证明任意 Markdown
> 渲染器将受保护节显示为活动文本，也不保证消费者采纳或遵守其规范。

即：判据防的是「受保护节被悄悄改坏 + 两份副本分叉」，不假装保证「渲染端一定显示为活动文本」。

（说明：本阶段只做裁定，不写判据、不引依赖。上述判据形状与措辞供阶段 2 实现时使用。）

## 6. rev1 → rev4 改了什么

### 6.1 rev1 → rev3（上一轮，已提交 `e493c2a`）

逐条对应 rev3 brief 的三件标的与编排者缺陷修正：

- **C1（消费面证据）**：§1 从 rev1 的「`src/ tests/` + 手挑文件」升级为**仓库级
  `grep -rn` + 显式 `--exclude-dir=.git,__pycache__,.pytest_cache` + A/B/C/D 四分类**。
  - 新增 **D 类打包读取**（rev1 完全漏掉），给出 `pyproject.toml:24-29` artifacts 行与
    `contract_render.load_template` 行号级结论：`read_text(encoding="utf-8")` **不解析 Markdown**。
  - 「唯一」加限定词：改为「唯一的**非测试运行时**消费者」，不再出现无限定「唯一的仓内机器消费者」。
- **C2（特异性与裁定）**：§4 表从「只有 E1–E4 攻击侧」升级为「E1–E4 + G1–G4 两侧」，每格填
  RED/GREEN 且标注实测/推断。
  - (b) 列 G1–G4 四个 RED 由本 WP 自己实测（脚本 `/tmp/wp29-optionb-measure.py`，完整 76 行
    逐字节比较，每格 `assert 变异后 != 变异前` 守卫）。
  - §5 裁定从 (b) 改为 **(c′)**，与 G1–G4 兼容（四条全 GREEN）。
  - 承诺量词闭合：「拦住 X」改为「一个精确形状 + 一个闭合字节维度」，并明写 E1–E4 为不承诺覆盖。
  - 不采用已撤回的哨兵推荐。
- **措辞**：§0 / §5 不再出现「(b) 覆盖 E1–E4 全部」式表述，改为区分灵敏度与特异性：
  (b) 灵敏度 1、特异性 0；(c′) 特异性 1、对 E1–E4 诚实申报不覆盖。
- **基线**：rev1 DoD 沿用 brief 的 `4 failed / 619 passed / 4 skipped` 是 **WP-28 lane** 数字
  （编排者 B48 抄错 lane）。本轮 DoD 用 **WP-29 lane 真实基线 `4 failed / 606 passed / 4 skipped`**
  （编排者已在 rev3 brief 标的 3 第 1 条确认并修正）。

### 6.2 rev3 → rev4（本轮，只动 §1 消费面证据）

本轮仅修订 §1，目标是让每个粘贴的 grep 块都能与字面重跑逐行一致：

- **主 grep 加排除项**：三条主 grep（`WORK_PACKAGE\.md\.tmpl`、
  `docs/agentic/templates/WORK_PACKAGE\.md`、宽口径 `WORK_PACKAGE`）统一追加
  `--exclude=WP-29-scope-decision.md --exclude=WP-28-consult-codex-shape-verdict.json`，
  消除「本交付物自指」与「codex 二签长文干扰」，并在文中写明排除理由。
- **补 `load_template` 调用点原文**（6 行，`grep -rn --exclude-dir=__pycache__ 'load_template'
  src tests`）：坐实生产调用点只有 `init_cmd.py:148`（铺开 reference 模板）与
  `contract_render.py:243`（渲染三份契约，不解析 markdown）；其余为定义/docstring/测试。
- **补 `_resources_files` 资源入口原文**（4 行，`grep -rn --exclude-dir=__pycache__
  '_resources_files' src`）：坐实 `importlib.resources.files` 的唯一调用点是 `load_template` 内
  的 `contract_render.py:254`，即「读取 package data 的入口只有一处」。
- **宽口径差集补全**：从「手挑 5 行」改为 `comm -23` 字面差集，补到完整 17 行；B/C 四分类
  按「主 grep 命中 / 宽口径补充命中」来源重新标注，新增 `cli.py` 非第二读取入口的未覆盖面申报。
- **去省略符**：移除 §1 全部 U+2026 省略符，每个 grep 粘贴块与 `grep` 字面重跑逐行一致。

## 7. 自我核查（selfcheck）

以下命令均在 worktree `/Users/admin/vibe/wp29-render-scope-decision`、分支
`feature/wp29-render-scope-decision`、HEAD `e493c2a62e14f9a7f9fc5528168b9be5d2b2bf23`（rev3 提交）执行。

```bash
git status --porcelain
# ->  M docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md
#   （提交前：工作树只有本文件处于 modified，无其它改动）
```

```bash
git diff --stat HEAD
# ->  docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md | 174 ++++++++++++++++-----
# ->  1 file changed, 137 insertions(+), 37 deletions(-)
```

```bash
printf 'single-U+2026: '; grep -c "$(printf '\342\200\246')" docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md || true
# -> single-U+2026: 0
printf 'double-U+2026: '; grep -c "$(printf '\342\200\246\342\200\246')" docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md || true
# -> double-U+2026: 0
```

```bash
git diff --exit-code HEAD -- pyproject.toml uv.lock && echo DEPS_UNCHANGED
# -> DEPS_UNCHANGED（uv.lock 不存在，pyproject.toml 零 diff）
```

```bash
git diff --exit-code HEAD -- src/agentic_loop/templates/ docs/agentic/templates/ && echo TEMPLATES_UNCHANGED
# -> TEMPLATES_UNCHANGED
```

模板逐字节核验（字面重跑）：

```text
$ wc -c src/agentic_loop/templates/WORK_PACKAGE.md.tmpl docs/agentic/templates/WORK_PACKAGE.md
    2889 src/agentic_loop/templates/WORK_PACKAGE.md.tmpl
    2889 docs/agentic/templates/WORK_PACKAGE.md
    5778 total

$ cmp src/agentic_loop/templates/WORK_PACKAGE.md.tmpl docs/agentic/templates/WORK_PACKAGE.md && echo IDENTICAL
IDENTICAL
```

全量（§6 命令）：

```text
$ PYTHONPATH=src python3.11 -m pytest tests -q
4 failed, 606 passed, 4 skipped in 116.99s
```

- 4 failed 全部在 `tests/test_finalize_merge_triple_sign.py`（本机
  `git init.defaultBranch=master` 与 fixture 冲突，**既有失败，不修**）。
- 4 skipped：`test_finalize_merge_wrapper_sync.py:28` ×1、`test_validate_wp_status_qoder.py:548` ×3。

（上述为提交前实跑输出。`git status --porcelain` 显示本文件为 modified，属本轮唯一改动；
提交后工作树将转为干净。）

## 附：与 DoD 的逐项对照

- [x] `WP-29-scope-decision.md` 存在，5 项逐条作答，每项附可核验证据（§0–§5）
- [x] 消费链一项附仓库级 `grep -rn` 原文命令 + 显式 `--exclude-dir` + `--exclude`（本交付物 + codex 二签）+ 完整输出，A/B/C/D 四分类（§1）
- [x] D 类给出 `pyproject.toml` artifacts 行 + `load_template` 调用点原文 + `_resources_files` 资源入口原文，行号级结论（不解析 Markdown）（§1）
- [x] 「唯一」带限定词：唯一的**非测试运行时**消费者（§1）
- [x] 每个 grep 粘贴块可字面重跑；全文零 U+2026 省略符（§1 / §7）
- [x] 渲染面一项区分「实测」与「推断」（§2，保留）
- [x] 威胁真实性一项附实际构造与 pytest 实测输出，`git status` 跑完干净（§3，保留）
- [x] 方案对比含攻击侧 E1–E4 + 合法编辑侧 G1–G4 两侧，每格 RED/GREEN 且标注实测/推断（§4）
- [x] (b) 列 G1–G4 四 RED 由执行者自己实测（`/tmp/wp29-optionb-measure.py`），附输出（§4）
- [x] 每个变异带 `assert 变异后 != 变异前` 守卫（§4 两个脚本均带）
- [x] §0/§5 用灵敏度/特异性表述，不再出现「(b) 覆盖 E1–E4 全部」（§0/§5）
- [x] 末尾有明确裁定（(c′)，§5），与 G1–G4 兼容，承诺量词闭合，不采用哨兵
- [x] 文档含「rev1 → rev4 改了什么」一节：§6.1 逐条对应 C1 / C2 / 措辞 / 基线，§6.2 记录 rev3→rev4 的 §1 证据补全（§6）
- [x] 零代码改动：`git diff --stat` 只含本 md 文件（§7）
- [x] 未引入任何依赖（`pyproject.toml` / `uv.lock` 零 diff，§7）
- [x] 未碰两份模板（`git diff --exit-code` 证明，§7）
- [x] 相对基线零回归：实测 `4 failed / 606 passed / 4 skipped`（§7）
- [x] 无 forbidden_paths / 跨 owner 写入
- [x] 无生产写入、无网络、无通知、无推送
- [x] 无 merge、无 push、不切生产分支

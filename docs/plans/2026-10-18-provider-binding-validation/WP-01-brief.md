# WP-01: 固定 triple-sign 测试的初始分支，使基线在非 main 默认分支宿主上转绿

> 冻结日期 2026-10-18 | 编排者 claude-code | 执行者 待定。
> 所属 Plan：PLAN-01（集成到 `plan/2026-10-18-provider-binding-validation`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze。

## 目标（一句话）

让 `tests/test_finalize_merge_triple_sign.py` 的初始分支由测试自己固定，
不再继承宿主 `init.defaultBranch`，从而在任何宿主上全绿。

## 不变式（验收标的）

**该测试模块的通过与否，不得取决于宿主 git 的 `init.defaultBranch` 配置。**

本机 `git config --get init.defaultBranch` 为 `master`；该模块的 4 个端到端用例
硬编码 `base_branch = "main"` 并在 `_merge_wp_branch` 里 `git checkout main`，
于是临时仓库建成 `master` 后 checkout 失败。这是环境依赖，不是产品缺陷。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `tests/test_finalize_merge_triple_sign.py`
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/**`
  - `docs/plans/2026-09-22-framework-hardening/**`
  - `.agentic/**`
- **owner 边界**：纯测试夹具改动，不涉及产品语义。

## 输入

- 依赖的上游 WP 产出：无
- 参考文档：`docs/plans/2026-09-22-framework-hardening` 中 WP-30 的
  `INV-W30-1 (D-13)` 口径（该分支已弃用，仅作归因参考，不整体回迁）

## 交付物清单

- [ ] `tests/test_finalize_merge_triple_sign.py` — 初始分支由夹具自己固定

## 完成定义（DoD）

- [ ] 交付物就绪
- [ ] 该模块在本机（`init.defaultBranch=master`）全绿
- [ ] 全套测试无新增失败
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

- 已知陷阱：WP-30 的同一修复散在两个提交里，还夹带了与本 WP 无关的
  case ④ 加固（`base_commit` 绑定真实值）与 `test_redispatch_quota_fallback.py`
  的改动。**不要整体回迁**，只取「固定初始分支」这一必要最小面，
  否则会把另一个分支的在途工作裹进来。
- 最小可行改动已实测：把 `git init -q` 改为 `git init -q -b main`
  即可让该模块 5 passed。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」同义，非另一份口径。

验收命令：`python3.11 -m pytest tests/test_finalize_merge_triple_sign.py -q`
（在 `init.defaultBranch=master` 的本机执行，期望全绿）

三条负面/正面证据：

1. **正向可达性对照**：未做任何变异时，该模块 5 passed，证明夹具能走到终点。
2. **原因特异 witness**：变异（把初始分支改回继承宿主默认）后，失败必须表现为
   `git checkout -q main` 返回非零的 `CalledProcessError`，而非其他原因。
3. **代表性禁止变异转红**：还原变异后该模块必须转红；恢复固定分支后转绿。

## Allowed and forbidden paths

本段与上文「范围」一节完全同义，非另一份口径：只能改
`tests/test_finalize_merge_triple_sign.py`，绝不能碰 `src/**`、
`docs/plans/2026-09-22-framework-hardening/**`、`.agentic/**`。

## Completion definition

本段与上文「完成定义（DoD）」同义，非另一份口径：交付物就绪、该模块全绿、
全套无新增失败、无 forbidden_paths 写入、无生产写入/网络/通知/推送、
commit message 符合规范。

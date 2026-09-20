# WP-29 阶段 1 rev5 第二签名裁定（codex，逐字转录）

> 咨询日期 2026-09-20 | consultant codex / provider kirogpt / model gpt-5.6-sol
> 传输：`codex exec --ignore-user-config --sandbox read-only --skip-git-repo-check`
> `-c model_reasoning_effort=high --output-schema`，cwd = 被审 worktree（read-only sandbox）
> 咨询请求：`WP-29-consult-rev5.md` sha256 `2f91b24dd6910672392c72c2b354222fdefadce5040bda3c3fc3269496eb9aab`
> 被审提交：`e2c483d26ef9999ac77aaaa22db59b2e0db5abe4`
> 交付物 sha256：`1ac5a413fdf1d74ff7078536a379e8fb8325176caf832be1e4c4a9e2551da6b1`
> exit 0 | 输入 58706 字节 | 输出 1779 字节
>
> **本轮是并行第二签名**：派发时 codex 未收到编排者的任何结论，
> 第一签名 `WP-29-review-rev5.md` 与本文件并行产出。

以下为 `--output-schema` 落盘答案的**逐字原文**（仅去掉文件末尾换行，未作任何改写、
未作摘要、未重排顺序；见记忆 `codex-output-schema-is-advisory`）：

---

REWORK

存在两个具体、边界明确的文档缺陷，修复后可重新签名：

1. [WP-29-scope-decision.md:517](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:517) 把 `f1eee7e…` 标成“rev5 提交”，但实际 rev5 提交是 `e2c483d…`。该修改也超出 brief 对 §7“仅更新与 §1 新数字有关格子”的授权。

   可重跑：

   ```bash
   git rev-parse HEAD
   sed -n '514,520p' docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md
   ```

   实际 HEAD 为 `e2c483d26ef9999ac77aaaa22db59b2e0db5abe4`，文档却写 `f1eee7e…（rev5 提交）`。

2. [WP-29-scope-decision.md:588](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:588) 的当前 DoD 自核查仍声称主 grep 的 `--exclude` 包含“本交付物 + codex 二签”，与 rev5 实际命令和标的 A 相反；当前命令只排除 `WP-29-scope-decision.md`。这是交付物内部的现行事实矛盾，应改成只排除本交付物。

其余冻结标的独立核验通过：

- 标的 A：两条主 grep 为 39/47 行且集合一致；差集过滤器同步，17 行逐行一致；两处长行均与源 grep 行同为 9660 bytes（含换行），SHA-256 均为 `409de41d2111fdc63ded00a086e2c90c52a43db8e9598416ec3f3351ac70f1b5`。
- 标的 B：选择路线 (a)，当前断言已收窄为 `_resources_files` 这一别名的调用面，并保留 `cli.py:25` 未覆盖面。
- 标的 C：`binary`、`locale`、`cwd`、`shell` 及排序承诺完整；在 `/bin/bash`、`LC_ALL=C` 下复现为 `39/47/17/6/4`。
- §2、§3、§4、§5 与 `f1eee7e` 逐节字节一致。
- 未发现用“等效替代”追认冻结判据的情况。
---

## 编排者的独立复核（不改动上文）

两个阻断项均由编排者在原文上独立复现成立：

| 项 | codex 给的位置 | 实测位置 | 复现结论 |
|----|---------------|---------|---------|
| 1 | `:517` | `:517` 确认 | `git rev-parse HEAD` = `e2c483d26ef9…`；文档写 `f1eee7e650c3…（rev5 提交）`。`f1eee7e` 是 **rev4** 的提交。成立 |
| 2 | `:588` | 实为 `:590` | 该行仍写 `--exclude`（本交付物 + codex 二签），与 §1 现行命令（只排除本交付物）矛盾。成立；codex 的行号偏 2 行，指认的文本无误 |

codex 列为「独立核验通过」的四项，编排者亦独立实测一致：主 grep 39/47 行且与粘贴块
逐字节相同（含顺序）、差集 17 行逐字节相同、两处长行 sha256 均为
`409de41d2111fdc63ded00a086e2c90c52a43db8e9598416ec3f3351ac70f1b5`、
§2/§3/§4/§5 与 `f1eee7e` 逐字节相同（171 行，sha 前 16 位 `f78662dd15809be3`）。

**双签名一致：REWORK**，阻断项两条，均为交付物内部现行事实矛盾，与标的 A/B/C 的实质无关。

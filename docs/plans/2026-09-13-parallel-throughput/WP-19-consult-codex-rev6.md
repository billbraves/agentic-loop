# WP-19 rev6 咨询记录（codex）

> 触发时间 2026-09-15 ｜ 提问者 claude（编排者）｜ 咨询者 codex（provider: kirogpt）
> 被审对象：`949b976`（`feature/wp19-wrapper-seams`），冻结输入 `WP-19-brief-rev5.md`
> 命令形态：`codex exec --sandbox read-only -m kirogpt --disable apps`（依 A31）

## 触发理由

rev6 需完成双签。另有一项处置争议必须由独立审核者裁定：执行者自报 `BLOCKED`
并称判据 fail-open，编排者实测否证后判 `ACCEPT`——编排者不能自审自过。

## 提问四点

1. rev6 把断言从「实现路径」降为「契约」是否恰当？有没有变成**永真用例**、失去检测能力？
2. 编排者对 A33「非 fail-open」的定性是否成立？有没有真能绕过拒收的形态被漏掉？
3. A33 落在本轮唯一白名单文件里但由 rev4 引入。rev5 那轮 codex 曾主张「凡落在本轮白名单
   且由本轮引入的缺陷必须本轮闭合」。转后续 WP 是否恰当？
4. 有没有双方都没看到的更深问题？

## codex 结论

**`[VERDICT] ACCEPT`**（P0 无）

| 级别 | 条目 | 处置 |
|------|------|------|
| P1 | A33 测试脆性（rev4 引入，非 rev6 阻断）：主区 symlink loop 被固定为 `True`，3.13+ 可能返回 `False`；应在后续 WP 改为「不抛异常 + 返回 bool」，并**单独保留** linked worktree loop 必须为 `True` | 采纳，并入任务「用例契约化」WP |
| P2 | `finalize_merge.sh` 注释所称「Python 异常导致 command substitution 跳过拒收」**不准确**：`set -euo pipefail` 下赋值中的非零退出直接终止脚本 | 采纳，与编排者独立实测一致，A29 修法 2 待办撤销 |
| P2 | **新发现**：判据与后续 `-f`、验证、写回之间存在 **symlink TOCTOU 窗口**；若本地并发恶意替换属威胁模型可另立安全 WP。不是 A33 静态 loop，也非 rev6 引入 | 采纳为新缺陷 **A34**，另立 WP，不阻断 rev6 |

### `[RATIONALE]`（要点）

1. **不是永真用例**：`isinstance(result, bool)` 既验「不抛异常」，也拒绝 `0/1` 伪 bool
   （`result in (True, False)` 会错误接受 `0`/`1`）。该用例单独看允许恒定 bool，
   但与新增的「linked worktree 超长路径必须 `True`」及既有的「主区普通路径必须 `False`」
   合起来看，检测能力仍在。
2. **A33 非 fail-open**（独立推演四条形态）：解析抛错时返回 `True`；3.13+ 主区 loop 探测主区
   返回 `False`，但该 loop 不可作为文件访问，后续 `-f` 仍拒绝；linked worktree 内 loop
   要么按父目录识别为 worktree、要么 Git 探测失败，两路都返回 `True`；指向真实
   linked-worktree 文件的 symlink 先解析到 worktree，仍 `True`。
   **「未发现无需竞态即可绕过拒收的形态」**——与编排者实测结论一致。
3. **处置恰当**：「落在白名单」只是**允许**修改，不等于**必须**顺带修复；本轮闭合义务需
   同时满足「本轮引入」。A33 由 rev4 引入、基线已失败，且 rev6 明确禁改实现，
   故转后续 WP 优于扩大冻结范围。**这同时澄清了 rev5 那条 P1 的适用边界。**
4. 已独立核实 `949b976^..949b976` 恰好只改 `tests/test_worktree_detection.py`（+28/-3），
   `gate/__init__.py` 零差异，A30 目标完成且无 rev6 新回归。

## 过程记录（流程缺陷复现）

- codex 指出编排者 prompt 里的 worktree 路径多写了一个 `s`
  （`wp19-wrappers-seams` → 实际 `wp19-wrapper-seams`），并自行纠正后继续。
- codex 另指出：rev5 与 rev6 是**同基线的替代提交**，不能用 `77941f4..949b976` 判断本轮范围，
  应审 `949b976^..949b976`。编排者原先用 AST 逐 def 比对，结论一致但路径不同；
  采纳其 range 写法为后续标准。
- 本次运行仍以 `codex_models_manager: failed to refresh available models` 结束，
  但 **verdict 已在 abort 前完整输出**，位于日志中段而非末尾。
  → **A31 补充**：不能只看日志尾部判断 codex 是否给出结论，须全文检索 `[VERDICT]`。

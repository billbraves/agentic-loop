# WP-19 咨询记录（codex，rev2+rev3 复审）

> 触发时间 2026-09-15 ｜ 提问者 claude（编排者）｜ 咨询者 codex（provider: kirogpt，model `gpt-5.6-sol`）
> 依 `CLAUDE.md`「record its question and recommendation in the iteration directory」落盘。
> 原始 prompt 暂存于 job tmp（`wp19-rev23-consult-prompt.txt`，约 30KB，非 Git-visible），
> 故提问要点在此复述留痕；codex 结论逐条摘录于下。

## 触发理由

rev1 的教训是编排者单方 ACCEPT 后被 codex 判 REWORK，且本轮返工要闭合的 A22
本身就是 codex 独立审出的。rev2+rev3 的验收同样不能自审自过：
按双签门禁，合并需 `review.decision=ACCEPT` **且** `consult.decision=ACCEPT`。

## 提问（要点）

1. A22 是否真的闭合？环境变量净化后还有无残余的「调用者声明仓库归属」通道？
2. rev3 相对 rev2 只多净化 4 个变量（`GIT_INDEX_FILE`、`GIT_OBJECT_DIRECTORY`、
   `GIT_ALTERNATE_OBJECT_DIRECTORIES`、`GIT_CEILING_DIRECTORIES`），
   编排者已实证**无任何测试能区分 rev3 与 rev2**（三路 revert：rev1 判据 3 failed/8 passed，
   rev2 与 rev3 判据均 11 passed）。这是可接受的 defense in depth，还是空动作？
3. fail-closed 是否在所有路径上成立？
4. 范围与纪律：执行者是否越界（allowlist 2 文件、0 docs/ 写入、0 merge）？
5. 有没有编排者没看到的更深问题？

## codex 结论

**`REWORK`**（5 条 findings，编排者已逐条独立复现，见 `WP-19.report.md` §复审）。

1. **fail-closed 对异常输出不成立**（P0，落在 allowlist 内）。
   `path_is_in_worktree` 只校验「恰好两行」与 `git_dir` 为绝对路径，
   未校验两行去空白后均非空。第二行为空白时 `common_dir=Path("")` 被解析成
   `directory`，若第一行也是该目录则返回 `False`——违反 Brief「输出异常 -> True」。
   另：两次 `Path.resolve()` 不在 `try` 内，symlink loop 抛 `RuntimeError`,
   违反 docstring 的「never raises」。
2. **gitfile 重指向**：worktree 根的 `.git` 是可写 gitfile，改指 common dir 后
   git 即把该目录解释为主仓，两侧相等 -> `False`。净化环境变量无法解决。
   —— 编排者已于 `1f7400f` 登记为 **A25（语义边界，登记不返工）**，理由见该条。
3. **入口前置 root 解析未净化**：`gate main()` 先调未净化的 `main_repo()`；
   `finalize_merge.sh:23`、`codex_merge_gate.sh:21` 也先跑继承环境的
   `git rev-parse --git-common-dir`。实测 `GIT_DIR=<别的仓>/.git` 能把
   `resolve_paths --root main_repo` 整体改指到另一个仓库。
   codex 自己指出「完整修复可能需要重新冻结范围，因为 wrapper/CLI 当前属 forbidden_paths」。
4. **status symlink 拓扑绕过**：判据用未解析的 `path.parent`；主区 symlink 指向
   worktree status 时判 `False`，而后续 `is_file()`/validator/读写都跟随 symlink
   操作 worktree 文件。判的是路径名归属，不是实际被读文件的归属。
5. **TOCTOU**：`os.environ` 拷贝无实质线程风险（两调用点均单线程 CLI）；
   真实风险是文件系统 TOCTOU——`is_file()`、git 探测、validator 读、最终写回
   之间 symlink/gitfile 可变。

### codex 明确排除的候选

`GIT_CONFIG_SYSTEM`、`GIT_CONFIG_NOSYSTEM`、`core.worktree`、`GIT_ATTR_*`、
`core.hooksPath`、replace refs——当前 `rev-parse` 不执行 hooks、不读 attributes、
不解析对象或 refs，故无影响（与编排者 24 向量探测结论一致）。
`PATH` 可替换 `git` 并伪造等值输出，但「允许调用者控制被执行程序已接近任意代码执行」，
codex 判定其不是最小 A22 威胁模型下最有价值的独立缺陷。

### codex 自陈的验证限制

只读沙箱无可用临时目录，**无法重跑 pytest**；等值输出、异常输出返回值、
入口 root 重绑定三项已用当前代码直接验证。
—— 故回归证据仍以编排者独立跑的全量套件为准（`4 failed + 574 passed + 4 skipped`）。

## 编排者处置

见 `WP-19.report.md` §rev4 返工范围。要点：F1 落在 allowlist 内，必修；
F4 判据侧可修（解析后再取父目录）；F2 已登记为 A25；F3 跨 forbidden_paths，
需另立 WP 并重新冻结范围，不在 WP-19 内扩权。

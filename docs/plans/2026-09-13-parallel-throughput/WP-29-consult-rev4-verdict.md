# WP-29 阶段 1 rev4 —— codex 第二签名裁定（逐字转录）

> 咨询请求：`docs/plans/2026-09-13-parallel-throughput/WP-29-consult-rev4.md`
> 被审 worktree：`/Users/admin/vibe/wp29-render-scope-decision`，提交 `f1eee7e`
> 执行方式：`env -u OPENAI_BASE_URL codex exec --sandbox read-only`（只读，exit 0）
> 裁定日期 2026-09-19 | 以下为 codex 最终答复的**逐字**转录（仅去 ANSI 控制序列）

---

REWORK

1. **Q1：标的 0 闭合了 B57 的窄问题，但不能单独证明过滤后的搜索仍回答原问题。**

五个命令块在当前指定执行面下均通过：

| 块 | 粘贴范围 | 粘贴/重跑 | 逐行比对 |
|---|---|---:|---|
| 1 | [WP-29-scope-decision.md:42](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:42) | 38/38 | IDENTICAL |
| 2 | [WP-29-scope-decision.md:86](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:86) | 46/46 | IDENTICAL |
| 3 | [WP-29-scope-decision.md:149](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:149) | 17/17 | IDENTICAL |
| 4 | [WP-29-scope-decision.md:181](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:181) | 6/6 | IDENTICAL |
| 5 | [WP-29-scope-decision.md:227](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:227) | 4/4 | IDENTICAL |

因此，“命令声明面与实际输出面不一致”这一 B57 已闭合。但以后仍须另外验证排除项不会改变答案，不能把“过滤已声明”当成充分条件。

本例中该附加条件实际满足：宽口径为 `219 → 排除自指后 97 → 再排除二签后 96`。自指占 122 行；二签文件只移除一行，即 `WP-28-consult-codex-shape-verdict.json:6` 的 INV-N3 引用。交付物又在 [WP-29-scope-decision.md:214](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:214) 将其按行号归入 C 类。因此过滤未改变 C1 的答案。

2. **Q2：替代方案在语义上等效，但执行者无权用它替换冻结验收条件，这是第一个阻断项。**

冻结 brief 明确要求：

- [WP-29-brief-rev4.md:127](/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-29-brief-rev4.md:127)：两处都逐字完整粘贴长 JSON 行。
- [WP-29-brief-rev4.md:131](/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-29-brief-rev4.md:131)：证据缺陷不得以“结论不受影响”豁免。
- [WP-29-brief-rev4.md:253](/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-29-brief-rev4.md:253)：Acceptance test 再次要求该长行在两处完整出现。

交付物却在 [WP-29-scope-decision.md:39](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:39)、[WP-29-scope-decision.md:83](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:83) 和差集命令中排除了该文件。

该行缺席确实**没有改变 C1 答案**；问题不是事实错误，而是冻结输入被执行者和第一签名事后改判。B59 可以作为下一版 brief 的改进理由，但不能追溯性地豁免 rev4。要采用替代方案，应先 re-freeze；否则必须按当前 brief 粘贴该行。

3. **Q3：B58 仍有残留；仅核验 `type` 不足，判据应携带执行面声明。**

本次成功环境是：

```text
grep = /usr/bin/grep
grep version = BSD grep 2.6.0-FreeBSD
cwd = /Users/admin/vibe/wp29-render-scope-decision
LC_ALL = C
shell = zsh（第三块依赖 process substitution）
```

交付物写的是裸 `grep`，第三块还依赖 shell 的 `<(...)`。`type grep` 只能发现当前环境被污染，不能让另一环境复现相同语义；它也没有固定 locale、cwd、shell、实现版本及 `grep -r` 的遍历顺序。

正确修法是执行面声明，至少固定：

```bash
cd /Users/admin/vibe/wp29-render-scope-decision
export LC_ALL=C
# 使用 zsh 或 bash 执行 process substitution
/usr/bin/grep ...
```

如果要求逐行完全一致，主 grep 还应显式排序；否则只能稳定承诺集合或行数相同，不能跨环境承诺输出顺序相同。

4. **Q4：当前事实很可能成立，但交付物的机械证据不足以支撑现有量词，这是第二个阻断项。**

[WP-29-scope-decision.md:222](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:222) 的命令只搜索 `_resources_files` 这个单一标识符。它能证明该别名只在 `load_template` 调用一次，却不能排除：

- `importlib.resources` 的其他别名；
- `pkgutil.get_data` / `pkg_resources`；
- `importlib.import_module` / `__import__`；
- 其他直接文件读取路径。

文档虽然在 [WP-29-scope-decision.md:249](/Users/admin/vibe/wp29-render-scope-decision/docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md:249) 手工申报了 `cli.py`，但没有给出可复现的同族入口穷举命令。冻结 brief 在 [WP-29-brief-rev4.md:166](/Users/admin/vibe/agentic_loop/docs/plans/2026-09-13-parallel-throughput/WP-29-brief-rev4.md:166) 明确要求搜索面足以支撑“只有一处”，否则降级量词。

我的宽搜索只找到：

```text
src/agentic_loop/contract_render.py:19  importlib.resources.files
src/agentic_loop/cli.py:25             importlib.resources
src/agentic_loop/cli.py:139            _resources.path(...)
```

未发现 `pkgutil.get_data`、`pkg_resources`、`import_module` 或 `__import__`。所以当前结论没有被反例推翻，但这些证据尚未进入交付物。应当二选一：

- 把结论收窄为“`_resources_files` 这一别名在 `src/` 中仅于 `load_template` 调用”；或
- 粘贴覆盖同族资源 API/动态导入形态的完整搜索，并明确其语法边界。

可重跑核心命令：

```bash
# 五块分别重跑；输出为 38、46、17、6、4
/usr/bin/grep -rn --exclude-dir=.git --exclude-dir=__pycache__ \
  --exclude-dir=.pytest_cache --exclude=WP-29-scope-decision.md \
  --exclude=WP-28-consult-codex-shape-verdict.json \
  'WORK_PACKAGE\.md\.tmpl' . | wc -l

/usr/bin/grep -rn --exclude-dir=.git --exclude-dir=__pycache__ \
  --exclude-dir=.pytest_cache --exclude=WP-29-scope-decision.md \
  --exclude=WP-28-consult-codex-shape-verdict.json \
  'docs/agentic/templates/WORK_PACKAGE\.md' . | wc -l

comm -23 \
  <(/usr/bin/grep -rn --exclude-dir=.git --exclude-dir=__pycache__ \
    --exclude-dir=.pytest_cache --exclude=WP-29-scope-decision.md \
    --exclude=WP-28-consult-codex-shape-verdict.json 'WORK_PACKAGE' . | sort) \
  <(/usr/bin/grep -rn --exclude-dir=.git --exclude-dir=__pycache__ \
    --exclude-dir=.pytest_cache --exclude=WP-29-scope-decision.md \
    --exclude=WP-28-consult-codex-shape-verdict.json \
    -e 'WORK_PACKAGE\.md\.tmpl' \
    -e 'docs/agentic/templates/WORK_PACKAGE\.md' . | sort -u) | wc -l

/usr/bin/grep -rn --exclude-dir=__pycache__ 'load_template' src tests | wc -l
/usr/bin/grep -rn --exclude-dir=__pycache__ '_resources_files' src | wc -l

# 同族资源入口复核
rg -n --glob '*.py' \
  '(from importlib(\.resources)? import|import importlib(\.resources)?|pkgutil\.get_data|pkg_resources|__import__\(|import_module\(|resources\.(files|path|open_text|open_binary|read_text|read_binary))' \
  src
```

未评判或改动 §5 的 (c′) 裁定；工作区保持只读。

[exited with code 0]

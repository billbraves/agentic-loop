# WP-22 rev2: 关掉 finalize probe 的字段注入面（B15）与写回段的按路径重读（B13）

> 冻结日期 2026-09-16 | 编排者 claude（claude-code） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> **本文是 rev2**：rev1 交付（`2fbf05d`）已被 codex 第二签名判 REWORK，编排者据其提示
> 写出 PoC 证实并加重定级。冻结后执行期间不得修改；需修订走 re-freeze（新建 rev3 并重派）。

## 目标（一句话）

rev1 把「判定与读取」正确收敛到同一次 `O_NOFOLLOW` open（A34 已关），但**新引入的
probe→bash 传输协议可被字段内容注入**，使合入门禁可被绕过（B15）；本轮把传输改成
无歧义编码 + 字段名白名单，并顺带让写回段读的旧 JSON 也来自那一次 open（B13）。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

### B15：注入可绕过合入检测（**已有可复现 PoC**）

`finalize_merge.sh` 的 probe 把 20 个字段以 `key<TAB>value` 单行文本交回 bash，
消费端在 `:204-206`：

```bash
while IFS=$'\t' read -r probe_key probe_value; do
  [[ -n "$probe_key" ]] && printf -v "$probe_key" '%s' "$probe_value"
done <<< "$probe_fields"
```

`render()`（`:102-108`）对字符串是 `str(value)` 原样返回，**不转义换行**。因此任何
字符串字段内容里的换行都会被 `read` 解析成新的一行 `key<TAB>value`，成为一次
`printf -v` 赋值。又因 `OPTIONAL_FIELDS` 在 `REQUIRED_FIELDS`**之后**发出
（`:158-171`），注入行可以**覆盖先前已正确读出的任一变量**。

`validate()` 不约束这些字符串的内容（`validate_wp_status.py:207-208` 只要求
`justification` 是非空 str），所以注入载荷可以完全合法地通过 schema 校验。

**PoC（真脚本调用，两次干净 fixture 复现）**：`consult.override.justification` 写

```
looks fine\nbranch\tfeature/decoy
```

构造 `git.branch = feature/real`（**从未合入 base**）、`feature/decoy`（已合入）。
`validate()` 全绿；真脚本输出：

```
FINALIZE_OK merged_commit=d38fd875...     rc=0     state -> MERGED
```

而 `git merge-base --is-ancestor feature/real main` 为**假**。合入检测
（`:282`）被绕过，因为它检查的是被覆盖后的 `feature/decoy`。

**这是 rev1 引入的回归**：派发点 `b72e9c4` 的旧版对**同一份 status** 拒收——

```
FINALIZE_FAIL: merge not detected (branch tip c1612103... is not an ancestor of base c5e5b55e...)
```

旧版每字段一次 `field` 子进程 + 命令替换赋给单个变量，换行是惰性的。
rev1 把「一次调用一个值」换成「一段文本多行赋值」，换行由此获得语法意义。

### B13：写回段仍按路径重读

`:325-348` 的写回段（rev1 按 Brief 明令零改动）里 `:328` 仍是
`with open(src, encoding="utf-8") as fh:`，即**再次按路径解析**并读旧 JSON。
写回**落点**已证免疫（`mktemp "$status_file.XXXXXX"` 取路径串的 dirname、不解析
symlink；`mv` 是 `rename(2)`，替换 symlink 本身而非其目标），但写回**读到的旧
JSON 的新鲜度未证**。本条目前登记为**缺陷、非已证漏洞**（无 PoC）——不得在报告里
把它说成已证漏洞。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `tests/test_finalize_merge_toctou.py`
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/validate_wp_status.py`（**判据唯一权威，零改动**；
    不得靠收紧 schema 去堵注入——那是把传输缺陷推给校验层）
  - `src/agentic_loop/gate/__init__.py`、`src/agentic_loop/independence.py`
  - `src/agentic_loop/wrappers/` 下其余全部 `.sh`
  - `src/agentic_loop/adapters/`、`src/agentic_loop/redispatch.py`
  - `docs/`（含本 brief 自身）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ **方向不可反**：修的是 probe→bash 的**传输**，不是 schema。
> 在 `validate_wp_status.py` 里禁掉 justification 含换行是错解：注入面在通道，
> 换一个不受 schema 约束的字段仍可复现。

## 交付物清单

- [ ] **传输改无歧义编码**。probe 与 bash 之间不再用「换行分记录 + TAB 分字段」的
      文本协议。可选形态（择一，理由写进报告）：
      - NUL 分隔 + `read -r -d ''`；
      - probe 输出 JSON，bash 侧走**单点**解析（同一个 python 调用批量取值）。
      判据：**任何字段值都不能改变记录边界**。
- [ ] **赋值端字段名白名单**。只接受 `REQUIRED_FIELDS` / `OPTIONAL_FIELDS` 里声明的
      变量名；任何其他 key 一律拒绝并 fail-closed（不是忽略）。
- [ ] **B13：写回读的旧 JSON 来自 probe 那一次 `open()`**。把 probe 已读到的 `raw`
      传给写回段（如经 `$tmp` 文件或 stdin），写回段不再 `open(src)`。
      落点已免疫、维持 `mktemp`+`mv` 的原子写不变。
- [ ] `tests/test_finalize_merge_toctou.py` 增补用例，**每条自带 oracle 三项**。

## 完成定义（DoD）

- [ ] **B15 回归用例**：把编排者的 PoC 固化为用例——
      - **负向**：`consult.override.justification` 含 `\nbranch\t<已合入的分支>`，
        `git.branch` 指向**未合入** base 的分支 → 必须 `FINALIZE_FAIL`、
        `rc != 0`、**`FINALIZE_OK` 不出现**、status 的 `state` 仍是
        `APPROVED_FOR_MERGE`、`git.merged_commit` 不存在。
      - **原因特异 witness**：断言拒收原因来自**合入检测或白名单拒绝**，
        不是「碰巧别处挂了」。给出你所依赖的那句诊断的 `file:line`。
      - **正向可达性对照（同 fixture）**：把 justification 换成不含换行的等价文本，
        其余全同 → 必须 `FINALIZE_OK` 且 `merged_commit` 等于真实 merge commit。
        这一项证明 fixture 本身能过全部门禁，负向那次不是死在别处。
      - **代表性禁止变异转红**：把你的白名单/编码守卫**临时**摘掉一处 →
        该用例必须转红（复现 `FINALIZE_OK` + 伪 MERGED）；随后还原到
        **零行 diff**（`git status` 干净），并把摘除形态与观测结果写进报告。
- [ ] **注入面不止 justification**：再取**一个**不同的字符串字段（如
      `qoder_security.override.approver` 或 `iteration_id`）做同形态负向用例，
      证明修的是通道而非某个字段。
- [ ] rev1 已有的 5 条用例**全部照旧通过**（A34 不得回退）。
- [ ] **跨版本**：新旧用例在 **python3.11、3.13、3.14** 三个解释器全绿
      （缺 pytest 的用 `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`）。
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线**零回归**。
      基线（编排者在 `dispatch_commit` 的 detached worktree 实测，见 status
      `evidence.baseline`）：`4 failed, 581 passed, 4 skipped`。那 4 个
      `tests/test_finalize_merge_triple_sign.py` 预存失败**不要修**。
- [ ] `validate_wp_status.py` diff **必须为 0 行**。
- [ ] 按缺陷 B7/B14：**直接跑工作树代码**（`PYTHONPATH=src bash src/...`），
      **不要**用 `agentic <sub>` 自证——本机 `agentic` 是指向**另一棵 worktree** 的
      editable 安装，判的是别人的代码。
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 不 merge、不 push、不切生产分支
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要改 schema 去堵注入**。`validate_wp_status.py` 零改动。注入面在传输通道，
   收紧某个字段的 schema 只是把同一个洞挪到别的字段。
2. **`printf -v` 的变量名来自数据 = 任意变量覆盖**。即使改了记录分隔符，只要 key
   仍来自数据且不过白名单，就仍可覆盖 `branch` / `consult_decision` 等判据变量。
   两件事要同时做：**无歧义编码**（管边界）+ **白名单**（管 key）。
3. **`set -euo pipefail` 下的读取一律要守卫**（缺陷 A12 的来历）。
   `git.merged_commit` 在首次 finalize 时不存在，必须解析为空而非中止。
4. **A34 不得回退**。判定与读取仍须收敛在同一次 `O_NOFOLLOW` open 上；
   `O_NOFOLLOW` 只拒最后一段是 symlink，中间目录段被替换仍是残余面，本轮不修，
   在 `[CONCERNS]` 申报即可。
5. **负面断言须给出打印点**。凡断言「报了某句话」，在报告里写出该句的
   `file:line`；若权威脚本对两种成因打印**同一句**，改用**差分对**证明
   （其余恒定、只改一个输入，断言红/绿翻转），不要断言无法区分的措辞。
   这是编排者缺陷 B11 的教训，本轮起对执行者同样适用。
6. **变异自证要还原干净**。摘守卫→看转红→还原，最终 diff 必须零行。

### 口径权威源引用

- status 校验判据：`src/agentic_loop/validate_wp_status.py` 的 `validate()`（唯一权威，本轮只读）
- `--field` 渲染语义：`validate_wp_status.main()`（唯一权威，probe 须与之同义）
- worktree 判定：`src/agentic_loop/gate/path_is_in_worktree`（唯一权威，不另造）
- B15 / B13 / B11 详情：`WP-08-candidate.md` 对应条目
- rev1 裁决：`WP-22-consult-codex-verdict.json`（codex REWORK + 编排者逐条核验）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/wrappers/finalize_merge.sh`
- `tests/test_finalize_merge_toctou.py`

**forbidden_paths**

- `src/agentic_loop/validate_wp_status.py` — the authoritative predicate;
  **zero-line diff**. Never tighten the schema to block the injection: the
  defect is in the transport channel, and another unconstrained string field
  reproduces it
- `src/agentic_loop/gate/__init__.py`, `src/agentic_loop/independence.py`
- every other `.sh` under `src/agentic_loop/wrappers/`
- `src/agentic_loop/adapters/`, `src/agentic_loop/redispatch.py`
- `docs/` — briefs and status files are orchestrator-maintained (including this brief)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** self-certify with `agentic <sub>` (defects B7/B14: the installed CLI
is an editable install pointing at a different worktree).

- `tests/test_finalize_merge_toctou.py` — B15 regression, each case carrying the
  oracle three items:
  - **negative**: `consult.override.justification` containing
    `\nbranch\t<a merged branch>` while `git.branch` names a branch **not**
    merged into base must yield `FINALIZE_FAIL`, `rc != 0`, no `FINALIZE_OK`,
    `state` still `APPROVED_FOR_MERGE`, and no `git.merged_commit`
  - **cause-specific witness**: assert the refusal comes from the merge check or
    the key whitelist, not from an incidental failure elsewhere; cite the
    `file:line` of the diagnostic you rely on
  - **positive reachability control** on the same fixture: the same status with a
    newline-free justification must reach `FINALIZE_OK` with the real merge commit
  - **representative forbidden mutation**: temporarily remove one of your
    whitelist/encoding guards; the case must go red (reproducing `FINALIZE_OK`
    plus a forged MERGED stamp), then restore to a **zero-line diff**
  - a second, different string field (e.g. `qoder_security.override.approver` or
    `iteration_id`) carrying the same payload shape, proving the fix is in the
    channel rather than in one field
- All 5 rev1 cases still pass (A34 must not regress).
- **Cross-version**: green under python3.11, 3.13 and 3.14.
- Whole suite: zero regression against the recorded baseline
  (`4 failed, 581 passed, 4 skipped` at `dispatch_commit`). The 4 pre-existing
  `tests/test_finalize_merge_triple_sign.py` failures stay — **do not fix them**.
- Every negative assertion must name the `file:line` that prints the message it
  expects. When the authoritative script prints the **same** message for two
  distinct causes, use a differential pair instead (hold everything constant,
  change only the one input, assert redness flips) — never assert on a message
  that cannot discriminate. This is the lesson of orchestrator defect B11.

## Completion definition

- [ ] Transport uses an unambiguous encoding: no field value can change a record
      boundary
- [ ] The assigning side whitelists variable names; any other key fails closed
- [ ] The writeback reads the old JSON from the probe's single `open()`, not by
      path; the atomic `mktemp` + `mv` landing stays unchanged
- [ ] B15 regression cases in place with all four oracle items, plus a second
      field proving the fix is channel-wide
- [ ] All 5 rev1 cases still pass; A34 not regressed
- [ ] All three interpreters (3.11, 3.13, 3.14) green
- [ ] Zero regression relative to the recorded baseline
- [ ] `validate_wp_status.py` diff is **zero lines**
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] Commit message follows the repository convention

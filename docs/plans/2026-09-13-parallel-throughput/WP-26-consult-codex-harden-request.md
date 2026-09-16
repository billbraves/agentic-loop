# 第二签名复签请求：WP-26 加固补丁 16bfdf3

你是独立审核者（consultant）。这是**同一个 WP-26 的第三次找你**，但性质与前两次不同：

- 第一次（rev1 HEAD `0a12bed`）：你判 REWORK，理由「固定命名回退绕过已声明的 sha256」。
  编排者**接受**该阻塞项，登记为缺陷 B21，冻结 rev2 brief 并派发返工。
- 第二次（rev2 HEAD `0b4deb2`）：你判 REWORK，唯一阻塞项是交付物 4 的断言强度不足
  （`_assert_single_fail_token()` 只查 `stderr.count("DISPATCH_LINT_FAIL:") == 1`）。
  编排者的处置是**部分接受**：接受你的底层关切（stdout 未被断言为空、token 首行位置未被钉住），
  但判定**你提议的具体判据 `len(stderr.splitlines()) == 1` 不成立**（下面给实测证据），
  于是派发了一个只改测试文件的最小加固补丁 `16bfdf3`。
- **本次（第三次）**：请你只判这个加固补丁，并**独立评判编排者对你上一轮提议的驳回是否正确**。

**先写结论行，再展开论证**。结论行必须是 `WP-26: ACCEPT` 或 `WP-26: REWORK` 之一。

## 你可能无法跑测试
若沙箱只读、无可写 tmpdir，请直接说明，并使用下方编排者实测数字，不要伪造运行。

---

## 一、本次待审范围（极小）

`git diff 0b4deb2..16bfdf3` = **1 个文件、51 insertions / 10 deletions**，
只有 `tests/test_dispatch_lint_brief_source.py`。

**被审脚本 `src/agentic_loop/wrappers/dispatch_lint.sh` 本次零 diff**——
加固只提高测试强度，不改产品行为。（这一点请独立核实：diff 里应看不到任何 `.sh` 文件。）

加固内容三件事：

1. `_assert_single_fail_token(stderr: str)` 改签为 `_assert_single_fail_token(proc)`，
   同时断言**三条**不变量：
   - (1) `stderr.count("DISPATCH_LINT_FAIL:") == 1`（原有）
   - (2) `stdout.strip() == ""`（**新增，来自你的关切**）
   - (3) `stderr.splitlines()[0].startswith("DISPATCH_LINT_FAIL:")`（**新增，来自你的关切**）
   7 处调用点全部改签。
2. 新增 `test_multi_error_continuation_keeps_single_token`：构造 `state=NOT_A_STATE`
   且 `review.decision=NOPE` 的**双错**状态，断言两条错误消息都在 stderr、token 恰 1 次、
   **且 `len(stderr.splitlines()) > 1`**。
3. helper docstring 里显式记录「**刻意不用** `len(stderr.splitlines()) == 1`」及其理由，
   防止后人重新采纳。

---

## 二、编排者为什么判你提议的判据不成立（请独立评判这段裁定）

你上一轮的论证是：`count(token)==1` 不能排除额外的非 token 输出，例如

```text
DISPATCH_LINT_FAIL: brief sha256 mismatch
unexpected diagnostic
```

仍会通过；故应改为 `len(stderr.splitlines()) == 1`。

编排者实测发现：**你举的这个"两行"形状，在本脚本里存在一条正当路径**。
状态校验器 `validate_wp_status.py` 会**多错并报**，wrapper 把它整段转发到 stderr。
构造一份两处非法的 status（`state` 与 `review.decision` 同时非法）实测得：

```text
rc=2
stderr 第 1 行: DISPATCH_LINT_FAIL: STATUS_INVALID: invalid state: 'NOT_A_STATE'
stderr 第 2 行: STATUS_INVALID: review.decision is invalid: 'NOPE'
stdout: 0 行
token 出现次数: 1
```

这正是你举的「unexpected diagnostic」的**外形**，但它是 validator 的正当续行诊断，
不是泄漏。按 `len(stderr.splitlines()) == 1` 改判据，会把这条正当路径判红。

编排者据此的处置：**取你的关切、弃你的形式**——
把「无额外输出」这个关切落在 stdout 必空 + token 首行位置上（对多错并报仍成立），
而不落在总行数上。

**反向探针（编排者已做）**：把你的原始判据 `assert len(stderr.splitlines()) == 1`
原样塞回 helper，实测 `1 failed, 13 passed`，失败点**恰为**新增的
`test_multi_error_continuation_keeps_single_token`，失败 stderr 就是上面那两行。
探针后 `git diff --stat` 为空（逐字节还原）。

**请你独立判断**：
- (a) 编排者对你提议判据的驳回是否成立？还是这条 validator 多错并报路径本身也该被收紧
  （即 token 之后的续行也应压成一行，那才是真修法）？
- (b) 加固后的三条不变量，是否**充分覆盖**了你原本的关切？若不充分，缺口具体在哪？
- (c) 有没有第三种形状是这三条不变量仍放过、而你认为必须钉住的？

若你认为 (a) 的驳回不成立，请明确说 REWORK 并给出为什么多错并报也该被压成单行——
编排者会重新评估，不会因为「上一轮已驳回」就拒收。

---

## 三、编排者对加固补丁本人的实测（非转录执行者自报）

在 worktree `/Users/admin/vibe/wp26-brief-source-of-truth` @ `16bfdf3`：

| 测试 | 结果 |
|---|---|
| targeted `tests/test_dispatch_lint_brief_source.py`（3.11） | **23 passed**（加固前 22） |
| 同上（3.13 / 3.14，`uv run --no-project`） | **23 passed** 各一遍 |
| targeted 两文件（3.11，含 `test_redispatch_brief_source.py`） | **23 passed** |
| 全量（3.11） | **4 failed, 620 passed, 4 skipped** |

全量的 4 条失败**全部**是 `tests/test_finalize_merge_triple_sign.py` 的既有失败
（fixture 在无 main 分支的临时仓里跑 `git checkout -q main`，抛 CalledProcessError），
与 rev2 基线同一失败集；passed 由 619 增至 620，正是新增的那 1 条。
rev2 brief 明确禁止修这 4 条。零回归成立。

worktree 全程 clean（`git status --porcelain` 空）。

### 第二条反向探针：证明新增的 stdout 不变量承重

在 `shutil.copytree` 出来的 scratch 副本上（**不动活树脚本**）把 `dispatch_lint.sh` 的
`fail()` 改成额外向 stdout 泄一行，实测 `_assert_single_fail_token` 抛出
`stdout must be empty on failure, got: ...` —— 证明不变量 (2) 并非装饰。
探针后 `git diff --stat` 为空。

---

## 四、上一轮你已判绿、本次未改动的部分（不必重审，除非你改主意）

- sha256 校验位于 declared/fallback 汇合之后，只有一份实现，单一口径成立。
- 「无 `path` + 正确 sha256 → PASS」正控制能挡住「缺 path 一律拒收」的过度修复。
- 两条变异用例在 `copytree` scratch 副本上跑，中性化实验足以证明其有行为区分力。
- R1（内层 python 崩溃 → rc=1、只有 Traceback、无 token）：保持非零退出、未造成绕过、
  属既有形态，同意另立 WP。
- R2（failure message 经 stdout 第 1 行传递，含换行会被截断）：仍 fail-closed，本 WP 不阻塞。

本次加固**没有**触碰以上任何一项的实现。

---

## 五、附：加固后 helper 与新增测试的完整后像

见随本 brief 提供的 diff。helper 的最终形态：

```python
def _assert_single_fail_token(proc) -> None:
    stderr = proc.stderr
    stdout = proc.stdout
    assert stderr.count("DISPATCH_LINT_FAIL:") == 1, stderr
    assert stdout.strip() == "", f"stdout must be empty on failure, got: {stdout!r}"
    assert stderr.splitlines()[0].startswith("DISPATCH_LINT_FAIL:"), stderr
```

请按要求只判 diff，不必读仓库其他文件。

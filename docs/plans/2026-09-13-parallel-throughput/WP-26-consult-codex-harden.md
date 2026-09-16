# WP-26 加固补丁 16bfdf3 的 codex 第二签名（复签，第 3 次）

> consultant: codex (adapter=codex, provider=kirogpt, identity_model=gpt-5.6-sol)
> 判定对象：`git diff 0b4deb2..16bfdf3`（仅 tests/test_dispatch_lint_brief_source.py，51+/10-）
> 请求 brief：`wp26-harden-brief.md`（明确请其独立评判编排者上一轮的驳回）
> `--output-schema` 解析失败（该 provider 的软约束，见 WP-21 记录），以下为**原文逐字**留痕。
> 结论：**REWORK**

---

WP-26: REWORK

编排者对上一轮具体判据的驳回成立，但替代断言仍未完整覆盖原始关切。

(a) `len(stderr.splitlines()) == 1` 不应作为所有失败路径的统一约束。validator 合法地多错并报，保留后续 `STATUS_INVALID:` 诊断比强制压成一行更合理。所给反向探针也足以证明全局单行断言会误伤正当路径。

(b) 新增三条不变量不充分。以下输出仍会全部通过 helper：

```text
DISPATCH_LINT_FAIL: brief sha256 mismatch
unexpected diagnostic
```

因为 token 恰好一次、位于 stderr 首行，且 stdout 为空。也就是说，上一轮指出的“任意非 token 续行未受约束”仍然存在；新增双错测试证明了某些续行合法，却没有区分合法续行与意外泄漏。

此外，`stdout.strip() == ""` 并不等价于 stdout 为空。它会放过 `" "`, `"\n"` 等纯空白输出，与 docstring 声明的“stdout is empty”及实测表中的“stdout: 0 行”不一致。应断言：

```python
assert proc.stdout == ""
```

(c) 必须钉住的第三种形状包括任意额外 stderr 续行，以及纯空白 stdout。建议作最小、仅测试侧返工：

- 普通失败用例要求 stderr 只有 token 首行。
- validator 多错用例单独允许并精确断言预期的两条诊断，至少验证续行数量和内容，不要开放任意续行。
- stdout 改为逐字节空字符串断言。

本次 diff 确实只涉及测试文件，不改变产品行为；给出的测试结果也没有显示实现回归。但这是测试加固补丁，其核心目标正是收紧输出契约，上述缺口因此属于合并前必须修复的有界缺陷。

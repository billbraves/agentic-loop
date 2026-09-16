# WP-26 rev3 `57cd572` 的 codex 第二签名

> consultant: codex (adapter=codex, provider=kirogpt, identity_model=gpt-5.6-sol)
> 判定对象：`58c7624..57cd572`（累计，4 文件 +1112/-7）+ `16bfdf3..57cd572`（本轮增量，仅测试文件 +195/-16）
> 请求 brief：`wp26-brief.md`（前史 + 编排者实测数字 + 需重点评判的具体问题）
> `--output-schema` 解析失败（该 provider 的软约束，见 WP-21 记录），以下为**原文逐字**留痕。
> 结论：**REWORK**

---

WP-26: REWORK

C1、C2 已关闭，本轮增量也确实只修改了 `tests/test_dispatch_lint_brief_source.py`，没有 `.sh` 或实现 `.py` 改动。但累计 diff 中仍有一项 brief 完整性缺陷需要在合并前修复。

阻塞项：

- `redispatch._brief_content()` 先用 `read_text()`取得将要派发的内容，随后再次用 `read_bytes()`计算 sha256。若文件在两次读取之间变化，校验的是第二份内容，返回并派发的却是第一份内容。因此“sha256 锚定实际派发 Brief”并未严格成立。
- 应只读取一次字节，例如 `raw = brief_path.read_bytes()`，对 `raw` 计算 sha256，并从同一个 `raw` 解码出返回内容。这样校验对象与实际派发对象才是同一份快照。建议同时把解码失败规范化为 `BriefIntegrityError`。

对 rev3 重点项的独立结论：

- C1 已关闭。普通路径精确要求 `lines[1:] == ()`；多错路径精确声明 continuation tuple，任意附加、缺失或内容变化都会失败。
- 空 `stderr` 不会触发 `lines[0]` 的 `IndexError`：前面的 `stderr.count(...) == 1` 会先以 `AssertionError` 失败，属于 fail-closed。
- C2 已关闭。`stdout == ""` 会拒绝空格、换行、JSON 以及任何其他非空内容。
- 三条 constructed-proc 测试适合作为 helper 单元测试；真实 subprocess 失败用例普遍调用同一 helper，continuation mutation 又证明了真实脚本输出与断言之间的连接，因此不只是同义反复。
- 三条逃逸测试不存在“其他断言先失败”的假绿：它们分别满足目标断言之前的全部条件，静态执行顺序能够把失败原因定位到 continuation 或 stdout 精确断言。
- 字面替换若因 `fail()` 重排而找不到目标，会在 `mutated != original_text` 处明确失败，属于可接受的 fail-closed 测试维护信号。
- 固定 `DISPATCH_LINT_SHA256` 确实会锁定整个脚本实现，`live_before` 与结束时逐字节自比已经足以证明活树未被变异。建议移除固定常量，但在本次冻结 brief 明确要求该变更闸门的前提下，我不把它单独列为阻塞项。

受“仅使用内联 Brief 与 diff”限制，我没有读取仓库或自行运行测试；测试判断采用了 brief 中编排者实测的 `20 passed` 和全量基线数据。

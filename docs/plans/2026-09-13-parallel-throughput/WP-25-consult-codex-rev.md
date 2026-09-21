# WP-25 rev2 `284e223` 的 codex 第二签名

> consultant: codex (adapter=codex, provider=kirogpt, identity_model=gpt-5.6-sol)
> 判定对象：`58c7624..284e223`（累计，3 文件 +275/-2）+ `359cb1a..284e223`（本轮增量，仅测试文件 +103/-12）
> 请求 brief：`wp25-brief.md`（前史 + 编排者实测数字 + 需重点评判的具体问题）
> `--output-schema` 解析失败（该 provider 的软约束，见 WP-21 记录），以下为**原文逐字**留痕。
> 结论：**REWORK**

---

WP-25: REWORK

阻塞项有两个，均可由所给代码直接确认，无需运行测试。

1. **B27 应升级为阻塞项。**  
   `DISCIPLINE_ANCHORS` 虽然是短语级，但新增守卫通过 `_EVISCERATION_2_RE` 和 `_EVISCERATION_3_RE` 间接锁定了整段周边措辞。编排者的探针已经证明：只改写非锚点措辞、保留全部语义锚点，测试仍会因 `evisceration produced no change` 失败。  
   `fail-closed` 只能证明它不会静默空过，不能消除这种错误拒绝；它实质上重新引入了 B10 所禁止的措辞耦合。应将变异构造改为锚点驱动或直接对内存文本操作，不依赖固定句首、标点和从句边界。

2. **守卫修改活树文件，不满足并行测试隔离。**  
   `try/finally` 能处理正常异常及通常的 `KeyboardInterrupt` 栈展开，但无法隔离 `pytest -n` 下的其他 worker。模板处于 `text2` 或 `text3` 状态时，其他锚点测试、渲染测试可能同时读取它并产生偶发失败。进程被 `SIGKILL`、解释器崩溃，或恢复写入本身失败时，也可能留下被污染的 tracked 文件。  
   建议完全取消 `CLAUDE_TMPL.write_text/write_bytes`：直接对 `text2`、`text3` 调用 `_assert_discipline_anchors` 即可验证同一断言路径；若必须验证文件读取面，应使用独立临时副本并注入路径。

另外存在一个明确的语义空过形状：存在性锚点无法检测语义反转。例如：

```text
use a differential pair instead: do not flip exactly one input,
and do not require the verdict to flip with it.
```

它保留 `differential pair`、`flip exactly one input` 和 `flip with it`，现有锚点测试全绿；现有 evisceration 正则仍可匹配并让守卫按预期“变红”，因此守卫本身也会通过，但纪律已经表达了相反规则。`read_face_pinning` 同样可以用“`-revN` 后 consumer channel 不必跟随”保留全部锚点而反转语义。应增加至少一组语义反转 mutation，或使用能约束肯定性动作关系的短句/结构判据。

关于 `pytest.raises(AssertionError)`：当前上下文中没有发现 B19 式假绿路径。作用域内只有 `_assert_discipline_anchors` 会主动抛出 `AssertionError`，随后又检查了具体缺失短语，原因特异性足够。

版本号方面，累计 diff 已同时修改 `CONTRACT_TEMPLATE_VERSION` 并断言其为 `"7"`；仅凭所给 diff，没有足够证据把版本一致性判据定为新的阻塞项。

我未运行测试：审查范围明确限定为 inline brief/diff，且当前沙箱只读。测试结果采用编排者提供的 `39 passed` 与基线一致性数据；上述 REWORK 结论来自代码结构，可静态确认。

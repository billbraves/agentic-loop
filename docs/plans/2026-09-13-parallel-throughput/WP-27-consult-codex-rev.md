# WP-27 rev2 `90fc603` 的 codex 第二签名

> consultant: codex (adapter=codex, provider=kirogpt, identity_model=gpt-5.6-sol)
> 判定对象：`58c7624..90fc603`（累计，2 文件 +737/-2）+ `a3264c0..90fc603`（本轮增量，仅测试文件 +249/-9）
> 请求 brief：`wp27-brief.md`（前史 + 编排者实测数字 + 需重点评判的具体问题）
> `--output-schema` 解析失败（该 provider 的软约束，见 WP-21 记录），以下为**原文逐字**留痕。
> 结论：**ACCEPT**

---

WP-27: ACCEPT

本轮增量仅修改 `tests/test_preflight_status_source.py`，未改动 `preflight.sh`。rev2 已补齐上一轮缺失的反向差分证明，满足 Brief。

- (a) 两条新用例真正约束了主仓紧值：主仓分别设置拒收值、工作树保持可通过，且错误信息精确命中对应 witness；随后仅翻转主仓目标字段便 PASS。删除 `dispatch_lint.sh` 调用后两个场景分别转为 PASS，也直接排除了“完全短路 scope/risk 判定”这一实际变异。除针对 fixture、dirty 状态或错误文本硬编码的对抗性实现外，没有合理的第三种错误实现能通过这些约束。
- (b) `_rewrite_main_status` 确实让主仓变 dirty，但实测正向对照仍 PASS，说明 dirty 没有引入额外拒收原因。它也不是这类安全门禁会合理采用的“绕过 lint”条件；累计 diff 未增加此类控制流。因此这是轻微测试变量差异，不构成 B19 式原因遮蔽或阻塞项。
- (c) 当前内容定位对现有平坦代码块有效。若未来加入嵌套 `if`，定位可能停在内层 `fi`，留下孤立的外层 `fi`，脚本将非零退出；而变异分支明确要求 `returncode == 0`，所以会响亮失败，不会静默假绿。可维护性一般，但 fail-closed。
- (d) 保留镜像用例合理。它证明“工作树中的坏 scope/risk 不会污染裁决”；两条新用例证明“主仓中的紧值会绑定”。两者方向互补，并非完全包含。降级后的 docstring 已准确限定其证明力。
- (e) 只选择 `network_authorized` 作为 risk 代表不构成覆盖不足。WP-27 修复的是整个 status 路径的来源，而不是逐个验证 `dispatch_lint.sh` 的四个 risk 分支；四项均显式设定基线，并对一个代表字段完成了原因特异差分，足以覆盖本 WP 的回归面。
- 新增测试不依赖 B22 的 TOCTOU 窗口：所有改写和两次执行均为顺序操作，没有并发换值。B22 可继续作为独立缺陷处理。

当前沙箱只读，且审查范围明确禁止读取仓库其他文件，因此我未独立运行测试。判定采用编排者提供的实测证据：targeted 在 Python 3.11、3.13、3.14 均为 `9 passed`；全量新增通过数与三条新用例一致；独立活树摘除变异精确使两条新差分转红。

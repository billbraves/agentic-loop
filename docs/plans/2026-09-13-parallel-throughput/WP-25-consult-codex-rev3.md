# WP-25 rev3 第二签名（codex 独立复核）

> 咨询时点 2026-09-17 | consultant: codex (provider kirogpt, model `gpt-5.6-sol`)
> independence: **strong**（engine-observed models differ: consultant=gpt-5.6-sol vs reviewer=claude-opus-5）
> 审查面：**累计 diff** `58c7624..aa1e43b`（3 文件）+ rev3 冻结 brief + rev2→rev3 增量 diff
> 单程审查（输入 68700 字节，未触发 chunking）。原始判定逐字转录于下，未做任何改写。

```
REWORK

阻塞缺陷：块定位不是唯一定位，存在 B29 式“检查面 / 使用面分离”逃逸。

- `_cut_discipline_block()` 使用 `text.index(start)` 和随后第一个 `end`，却未断言边界标记唯一。若在真实纪律前插入一份冻结正文作为 decoy，再反转后面的实际纪律，逐字断言会读取 decoy 并保持 GREEN；全局 `DISCIPLINE_ANCHORS` 也仍 GREEN。这直接推翻了“给反转开绿灯必须修改测试中的冻结常量”这一核心保证。
- 当前 diff 中六个配置边界字符串看起来各自只有一个有效出现点；标题改名或普通内容插入通常会因切割失败或正文不等而 fail-closed。但实现没有把“唯一性”编码成不变量，未来重复标题或复制纪律时可能静默漂移。
- 可执行修法：切割前枚举 `start`、`end` 的全部位置，分别要求恰好一次，并校验三个块按预期顺序、不重叠。增加变异用例：在真实块前复制完整冻结块，然后反转真实块；断言因“边界不唯一”转红。该修法未实测。

另一个需要一并收口的语义逃逸：

- 起始标记排除了 Markdown 列表前缀 `- `，而 `_normalize = " ".join(text.split())` 又抹除了所有空白结构。因此删除 `- **Criteria sourcing.**` 或 `- Every negative assertion` 前的 `- `，逐字锁仍可 GREEN；加入空行和缩进、把部分规则变成 Markdown code block，也可能得到相同规范化文本。这不是纯折行，而是协议渲染结构变化。
- 可执行修法：将完整列表起始符纳入锁定，例如 `- **Criteria sourcing.**`、`- **Read-face pinning.**`、`- Every negative assertion`；同时保留当前正文空白归一化，但增加结构断言，拒绝块内新增空段、代码块或其他改变 Markdown 归属的格式。补充删除列表前缀的负面变异用例。该修法未实测。

其余审查结论：

- 三个切割区间确实覆盖 `may only`、`Never`、`must`、`cannot`、`require` 等承载极性的正文；在无重复标记的当前文本上，三类极性变异会转红。
- 区间边界在当前模板中紧贴相邻 bullet，没有明显吞入无关正文；冻结文本与展示的模板内容逐字一致，392/386/515 的顺序应理解为 criteria/negative/read-face。
- rev2 锚点基线断言被逐字等价蕴含，但 B20 变异用例仍单独证明旧锚点层可承载，因此属于 brief 明确要求保留的分层回归证据，不构成阻塞。
- 变异均作用于一次读取后传入判据的同一字符串，没有活树写入；普通路径下未发现新的读取面分离。
- 累计 diff 中模板和版本修改来自前两轮；rev3 增量只修改允许的测试文件，范围符合冻结说明。

本结论仅基于内联 brief 与累计 diff 的代码审查；未读取仓库其他文件，也未运行测试。```

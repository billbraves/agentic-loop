# WP-01 最终独立评审(编排者作为 reviewer,第二轮)

被审对象:`e670991`(全部 10 提交 `e23eb63..e670991`),brief rev15。
第一轮评审见 `WP-01-review.md`(判 CHANGES_REQUESTED,Finding 1)。
本轮评审方式:读增量全量 diff + 独立复跑 + **用 r9 指认的机理反向扫新测试本身**。

## 裁决

**ACCEPT** —— 建议进入实现二签,然后合入。

第一轮的阻断项 Finding 1 已闭合且**被变异证明承重**;r9-r12 追加指认的两条
假绿面已各自被新变异锁死;本轮新发现一条实现偏离(D6 环境继承)已修复并复验。

## 本轮独立核实为真

| 项 | 结果 |
|---|---|
| 全量套件 | **843 passed / 4 skipped / 0 failed**(基线 807;+31 矩阵,+5 增量) |
| 28 条具名变异 | **28/28 PASS**,每条具名承重实例转红、恢复后回绿 |
| 等价控制 M-B1`[kimi]` | 全程保持绿 |
| must-stay-green 七项 | 全绿(26 passed) |
| F8 闭合完整性 | 三条 raise(S4/S10/S11)、两个调用点、**两个 catcher**,文案与退出码一致 |
| canonical 锚点 | `# F8 legacy hand-off (M-B6a/M-B6b anchor)` 逐字落地,M-B6a/b 可机械施加 |
| `_stub_io` 开关 | `stub_resolver` 默认 True,既有调用点行为不变(843 中既有 838 全部仍绿) |
| D7 覆盖完整性 | 默认 registry **只有** kimi/claude 两 key,D7 参数化已**全覆盖**,无遗漏 key |
| D7 oracle 实质性 | 用 `object()` 哨兵断言 binding **身份**透传,非首选工厂构造计数断言为空 |
| 范围 | 仍只有 5 个 allowed 代码文件 + 本 WP 自己的 plan 产物 |

## 两条曾被证实的假绿面:现已关闭

本 WP 最值得记录的事实 —— 下列两处**各自单改一行**,在 D6/D7 存在之前
**保持全量 838 passed 全绿**(编排者逐条实测,每次单改 + 跑全量 + 还原):

| 单行改动 | 当时结果 | 现在锁定者 |
|---|---|---|
| 默认 registry `"kimi"` key 改构造 `ClaudeAdapter` —— **本 WP 要禁的静默换 adapter 本身** | 838 全绿 | **M-D7a** 使 D7`[kimi]` 转红 |
| 主路径 `probe=True` → `probe=False` —— **生产注入探针整体关闭** | 838 全绿 | **M-D6a** 使 D6`[main]` 转红 |

即「20/20 变异红证成立」与「两条一行即可击穿本 WP 目标的假绿」曾**同时为真**。
机理:矩阵只锁 resolver **内部**决策,而 `_stub_io()` 把 `_resolve_developer`
整体替换(且那 lambda 忽略 `repo`/`probe`)、所有 resolver 测试都注入自定义
registry —— 双双遮蔽了生产接线。这条教训比本 WP 修的原缺陷更有长期价值。

## 本轮新发现并已修复:D6 环境继承(非阻断,已闭合)

`test_main_resolver_call_contract[main]` 原先只在 legacy 分支 `setenv("PROBE_CMD")`,
`[main]` 分支**未显式清除**,于是继承环境变量走进 legacy 分支:

```
PROBE_CMD="echo PROBE_OK" pytest ...::test_main_resolver_call_contract -q
-> FAILED test_main_resolver_call_contract[main]    (1 failed, 1 passed)
```

违反 rev15 brief `:902` 冻结的「**显式清除或设置** `PROBE_CMD`(不得继承环境)」。
属**实现偏离冻结规格**(brief 已写明,实现只做了一半),已由 `e670991` 补
`monkeypatch.delenv("PROBE_CMD", raising=False)` 修复;污染环境下复验 2 passed,
干净环境全量仍 843。

> 这条本身就是「测试对环境不设防」的小型实例 —— 与 Finding 1、与两条假绿面
> 同属一个家族:**没有被显式钉住的前提,迟早会被环境或重写悄悄改掉**。

## 工具层发现:编排者自己的变异 harness 曾会伪造红证(已修)

r10 指出:harness 原先「`count()` 后 `replace(..., 1)`」,即接受多重匹配并改
**第一处**。canonical 块落地后 `except ProbeFailedError:` 在主/legacy 各一处,
M-B6a/M-B6b 会**改到主路径却声称在测 legacy**,B6 的 legacy 面不转红 —— 一条
凭空伪造的红证。已先修工具(模糊锚点一律 fail-closed + `occurrence` 精确定位),
复跑既有 20 条确认全部锚点唯一、20/20 仍 PASS,之后才继续。

修复的价值随即兑现:M-D7b 的锚点在 `redispatch.py` 内有两处匹配
(`:144` 默认 registry 是目标、`:275` flash 工厂不相干),**加固后的 harness
如实报 BLOCKED 而非伪造红证**;rev15 补 `occurrence=1` 后 28/28。

## 残余风险(如实记录,均不阻断)

1. **原生 kimi 路径未做凭证脱敏** —— 不知道原生 credential env 名,属另一 WP。
   该 detail 字符串按 F7 声明为 resolver 内部敏感值,由 C 族锁零外流。
   报告与本评审**均未声称**已脱敏(F7 明令)。
2. **生产面「来源可信的单跳 flash」端到端未验证** —— 测试全用 stub、不触网。
   D6/D7 锁住了接线与参数契约,但真实 kimi/flash 子进程行为不在本 WP 范围。
3. **F3 的配置事实** —— 生产权威(`main_repo()`)与被审 checkout 的
   `config.toml` 内容不同(主/fallback 相反),**不是解析器 bug**;
   checkout 内的断言只是该 checkout 的配置不变式,**不等于生产零回归**。
4. **shell-out-to-git 测试在并发 git 操作下会伪失败** —— 编排者实测一次
   273 errors 系自己并发 `checkout` 所致,串行复跑即 843/0。已记入报告。
5. **逐字变异纪律的脆性** —— 行为等价的重写会摧毁锚点可施加性(M-B3 与
   M-B6 已各重演一次)。rev15 用冻结 canonical 形态 + 定位注释缓解,
   但根治需改为 AST 匹配,属另一 WP。

## 二签台账

| 次 | 对象 | 裁决 | 必改项 |
|---|---|---|---|
| r7 | rev8 语义 | ACCEPT | 0 |
| r8 | rev9 模板兼容 delta | ACCEPT | 0 |
| r9 | rev10(F8/B6) | REWORK | 5(含两条假绿面指认) |
| r10 | rev11 | REWORK | 3(含 harness 伪造红证) |
| r11 | rev12 | REWORK | 3(attempt 1 因 consultant 配额 402 作废) |
| r12 | rev13 | REWORK | 4(措辞/格式残留) |
| r13 | rev14 | **ACCEPT** | 0 |

实现侧尚未二签 —— 建议在合入前就 `e670991` 的完整 diff 走一轮
implementation consult(本评审为编排者单签)。

# WP-01 独立评审(编排者作为 reviewer)

被审对象:`65b52cf`(实现 7 提交 `e23eb63..65b52cf`),brief rev9(双签 ACCEPT)。
评审方式:读全量 diff + 独立复跑测试与 20 条变异 + 对抗性推演,不采信执行者自述。

## 裁决

**CHANGES_REQUESTED** —— 实现对冻结规格是忠实的,矩阵与变异红证全部成立;
但发现**一条矩阵覆盖不到的真实缺陷**(Finding 1),需在合入前处置。

## 已独立核实为真

| 项 | 结果 |
|---|---|
| 全量套件 | 838 passed / 4 skipped / 0 failed(基线 807/4,净增 31 实例) |
| 20 条具名变异 | **20/20 PASS**:每条具名承重实例转红、恢复后回绿 |
| 等价控制 M-B1`[kimi]` | 全程保持绿(DoD 例外规则二成立) |
| must-stay-green 七项 | 全绿 |
| 范围 | 仅 5 个 allowed 代码文件 + 本 WP 自己的 report/status,零 forbidden 命中 |
| 原缺陷是否消失 | 候选循环、`continue`、全部 `"falling back"` 文案均已删除;resolver 内无任何从首选走向 `claude` 的路径 |
| F7 零外流 | 三条异常文案均为固定类别,无 `probe_output` 拼接 |
| F7 分路脱敏 | native 支在任何 `redact_env_value` 调用之前返回(无 TypeError 面);bound 支硬性脱敏 |
| 报告诚实性 | 未声称「已对原生 kimi 凭证脱敏」;F3 的生产 vs checkout 事实照写未改写 |

## Finding 1(阻断):legacy `PROBE_CMD` 路径的 S4 raise 无人接

`main()` 有两处 `_resolve_developer` 调用,只有一处包了 `try/except`:

- `redispatch.py:461`(`probe=True`)**有** `except ProbeFailedError` → 干净地
  打印 `REDISPATCH_STOP` 并 `return 0`;
- `redispatch.py:513`(`probe=False`,legacy `PROBE_CMD` 分支)**没有**。

`probe=False` 时 S5b 在探针前就返回,所以 quota/other 两条 raise 不可达;
**但 S4(`unknown developer adapter`)发生在 S5b 之前**。编排者实测确认可达:

```
_resolve_developer(repo=..., probe=False) with adapter_name="no-such-adapter"
-> RAISES ProbeFailedError('unknown developer adapter')
```

后果:配置里 developer adapter 名写错时,legacy 路径不是 `REDISPATCH_STOP`
交人,而是**未捕获异常 + traceback**。与 brief `:800-801` 的担忧完全同类
(「该路径只在 legacy 分支运行,漏改会在生产运行时才崩」),只是漏的面
从三元解包换成了异常传播。

**为何矩阵测不到**:D5 / B3 都把 `_resolve_developer` 整个 monkeypatch 掉,
`main()` 边界上从不走真实 S4;A3 只测 resolver 层的 raise,不测 `main()` 是否接。
这不是执行者偷工,是冻结矩阵本身的盲区。

**定性**:S4 的 raise 本身**符合**冻结规格(brief `:340` / `:410` 逐字如此),
缺的是 `main()` 的接收端。所以这不是「实现偏离 brief」,而是
**brief 的 `main()` 接线要求不完整**。编排者**不自行打补丁**:
按 §4.1,改 `main()` 的异常处置属行为面变更,应走 brief 修订或明确授权,
不能在评审阶段顺手加——否则这次加的分支同样没有承重测试。

### 建议处置(供裁决)

1. **最小修订(推荐)**:brief 出 rev10 加一条 `main()` 接线要求
   (legacy 路径同样捕获 `ProbeFailedError` → `REDISPATCH_STOP`)+ 一条承重测试
   (不 monkeypatch resolver,让真实 S4 穿过 `main()`)+ 一条变异
   (删掉该 `except` → 该测试转红)。走 r9 二签确认,再派发一轮小实现。
2. **记录为已知缺陷**:本 WP 按原样合入,Finding 1 单独立 WP。
   风险:配置写错时生产 legacy 路径崩在运行时,而本 WP 的目标正是
   「失败要交人、不要静默降级」——崩 traceback 虽不静默,也不是交人。

## Finding 2(非阻断,记录):M-B3 锚点曾被拆散

第一轮 20 条变异时 M-B3 判 BLOCKED:冻结的
`fallback_binding=None if fallback_applied else fallback_binding`
被实现成两行重赋值 + 变量名 `fb`,逐字锚点消失。行为等价,但变异无法机械施加。
已由 `7b3c99e` 改回冻结形态,复跑 20/20 PASS。

**值得记住的教训**:这正是「逐字锚点」纪律的价值——行为等价的重写会悄悄
摧毁变异可执行性,而全绿的测试套件对此完全无感。

## Finding 3(非阻断,证据卫生)

一次全量运行出现 `273 errors`,根因是编排者自己在同一仓库并发
`git checkout`(多个套件 shell-out 到 git)。串行复跑即 838/4/0。
已写入执行报告的「已知伪失败模式」,避免后人误判为 flaky。

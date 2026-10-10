# WP-01: developer 探针失败不得静默降级到 claude

> 冻结日期 2026-10-10 | rev11 | 编排者 claude-code 角色 | 执行者 kimi
> (rev7 起编排者会话的实际执行工具切换为 kimi-coding/k3;角色与独立性不变,
>  评审仍由编排者角色、二签仍由 codex 承担,记录以与实际工具一致为准。)
> 冻结后执行期间只读。修订走 re-freeze(rev12),不原地改。
> 基线 `main` `0ba058d`。设计见同目录 `DESIGN.md`。
> 存档:rev1 `WP-01-brief.rev1.md`、rev2 `WP-01-brief.rev2.md`、
> rev3 `WP-01-brief.rev3.md`(含 rev3 相对 rev2 的变更表)、
> rev4 `WP-01-brief.rev4.md`(含 rev4 相对 rev3 的变更表)、
> rev5 `WP-01-brief.rev5.md`(含 rev5 相对 rev4 的变更表)、
> rev6 `WP-01-brief.rev6.md`(含 rev6 相对 rev5 的变更表与 r4 三项必改的关闭方式)、
> rev7 `WP-01-brief.rev7.md`(含 rev7 的矩阵化重写说明与旧→新映射表)。
> rev8 未单独存档:rev9 与 rev8 的全部差异即文末三个英文别名节,`git diff` 可证。
> rev4 由第三轮二签 REWORK(`.agentic/wp01-brief-consult-r3-attempt2.answer.md`,
> `CODEX_DECISION: REWORK`,绑定 worktree head `a4bc5d7` / brief rev3
> sha256 `ea608a02`)驱动,逐条关闭其**五项必改**。
> 该轮 r3 attempt 1 已作废(answer 空体、verdict 未写出即耗尽预算),
> 见 receipt 的 `voided_attempts`。
>
> **rev5 的来源不是二签,是编排者自己的派发前独立复核。**
> r4 已在 `WP-01.status.json` 开为 `PENDING` 并绑 rev4,但**提示词与 harness 从未写出,
> 从未派发**,因此 **rev4 没有、也不会有 codex 裁决**;其 `prior_revs` 记为
> `SUPERSEDED_BEFORE_CONSULT`。编排者在动手写 r4 提示词前按 `CLAUDE.md`
> §Review「不得因为是自己写的计划就放行」复核 rev4,实测发现**三处新引入的假绿面**
> (见 §「rev5 相对 rev4 的变更」),其中第一处会让 rev4 新增的承重不变式
> **恒绿、不可能转红**。带着它派发只会烧掉一轮预算去确认已知事实,故先出 rev5,
> 再把 r4 一次性打在 rev5 上。
> 本次 re-freeze 由用户 2026-10-10 明确指示,`freeze_scope` 的 `AUTONOMY_STOP`
> 已据此放行(`AGENTIC_AUTONOMY_APPROVE=1`,仅限该步)。
>
> 配置权威仍是 `main_repo()`,未改全局语义;三处修正**全部是 brief 内的测试规格
> 与记账口径修正**,不触产品语义、不扩范围,故仍停在 REWORK 层级不升 CONSULT。
>
> **rev6 由第四轮二签 REWORK 驱动**
> (`.agentic/wp01-brief-consult-r4.answer.md`,`CODEX_DECISION: REWORK`,
> 绑定 worktree head `1b9fa9b` / brief rev5 sha256 `4ed58156`,
> session `01a1...` 见 receipt),逐条关闭其**三项必改**
> (见 §「rev6 相对 rev5 的变更」)。r4 是**首次在 rev5 上取得的有效裁决**
> (`valid_consult: true`,marker 形式),也是本 WP 四轮里第三个有效轮次。
> 三项必改中第三项(DoD 交叉记账自相矛盾)**是编排者 rev5 自己引入的回归**,
> 已在 rev6 建模复现并修正;另两项是 rev4 遗留、rev5 未触及的漏面。
> 三项**全部仍是 brief 内的测试规格与记账口径修正**,不触产品语义、不扩范围,
> 故仍停在 REWORK 层级不升 CONSULT ——
> r4 Q10 明确裁定「规格偏重但尚未到必须 CONSULT 拆 WP 的程度:生产改动仍围绕
> 一个 adapter detail API、一个 resolver 和两个 `main()` 接线点,依赖紧密,
> 强拆反而产生中间 API 状态」。
>
> **rev7 由第五轮二签 REWORK 驱动**
> (`.agentic/wp01-brief-consult-r5.answer.md`,`CODEX_DECISION: REWORK`,
> 绑定 worktree head `89a03b4` / brief rev6 sha256 `602c938a`),
> 逐条关闭其**三项必改**,并按 r5 Q10(a) 的裁定做**矩阵化压缩**
> (18 条编号不变式 → 16 个测试条目 + CHAR-1;守卫互补与连带红记账整套删除),
> 结构方向由用户在 r5 裁决后拍板。r5 Q10(b) 裁定:矩阵化后仍单 WP,不必拆包。
> **本 brief 尚未获授权实现**:r5 receipt 记 `implementation_authorized: false`、
> `dispatch_authorized: false`、`wp_state_at_dispatch: "DRAFT"`。
> **rev8 由第六轮二签 REWORK 驱动**
> (`.agentic/wp01-brief-consult-r6.answer.md`,`CODEX_DECISION: REWORK`,
> 绑定 worktree head `360fce6` / brief rev7 sha256 `027d1256`),
> 逐条关闭其**四项必改**(见 §「rev8 相对 rev7 的变更」)。
> r6 的元判断:矩阵方向正确、核心「不换 adapter」覆盖已基本充分,
> 本轮缺的是 S4/S7 两个 egress 空格(覆盖)加三处执行口径(精确性);
> rev8 **只做定点修订,不再扩轴**。
> r7 已审 rev8:**CODEX_DECISION: ACCEPT**
> (`.agentic/wp01-brief-consult-r7.answer.md`,绑 `695066e` / rev8 sha256 `20dff7a6`,
> `valid_consult: true`,七轮后首个 ACCEPT)。
> **rev11 关闭 r9 二签的五条必改项**。r9 确认了 Finding 1 的定性,但指出
> rev10 的 B6 **仍可假绿**,并用同一「边界被整体 stub」机理找出**两条更严重的
> 接缝盲区**。编排者**实测复现了两条**(每条都是单改一处 + 跑全量 + 还原):
>
> - 把默认 registry 的 `"kimi"` key 改成构造 `ClaudeAdapter`
>   —— **即本 WP 要禁止的静默换 adapter 本身** —— **838 passed 全绿**;
> - 把主路径 `probe=True` 改成 `probe=False`
>   —— **生产注入探针被整体关闭** —— **838 passed 全绿**。
>
> 即:20/20 变异红证成立的同时,存在两条能直接击穿本 WP 目标却被全套测试
> 放过的生产接线面。机理:矩阵只锁 resolver **内部**决策,
> 而「`main()` 用什么参数调 resolver」「默认 registry 的 key→class→binding 组合」
> 这两处跨边界接线,被 `_stub_io()` 的 `_resolve_developer` 整体替换
> (`tests/...:35`,该 lambda **忽略 `repo` 与 `probe`**)与「所有 resolver 测试
> 都注入自定义 registry」双双遮蔽。
> rev11 新增 **F9**、**B6 加固**、**M-B6a/M-B6b**、**D6**、**D7** 及其变异。
> rev10 存档 `WP-01-brief.rev10.md`(`941d5544`)。
>
> **rev10 关闭实现评审的 Finding 1**(阻断项,见 `WP-01-review.md`):
> rev9 实现经编排者独立评审 —— 矩阵 19 条目全在、20 条变异全部成立 ——
> 但发现**冻结矩阵覆盖不到的一条真实缺陷**:`main():513`(legacy `PROBE_CMD`
> 路径,`probe=False`)**未捕获** `ProbeFailedError`,而 **S4 发生在 S5b 之前**
> 故在该路径可达。配置里 adapter 名写错时,legacy 路径不是 `REDISPATCH_STOP`
> 交人,而是未捕获异常 + traceback。矩阵测不到的机理:D5/B3 把
> `_resolve_developer` 整个 monkeypatch 掉,真实 S4 从不穿过 `main()` 边界。
> rev10 新增 **F8**(`main()` 两处调用点的异常处置)、承重测试 **B6**
> (不 stub resolver)与变异 **M-B6**。rev9 存档 `WP-01-brief.rev9.md`(`03a6087c`)。
>
> **rev9 是纯模板兼容修订**:派发闸 `dispatch_lint` 要求 brief 含三个英文节名
> (`## Acceptance tests` / `## Allowed and forbidden paths` / `## Completion definition`,
> 现行模板与 kqff WP-1 先例均带),本 brief 全中文标题不满足。
> rev9 只在文末**追加三个英文别名节**(内容仅为指向中文正文的同义声明,
> 见文末),**不增删改任何既有行**。绑定 r8 二签确认该 delta 无语义。

## 目标(一句话)

`_resolve_developer()` 在 developer 首选探针失败时,按失败原因分流到「单跳 flash 回退」
或「STOP 交人」,**绝不**推进到另一个 adapter 把 developer 静默换成 claude;
且探针原始输出只在内存里参与额度判定,不进 reasons / 异常 / 日志 / status。

## rev8 相对 rev7 的变更(r6 四项必改)

> r6 裁决原文:`.agentic/wp01-brief-consult-r6.answer.md`(`CODEX_DECISION: REWORK`,
> 绑 rev7 @ `360fce6` / sha256 `027d1256`,`valid_consult: true`)。
> 四项必改由编排者逐条对照 rev7 文本核实为真后采纳。

| r6 必改项 | 关闭方式 | 落点 |
|---|---|---|
| 1. S4 与 S7 的零外流空格:A3 只查异常文案(可 `print(adapter_name)` 泄漏配置原文);B4 只查标志位(可通过支 `print(probe_output)`,直接违反 F7「探针输出唯一用途是喂 `is_quota_error`」) | **A3** 改用带哨兵的未知名(`no-such-adapter-SENTINEL4`),加 capsys 断言与变异 **M-A3b**;新增 **C0** 通过支零外流(按 binding 参数化)与变异 **M-C0** | A3;新增 C0 |
| 2. S1-S11 锚点表缺 `probe=False` 分支,与 must-stay-green 第 5 项不闭合 | 位点表声明为 **`probe=True` 子图**,S5 与 S6 之间冻结 **S5b** `if not probe: return adapter, reasons, False`;新增 **B5** 测试该路径(探针计数 0)与变异 **M-B5** | S 表;新增 B5 |
| 3. 硬验收对「红错实例」无处置:M-B1 的 [kimi] 是**等价控制实例**(原式与变异式等价),它转红说明变异不纯/位点错/参数化坏,不能仅作信息忽略 | DoD 新增**等价控制规则**:被显式声明为等价控制的实例(当前仅 M-B1[kimi])**必须保持绿,转红即 BLOCKED** | §DoD |
| 4. 「报告所有实际连带红」不可机械执行(五步法只跑具名测试,无从得知全部连带) | DoD 改为:**只记录本次命令实际覆盖到的实例**;连带红讨论限于该测试自身的实例 | §DoD |
| (r6 Q8 附带意见)CHAR-1 声称锁五种退化配置但测试只构造一种 | CHAR-1 **参数化为五种 fixture**(无 config / `[roles]` 空 / `[]` / `""` / 缺项) | CHAR-1 |

**rev8 不变的部分**:矩阵轴与族结构;A/B/C/D 既有条目的断言与四元组;
F1-F7 行为目标;范围;基线;五步法。规模:18 个测试条目 + CHAR-1
(8 个双实例参数化),20 条具名变异。r6 明确:「不建议再扩大 adapter/outcome 轴」。



## rev7 相对 rev6 的变更(r5 三项必改 + 矩阵化压缩)

> r5 裁决原文:`.agentic/wp01-brief-consult-r5.answer.md`(`CODEX_DECISION: REWORK`,
> 绑 rev6 @ `89a03b4` / sha256 `602c938a`,`valid_consult: true`)。
> 三项必改由编排者逐条独立核实为真后采纳;
> **矩阵化压缩的结构方向由用户在 r5 裁决后拍板**(r5 Q10(a) 的裁定:
> 逐条追加编号的边际收益已转负,rev7 应压缩为参数化矩阵而非继续膨胀;
> Q10(b):矩阵化后仍单 WP,不必拆包)。

| r5 必改项 | 关闭方式 | 落点 |
|---|---|---|
| 1. 补「非 kimi 首选 + 额度命中 + 无 fallback」的不换 adapter oracle(漏网实现:`adapter_name != "kimi"` 时在该支改派 kimi) | **A2 按 primary ∈ {kimi, codex} 参数化**,registry 三计数工厂,断言固定 STOP 文案 + 所有非首选工厂计数 0;codex 实例直接杀死该漏网实现(kimi 计数变 1) | A2 / M-A2 |
| 2. 补 bound 路径两条 quota 分支的零外流 oracle(`INV-P6c`/`INV-P2d` 都限 native;`INV-P6` 虽 bound 却只走非额度) | **C1 / C2 按 binding ∈ {native, bound} 参数化**;无条件泄漏变异由同一测试的两个实例共同承重 | C1 / C2 / M-C1 / M-C2 |
| 3. 统一连带红不匹配的处置协议;补 `M-P1b`;修正「`M-P2d` 整条替换」的错误总括 | **整套「对角线交叉记账 + 冻结连带红集合」机制删除**:硬验收只剩「具名承重测试转红」;连带红降为纯信息记录,不与任何冻结集合比对、不触发 BLOCKED。`M-P1b` 未冻结问题与 `:850` 错误总括随机制删除一并消失 | §DoD |

**结构压缩(rev7 本体)**:

- 18 条编号不变式 + 守卫互补 → **16 个测试条目 + CHAR-1**(7 个双实例参数化),
  **17 条具名变异**,每个独立决策位点一条代表。
- F6 的决策位点表 **S1-S11** 冻结为变异锚点全集(见承重矩阵节)。
- **S4 未知名前置支从「其余」拆出**(r5 Q8):它发生在探针之前、没有
  `probe_output`、不参与额度分流;A3 增加固定文案精确相等断言
  (同时证明原始配置值不被回显)。
- **守卫互补取消的依据**:rev5/6 需要 `binding is None` / `is not None` 守卫,
  是因为每条不变式只覆盖一个 binding 实例,无条件泄漏会同时红两条、无法归因。
  参数化后同一测试的两个实例**本来就该同时红**,无条件变异成为正确形态,
  守卫及其记账随之失去存在理由。

**旧编号 → 新条目映射**(沿革追溯用;历史变更表中的旧编号不再回改):

`INV-P1`→A1[kimi]、`INV-P1b`→A3、`INV-P1d`→A1[codex]、`INV-P2`→B1[kimi](+B2)、
`INV-P2b`→A2[kimi]、`INV-P2c`→B1[codex] / M-B1、`INV-P2d`→C2[native]、
`INV-P3`→B2、`INV-P4`→D1、`INV-P5`→B3、`INV-P6`→C3[bound]、
`INV-P6b`→C4、`INV-P6c`→C1[native]、`INV-P6d`→C3[native]、`INV-P7`→D2、
`INV-P8`→D3、`INV-P9`→D4、`INV-P9b`→D5、`CHAR-P1c`→CHAR-1。

**rev7 不变的部分**:F1/F2/F3/F5/F6/F7 的行为目标与冻结实现文本
(F6 仅按 r5 Q8 把未知名支拆为独立条目,分流语义不变);范围与
allowed/forbidden_paths;基线口径;must-stay-green 七项;五步变异顺序;
无测试退化门禁。生产代码依然一行未动。

## rev6 相对 rev5 的变更(第四轮二签 REWORK 的三项必改)

> r4 裁决原文:`.agentic/wp01-brief-consult-r4.answer.md`。
> rev5 相对 rev4 的变更表见下一节;更早的沿革见存档。
>
> **r4 已确认充分、rev6 不再改动的部分**(避免重复劳动):
> R3-1(`INV-P2b` 拆支)、R3-2(两步式 `M-P8` + 签名有序断言)、R3-4(`INV-P4`
> 改绑 base-only oracle)充分;修正 1 的 `reasons` 不可观测建模「充分成立」,
> 且 `M-P6`/`M-P6c`/`M-P6d` 三条「本身形成干净对角线、守卫方向没有写反」;
> 修正 2(`INV-P9b`)充分,且 r4 独立确认 `main()` 内除 `:538`/`:542` 外
> **没有第三处**未穿 `repo` 的同类配置读取;修正 3(`INV-P2c` 计数 2 +
> 最后一次实参)充分;`reasons` 纪律(附注 11)「充分且自洽」,
> r4 逐条核过 `INV-P1`/`P1b`/`P2b`/`P6`/`P6d`/`P6c` 的 oracle,
> 确认**没有**现存不变式仍在 raise 支上隐含依赖 `reasons`;
> `INV-P1b`/`INV-P3`/`INV-P7`/must-stay-green 七项/baseline 口径均充分。

| # | r4 必改项 | 为什么是缺陷(编排者已独立复现) | rev6 的关闭方式 | 落点 |
|---|---|---|---|---|
| 1 | **补 native「额度命中 + 无 fallback」支的零外流覆盖** | r4 指出 F6 的四支分流里,**第三支(额度命中但 `fallback_binding is None`)没有任何输出外流 oracle**。编排者 grep 核实:`INV-P2b` 的 oracle 只有「抛 `ProbeFailedError`、异常文案等于 `probe failed: quota, no fallback`、claude 工厂与探针计数为 0」,**capsys / stdout / 哨兵三个词在其规格块内出现 0 次**。于是实现可以只在这一支 `print(probe_output)`,而 `INV-P6c`(额度+**有** fallback)与 `INV-P6d`(**非**额度)都保持绿 —— 这是与 rev4 的 `M-P6c` 同类的「分支与 oracle 错配」漏面,只是换到了第三支 | 新增 **`INV-P2d`** / **`M-P2d`**:native + 额度命中 + `fallback_binding is None`,哨兵 `NATIVE_EGRESS_SENTINEL_E`,oracle = 异常文案精确相等 + capsys stdout/stderr 零哨兵;变异是三重条件守卫的 `print`,只在该支生效,保证其余三条 egress 不变式不被顶替 | §F7;**新增 INV-P2d** |
| 2 | **把「不换 adapter」从 kimi→claude 特例泛化** | r4 指出核心目标的承重测试**全部绑在当前默认组合上**:`INV-P1`、`INV-P1b`、`INV-P2b` 只监控 `claude` 计数,而唯一用非 kimi 首选的 `INV-P2c` **只覆盖合法的 flash 路径**。编排者核实无误。于是仍可写出:**非 kimi 首选(如 codex)发生非额度失败时偷偷构造 `registry["kimi"](...)`,kimi 首选时正常抛错** —— 它通过现有 `INV-P1/P1b/P2b/P2c`、保留全部冻结原表达式、让所有既列变异照常转红。r4 的判词:「生产默认 registry 当前只有 kimi/claude,并不能把『禁止换 adapter』的规格降格为只防 kimi→claude」 | 新增 **`INV-P1d`** / **`M-P1d`**:**codex 首选 + 非额度失败 + 无 fallback**,registry 注入 `codex`/`kimi`/`claude` 三个计数工厂,断言抛 `ProbeFailedError` 且**所有非首选工厂计数全为 0**(不止 claude);并把「非首选工厂计数全为 0」立为**全族 oracle 口径**,`INV-P1`/`INV-P1b`/`INV-P2b` 的断言一并从「claude 计数 0」升级为「所有非首选工厂计数 0」 | **新增 INV-P1d**;INV-P1 / P1b / P2b 的 oracle 口径 |
| 3 | **修正 DoD 交叉记账的自相矛盾**(**编排者 rev5 自己引入的回归**) | rev5 新增的交叉记账条款先说「`M-P1` / `M-P6` / `M-P6d` 共用同一原表达式,施加这**四条**中任意一条时须记录其余承重测试仍绿」,随后只给出 `M-P6`/`M-P6c`/`M-P6d` **三行**矩阵,`M-P1` 不在其中。编排者建模复现:`M-P1` 把非额度 raise 整条替换为返回 claude,于是 `INV-P1` 红(正是其承重)、`INV-P6` 与 `INV-P6d` 因**等不到预期异常**也红 —— **一条变异红三条**,触发同条款的「两条同时红 → 报 BLOCKED」,**正确执行者必然被逼报 BLOCKED**。r4 判词:「这不是次要文案问题,而是可重复的执行死角」 | 交叉对角线范围**明确限定为 `M-P6` / `M-P6c` / `M-P6d` 三条**,`M-P1` 从该规则**删除**;另明文记录:`M-P1` / `M-P1b` / `M-P2b`(无守卫、整条替换 raise)**预期会连带**使 `INV-P6` / `INV-P6d` 转红,**这些连带红既不构成承重证据,也不得触发 BLOCKED**;BLOCKED 只在三条对角线变异之间出现跨红时才报。rev6 新增的 `M-P1d` / `M-P2d` **带守卫、零连带红**,明文列为豁免条款的例外,出现额外转红即视为写错 | §DoD |

**rev6 不变的部分**:F1/F2/F3/F5/F6/F7 的**行为目标与冻结实现文本一字未动**;
`INV-P2 / P2c / P3 / P4 / P5 / P6 / P6b / P6c / P6d / P7 / P8 / P9 / P9b` 与
`CHAR-P1c` 的规格未动;「必须保持绿集合」七项未动;基线数字未动。
rev6 只新增两条不变式、统一一处 oracle 口径、修一条 DoD 自相矛盾。

**rev6 承重不变式全集**(18 条带变异):
`INV-P1 / P1b / P1d / P2 / P2b / P2c / P2d / P3 / P4 / P5 / P6 / P6b / P6c / P6d /
P7 / P8 / P9 / P9b`
+ `CHAR-P1c`(characterization,无变异,不计入)+ 必须保持绿集合(7 项)。

## rev5 相对 rev4 的变更(编排者派发前独立复核的三项修正)

> 本节为 rev5 原文,rev6 原样保留作为沿革记录。rev4 相对 rev3 的变更表见下一节;
> rev3 相对 rev2 的见存档 `WP-01-brief.rev3.md`。

| # | rev4 的缺陷 | 为什么是缺陷(实测) | rev5 的关闭方式 | 落点 |
|---|---|---|---|---|
| 1 | **`M-P6c` 不可能让 `INV-P6c` 转红**(决定性) | rev4 把变异冻结为在探针调用行后插入 `if binding is None: reasons.append(probe_output)`,而 `INV-P6c` 走的是**非额度支**即 `raise ProbeFailedError` 收场。`reasons` 是 `_resolve_developer` 的**函数局部变量**,raise 时随栈帧丢弃;brief 全文无任何条款要求把它挂到异常上(`:173` 只管正常返回的三元组),`ProbeFailedError` 类体也是空的(`redispatch.py:98`)。于是测试**拿不到 `reasons` 的任何句柄**,两次运行的异常文案逐字相同。编排者按冻结文本建模实跑:变异产生**零可观测差异**,`INV-P6c` 恒绿。这与 r3 Q9 否掉 rev2 `M-P6b` 的理由(「去掉脱敏后密钥只存在内存,oracle 看不见」)是**同一个错误换了位置重现** —— r3 必改项 3 因此并未真正关闭 | 把 native 零外流**拆成两条,各自绑定可观测面**:`INV-P6c` 改走**额度支且有 fallback 的可返回路径**(此时 `reasons` 随三元组返回,测试可直接断言每个元素);新增 `INV-P6d` 专管**非额度 raise 支**,oracle 只认**异常文案 + capsys 的 stdout/stderr**。两条的变异都用 `binding is None` / `is not None` 守卫,保证位点互不顶替 | §F7;INV-P6c;**新增 INV-P6d** |
| 2 | **F5 漏掉 `main():538` 的第二个配置权威** | `INV-P9` 的注释(rev4 `:495-496`)自己点名「`main():538` 的 `resolve_role_fallback_binding("developer")` 不传 `repo`,而 `:542` 的 `load_quota_patterns(repo_root)` 传了 —— 两个权威视图」,但 rev4 **只在 `_resolve_developer()` 内部修了这件事**,`main()` 里的原始双权威留在原地(实测 `redispatch.py:538` 仍是无 `repo` 调用)。而 `INV-P9` 的 spy 只包 `_resolve_developer` 的三处调用,**查不出 `main()` 的那一处** | F5 的连带面补上 `main():538` 的显式穿参;新增 `INV-P9b` / `M-P9b` 用 spy 钉住 `main()` 这一处收到的实参是 `repo_root` | §F5;**新增 INV-P9b** |
| 3 | **`INV-P2c` 的工厂计数口径算错一次,且未要求注入 registry 键** | rev4 断言「codex 工厂计数 1」。但 F6 冻结的实现必须先 `registry[adapter_name](binding)` 构造出 adapter 才能调 `probe_injection_detail()`,探针失败后再 `registry[adapter_name](fallback_binding)` 构造 flash —— **同一个工厂被调两次**。按「计数 1」写断言会让**正确实现**也转红,执行者据此报无谓 BLOCKED 或反向把实现改坏。另外默认 registry 只有 `kimi`/`claude` 两键(`redispatch.py:137-143` 实测),不显式注入 `codex` 会先撞上 F6 的「adapter 名不在 registry → raise」支,本条退化成 `INV-P1b` 的重复覆盖;`kimi` 键缺失则 `M-P2c` 会抛 `KeyError`,红的因果与宣称语义不符 | 计数改为 **2**,实参断言改为「**最后一次**调用收到的 **is** `fallback_binding`」;写明 registry 必须同时注入 `codex` 与 `kimi` 两个计数 stub,并冻结 `M-P2c` 施加后的期望红证 | INV-P2c |
| 附 | `INV-P6` 的 oracle 清单含 `reasons`,在 raise 支上是**空断言** | 同缺陷 1 的根因:`INV-P6` 也走非额度 raise 支,`reasons` 同样不可观测。保留它会让人误以为那是一道真 oracle | `INV-P6` 的 oracle 清单删去 `reasons`,只留异常文案 + capsys;并把「raise 支上 `reasons` 不可观测」写进 §附注 11 作为全局记账纪律 | INV-P6;附注 11 |
| 附 | `M-P6` 的变异是**无条件**泄漏 | 无条件泄漏会让 `INV-P6`(bound)与新增的 `INV-P6d`(native)**同时转红**,无法区分哪条在承重,违反本 brief 自己的「一变异一承重测试」纪律 | `M-P6` 改为 `binding is not None` 守卫的条件式泄漏,与 `M-P6d` 的 `binding is None` 守卫严格互补 | M-P6 / M-P6d |

**rev5 不变的部分**(避免误读):F1/F2/F3/F5/F6/F7 的**行为目标与冻结实现文本一字未动**;
`INV-P1 / P1b / P2 / P2b / P3 / P4 / P5 / P6b / P7 / P8 / P9` 与 `CHAR-P1c` 的规格未动;
「必须保持绿集合」七项未动;基线数字未动。rev5 只动**测试规格、变异守卫、记账口径**
与 F5 的一处漏改。

**rev5 承重不变式全集**(16 条带变异):
`INV-P1 / P1b / P2 / P2b / P2c / P3 / P4 / P5 / P6 / P6b / P6c / P6d / P7 / P8 / P9 / P9b`
+ `CHAR-P1c`(characterization,无变异,不计入)+ 必须保持绿集合(7 项)。

## rev4 相对 rev3 的变更(五项必改的关闭方式)

> 本节为 rev4 原文,rev5 原样保留作为沿革记录。

| r3 必改项 | 关闭方式 | 落点 |
|---|---|---|
| 1. 增加 `INV-P2b`:额度输出且 `fallback_binding=None` 时抛 `ProbeFailedError`,Claude 工厂/探针计数均为 0;绑定 mutation 将该 STOP 分支精确替换为返回 Claude | F6 把「额度命中但未配 fallback」从「视同非额度失败」**拆成自己的具名分支**,冻结独立异常文案 `probe failed: quota, no fallback`;新增 **INV-P2b** + **M-P2b** 绑在该 raise 上 | §F6;INV-P2b |
| 2. 重写 M-P8:冻结完整可直接施加的 import/表达式,测试 monkeypatch 实际 lookup namespace,去掉不存在的 `_first_of`;签名断言改为参数名、顺序、keyword-only kind 与无 `*args/**kwargs` 的精确断言 | M-P8 冻结为**两段式逐字替换**(恢复模块级 `from agentic_loop.resolve_paths import get_roles` + 表达式改用 `get_roles().get("developer")[0]`);INV-P8 的 monkeypatch 目标改为 `agentic_loop.redispatch.get_roles`(`raising=False`,已实测可用);签名断言改为 `inspect.signature` 的有序 `(name, kind)` 列表精确相等 | INV-P8 / M-P8 |
| 3. 增加 native detail 零外流不变式:`binding=None`、native stdout 含哨兵时,异常、`reasons`、stdout/stderr 均不得含原文;绑定只泄露 native 输出的明确 mutation | 新增 **INV-P6c**(真实 `KimiAdapter(binding=None)` + stub `subprocess.run`)+ **M-P6c**(在探针调用行后插入 `if binding is None: reasons.append(probe_output)`,条件泄露,故 INV-P6 恒绿、仅 INV-P6c 转红) | §F7;INV-P6c |
| 4. 将 M-P4 的唯一承重 oracle 改为新增的 base-inheriting exact-bool 测试;既有十条列为 must-stay-green | M-P4 承重测试改为 `test_base_default_probe_injection_returns_exact_bool`;`tests/test_injection_probe.py` 既有 10 条**降级**进「必须保持绿集合」 | INV-P4;§必须保持绿集合 |
| 5. 在 DoD 写明 mutation 顺序 | DoD 新增「变异施加顺序(强制)」五步法:先实现并全绿 → 验证原表达式存在 → 施加单条变异 → 确认具名测试转红 → 恢复源文件再下一条 | §DoD |
| (建议项,采纳)`M-P1c`/`INV-P1c` 改名以免误导「承重不变式」计数 | 全量改名为 **`CHAR-P1c`**,并在 DoD 与计数口径里单列「characterization 前提」,不计入带变异的承重不变式 | CHAR-P1c;§DoD |
| (编排者 rev4 自补)「不换 adapter」此前只是**偶然**成立:flash 回退若写 `registry["kimi"](fallback_binding)`,在首选非 kimi 时本身就是跨 adapter 换派 | F6 冻结 flash 构造为 `registry[adapter_name](fallback_binding)`;新增 **INV-P2c** + **M-P2c** 用非 kimi 首选把「同一 registry key」钉成结构性事实 | §F6;INV-P2c |

## 范围

`allowed_paths`
- `src/agentic_loop/redispatch.py`
- `src/agentic_loop/adapters/base.py`
- `src/agentic_loop/adapters/kimi.py`
- `tests/test_redispatch_quota_fallback.py`
- `tests/test_injection_probe.py`

`forbidden_paths`
- `src/agentic_loop/resolve_paths.py`(`DEFAULT_ROLES` 展平是无害设计,见 DESIGN §2;
  本 WP 的配置权威问题一律在 `redispatch.py` 内显式穿 `repo` 解决,**不动解析器**)
- `src/agentic_loop/quota_fallback.py`(判定逻辑复用,不改)
- `src/agentic_loop/bootstrap_cmd.py`(F1 的加法设计正是为了让它零改动)
- `src/agentic_loop/adapters/claude.py`、`adapters/codex.py`
- `.agentic/config.toml`(rev2 起禁写:rev1 的 F4 已删除)
- `src/agentic_loop/secret_redaction.py`(复用 `redact_env_value`,不改)
- `uv.lock`(本仓当前**未跟踪**此文件,列入即禁止新建)、
  `docs/plans/2026-09-*/**`、其他任何路径

> 若实现中发现**必须**改 `resolve_paths.py` 才能完成 F5,**立即 BLOCKED 上报**,
> 不得自行扩范围 —— 那等于改配置权威语义,须升 CONSULT。

## 输入

- `DESIGN.md` §1 缺陷、§2 非缺陷(勿"顺手修")、§3 四条取向
  (rev2 冻结前编排者已修正两处:§3 R3 的实现处数由「5 处」改为**四处定义**
  `adapters/base.py:193` / `kimi.py:168` / `claude.py:126` / `codex.py:199`
  + 唯一独立生产调用方 `bootstrap_cmd.py:88-92`;§3 R4 标注为**已移出本 WP**。
  `DESIGN.md` 不在 `allowed_paths`,执行者零改动)
- 二签 r1 全文:`.agentic/probe-wp01-brief-consult.answer.md`(rev2 八项必改来源)
- 二签 r2 全文:`.agentic/wp01-brief-consult-r2.answer.md`(**本 rev 四项必改来源**)
- `quota_fallback.py`:`is_quota_error(output, patterns=None)`、
  `load_quota_patterns(repo)` 已就位,**直接复用,不要新写判定**
- `resolve_role_binding(role, repo=None)` / `resolve_role_fallback_binding(role, repo=None)`
  均已接受 `repo`,**调用方传参即可**,不需改解析器
- `secret_redaction.redact_env_value(text, api_key_env)` 已就位

## 功能点

**F1 探针交出输出(加法,不改 bool 签名,默认实现不得递归)**
在 `adapters/base.py` 新增 `probe_injection_detail(self) -> tuple[bool, str]`。
默认实现必须**自己**完成判定,**绝不**回调 `self.probe_injection()`:
`_binding is None` → `return (self.probe(), "")`;否则保持现默认的 fail-closed
语义(`raise NotImplementedError(...)`,文案可沿用)。
`probe_injection()` 改为 `return self.probe_injection_detail()[0]`。
> 陷阱:若默认 detail 回调 `probe_injection()`,而 `probe_injection()` 又委托
> detail,则无限递归 —— 二签 r1 Q9 明确点出。必须写成非递归。
`claude.py` / `codex.py` 不改,继承 base 默认,bool 契约不变。

**F2 kimi 两条真实 detail 路径都要交出真实输出**
`adapters/kimi.py` 覆写 `probe_injection_detail()`,两条路径都返回**真实**输出:
- `_binding is None`(原生 kimi):不得只 `return (self.probe(), "")`。必须真跑
  原生探针命令 `[self._kimi_bin, "-p", "reply PROBE_OK"]` 并返回其 stdout,
  `ok = (proc.returncode == 0 and "PROBE_OK" in out)`;
  否则生产原生 kimi 永远认不出额度文本 —— 二签 r1 Q1 第二条逃逸。
- `_binding` 非空(provider 绑定):跑注入探针
  `[self._kimi_bin, "--config-file", cfg, "--model", self._binding.cli_selector,
  "-p", self._PROBE_PROMPT]`,`ok = (proc.returncode == 0 and self._SENTINEL in out)`。
两条路径的脱敏按 F7 的**分路政策**处理(不是"都脱敏")。
`OSError` 分支返回 `(False, "")`。

**F3 不触碰主 binding 评级(范围已校正为"被审 checkout 配置不变式")**
`resolve_paths.py` 在 `forbidden_paths`,解析器语义由构造保证不变。
`test_project_config_primary_developer_stays_native`(断言
`resolve_role_binding("developer", repo=REPO) == ("kimi", None)`,`REPO` 是本
checkout)必须保持绿。
**但必须如实记账**:该断言只是**被审 checkout 的配置不变式**,不是生产零回归。
编排者 2026-10-09 实测的生产权威(`main_repo()` = `/Users/admin/vibe/agentic_loop`)结果是
主 binding = `deepseekflash`(`identity_model=deepseek-flash`)、fallback = `None`;
被审 checkout 结果相反(主 = `None`、fallback = `deepseekflash`,
`identity_model=deepseek-v4-flash`)。两边 `config.toml` 内容不同,不是解析器 bug。
本 WP **不改任何 config.toml**,也不试图统一两边;执行报告须复述这一实测事实,
不得把 checkout 断言写成"生产不回归"。

**F4(rev1)已删除**
rev1 的 `.agentic/config.toml` 规范化与本 WP 的行为目标无关,且生产 config 不读
被审 checkout 的值,属另一目的。二签 r1 Q7 建议移出,rev2 采纳:`config.toml`
进 `forbidden_paths`,`test_project_config_resolves_flash_fallback` 的断言
**保持 checkout 现值不动**(`identity_model == "deepseek-v4-flash"`、
`cli_selector == "deepseek/v4-flash"`),列入「必须保持绿集合」。

**F5 单一配置权威:删 `roles_config`,显式穿 `repo`,一处取数**
**签名改为**:`_resolve_developer(*, repo: Path, registry: dict[str, Any] | None = None,
probe: bool = True) -> tuple[Adapter, list[str], bool]`。

- **删除 `roles_config` 形参**(二签 r2 Q4 首选项)。它来自展平后的 `get_roles()`,
  与 `get_roles_raw()` 驱动的 binding 是两个配置视图,保留形参就留着重新分叉的口子。
  adapter 名与 binding 必须出自**同一次**解析:
  `adapter_name, binding = resolve_role_binding("developer", repo=repo)`。
- `fallback_binding = resolve_role_fallback_binding("developer", repo=repo)`
- `quota_patterns = load_quota_patterns(repo)`
- **连带面(已全仓检索确认封闭,共四处)**:
  - 定义 `redispatch.py:126`
  - `main()` `:480` `adapter, _ = _resolve_developer(get_roles(), probe=True)`
    → `adapter, _, fb = _resolve_developer(repo=repo_root, probe=True)`
  - `main()` `:532` `adapter, _ = _resolve_developer(get_roles(), probe=False)`
    → `adapter, _, fb = _resolve_developer(repo=repo_root, probe=False)`
    (**legacy `PROBE_CMD` 路径专属**,见 DoD 的定向覆盖要求)
  - `tests/test_redispatch_quota_fallback.py:234` 的 monkeypatch
    `lambda roles, probe=True: (_StubDev(), [])`
    → `lambda *, repo, registry=None, probe=True: (_StubDev(), [], False)`
- **`main()` 内的第二个配置权威(rev5 新增,关闭 rev4 漏面)**:
  `redispatch.py:538` 的 `fallback_binding = resolve_role_fallback_binding("developer")`
  **不传 `repo`**,而紧邻的 `:542` `load_quota_patterns(repo_root)` 传了。
  这正是 D4 注释点名的「两个权威视图」**缺陷本体**,rev4 却只在
  `_resolve_developer()` 内部修掉,`main()` 里的原始双权威留在原地;
  且 D4 的 spy 只包 `_resolve_developer` 的调用,**查不出这一处**。
  **改为** `fallback_binding = resolve_role_fallback_binding("developer", repo=repo_root)`。
  `repo_root = main_repo()` 已在 `main():382` 就位,**先于** `:538`,无需移动。
  由 **D5** / **M-D5** 锁定。
- `get_roles` 在 `redispatch.py` 删后只剩 `:35` 的 import 成为死引用,**一并删除**
  (全仓检索:redispatch 内除 import 外仅 `:480` / `:532` 两处调用)。
  `resolve_paths.get_roles` 本身不动(仍被其他模块使用)。
- `repo_root = main_repo()` 已在 `main()` 现有行内,权威保持 `main_repo()`。

**F6 单一首选 + 原因分流 + 回退状态贯通**
`_resolve_developer()` 按 F5 取到唯一首选后探针:
- 探针通过 → 原样返回,`fallback_applied = False`。
- 探针失败且 `is_quota_error(probe_output, quota_patterns)` 为真且
  `fallback_binding` 非空 → 用 `fallback_binding` 构造 flash adapter 返回,
  `fallback_applied = True`。**构造表达式冻结为**
  `registry[adapter_name](fallback_binding)` —— 见下方「同一 registry key」。
- 探针失败且命中额度但 `fallback_binding is None` → **独立具名 STOP 分支**,
  `raise ProbeFailedError("probe failed: quota, no fallback")`。
  rev3 把它写成「视同非额度失败」,实现上会与非额度分支共用同一个 raise,
  于是「额度命中 + 无 fallback」没有自己的承重位点:实现可在这一支改派 claude
  而通过 rev3 全部不变式与变异(二签 r3 Q2/Q9 判定的决定性漏面)。
  本 rev 把它拆成**自己的 raise 语句**,由 A2 / M-A2 直接锁定。
  > 文案 `probe failed: quota, no fallback` 只含固定类别词,不含探针输出,
  > 不违反 F7;C 族的哨兵断言针对探针输出原文,与本文案无交集。
- **`adapter_name` 不在 registry`(前置支,发生在探针**之前**,没有
  `probe_output`,不参与额度分流)→ `raise ProbeFailedError("unknown developer adapter")`,
  文案精确固定、**不回显原始配置值**(r5 Q8)。
- 其余一切失败(非额度探针失败)→ `raise ProbeFailedError("probe failed: other")`。

**同一 registry key(rev4 新增的结构性约束)**
flash 回退**必须**用 `registry[adapter_name](fallback_binding)` 构造,
**不得**写成 `registry["kimi"](fallback_binding)`。rev3 之前「不换 adapter」在
flash 支上只是**偶然**成立 —— 因为生产首选恰好是 kimi;一旦 `roles.developer`
首选改成别的 adapter,硬编码 `"kimi"` 本身就是一次静默跨 adapter 换派,
正是本 WP 唯一目标所禁止的。该约束由 B1 的 [codex] 参数化实例 / M-B1 用**非 kimi 首选**钉死。

**删除**三段跨 adapter 逻辑:`:165-171` 的候选循环与其中的 `continue`、
`:178` 的「all configured ... falling back to built-in kimi」、
`:159-165` 候选为空分支的 `registry["kimi"](binding)` 兜底。
删除后函数体内**不存在任何候选循环**,只有一个 `adapter_name`。
**返回值扩为三元**:`(adapter, reasons, fallback_applied: bool)`。
`main()` 在 `fallback_applied is True` 时,给
`_dispatch_with_quota_fallback(...)` 传 `fallback_binding=None`,
使"探针阶段已跳 flash"后不可能再 flash→flash(二签 r1 Q1 第三条逃逸、`:538-543`)。

**F7 探针原始输出禁止外流(分路脱敏政策)**
原始探针输出的**唯一**用途是在内存里喂 `is_quota_error()`。
- `reasons` / `ProbeFailedError` 文案 / stdout / stderr / status 只允许写**固定类别**
  (如 `probe failed: quota` / `probe failed: other` / `unknown developer adapter`),
  **不得**拼接探针输出、config 原文或 env 值。
- **bound 路径(`_binding` 非空)**:返回前必须
  `out = redact_env_value(out, self._binding.api_key_env)`。这是硬性不变式,
  由 C4 直接 oracle 锁定。
- **native 路径(`_binding is None`)的安全语义(取二签 r2 Q6 选项 (a))**:
  原生 kimi 没有本仓已知的 `api_key_env`。编排者 2026-10-09 实测了两件**不同**的事,
  执行者不得混用:
  - `_run(..., redact_env=None)` **跳过**脱敏 —— 因为 `kimi.py:129` 是 `if redact_env:`
    守卫,`None` 为假即原样返回 `proc.stdout`;
  - `redact_env_value(text, None)` **不是原样返回,而是抛 `TypeError`** ——
    其签名为 `(text: str, api_key_env: str)`,实现首行 `os.environ.get(api_key_env)`
    对 `None` 抛 `TypeError: str expected, not NoneType`(实测)。
    故**严禁**写成 `redact_env_value(out, self._binding.api_key_env if self._binding else None)`
    这类统一调用,native 分支会直接崩。native 分支必须**不调用** `redact_env_value`。

  因此:
  - 该 detail 字符串被声明为 **resolver 内部敏感值**,`_resolve_developer()` 内
    除喂 `is_quota_error()` 外**零外流**(由 C 族锁定);
  - **不得**在代码注释、docstring 或执行报告中声称"adapter 已对原生 kimi 凭证脱敏"
    —— 本 WP 不知道原生凭证 env 名,声称即是假陈述;
  - rev2 的措辞「按现有 `_run` 的脱敏约定处理,不得裸返回」**作废**:
    `_run(..., redact_env=None)` 本身就是裸返回,该要求不可执行。
  - 若未来要真脱敏原生路径,须先确定原生 credential env 名与算法,属另一 WP。

**F8 `main()` 两处调用点都必须把 resolver 的 raise 变成交人(rev10 新增)**
`_resolve_developer()` 的三条 raise(S4 / S10 / S11)在 `main()` 里有**两个**
调用点,rev9 实现只在其中一个包了 `try/except`:
- `:461`(`probe=True`,主路径)**已有** `except ProbeFailedError` →
  `print("REDISPATCH_STOP: probe failed — 不重派,查根因")` + `return 0`;
- `:513`(`probe=False`,legacy `PROBE_CMD` 分支)**没有**。

`probe=False` 时 S5b 在探针前返回,故 S10/S11 不可达;**但 S4 在 S5b 之前**,
配置名写错即在该路径抛出。冻结要求:**两处调用点的异常处置语义一致**,
即 legacy 路径同样捕获 `ProbeFailedError` 并走同一 `REDISPATCH_STOP` 交人出口
(文案与退出码与主路径一致;不得新造文案、不得 `raise`、不得静默 `pass`)。

> 本 WP 的目标是「失败要交人,不要静默降级」。崩 traceback 虽然不静默,
> 也**不是交人** —— 它没给出 `REDISPATCH_STOP` 这个可操作信号,
> 且让 legacy 路径与主路径对同一个配置错误给出两种行为。

**F9 跨边界接线必须被锁(rev11 新增,关 r9 必改项 3/4)**
本 WP 的目标是「developer 探针失败不得静默换 adapter」。
除 resolver 内部决策外,**两处跨边界接线**同样能单独击穿该目标,必须各自承重:

1. **`main()` 调 resolver 的参数契约**:主路径必须 `probe=True`、
   legacy 路径必须 `probe=False`、两处都必须 `repo=repo_root`(即 `main_repo()`)。
   `probe=True → False` 会**整体关闭生产注入探针**;`repo` 改别处会破坏 F5 的
   单一配置权威。由 **D6** 锁定。
2. **默认 registry 的 key→class→binding 组合**:不传 `registry` 时,
   `"kimi"` key 必须构造 `KimiAdapter`、`"claude"` key 必须构造 `ClaudeAdapter`,
   且构造时收到的 binding 必须与 `resolve_role_binding()` 返回的对象 **`is` 同一个**
   (不得丢弃 binding 使真实 adapter 退回 native 路径)。
   `"kimi"` key 构造 `ClaudeAdapter` **就是本 WP 要禁止的静默换 adapter**。
   由 **D7** 锁定。

> 编排者 rev11 冻结前实测:上述两条各自单改一处,**全量 838 passed 全绿**。
> 这不是覆盖洁癖,是两条已证实的假绿面。

## 承重测试与必须转红的变异(矩阵式,rev7 重写)

> rev7 结构性变化:r5 Q10(a) 判定「逐条追加编号」的边际收益已转负,
> 本节从 18 条编号不变式重写为**轴 × 实例**的参数化矩阵。
> 轴:primary ∈ {kimi, codex(非 kimi 代表)};binding ∈ {native(`None`), bound};
> outcome ∈ {通过, 额度+有 fallback, 额度+无 fallback, 非额度},
> 外加探针前的未知名前置支(S4)。oracle 三类:不换 adapter / 结局与状态贯通 /
> 零外流。旧编号映射见 §「rev7 相对 rev6 的变更」。
>
> 每条 M-* 仍以**四元组**冻结:目标函数 / 原表达式(逐字)/ 变异表达式(逐字)/
> 承重测试(**参数化条目须点名承重实例**)。执行者不得自选位点或措辞;
> 预期实现中找不到原表达式 → 立即 BLOCKED,不得近似施加。
> **rev7 取消全部守卫互补与连带红记账**(见 §DoD 的硬验收口径与附注 12)。

**F6 冻结实现的决策位点表(`probe=True` 子图 + S5b 的 `probe=False` 提前返回;**
**变异锚点全集,实现完成后逐字存在;r6 必改项 2)**:

```python
adapter_name, binding = resolve_role_binding("developer", repo=repo)      # S1
fallback_binding = resolve_role_fallback_binding("developer", repo=repo)  # S2
quota_patterns = load_quota_patterns(repo)                                # S3
if adapter_name not in registry:                                          # S4
    raise ProbeFailedError("unknown developer adapter")
adapter = registry[adapter_name](binding)                                 # S5
if not probe:                                                             # S5b
    return adapter, reasons, False
ok, probe_output = adapter.probe_injection_detail()                       # S6
if ok:                                                                    # S7
    return adapter, reasons, False
if is_quota_error(probe_output, quota_patterns):                          # S8
    if fallback_binding is not None:                                      # S9
        return registry[adapter_name](fallback_binding), reasons, True
    raise ProbeFailedError("probe failed: quota, no fallback")            # S10
raise ProbeFailedError("probe failed: other")                             # S11
```

> S4 由 rev7 从「其余」拆出(r5 Q8):未知名失败发生在**探针之前**,
> 没有 `probe_output`,不参与额度分流,异常文案固定且不回显配置值;
> rev8 起 A3 还直接锁该支的 stdout/stderr 零回显。
> **S5b 由 rev8 补出**(r6 必改项 2):F5 的签名保留 `probe` 形参,
> must-stay-green 第 5 项要求 `probe=False` 不探针直接返回首选;
> 没有这一行,位点表与该要求不闭合。S5b 由 B5 直接锁定。

**测试环境公共约定**:resolver 层测试(A/B/C 族与 D3/D4)用 stub adapter +
monkeypatch `redispatch.resolve_role_binding` / `resolve_role_fallback_binding`
注入场景,不真发子进程;registry 一律注入 `kimi` / `claude` / `codex`
三个**工厂与探针均带计数**的 stub。「所有非首选工厂计数 0」指
registry 内除首选键外**每一个**工厂的工厂计数与探针计数均为 0。

### A 族:不换 adapter(本 WP 唯一目标的直接承重)

- **A1 非额度 STOP 支不换 adapter**
  `test_no_adapter_switch_on_nonquota_stop[primary]`,primary ∈ {kimi, codex}:
  - monkeypatch `resolve_role_binding` → `(primary, binding)`;
    `resolve_role_fallback_binding` → `None`;
    首选 stub 探针恒失败,输出**非额度**文本(如 `compile error`)。
  - 断言:抛 `ProbeFailedError`,`str(exc) == "probe failed: other"`;
    首选工厂计数 1;**所有非首选工厂计数 0**。
  - **M-A1** 目标函数:`redispatch._resolve_developer` @ **S11**
    原表达式:`raise ProbeFailedError("probe failed: other")`
    变异表达式:`return registry["claude"](None), reasons, False`
    承重实例:**[kimi] 与 [codex] 都必须转红**(无条件替换对两个首选都成立
    —— 这正是参数化取代守卫之处,见附注 12)。

- **A2 额度命中且无 fallback 的 STOP 支不换 adapter**(关 r5 必改项 1)
  `test_no_adapter_switch_on_quota_stop[primary]`,primary ∈ {kimi, codex}:
  - 同 A1,但探针输出含 `DEFAULT_QUOTA_PATTERNS` 可命中的额度措辞
    (如 `insufficient balance`),fallback 为 `None`。
  - 断言:抛 `ProbeFailedError`,`str(exc) == "probe failed: quota, no fallback"`;
    首选工厂计数 1;所有非首选工厂计数 0。
  - **M-A2** 目标函数:`redispatch._resolve_developer` @ **S10**
    原表达式:`raise ProbeFailedError("probe failed: quota, no fallback")`
    变异表达式:`return registry["claude"](None), reasons, False`
    承重实例:**[kimi] 与 [codex] 都必须转红**。
  > r5 的漏网实现(`if adapter_name != "kimi": return registry["kimi"](None), ...`
  > 落在本支)会被 **[codex] 实例的 kimi 计数断言**直接杀死。

- **A3 未知名前置支:一个工厂都不许造**(关 r5 Q8)
  `test_unknown_adapter_builds_nothing`:
  - monkeypatch `resolve_role_binding` → `("no-such-adapter-SENTINEL4", None)`
    (rev8:未知名**自带哨兵**,使「配置值回显」可观测)。
  - 断言:抛 `ProbeFailedError`,`str(exc) == "unknown developer adapter"`
    (**精确相等** —— 证明原始配置值未被回显进异常);
    **capsys 捕获的 stdout 与 stderr 均不含 `no-such-adapter-SENTINEL4`**
    (rev8 新增,关 r6 必改项 1 的 S4 半:配置原文也不得打印);
    **registry 内全部三个工厂计数均为 0**(首选名不在 registry,一个都不许造)。
  - **M-A3** 目标函数:`redispatch._resolve_developer` @ **S4**
    原表达式:`raise ProbeFailedError("unknown developer adapter")`
    变异表达式:`return registry["kimi"](None), reasons, False`
    承重测试:A3(换派面)。
  - **M-A3b** 目标函数:`redispatch._resolve_developer` @ **S4**(同位点另一面)
    原表达式:`raise ProbeFailedError("unknown developer adapter")`
    变异表达式(两行,逐字):
    ```python
    print(adapter_name)
    raise ProbeFailedError("unknown developer adapter")
    ```
    承重测试:A3(配置值外流面,capsys 断言转红)。
  > M-A3 与 M-A3b 同位点不同面(换派 vs 外流),分别施加、分别记红。

### B 族:结局与状态贯通

- **B1 额度+有 fallback 走同一 registry key 的单跳 flash**
  `test_quota_flash_returns_same_registry_key[primary]`,primary ∈ {kimi, codex}:
  - 首选 stub 探针恒失败、输出含额度措辞;`fallback_binding` 为 flash binding。
  - 断言:正常返回,`fallback_applied is True`;返回 adapter 由**首选工厂**构造
    —— 首选工厂计数 **2**(S5 探针构造 + S9 flash 构造),**最后一次**调用实参
    `is fallback_binding`;[codex] 实例额外断言 kimi 工厂计数 0。
  - **M-B1** 目标函数:`redispatch._resolve_developer` @ **S9**
    原表达式:`registry[adapter_name](fallback_binding)`
    变异表达式:`registry["kimi"](fallback_binding)`
    承重实例:**[codex]**([kimi] 实例下两者等价,保持绿是预期,记为信息,
    不构成失败)。
  > 计数口径(rev6 修正 3,r5 Q5 复核充分):同一工厂被调两次是正确实现,
  > 实参断言必须限定「最后一次」。

- **B2 探针输出确实被消费者读到** `test_probe_output_is_read_by_consumer`:
  - 同一 kimi 首选 stub,仅改探针**输出文本**(额度 ↔ 非额度),`ok` 恒 False;
    断言两次结局不同(flash 返回 vs `ProbeFailedError`)。
  - **M-B2a** 目标函数:`redispatch._resolve_developer` @ **S8**
    原表达式:`is_quota_error(probe_output, quota_patterns)`
    变异表达式:`False`
    承重测试:B2(额度输入与非额度输入的结局变得相同 → 红)。
  - **M-B2b** 目标函数:`redispatch._resolve_developer` @ **S8**(同行不同面)
    原表达式:`is_quota_error(probe_output, quota_patterns)`
    变异表达式:`is_quota_error("", quota_patterns)`
    承重测试:B2。
  > 两条变异同一行但不同面(谓词恒假 vs 入参置空),分别施加、分别记红。
  > 变异点必须在 `_resolve_developer()` 这个**消费者**处,不得挂在
  > `KimiAdapter.probe_injection_detail()` 上(stub 碰不到生产 kimi)。

- **B3 探针阶段已跳 flash 后 dispatch 不得再 flash**
  `test_probe_stage_flash_disables_dispatch_flash`:
  - `main()` 装配(`REDISPATCH_DRY_RUN=1`,不真派发、不触网),monkeypatch
    `_resolve_developer` 返回 `(_StubDev(), [], True)`;断言传给
    `_dispatch_with_quota_fallback` 的 `fallback_binding is None`;
    覆盖 `_resolve_developer → main → _dispatch_with_quota_fallback` 全链。
  - **M-B3** 目标函数:`redispatch.main`
    原表达式:`fallback_binding=None if fallback_applied else fallback_binding`
    变异表达式:`fallback_binding=fallback_binding`
    承重测试:B3。

- **B4 通过支的回退标志为 False** `test_fallback_flag_false_on_pass`:
  - 首选 stub 探针通过;断言返回三元组第三元 `is False`。
  - **M-B4** 目标函数:`redispatch._resolve_developer` @ **S7**
    原表达式:`return adapter, reasons, False`
    变异表达式:`return adapter, reasons, True`
    承重测试:B4。

- **B5 `probe=False` 不探针直接返回首选**(rev8 新增,关 r6 必改项 2)
  `test_probe_false_returns_primary_without_probing`:
  - 以 `probe=False` 调用;registry 三个计数 stub,首选 stub 的探针
    **若被调用即记录**(计数即证据)。
  - 断言:正常返回 `(首选 adapter, reasons, False)`;**首选工厂的探针计数为 0**;
    所有非首选工厂计数为 0。
  - **M-B5** 目标函数:`redispatch._resolve_developer` @ **S5b**
    原表达式:`if not probe:`
    变异表达式:`if False:`
    承重测试:B5(删掉提前返回后首选 stub 被探针,探针计数 0→1 → 红)。

- **B6 legacy `probe=False` 路径的 S4 raise 必须被 `main()` 接成交人**
  (rev10 新增,关实现评审 Finding 1)
  `test_legacy_path_unknown_adapter_stops_not_crashes`:
  - **不得** monkeypatch `_resolve_developer` —— 否则真实 S4 不穿过 `main()`,
    那正是 D5/B3 漏掉这条的原因;改为 monkeypatch
    `redispatch.resolve_role_binding` 返回带哨兵的未知名
    `("no-such-adapter-SENTINEL6", None)`;
  - 设 `PROBE_CMD` 走 legacy 分支(使 `:513` 的 `probe=False` 调用发生),
    并设 `REDISPATCH_DRY_RUN=1` 不真派发、不触网;
  - **不得复用现形态的 `_stub_io()`**:该 helper 自身
    (`tests/test_redispatch_quota_fallback.py:35`)会 monkeypatch
    `_resolve_developer`,直接抵消本条的全部意义。必须给 helper 加
    `stub_resolver: bool = True` 开关并以 `stub_resolver=False` 调用,
    或为 B6 单独装配其余 I/O stub(两种都可,但 resolver 必须是真的)。
  - 断言**四项**(rev11 按 r9 必改项 1 加固):
    ① `main()` **返回 0**(不抛异常、不非零退出);
    ② **`_dispatch_with_quota_fallback` 调用次数为 0** —— 用 spy/bomb 替换,
       被调到即失败。这是「接住后**立即停止**」的控制流 oracle,
       缺它则 `except: print(STOP); pass` 可以三项全绿却继续往下派发(r9 实证);
    ③ capsys 的 stdout **精确等于**那一行 STOP 文案(收紧为相等,不是包含),
       防 STOP 之后继续打印 dry-run JSON;
    ④ stdout/stderr **均不含**哨兵 `no-such-adapter-SENTINEL6`
    (S4 的零外流面在 `main()` 边界同样成立)。
  - **冻结实现形态(canonical,逐字)**:legacy 调用点必须写成
    ```python
        try:
            adapter, _, fallback_applied = _resolve_developer(repo=repo_root, probe=False)
        except ProbeFailedError:
            print("REDISPATCH_STOP: probe failed — 不重派,查根因")
            return 0
    ```
    **不得**抽 helper、**不得**写 `as exc`、**不得**改换行、**不得**把文案提成常量
    —— 否则下面两条变异的锚点逐字不匹配即判 BLOCKED(rev9 的 M-B3 已重演过一次)。
  - **M-B6a**(rev11,替代整块锚点)目标函数:`redispatch.main` @ legacy 调用点
    原表达式:`        except ProbeFailedError:`
    变异表达式:`        except RuntimeError:`
    承重测试:B6(`ProbeFailedError` 不再被接住、穿出 `main()` → 红)。
  - **M-B6b**(rev11)目标函数:`redispatch.main` @ legacy 调用点
    原表达式(该 `except` 块内的 `return 0`,逐字两行):
    ```python
            print("REDISPATCH_STOP: probe failed — 不重派,查根因")
            return 0
    ```
    变异表达式:
    ```python
            print("REDISPATCH_STOP: probe failed — 不重派,查根因")
            pass
    ```
    承重测试:B6(接住却不停止 → 断言②的 dispatch bomb 被调到 / 断言③出现
    额外 dry-run 输出 → 红)。
  > **为何拆两条**:M-B6a 锁「是否接住」,M-B6b 锁「接住后是否立即停止」。
  > 两条锚点都是单行/两行的稳定形态,比整块五行锚点抗重写。
  > M-B6 与 M-A3/M-A3b 不同层:后两条锁 resolver **是否 raise**,
  > M-B6 锁 `main()` **是否接**。resolver 层全绿不蕴含 `main()` 层已接 ——
  > 这正是 rev9 漏掉 Finding 1 的机理。

### C 族:零外流(全部按 binding 参数化)

> 哨兵约定:native 实例用字面量 `NATIVE_EGRESS_SENTINEL`,bound 实例用
> `BOUND_EGRESS_SENTINEL`,两者字面值互不相同;均经 stub 的
> `probe_injection_detail()` **返回值**注入(不真发子进程)。
> adapter 层的真实脱敏由 C4 单独锁定;resolver 层的职责是「拿到什么都不能外吐」。

- **C0 通过支零外流**(rev8 新增,关 r6 必改项 1 的 S7 半)
  `test_zero_egress_on_probe_pass[binding_kind]`,binding_kind ∈ {native, bound}:
  - 首选 stub 探针**通过**(`ok=True`),其 `probe_output` 含哨兵
    (native 实例 `NATIVE_EGRESS_SENTINEL`,bound 实例 `BOUND_EGRESS_SENTINEL`);
  - 断言:正常返回首选 adapter、`fallback_applied is False`;
    返回的 `reasons` **每个元素**、capsys 捕获的 stdout/stderr 均不含哨兵。
  > 通过支的输出仍是 `probe_output`,F7 的「唯一用途是喂 `is_quota_error`」
  > 不以探针成功为例外 —— 「不是失败输出」推不出「允许输出」(r6 Q2)。
  - **M-C0** 目标函数:`redispatch._resolve_developer` @ **S7**
    原表达式(两行,逐字):
    ```python
    if ok:
        return adapter, reasons, False
    ```
    变异表达式(三行,逐字):
    ```python
    if ok:
        print(probe_output)
        return adapter, reasons, False
    ```
    承重实例:**[native] 与 [bound] 都必须转红**。

- **C1 可返回支(额度+有 fallback)零外流**
  `test_zero_egress_on_quota_flash_return[binding_kind]`,binding_kind ∈ {native, bound}:
  - 构造进入 B1 同一路径(额度措辞 + fallback 非空),探针输出含哨兵;
    native 实例 binding 为 `None`,bound 实例 binding 为一个 stub `ProviderBinding`。
  - 断言:返回三元组的 `reasons` **每个元素**、capsys 捕获的 stdout/stderr
    均不含哨兵;并断言 `fallback_applied is True`(证明确实走了可返回支,
    防空路径假过)。
  - **M-C1** 目标函数:`redispatch._resolve_developer` @ **S6 之后插入一行**
    原表达式:`ok, probe_output = adapter.probe_injection_detail()`
    变异表达式(两行,逐字):
    ```python
    ok, probe_output = adapter.probe_injection_detail()
    reasons.append(probe_output)
    ```
    承重实例:**[native] 与 [bound] 都必须转红**。

- **C2 额度+无 fallback STOP 支零外流**(关 r5 必改项 2 的 bound 半)
  `test_zero_egress_on_quota_stop[binding_kind]`,binding_kind ∈ {native, bound}:
  - 构造进入 A2 同一路径(额度措辞 + fallback 为 `None`),探针输出含哨兵。
  - 断言:`str(exc) == "probe failed: quota, no fallback"`(**精确相等**);
    capsys stdout/stderr 均不含哨兵。
  - **M-C2** 目标函数:`redispatch._resolve_developer` @ **S10**
    原表达式:`raise ProbeFailedError("probe failed: quota, no fallback")`
    变异表达式(两行,逐字):
    ```python
    print(probe_output)
    raise ProbeFailedError("probe failed: quota, no fallback")
    ```
    承重实例:**[native] 与 [bound] 都必须转红**。

- **C3 非额度 STOP 支零外流**
  `test_zero_egress_on_nonquota_stop[binding_kind]`,binding_kind ∈ {native, bound}:
  - 构造进入 A1 同一路径(非额度文本 + 哨兵)。
  - 断言:`str(exc) == "probe failed: other"`(**精确相等**);
    capsys stdout/stderr 均不含哨兵。
  - **M-C3** 目标函数:`redispatch._resolve_developer` @ **S11**
    原表达式:`raise ProbeFailedError("probe failed: other")`
    变异表达式:`raise ProbeFailedError(f"probe failed: other: {probe_output}")`
    承重实例:**[native] 与 [bound] 都必须转红**。

- **C4 bound detail 返回值本身不含密钥**(adapter 层直接 oracle)
  `test_kimi_bound_detail_redacts_api_key`:
  - 真实 `KimiAdapter(binding=<flash binding>)`;`monkeypatch.setenv` 使
    `binding.api_key_env` 指向哨兵密钥值;monkeypatch `subprocess.run` 让
    stdout **包含该哨兵**;调用 `probe_injection_detail()`;
    断言返回的 detail 串**不含**该哨兵,且**含** stdout 里另一段非密钥文本
    (防空变异假过)。
  - **M-C4** 目标函数:`KimiAdapter.probe_injection_detail`(bound 支)
    原表达式:`out = redact_env_value(out, self._binding.api_key_env)`
    变异表达式:`out = out`
    承重测试:C4。

### D 族:契约、前提与配置权威

- **D1 base 默认 bool 契约零回归** `test_base_default_probe_injection_returns_exact_bool`:
  - 在 `tests/test_injection_probe.py` 内定义**只继承 `Adapter`、不覆写
    `probe_injection` / `probe_injection_detail`** 的最小子类(实现四个抽象方法
    `capabilities` / `identity` / `probe` / `review`,已实测
    `Adapter.__abstractmethods__` 恰为这四个),`_binding` 为 `None`;
    令其 `probe()` 分别返回 `True` / `False`,断言
    `probe_injection() is True` / `is False`(**`is` 精确比较**,元组必红)。
  - **M-D1** 目标函数:`Adapter.probe_injection`(`adapters/base.py`)
    原表达式:`return self.probe_injection_detail()[0]`
    变异表达式:`return self.probe_injection_detail()`
    承重测试:D1。
  > 既有 10 条(`tests/test_injection_probe.py:50/61/70/77/93/103/112/127/137/144`)
  > 降为 must-stay-green:Claude/Codex/Kimi 都覆写了 `probe_injection()`
  > (`claude.py:126`、`codex.py:199`、`kimi.py:168`),它们**不可靠地**杀死
  > base 的变异;承重红证只认 D1。

- **D2 kimi 两条 detail 路径交出真实输出**
  `test_kimi_detail_returns_real_output[path]`,path ∈ {native, bound}:
  - 真实 `KimiAdapter` + monkeypatch `subprocess.run`(不真发网络),分别在
    `binding=None` 与 binding 非空下调用 `probe_injection_detail()`,断言返回的
    输出串确实包含被 stub 的 stdout 内容(不是 `""`)。
  - **M-D2** 目标函数:`KimiAdapter.probe_injection_detail`(native 支)
    原表达式:`return (proc.returncode == 0 and "PROBE_OK" in out, out)`
    变异表达式:`return (self.probe(), "")`
    承重实例:**[native]**。[bound] 实例的非空性由 C4 的「含另一段非密钥文本」
    断言间接锁定 —— 这是刻意的职责划分,不是遗漏。

- **D3 `roles_config` 来源已消失:冲突输入不能影响选择**
  `test_flattened_roles_cannot_select_adapter`:
  - `monkeypatch.setattr("agentic_loop.redispatch.resolve_role_binding",
    lambda role, *, repo=None: ("kimi", binding))`;
  - `monkeypatch.setattr("agentic_loop.redispatch.get_roles",
    lambda *a, **k: {"developer": ["claude"]}, raising=False)`
    —— **`raising=False` 必需**:F5 删掉 `redispatch.py:35` 的 import 后,
    正确实现里 `redispatch.get_roles` **不存在**,不加该参数 monkeypatch 直接
    `AttributeError`;
  - patch 的命名空间必须是 `agentic_loop.redispatch.get_roles`,不是
    `resolve_paths` 的(M-D3 在 `redispatch` 模块里以模块全局名调用);
  - 断言:kimi 工厂计数 1、claude 工厂计数 0、返回 adapter 是 kimi stub;
  - **签名精确断言**(同一测试内):
    ```python
    sig = inspect.signature(redispatch._resolve_developer)
    assert [(n, p.kind) for n, p in sig.parameters.items()] == [
        ("repo", inspect.Parameter.KEYWORD_ONLY),
        ("registry", inspect.Parameter.KEYWORD_ONLY),
        ("probe", inspect.Parameter.KEYWORD_ONLY),
    ]
    ```
    有序列表相等同时锁死参数名、顺序、kind;任何新增形参或
    `*args` / `**kwargs` 都会转红。
  - **M-D3** 目标函数:`redispatch._resolve_developer`,**两步逐字替换**:
    步 1:在模块级 import 块紧跟
    `from agentic_loop.resolve_paths import resolve_role_fallback_binding`
    之后新增一行 `from agentic_loop.resolve_paths import get_roles`;
    步 2:原表达式 `adapter_name, binding = resolve_role_binding("developer", repo=repo)`
    变异表达式(两行):
    ```python
    adapter_name = get_roles(repo).get("developer")[0]
    _, binding = resolve_role_binding("developer", repo=repo)
    ```
    承重测试:D3。
  > 已实测 `get_roles()["developer"] == ['kimi', 'claude']`(list),`[0]` 即首选名,
  > 无需辅助函数。变异后 `adapter_name` 变 `"claude"` → claude 工厂计数 0→1,必红。
  > 本条只证伪它所冻结的这一个展平入口;另一个展平入口的恢复靠 D4 与 diff review。

- **D4 resolver 三处取数收到同一个 `repo`** `test_all_config_reads_share_one_repo`:
  - spy 包住 `redispatch.resolve_role_binding` /
    `redispatch.resolve_role_fallback_binding` / `redispatch.load_quota_patterns`,
    记录每次收到的 `repo` 实参;以 `repo=tmp_path` 调用 `_resolve_developer`,
    断言三次记录**全等于** `tmp_path`(不是 `None`、不是 `main_repo()`)。
  - **M-D4** 目标函数:`redispatch._resolve_developer` @ **S2**
    原表达式:`resolve_role_fallback_binding("developer", repo=repo)`
    变异表达式:`resolve_role_fallback_binding("developer")`
    承重测试:D4。

- **D5 `main()` 的 fallback 取数收到 `repo_root`**
  `test_main_dispatch_fallback_binding_uses_repo_root`:
  - 复用 B3 的 `main()` 装配(`REDISPATCH_DRY_RUN=1`),monkeypatch
    `_resolve_developer` 返回 `(_StubDev(), [], False)`
    (**`fallback_applied=False`**,使 F6 的
    `fallback_binding=None if fallback_applied else fallback_binding` 原样透传,
    不与 B3 的面混淆);
  - spy 记录 `redispatch.resolve_role_fallback_binding` 每次收到的 `repo` 实参
    (位置与关键字都记);
  - 断言:`main()` 路径上该函数被调到(计数 ≥ 1),且每次 `repo == main_repo()`。
  - **M-D5** 目标函数:`redispatch.main`
    原表达式:`resolve_role_fallback_binding("developer", repo=repo_root)`
    变异表达式:`resolve_role_fallback_binding("developer")`
    承重测试:D5。
  > 不得以「`repo=None` 时解析器回落 `main_repo()`,结果一样」为由跳过:
  > 那是 `resolve_paths.py:360` 的偶然同值;断言打在**实参**上,不是解析结果上。

- **D6 `main()` 调 resolver 的参数契约**(rev11 新增,关 r9 必改项 3)
  `test_main_resolver_call_contract[path]`,path ∈ {main, legacy}:
  - spy `redispatch._resolve_developer`:**只记录**收到的 `repo` 与 `probe`,
    并返回安全 stub `(_StubDev(), [], False)`;
  - `path == "main"`:不设 `PROBE_CMD`,走 `:461`;
    断言唯一一次调用的 `repo == main_repo()` 且 **`probe is True`**;
  - `path == "legacy"`:设 `PROBE_CMD` 走 `:513`;
    断言唯一一次调用的 `repo == main_repo()` 且 **`probe is False`**;
  - 两实例都断言调用次数**恰为 1**(防两条路径都被走一遍)。
  > 这里 patch `_resolve_developer` 是**正当**的:本条的 oracle 正是
  > **跨边界的调用参数本身**,不是 resolver 内部行为。
  - **M-D6a** 目标函数:`redispatch.main` @ `:461`
    原表达式:`_resolve_developer(repo=repo_root, probe=True)`
    变异表达式:`_resolve_developer(repo=repo_root, probe=False)`
    承重实例:**[main]**(生产注入探针被整体关闭 → 红)。
  - **M-D6b** 目标函数:`redispatch.main` @ legacy 调用点
    原表达式:`_resolve_developer(repo=repo_root, probe=False)`
    变异表达式:`_resolve_developer(repo=repo_root, probe=True)`
    承重实例:**[legacy]**。
  - **M-D6c** 目标函数:`redispatch.main` @ `:461`
    原表达式:`_resolve_developer(repo=repo_root, probe=True)`
    变异表达式:`_resolve_developer(repo=iteration_dir, probe=True)`
    承重实例:**[main]**(F5 单一配置权威被破坏 → 红)。
  > 编排者实测:M-D6a 这一改(主路径 `probe=True`→`False`)在 rev10 实现下
  > **全量 838 passed 全绿** —— 这是 D6 必须存在的直接证据。

- **D7 默认 registry 的 key→class→binding 组合**(rev11 新增,关 r9 必改项 4)
  `test_default_registry_preserves_adapter_and_binding[primary]`,
  primary ∈ {kimi, claude}:
  - **不传 `registry`**,走真实 `_resolve_developer` 的默认 registry;
  - monkeypatch 模块内的 `KimiAdapter` / `ClaudeAdapter` 为**带构造计数的 spy class**
    (记录自己被构造的次数与收到的 `binding`);
  - monkeypatch `resolve_role_binding` 返回 `(primary, sentinel_binding)`;
  - **`probe=False`**(经 S5b 提前返回,保证不起任何子进程、不触网);
  - 断言:**只有与 key 同名的那个 class 被构造**(另一个构造计数为 0),
    且它收到的 binding 与 `resolve_role_binding()` 返回的对象 **`is` 同一个**。
  - **M-D7a** 目标函数:`redispatch._resolve_developer` 默认 registry 的 `"kimi"` 条目
    原表达式:`"kimi": lambda b: KimiAdapter(`
    变异表达式:`"kimi": lambda b: ClaudeAdapter(`
    承重实例:**[kimi]**(**本 WP 要禁止的静默换 adapter 本身**)。
  - **M-D7b** 目标函数:同上
    原表达式:`kimi_bin=os.environ.get("KIMI_BIN", "kimi"), binding=b)`
    变异表达式:`kimi_bin=os.environ.get("KIMI_BIN", "kimi"), binding=None)`
    承重实例:**[kimi]**(binding 被丢弃,真实 adapter 退回 native 路径 → 红)。
  > 编排者实测:M-D7a 这一改在 rev10 实现下**全量 838 passed 全绿**。
  > 「所有 resolver 测试都注入自定义 registry」把生产默认 registry 整个遮蔽了。

### CHAR-1 空配置折叠事实的锁定(characterization,无变异,不计入承重数)

对 `tmp_path` 下的**五种退化配置逐一参数化**(r6 Q8 附带意见:声称五种
就测五种):无 `.agentic/config.toml` / `[roles]` 为空 / `developer = []` /
`developer = ""` / developer 缺项而其他 role 存在。每种都断言
`resolve_role_binding("developer", repo=tmp) == ("kimi", None)` 且
`resolve_role_fallback_binding("developer", repo=tmp) is None`。
编排者实测五种退化配置(无 config / `[roles]` 空 / `developer = []` /
`developer = ""` / developer 缺项而其他 role 存在)一律折叠为 `("kimi", None)`,
根因在 `resolve_paths.py:364-367` 的 `_first_candidate(DEFAULT_ROLES.get(role))`。
本条锁定的是 **forbidden 文件**的既有行为,本 WP 不改它,故无本 WP 变异可绑;
若将来折叠语义改变,本条转红,迫使重审「`adapter_name` 恒非空」前提。
**产品决策(冻结)**:「原始空配置必须 STOP 而不是默认 kimi」不在本 WP 范围,
要那个语义须改 `resolve_paths.py`(forbidden),属升 CONSULT 的范围扩大。

### 必须保持绿集合(七项,防收紧过度杀伤合法路径)

- `test_project_config_primary_developer_stays_native`
- `test_project_config_resolves_flash_fallback`(**断言不动**,见 F4)
- `tests/test_bootstrap.py`(全文件)
- `tests/test_codex_gate_capability_merge.py`(全文件)
- `_resolve_developer(..., probe=False)` 的既有行为(不探针时直接返回首选)
- 配置首选探针**通过**时的正常路径
- `tests/test_injection_probe.py` 既有 10 条断言(D1 是增量,不替换)

## 交付物清单

- `src/agentic_loop/adapters/base.py`:新增非递归 `probe_injection_detail`,
  `probe_injection` 委托
- `src/agentic_loop/adapters/kimi.py`:覆写 `probe_injection_detail`,
  两条路径真实输出 + bound 路径脱敏
- `src/agentic_loop/redispatch.py`:`_resolve_developer` **删 `roles_config`**
  + 必填 `repo` + 单一权威 + 单一首选 + 原因分流 + 三元返回;
  `main()` 两处调用与 `fallback_binding` 贯通;
  **`main():538` 的 `resolve_role_fallback_binding` 补 `repo=repo_root`**(rev5);
  删除死 `get_roles` import
- `tests/test_redispatch_quota_fallback.py`:
  A1×2 / A2×2 / A3(双变异)/ B1×2 / B2 / B3 / B4 / B5 /
  C0×2 / C1×2 / C2×2 / C3×2 / C4 / D2×2 / D3 / D4 / D5 测试
  + `CHAR-1`(五 fixture 参数化)+ 三元返回与新签名的 stub 同步
- `tests/test_injection_probe.py`:D1(继承默认的精确 bool 断言,新增)
- 执行报告(§C 格式),含逐条变异红证 + F3 的生产/checkout 实测事实复述

## 完成定义(DoD)

- [ ] F1、F2、F3、F5、F6、F7 逐项实现(F4 已删除,`config.toml` 零改动)
- [ ] 承重矩阵的 **21 个测试条目 + CHAR-1** 全部存在并通过(rev10:B6;rev11:D6/D7);10 个双实例
      参数化条目(A1 / A2 / B1 / C0 / C1 / C2 / C3 / D2 / D6 / D7)的**两个实例**都断言到位
- [ ] **27 条具名变异各自使其四元组点名的承重测试(与承重实例)转红**
      (rev10:M-B6→rev11 拆为 M-B6a/M-B6b;rev11 新增 M-D6a/M-D6b/M-D6c/M-D7a/M-D7b)。
      报告逐条记录命令与输出;施加每条变异前先断言被变异的源文件确实
      与原文不同(如 `git diff --stat` 非空,杜绝空变异读成绿)
- [ ] 每条变异记账含四元组对应关系:目标函数 / 原表达式 / 变异表达式 /
      承重测试(与承重实例);凡预期实现中找不到所列原表达式的,
      **报 BLOCKED 而非近似施加**,并附当前实际代码片段
- [ ] **变异施加顺序(强制五步法)**:① 先把 F1/F2/F3/F5/F6/F7 实现完跑到
      全量绿(含必须保持绿集合),此前不得核对任何变异锚点(当前代码里本来
      就没有它们,此时检查只会得到无谓失配);② 对单条变异先定位并确认
      原表达式逐字存在,找不到才报 BLOCKED;③ 只施加这一条并证 diff 非空;
      ④ 跑该条具名承重测试确认转红,记录命令与输出;⑤ 恢复源文件
      (如 `git checkout -- <file>`)确认回绿再做下一条。**禁止叠加变异**
- [ ] **硬验收口径(rev7 简化,关 r5 必改项 3)**:**唯一硬验收是
      「具名承重测试的承重实例转红」**。rev5/rev6 的「对角线交叉记账」与
      「冻结连带红集合」整套机制**已删除**:参数化取代了守卫互补
      (同一无条件变异由两个实例共同承重,见附注 12),不再需要用连带绿
      证明位点分离。连带红的处理(rev8 修正,r6 必改项 4):
      五步法只跑具名承重测试,因此**只记录该次命令实际覆盖到的实例**;
      连带红讨论限于该测试自身的实例,不要求、也不允许为「列出全部连带红」
      去跑额外套件。任何连带红都不构成承重证据。
      例外规则一:若某条变异的**承重实例没有转红**,无论其他测试红绿如何,
      一律按五步法②报 BLOCKED,不得用其他测试的红替代。
      例外规则二(**等价控制实例**,rev8 新增,关 r6 必改项 3):
      被四元组显式声明为**等价控制**的实例 —— 当前仅有 **M-B1 的 [kimi]**
      (该实例下原表达式与变异表达式等价)—— **必须保持绿**;
      它一旦转红,说明变异不纯、测试参数隔离错误或施加范围错误,
      **报 BLOCKED**,不得作为信息忽略。等价控制实例清单即此一处,
      将来新增变异时若存在同类实例,须在同一四元组里显式声明
- [ ] 「必须保持绿集合」七项全绿,按名逐一记录结果
- [ ] **legacy `PROBE_CMD` 路径(`main():532`)有定向测试覆盖三元解包**
      (该路径只在 legacy 分支运行,漏改会在生产运行时才崩)
- [ ] **F8:`main()` 两处调用点的异常处置语义一致**,legacy 路径的
      `ProbeFailedError` 同样走 `REDISPATCH_STOP` 交人出口
      (由 **B6** / **M-B6a** / **M-B6b** 锁定);B6 **不得** monkeypatch
      `_resolve_developer`,且必须带 `_dispatch_with_quota_fallback` 零调用 oracle
- [ ] **F9:两处跨边界接线各自承重** —— `main()→resolver` 的 `probe`/`repo` 参数契约
      (**D6** + M-D6a/b/c)与默认 registry 的 key→class→binding 组合
      (**D7** + M-D7a/b)。两者在 rev10 实现下均**全量全绿可假绿**,编排者已实测,
      故这两条是硬性 DoD 项,不得以「diff review 已看过」替代
- [ ] `bootstrap_cmd.py`、`adapters/claude.py`、`adapters/codex.py`、
      `resolve_paths.py`、`quota_fallback.py`、`secret_redaction.py`、
      `.agentic/config.toml` diff 均为空
- [ ] 全量:`env -u AGENTIC_PYTHON GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch
      GIT_CONFIG_VALUE_0=main PYTHONPATH=src python3.11 -m pytest tests -q` 全绿,
      通过数 ≥ 本 WP base commit 实测基线。该基线由编排者 2026-10-09 在
      `715232d` 实测为 **807 passed, 4 skipped**(命令同上),并于 2026-10-10
      在被审 worktree 复测复现(`src`/`tests` 与 base 逐字节相同)。
      执行者须在自己的 worktree 复测该命令并记录实际数字,
      **不得从别的 WP brief 抄数字**
- [ ] **无测试退化**(通过数门禁单独不足 —— 新增测试会抵消被删旧测试)。
      报告须附 `git diff --stat` 与测试文件 diff review,逐条说明
      **被删除或被改弱的既有测试断言**;既有断言的删除/放宽**一律报 BLOCKED**,
      不得以「全量通过数未降」为由自行放行
- [ ] 无 `forbidden_paths` 写入
- [ ] 无生产 DB 写入、无网络(测试全用 stub,不得真打 DeepSeek/kimi)、无推送
- [ ] commit message 规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注:已知陷阱

1. **测试环境**:必须 `env -u AGENTIC_PYTHON`,否则 `AGENTIC_PYTHON` 漏进子进程
   shell 绕过 python3 stub 产生假失败;`python3.11` 无 agentic_loop,须 `PYTHONPATH=src`;
   临时仓缺 `main` 分支会让 4 个三签测试假失败,用进程级
   `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch GIT_CONFIG_VALUE_0=main` 消除。
   **不要改 git config。**
2. **口径权威源**:额度判定只有 `quota_fallback.py` 一份,禁止在 redispatch 里
   写第二份可执行判定(规范 §5.3)。
3. **评级不变式**:别"顺手"给被审 checkout 的 `roles.developer` 绑 `provider` ——
   那会把独立性评级从 weak-attested 翻成 degraded-weak。DESIGN §2 已说明;
   `config.toml` 整体在 `forbidden_paths`。
4. **纯函数优先**:`probe_injection_detail` 的输出口不要夹带 `now()`;它本身必须
   跑子进程(这是它的职责),但不得写文件、不得读 config。
5. **脱敏**:见 F7 的**分路政策** —— bound 路径硬性脱敏(C4 直接锁定);
   native 路径声明为 resolver 内部敏感值、零外流,**不得声称已脱敏**。
6. **递归**:F1 的默认实现绝不能回调 `probe_injection()`。
7. **配置权威**:`main_repo()` 是权威,不得改成"当前 worktree 配置是生产权威" ——
   那是语义变更,须 CONSULT,不在本 WP 授权内。
8. **冲突预告**:`wip/kimi-managed-k3-oauth` `1aa97e3` 也改 `probe_injection()`。
   本 WP 不管它;若后续并入由那一侧和解。
9. **空配置折叠是既有事实,不是本 WP 的缺陷**:见 `CHAR-1`。实测五种退化配置
   一律折叠为 `("kimi", None)`。本 WP 依赖"`adapter_name` 恒非空"这一前提,
   并用 `CHAR-1` 把该前提钉成测试;**不得**为了"空配置 STOP"去改 `resolve_paths.py`。
10. **同一行不同面的成对变异(如 M-B2a / M-B2b)**:一个把谓词置假,一个把
    入参置空。两条都要单独施加、单独记红,不得合并记账。
11. **`raise` 支上的 `reasons` 不可观测(全局记账纪律)**。`reasons` 是
    `_resolve_developer()` 的函数局部变量:正常返回时它作为三元组第二元交到
    调用方手里,**可以**做 oracle;一旦函数以 `raise` 收场,该列表随栈帧丢弃
    (brief 没有任何条款要求把它挂到异常上,`ProbeFailedError` 类体也是空的,
    `redispatch.py:98`)。因此 raise 支上「断言 `reasons` 不含哨兵」是空断言。
    纪律:**要测 `reasons` 就绑到能正常返回的路径**(C1);**要测 raise 支,
    oracle 只能是异常文案与 capsys**(C2 / C3)。
12. **参数化取代守卫(rev7)**。rev5/6 需要 `binding is None` / `is not None`
    互补守卫,是因为每条不变式只覆盖一个 binding 实例,无条件泄漏会同时红两条、
    无法归因。rev7 把 egress 与不换 adapter 两族按实例参数化后,**同一测试的
    两个实例本来就该同时红**,无条件变异成为正确形态,守卫与连带红记账随之
    失去存在理由。执行者**不得**自行给变异加守卫「优化」—— 那会让两个实例中
    的一个保持绿,直接违反该变异的承重实例要求。
13. **`main()` 与 resolver 是两个配置权威面**。F5 让 `_resolve_developer()`
    内部三处取数共用一个 `repo`(D4),但 `main():538` 的
    `resolve_role_fallback_binding` 是**第四处**,由 D5 单独看守。
    两处在生产里恰好同值(`resolve_paths.py:360` 的
    `repo = repo or main_repo()`),那是偶然,不是保证;断言打在实参上。
14. **「不换 adapter」不等于「不换成 claude」**。本 WP 的唯一目标是
    「探针失败不得前进到另一个 adapter」,不是「不得前进到 claude」。
    生产默认 registry 恰好只有 `kimi`/`claude` 两键,这是巧合。
    A 族断言一律为「**所有非首选工厂**计数为 0」,并由 [codex] 参数化实例
    把该泛化钉成结构性事实;执行者不得把任何一条简化回只断 claude。
15. **egress oracle 的格子自查表(rev8 修正)**。F6 决策位点与零外流 oracle 的对应:
    - S4 未知名前置支:无 `probe_output`,但有**配置值回显面** → **A3**
      (哨兵未知名 + 文案精确 + capsys,rev8 起);文案不再只是「顺带锁」;
    - S5b `probe=False`:不探针,无 `probe_output`,无外流面(B5 锁不探针本身);
    - S7 通过支:输出仍是 `probe_output`,「成功」不构成外流豁免 → **C0**
      (双实例,rev8 新增);
    - S9 额度+有 fallback(可返回)→ **C1**(双实例);
    - S10 额度+无 fallback(raise)→ **C2**(双实例);
    - S11 非额度(raise)→ **C3**(双实例);
    另有 C4 直接锁 bound detail 返回值的脱敏。
    **将来若 F6 新增决策位点,必须同时更新本表并配上对应 oracle。**

## Acceptance tests

本段与上文「承重测试与必须转红的变异(矩阵式,rev7 重写)」「交付物清单」
「完成定义(DoD)」同义,**非另一份口径**;仅为派发闸 `dispatch_lint` 的
模板节名识别而设(现行模板与 kqff WP-01 先例均带此三别名节)。

## Allowed and forbidden paths

本段与上文「范围」一节的 allowed_paths / forbidden_paths 完全同义,非另一份口径。

## Completion definition

本段与上文「完成定义(DoD)」一节同义,非另一份口径。

# WP-12: 缺信号不等于冻结，退出码不等于成功

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

让健康监测在「信号根本没采到」时说 `UNKNOWN`，而不是并进冻结判定报假警（B2）；
让「执行成功」的判据不再是不可信的进程退出码（B6）；顺手关掉一个会制造假失败的
测试仪表（B3）。

## 背景

缺陷 B2、B6、B3（`WP-08-candidate.md` §B2 §B6 §B3）。三者合成一个 WP，
因为它们是同一个故事的三段：**编排者用来判断执行者状态的仪表全都可能说谎。**

**B2 —— 缺信号被并进冻结判定。** `kimi-health.sh` 的冻结判据是「输出尾内容哈希
未变 **且** git dirty 未变」（`kimi-health.sh:124-133`）。本轮用
`KimiAdapter.implement()`（`subprocess.run(stdout=PIPE)`，全程缓冲）派发，
`.out` 文件始终 0 字节，`tail_hash` 恒为常量，两个信号里的一个从一开始就是死的；
只剩 git dirty，而 kimi 写一个大文件期间 dirty 本来就不变 →
连报 `FROZEN_3m` / `FROZEN_7m` 假警。假警的真实代价不是浪费一次仲裁，
而是**训练人忽略告警**。

> 实现细节，改之前先看清：`tail_hash()`（`kimi-health.sh:53-57`）在文件**不存在**时
> 返回硬编码常量 `d41d8cd98f00b204e9800998ecf8427e`，那是 MD5 的空摘要（32 hex），
> 而函数体实际用的是 `shasum`（SHA-1，40 hex）。两者长度不同因而永不碰撞，
> 所以「文件不存在」和「文件存在但为空」目前确实能区分开——但这是**巧合**，
> 不是设计。文件存在且为空时得到的是真正的 SHA-1 空摘要
> `da39a3ee5e6b4b0d3255bfef95601890afd80709`。本 WP 要处理的正是后一种情况
> （buffered 派发下文件被创建但一直是 0 字节）。顺手把这个跨算法哨兵值改干净。

**B6 —— rc 假失败。** WP-03 的 rework 派发用了 `set -o pipefail` + `${PIPESTATUS[0]}`
（B4 已修），拿到 rc=1；但 stdout 里 kimi 明确输出 `[STATUS] DONE` + `[COMMIT] 78b33f2`，
且 worktree 里该 commit 确实存在、工作区干净、改动完全正确。rc=1 是假失败。
而 `adapters/kimi.py:132` 是 `dispatched=proc.returncode == 0`。
与 B4 合起来看更糟：**rc 既可能假 0（被 tee 吞）也可能假 1（kimi 自身），
两个方向都不可信。**

**B3 —— 仪表打坏被测物。** `tests/test_gate_runner_shell.py` 与
`tests/test_init_githooks.py` 会在 PATH 上装一个 stub `python3`；设
`AGENTIC_PYTHON=python3.11` 会绕过 stub。实测带该环境变量跑这两个文件 1 failed，
不带则 2 passed。本轮编排者据此得出「门跑出 6 个失败，kimi 报 4 个」的差异并怀疑
执行者漏报——**实际是编排者的仪表把测试搞坏了，kimi 报的 4 是对的。**

## 范围

**allowed_paths**
- `src/agentic_loop/wrappers/kimi-health.sh`
- `src/agentic_loop/adapters/base.py`
- `src/agentic_loop/adapters/kimi.py`
- `src/agentic_loop/adapters/claude.py`
- `AGENTS.md`
- `src/agentic_loop/templates/AGENTS.md.tmpl`
- `tests/test_health_unknown_no_output.py`
- `tests/test_adapter_dispatched_semantics.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`
- `src/agentic_loop/wrappers/preflight.sh`（属 WP-11）
- `src/agentic_loop/wrappers/quality-gate.sh`（属 WP-13）
- `tests/test_gate_runner_shell.py`（见交付物 5 的说明：**只读不改**）
- `tests/test_init_githooks.py`（同上）
- 其余一切未在 allowed 列出的路径

> 本 WP 属 `lane-gate`，排在 WP-11 之后**串行**：两者同碰 `wrappers/` 与
> `AGENTS.md` / `AGENTS.md.tmpl`，并发必撞。不得与 WP-11 并发。

## 输入

- 依赖的上游 WP 产出：WP-11 必须先 MERGED（同碰 `AGENTS.md` 与 `AGENTS.md.tmpl`）
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B2 §B3 §B6
- 现状代码：`kimi-health.sh:53-57`（`tail_hash`）与 `:118-152`（冻结累计与契约行）；
  `adapters/base.py:120-140`（`ImplementResult` 定义与 `dispatched` 注释）；
  `adapters/kimi.py:132`、`adapters/claude.py:99`
- 契约文档：`AGENTS.md` §4.2（health 的契约行与派发判据）

## 交付物清单

**B2 —— 缺信号要说 UNKNOWN**

1. `kimi-health.sh` 新增一个契约首 token `UNKNOWN_NO_OUTPUT`，在输出文件不存在
   **或**内容为空（尾哈希等于空内容摘要）时发出，**不进入冻结累计**
   （即该轮不递增 `frozen`，也不因此清零——语义是「这一轮没采到信号」）。
2. 顺手修掉上文点出的跨算法哨兵值：文件不存在与文件为空都应走同一条
   `UNKNOWN_NO_OUTPUT` 路径，不需要靠两个不同算法的空摘要来区分。
3. `AGENTS.md` §4.2 与 `AGENTS.md.tmpl` 同步：契约行首 token 列表加入
   `UNKNOWN_NO_OUTPUT` 并写明编排者的应对（**不是**告警，是「这个派发形态不满足
   health 的前置条件，去修派发形态」）；同时写明派发必须是 `| tee <log>` 的
   **流式**形态，buffered 捕获（`subprocess.run(stdout=PIPE)`）不满足 health 前置条件。

**B6 —— rc 不再当成功判据**

4. `ImplementResult.dispatched` 的语义改为「进程已启动」而非「执行成功」：
   - `adapters/base.py` 的字段注释（现为「派发命令是否成功发起」，语义其实已对，
     但 kimi/claude 的实现把它当 rc==0 用）写清楚它**不**表示执行成功；
   - `adapters/kimi.py:132` 与 `adapters/claude.py:99` 的 `dispatched=proc.returncode == 0`
     改为反映「进程确实起来了」，rc 仍**记录**在结果里供辅助参考，但不作为
     `dispatched` 的判据。
   > `claude.py` 也在 allowed 里，因为它有同一行同一模式；只改 kimi 会让两个
   > adapter 的同名字段语义分叉，那比不改更糟。
   > 若你发现改 `claude.py` 会牵连超出本 WP 的行为，**停手**并在 `[CONCERNS]` 说明，
   > 只改 kimi 并把分叉记为遗留。
5. `AGENTS.md` §4.2 写明成功判据是「stdout 末尾有执行报告且 `[STATUS]` 为
   `DONE`/`DONE_WITH_CONCERNS`」+「worktree 里 commit 确实存在」，由编排者独立核验；
   rc 只作辅助信号记录，不用于分支决策。

**B3 —— 文档层关掉假失败**

6. `AGENTS.md` §9（仓库测试命令）写明：`AGENTIC_PYTHON` 只管 wrapper 自身对
   Python 模块的调用，**跑全量测试时不得设置**，理由是
   `tests/test_gate_runner_shell.py` 与 `tests/test_init_githooks.py` 会在 PATH 上
   装 stub `python3`，该环境变量会绕过 stub 制造假失败。
   > B3 的另一个修法是「让那两个测试对 `AGENTIC_PYTHON` 免疫」。本 WP 冻结的是
   > **文档修法**，那两个测试文件在 forbidden_paths 里、只读不改。
   > 理由：改测试去适配一个诊断用环境变量，是让被测物迁就仪表；而这个变量本来
   > 就只该管 wrapper。若你认为免疫改法更好，写进 `[CONCERNS]`。

## 完成定义（DoD）

- [ ] **characterization test 先行（B2）**：先固化 `kimi-health.sh` 现有的全部契约
      首 token 路径（`PROGRESS` / `FROZEN_<N>m` / `FROZEN_7m soft_limit=frozen_hard`
      / `DONE <state>`）及其退出码，证明新增 `UNKNOWN_NO_OUTPUT` 没有改变任何
      既有路径的判定。**这是本 WP 最硬的一条**：health 是编排者的仪表，
      改仪表不得改既有读数。
- [ ] 正向测试：输出文件不存在 → `UNKNOWN_NO_OUTPUT`，rc=0
- [ ] 正向测试：输出文件存在但 0 字节 → `UNKNOWN_NO_OUTPUT`，rc=0
- [ ] **反向测试（关键）**：连续多轮 `UNKNOWN_NO_OUTPUT` **不会**累积成
      `FROZEN_3m` / `FROZEN_7m`（这正是 B2 的假警机制，必须钉死）
- [ ] 正向测试：输出文件有内容且内容不变、dirty 不变 → 仍照旧累计并在阈值报 FROZEN
      （证明没把冻结检测整个关掉）
- [ ] 测试：`dispatched` 在 rc 非零但进程确实跑完时为 True；
      在派发命令根本起不来（如二进制不存在）时为 False
- [ ] `AGENTS.md` 与 `AGENTS.md.tmpl` 在 §4.2 的契约行与派发形态要求上语义一致
- [ ] 未改动 `tests/test_gate_runner_shell.py` 与 `tests/test_init_githooks.py`
- [ ] `python3.11 -m pytest tests -q` 除已知 4 个预存基线失败外全绿
- [ ] 无 forbidden_paths 写入
- [ ] 无生产 DB 写入、无网络、无推送
- [ ] commit message 符合规范（gitmoji 前缀 + 中文说明）

## 风险声明

| 维度 | 取值 |
|------|------|
| production_writes | `FORBIDDEN` |
| network | `FORBIDDEN` |
| notifications | `FORBIDDEN` |
| data_access | `READ_ONLY` |

## 附注：已知陷阱

1. **health 脚本是纯测量，不得获得任何副作用。** 它现在不启动执行器、不写 status、
   不杀进程、不碰锁、不联网（`AGENTS.md` §4.2 明文）。新增的 UNKNOWN 路径同样
   只许 measure + print + 写 snapshot。
2. **退出码语义是契约**：`0` = 测量成功，非零 = 脚本自错（`64` usage /
   `65` status 不可读 / `66` git 失败）。`UNKNOWN_NO_OUTPUT` 是**测量成功**
   （成功测到「没有信号」），必须 rc=0。把它做成非零会让编排者以为脚本坏了。
3. **`dispatched` 有下游。** 改语义前 `grep -rn "dispatched" src tests` 确认全部
   读取点，别只改赋值处。
4. snapshot 的 JSON 结构（`state`/`tail_hash`/`dirty_sig`/`frozen`）是跨轮次状态，
   加字段要保证读旧 snapshot 不炸（`read_snap` 用的是 `d.get(...)`，跟随该写法）。
5. **本仓 Python 兼容 >= 3.9**，跟随现有 `from __future__ import annotations` 写法。
6. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
   跑全量测试时**不要设** `AGENTIC_PYTHON`——这正是本 WP 第 6 项要写进文档的那条。
7. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的 characterization / 正向 / 反向测试要求见上文 DoD。

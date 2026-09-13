# WP-08（候选）：dogfood 首轮暴露的框架自身缺陷清单

> 状态：**候选，未冻结**，等用户裁定纳入本迭代 / 另起迭代 / 拆分。
> 来源：2026-09-13 首轮并行（WP-01 + WP-03）dogfood 期间由编排者实测踩到，
> 每条都有可复现证据，非推测。

## 分级

**A 类 = 开箱即坏**（`agentic init` 出来的默认配置过不了自己的门），
**B 类 = 误导性错误信息**（信息不足导致误诊，浪费一轮排查），
**C 类 = 契约与模板不一致**（模板默认值与生命周期约束互相打脸）。

## A 类

### A0. 双签合并门在「编排者即审核者」的正常路径下无法通过，除非编排者自证一个可能为假的声明

- 证据：`agentic gate` 对 WP-01 实跑结果：
  `GATE_FAIL: independence level none does not meet minimum weak; reasons:
  reviewer identity unavailable (orchestrator, attested not engine-proven);
  no implementer fallback available; reviewer attestation missing`。
- 机制：`independence.evaluate()` 有三条路径。strong 要求两个 engine-observed
  model id 不同——本仓三签全绑同一 `deepseek-v4-pro`，永远达不到。degraded 路径
  （consultant vs implementer，两边都是机器观测身份，无需自证）**只在
  `review.decision == "N/A"` 时才populate `implementer_id`**
  （`gate/__init__.py:738-741`）。于是编排者一旦如实写下 `ACCEPT`，就只剩
  bootstrap 路径，其唯一信号是 `review.attestation`，而
  `ReviewerAttestation.is_valid()` 要求 `fresh_session is True` 且
  `adversarial_prompt is True`（严格 `is True`，字符串与 1 都不认）。
- 后果：**流程把「如实审核」惩罚成「过不了门」**。`fresh_session` 是关于「审核者是否
  在一个干净会话里、未参与规划」的事实断言。本轮我（编排者）撰写了 PLAN 与两个
  brief、派发并盯完执行，`fresh_session` 为假。要过门就得写 `true`，
  那是伪造审计记录以换取合并许可——正是 `min_independence` 想防的事。
  于是唯一诚实的出路是不合并。本轮两个 WP 已 ACCEPT 但卡在此处。
- 这不是「配置调松一点」能解决的：把 `min_independence` 降到 `none` 等于关掉双签。
- 修法（需要产品决策，建议交 Codex 复核）：
  1. 让 degraded 路径对 `review.decision == "ACCEPT"` 也可用——
     consultant 与 implementer 都是机器观测身份，比自证的 attestation **更强**，
     没有理由只在 `N/A` 时才用；这看起来就是个条件写窄了的缺陷。
  2. 或把 `fresh_session` 从 attestation 必填项里移除，改为记录性字段
     （如实写 false 也能过），只保留 `adversarial_prompt` 作为条件；
     并让门在 `fresh_session=false` 时把该事实写进 `consult.independence` 留痕。
  3. 或引入「审核者由独立会话签署」的真实机制（另起一个 claude 会话专做 review，
     其身份可被 engine 观测），从根上让 strong/weak 可挣得而非自证。
- 优先级：**最高**。它挡住的不是某个 WP，而是整条流水线的最后一步。


### A1. `agentic init` 生成的 gate 配置形式，`quality-gate.sh` 读不到

- 证据：`src/agentic_loop/init_cmd.py:57` 注释掉的示例是 `[[quality_gate.rule]]`；
  而 `quality-gate.sh` 与 `resolve_paths.py:254` 只认统一 `[[gate]]`
  （`kind="command"`, `stage="pre_review"`）。`docs/QUICKSTART.zh-CN.md:209` 确认
  `[[gate]]` 是正式形式。
- 后果：照 init 模板填规则 → `QUALITY_GATE_FAIL: [[gate]] (kind=command,
  stage=pre_review) is absent or defines no rules`，fail-closed 直接拒绝。
  新用户第一次跑门就撞墙，且错误信息不提示「你写的是旧形式」。
- 修法：init 模板改吐 `[[gate]]`；并在 `resolve_paths` 侧对残留
  `[[quality_gate.rule]]` 给一条明确的迁移提示而不是当作「没有规则」。

### A2. `STATUS.json.tmpl` 默认 `state="DRAFT"`，与「状态文件只提交两次」纪律冲突

- 证据：`src/agentic_loop/templates/STATUS.json.tmpl:7` 是 `DRAFT`；
  `preflight.sh:56-67` 的可执行状态集是 `APPROVED|DISPATCHED|IMPLEMENTING|CHANGES_REQUESTED`；
  且 preflight/quality-gate 读的是**副 worktree 已提交的副本**。
- 后果：按模板冻结 → preflight 报 `state DRAFT is not executable`；
  要修就得补一个 `DRAFT→APPROVED` 的提交，而那是第三次提交，
  `agentic plan lint` 立刻判 DIRTY（状态文件只允许 freeze + finalize 两次提交）。
  本轮实测被迫 `git commit --amend` 把冻结提交本身改成 `APPROVED` 才走通。
- 修法：模板默认值改 `APPROVED`（`validate_wp_status.py` 的
  `active_states = STATES - {"DRAFT","APPROVED"}` 已使 APPROVED 不要求
  base_commit/branch/worktree/executor，冻结形式天然合法）；
  或在 lint 侧显式放行一次 DRAFT→APPROVED 转换提交。二者择一，不能都不做。

### A3. `agentic init` 的默认配置自相矛盾：三签同模型 + `min_independence = "strong"`

- 证据：`init_cmd.py:38-53` 的默认 `[providers.deepseek]` 把
  `identity_model = "deepseek-v4-pro"` 作为「独立性评级唯一依据」，
  并让 `[roles]` 的 developer/reviewer/consultant 三签全绑该 provider；
  同一份模板第 65-66 行写 `[review_policy] min_independence = "strong"`。
  而 `independence.evaluate()` 的 strong 要求两个 engine-observed model id **不同**。
- 后果：`agentic init` 出来的默认配置，合并门**永久拒绝**——三签同 id 最高只能评到
  weak，而门限要 strong。与 A1 合起来，init 的默认配置在两个独立维度上都过不了自己的门。
- 本仓 `.agentic/config.toml:56-59` 已经手写了这条警告并把门限降到 `weak`，
  说明踩过；但 init 模板没跟上，下一个新项目照样撞。
- 修法：init 模板的 `min_independence` 默认值与默认 roles 绑定保持一致——
  三签同 provider 时默认吐 `weak` 并在注释里写明「若改成 strong，
  必须先把三签拆到不同 identity_model，否则门永久拒绝」。
  **不是**把警告写进注释就算了：默认值本身必须自洽。
- 归属：并入 WP-09（与 A1 同文件同区域）。

## B 类

### B1. `preflight.sh` 的 tracked 检查吞掉 stderr，把「路径不在本 worktree 内」误报成「未跟踪」

- 证据：`preflight.sh:69` `git ls-files --error-unmatch "$status_file" >/dev/null 2>&1`
  把 git 的真实错误一起丢进 `/dev/null`。传主区**绝对路径**时，git 实际报的是
  "outside repository"，wrapper 却输出
  `PREFLIGHT_FAIL: status file must be tracked before implementation`。
- 后果：本轮据此误判「文件没提交」，去查提交状态查了一轮，实际问题是路径形式。
- 修法：区分两种失败——先判路径是否落在当前 worktree 内，再判 tracked；
  或把 git 的 stderr 带进错误信息。

### B2. `agentic health` 的输出尾哈希信号，会被「缓冲式 subprocess 捕获」的派发形态整体致盲

- 证据：`kimi-health.sh` 的 freeze 判据是「输出尾内容哈希未变 **且** git dirty 未变」。
  本轮用 `KimiAdapter.implement()`（`subprocess.run(stdout=PIPE)`，全程缓冲）派发，
  `.out` 文件始终 0 字节，`tail_hash` 恒为空串哈希 `da39a3ee…`，
  两个信号里的一个从一开始就是死的；只剩 git dirty，而 kimi 写一个大文件期间
  dirty 本来就不变 → 连报 `FROZEN_3m` / `FROZEN_7m` 假警。
- 后果：假警会触发 §4.2 的仲裁流程，浪费编排者动作；更糟的是它训练人忽略告警。
- 修法：health 脚本在输出文件不存在或为空串哈希时，明确报
  `UNKNOWN_NO_OUTPUT` 而不是并入 frozen 判定（缺信号 ≠ 冻结）；
  并在 AGENTS.md §4.2 写明派发必须是 `| tee <log>` 的流式形态，
  buffered 捕获不满足 health 前置条件。

### B3. `AGENTIC_PYTHON` 覆盖会打穿测试自带的 `python3` stub，制造假失败

- 证据：`tests/test_gate_runner_shell.py` 与 `tests/test_init_githooks.py`
  会在 PATH 上装一个 stub `python3`；设 `AGENTIC_PYTHON=python3.11` 会绕过 stub。
  实测：带该环境变量跑这两个文件 1 failed，不带则 2 passed。
- 后果：本轮据此得出「门跑出 6 个失败，kimi 报 4 个」的差异，怀疑执行者漏报；
  实际是编排者的仪表把测试搞坏了。**kimi 报的 4 是对的。**
- 修法：文档明确 `AGENTIC_PYTHON` 只管 wrapper 自身调用，
  且跑全量测试时不得设置；或让这两个测试对 `AGENTIC_PYTHON` 免疫。

### B4. `| tee` 会吞掉派发的真实退出码

- 证据：本轮 WP-03 续跑 `kimi … | tee out2` 返回 exit 0，
  但 out2 内容是 `StepInterrupted()` + `Tool call arguments must be valid JSON.`
  ——kimi 在第 1 步就死了。exit 0 是 tee 的状态。
  `redispatch.sh:8` 有 `set -euo pipefail`，但编排者手写的派发命令没有。
- 后果：把「派发失败」读成「派发成功」，直接影响下一步判断。
- 修法：AGENTS.md §4.2 的派发范式里显式要求 `set -o pipefail`
  或检查 `${PIPESTATUS[0]}`。

### B5. `agentic quality-gate` 从主区跑会把编排者自己的改动算成 WP 越界

- 证据：`quality-gate.sh:41-46` 收集改动集的四条 git 命令都在**进程的当前工作目录**
  执行；脚本第 26 行确实调了 `resolve_paths --root current_worktree` 拿到 `repo_root`，
  但**该变量之后从未被使用**（全文只有赋值处与一句注释提到它），脚本也从不 `cd`，
  所以改动集完全由调用者的 cwd 决定。在主区对着某个 WP 的
  status 文件跑，会把编排者自己的 `.agentic/config.toml`、别的 WP 的 status、
  甚至 `uv.lock` 全部报成 `changed path outside allowed scope`。
- 后果：本轮实测得到 4 条假越界，看起来像 WP 违规，实则是「跑错目录」。
  这在并行场景下尤其危险：编排者本来就总有未提交的协调性改动。
- 修法：门在检测到「status 文件声明的 worktree ≠ 当前 worktree」时，
  直接 `QUALITY_GATE_FAIL: must run inside <declared worktree>` 拒绝，
  而不是照着错误的改动集算 scope。

### B6. kimi CLI 成功完成一轮后仍可能返回非零退出码，`dispatched` 判据不可信

- 证据：WP-03 的 rework 派发用了 `set -o pipefail` + `${PIPESTATUS[0]}`（已按 B4 修正），
  拿到 rc=1；但 stdout 里 kimi 明确输出 `[STATUS] DONE` + `[COMMIT] 78b33f2`，
  且 worktree 里该 commit 确实存在、工作区干净、改动完全正确。rc=1 是假失败。
- 后果：`KimiAdapter._run` 用 `dispatched = (returncode == 0)`
  （`adapters/kimi.py`），据此会把一次成功执行判成派发失败。
  与 B4 合起来看更糟：rc 既可能假 0（被 tee 吞）也可能假 1（kimi 自身），
  **两个方向都不可信**。
- 修法：不要把 kimi 的 rc 当作成功判据。判据应是「stdout 末尾有执行报告
  且 [STATUS] 为 DONE/DONE_WITH_CONCERNS」+「worktree 里 commit 确实存在」，
  由编排者独立核验。rc 只作为辅助信号记录，不用于分支决策。
  `ImplementResult.dispatched` 的语义应改为「进程已启动」而非「执行成功」。

## C 类

### C1. scope 是前缀匹配，不是 glob——但 PLAN/brief 里用 glob 写法不会报错

- 证据：`gate/__init__.py` 的 `scope_prefix()` 只剥尾部 `/**` 与 `/*`；
  `scope_matches(path, prefix)` 是 `path == prefix or path.startswith(prefix + "/")`。
  故 `tests/test_gate_report` 永远匹配不上 `tests/test_gate_report.py`。
- 后果：本轮 PLAN §5 写的是 `tests/test_gate_report*.py`（glob 意图），
  编排者手抄进 status 时降级成 `tests/test_gate_report`，
  中间的 `*` 被静默吃掉，门到实现完成后才报
  `changed path outside allowed scope: tests/test_gate_report.py`，
  修它要 `--amend` 冻结提交并 rebase 两条 feature 分支。
  **同一个坑在 WP-03 上又踩了一次**：PLAN §5 写 `tests/test_plan*.py`，
  status 里降级成 `tests/test_plan`，同样匹配不到 `tests/test_plan_lanes.py`，
  同样要第二次 `--amend` + rebase 两条分支。一轮 dogfood 两个 WP 全中，
  说明这不是手误而是形式陷阱——PLAN 里的 glob 写法与 status 里的前缀语义
  长得一样但含义不同，人抄一遍就错。
- 修法：`validate_wp_status.py` 已对非尾缀 wildcard 有校验
  （见 `validate_wp_status.py:150` 附近），但对「写了 glob 却被剥成无效前缀」
  这种情况应直接 STATUS_INVALID，而不是接受一个匹配不到任何东西的前缀。
  另：`dispatch-lint` 应校验 status 的 allowed_paths 与 brief/PLAN 的 scope 表一致。

### C2. `evidence.tests` 的结构要求只在校验器里，模板与文档没写

- 证据：`validate_wp_status.py` 要求每条 `evidence.tests` 是 dict 且带 `exit_code`；
  本轮先写成字符串列表 → `STATUS_INVALID: each evidence.tests entry requires an exit_code`。
- 修法：`STATUS.json.tmpl` 给一条带 `name`/`command`/`exit_code`/`note` 的注释示例。

### C3. `agentic preflight` / `quality-gate` 读的是副 worktree 已提交副本，
但 review 阶段编排者写的是主区工作区——两者永久不一致，无机制提示

- 证据：本轮 preflight 对 WP-03 报 `state=DISPATCHED`，而主区工作区已是
  `CHANGES_REQUESTED`（编排者刚写的 REWORK）。两个都"对"，只是读的不是同一份。
- 后果：编排者容易误以为自己的状态写入生效了。C 类而非 B 类，因为这是设计使然
  （状态文件只提交两次，中间的变更本就只在主区工作区累积），
  但**没有任何一处提示读者「你看到的是冻结副本」**。
- 修法：preflight/quality-gate 的输出行显式标注读取来源，如
  `state=DISPATCHED (from committed copy at <branch>)`。纯输出层，零风险。

## 拆包结论（用户已裁定：立 WP-08，按建议拆）

用户 2026-09-13 决定：合并两个已 ACCEPT 的 WP、把编排者的 `.agentic/config.toml`
修复并入 WP-08、其余按编排者建议执行。合并已尝试并卡在 A0（见上），
故本节只落拆包。

| 新 WP | 内容 | lane | 依赖 | 理由 |
|-------|------|------|------|------|
| **WP-08** | A0 双签独立性死锁 | `lane-gate-fix` | 无 | 挡住整条流水线最后一步，优先级最高，且需产品决策 |
| **WP-09** | A1 gate 配置形式不一致 + A3 默认门限与默认 roles 自相矛盾 + 编排者已做的 `.agentic/config.toml` 迁移 | `lane-config` | 无 | 开箱即坏（两个独立维度）；把编排者的现存改动正式纳入一个 WP 的 scope |
| **WP-10** | A2 `STATUS.json.tmpl` 默认 DRAFT | `lane-template` | 无 | 开箱即坏，与 A1 独立，可并行 |
| **WP-11** | B1 + B4 错误信息与派发范式 | `lane-gate` | WP-02 之后 | 都碰 `wrappers/`，与 WP-02 同 lane 串行避免撞车 |
| **WP-12** | B2 + B6 health 致盲 + kimi rc 不可信 + B3 `AGENTIC_PYTHON` 打穿 stub | `lane-gate` | WP-11 之后 | 同碰 `wrappers/` 与测试，同 lane 串行 |
| **WP-13** | B5 quality-gate 跑错目录 + C3 读冻结副本不提示 | `lane-gate` | WP-12 之后 | 同上 |
| **WP-14** | C2 `evidence.tests` 模板补注释 | `lane-template` | WP-10 之后 | 与 A2 同碰 `templates/`，同 lane |
| **并入 WP-04** | C1 scope 前缀 vs glob | `lane-gate`（原） | WP-02 | 与「派发前 scope 交叉检查」天然同域，不单列 |

并行结构：`lane-gate-fix`（WP-08）、`lane-config`（WP-09）、`lane-template`
（WP-10 → WP-14）三条可同时开工；`lane-gate` 的 WP-11/12/13 排在既有
WP-02 → WP-04 之后。C1 并入 WP-04 的 scope。

**WP-08 优先单独开工**，因为在 A0 解掉之前，任何 WP 做完都同样卡在合并门前。

## 原始建议（保留）


A1 与 A2 是「新用户第一次用就撞」的开箱缺陷，建议优先，且彼此独立可并行。
B1/B4 是纯错误信息与范式文档，成本低。B2/B3 需要碰测试与 health 脚本，
建议与 WP-02（wrapper 输出层）同 lane 串行以免撞 `wrappers/`。
C1 与 WP-04（派发前 scope 交叉检查）天然同域，建议并入 WP-04 而不是单列。

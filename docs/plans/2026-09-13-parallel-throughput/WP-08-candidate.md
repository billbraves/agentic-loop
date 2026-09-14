# WP-08（候选）：dogfood 首轮暴露的框架自身缺陷清单

> 状态：**候选，未冻结**，等用户裁定纳入本迭代 / 另起迭代 / 拆分。
> 来源：2026-09-13 首轮并行（WP-01 + WP-03）dogfood 期间由编排者实测踩到，
> 每条都有可复现证据，非推测。

## 分级

**A 类 = 开箱即坏**（`agentic init` 出来的默认配置过不了自己的门，
或框架允许的合法配置过不了自己的派发门——A4、A7 属后者），
**B 类 = 误导性错误信息**（信息不足导致误诊，浪费一轮排查），
**C 类 = 契约与模板不一致**（模板默认值与生命周期约束互相打脸）。

> ⚠️ **B7 是 B 类里的异类**：它不只是信息误导，而是「门禁跑的根本不是本仓的代码」。
> 之所以仍归 B 而非 A，是因为它不改变任何单个 WP 的判定正确性（判据文件当前两边一致），
> 但它使整轮 dogfood 的验证证据链失去机制保证。**修 B7 的优先级应高于其余 B 类。**

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

### A4. 冻结期填不了 `git.branch`/`worktree`，但 preflight 又要求它——冻结与派发的字段时序冲突

**现象**（本轮实跑，`a556c26`）：七个 WP 冻结时 `git.branch`/`git.worktree` 留空
（模板 `STATUS.json.tmpl` 默认即为空串），派发时 `agentic preflight` 直接拒绝：

```
PREFLIGHT_FAIL: current branch feature/wp08-independence-degraded != status branch
```

`preflight.sh:45` 拿活分支比 `git.branch`，空串永不相等，七个 WP 全部无法派发。

**为什么不能在派发时补**：三条路都堵着——

1. **另起一个提交补字段**：`_wp_commit_discipline`（`plan_cmd.py:355-367`）把
   非 freeze、非 `state=MERGED` 的提交一律归为 `sync`，于是 `plan lint` 对该 WP
   永久 DIRTY，`plan merge` fail-closed。正是 §4.3 要消灭的「review 同步 / codex 同步」污染。
2. **只改工作区不提交**：`quality-gate.sh` 的改动集含 `git diff`（未提交改动），
   status 文件不在 `allowed_paths` 里，于是实测报
   `QUALITY_GATE_FAIL: changed path outside allowed scope: ...WP-08.status.json`
   ——执行者必跑的门被自己的协调文件打挂。
3. **把 status 路径加进 `allowed_paths`**：等于把状态写入面交给执行者，
   违反全局规范 §4.1「仅编排者维护 status」与 §5.7 隔离。

**本轮的处置**：用户授权 `git commit --amend` 改写未推送的 `a556c26`
（→ `802b667`），把七个 WP 的 branch/worktree 补进**同一个** freeze 提交，
保持「每 WP 恰好一次 freeze」。事后 `plan lint` 对 WP-08..14 只剩
`finalize commit x0`，无 sync 提交。

**这是缺陷而非操作失误的理由**：冻结（`APPROVED`，scope 与验收标准定稿）
天然发生在开 worktree 之前，此时 branch/worktree **尚不存在**；
而 `validate_wp_status.py:462-464` 只在 `active_states`（不含 `APPROVED`）
才要求这三个字段非空——**校验器认为冻结期留空是合法的**，
`preflight.sh` 却要求它非空。两者对同一状态的要求不一致。

**候选修法**（择一，需评估）：

- `preflight.sh`：`git.branch` 为空时视为「尚未绑定」，
  用活分支回填并提示，而不是失败；绑定后再比对（要防止绑错分支）。
- 或：承认 `APPROVED -> DISPATCHED` 的状态跃迁本身就该带一次合法的状态写入，
  在 `_wp_commit_discipline` 里把「freeze 之后、`state=DISPATCHED` 的第一个提交」
  也算合法（freeze/dispatch/finalize 三次提交纪律），而非一律判 sync。
- 或：`agentic preflight` 增一个 `--bind-branch` 子动作，由编排者显式在
  freeze 提交里 amend/补齐，把本轮的人工操作变成有据可循的一等命令。

> 注意第二条会把「两次提交」纪律改成「三次」，是文档级契约变更，
> 需要用户裁定，不能由执行者顺手改。

### A7. 以另一个 WP 分支为基线时，本 WP 的 status 在副 worktree 索引里不可见，preflight 必挂

**现象**（2026-09-14 实跑 WP-17）：WP-17 经用户裁定以
`feature/wp08-independence-degraded` @ `a46578c` 为基线（WP-08 作上游依赖）。
worktree 建好、分支起点正确（已核实 `_should_populate_implementer` 在场），
但 `agentic preflight` 在副 worktree 里报：

```
PREFLIGHT_FAIL: status file must be tracked before implementation
```

**根因是提交拓扑，不是传参错误**。`preflight.sh:69` 是
`git ls-files --error-unmatch "$status_file"`，它按**当前 worktree 的索引**解析。
而各 status 文件首次出现的提交不同：

| 文件 | 所在提交 | `a46578c` 能否看到 |
|------|----------|--------------------|
| `WP-08.status.json` | `802b667`（七 WP 冻结） | **能**——`a46578c` 是 `802b667` 的子提交 |
| `WP-17.status.json` | `2dd9cfc`（WP-15/17 冻结） | **不能**——`2dd9cfc` 与 `a46578c` 是 `802b667` 的两个分叉 |

已用 `git cat-file -e` 逐一核实：
`feature/wp08-independence-degraded:…/WP-17.status.json` →
`fatal: path … exists on disk, but not in 'feature/wp08-independence-degraded'`；
同一路径在 `2dd9cfc` 下存在。

**为什么这是缺陷而非操作失误**：常规 WP 的基线就是 plan 分支，冻结提交天然是
基线的祖先，`ls-files` 永远能看到。但**一旦某 WP 以另一个未合并的 WP 分支为基线**
（A5 修法 2 这种自举场景的必然形态），冻结提交与基线就成了兄弟分叉，
`ls-files` 必然查不到。框架允许 `git.base_branch` 填任意分支
（`validate_wp_status.py:439` 只校验非空），却没有任何一处提示这会打挂 preflight。

**本轮的处置**：在副 worktree 里 `git merge --no-ff plan/2026-09-13-parallel-throughput`
把冻结提交并进 WP-17 分支。该提交只动 `docs/plans/`，不含代码，
故不污染 WP-17 的代码 diff，且副作用是好的——执行者在自己 worktree 里
就能读到自己的冻结 brief。

**候选修法**（择一）：

- `preflight.sh:69` 改成在**主仓**索引里查 status（用已有的 `main_root`，
  `resolve_paths --root main_repo` 那一行就在 `:77`），而不是当前 worktree。
  status 本就是主区 live 状态（全局规范 §4.1），在主仓查才是对的语义。
- 或：`dispatch-lint` 增一条检查——`git.base_branch` 不是 plan 分支时，
  校验冻结提交是否为 `base_commit` 的祖先，不是则明确报
  「以 WP 分支为基线须先把冻结提交并入该分支」，把这次的摸索变成一次性提示。
- 或：文档化「上游依赖型 WP 的派发前置步骤」，写进 `AGENTS.md` §4.2。

> 与 A4 同源但不是同一条：A4 是「冻结期填不了 branch/worktree」（字段时序），
> A7 是「派发期 status 在副 worktree 索引里不可见」（提交拓扑）。
> 两者都出现在冻结与派发的接缝处，修 A4 不会顺手修掉 A7。

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

**2026-09-13 WP-08 派发期二次实测复现**（不再是推演，是完整跑了一遍的观测）：

- 派发 3 分钟后 monitor 报 `FROZEN_3m tail=""`——`tail` 就是空串，B2 描述的
  「一个信号从一开始就是死的」在实盘上原样出现。
- 同一时刻的独立核查：`.out` 文件 0 字节；health snapshot 里
  `tail_hash=da39a3ee5e6b4b0d3255bfef95601890afd80709`（空串的 SHA-1）；
  而 `ps` 显示派发 wrapper 与 `Kimi Code` 进程都活着，其子进程正在跑
  `python3.11 -m pytest tests -q`，worktree 里三个目标文件已就位
  （`gate/__init__.py` 已改，两个测试文件各 220 / 123 行）。
  **执行者完全健康，告警纯属虚报。**
- 附带确认了 §B2 修法里「空串哈希」这一判据的可用性：`tail_hash` 恒等于
  `da39a3ee…` 正是 `UNKNOWN_NO_OUTPUT` 该识别的特征值。
  （注意与 §B2 原记的 `d41d8cd9…` 区分：那个是 `tail_hash()` 在**文件缺失**
  分支返回的 MD5-of-empty，此处是文件存在但为空时 `shasum` 的 SHA-1。
  两个空态走两条不同的哈希算法，本身也是 B2 该一并收敛的口径不一致。）
- 编排者的临时对策（不属任何 WP，仅本轮操作）：monitor 改用
  「health 输出 + 派发进程是否存活」双判据，`FROZEN_*` 不再单独作为终止条件。
  这恰好印证 B2 的修法方向——**缺信号必须与冻结区分开**。

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

### B7. dogfood 改的是 `src/`，但 `agentic` 跑的是 uv 装的另一个仓的快照——本仓的框架改动在门禁运行中完全不生效

- 触发：给 WP-15 跑 `dispatch-lint` 时，直接
  `bash src/agentic_loop/wrappers/dispatch_lint.sh` 报
  `ModuleNotFoundError: No module named 'agentic_loop'`（真实退出码 2，fail-closed 正确），
  只有 `PYTHONPATH=src` 或走 `agentic dispatch-lint` 才通。顺着查出下面整条链。
- 证据（三段，全部实测）：
  1. **wrapper 的 preamble 路径不存在**。11 个 wrapper 全都 export
     `PYTHONPATH="…:$main_root/packages/agentic-loop/src"`
     （`dispatch_lint.sh:21` 等），但本仓 `ls -d packages/agentic-loop/src` →
     No such file or directory。本仓源码在 `src/`。这句 export 从头到尾是空操作。
  2. **CLI 的 dogfood 通道在本仓落不到地**。`cli.py` 的 `resolve_wrapper()`
     优先取 `_main_root()/scripts/agentic/<name>`（注释写明 "live edits (dogfood) win"），
     否则退回 wheel 内置 `agentic_loop/wrappers/<name>`。本仓
     `ls -d scripts` → 不存在，wrapper 全在 `src/agentic_loop/wrappers/`。
     故 `agentic dispatch-lint` 实际跑的是 **wheel 内置副本**，不是工作树那份。
  3. **Python 模块也来自另一个仓的快照**。`agentic` 的 shebang 指向
     `~/.local/share/uv/tools/agentic-loop/bin/python`（3.12.7），
     其 `dist-info/direct_url.json` = `file:///Users/admin/vibe/agentic-loop-main-codex-merge`，
     **非 editable**（无 `.pth` 指向本仓）。装载源那个仓的 HEAD 是 `600c2f1`
     `✅ chore(plan): finalize Codex verdict recovery merge`（分支 `main`，已 merge WP-16）。
     `diff -rq -x __pycache__` 已装副本 vs 本仓 `src/agentic_loop`：唯一差异是
     `adapters/codex.py`——**已装副本比本仓工作树新**，含 WP-16 的有界恢复实现
     （`grep -c _NORMALIZATION_INPUT_MAX_BYTES`：已装 4，工作树 0）。
- 后果（这是本条的要害，不是"少配了个环境变量"）：
  - 本仓对 `src/agentic_loop/**` 的任何改动，**在 `agentic *` 的门禁运行里一律不生效**，
    要等 `agentic update` 重装才进副本。dogfood 的核心假设——"改框架、立刻用改后的框架验自己"
    ——在本仓不成立，且**没有任何一处提示**（不像 C3 至少两边都"对"，
    这里是跑了完全另一个仓的代码却显示 PASS）。
  - 反向也成立：我给 WP-15 拿到的 `DISPATCH_LINT_PASS`，是**另一个仓的
    `dispatch_lint.sh` + `validate_wp_status.py`** 判的。判据本身没差异（该文件两边一致），
    所以这次结论仍然有效；但这是运气，不是机制保证。
  - 版本号相同（两边都 `0.8.13`）无法暴露漂移：装载源与本仓同版本号但不同内容。
- 与已有条目的关系：不是 B3 的重复。B3 说 `AGENTIC_PYTHON` 覆盖会打穿测试的
  `python3` stub；本条说的是**模块本体来源错仓**，`AGENTIC_PYTHON`
  在这里恰好是让它能跑起来的那一半（`cli.py:213` 把 `sys.executable` 注入 wrapper env，
  见 `docs/KNOWN-ISSUE-bare-python3.md`）。
- 修法（三处，按优先级）：
  1. `resolve_wrapper()` 的 dogfood 分支要认本仓的实际布局：
     除 `scripts/agentic/<name>` 外，也探 `src/agentic_loop/wrappers/<name>`
     （或反过来，把本仓 wrapper 迁到 `scripts/agentic/` 以对齐 CLI 契约）。
     二者选一，但必须让"框架自己的仓"命中 main 分支而非 bundled。
  2. wrapper preamble 的 `packages/agentic-loop/src` 改成本仓真实源码根，
     并在解析失败时明确报"framework source root not found"，
     而不是靠 `python3 -m` 的 `ModuleNotFoundError` 间接暴露。
  3. dogfood 场景应 editable 安装（`uv tool install -e .` 或等价），
     否则 `agentic` 与工作树永久脱钩。至少要有一条 gate 或 `agentic --version`
     输出装载来源路径 + 是否 editable，让"我跑的是哪份代码"可见。
- 归 B 类而非 A 类：不阻塞任何单个 WP 的判定正确性（判据文件当前两边一致），
  但会让整轮 dogfood 的验证证据链失去意义，且随任一侧继续改动即刻恶化为假绿。

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

### A5 `developer` 角色不绑 provider 会让 WP-08 的 A0 解锁静默失效

**发现时间**：2026-09-13 23:46（WP-08 已 ACCEPT 之后）
**触发**：`.agentic/config.toml` 于 23:37 被会话外手工改动（reviewer/consultant
重指向本机 kiro 网关），其中 `developer` 从
`{ adapter = "kimi", provider = "deepseek" }` 改为裸字符串 `"kimi"`。

**现象**：A0 完全复现，reasons 与原缺陷逐字相同：

```
level='none'  meets_threshold(none,'weak')=False
  - reviewer identity unavailable (orchestrator, attested not engine-proven)
  - no implementer fallback available
  - reviewer attestation missing
  - fail-closed: independence level none
```

**机理**：WP-08 的修复把 degraded 路径的准入条件放宽到 `ACCEPT` 之后，
`implementer_id` 由 `_resolve_implementer_identity(executor_tool, binding)` 解析，
而该函数在 `binding is None` 时返回 `None`（这是刻意的 fail-closed：
拿不到 engine 观测的 model 就不假装有身份）。于是：

- `implementer_id = None` → `is_bootstrap_normal = True`
- degraded 路径根本不进入，退回 bootstrap
- bootstrap 唯一信号是 `review.attestation`，而 `fresh_session` 为假

即回到「要过门就得伪造审计记录」的死锁。

**config 注释与实况不符**：该次改动在 `[roles]` 写下
「developer 不绑 provider…绑了也不影响评级——只有 `review.decision == "N/A"`
时才用 `executor.tool` 构造 `implementer_id`」。这句话在 WP-08 之前成立，
在 WP-08 之后不成立：`_should_populate_implementer` 已含 `ACCEPT`，
`developer` 的 provider 绑定自此成为 degraded 路径的**必要输入**。
注释是按旧语义写的。

**这不是 WP-08 的缺陷**：`a46578c` 的代码在有绑定时正确解锁 A0（已实测），
fail-closed 行为也正确。这是一处**配置—代码耦合未被文档化**的问题。

**候选修复（未指派，需用户裁决）**

1. `developer` 恢复 provider 绑定（任一有 `identity_model` 的 provider 即可，
   不必与 consultant 同源——degraded 只要求两边都被 engine 观测）。
   最小改动，但 `.agentic/config.toml` 是 WP-08 的 forbidden path，
   且改配置属用户决策，编排者不得自行改。
2. `gate` 在 `_should_populate_implementer(review_decision)` 为真却拿不到
   implementer 绑定时，输出一条明确诊断（如
   `developer role has no provider binding; degraded independence path unavailable`），
   而非现在这样并入通用的 `no implementer fallback available`。
   属新 WP，可与 A4 同批。
3. 在 `[roles]` 的注释里记录该耦合，防止下次再按旧语义解绑。

**另一处观察（非缺陷）**：新配置下 reviewer=`claude-opus-5` 与
consultant=`gpt-5.6-sol` 确为异源，但 `gate/__init__.py:795` 仍硬编码
`reviewer_id=None`，故 strong 在 gate 路径上依旧不可达。
该配置的 `[review_policy]` 注释已如实说明这一点，与代码一致。

#### A5 定性修正（2026-09-14，用户澄清后）

上文把 A5 记为「配置与代码耦合未文档化，补上 developer 的 provider 绑定即可」，
**该定性错误，作废**。用户澄清：kimi 实际跑在 codingplan 的 k3，只有 claude/codex
走 kiro 代理。因此 `developer = "kimi"` 不绑 provider 是**如实反映现状**，
不是疏漏。

编排者原建议「给 developer 绑 kirogpt」是错的，撤回。两处危害：

1. `identity_model` 会记成 `gpt-5.6-sol`——给 implementer 挂一个它没在使用的
   模型身份，**属伪造审计记录换合并许可**，与写 `fresh_session = true` 同类。
   WP-08 存在的意义正是禁止此类操作。
2. 并非只改 identity。`provider_binding.build_binding()` 对 `kimi`
   （属 `_ANTHROPIC_ADAPTERS`）强制要求 `anthropic_base_url`，且
   `adapters/kimi.py:58` 将其写入配置、`:95` 以 `--model <cli_selector>` 覆盖模型。
   即**不存在「只声明 identity_model 而不改路由」的写法**，绑定必然把 kimi 的
   实际流量改指到代理上，改变执行环境。

**A5 的真实性质**：不是配置错误，而是**判据设计与本仓实际拓扑不匹配**。
degraded 要求 implementer 身份 engine 可观测，而本仓 implementer 不经框架
provider 层，架构上就观测不到。三条路径因此全部落空：

| 路径 | 阻塞点 | 可达 |
|------|--------|------|
| strong | `gate/__init__.py:795` 硬编码 `reviewer_id=None` | 否 |
| degraded | k3 不经 provider 层，implementer 身份观测不到 | 否 |
| bootstrap | 唯一信号 `fresh_session` 本轮为假，如实写必不过 | 否 |

WP-08 的代码正确、配置也正确，A0 仍锁死。这比原记录的严重。

**修正后的候选修法（待用户裁决，编排者不自行选）**

1. **让 kimi 真实身份可观测**：`[providers]` 增一条如实描述 codingplan/k3 的条目
   （`identity_model` 填 k3 真实模型 id，`anthropic_base_url` 填其实际端点）。
   degraded 由此成立且无任何伪造。**前提：kimi 确有 anthropic 兼容端点**，未确认。
2. **扩judgment判据**：立新 WP，在 degraded 之外补一条「实现者身份不可观测」下的
   合法替代证据（如 commit 作者 + 隔离 worktree）。最重，但对得上本仓拓扑。
3. **本轮显式记账放行**：承认三路径在当前拓扑下均不可达，作为一次有完整记录的
   例外合并 WP-01/03/08，修判据留给后续 WP。需用户明确授权，理由须完整写入 status。

三条都不涉及放宽 `min_independence`（仍为 `weak`），也都不伪造任何字段。

#### A5 裁定（2026-09-14，用户选定修法 2）

**用户裁定：走修法 2**——立新 WP 扩展评级判据。修法 1 不再是首选。

裁定前的关键输入是 codex 对 WP-15 的独立审核
（`WP-15-consult-codex.md`，`[VERDICT] REWORK`），它推翻了修法 1 的前提。
修法 1 的三项阻断条件：

| 阻断条件 | 依据 | 严重性 |
|---------|------|--------|
| `identity_model` 直接来自可手改的 TOML，`build_binding()` 原样读、`identity()` 原样返回，注入探针只验 sentinel 不验模型——**任何人都能把真实路由指向模型 A 却声明模型 B，凭此伪造 degraded 独立性** | `provider_binding.py` `build_binding()`；`adapters/kimi.py:45-47` | P0 |
| `--config-file` **独立加载**，不与 `~/.kimi/config.toml` 合并；`_temp_config()` 只输出 provider/model，绑定即丢 `default_thinking`、模型 `capabilities`、`[loop_control]`、`[background]`、`[notifications]`、`[mcp.client]` 与 13 个 `[[hooks]]` | `adapters/kimi.py:49-64`；`~/.kimi/config.toml:2,50,79+` | P1 |
| 模板硬编码 `type = "anthropic"` 且要求 `anthropic_base_url`，但本机 K3 实为 `type = "kimi"` managed provider + OAuth（A5 原记录已自注「anthropic 兼容端点未确认」） | `adapters/kimi.py:56-63`；`~/.kimi/config.toml:70-75` | P1 |

其中 **P0 是方向性的**：修法 1 本质上是让合并门去读一个用户可手改的字符串，
与 WP-08 存在的理由（不许自证）属同一类问题，只换了个字段。
`identity_model` 的可信性没有任何代码防线——这是 codex 对
「有人能否借这条路填假 model 伪造 degraded」一问的直接回答。

**编排者已核实的事实**（不依赖 codex 报告，直读 `~/.kimi/config.toml`）：
`default_thinking = true`（`:2`）；`[models."kimi-code/k3"]` 的
`max_context_size = 1048576`（`:49`）与
`capabilities = ["thinking", "video_in", "image_in"]`（`:50`）；
K3 provider 是 `type = "kimi"`（`:70-71`）走 OAuth（`:75`）。
**未能独立验证**：「`--config-file` 不与全局配置合并」这一机制，
目前仅有 codex 的核实为依据（`kimi --version` / `--help` 当时被 auto mode
安全分类器拦下）。

**修法 2 的目标**：让 orchestrator-as-reviewer 的诚实 `ACCEPT`
有一条通路，既不靠自证 attestation（A0 的死结），也不靠可伪造的
`identity_model`（修法 1 的 P0）。

**已起草 `WP-17-brief.md`（草案，未冻结）**。核心设计判断：新判据的证据必须是
**engine 能用 `git` 自行核对的事实**（commit author 与编排者不同、branch 与
base_branch 不同、tree 与 base_commit 不同、改动全在 `allowed_paths` 内），
不能是任何来自 status 文件的自填字段——否则就是把 bootstrap 的自证换个字段名，
重犯修法 1 被否掉的同一错误。该判据只证明「改动由他方产生、经隔离、范围受限」，
**不证明模型差异，故只能评 `weak`，永不评 `strong`**。

**三个设计点用户已于 2026-09-14 裁定**：
(1) **复用 `weak`**，`INDEPENDENCE_LEVELS` / `_LEVEL_RANK` 一处不改，
靠 `reasons` 标 `level=weak-isolated` 区分来源（新增级别会让现有
`min_independence = "weak"` 拒绝更低的新级别，A0 依然锁死，还要连带改配置）；
(2) **要求** `capabilities.sandbox_enforced`，直接复用
`_weak_engine_enforced()` 的 `weak_ok`，不另写并行判断；
(3) **git 事实由 `gate/` 读好后以 `IsolationEvidence` 传入**，
`evaluate()` 内不得有任何 I/O，保住纯函数性质。

**另有一项起草时核实出的顺序约束**：主区 `gate/__init__.py` 不含
`_should_populate_implementer`（`grep -c` 为 0，该函数只在未合并的
`feature/wp08-independence-degraded` 上），而 WP-17 改的正是同两个文件。
更要紧的是 WP-08 的合并本身卡在 A0，而 WP-17 就是去解 A0 的——**存在自举问题**。
编排者倾向让 WP-17 基于 `feature/wp08-independence-degraded` 开分支
（把 WP-08 当上游依赖），而非动用一次例外合并先把 WP-08 落地。

修法 1 不作废、只是不作首选；其三项阻断条件记录在案，供日后重启该路线时参考。
WP-01/WP-03/WP-08 的合并在修法 2 落地前继续挂起。

### A6 `kimi.py` 把 `max_context_size` 硬编码为 DeepSeek 的 768K

**发现时间**：2026-09-14（为 A5 修法 1 评估代价时）

`adapters/kimi.py:63` 在临时配置模板里写死：

```python
f'max_context_size = 786432\n'
```

无参数、无配置项、不读 provider 配置。786432 = 768K 是当初为 DeepSeek 端点选的值
（同一函数 docstring `:51` 与注释 `:54` 至今仍写 DeepSeek）。

**后果**：kimi 的实际后端是 codingplan/k3，真实窗口 1048576（1M）。一旦
`developer` 绑上任何 provider，`kimi.py:107` 便以该临时配置启动 kimi，
768K 覆盖 1M —— **k3 静默损失约 25% 可用上下文，无任何告警**。

**绕不开**：绑定路径上 `:107`（派发）与 `:171`（注入探针）都只经
`_temp_config()`，不存在「绑定但不套用该模板」的路径。

**定性**：这是缺陷，不是绑定应付的代价。该值本应随 provider 配置走
（如 `[providers.X].max_context_size`，缺省时保留现值），却被钉死成某一个
provider 的数值。编排者先前把它表述为「需用户接受的风险」措辞不当，已更正。

**顺带**：同一模板不产出 `CLAUDE_CODE_EFFORT_LEVEL` 等字段，框架派发路径下丢失；
`_PROBE_PROMPT`/`_SENTINEL`（`:165-166`）也仍写 `DEEPSEEK_PROBE_OK`，
与实际 provider 无关，属同一处未随 provider 泛化的遗留。

**候选修法**：`max_context_size` 提为 provider 配置项，`build_binding()` 透传，
模板改为读 binding；未声明时回退 786432 以零回归。

**已立 WP-15**（`WP-15-brief.md`，rev2）。

**rev2 的两处修正**（依 codex 咨询 `WP-15-consult-codex.md`）：

1. **A6 与 A5 解耦**。上文「与 A5 修法 1 同批（A5 修法 1 落地前 A6 必须先修）」
   的因果**已作废**：修法 1 另有三项独立阻断条件（见 §A5 裁定节的表），
   修完 A6 一条也不解决；且用户已裁定 A5 走修法 2。WP-15 现为**独立修复**。
2. **回退值的落点**。原设想「`ProviderBinding.max_context_size = 786432`
   作 dataclass 默认值」被 codex 否掉：`max_context_size` 是 Kimi 的 model 属性
   而非 provider 身份属性，把 768K 放进默认值会让「provider 未声明」与
   「provider 声明了 768K」在 binding 上无法区分。改为
   `int | None = None` + renderer 侧命名常量 `_LEGACY_MAX_CONTEXT_SIZE`。
   模板那一行不能省略——Kimi 配置模型的 `LLMModel.max_context_size` 是必填项。

**A6 的定性经 codex 确认成立**：「硬编码 768K 应改为可配置，并保留旧配置的
兼容回退」。编排者先前把它表述为「需用户接受的风险」确属措辞不当。

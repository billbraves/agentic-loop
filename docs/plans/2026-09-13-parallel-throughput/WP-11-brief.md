# WP-11: 把两个「静默说谎」的失败路径修成会说真话

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

修掉两处让编排者据以做出错误判断的信号损坏：`preflight.sh` 吞掉 git 的真实错误
把「路径不在本 worktree」误报成「文件未跟踪」（B1）；`| tee` 吞掉派发的真实退出码
把「派发失败」读成「派发成功」（B4）。

## 背景

缺陷 B1 与 B4（`WP-08-candidate.md` §B1 §B4）。合并成一个 WP 是因为两者同属
「wrapper/派发范式的信号可信度」，且改动面都小；分开做会让 `lane-gate` 多排一轮。

**B1**：`preflight.sh:69` 是

```bash
if ! git ls-files --error-unmatch "$status_file" >/dev/null 2>&1; then
  echo "PREFLIGHT_FAIL: status file must be tracked before implementation" >&2
```

`2>&1` 把 git 的真实错误一起丢进 `/dev/null`。传主区**绝对路径**时 git 实际报的是
"outside repository"，wrapper 却宣称文件未跟踪。本轮编排者据此去查提交状态查了一轮，
真实问题是路径形式。两种失败原因不同、修法不同，却共用一句错误信息。

注意 `preflight.sh:50-59` 已经有一段 worktree 一致性校验，但它只在
`status.git.worktree` **非空**时生效；`APPROVED` 状态的 status 文件按
`validate_wp_status.py:458` 的宽松档允许 `worktree` 为空，此时那段被整体跳过，
于是 B1 的误报路径依然可达。

**B4**：本轮 WP-03 续跑 `kimi … | tee out2` 返回 exit 0，但 `out2` 内容是
`StepInterrupted()` + `Tool call arguments must be valid JSON.`——kimi 在第 1 步就死了。
exit 0 是 `tee` 的退出码。`redispatch.sh:8` 有 `set -euo pipefail`，
但 AGENTS.md §4.2 给编排者的派发范式里没有这一条，手写派发命令就会中招。

> B4 的孪生缺陷 B6（kimi 成功完成一轮后仍可能返回 rc=1）属 WP-12，本 WP 不碰。
> 两者合起来的结论是 rc 两个方向都不可信，但本 WP 只负责「不要再让 `tee`
> 制造假 0」，不负责重新定义成功判据。

## 范围

**allowed_paths**
- `src/agentic_loop/wrappers/preflight.sh`
- `AGENTS.md`
- `src/agentic_loop/templates/AGENTS.md.tmpl`
- `tests/test_preflight_tracked_error.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`
- `src/agentic_loop/adapters/`（`ImplementResult.dispatched` 的语义属 WP-12）
- `src/agentic_loop/wrappers/kimi-health.sh`（属 WP-12）
- `src/agentic_loop/wrappers/quality-gate.sh`（属 WP-13）
- 其余一切未在 allowed 列出的路径

> 本 WP 属 `lane-gate`，排在 WP-02 之后**串行**，因为 WP-02 会改
> `wrappers/quality-gate.sh` 且与本 WP 同碰 `wrappers/`。不得与 WP-02 并发。

## 输入

- 依赖的上游 WP 产出：WP-02（路径匹配逻辑去重）必须先 MERGED
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B1 §B4
- 现状代码：`preflight.sh:50-72`；`redispatch.sh:8`（正确范式的现成例子）；
  `AGENTS.md` §4.1 与 §4.2

## 交付物清单

**B1 —— 区分两种失败**

1. `preflight.sh` 的 tracked 检查改成先分辨「路径是否落在当前仓/worktree 内」，
   再判 tracked；两种失败给两条不同的错误信息，且**把 git 的 stderr 带进错误信息**
   （现在是整条丢掉）。
   > 具体形态由你定，但必须满足：路径在仓外时错误信息里出现「路径/仓库」语义
   > 而不是「未跟踪」；文件确实在仓内但未提交时仍报原来的
   > `PREFLIGHT_FAIL: status file must be tracked before implementation`
   > （这条现有信息是对的，不要改字样，下游可能在匹配它）。
2. 退出码保持 `2` 不变。**这是硬要求**：preflight 的 rc 是契约，
   下游按 rc 分支，新增一种失败原因不等于新增一个 rc。

**B4 —— 把派发范式写进契约**

3. `AGENTS.md` §4.1（派发命令形态）显式要求：任何带管道的派发命令必须
   `set -o pipefail` 或检查 `${PIPESTATUS[0]}`，并说明理由（`tee` 的 rc 会盖掉
   派发进程的 rc）。给一个正例，指向 `redispatch.sh:8` 作为仓内既有范式。
4. `src/agentic_loop/templates/AGENTS.md.tmpl` 同步。
   > 两份是「本仓契约」与「init 出去的模板契约」，必须一起改，否则新项目
   > scaffold 出来的契约缺这一条。改完确认两份在这一段上语义一致
   > （模板里有 `$orchestrator` 之类占位符，逐字节相同不是要求，语义一致是）。

## 完成定义（DoD）

- [ ] **反向测试（B1 的硬要求）**：构造两种失败各一例——
      (a) status 文件路径指向当前仓外 → 断言错误信息**不**含 "must be tracked"，
      且含可辨识的路径/仓库语义；
      (b) status 文件在仓内但未 `git add` → 断言仍报
      `PREFLIGHT_FAIL: status file must be tracked before implementation`。
      两例都断言 `rc == 2`。
      这条测试的意义是把「两种原因两条信息」变成机器可验的，
      否则下次改 wrapper 又会合并回一句话。
- [ ] `preflight.sh` 其余任何检查的行为与退出码不变（现有 preflight 测试全绿即可证）
- [ ] `AGENTS.md` 与 `AGENTS.md.tmpl` 的 pipefail 要求语义一致
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

1. **`preflight.sh` 是派发前的硬门，改它的失败路径要格外小心「把门改松」。**
   新增的路径判断不得让任何原本会 fail 的输入变成 pass。反向测试 (b) 就是钉这个的。
2. **不要把 tracked 检查整段删掉换成 Python。** wrapper 层是 shell 契约，
   保持形态；`AGENTIC_PYTHON` 只管 wrapper 自身对 Python 模块的调用。
3. B1 提到的 `preflight.sh:50-59` worktree 校验段**不要动**——那段的加严属 WP-06
   （lane 独立 worktree 强制）。本 WP 只在 tracked 检查处补路径分辨。
   若你认为两处应当合并，写进 `[CONCERNS]`。
4. **本仓 Python 兼容 >= 3.9**；shell 部分跟随现有写法（`set -euo pipefail` 等）。
5. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
   跑全量测试时**不要设** `AGENTIC_PYTHON`（见 §B3，会打穿测试自带的 `python3` stub
   制造假失败）。
6. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的反向测试要求见上文 DoD。

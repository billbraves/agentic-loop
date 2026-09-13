# WP-13: 门要么拒绝跑错目录，要么说清自己读的是哪一份

> 冻结日期 2026-09-13 ｜ 编排者 Claude ｜ 执行者 kimi（provider: deepseek）
> 冻结后执行期间不得修改。修订走 re-freeze（rev2）。

## 目标（一句话）

`agentic quality-gate` 在当前 worktree 与 status 声明的 worktree 不一致时直接拒绝，
而不是照着错误的改动集算出一堆假越界（B5）；preflight / quality-gate 的输出显式
标注「你看到的状态来自已提交的冻结副本」（C3）。

## 背景

缺陷 B5 与 C3（`WP-08-candidate.md` §B5 §C3）。两者同属「门读错了对象却不声明」，
且都只碰输出层与前置校验，合成一个 WP。

**B5 —— 跑错目录产出假越界。** `quality-gate.sh:41-46` 收集改动集的四条 git 命令
（`git diff base...HEAD` / 工作区 / `--cached` / `ls-files --others`）都在**进程的
当前工作目录**里执行。脚本第 26 行确实调了
`resolve_paths --root current_worktree` 拿到 `repo_root`，但**那个变量之后从未被使用**
（全文只有赋值处与一句注释提到它），脚本从不 `cd`，因此改动集完全由调用者的 cwd 决定。

于是在主区对着某个 WP 的 status 跑，会把编排者自己的 `.agentic/config.toml`、
别的 WP 的 status、甚至 `uv.lock` 全部报成 `changed path outside allowed scope`。
本轮实测得到 4 条假越界，看起来像 WP 违规，实则是「跑错目录」。
这在并行场景下尤其危险：**编排者本来就总有未提交的协调性改动**，
所以主区跑门几乎必然产出假阳性。

`preflight.sh:50-59` 已经有一段现成的 worktree 一致性校验可作范式参考
（把 `status.git.worktree` 解析成绝对路径后与 `$(cd "$repo_root" && pwd -P)` 比对，
不一致就 `PREFLIGHT_FAIL` + rc=2）。注意那段只在 `status.git.worktree` **非空**时生效。

**C3 —— 读的是冻结副本，无人告知。** preflight / quality-gate 读的是**副 worktree 里
已提交的 status 副本**，而 review 阶段编排者写的是**主区工作区**，两者永久不一致。
本轮 preflight 对 WP-03 报 `state=DISPATCHED`，而主区工作区已是 `CHANGES_REQUESTED`
（编排者刚写的 REWORK）。两个都「对」，只是读的不是同一份。
这是设计使然（状态文件只允许提交两次，中间的变更本就只在主区工作区累积），
**但没有任何一处提示读者「你看到的是冻结副本」**——所以编排者容易误以为
自己的状态写入生效了。

## 范围

**allowed_paths**
- `src/agentic_loop/wrappers/quality-gate.sh`
- `src/agentic_loop/wrappers/preflight.sh`
- `tests/test_quality_gate_wrong_worktree.py`
- `tests/test_gate_status_source_label.py`

**forbidden_paths**
- `.env`
- `.context/`
- `.agentic/config.toml`
- `src/agentic_loop/wrappers/kimi-health.sh`（属 WP-12）
- `src/agentic_loop/gate/`（判定逻辑不在本 WP，本 WP 只碰 wrapper 的前置校验与输出层）
- `src/agentic_loop/validate_wp_status.py`
- 其余一切未在 allowed 列出的路径

> 本 WP 属 `lane-gate`，排在 WP-12 之后**串行**：与 WP-11 同碰 `preflight.sh`、
> 与 WP-02 同碰 `quality-gate.sh`。不得与同 lane 任何 WP 并发。

## 输入

- 依赖的上游 WP 产出：WP-12 必须先 MERGED（同 lane 串行；且 WP-11 已改过 `preflight.sh`）
- 缺陷记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B5 §C3
- 现状代码：`quality-gate.sh:26`（未被使用的 `repo_root`）与 `:41-46`（改动集收集）；
  `preflight.sh:50-59`（现成的 worktree 一致性校验范式）

## 交付物清单

**B5 —— 拒绝跑错目录**

1. `quality-gate.sh` 在收集改动集**之前**加一道 fail-closed 前置校验：
   若 `status.git.worktree` 非空且解析出的绝对路径 ≠ 当前 worktree，
   直接 `QUALITY_GATE_FAIL: must run inside <declared worktree>` 并退出，
   **不做任何 scope 计算**。范式照 `preflight.sh:50-59`。
2. 退出码用现有的 `2`。**这是硬要求**：门的 rc 是契约（`0` / `2` / `64`），
   新增一种失败原因不等于新增一个 rc。
3. `status.git.worktree` 为空时（`APPROVED` 等宽松档允许为空）**不能**据此放行到
   错误目录，也不能因此报错——此时无声明可比对，按现状继续，
   但要在输出里说明「未声明 worktree，改动集取自当前目录」。
   > 这一条是本 WP 唯一的判断题：无声明时既不该假装校验过，也不该硬性拒绝
   > （那会挡住合法的宽松档用法）。如果你认为应当直接拒绝，
   > **不要自行改成拒绝**，写进 `[CONCERNS]` 让编排者裁。
4. 顺手删掉或真正用上第 26 行那个死变量 `repo_root`——它现在的存在会让读者
   误以为脚本已经处理了目录问题。**优先「真正用上」**：既然要做一致性校验，
   正好需要当前 worktree 的绝对路径。

**C3 —— 标注读取来源**

5. `preflight.sh` 与 `quality-gate.sh` 输出 state 的那些行显式标注来源，形如
   `state=DISPATCHED (from committed copy at <branch>)`。纯输出层，零判定风险。
   > 具体措辞由你定，但必须让读者一眼看出「这不是主区工作区的当前值」。
   > 若某条输出行本来就没有 state，不必强行加。

## 完成定义（DoD）

- [ ] **反向测试（B5 的硬要求）**：在**主区**对着一个声明了副 worktree 的 status
      跑 quality-gate → 断言 rc=2、输出含 `must run inside`，
      且**输出里不出现任何 `outside allowed scope` 字样**
      （即证明它在算 scope 之前就拒绝了，而不是先算出假越界再补一句警告）。
      这是本 WP 最硬的一条：B5 的危害正是假越界看起来像真违规。
- [ ] 正向测试：在**声明的 worktree 内**跑同一个 status → 前置校验放行，
      scope 判定行为与改动前完全一致（用现有 WP 的真实 status 做即可）
- [ ] 正向测试：`status.git.worktree` 为空时不因新校验而失败（宽松档不被挡）
- [ ] 测试：preflight 与 quality-gate 的 state 输出行含来源标注
- [ ] `quality-gate.sh` 与 `preflight.sh` 其余任何检查的行为与退出码不变
      （现有 gate/preflight 测试全绿即可证）
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

1. **这个 WP 给质量门加了一道新的拒绝路径，最大的风险是挡住合法调用。**
   `status.git.worktree` 为空的宽松档必须继续可用（交付物第 3 项），
   正向测试就是钉这个的。
2. **不要用 `cd` 把脚本挪进声明的 worktree 去「顺便修好」。** 那会让门在
   调用者不知情的情况下改变工作目录语义，比拒绝更危险。本 WP 的决定是**拒绝**，
   不是**纠正**。
3. `resolve_paths --root current_worktree` 与 `--root main_repo` 是两个不同的根，
   脚本里两者都出现过（第 26 行与第 112 行），改动时别把它们弄混——
   配置读 `main_repo`（INV-4），改动集看当前 worktree。
4. C3 是纯输出层。**不得**为了「让状态一致」去改读取来源（例如改成读主区工作区）——
   那会打穿「状态文件只提交两次」的纪律，且让门读到未提交的内容。
5. **本仓 Python 兼容 >= 3.9**；shell 部分跟随现有写法。
6. 测试命令用 `python3.11`：本机 `python3` 是 3.14 且没装 pytest。
   跑全量测试时**不要设** `AGENTIC_PYTHON`（见 §B3）。
7. 预存基线失败：`tests/test_finalize_merge_triple_sign.py` 的 4 个失败与本 WP
   无关，勿修。

## Allowed and forbidden paths

见上文「范围」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点，内容同上，
以 `<WP>.status.json` 的 `scope.allowed_paths` / `scope.forbidden_paths` 为机器权威。

## Completion definition

见上文「完成定义（DoD）」一节，此处为 `agentic dispatch-lint` 要求的英文标题锚点。

## Acceptance tests

`python3.11 -m pytest tests -q` 除 4 个预存基线失败外全绿。
本 WP 特有的正向 / 反向测试要求见上文 DoD。

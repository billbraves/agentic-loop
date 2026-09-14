# WP-18: engine 侧派发证明（DispatchProof）——替换 WP-17 可伪造的 author 判据

> 冻结日期 2026-09-14 | 编排者 claude-code | 执行者 kimi
> 基线 `plan/2026-09-13-parallel-throughput`
> **状态：已冻结，执行期间不得修改**（修订须走 re-freeze，出 `rev2`）

## 目标（一句话）

把独立性判据的来源证明从「执行者可自填的 git author」换成
「engine 自己 fork 子进程时观测到、执行者无法触及的派发事实」。

## 为什么必须换（A11 的实证）

WP-17 的 `author_differs_from_orchestrator` 已被实证可伪造：

```
同一操作者、同一终端，仅加环境变量：
  GIT_AUTHOR_NAME=totally-other-agent GIT_AUTHOR_EMAIL=other@agent.ai git commit
-> 四项判据全 True，evaluate() 返回 weak，合并门被骗过
-> reasons 打出假陈述 "change proven to originate elsewhere"
```

根因：`git author` 有三条自设途径（`git config user.*`、`GIT_AUTHOR_*`、
`git commit --author`），是**声明**不是**观测**。详见 `WP-08-candidate.md` §A11。

## 设计：唯一可信的信号在 engine fork 的那一刻

盘点本仓现有信号（已核实）：

| 信号 | 位置 | 执行者能否伪造 | 可用 |
|------|------|----------------|------|
| git author | commit | ✅ 三条途径 | ❌ A11 |
| `executor.tool` | status.json | ✅ 执行者可写 | ❌ |
| `identity_model` | `.agentic/config.toml` | ✅ 可编辑声明 | ❌ A10 |
| WP 锁 `owner`/`session_hint` | 主区 `.agentic/locks/` | ❌ §4.1 禁写主区 | ⚠️ 记的是**编排者** |
| **`subprocess.run` 返回的 pid/exit_code/输出** | `kimi.py:_run()` | ❌ engine 自己 fork | ✅ **本 WP 用这条** |

关键洞察：`adapters/kimi.py:_run()` 里的 `subprocess.run(cmd, ...)` 是 **engine
自己 fork 的进程**。子进程 pid、真实退出码、engine 拼出的 argv、fork 时刻，
全部由 engine 观测且**从不经过执行者的手**。执行者甚至无法知道自己的 pid 被记了。
`kimi.py:47` 当前 `session=None`，即这条链存在但没被采集 —— 这就是缺口。

## 范围

### allowed_paths
```
src/agentic_loop/adapters/base.py
src/agentic_loop/adapters/kimi.py
src/agentic_loop/redispatch.py
src/agentic_loop/independence.py
src/agentic_loop/gate/__init__.py
tests/test_dispatch_proof.py
tests/test_independence_dispatch_proof.py
```

### forbidden_paths
```
.env
.context/
.agentic/config.toml
.agentic/locks/
src/agentic_loop/wrappers/
src/agentic_loop/validate_wp_status.py
docs/plans/
```

## 交付物

### 1. `adapters/base.py`：`DispatchProof` frozen dataclass

```python
@dataclass(frozen=True)
class DispatchProof:
    """engine 在 fork 执行者子进程时观测到的派发事实。

    每一项都由 engine 自己产生，执行者无法读、无法写、无法预测。
    与 IsolationEvidence 的根本区别：那个读 git（执行者可造），
    这个读 engine 自己的 subprocess 句柄（执行者不可触及）。
    """
    dispatched_by_engine: bool = False   # engine 确实 fork 了子进程
    child_pid: int | None = None         # 子进程真实 pid
    exit_code: int | None = None         # 真实退出码
    argv_hash: str = ""                  # engine 拼出的 argv 的 sha256（含 worktree/model）
    dispatched_at: int | None = None     # fork 时刻 unix ts
    orchestrator_session: str = ""       # 编排者会话（锁 owner，主区不可写）
    executor_tool: str = ""              # engine 从 binding 解出的 tool，非 status 自填
```

全部默认 fail-closed（`False`/`None`/`""`）。

### 2. `adapters/kimi.py`：`_run()` 采集并回传

- `ImplementResult` 增 `proof: DispatchProof | None = None` 字段（默认 None 保后向兼容）
- `_run()` 用 `subprocess.Popen` 取代 `subprocess.run` **仅为拿到 pid**，
  其余行为逐字保持（stdout/stderr 合并、redact、退出码语义、OSError 处理）
- OSError 分支必须 `proof=None`（fork 失败 → 无证明 → fail-closed）

### 3. `redispatch.py`：落盘到 engine-only 字段

- 派发后把 `proof` 写入 status 的 `executor.dispatch_proof`
- ⚠️ **不得**改 `validate_wp_status.py`（在 forbidden_paths）——
  schema 校验的加严另立 WP，本 WP 只写不校验。在代码注释里写明这一点。

### 4. `independence.py`：新判据 `weak-dispatched`

```python
def evaluate(..., *, proof: DispatchProof | None = None) -> tuple[str, list[str]]:
```

- 位置：bootstrap 分支内，**排在 attestation 与 isolation 之后**（第四条并列出路）
- 放行条件（全部满足才给 `weak`）：
  `weak_ok` and `dispatched_by_engine` and `child_pid is not None`
  and `exit_code is not None` and `argv_hash` 非空 and `orchestrator_session` 非空
- reasons 必须写明 **`level=weak-dispatched`** 与全部原始值
- **永不评 strong**
- **`evaluate()` 必须保持纯函数**：无 I/O、无 subprocess/os/pathlib/git

### 5. `gate/__init__.py`：读回并传入

- 新增 `collect_dispatch_proof(status_file, validator)`：从 `executor.dispatch_proof`
  读回并构造 `DispatchProof`；任何字段缺失/类型错 → 该字段落 fail-closed 默认值
- `main()` 仅在 `is_bootstrap_normal` 时采集并传入
- 读取失败绝不抛 `GATE_FAIL`，退到 `None`

### 6. 两个测试文件

`test_dispatch_proof.py`：
- characterization：`proof=None` 时既有四条路径（none / weak-attested /
  weak-isolated / degraded）逐字不变
- 逐项反向：六个放行条件各自置 fail-closed 值 → `none`
- **反伪造用例（本 WP 的立命之处）**：证明执行者无法通过
  ① 改 `git config user.*` ② 设 `GIT_AUTHOR_*` ③ `git commit --author`
  ④ 自填 `status.json` 的任何字段 —— 使 `weak-dispatched` 放行
- `DispatchProof()` 裸默认 → `none`

`test_independence_dispatch_proof.py`：
- 优先级：WP-08 degraded > attestation > isolation > dispatch_proof，
  逐一验证前者生效时 reasons **不含** `weak-dispatched`
- `evaluate()` 纯函数 AST 核验
- strong 不可达
- `INDEPENDENCE_LEVELS` / `_LEVEL_RANK` 未变

## 完成定义（DoD）

- [ ] 七个交付物就绪，改动只落在 allowed_paths
- [ ] `python3.11 -m pytest tests -q` 相对基线零回归
      （基线 4 failed 为预存 `test_finalize_merge_triple_sign.py`，不得修）
- [ ] `evaluate()` 纯函数：函数体与模块级均无
      `subprocess`/`os`/`pathlib`/`Path`/`open`/`git`/`shutil`/`io`
- [ ] `INDEPENDENCE_LEVELS` 与 `_LEVEL_RANK` 逐字未变
- [ ] `weak-dispatched` 永不评 strong；`meets_threshold(weak,"strong")` 仍 False
- [ ] 四条既有路径优先级保持，前三条生效时 reasons 不含 `weak-dispatched`
- [ ] 反伪造用例覆盖上述四条途径且全部 `none`
- [ ] `DispatchProof` 的每个字段都能追溯到 engine 侧观测点，无一来自 status 自填

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 已知陷阱

1. **`Popen` 替换 `run` 必须行为等价**：`stdout=PIPE, stderr=STDOUT, text=True`
   语义、`communicate()` 后的退出码、`redact_env_value` 调用点、OSError 分支
   全部逐字保持。这是 characterization 的重点。
2. **不要碰 `validate_wp_status.py`**（forbidden）。编排者已实测：
   校验器的未知字段检查只作用于**顶层**（`:377-383` 的 `allowed = required |
   OPTIONAL_TOP_LEVEL`），`executor.dispatch_proof` 加进去返回 `STATUS_VALID`，
   **无需改 schema**。反过来说，这也意味着该字段当前**不受 schema 保护**——
   加严校验（禁执行者写 dispatch_proof）另立 WP，本 WP 只写不校验，
   须在代码注释里写明这个缺口。
3. **`argv_hash` 不要含密钥**：argv 里可能有 `--config-file <tmp>` 路径，
   哈希前先经 `secret_redaction`，或只哈希白名单字段（worktree/model/tool）。
4. **B7 已修**，`agentic` 现跑本仓 src/。但仍用 `python3.11 -m pytest` 自测，
   不要用 `agentic quality-gate` 自证（那会触发 A0 双签门，本 WP 正在修它）。
5. **A9 不在本 WP 范围**：若发现 degraded 路径异源比较返回 `strong`，
   那是已登记的预存缺陷，**不要顺手修**，报 `[CONCERNS]`。
6. **不得 merge / push / 切分支**。不得写 `docs/plans/`。

## 与既有判据的关系

```
有 developer 绑定       -> WP-08 degraded（实现者 model 可观测）      -> weak
无绑定 + 人工签署        -> WP-07 attestation                        -> weak-attested
无绑定 + engine 派发证明 -> 本 WP DispatchProof                       -> weak-dispatched
无绑定 + 仅 git 事实     -> WP-17 isolation（A11：可伪造，待返工降级） -> weak-isolated
全不满足                -> none（fail-closed，不变）
```

本 WP **不删除** WP-17 的 isolation 判据（那是 WP-17 返工的事），
只在其之后增加一条更强的并列出路。

## 执行报告格式

```
[STATUS] DONE / DONE_WITH_CONCERNS / BLOCKED
[COMMIT] hash / message
[CHANGES] - path (说明)
[TESTS]   - name: PASSED/FAILED
[CONCERNS]
[BLOCKER]
```

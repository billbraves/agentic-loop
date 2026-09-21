# WP-26 rev4: 「校验的字节 = 派发的字节」不变式，两个消费面一并收口

> 冻结日期 2026-09-17 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。
> 前序：rev1 `0a12bed`(B16) → rev2 `0b4deb2`(B21) → 加固 `16bfdf3` → rev3 `57cd572`(B25)。
> 本 rev 是**第 3 次 re-freeze**，已按任务 #24 规则完成停手复核计划，裁定见
> `WP-26-plan-review-before-rev4.md`（用户已批准 §5 的「两个消费面一并收口」）。

## 目标（一句话）

关掉「sha256 校验的那份字节」与「实际交给下游使用的那份字节」不是同一次读取造成的缺口，
python 与 bash 两个消费面同时收口。

## 本 rev 的验收标的是不变式，不是缺陷编号

**这是本 rev 与前三轮最根本的差别，务必按不变式实现与自检，不要只盯 B29 这个编号。**

> **INV-B（Brief 字节同一性）**：从 `evidence.brief.sha256` 校验通过，到下游判据/派发面
> 实际消费的正文，中间**不得有第二次对该文件的 I/O**。校验对象与使用对象必须是**同一次
> 读取得到的同一份字节快照**。这条要求对**所有**分支成立：声明路径分支、固定命名回退
> 分支、python 消费面、bash 消费面。

前三轮的失败点（B16 声明路径 / B21 分支覆盖 / B25 约束强度 / B29 读取同一性）是**同一条链
的四环**。rev4 收口的是最后一环，但**判据按不变式写**：任何一处「先校验、后重读」都算违反，
即便它不叫 B29、即便它在本轮 diff 之外。若你在 `allowed_paths` 内发现第三处同族缺口，
一并修掉并在报告里点名；不要因为 brief 没列编号就放过。

## Allowed and forbidden paths

**allowed_paths**（4 个文件）:

- `src/agentic_loop/redispatch.py`
- `src/agentic_loop/wrappers/dispatch_lint.sh`
- `tests/test_redispatch_brief_source.py`
- `tests/test_dispatch_lint_brief_source.py`

> 注意：本 rev 与 rev3 相反 —— rev3 是纯测试侧收紧、两个实现文件零 diff；
> **rev4 必须改实现**，因为缺口在实现里。rev3 的 `dispatch_lint.sh` 零 diff 约束在本 rev 解除，
> 但 rev3 建立的断言强度（见「不得改动」表）一条都不许退。

**forbidden_paths**:

- `src/agentic_loop/wrappers/preflight.sh` —— B22 同族但归任务 #27，**不要顺手修**
- `src/agentic_loop/wrappers/finalize_merge.sh`
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/gate/__init__.py`
- `src/agentic_loop/templates/`
- `tests/test_finalize_merge_triple_sign.py` —— 那 4 条是既有环境失败，**不要修**
- `CLAUDE.md`, `AGENTS.md`, `docs/agentic/OPERATING_MODEL.md`, `docs/plans/`
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## 输入

- 被审树：worktree `/Users/admin/vibe/wp26-brief-source-of-truth`，分支
  `feature/wp26-brief-source-of-truth`，HEAD `57cd572`（在其上叠加，**不要** reset）。
- 缺口位置（编排者本轮实测确证，非转述）：
  - **python 侧** `src/agentic_loop/redispatch.py:174-186`：`content = brief_path.read_text()`
    取得将要派发的正文，随后 `hashlib.sha256(brief_path.read_bytes())` **第二次**读盘算摘要。
    实测：拦 `Path.read_text` 使派发面得 EVIL、磁盘留 GOOD 供 `read_bytes` —— **sha256 对
    GOOD 校验通过，函数返回并派发 EVIL**。（macOS 上拦截需按 realpath 比对，`/var` →
    `/private/var` 会导致不命中。）
  - **bash 侧** `src/agentic_loop/wrappers/dispatch_lint.sh:64-141` 与 `:150`：进程 A 校验
    sha256 后只 `print(real)` 交出**路径**；bash 用 `sed -n '2p'` 取路径字符串；`:150` 起
    进程 B 再 `open(path).read()` **重读**做 section 判据。跨进程传路径而非已校验字节，
    窗口比 python 侧更宽（中间还隔一次 `[[ -f ]]` 和一次进程启动）。

## 交付物清单

1. **python 侧单次读取**：`raw = brief_path.read_bytes()` 只读一次；对 `raw` 算 sha256；
   返回内容从**同一个** `raw` 解码（`raw.decode("utf-8")`）。
   解码失败规范化为 `BriefIntegrityError`（不得让 `UnicodeDecodeError` 裸穿）。
   `OSError` 仍规范化为 `BriefIntegrityError`，措辞可保留现有两条中的任一条，但**同一次读取
   只应有一条读失败措辞**（原「cannot read brief」与「cannot compute brief sha256」在合并
   为单次读取后必然合并为一条，这是预期结果，不是丢证据）。
2. **bash 侧单次读取**：把已校验的**字节/正文本身**交给 section 判据，不再跨进程传路径重读。
   实现形态不限，下列任一皆可，选定后在报告里说明选择理由：
   - (a) 把 section 判据并入进程 A：同一个 python 进程内 `raw = open(real,"rb").read()`，
     算 sha256、跑 section 检查、最后才 print 结果；
   - (b) 进程 A 把已校验正文经 stdout/临时 fd 传给进程 B，进程 B **不再 open 路径**。
   > 若选 (a)，注意 bash 握手协议当前是「行1=BRIEF_OK，行2=路径」，`brief_file` 变量在
   > `:145` 的 `[[ -f ]]` 与 `:150` 处均有消费者，改动需一并收口；**不得**留下一个仍会重读的
   > 消费者。若某个下游确实只需要路径（不读内容），保留传路径是允许的，但报告须逐个列出
   > `brief_file` 的所有消费者并说明各自是否读内容。
3. **不得引入新的重读**：修完后，两个消费面对 brief 文件的 `open`/`read_text`/`read_bytes`
   调用次数各自**必须为 1**，并在报告里给出实测计数方式（如插桩计数或静态枚举 + 用例证明）。

## Acceptance tests

**A. 不变式的正面钉死（本 rev 核心判据，两个消费面各一条，必须用拦截/差分，不许读代码确认）**

1. **python 侧**：构造一条用例，使「校验面读到的字节」与「派发面拿到的字节」若来自两次不同
   读取则必然不同（例如 monkeypatch 使第一次读返回 GOOD、第二次读返回 EVIL，或反之），
   断言修复后的实现**不可能**出现「校验通过而派发 EVIL」。
   **反向差分（注意方向）**：这条用例断言的是「安全性质成立」（校验通过 ⇒ 派发的就是被校验的那份），
   所以在**旧实现**（`57cd572` 的 `_brief_content`，两次读）上该用例 **FAIL**，
   在**新实现**（单次 `read_bytes`）上 **PASS**。
   请在报告里给出这两次实测输出。
   （注意这与「变异用例」的方向相反：变异用例断言「必须转红」，故在旧实现上 FAIL 是因为红没出现；
   本条断言「必须安全」，在旧实现上 FAIL 是因为不安全被检出。两者都是「旧 FAIL / 新 PASS」，
   照这个方向写就不会错。）
2. **bash 侧**：同族一条。因为跨进程，拦截手法与 python 侧不同 —— 允许用
   「`AGENTIC_PYTHON` 前置一个记录型 python3」或「在两次读之间改盘上内容」等方式制造差分。
   方向同上：**旧实现（`57cd572` 的 `dispatch_lint.sh`）上该用例 FAIL、rev4 上 PASS**，
   报告给出两次实测输出。
   > 若你判断某种拦截手法在本仓不可行，**不得降级为「读代码确认只有一次 open」**，
   > 而应 BLOCKED 上报并说明为何不可行。静态计数只能作为交付物 3 的补充证据，
   > 不能替代这条差分用例。

**B. 每个 print point 各有原因特异的 witness（本 rev 的第二条硬要求）**

不变式修完后，两个消费面的失败出口如下（编排者已枚举，你须逐个覆盖）：

python 侧 `_brief_content` 的 `BriefIntegrityError` 出口（当前 6 处，合并读取后预期 5～6 处）：

| # | 出口 | 现措辞 |
|---|------|--------|
| 1 | `..` 逃逸 | `brief path escapes main repo: {p}` |
| 2 | symlink 逃逸 | `brief path escapes main repo (symlink): {p}` |
| 3 | 声明路径不存在 | `brief not found at {p}` |
| 4 | 读失败 | `cannot read brief: {exc}` |
| 5 | sha256 不匹配 | `brief sha256 mismatch: computed=… declared=…` |
| 6 | **新增**：解码失败 | 由你拟定，须与上面 5 条**互不相同** |

bash 侧 heredoc `fail()` 出口（当前 8 处，其中 #2/#3 与 #5/#6 措辞重复）：

| # | 行 | 现措辞 |
|---|----|--------|
| 1 | 84 | `cannot read status: {exc}` |
| 2 | 100 | `brief path escapes main repo: {path}` |
| 3 | 103 | `brief path escapes main repo: {path}` ← 与 #2 逐字相同 |
| 4 | 107 | `brief path escapes main repo (symlink): {path}` |
| 5 | 110 | `brief not found at {real}`（声明路径分支） |
| 6 | 116 | `brief not found at {real}`（回退分支） ← 与 #5 逐字相同 |
| 7 | 127 | `cannot compute brief sha256: {exc}` |
| 8 | 129 | `brief sha256 mismatch: …` |

要求：**每一个出口都要有一条用例，其断言能把失败原因钉到这一个出口，而不是钉到
「某个失败发生了」。** 具体地：

- 若两个出口措辞逐字相同（#2/#3、#5/#6），**必须**在实现里把措辞改成可区分的
  （例如 #3 补上 `(absolute)`、#6 补上 `(fallback)`），否则用例无法做到原因特异 ——
  这属于本 rev 允许且要求的实现改动。
- witness 由 **fixture 承载**：每条用例的输入只应触发它那一个出口。
  （见任务 #17 的教训：witness 的原因特异性由 fixture 而非断言的措辞承载。）
- 每条负面用例带 oracle 三项：① 正向可达性控制（同形状但合法的输入必须 PASS）
  ② 原因特异的 witness（断言精确措辞，非子串包含）③ 能让它转红的变异。
- **不许用「rc != 0」或「stderr 非空」这类真空通过的断言**（任务的既有教训）。

**C. rev3 的断言强度全部保留（回归即驳回）**

- `_assert_single_fail_token()` 的四条约束：stdout 逐字节空串、普通路径续行元组为空、
  多错路径精确声明续行元组、token 计数恰 1 且首行以 token 开头。
- 那 5 条 helper 单元测试（3 条逃逸转红 + 2 条正当路径不误红）全部保留。
- 「刻意不用全局 `len(splitlines())==1`」的拒用理由 docstring 保留。

**D. 变异与固化**

- forbidden 变异仍跑在 `shutil.copytree` 的 scratch 副本上，测后丢弃。
- **`DISPATCH_LINT_SHA256` 固定常量必须删除**：本 rev 要改 `dispatch_lint.sh`，
  锁死整个脚本 sha256 的常量与之直接冲突。改为 rev3 已有的
  「`live_before` 与结束时逐字节自比」，只证明活树未被本次测试变异，不锁实现内容。
  （codex 在 WP-26 rev3 复签里已建议移除该常量，本 rev 采纳。）

**E. 门禁与回归**

- 3.11 / 3.13 / 3.14 全绿。
- 相对基线零回归。基线（HEAD `57cd572`，编排者本轮实测）：
  - targeted `tests/test_dispatch_lint_brief_source.py` + `tests/test_redispatch_brief_source.py`
    = **29 passed**
  - 全量 3.11 = **4 failed, 626 passed, 4 skipped**，4 条失败全为
    `tests/test_finalize_merge_triple_sign.py` 的 `git checkout -q main` CalledProcessError
    （本机 `init.defaultBranch=master` 的环境失败，**不要修**）
- 活树两个实现文件的**修改前** sha256（供你确认起点一致）：
  - `dispatch_lint.sh` = `ca5d34de1ec67b9edd2c586ec5839a5ea389b67b13411ce73afbdda88d858363`
  - `redispatch.py` = `5ef6f0648aac0b062ad9ba7ea82663b5dc1442248380ac626d35bfe321b6d53c`

## 不得改动（前三轮已双签名通过，回归即驳回）

| 行为 | 现状 | 来源 |
|---|---|---|
| `evidence.brief.path` 声明优先于固定命名 | 已修 | rev1 (B16) |
| sha256 校验只依赖 `sha256` 在场，与 `path` 无关；位于两分支汇合之后 | 已修 | rev2 (B21) |
| 四种在场组合矩阵 + 「无 path + 对 sha256 → PASS」正控制 | 已齐备 | rev2 |
| 五种路径逃逸 fail-closed（`../` / 绝对 / symlink×2 / 不存在）全部 rc=2 | 已修 | rev1/rev2 |
| 失败输出契约：stdout 逐字节空、续行元组精确 | 已修 | rev3 (B25) |
| 变异测试跑 scratch 副本 | 已改 | rev2 |
| 回退分支的零回归语义（老 status 无 brief 块仍能派发） | 保持 | rev1 |

> 唯一解除的约束是 rev3 的「两个实现文件零 diff」—— 本 rev 必须改实现。
> 但**行为语义**只允许在「读取次数」和「出口措辞可区分性」两处变化，
> 其余对外可观察行为（rc、token 形状、拒收/放行判定）一律不变。

## Completion definition

- [ ] python 侧：单次 `read_bytes`，sha256 与返回内容同源；解码失败 → `BriefIntegrityError`
- [ ] bash 侧：section 判据消费已校验字节，不再跨进程传路径重读；`brief_file` 的所有消费者已逐个列出并交代
- [ ] 两个消费面对 brief 的读取调用各 1 次，报告给出实测计数
- [ ] A1 python 侧不变式差分用例：方向正确（旧实现 `57cd572` 上 FAIL、rev4 上 PASS），报告含两次实测输出
- [ ] A2 bash 侧不变式差分用例：同上方向（不可行则 BLOCKED，不得降级为静态确认）
- [ ] B：python 侧 5～6 个出口、bash 侧 8 个出口，**每个**都有原因特异 witness 的用例
- [ ] 重复措辞（bash #2/#3、#5/#6）已在实现里改为可区分
- [ ] 每条负面用例带 oracle 三项，无「rc != 0」式真空断言
- [ ] C：rev3 的四条输出契约约束 + 5 条 helper 用例 + 拒用理由 docstring 全部保留
- [ ] D：`DISPATCH_LINT_SHA256` 固定常量已删除，改为 `live_before` 逐字节自比
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（29 passed 只增不减；那 4 条既有失败不要修）
- [ ] 无 forbidden_paths 写入（特别是 `preflight.sh` 不许碰）、无跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

- production_writes: FORBIDDEN
- network: FORBIDDEN
- notifications: FORBIDDEN
- data_access: READ_ONLY

## 附注：已知陷阱

- **这是第 3 次 re-freeze，范围比前三轮大（4 文件、含实现）。** 扩大范围是用户批准的裁定：
  两个消费面同族、同在 `allowed_paths`，只修一面则另一面仍在，按点状修法继续切分只会招来
  第 4 次返工。但**不要再扩**：`preflight.sh` 的同族缺口（B22）已另立任务 #27，碰它算越界。
- **不要把 A1/A2 写成「读代码确认只有一次 open」。** 前三轮反复栽在「约束强度不足」上：
  静态确认无法阻止未来重新引入第二次读取，只有差分/拦截用例能。
- **反向差分的方向别写反。** 统一口径：**旧实现上该用例 FAIL、新实现上 PASS**。
  WP-27 曾因把方向写反而返工一轮，不要重踩。
- **不要因为 brief 只点名 B29 就只修 B29。** 判据是 INV-B，凡「先校验后重读」皆在范围内。
- **合并读取会让两条读失败措辞合并成一条**，这是预期结果。不要为了保住两条措辞而保留两次读取。
- macOS 上做拦截需按 realpath 比对（`/var` → `/private/var`），编排者第一次实测就栽在这。
- 若发现某条既有用例因本 rev 的措辞变更而假红，**改用例**（它在 `allowed_paths` 里），
  不要为迁就用例而放弃措辞可区分性。

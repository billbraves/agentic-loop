# WP-02: finalize 支持顺序型 WP（branch == base_branch）

> 冻结日期 2026-10-12 | 编排者 claude-code（DSH 会话）| 执行者 kimi。
> 所属 Plan：PLAN-01（集成到 `plan/2026-10-12-sequential-plan-gates`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（规则见「Re-freeze 规则」一节）。

## Re-freeze 规则（编排者冻结前自检）

- 第 3 次**及以后** re-freeze：冻结前必须停手复核计划，未经用户批准不得冻结。
- 验收标的必须写成**不变式**，台账编号只作破口清单，不得取代不变式成为标的。

## 目标（一句话）

让 `agentic finalize` 能 stamp 顺序型 WP（`git.branch == git.base_branch`），
同时**不削弱**并行道形态必须唯一解析出真实合并提交的要求。

## 背景（为何存在这个缺口）

`wrappers/finalize_merge.sh:380` 只认「WP 分支被合并进集成分支」产生的合并提交：

```bash
candidates=$(git -C "$repo_root" rev-list --merges --parents "$base_tip" \
  | awk -v t="$wp_tip" '$3==t{print $1}')
```

`$3` 是第二父。AGENTS.md §4.3 许可顺序型 WP 直接在集成分支上工作，此时
`wp_tip == base_tip`，这样的合并提交不存在 → 候选数 0 → 退出 2。而
`plan merge` 要求 WP 先 `MERGED`，形成死锁。

实测复现（probe-no-degrade，2026-10-12）：

```
FINALIZE_FAIL: cannot uniquely resolve merge commit for
  plan/2026-10-09-developer-probe-no-degrade tip 2c51aed... (found 0)
```

该 WP 最终由编排者手工 stamp，依据记录在 `8e3a7fe` 提交信息与
`2026-10-09-developer-probe-no-degrade/DESIGN.md` §5 的 G1 条。

## 取向（冻结）

**F1 判别依据是分支身份，不是候选数。** 顺序型分支的进入条件**必须**是
`branch == base_branch` 两个字段字符串相等。

**F2 顺序型分支下 `merged_commit = wp_tip`。** 顺序型 WP 的最终实现提交就是
它的集成点（它本来就在集成分支上）。

**F3 并行道路径一字不改。** `branch != base_branch` 时，候选解析、唯一性要求、
0/多候选的 fail-closed 行为全部保持现状。

**F4 `:371` 的祖先前置条件保留。** 同分支情形下它自动成立（提交是自己的祖先），
不需要为顺序型特判跳过；**不得**删除或弱化这一检查。

**F5 既有双签/三签闸门不受影响。** `review.decision` / `consult.decision`
必须 ACCEPT（v3 还要 `qoder_security`）的要求与本改动正交，一律保留。

## 范围

- **allowed_paths**（白名单，只能改这些）：
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `tests/test_finalize_merge_sequential.py`（新增）
- **forbidden_paths**（黑名单，绝不能碰）：
  - `src/agentic_loop/plan_cmd.py`（G2 的地盘，WP-03 负责；plan 层本就正常）
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/wrappers/codex_merge_gate.sh`
  - `src/agentic_loop/wrappers/merge.sh`
  - `src/agentic_loop/wrappers/preflight.sh`
  - `.agentic/config.toml`
  - `uv.lock`
  - 任何 `docs/plans/2026-10-09-developer-probe-no-degrade/**`（历史计划不回填）
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

## 输入

- 依赖的上游 WP 产出：无（本 WP 是 PLAN-01 的第一个）
- 参考文档：本迭代 `DESIGN.md` §1 G1 / §2 R1；AGENTS.md §4.3、§5
- 现场：`src/agentic_loop/wrappers/finalize_merge.sh:358-408`
- 既有测试搭 git fixture 的范式：`tests/test_finalize_merge_first_call.py:42`
  （`_run_git` helper）

## 交付物清单

- [ ] `src/agentic_loop/wrappers/finalize_merge.sh` — 按 F1 增加顺序型分流
- [ ] `tests/test_finalize_merge_sequential.py` — 下列 S1-S6 全部用例

## 验收不变式（标的）

以下是本 WP 的验收**标的**；S 编号只是破口清单，不得取代不变式。

**INV-1（顺序型可 stamp）**：当 `git.branch == git.base_branch` 且该 WP 双签
ACCEPT 时，`finalize` 退出 0，并把 `git.merged_commit` 写成 `wp_tip`，
`state` 写成 `MERGED`。

**INV-2（并行道零回归）**：当 `branch != base_branch` 时，行为与改动前逐字节
一致 —— 唯一候选时 stamp 该合并提交；0 候选或多候选时 fail-closed 退出 2。

**INV-3（顺序型不得成为兜底）**：`branch != base_branch` 且候选数为 0 时，
**必须**仍然失败，**不得**退化成「用 wp_tip 兜底」。这是本 WP 最重要的负面断言：
判别必须依据分支身份，而非解析结果为空。

**INV-4（双签仍然承重）**：顺序型路径下，`review.decision` 或
`consult.decision` 不是 ACCEPT 时仍然 fail-closed，不因走了新分支而放行。

**INV-5（幂等）**：已 `MERGED` 且已记录 `merged_commit` 的顺序型 WP，重跑
`finalize` 退出 0 并报 already finalized；若记录值与 `wp_tip` 不符则失败。

## Acceptance tests

本段与上文「交付物清单」「完成定义（DoD）」中的验收测试要求同义，非另一份口径。

每一份 WP 的每条负面断言都必须提供 oracle 校验四项证据：

1. **正向可达性对照**：在同一 fixture 上做一次不带注入/变异的正向运行，
   必须到达终点，证明前置条件确实可达终点。
2. **原因特异 witness**：负向运行必须给出原因特异的 witness（异常标记、
   状态或精确事件），证明失败被正确归因。
3. **代表性禁止变异转红**：至少一个代表性禁止变异（如改掉锚点标题、
   删去关键守卫）必须使测试转红。
4. **变异集按判据自身的组成步骤生成**：判据自检的变异集必须按判据自身的组成步骤生成，
   不得按已知缺陷清单枚举；某步骤不可攻击须在报告里写明理由。变异必须施加于判据
   真实的输入面（文件字节 / 进程边界 / 外部状态），不得只改判据已持有的内存表示。
   判别方式：把被修的缺陷还原成原状，该用例必须转红；仍绿则该用例不承重。
   同类输入面的等价载体（如临时副本）满足本项；若变异会写到被判据保护的制品
   本身，须优先选用不写该制品的等价载体。

注意：第 1 项证明「前置可达」，第 2 项证明「失败归因」，
**两者不能互相替代**——「无注入时能到终点」并不排除「带注入时死在别处」。

### 具名用例（破口清单）

每条都必须走**真实子进程**调用 `finalize_merge.sh`（不得只测 Python 内部函数），
并在临时 git 仓库里构造真实提交图。

- **S1 `[sequential-happy]`** → INV-1。造 `branch == base_branch` 的双签 WP，
  跑 finalize，断言 exit 0、`state == MERGED`、`merged_commit == wp_tip`。
- **S2 `[parallel-happy]`**（正向可达性对照，oracle 第 1 项）→ INV-2。
  造真实的 `feature/x` 合并进集成分支，断言 exit 0 且 stamp 的是那个**合并提交**
  （不是 `wp_tip`）。
- **S3 `[parallel-unmerged-must-fail]`** → INV-3，**本 WP 的决定性用例**。
  造 `branch != base_branch` 且**从未合并**的 WP，断言 exit 2 且 stdout/stderr
  含 `cannot uniquely resolve merge commit`（原因特异 witness，oracle 第 2 项）。
  断言 `merged_commit` **未被**写入，尤其不得等于 `wp_tip`。
- **S4 `[parallel-multi-candidate]`** → INV-2 后半。构造两个合并提交其第二父同为
  `wp_tip`（可对同一分支尖端合并两次到不同集成分支状态），断言 exit 2。
  若该图在 git 下不可构造，须在报告里写明理由并说明替代构造。
- **S5 `[sequential-double-sign-still-load-bearing]`** → INV-4。顺序型 fixture，
  把 `consult.decision` 改成 `REWORK`，断言 exit 2（不得因走顺序型路径而放行）。
- **S6 `[sequential-idempotent]`** → INV-5。S1 之后重跑 finalize，断言 exit 0
  且报 already finalized；再把 `merged_commit` 篡改成别的 40 位 sha，断言 exit 2。

### 必须保持绿的集合（零回归）

```
pytest tests/test_finalize_merge_first_call.py \
       tests/test_finalize_merge_toctou.py \
       tests/test_finalize_merge_triple_sign.py \
       tests/test_finalize_merge_wrapper_sync.py \
       tests/test_plan.py -q
```

### 承重自检（DoD 必做，报告须附逐条结果）

按 oracle 第 4 项，变异须按判据自身组成步骤生成，而非按已知缺陷枚举。
至少包含以下具名变异，逐条「施加 → 跑指定用例 → 确认转红 → 还原 → 确认回绿」：

- **M-1**：把 F1 的判别条件由 `branch == base_branch` 改成
  `candidate_count -eq 0` → **S3 必须转红**。
  （这正是 INV-3 要禁的那个错误实现；若 S3 不红，说明 S3 不承重。）
- **M-2**：顺序型分支里把 `merged_commit` 由 `wp_tip` 改成 `base_tip` 之外的
  任意固定值（如 `HEAD~1`）→ **S1 必须转红**。
- **M-3**：删掉 `:371` 的祖先前置检查 → 至少一条用例必须转红；若全绿，
  须在报告中说明该检查在哪条用例下承重，或承认它当前不承重。
- **M-4**：在顺序型路径上跳过双签校验 → **S5 必须转红**。
- **M-5**：把顺序型判别写成**单**字段比较（只比 `branch` 非空、不比两者相等）
  → S2 或 S3 必须转红。

变异施加于**文件字节**（脚本源文件的临时副本或原地改后还原），不得只改
内存中的参数。每条变异的锚点必须在文件内**唯一**；若不唯一，须在报告里
声明 `occurrence` 序号。

## 完成定义（DoD）

- [ ] 交付物逐项就绪
- [ ] S1-S6 全绿
- [ ] M-1 ~ M-5 逐条红证齐备（含还原回绿），报告附逐条结果
- [ ] 「必须保持绿的集合」全绿
- [ ] 全量 `python3.11 -m pytest tests -q` 不低于基线（基线须在报告中实测记录）
- [ ] `agentic quality-gate <status.json>` 全绿
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

> 若需偏离默认（如生产写入），须编排者 + 独立顾问双重审核并在此记录授权原因。

## 附注

- **已知陷阱 1**：最容易写错的实现是「候选数为 0 就用 wp_tip 兜底」。它能让
  S1 通过、看起来修好了，但会把并行道的真实故障（分支没合、合并提交被 rebase
  掉）伪造成成功 stamp。INV-3 + S3 + M-1 三者专为钉死这一点。
- **已知陷阱 2**：`finalize_merge.sh` 有 TOCTOU 加固（单次 `O_NOFOLLOW` 打开，
  见文件头 A34 注释）。改动**不得**引入对 `$status_file` 的二次 `open`/读取，
  否则 `tests/test_finalize_merge_toctou.py` 应当转红 —— 若它没红，请在报告里
  指出该测试的覆盖边界。
- **已知陷阱 3**：`set -euo pipefail` 下，用 `x=$(cmd)` 形式承接可能非零退出的
  判定会直接中断脚本（文件头 A29 注释已记录同类事故）。新增判定须用 `if !` 形式
  fail-closed，不得追加 `|| true` / `|| echo false`。
- **dogfood 机会**：本 WP 落地后，PLAN-01 自己（顺序型形态）的收敛就应当能用
  `agentic finalize` 正常 stamp。编排者会以此做端到端验证；若仍需手工 stamp，
  说明 F1/F2 没真正修好。
- 口径权威源引用：`src/agentic_loop/wrappers/finalize_merge.sh:380`（候选解析）、
  `:371`（祖先前置）、`:398`（状态闸门）；AGENTS.md §4.3（顺序 WP 在集成分支上工作）。

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

本段与上文「范围」一节中的 allowed_paths / forbidden_paths 完全同义，
非另一份口径：只能改 allowed_paths 白名单内的路径，绝不能碰
forbidden_paths 黑名单；owner 边界对齐 CODEOWNERS，不跨 owner 写入。

## Completion definition

本段与上文「完成定义（DoD）」一节同义，非另一份口径：交付物逐项就绪、
验收测试全绿、无 forbidden_paths / 跨 owner 写入、无生产写入/网络/通知/
推送，commit message 符合规范。

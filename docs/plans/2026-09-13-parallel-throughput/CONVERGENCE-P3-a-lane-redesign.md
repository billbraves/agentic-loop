# CONVERGENCE-P3-a · lane 全局重设计（落地记录）

> 日期：2026-09-20（用户「按建议执行」放行）
> 范围：**仅重分配在途 WP 的 `lane` 字段**（消除并行撞车）。不含 WP-09~14 存量重估（产品判断）、不冻结、不派发、不改任何 WP 的 `state`。
> 落地对象：`PLAN-01.status.json`。本文档为 P3-a 的分析与决策记录（Git-visible，符合 §10）。

## 1. 方法

1. 提取 12 个在途 WP（非 MERGED：09/10/11/12/13/14/15/17/18/23/25/26）status.json 的 `scope.allowed_paths`（**全部为精确文件路径**，无 glob/目录，重叠判断可靠）。
2. 构建 `file → [WP]` 映射，找出被 ≥2 个在途 WP 声明的文件（撞车点）。
3. 以「文件重叠」为边构建 WP 图，用并查集求连通分量。
4. **同一连通分量内的 WP 必须同 lane 串行**（lane 是串行等价类：同 lane 任一时刻只一个 READY WP 被 `plan lanes` 挑中）；不同分量无文件重叠，可分属不同 lane 并行。

## 2. 撞车点与连通分量

**11 个被 ≥2 个在途 WP 碰的文件**：

| 文件 | 触碰者 |
|---|---|
| `src/agentic_loop/adapters/base.py` | WP-12, WP-17, WP-18 |
| `src/agentic_loop/adapters/kimi.py` | WP-12, WP-15, WP-18 |
| `src/agentic_loop/gate/__init__.py` | WP-17, WP-18, WP-23 |
| `src/agentic_loop/independence.py` | WP-17, WP-18 |
| `src/agentic_loop/redispatch.py` | WP-18, WP-26 |
| `src/agentic_loop/resolve_paths.py` | WP-09, WP-23 |
| `src/agentic_loop/wrappers/preflight.sh` | WP-11, WP-13 |
| `AGENTS.md` | WP-11, WP-12 |
| `src/agentic_loop/templates/AGENTS.md.tmpl` | WP-11, WP-12 |
| `docs/agentic/templates/STATUS.json` | WP-10, WP-14 |
| `src/agentic_loop/templates/STATUS.json.tmpl` | WP-10, WP-14 |

**3 个连通分量**：

- **分量1（9个）**：WP-09, WP-11, WP-12, WP-13, WP-15, WP-17, WP-18, WP-23, WP-26
- **分量2（2个）**：WP-10, WP-14
- **分量3（1个）**：WP-25

## 3. lane 方案

| 分量 | lane | 成员 | 语义 |
|---|---|---|---|
| 1 | `lane-core` | WP-09/11/12/13/15/17/18/23/26 | 核心引擎纠缠簇（adapters/gate/independence/redispatch/resolve_paths/preflight/AGENTS），全串行 |
| 2 | `lane-template` | WP-10/14 | STATUS 模板（保留原 lane） |
| 3 | `lane-contract` | WP-25 | 契约渲染（contract_render/CLAUDE.md.tmpl），独立 |

- `depends_on` 链保留不动：WP-12→[WP-11]、WP-13→[WP-12]、WP-14→[WP-10]（真实先后依赖，与 lane 串行叠加）。
- MERGED WP（01/03/08/19/21/22/24/27/28/29）的 lane 不动（不参与就绪集）。
- 改动：10 个 lane 字段（WP-09/11/12/13 改值；WP-15/17/18/23/25/26 由省略 default 补明确 lane）+ `timestamps.updated_at`。

## 4. 验证（基线 vs 重设计后）

`agentic plan lanes`：

- **基线（重设计前）** READY = {WP-09(lane-config), WP-10(lane-template), WP-11(lane-gate), WP-15(default)}。此就绪集**恰好**无直接重叠，但属脆弱偶然：一旦 WP-15 done，default lane 会挑 WP-17（碰 base.py），同时 WP-11 done 后 lane-gate 挑 WP-12（也碰 base.py）→ **WP-12 vs WP-17 撞 base.py**。
- **重设计后** READY = {WP-09(lane-core), WP-10(lane-template), WP-25(lane-contract)}，三者 allowed_paths 无共同文件；分量1 其余 8 个 WP 被 `lane-core` same-lane serialization 串行。**任意时刻跨 lane 挑中的 WP 必属不同连通分量（无文件重叠）→ 无撞车**。

`agentic plan check`：`state=ACTIVE`、22 WP 无 `MISSING`、无 `PLAN_INVALID`（schema 合法）、not converged（12 pending）。

## 5. 并行度上限与根因（重要）

- **最大安全并行度 = 3**（lane-core / lane-template / lane-contract 各一）。
- **瓶颈是分量1**：9 个核心引擎 WP 因文件纠缠必须全串行，P3 批量派发时只能一个接一个。根因是 **WP-18 为枢纽**（一个 WP 碰 base.py/kimi.py/redispatch.py/independence.py/gate 五个核心文件，直接撞 6 个 WP），叠加 WP-12/17/23/26/15/09/11/13 的链式重叠。
- **提升并行度须重拆 WP**（缩小各 WP 的 allowed_paths、消除文件所有权交叠），这属于比 lane 重设计更深一层的结构调整，**超出 P3-a 范围**，须另立裁定。lane 重设计只能在现有 WP 拆分粒度下给出安全调度，不能凭空创造并行度。

## 6. 禁区遵守 + 提交

- 只改 `PLAN-01.status.json`（lane 字段 + updated_at）；未动 6 个无关未提交改动（`.agentic/config.toml`/`AGENTS.md`/`CLAUDE.md`/`docs/agentic/OPERATING_MODEL.md`/`src/agentic_loop/provider.py`/`tests/test_provider.py`）与 `uv.lock`；未清理工作树；未冻结/派发任何 WP；未 push。
- 分析脚本（`.agentic/tmp_lane_analysis.py`、`.agentic/tmp_apply_lane.py`）为 local state，用后删除，不提交。
- 提交：`git add` + `git commit --` 显式路径（`PLAN-01.status.json` + 本记录）。

## 7. 后续

- **P3 其余部分**：WP-09~14 存量重估（逐个核验其目标缺陷 A1/A2/B1~B6 是否已被 WP-19/21/22/24/27 修复，可能可 APPROVE→直接 MERGED 或需 REWORK）；批量派发（须逐步批准）。
- **P1**：门禁修复批 WP-30~33（待 B32 全文）。
- **并行度**：若须突破分量1 的串行瓶颈，另立「WP 重拆」裁定（缩小 allowed_paths 交叠）。

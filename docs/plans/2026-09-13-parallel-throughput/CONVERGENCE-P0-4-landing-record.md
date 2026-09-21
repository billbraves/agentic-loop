# CONVERGENCE-P0-4 落地记录：PLAN-01 对账修订（#4 批准落地）

> 编排者 claude ｜ 落地日期 2026-09-20 ｜ 依据 CONVERGENCE-PLAN.md §2 #4（用户批准）
> 本文件是 `CONVERGENCE-P0-4-plan-reconciliation.md` 草案的**落地记录**。
> 草案 §4/§5 修订建议已于 2026-09-20 经用户批准并落地到 `PLAN-01.status.json` 本体；
> 草案末尾「本文件是草案，不修改本体」声明自此失效——**以本落地记录为准**。

## 1. 落地动作

编辑 `PLAN-01.status.json` 本体（用户批准 #4）：

- 移除废弃 WP-02/04/05/06/07（5 个）
- 增补实际推进的 WP-15/17/18/19/21/22/23/24/25/26/27/29（12 个）
- 清理 WP-11 `depends_on`：`["WP-04"]`→`[]`（WP-04 废弃）
- `state`：DRAFT→ACTIVE
- `timestamps.updated_at`：刷新到落地时刻
- work_packages 总数：15→22

提交信息前缀 `📋 plan(2026-09-13-parallel-throughput): PLAN-01 对账修订（P0-4 草案落地）`，
与本文件同批显式路径提交。

## 2. lane 落地实况

- WP-19→`lane-gate`（草案 §4.2 明确）
- 其余 11 个增补 WP **省略 `lane` 字段**，由 `plan_cmd._normalize_work_packages`
  落到 `DEFAULT_LANE="default"`（表达「P3 待定」）
- `depends_on` 全 `[]`
- WP-12/13/14 的既有 depends_on 链（`[WP-11]`/`[WP-12]`/`[WP-10]`）保留未动

## 3. `agentic plan check` 实测（EXIT=3 not converged，预期）

- `state=ACTIVE`
- 22 个 WP 全部识别、**无 MISSING**（对比草案 §0 现状的 5 个 MISSING）
- 各 state 与草案 §4.5 逐项一致
- 末行 `not converged (12 WP(s) pending)`

**§4.5 笔误更正**：草案 §4.5 末行与下方文字写「11 个未 MERGED」，实际为 **12 个**
（WP-09/10/11/12/13/14/15/17/18/23/25/26）。§4.5 列表本身已列全 12 项，仅末行计数「11」
是笔误；plan check 实测 `12 WP(s) pending` 为正确值。

## 4. `agentic plan lint` 实测（EXIT=3，DIRTY）

22 个 WP 全报 DIRTY，根因两类：

1. **历史 status-sync 中间提交**（WP-01/03/08/17/18/19/21/22/24/25/26/27/28/29）：
   如 `d3f2be2d`/`11a4c224`（WP-01/03/08 记 consult 与 override）、各 WP 的
   review/consult/dispatch/refreeze 逐次提交。违反 AGENTS.md §4.3 commit discipline
   （status 应只在 freeze 与 finalize 各提交一次，签名决策累积到 finalize 一次提交），
   但属**本 plan 历史遗留**——#4 修订前即存在，且 #4 只改 plan status、不产生任何提交，
   故 **lint DIRTY 非 #4 引入**。
2. **在途 WP finalize x0**（WP-09~15/23/25/26）：尚未 MERGED，无 finalize 提交，属预期。

**影响与处置**：lint DIRTY 是 P6 `agentic plan merge` 的**前置障碍**（§4.3：merge fails
closed unless every WP MERGED AND commit-discipline lint clean）。修复历史 status-sync 须
rewrite 已提交历史（属禁区，且集成分支已有大量后续提交），故**不在 #4 范围**；记录备查，
留待 P6 前由用户裁定（清理历史 vs 豁免 lint）。**不阻塞 #4 落地**（#4 是 plan status 修订，
非 plan merge）。

## 5. 遗留风险（草案 §6 风险 1 仍成立）

增补 WP 的 lane 为 fail-safe 归置（重叠簇落 default 串行），但跨现有 lane 的文件重叠未解：

- WP-23（default）碰 `resolve_paths.py`，与 WP-09（lane-config）同文件
- WP-18 碰 `adapters/base.py`/`adapters/kimi.py`/`redispatch.py`/`independence.py`/`gate/__init__.py`，
  与 WP-15（kimi.py）/WP-17（base.py、independence.py、gate）/WP-26（redispatch.py）全撞
- WP-17/18/23 均碰 `gate/__init__.py`

P3 实际派发前**必须**全局重设计 lane（含 WP-09~14 与全部在途增补 WP），并用
`agentic plan lanes` 复核就绪集，否则并行派发会撞车。当前 default 归置只保证「不并行即不撞」，
不保证并行安全。

## 6. 禁区遵守

- 未碰 6 个无关未提交改动（`.agentic/config.toml`、`AGENTS.md`、`CLAUDE.md`、
  `docs/agentic/OPERATING_MODEL.md`、`src/agentic_loop/provider.py`、`tests/test_provider.py`）与 `uv.lock`
- 未冻结、未派发任何 WP
- 未 push
- 未清理任何工作树
- 仅改 `PLAN-01.status.json` 本体（#4 授权范围）+ 本落地记录

## 7. 后续（待用户指示）

#4 落地后解锁 P1/P3。下一步候选（须用户明确批准后逐步执行，每步走完整门禁）：

- **P1**：新立 WP-30~33 门禁修复批（前置：B32 全文缺口须用户补全）
- **P3**：WP-09~14 存量重估 + lane 全局重设计（解 §5 风险）+ 批量派发
- **#6/#7**：WP-25/26/18 rev5 停手复核草稿批准冻结（re-freeze=3 门）

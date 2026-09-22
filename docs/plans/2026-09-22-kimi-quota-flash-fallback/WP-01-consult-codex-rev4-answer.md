CODEX_DECISION: REWORK

1. CODEX_FINDING #1：闭环  
   [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:324) 已加入畸形 TOML 文件 fixture。真实解析入口 [resolve_paths.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/resolve_paths.py:129) 通过 `tomllib.load` 读取文件。用 Python 3.11 实测该内容抛出 `tomllib.TOMLDecodeError: Expected ']' at the end of a table declaration`。因此 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:361) 的 `except Exception` 删除后，异常必然逃逸，该测试转红。

2. CODEX_FINDING #2：闭环  
   [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:148) 已拆成三个独立承重点：
   - (a1) `except Exception` 对应 malformed TOML witness；
   - (a2) `isinstance`/非空守卫对应 [bad_override 测试](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:316)，删除守卫后空列表返回 `()`、字符串返回字符 tuple，均不再等于默认值；
   - (b) `except re.error` 对应坏正则 witness，守卫位于 [is_quota_error](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:269)。  
   (a1) 与 (a2) 已不再共用 witness，rev3 的不可执行根因消除。

3. CODEX_FINDING #3：部分闭环  
   Acceptance tests §3 已同步，见 [WP-01-brief.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:134)；C1 mutation-probe 也已同步，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:1032)。但测试计数仍不一致：
   - B1 实际定义 7 个 test functions，不是 [8 passed](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:277)；
   - B2 追加 4 个后合计应为 11，不是 [12 passed](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:369)；
   - 三个新增测试文件合计为 `11 + 5 + 10 = 26` 个 test functions，不是 IMPLEMENTATION-PLAN [约 21 个](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:952) 和 brief [约 21 个](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01-brief.md:77)。

CODEX_RATIONALE:

rev4 已实质关闭 `except Exception` 的 oracle 缺口，INV-2 的三个 mutation witness 现在真实、独立且可执行。此前确认的坏正则防线、范围守卫 fail-closed、额度语义收窄、main() 接线、架构落点和单跳控制流均未发现回退；范围守卫仍具备 `set -euo pipefail`、基线有效性校验及非空失败，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:962)。

brief 实际 SHA-256 为 `5a694a7ea27dd7a8b6095d353a90cf62b65dfedaadbeaa244d821ce8f6575f13`，与 [WP-01.status.json](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/WP-01.status.json:62) 的 rev4 锚定一致。但 finding #3 明确要求同步测试计数，目前精确验收输出仍会与计划不符，因此尚不能冻结。剩余修改仅是文档计数校正，不应扩大到源码、架构、adapter 或 gate。

CODEX_FINDINGS:

1. 有界修正以下计数：
   - B1 Step 4：`8 passed` → `7 passed`；
   - B2 Step 4：`12 passed` → `11 passed`；
   - B6 Step 1：`新增 ~21 个` → `新增 26 个`；
   - brief DoD：`新增 ~21 个` → `新增 26 个`。
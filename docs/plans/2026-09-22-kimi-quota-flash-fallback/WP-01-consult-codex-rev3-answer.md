CODEX_DECISION: REWORK

1. Finding #1：部分闭环  
   坏正则分支已闭环：测试通过真实 `patterns` 参数传入非法正则，删除 `is_quota_error` 的 `except re.error` 后首个断言会直接抛出 `re.error`，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:191) 和同文件 [is_quota_error](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:257)。

   但 config 回落分支尚未完全闭环。`test_load_patterns_fails_safe_on_bad_override` 目前只测试空列表和错误类型，见 [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:316)；两者都不会触发 `except Exception`。因此删除 `load_quota_patterns` 的 `except Exception` 后，这些测试仍会全绿，与 INV-2 声称的承重变异不符。真实 `_load_config` 会直接解析 TOML，畸形 TOML 可抛解析异常，见 [resolve_paths.py](/Users/admin/vibe/.worktrees/kqff/src/agentic_loop/resolve_paths.py:129)。

2. Finding #2：闭环  
   [IMPLEMENTATION-PLAN.md](/Users/admin/vibe/.worktrees/kqff/docs/plans/2026-09-22-kimi-quota-flash-fallback/IMPLEMENTATION-PLAN.md:951) 已具备 `set -euo pipefail`、非空基线断言、commit 有效性检查、集合差文件非空失败和 forbidden diff 非空失败。空基线、无效基线、`git diff` 失败及越界路径都会非零退出；只有两项结果均为空才打印 `SCOPE_GUARD_PASS`。原先“`comm` 输出了违规项但退出 0”的假绿路径已经消除。

CODEX_RATIONALE:

rev3 已正确修复坏正则 oracle 和范围守卫；rev2 已确认的额度模式收窄、INV-W1/W2 接线测试，以及架构落点、主档 binding 隔离、单跳控制流和密钥消费面仍成立。brief 的实际 SHA-256 也与 status 中 rev3 的 `0883b6a1…` 完整值一致。

当前唯一阻断仍是 INV-2(a) 对 `except Exception` 的承重声明不可执行，属于 oracle 四证据不足，而非实现期细节。补齐一个畸形 TOML 用例即可有界关闭。

CODEX_FINDINGS:

1. 在 B2 增加畸形 TOML 测试，例如写入无法解析的 `.agentic/config.toml`，断言 `load_quota_patterns(repo)` 返回 `DEFAULT_QUOTA_PATTERNS` 且不抛异常。删除 `load_quota_patterns` 的 `except Exception` 后，该测试必须因 TOML 解析异常转红。
2. 将 INV-2 映射明确拆绑：
   - 删除 `except Exception` → 畸形 TOML 测试转红；
   - 删除 `isinstance`/非空守卫 → 现有空列表或错误类型测试转红。
3. 同步 Acceptance tests §3、C1 mutation-probe 和 B2 测试计数。其余内容无需扩大修改范围。
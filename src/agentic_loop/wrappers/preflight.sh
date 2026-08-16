#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <work-package-status.json>" >&2
  exit 64
fi

status_file=$1
# Locate sibling wrappers relative to THIS script's own directory so a bundled
# copy under agentic_loop/wrappers/ calls its co-located siblings — not an
# absent scripts/agentic/ in an external pip-install project. macOS BSD readlink
# has no -f, so resolve via dirname + cd (never `readlink -f`).
here="$(cd "$(dirname "$0")" && pwd)"
# git-optional preamble: inside the framework repo, prepend the live source path
# so dogfood edits take effect without reinstall; outside any git repo (external
# pip-install consumer) skip the prepend and rely on the already-installed
# agentic_loop module. `git rev-parse` runs best-effort so its non-zero does not
# trip `set -e`.
main_root=""
if _gcd="$(git rev-parse --git-common-dir 2>/dev/null)"; then
  main_root="$(dirname "$(cd "$_gcd" && pwd)")"
  export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$main_root/packages/agentic-loop/src"
fi
repo_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root current_worktree) || { echo "PREFLIGHT_FAIL: resolver failed to resolve current_worktree" >&2; exit 2; }
branch=$(git branch --show-current)
primary_worktree=$(git worktree list --porcelain | awk '/^worktree / {print substr($0, 10); exit}')

"${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file"

expected_branch=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field git.branch)
expected_worktree=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field git.worktree)
state=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field state)

if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  echo "PREFLIGHT_FAIL: implementation is forbidden on $branch" >&2
  exit 2
fi

if [[ "$(cd "$repo_root" && pwd -P)" == "$(cd "$primary_worktree" && pwd -P)" ]]; then
  echo "PREFLIGHT_FAIL: implementation must run in a secondary worktree" >&2
  exit 2
fi

if [[ "$branch" != "$expected_branch" ]]; then
  echo "PREFLIGHT_FAIL: current branch $branch != status branch $expected_branch" >&2
  exit 2
fi

if [[ -n "$expected_worktree" ]]; then
  case "$expected_worktree" in
    /*) expected_abs=$expected_worktree ;;
    *) expected_abs="$primary_worktree/$expected_worktree" ;;
  esac
  if [[ "$(cd "$repo_root" && pwd -P)" != "$(cd "$expected_abs" && pwd -P)" ]]; then
    echo "PREFLIGHT_FAIL: current worktree does not match status worktree" >&2
    exit 2
  fi
fi

case "$state" in
  APPROVED|DISPATCHED|IMPLEMENTING|CHANGES_REQUESTED) ;;
  *)
    echo "PREFLIGHT_FAIL: state $state is not executable" >&2
    exit 2
    ;;
esac

if ! git ls-files --error-unmatch "$status_file" >/dev/null 2>&1; then
  echo "PREFLIGHT_FAIL: status file must be tracked before implementation" >&2
  exit 2
fi

# 并发闸（concurrency lock）：实现/返工前必须持有本 WP 锁。
# 见 docs/superpowers/specs/2026-08-01-agentic-concurrency-lock-design.md §5.1
# 锁/lint 脚本只在主仓存在（唯一事实源），用 resolver 求主仓根定位它们（INV-4）。
main_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root main_repo) || { echo "PREFLIGHT_FAIL: resolver failed to resolve main_repo" >&2; exit 2; }

# 派发前只读硬门：校验不过不该占锁（lint 必须在锁 acquire 之前）。
if ! lint_reason=$("$here/dispatch_lint.sh" "$status_file" 2>&1 >/dev/null); then
  echo "PREFLIGHT_FAIL: dispatch-lint ${lint_reason:-unknown}" >&2
  exit 2
fi

# Autonomy gate (opt-in): dispatch_developer requires approval unless [autonomy]
# auto-approves it (ultra mode) or the human-approved env override is set.
# AUTONOMY_NOT_CONFIGURED (no [autonomy] section) does not gate — backward compat.
autonomy_out=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.autonomy dispatch_developer 2>/dev/null || true)
if [[ "$autonomy_out" == AUTONOMY_STOP* ]] && [[ "${AGENTIC_AUTONOMY_APPROVE:-0}" != "1" ]]; then
  echo "PREFLIGHT_STOP: autonomy requires human approval (dispatch_developer); set AGENTIC_AUTONOMY_APPROVE=1 after human approval" >&2
  exit 3
fi

iter=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field iteration_id)
wp=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field work_package_id)
if ! lock_out=$("$here/lock.sh" acquire --kind wp --key "${iter}__${wp}"); then
  echo "PREFLIGHT_FAIL: WP 锁未取得 —— $lock_out" >&2
  echo "  （另一个会话正在此 WP 上作业；确认其已停止后可 lock.sh acquire --force-takeover）" >&2
  exit 2
fi
echo "LOCK: $lock_out" >&2

echo "PREFLIGHT_PASS branch=$branch state=$state worktree=$repo_root"

#!/usr/bin/env bash
# Local no-ff merge of an APPROVED_FOR_MERGE work package into its base branch.
#
# This gate replaces the bare `git merge --no-ff` an orchestrator used to type by
# hand. It carries the [autonomy] policy check (local_merge_no_ff) plus integrity
# preconditions so the merge can never fire without approval, on the wrong
# branch, or across an invalid commit range.
#
# Safety scope: only the LOCAL merge. It never pushes (push stays a hard
# always_stop action elsewhere); finalize_merge.sh stamps state=MERGED afterwards.
set -euo pipefail

usage() { echo "usage: $0 <work-package-status.json>" >&2; exit 64; }
[[ $# -eq 1 ]] || usage
status_arg=$1

# Locate sibling wrappers relative to THIS script's own directory (mirrors
# finalize_merge.sh so a bundled copy calls its co-located siblings).
here="$(cd "$(dirname "$0")" && pwd)"

# git-optional preamble: inside the framework repo, prepend the live source path
# so dogfood edits take effect without reinstall; outside any git repo rely on
# the already-installed agentic_loop module.
main_root=""
if _gcd="$(git rev-parse --git-common-dir 2>/dev/null)"; then
  main_root="$(dirname "$(cd "$_gcd" && pwd)")"
  export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$main_root/packages/agentic-loop/src"
fi
repo_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root main_repo) || { echo "MERGE_FAIL: resolver failed to resolve main_repo" >&2; exit 2; }

# Status file is the single source of truth in the main repo.
case "$status_arg" in
  /*) status_file="$status_arg" ;;
  *) status_file="$repo_root/$status_arg" ;;
esac

# WP-02 single authority (agentic_loop.gate.path_is_in_worktree), the same
# WORKTREE refusal semantics as preflight.sh:37-50 and finalize_merge.sh: a
# status path that resolves inside a linked worktree is refused — the main-repo
# copy is the single source of truth. The git-fact predicate is referenced,
# never reimplemented: the retired path-literal test (a glob match on a
# dot-worktrees path segment) missed every sibling worktree
# (`git worktree add ../wpN-x`), the layout this repo actually uses
# (A13, WP-19). The literal is spelled out in prose, not as a contiguous
# string, so F6's conservative raw scan of .sh files needs no exemption here.
#
# Fail-closed form (INV-B): a probe crash, missing Python, failed import or any
# unexpected stdout collapses into PROBE_FAIL via `|| echo PROBE_FAIL`, and the
# `!= "MAIN"` comparison below refuses it. Only the exact verdict MAIN passes;
# never append `|| true`/`|| echo false` here, which would turn a crashed probe
# into "not a worktree" (fail-open).
wt_verdict=$("${AGENTIC_PYTHON:-python3}" - "$status_file" <<'PY' 2>/dev/null || echo PROBE_FAIL
import sys
from pathlib import Path
from agentic_loop.gate import path_is_in_worktree
print("WORKTREE" if path_is_in_worktree(Path(sys.argv[1])) else "MAIN")
PY
)
if [[ "$wt_verdict" != "MAIN" ]]; then
  echo "MERGE_FAIL: status file resolves inside a worktree ($status_file); pass the main-repo copy" >&2
  exit 2
fi
if [[ ! -f "$status_file" ]]; then
  echo "MERGE_FAIL: status file not found at $status_file" >&2
  exit 2
fi

field() { "${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field "$1"; }

if ! "${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" >/dev/null; then
  echo "MERGE_FAIL: status validation failed" >&2
  exit 2
fi

state=$(field state)
branch=$(field git.branch)
base_branch=$(field git.base_branch)
git_commit=$(field git.commit)

# Autonomy gate (opt-in): local_merge_no_ff requires approval unless [autonomy]
# auto-approves it (ultra mode). AUTONOMY_NOT_CONFIGURED does not gate.
autonomy_out=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.autonomy local_merge_no_ff 2>/dev/null || true)
if [[ "$autonomy_out" == AUTONOMY_STOP* ]] && [[ "${AGENTIC_AUTONOMY_APPROVE:-0}" != "1" ]]; then
  echo "MERGE_STOP: autonomy requires human approval (local_merge_no_ff); set AGENTIC_AUTONOMY_APPROVE=1 after human approval" >&2
  exit 3
fi

# Preconditions (fail before any git mutation).
if [[ "$state" != "APPROVED_FOR_MERGE" ]]; then
  echo "MERGE_FAIL: state must be APPROVED_FOR_MERGE (got $state)" >&2
  exit 2
fi
if [[ -z "$branch" ]]; then
  echo "MERGE_FAIL: git.branch is required" >&2
  exit 2
fi
if [[ -z "$base_branch" ]]; then
  echo "MERGE_FAIL: git.base_branch is required" >&2
  exit 2
fi

# Must run ON the base branch (never merge into a worktree branch).
current=$(git -C "$repo_root" branch --show-current)
if [[ "$current" != "$base_branch" ]]; then
  echo "MERGE_FAIL: must run on base branch $base_branch (current: $current)" >&2
  exit 2
fi

# Integrity: the WP branch tip must exist and git.commit must be its ancestor.
wp_tip=$(git -C "$repo_root" rev-parse --verify --quiet "refs/heads/$branch^{commit}") || {
  echo "MERGE_FAIL: cannot resolve branch '$branch' tip" >&2
  exit 2
}
if [[ -n "$git_commit" ]] && ! git -C "$repo_root" merge-base --is-ancestor "$git_commit" "$wp_tip"; then
  echo "MERGE_FAIL: git.commit ($git_commit) is not an ancestor of branch tip ($wp_tip)" >&2
  exit 2
fi

# Refuse to merge a branch into itself (base == branch).
if [[ "$branch" == "$base_branch" ]]; then
  echo "MERGE_FAIL: branch == base_branch ($branch); nothing to merge" >&2
  exit 2
fi

# Execute the local no-ff merge, preserving the WP branch history.
if ! git -C "$repo_root" merge --no-ff --no-edit "$branch"; then
  conflicted=$(git -C "$repo_root" diff --name-only --diff-filter=U 2>/dev/null || true)
  if [[ -n "$conflicted" ]]; then
    echo "MERGE_FAIL: merge conflicts in:" >&2
    while IFS= read -r f; do
      [[ -n "$f" ]] && echo "    - $f" >&2
    done <<< "$conflicted"
    echo "  resolve then: git -C $repo_root merge --continue   (or abort: git -C $repo_root merge --abort)" >&2
  else
    echo "MERGE_FAIL: git merge --no-ff $branch failed" >&2
  fi
  exit 2
fi

merged_commit=$(git -C "$repo_root" rev-parse HEAD)
echo "MERGE_OK merged_commit=$merged_commit branch=$branch into=$base_branch"
echo "MERGE_NEXT: run 'agentic finalize $status_arg' to stamp state=MERGED"

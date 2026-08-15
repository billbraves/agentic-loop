#!/usr/bin/env bash
# Finalize a work-package status after the orchestrator has manually merged it.
# Writes only status.json; never checks out, merges, or pushes git state.
set -euo pipefail

usage() { echo "usage: $0 <work-package-status.json>" >&2; exit 64; }

[[ $# -eq 1 ]] || usage
status_arg=$1

# Locate sibling wrappers relative to THIS script's own directory so a bundled
# copy under agentic_loop/wrappers/ calls its co-located sibling — not an absent
# scripts/agentic/ in an external pip-install project. macOS BSD readlink has no
# -f, so resolve via dirname + cd (never `readlink -f`).
here="$(cd "$(dirname "$0")" && pwd)"

# git-optional preamble: inside the framework repo, prepend the live source path
# so dogfood edits take effect without reinstall; outside any git repo (external
# pip-install consumer) skip the prepend and rely on the already-installed
# agentic_loop module. `git rev-parse` runs best-effort so its non-zero does not
# trip `set -e`. macOS BSD readlink has no -f, so resolve via dirname + cd.
main_root=""
if _gcd="$(git rev-parse --git-common-dir 2>/dev/null)"; then
  main_root="$(dirname "$(cd "$_gcd" && pwd)")"
  export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$main_root/packages/agentic-loop/src"
fi
repo_root=$(python3 -m agentic_loop.resolve_paths --root main_repo) || { echo "FINALIZE_FAIL: resolver failed to resolve main_repo" >&2; exit 2; }

# Status file is the single source of truth in the main repo. Resolve relative
# paths against main repo root, not cwd (which may be a worktree).
case "$status_arg" in
  /*) status_file="$status_arg" ;;
  *) status_file="$repo_root/$status_arg" ;;
esac

# Refuse worktree-local copies: they are branch-local working-tree state, not
# the shared source of truth. Mirrors codex_merge_gate.sh:42-45.
if [[ "$status_file" == *"/.worktrees/"* ]]; then
  echo "FINALIZE_FAIL: status file resolves inside a worktree ($status_file); pass the main-repo copy (single source of truth)" >&2
  exit 2
fi

if [[ ! -f "$status_file" ]]; then
  echo "FINALIZE_FAIL: status file not found at $status_file" >&2
  exit 2
fi

field() { python3 -m agentic_loop.validate_wp_status "$status_file" --field "$1"; }

# Step 1: schema/state-machine validation.
if ! python3 -m agentic_loop.validate_wp_status "$status_file" >/dev/null; then
  echo "FINALIZE_FAIL: status validation failed" >&2
  exit 2
fi

# Read status fields required for the merge-finalization decision.
schema_version=$(field schema_version)
state=$(field state)
review_decision=$(field review.decision)
consult_decision=$(field consult.decision)
git_commit=$(field git.commit)
tests_json=$(field evidence.tests)
base_branch=$(field git.base_branch)
branch=$(field git.branch)
iteration_id=$(field iteration_id)
wp_id=$(field work_package_id)
merged_commit_recorded=$(field git.merged_commit)

# Read the optional consult.override fields for the honest-REWORK escape hatch.
# Missing or incomplete override resolves to empty values and therefore fails
# closed below; this mirrors validate_wp_status._override_is_legal exactly.
override_approved=$(field consult.override.approved 2>/dev/null || true)
override_approver=$(field consult.override.approver 2>/dev/null || true)
override_justification=$(field consult.override.justification 2>/dev/null || true)
override_reviewed_at=$(field consult.override.reviewed_at 2>/dev/null || true)
override_legal="false"
if [[ "$override_approved" == "True" && -n "$override_approver" && -n "$override_justification" && -n "$override_reviewed_at" ]]; then
  override_legal="true"
fi

# Read the optional qoder_security third-signature fields. Missing or incomplete
# values resolve to empty and therefore fail closed below; this mirrors
# validate_wp_status._qoder_security_satisfied exactly. This block is read-only:
# a FINDINGS/ERROR decision is never rewritten to PASS here.
qoder_decision=$(field qoder_security.decision 2>/dev/null || true)
qoder_override_approved=$(field qoder_security.override.approved 2>/dev/null || true)
qoder_override_approver=$(field qoder_security.override.approver 2>/dev/null || true)
qoder_override_justification=$(field qoder_security.override.justification 2>/dev/null || true)
qoder_override_reviewed_at=$(field qoder_security.override.reviewed_at 2>/dev/null || true)
qoder_override_legal="false"
if [[ "$qoder_override_approved" == "True" && -n "$qoder_override_approver" && -n "$qoder_override_justification" && -n "$qoder_override_reviewed_at" ]]; then
  qoder_override_legal="true"
fi

# Step 2: preconditions (any failure means do not mutate status).
if [[ "$review_decision" != "ACCEPT" && "$review_decision" != "N/A" ]]; then
  echo "FINALIZE_FAIL: review.decision must be ACCEPT or N/A (got $review_decision)" >&2
  exit 2
fi

if [[ "$consult_decision" != "ACCEPT" && "$override_legal" != "true" ]]; then
  echo "FINALIZE_FAIL: consult.decision must be ACCEPT (got $consult_decision)" >&2
  exit 2
fi

# v3-only third signature: qoder_security must be PASS or carry a complete,
# approved override. v2 stays double-sign only (no qoder requirement), so this
# branch is keyed on schema_version alone — never on block presence (INV-6).
if [[ "$schema_version" == "agentic-wp-status/v3" ]]; then
  if [[ "$qoder_decision" != "PASS" && "$qoder_override_legal" != "true" ]]; then
    echo "FINALIZE_FAIL: qoder_security.decision must be PASS or carry a complete approved override (got $qoder_decision)" >&2
    exit 2
  fi
fi

if [[ -z "$git_commit" ]]; then
  echo "FINALIZE_FAIL: git.commit is empty" >&2
  exit 2
fi

if [[ -z "$tests_json" || "$tests_json" == "[]" ]]; then
  echo "FINALIZE_FAIL: evidence.tests is empty" >&2
  exit 2
fi

# Resolve branch tips in the main repo (read-only).
wp_tip=$(git -C "$repo_root" rev-parse --verify --quiet "refs/heads/$branch^{commit}") || {
  echo "FINALIZE_FAIL: cannot resolve branch '$branch' tip" >&2
  exit 2
}

base_tip=$(git -C "$repo_root" rev-parse --verify --quiet "refs/heads/$base_branch^{commit}") || {
  echo "FINALIZE_FAIL: cannot resolve base branch '$base_branch' tip" >&2
  exit 2
}

# Integrity precondition: the WP branch tip must already have been merged into
# base. This prevents marking MERGED before the orchestrator actually merged.
if ! git -C "$repo_root" merge-base --is-ancestor "$wp_tip" "$base_tip"; then
  echo "FINALIZE_FAIL: merge not detected (branch tip $wp_tip is not an ancestor of base $base_tip)" >&2
  exit 2
fi

# Step 3: precisely resolve the merge commit that introduced this WP tip.
# Match merge commits in base history whose second parent equals wp_tip.
# Never fall back to base_tip: under concurrency base_tip may be another WP's
# merge commit. Codex plan-consultation BLOCKING/Q3.
candidates=$(git -C "$repo_root" rev-list --merges --parents "$base_tip" | awk -v t="$wp_tip" '$3==t{print $1}')
candidate_count=$(printf '%s' "$candidates" | grep -c '^[0-9a-f]\{40\}$' || true)

# Step 7: idempotency for an already-finalized WP.
if [[ "$state" == "MERGED" && -n "$merged_commit_recorded" ]]; then
  if [[ "$candidate_count" -ne 1 ]]; then
    echo "FINALIZE_FAIL: cannot uniquely resolve merge commit for $branch tip $wp_tip (found $candidate_count)" >&2
    exit 2
  fi
  resolved=$(printf '%s' "$candidates")
  if [[ "$merged_commit_recorded" != "$resolved" ]]; then
    echo "FINALIZE_FAIL: recorded merged_commit != resolved ($merged_commit_recorded vs $resolved)" >&2
    exit 2
  fi
  echo "FINALIZE_OK merged_commit=$resolved (already finalized)"
  exit 0
fi

if [[ "$state" != "APPROVED_FOR_MERGE" ]]; then
  echo "FINALIZE_FAIL: state must be APPROVED_FOR_MERGE or MERGED (got $state)" >&2
  exit 2
fi

if [[ "$candidate_count" -ne 1 ]]; then
  echo "FINALIZE_FAIL: cannot uniquely resolve merge commit for $branch tip $wp_tip (found $candidate_count)" >&2
  exit 2
fi

merged_commit=$(printf '%s' "$candidates")

# Step 4 & 5: atomic write with self-validation.
updated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

tmp_status=$(mktemp "$status_file.XXXXXX")
trap 'rm -f "$tmp_status"' EXIT

python3 - "$status_file" "$tmp_status" "$merged_commit" "$updated_at" <<'PY'
import json, sys
src, dst, merged_commit, updated_at = sys.argv[1:5]
with open(src, encoding="utf-8") as fh:
    data = json.load(fh)
data["state"] = "MERGED"
data["git"] = dict(data.get("git", {}))
data["git"]["merged_commit"] = merged_commit
data["timestamps"] = dict(data.get("timestamps", {}))
data["timestamps"]["updated_at"] = updated_at
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

if ! python3 -m agentic_loop.validate_wp_status "$tmp_status" >/dev/null; then
  echo "FINALIZE_FAIL: post-write validate failed" >&2
  exit 2
fi

mv "$tmp_status" "$status_file"
trap - EXIT

# Step 6: release the WP advisory lock. Failure is advisory only.
lock_key="${iteration_id}__${wp_id}"
release_err=$(mktemp)
if ! "$here/lock.sh" release --kind wp --key "$lock_key" >/dev/null 2>"$release_err"; then
  echo "FINALIZE_WARN: WP lock release failed ($(cat "$release_err" 2>/dev/null || echo unknown))" >&2
fi
rm -f "$release_err"

echo "FINALIZE_OK merged_commit=$merged_commit"

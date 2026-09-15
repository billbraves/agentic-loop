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
repo_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root main_repo) || { echo "FINALIZE_FAIL: resolver failed to resolve main_repo" >&2; exit 2; }

# Status file is the single source of truth in the main repo. Resolve relative
# paths against main repo root, not cwd (which may be a worktree).
case "$status_arg" in
  /*) status_file="$status_arg" ;;
  *) status_file="$repo_root/$status_arg" ;;
esac

# Refuse worktree-local copies: they are branch-local working-tree state, not
# the shared source of truth. Mirrors codex_merge_gate.sh:42-45.
# A13: git-fact judgment instead of a "/.worktrees/" path literal (sibling
# worktrees like ../wpN-x never contain that segment). The single
# authoritative predicate is agentic_loop.gate.path_is_in_worktree (§5.3);
# this wrapper only references it. Unresolvable paths fail closed (refused).
#
# A34: the predicate and every downstream read ("-f", both validator calls,
# every --field, the old-JSON read) used to re-resolve the path string
# independently, leaving a symlink-swap TOCTOU window between judgment and
# use. The probe below collapses judgment and reads onto ONE opened file:
# one Python process runs predicate -> os.open(O_NOFOLLOW) -> read -> validate
# -> extract the decision fields, and hands everything back in a single
# result. A symlink swapped in after the predicate is refused by O_NOFOLLOW
# at open time (final-segment symlinks only; mid-directory swaps are the
# declared residual surface), so no third party can re-point the path between
# the worktree verdict and the reads that feed the decision. The plain
# assignment keeps the probe fail-closed: any probe crash aborts this script
# under set -e instead of being mistaken for a verdict.
probe=$("${AGENTIC_PYTHON:-python3}" - "$status_file" <<'PY'
import errno
import json
import os
import sys
from pathlib import Path

from agentic_loop.gate import path_is_in_worktree
from agentic_loop.validate_wp_status import validate

# (dotted status path, bash-safe variable name, required)
REQUIRED_FIELDS = (
    ("schema_version", "schema_version"),
    ("state", "state"),
    ("review.decision", "review_decision"),
    ("consult.decision", "consult_decision"),
    ("git.commit", "git_commit"),
    ("evidence.tests", "tests_json"),
    ("git.base_branch", "base_branch"),
    ("git.branch", "branch"),
    ("iteration_id", "iteration_id"),
    ("work_package_id", "wp_id"),
)
OPTIONAL_FIELDS = (
    ("git.merged_commit", "merged_commit_recorded"),
    ("consult.override.approved", "override_approved"),
    ("consult.override.approver", "override_approver"),
    ("consult.override.justification", "override_justification"),
    ("consult.override.reviewed_at", "override_reviewed_at"),
    ("qoder_security.decision", "qoder_decision"),
    ("qoder_security.override.approved", "qoder_override_approved"),
    ("qoder_security.override.approver", "qoder_override_approver"),
    ("qoder_security.override.justification", "qoder_override_justification"),
    ("qoder_security.override.reviewed_at", "qoder_override_reviewed_at"),
)


def lookup(data, dotted):
    value = data
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def render(value):
    # Exact --field rendering: containers as compact JSON, None as empty.
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def emit(verdict):
    print(f"FINALIZE_PROBE\t{verdict}")


path = sys.argv[1]

# 1) Worktree predicate on the path (WP-19 single authority, referenced only).
if path_is_in_worktree(Path(path)):
    emit("WORKTREE")
    sys.exit(0)

# 2) Open ONCE with O_NOFOLLOW and never re-resolve: a symlink swapped in
# after the predicate is refused here instead of being followed by the reads.
try:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
except FileNotFoundError:
    emit("NOT_FOUND")
    sys.exit(0)
except OSError as exc:
    emit("SYMLINK" if exc.errno == errno.ELOOP else "OPEN_FAILED")
    sys.exit(0)

try:
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        raw = handle.read()
except IsADirectoryError:
    emit("NOT_FOUND")
    sys.exit(0)

try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"STATUS_INVALID: invalid JSON at line {exc.lineno}: {exc.msg}", file=sys.stderr)
    emit("INVALID")
    sys.exit(0)
if not isinstance(data, dict):
    print("STATUS_INVALID: status root must be a JSON object", file=sys.stderr)
    emit("INVALID")
    sys.exit(0)

# 3) Whole-file schema/state-machine validation (same rules as the CLI).
errors = validate(data)
if errors:
    for error in errors:
        print(f"STATUS_INVALID: {error}", file=sys.stderr)
    emit("INVALID")
    sys.exit(0)

lines = ["FINALIZE_PROBE\tOK"]
for dotted, var in REQUIRED_FIELDS:
    found, value = lookup(data, dotted)
    if not found:
        # Mirror `--field` on a missing key: STATUS_INVALID on stderr plus exit
        # 2; the plain assignment above then aborts this script under set -e.
        print(f"STATUS_INVALID: unknown field {dotted}", file=sys.stderr)
        sys.exit(2)
    lines.append(f"{var}\t{render(value)}")
for dotted, var in OPTIONAL_FIELDS:
    found, value = lookup(data, dotted)
    # Missing optional fields resolve to empty (fail-closed), like the guarded
    # `field ... 2>/dev/null || true` reads this probe replaces.
    lines.append(f"{var}\t{render(value) if found else ''}")
print("\n".join(lines))
PY
)

probe_head=${probe%%$'\n'*}
probe_kind=${probe_head#*$'\t'}
case "$probe_kind" in
  WORKTREE)
    echo "FINALIZE_FAIL: status file resolves inside a worktree ($status_file); pass the main-repo copy (single source of truth)" >&2
    exit 2 ;;
  NOT_FOUND)
    echo "FINALIZE_FAIL: status file not found at $status_file" >&2
    exit 2 ;;
  SYMLINK)
    echo "FINALIZE_FAIL: status file is a symlink ($status_file); refusing to follow it (finalize must read the real main-repo file)" >&2
    exit 2 ;;
  OPEN_FAILED)
    echo "FINALIZE_FAIL: cannot open status file at $status_file" >&2
    exit 2 ;;
  INVALID)
    echo "FINALIZE_FAIL: status validation failed" >&2
    exit 2 ;;
  OK)
    ;;
  *)
    echo "FINALIZE_FAIL: status probe returned an unparseable verdict" >&2
    exit 2 ;;
esac

# Read status fields required for the merge-finalization decision, as handed
# back by the probe from the ONE opened file (A34).
probe_fields=${probe#*$'\n'}
while IFS=$'\t' read -r probe_key probe_value; do
  [[ -n "$probe_key" ]] && printf -v "$probe_key" '%s' "$probe_value"
done <<< "$probe_fields"

# A12: git.merged_commit is the field THIS script writes, so it is absent on
# the first finalize call. The probe resolves it to empty (fail-closed),
# never aborts — same semantics as the guarded read it replaces.

# The optional consult.override fields for the honest-REWORK escape hatch.
# Missing or incomplete override resolves to empty values and therefore fails
# closed below; this mirrors validate_wp_status._override_is_legal exactly.
override_legal="false"
if [[ "$override_approved" == "True" && -n "$override_approver" && -n "$override_justification" && -n "$override_reviewed_at" ]]; then
  override_legal="true"
fi

# The optional qoder_security third-signature fields (already extracted by the
# probe; missing resolves to empty). Missing or incomplete values fail closed
# below; this mirrors validate_wp_status._qoder_security_satisfied exactly.
# This block is read-only: a FINDINGS/ERROR decision is never rewritten to
# PASS here.
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

# Autonomy gate (opt-in): when the project defines [autonomy] and finalize_merge
# is not auto-approved, require an explicit human approval before stamping MERGED.
# AUTONOMY_NOT_CONFIGURED (no [autonomy] section) does not gate — backward compat.
autonomy_out=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.autonomy finalize_merge 2>/dev/null || true)
if [[ "$autonomy_out" == AUTONOMY_STOP* ]] && [[ "${AGENTIC_AUTONOMY_APPROVE:-0}" != "1" ]]; then
  echo "FINALIZE_STOP: autonomy requires human approval (finalize_merge); set AGENTIC_AUTONOMY_APPROVE=1 after human approval" >&2
  exit 3
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

if ! "${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$tmp_status" >/dev/null; then
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

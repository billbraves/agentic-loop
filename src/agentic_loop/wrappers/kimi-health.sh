#!/usr/bin/env bash
# Single-shot health measurement for a dispatched kimi worker (甲-3a).
# Pure measurement only: reads status.state + kimi output tail hash + git dirty,
# accumulates a frozen counter across calls via a snapshot file, prints exactly
# one contract line to stdout. Does NOT launch kimi, write status, kill procs,
# touch locks, or decide re-dispatch — that is the orchestrator's job.
# Spec: docs/superpowers/specs/2026-08-02-kimi-health-dispatch-monitoring-design.md
set -euo pipefail

err() { echo "HEALTH_ERROR: $1" >&2; exit "${2:-64}"; }

if [[ $# -ne 3 ]]; then
  err "usage: $0 <status-json> <kimi-output-file> <snapshot-file>" 64
fi

status_json=$1
output_file=$2
snapshot_file=$3

read_state() {  # read_state <status-json> -> prints .state, or errors
  python3 - "$1" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except FileNotFoundError:
    sys.exit(65)
except json.JSONDecodeError:
    sys.exit(65)
if not isinstance(d, dict):
    sys.exit(65)
print(d.get("state") or "")
PY
}

if ! state=$(read_state "$status_json"); then
  err "cannot read status state from $status_json" 65
fi

: "${TAIL_LINES:=40}"

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
main_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root main_repo) || err "resolver failed to resolve main_repo" 66

tail_hash() {  # tail_hash <output-file> -> sha of last TAIL_LINES (empty if absent)
  local f="$1"
  [[ -f "$f" ]] || { echo "d41d8cd98f00b204e9800998ecf8427e"; return 0; }
  tail -n "$TAIL_LINES" "$f" | shasum | awk '{print $1}'
}

worktree_path() {  # resolve status .git.worktree relative to main_root
  local wt
  wt=$(python3 - "$status_json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print((d.get("git") or {}).get("worktree") or "")
PY
)
  [[ -z "$wt" ]] && { echo ""; return 0; }
  case "$wt" in /*) echo "$wt";; *) echo "$main_root/$wt";; esac
}

git_dirty_sig() {  # git_dirty_sig <worktree> -> "lines:sha" or "nogit"
  local wt="$1"
  [[ -z "$wt" ]] && { echo "nogit"; return 0; }
  local porcelain
  if ! porcelain=$(git -C "$wt" status --porcelain 2>/dev/null); then
    return 66
  fi
  local n sha
  n=$(printf '%s' "$porcelain" | grep -c . || true)
  sha=$(printf '%s' "$porcelain" | shasum | awk '{print $1}')
  echo "${n}:${sha}"
}

wt_path=$(worktree_path)
th=$(tail_hash "$output_file")
if ! ds=$(git_dirty_sig "$wt_path"); then
  err "git status failed for worktree $wt_path" 66
fi

: "${FROZEN_STALL_TICKS:=3}"
: "${FROZEN_HARD_TICKS:=7}"

# DONE takes precedence over freeze logic.
case "$state" in
  READY_FOR_REVIEW|BLOCKED)
    echo "DONE $state"
    python3 - "$snapshot_file" "$state" "$th" "$ds" 0 <<'PY'
import json, sys
json.dump({"state": sys.argv[2], "tail_hash": sys.argv[3],
           "dirty_sig": sys.argv[4], "frozen": int(sys.argv[5])},
          open(sys.argv[1], "w"), ensure_ascii=False)
PY
    exit 0
    ;;
esac

# Read previous snapshot (absent => baseline).
read_snap() {
  python3 - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("::baseline"); sys.exit(0)
print("\t".join([d.get("state","") or "", d.get("tail_hash","") or "",
                 d.get("dirty_sig","") or "", str(d.get("frozen",0))]))
PY
}

prev=$(read_snap "$snapshot_file")
if [[ "$prev" == "::baseline" ]]; then
  frozen=0; changed="baseline"
else
  IFS=$'\t' read -r p_state p_th p_ds p_frozen <<<"$prev"
  changed=""
  [[ "$state" != "$p_state" ]] && changed="${changed}state,"
  [[ "$th" != "$p_th" ]] && changed="${changed}tail,"
  [[ "$ds" != "$p_ds" ]] && changed="${changed}dirty,"
  if [[ -n "$changed" ]]; then
    frozen=0
  else
    frozen=$(( p_frozen + 1 ))
  fi
fi

# One-line tail excerpt for human adjudication (single-lined, truncated, escaped).
tail_excerpt() {
  [[ -f "$output_file" ]] || { echo ""; return 0; }
  tail -n 1 "$output_file" | tr '\n\r\t' '   ' | sed 's/"/'"'"'/g' | cut -c1-200
}

# Emit exactly one contract line.
if [[ "$frozen" -ge "$FROZEN_STALL_TICKS" ]]; then
  if [[ "$frozen" -ge "$FROZEN_HARD_TICKS" ]]; then
    # Hard freeze = the frozen_hard soft-limit signal. Health only REPORTS the
    # signal name; the orchestrator classifies it via
    # `agentic autonomy signal frozen_hard`.
    echo "FROZEN_7m soft_limit=frozen_hard tail=\"$(tail_excerpt)\""
  else
    echo "FROZEN_${frozen}m tail=\"$(tail_excerpt)\""
  fi
else
  echo "PROGRESS ${changed%,}"
fi

# Persist snapshot.
python3 - "$snapshot_file" "$state" "$th" "$ds" "$frozen" <<'PY'
import json, sys
json.dump({"state": sys.argv[2], "tail_hash": sys.argv[3],
           "dirty_sig": sys.argv[4], "frozen": int(sys.argv[5])},
          open(sys.argv[1], "w"), ensure_ascii=False)
PY

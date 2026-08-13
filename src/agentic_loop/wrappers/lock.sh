#!/usr/bin/env bash
# Advisory double-layer lock for concurrent agentic orchestration.
# WP lock: who is editing a work package. Merge lock: who writes to main HEAD.
# mkdir is the atomic primitive; owner.json holds owner + heartbeat.
# See docs/superpowers/specs/2026-08-01-agentic-concurrency-lock-design.md
set -euo pipefail

TTL_MIN="${AGENTIC_LOCK_TTL_MIN:-30}"

die() { echo "$1" >&2; exit "${2:-64}"; }

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
repo_root=$(python3 -m agentic_loop.resolve_paths --root main_repo) || die "LOCK_FAIL: resolver failed to resolve main_repo" 2
locks_root="$repo_root/.agentic/locks"

cmd="${1:-}"; shift || true
kind=""; key=""; owner=""; note=""; takeover=0; force=0; show_all=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind) kind="$2"; shift 2;;
    --key) key="$2"; shift 2;;
    --owner) owner="$2"; shift 2;;
    --note) note="$2"; shift 2;;
    --takeover) takeover=1; shift;;
    --force-takeover) force=1; shift;;
    --all) show_all=1; shift;;
    *) die "unknown arg: $1" 64;;
  esac
done

# Derive owner from session id when not passed.
if [[ -z "$owner" && "$cmd" != "status" ]]; then
  if [[ -n "${CLAUDE_CODE_SESSION_ID:-}" ]]; then
    owner="claude-${CLAUDE_CODE_SESSION_ID:0:8}"
  else
    die "no --owner and CLAUDE_CODE_SESSION_ID unset; refuse to fabricate owner id" 64
  fi
fi

lock_dir() {
  case "$kind" in
    wp) [[ -n "$key" ]] || die "wp lock needs --key" 64; echo "$locks_root/wp/$key";;
    merge) echo "$locks_root/merge";;
    *) die "bad --kind: $kind (wp|merge)" 64;;
  esac
}

now() { date +%s; }

read_field() {  # read_field <owner.json> <field>
  python3 - "$1" "$2" <<'PY'
import json,sys
try:
    d=json.load(open(sys.argv[1]))
    v=d.get(sys.argv[2],"")
    print(v if v is not None else "")
except Exception:
    print("")
PY
}

write_owner() {  # write_owner <dir> [taken_over_from]
  local d="$1" prev="${2:-}" session_pid_value=""
  if [[ -n "${AGENTIC_SESSION_PID:-}" ]]; then
    session_pid_value="$AGENTIC_SESSION_PID"
  elif [[ -n "${PPID:-}" ]]; then
    session_pid_value="$PPID"
  fi
  python3 - "$d/owner.json" "$owner" "$note" "$(now)" "$$" "${CLAUDE_CODE_SESSION_ID:-}" "$prev" "$session_pid_value" <<'PY'
import json,sys
path,owner,note,ts,pid,sess,prev,session_pid=sys.argv[1:9]
obj={"owner":owner,"session_hint":sess,"acquired_at":int(ts),
     "heartbeat_at":int(ts),"pid":int(pid),"note":note}
if prev:
    obj["taken_over_from"]=prev
if session_pid:
    obj["session_pid"]=int(session_pid)
json.dump(obj,open(path,"w"),ensure_ascii=False,indent=2)
PY
}

touch_heartbeat() {  # touch_heartbeat <dir>
  python3 - "$1/owner.json" "$(now)" <<'PY'
import json,sys
path,ts=sys.argv[1],int(sys.argv[2])
d=json.load(open(path)); d["heartbeat_at"]=ts
json.dump(d,open(path,"w"),ensure_ascii=False,indent=2)
PY
}

case "$cmd" in
  acquire)
    L=$(lock_dir)
    mkdir -p "$(dirname "$L")"
    if mkdir "$L" 2>/dev/null; then
      write_owner "$L"
      echo "LOCK_ACQUIRED owner=$owner dir=$L"; exit 0
    fi
    cur=$(read_field "$L/owner.json" owner)
    if [[ "$cur" == "$owner" ]]; then
      touch_heartbeat "$L"
      echo "LOCK_REACQUIRED owner=$owner"; exit 0
    fi
    # Malformed lock: dir exists but owner.json is missing/empty/unparseable
    # (external mkdir, or a crash between mkdir and write_owner). Not a live
    # owner, so don't misreport it as LOCK_STALE; claimable via a takeover flag.
    if [[ -z "$cur" ]]; then
      if [[ "$force" -eq 1 || "$takeover" -eq 1 ]]; then
        write_owner "$L" "malformed"
        echo "LOCK_TAKEOVER owner=$owner from=malformed (claimed malformed lock)"; exit 0
      fi
      echo "LOCK_MALFORMED dir=$L (no valid owner.json; pass --takeover to claim)"; exit 1
    fi
    if [[ "$force" -eq 1 ]]; then
      write_owner "$L" "$cur"
      echo "LOCK_FORCE_TAKEOVER owner=$owner from=$cur"; exit 0
    fi
    hb=$(read_field "$L/owner.json" heartbeat_at); hb=${hb:-0}
    age=$(( $(now) - hb )); ttl_s=$(( TTL_MIN * 60 ))
    if [[ "$age" -le "$ttl_s" ]]; then
      echo "LOCK_HELD_BY_OTHER owner=$cur remaining_s=$(( ttl_s - age ))"; exit 1
    fi
    if [[ "$takeover" -eq 1 ]]; then
      session_pid=$(read_field "$L/owner.json" session_pid)
      if [[ -n "$session_pid" ]]; then
        if kill -0 "$session_pid" 2>/dev/null; then
          echo "LOCK_ALIVE_REFUSED owner=$cur session_pid=$session_pid (stale by TTL but session process alive; use --force-takeover to override)"
          exit 1
        fi
      fi
      write_owner "$L" "$cur"
      if [[ -n "$session_pid" ]]; then
        echo "LOCK_TAKEOVER owner=$owner from=$cur stale_age_s=$age"
      else
        echo "LOCK_TAKEOVER owner=$owner from=$cur stale_age_s=$age liveness=unverified"
      fi
      exit 0
    fi
    echo "LOCK_STALE owner=$cur stale_age_s=$age (pass --takeover to claim)"; exit 1
    ;;
  heartbeat)
    L=$(lock_dir)
    [[ -d "$L" ]] || { echo "HEARTBEAT_LOST no_lock dir=$L"; exit 1; }
    cur=$(read_field "$L/owner.json" owner)
    if [[ "$cur" != "$owner" ]]; then
      echo "HEARTBEAT_LOST owner_now=$cur me=$owner"; exit 1
    fi
    touch_heartbeat "$L"; echo "HEARTBEAT_OK owner=$owner"; exit 0
    ;;
  release)
    L=$(lock_dir)
    [[ -d "$L" ]] || { echo "LOCK_RELEASED (already absent)"; exit 0; }
    cur=$(read_field "$L/owner.json" owner)
    if [[ "$cur" != "$owner" ]]; then
      echo "RELEASE_DENIED owner=$cur me=$owner"; exit 1
    fi
    rm -rf "$L"; echo "LOCK_RELEASED owner=$owner"; exit 0
    ;;
  status)
    if [[ "$show_all" -eq 1 || -z "$kind" ]]; then
      echo "LOCK_STATUS root=$locks_root"
      find "$locks_root" -name owner.json 2>/dev/null | while read -r f; do
        o=$(read_field "$f" owner); hb=$(read_field "$f" heartbeat_at); hb=${hb:-0}
        age=$(( $(now) - hb )); fresh=$([[ $age -le $(( TTL_MIN*60 )) ]] && echo fresh || echo STALE)
        echo "  $(dirname "$f") owner=$o age_s=$age $fresh"
      done
      exit 0
    fi
    L=$(lock_dir)
    if [[ -d "$L" ]]; then
      o=$(read_field "$L/owner.json" owner); hb=$(read_field "$L/owner.json" heartbeat_at); hb=${hb:-0}
      age=$(( $(now) - hb ))
      echo "LOCK_PRESENT dir=$L owner=$o age_s=$age"
    else
      echo "LOCK_ABSENT dir=$L"
    fi
    exit 0
    ;;
  *) die "usage: lock.sh <acquire|heartbeat|release|status> [--kind wp|merge] [--key ..] [--owner ..] [--note ..] [--takeover] [--force-takeover] [--all]" 64;;
esac

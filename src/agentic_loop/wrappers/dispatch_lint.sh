#!/usr/bin/env bash
# Read-only pre-dispatch lint: checks WP brief presence/sections and §4.1 risk
# boundaries. Pure read-only; never mutates files.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <work-package-status.json>" >&2
  exit 64
fi

status_arg=$1

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
main_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root main_repo) || { echo "DISPATCH_LINT_FAIL: resolver failed to resolve main_repo" >&2; exit 2; }
iterations_dir=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root iterations_dir) || { echo "DISPATCH_LINT_FAIL: resolver failed to resolve iterations_dir" >&2; exit 2; }

case "$status_arg" in
  /*) status_file="$status_arg" ;;
  *) status_file="${main_root:+$main_root/}$status_arg" ;;
esac

fail() {
  echo "DISPATCH_LINT_FAIL: $1" >&2
  exit 2
}

# 1. Run validate_wp_status first (read-only, reused).
if ! lint_reason=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" 2>&1 >/dev/null); then
  [[ -n "$lint_reason" ]] || lint_reason="status validation failed"
  fail "$lint_reason"
fi

# Extract fields needed for the lint checks.
extracted=$(python3 - "$status_file" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
allowed = data.get("scope", {}).get("allowed_paths", [])
risk = data.get("risk", {})
print(data.get("iteration_id", ""))
print(data.get("work_package_id", ""))
print(json.dumps(allowed, ensure_ascii=False))
print(json.dumps(risk, ensure_ascii=False))
PY
)
iteration_id=$(printf '%s\n' "$extracted" | sed -n '1p')
work_package_id=$(printf '%s\n' "$extracted" | sed -n '2p')
allowed_json=$(printf '%s\n' "$extracted" | sed -n '3p')
risk_json=$(printf '%s\n' "$extracted" | sed -n '4p')

brief_file="$iterations_dir/$iteration_id/${work_package_id}-brief.md"

# 2. Brief must exist.
if [[ ! -f "$brief_file" ]]; then
  fail "brief not found at $brief_file"
fi

# 3. Required brief sections must be present and non-empty.
section_issue=$(python3 - "$brief_file" <<'PY' || true
import re, sys
path = sys.argv[1]
required = [
    "Acceptance tests",
    "Allowed and forbidden paths",
    "Completion definition",
]
try:
    text = open(path, encoding="utf-8").read()
except FileNotFoundError:
    print(f"brief not found at {path}")
    sys.exit(0)

for heading in required:
    pattern = r"^##\s+" + re.escape(heading) + r"\s*$"
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        print(f"brief missing section '{heading}'")
        sys.exit(0)
    rest = text[m.end():]
    nm = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[:nm.start()] if nm else rest
    non_empty = False
    for line in section.splitlines():
        s = line.strip()
        if s and not s.startswith("<!--"):
            non_empty = True
            break
    if not non_empty:
        print(f"brief missing section '{heading}'")
        sys.exit(0)

sys.exit(1)  # all good -> no output
PY
)
if [[ -n "$section_issue" ]]; then
  fail "$section_issue"
fi

# 4. §4.1 risk boundary: any authorized risk flag blocks automatic dispatch.
risk_issue=$(python3 - "$risk_json" <<'PY'
import json, sys
risk = json.loads(sys.argv[1])
keys = [
    "production_writes_authorized",
    "network_authorized",
    "real_notifications_authorized",
    "irreversible_actions_authorized",
]
for k in keys:
    if risk.get(k) is True:
        print(f"risk.{k} authorized → 需人工审批,不可自动派发")
        break
PY
)
if [[ -n "$risk_issue" ]]; then
  fail "$risk_issue"
fi

# 5. scope.allowed_paths must be non-empty.
allowed_empty=$(python3 - "$allowed_json" <<'PY'
import json, sys
allowed = json.loads(sys.argv[1])
print("0" if allowed else "1")
PY
)
if [[ "$allowed_empty" == "1" ]]; then
  fail "scope.allowed_paths is empty"
fi

echo "DISPATCH_LINT_PASS"
exit 0

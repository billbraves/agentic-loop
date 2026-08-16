#!/usr/bin/env bash
# Independent Codex merge-gate for a work package (AGENTS.md double-sign rule).
#
# This script is now a thin shell around ``agentic_loop.gate`` (WP-18: the
# engine moved into the agentic_loop package). All precondition, diff, effort,
# and verdict logic lives in the Python engine; this file only forwards
# arguments and preserves the historical CLI contract.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <work-package-status.json>" >&2
  exit 64
fi

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
exec "${AGENTIC_PYTHON:-python3}" -m agentic_loop.gate "$@"

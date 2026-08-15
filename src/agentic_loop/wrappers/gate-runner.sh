#!/usr/bin/env bash
set -euo pipefail

# Thin shell entry for the unified [[gate]] runner (WP-02).
#
# Computes the changed-path set exactly like quality-gate.sh (base...HEAD +
# worktree + cached + untracked), then delegates gate scheduling/execution to
# the runner engine. The runner reads the unified [[gate]] array from the main
# repo config (INV-4) and applies the §3.4 frozen ordering + generic result
# model. It prints the normalized gates[] JSON to stdout and exits non-zero when
# a blocking gate fails.
#
# usage: gate-runner.sh <work-package-status.json> [pre_review|merge]

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <work-package-status.json> [pre_review|merge]" >&2
  exit 64
fi

status_file=$1
stage=${2:-pre_review}
if [[ "$stage" != "pre_review" && "$stage" != "merge" ]]; then
  echo "GATE_RUNNER_FAIL: stage must be pre_review or merge" >&2
  exit 64
fi

# git-optional preamble (mirrors quality-gate.sh): prepend the live package
# source so dogfood edits take effect without reinstall; outside any git repo
# rely on the already-installed agentic_loop module.
main_root=""
if _gcd="$(git rev-parse --git-common-dir 2>/dev/null)"; then
  main_root="$(dirname "$(cd "$_gcd" && pwd)")"
  export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$main_root/packages/agentic-loop/src"
fi

python3 -m agentic_loop.validate_wp_status "$status_file"
base_branch=$(python3 -m agentic_loop.validate_wp_status "$status_file" --field git.base_branch)

base_ref=$base_branch
if ! git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
  echo "GATE_RUNNER_FAIL: base ref not found: $base_ref" >&2
  exit 2
fi

changed_file=$(mktemp)
trap 'rm -f "$changed_file"' EXIT
{
  git diff --name-only --diff-filter=ACMR "$base_ref"...HEAD
  git diff --name-only --diff-filter=ACMR
  git diff --name-only --diff-filter=ACMR --cached
  git ls-files --others --exclude-standard
} | awk 'NF' | sort -u > "$changed_file"

python3 -m agentic_loop.runner.gate_runner \
  --stage "$stage" --paths "$changed_file" --status "$status_file"

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <work-package-status.json> [--full]" >&2
  exit 64
fi

status_file=$1
mode=${2:-changed}
if [[ "$mode" != "changed" && "$mode" != "--full" ]]; then
  echo "QUALITY_GATE_FAIL: second argument must be --full" >&2
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
repo_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root current_worktree) || { echo "QUALITY_GATE_FAIL: resolver failed to resolve current_worktree" >&2; exit 2; }
"${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file"

base_branch=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field git.base_branch)
allowed_json=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field scope.allowed_paths)
forbidden_json=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.validate_wp_status "$status_file" --field scope.forbidden_paths)

base_ref=$base_branch
if ! git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
  echo "QUALITY_GATE_FAIL: base ref not found: $base_ref" >&2
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

python3 - "$changed_file" "$allowed_json" "$forbidden_json" <<'PY'
import json
import pathlib
import sys

changed = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
allowed = json.loads(sys.argv[2])
forbidden = json.loads(sys.argv[3])

def matches(path: str, prefix: str) -> bool:
    normalized = prefix.removeprefix("./")
    return path == normalized.rstrip("/") or path.startswith(normalized.rstrip("/") + "/")

errors = []
for path in changed:
    if any(matches(path, prefix) for prefix in forbidden):
        errors.append(f"forbidden changed path: {path}")
    elif allowed and not any(matches(path, prefix) for prefix in allowed):
        errors.append(f"changed path outside allowed scope: {path}")
if errors:
    for error in errors:
        print(f"QUALITY_GATE_FAIL: {error}", file=sys.stderr)
    raise SystemExit(2)
PY

git diff --check "$base_ref"...HEAD
git diff --check
git diff --cached --check

# Path->test rules are project-specific, so they live in the project's
# .agentic/config.toml unified [[gate]] array (kind="command", stage="pre_review"),
# NOT hard-coded here. This keeps the wrapper generic enough to bundle into the
# wheel.
#
# Fail-closed: a quality gate that silently reports PASS because its rules are
# undefined is not acceptable. `resolve_paths --config-section gate` returns the
# command gate (or {"rule": []} when none exists), so it cannot by itself signal
# "the project defined no rules" — an absent gate falls back to an empty rule
# list. We therefore inspect the raw config file directly: when a project ships
# an .agentic/config.toml that OMITS a usable command-gate rule list, refuse with
# a non-zero exit rather than passing on undefined rules. A command gate that
# EXISTS with a non-empty rule list drives the plan normally — an empty plan
# produced because the current changed set matches no rule is a legitimate PASS.
# A repo with no .agentic/config.toml at all keeps the built-in default behavior
# (bare bootstrap; no project config to betray).
# Resolve the config root the SAME way the plan read below does: the engine's
# --config-section reads .agentic/config.toml from main_repo() (INV-4: config is
# a main-repo/iteration concern, resolved in one place). Ask the engine for that
# same root here so the fail-closed guard and the actual plan can never diverge
# — do NOT open-code ${main_root:-$repo_root}, whose fallback could silently read
# the worktree while the plan reads main_repo.
qg_config_root=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --root main_repo) \
  || { echo "QUALITY_GATE_FAIL: resolver failed to resolve main_repo for config" >&2; exit 2; }
qg_section_status=$(python3 - "$qg_config_root" <<'PY'
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
cfg = repo / ".agentic" / "config.toml"
if not cfg.is_file():
    print("NO_CONFIG_FILE")
    raise SystemExit(0)
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]
with open(cfg, "rb") as fh:
    data = tomllib.load(fh)
gates = data.get("gate")
rules = None
if isinstance(gates, list):
    for gate in gates:
        if (
            isinstance(gate, dict)
            and gate.get("kind") == "command"
            and gate.get("stage") == "pre_review"
        ):
            rules = gate.get("rule")
            break
print("OK" if isinstance(rules, list) and len(rules) > 0 else "MISSING_SECTION")
PY
) || { echo "QUALITY_GATE_FAIL: could not inspect [[gate]] config" >&2; exit 2; }
if [[ "$qg_section_status" == "MISSING_SECTION" ]]; then
  echo "QUALITY_GATE_FAIL: [[gate]] (kind=command, stage=pre_review) is absent or defines no rules; refusing to pass with undefined quality rules (fail-closed)" >&2
  exit 2
fi

qg_config=$("${AGENTIC_PYTHON:-python3}" -m agentic_loop.resolve_paths --config-section gate) \
  || { echo "QUALITY_GATE_FAIL: could not read [[gate]] config" >&2; exit 2; }

# Expand the changed set into the ordered, de-duplicated list of test commands.
# Matching semantics mirror the previous hard-coded bash `case`:
#   * each rule's `match` is a path prefix (a trailing /** or /* is stripped);
#   * `changed` mode: every changed path selects the FIRST rule it matches
#     (declaration order = precedence, so a more specific rule such as the
#     frontend build must be declared before the broader research rule);
#   * `--full` mode: every rule is selected;
#   * selected rules contribute their `run` commands, emitted in rule-declaration
#     order with global first-occurrence de-duplication (so a shared command such
#     as the baseline suite runs once even when several rules request it).
plan_file=$(mktemp)
trap 'rm -f "$changed_file" "$plan_file"' EXIT
python3 - "$changed_file" "$qg_config" "$mode" >"$plan_file" <<'PY'
import json
import sys

changed = [
    p for p in open(sys.argv[1], encoding="utf-8").read().splitlines() if p.strip()
]
config = json.loads(sys.argv[2])
mode = sys.argv[3]

rules = config.get("rule") or []


def _prefix(match: str) -> str:
    m = match.strip()
    for suffix in ("/**", "/*"):
        if m.endswith(suffix):
            return m[: -len(suffix)]
    return m


def _matches(path: str, match: str) -> bool:
    prefix = _prefix(match).rstrip("/")
    if not prefix:
        return True
    return path == prefix or path.startswith(prefix + "/")


selected = [False] * len(rules)
if mode == "--full":
    selected = [True] * len(rules)
else:
    for path in changed:
        for idx, rule in enumerate(rules):
            if _matches(path, str(rule.get("match", ""))):
                selected[idx] = True
                break  # first matching rule wins (mirrors the bash `case`)

emitted = []
seen = set()
for idx, rule in enumerate(rules):
    if not selected[idx]:
        continue
    for cmd in rule.get("run", []) or []:
        if cmd not in seen:
            seen.add(cmd)
            emitted.append(cmd)

for cmd in emitted:
    print(cmd)
PY

# Announce the whole plan up front (before any command runs) so the selected
# test-target expansion is fully observable — even if a later command aborts the
# run — and so equivalence to the previous hard-coded target set can be asserted
# directly from stdout.
while IFS= read -r cmd; do
  [[ -z "$cmd" ]] && continue
  echo "QUALITY_GATE_PLAN: $cmd"
done < "$plan_file"

# Execute each planned command.
#
# Exit-code contract (preserves the previous run_pytest_dir semantics):
#   * exit 0            -> pass
#   * exit 5 (no tests) -> skip (not fatal), ONLY for pytest commands
#   * exit 4 (path/target not found — pytest's "usage error" for a missing
#                          directory or file) -> skip (not fatal), ONLY for
#                          pytest commands; mirrors the old `[[ ! -e "$target" ]]`
#                          pre-check that skipped absent targets before pytest
#                          ever ran.
#   * any other non-zero -> fatal (a real test/build failure is never swallowed)
#
# The rc 4/5 skip is scoped to pytest commands only. The old script applied it
# solely inside run_pytest_dir; a non-pytest command such as `npm ... run build`
# has no such usage-error convention, so ANY non-zero rc from it must stay fatal.
while IFS= read -r cmd; do
  [[ -z "$cmd" ]] && continue
  rc=0
  bash -c "$cmd" || rc=$?
  if [[ $rc -eq 0 ]]; then
    continue
  fi
  if [[ "$cmd" == *pytest* ]]; then
    if [[ $rc -eq 5 ]]; then
      echo "QUALITY_GATE_SKIP: no tests collected: $cmd"
      continue
    fi
    if [[ $rc -eq 4 ]]; then
      echo "QUALITY_GATE_SKIP: no test target: $cmd"
      continue
    fi
  fi
  echo "QUALITY_GATE_FAIL: command failed (exit $rc): $cmd" >&2
  exit "$rc"
done < "$plan_file"

echo "QUALITY_GATE_RESULT=PASS"

"""Qoder security merge-gate engine (WP-03 REWORK, CLI adapter layer).

This is the third, independent signature on the merge gate: it scans the WP's
scope-filtered base→tip changed paths with qoder's dedicated ``security scan``
subcommand and writes a ``qoder_security`` status block with one of ``PASS`` /
``FINDINGS`` / ``ERROR``.

Design invariants (preserved from the ACCEPT-ed first pass):

- **fail-closed**: high/medium findings and every ERROR decision block the merge;
  only an explicit ``override.approved == true`` (with the four consult-override
  fields) can relax that, and the original decision/findings/error are always
  preserved honestly — ERROR is never rewritten into PASS.
- **network boundary**: qoder is an external service, so the gate refuses to send
  the changed paths unless ``risk.network_authorized`` is ``true``; otherwise it
  records ``ERROR`` with ``error.kind == network_not_authorized``.
- **shell is thin**: ``scripts/agentic/qoder_security_gate.sh`` only forwards to
  ``python3 -m agentic_loop.gate.qoder_security``; all logic lives here.

REWORK scope (this module's CLI adapter only): the frozen invocation contract was
re-frozen to the real ``qodercli`` scanner entry point —

    qodercli --cwd <worktree_root> security scan \
      --report sarif=<abs_tmp_report.sarif> \
      --fail-on none \
      --wait-timeout <seconds> \
      [--config <qodersec_config>] \
      <relative_changed_path>...

Output is read from the SARIF 2.1.0 report file (never stdout). The engine state
machine, ``gate.py`` → ``gate/`` conversion, and all fail-closed semantics are
unchanged. L3 is recorded as *requested*, never claimed as *enforced*.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from agentic_loop.gate import GateError
from agentic_loop.gate import _diff_path_from_header
from agentic_loop.gate import compute_wp_diff
from agentic_loop.gate import gate_log
from agentic_loop.gate import gate_warn
from agentic_loop.gate import git_output
from agentic_loop.gate import load_status_json
from agentic_loop.gate import read_field
from agentic_loop.gate import run_validator
from agentic_loop.resolve_paths import get_gates
from agentic_loop.resolve_paths import iterations_dir
from agentic_loop.resolve_paths import main_repo

# ``qoder_security.py`` lives at ``agentic_loop/gate/qoder_security.py``; the
# package root (``agentic_loop/``) is two parents up, same as gate/__init__.py.
_PACKAGE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_LEVEL = "L3"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_WAIT_TIMEOUT_SECONDS = 300
DEFAULT_FAIL_ON = "none"
VALID_FAIL_ON = {"none", "medium", "high"}
SARIF_VERSION = "2.1.0"

VALID_SEVERITIES = {"high", "medium", "low"}
DECISIONS = {"PASS", "FINDINGS", "ERROR"}
ERROR_KINDS = {
    "auth_expired",
    "credits_exhausted",
    "network_not_authorized",
    "parse_failed",
    "preflight_failed",
    "timeout",
}

# Categorical severity → normalized {high, medium, low}. ``critical`` folds into
# ``high`` because the status schema only admits three levels. Unknown values are
# NOT mapped (fail-closed, never guessed).
SEVERITY_NORMALIZATION: dict[str, str] = {
    "critical": "high",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

# SARIF ``level`` → normalized {high, medium, low}. Unknown values fail closed.
SARIF_LEVEL_NORMALIZATION: dict[str, str] = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "low",
}

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}

_CREDITS_SIGNALS = ("credit", "quota", "exhaust", "insufficient", "billing")
_AUTH_SIGNALS = ("auth", "token", "401", "unauthorized", "credential", "expired")
_TIMEOUT_SIGNALS = ("timeout", "timed out")
_NETWORK_SIGNALS = ("network", "connection", "unreachable", "dns", "refused")


@dataclass(frozen=True)
class Finding:
    """A normalized qoder finding as written to the status block."""

    category: str
    severity: str
    file: str
    dataflow: str
    summary: str
    scope: str = "in_scope"
    suppressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "dataflow": self.dataflow,
            "summary": self.summary,
            "scope": self.scope,
            "suppressed": self.suppressed,
        }


@dataclass(frozen=True)
class ParsedFinding:
    """An intermediate SARIF result before scope attribution."""

    severity: str
    rule_id: str
    message: str
    paths: tuple[str, ...]
    dataflow: str
    suppressed: bool


@dataclass(frozen=True)
class ScanDecision:
    """Result of combining SARIF findings with the scanner exit code."""

    decision: str
    error_kind: str | None = None
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class QoderParseError(Exception):
    """Raised when the SARIF report is unusable (fail-closed)."""


class QoderPreflightError(Exception):
    """Raised for preflight failures mapping to ``error.kind=preflight_failed``."""


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested).
# ---------------------------------------------------------------------------
def normalize_severity(raw: Any) -> str | None:
    """Normalize a categorical severity string to ``{high, medium, low}``.

    Returns ``None`` for any value that cannot be trusted to map into the frozen
    three-level domain (unknown severities must fail closed, never downgrade).
    """
    if not isinstance(raw, str):
        return None
    return SEVERITY_NORMALIZATION.get(raw.strip().lower())


def _security_severity_to_level(value: Any) -> str | None:
    """Map a numeric SARIF ``security-severity`` to ``{high, medium, low}``.

    Returns ``None`` for ``0.0`` (meaning "no security severity" — fall through
    to the level-based signal). Raises ``QoderParseError`` for non-numeric or
    out-of-range values (fail-closed, never guessed).
    """
    if isinstance(value, bool):
        raise QoderParseError(f"invalid_severity: security-severity is a boolean: {value!r}")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise QoderParseError(f"invalid_severity: security-severity not numeric: {value!r}") from None
    if math.isnan(num) or math.isinf(num) or num < 0 or num > 10:
        raise QoderParseError(f"invalid_severity: security-severity out of range: {value!r}")
    if num == 0.0:
        return None
    if num >= 7.0:  # >=9.0 is raw=critical, folded into high
        return "high"
    if num >= 4.0:
        return "medium"
    return "low"


def _sarif_level_to_normalized(level: Any) -> str:
    if not isinstance(level, str):
        raise QoderParseError(f"unknown_sarif_level: {level!r}")
    normalized = SARIF_LEVEL_NORMALIZATION.get(level.strip().lower())
    if normalized is None:
        raise QoderParseError(f"unknown_sarif_level: {level!r}")
    return normalized


def _max_severity(*levels: str) -> str:
    return max(levels, key=lambda s: _SEVERITY_RANK[s])


def normalize_sarif_result_severity(result: dict[str, Any], rule: dict[str, Any] | None) -> str:
    """Return the highest recognizable severity signal for one SARIF result.

    Collects the ``security-severity`` and categorical ``severity`` signals from
    both the result properties and the rule metadata, merges every recognizable
    candidate, and returns the maximum. Also considers the SARIF ``level``
    (result level, else rule default, else ``warning``).
    ``security-severity == 0.0`` contributes no security-severity signal and
    falls back to the remaining signals. Unknown/invalid values fail closed.
    """
    candidates: list[str] = []

    result_props = result.get("properties")
    rule_props = rule.get("properties") if isinstance(rule, dict) else None

    # 1. security-severity: collect BOTH result.properties and rule metadata.
    #    Every recognizable signal contributes a candidate (never result-first
    #    dropping the rule signal); 0.0 maps to None and contributes nothing.
    if isinstance(result_props, dict) and "security-severity" in result_props:
        sec_sev = result_props.get("security-severity")
        if sec_sev is not None:
            mapped = _security_severity_to_level(sec_sev)
            if mapped is not None:
                candidates.append(mapped)
    if isinstance(rule_props, dict) and "security-severity" in rule_props:
        sec_sev = rule_props.get("security-severity")
        if sec_sev is not None:
            mapped = _security_severity_to_level(sec_sev)
            if mapped is not None:
                candidates.append(mapped)

    # 2. categorical severity property (optional, non-standard SARIF extension).
    #    Collect BOTH result.properties and rule metadata; an unknown value in
    #    either source fails closed (never masked by the other source).
    if isinstance(result_props, dict) and "severity" in result_props:
        cat_sev = result_props.get("severity")
        if cat_sev is not None:
            mapped = normalize_severity(cat_sev)
            if mapped is None:
                raise QoderParseError(f"unknown severity: {cat_sev!r}")
            candidates.append(mapped)
    if isinstance(rule_props, dict) and "severity" in rule_props:
        cat_sev = rule_props.get("severity")
        if cat_sev is not None:
            mapped = normalize_severity(cat_sev)
            if mapped is None:
                raise QoderParseError(f"unknown severity: {cat_sev!r}")
            candidates.append(mapped)

    # 3. SARIF level: result.level, else rule defaultConfiguration.level, else
    #    ``warning`` (fail-closed default).
    level: Any = result.get("level")
    if level is None and isinstance(rule, dict):
        default_cfg = rule.get("defaultConfiguration")
        if isinstance(default_cfg, dict):
            level = default_cfg.get("level")
    if level is None:
        level = "warning"
    candidates.append(_sarif_level_to_normalized(level))

    return _max_severity(*candidates)


def _has_blocking(findings: list[Finding]) -> bool:
    """True when any high/medium finding exists, regardless of scope.

    Scope is informational metadata only: out-of-scope findings still block the
    merge. This is the fail-closed contract for cross-file dataflow gates.
    """
    return any(f.severity in ("high", "medium") for f in findings)


def compute_decision(findings: list[Finding]) -> str:
    """State machine: FINDINGS iff any high/medium finding, else PASS.

    Low-only findings (or no findings) → PASS; low findings are still recorded in
    status but do not block. Any high/medium finding blocks, regardless of scope.
    """
    if _has_blocking(findings):
        return "FINDINGS"
    return "PASS"


def is_override_approved(override: Any) -> bool:
    """True when ``override`` is a complete, human-approved override.

    Mirrors the validator's consult-override shape: ``approved`` must be the
    boolean ``True`` and ``approver`` / ``justification`` / ``reviewed_at`` must
    all be non-empty strings.
    """
    if not isinstance(override, dict):
        return False
    if override.get("approved") is not True:
        return False
    return all(
        isinstance(override.get(key), str) and override[key].strip()
        for key in ("approver", "justification", "reviewed_at")
    )


def blocking(decision: str, override: Any = None) -> bool:
    """True when the qoder_security block blocks the merge.

    PASS never blocks. FINDINGS and ERROR block unless a complete, approved
    override is present (which relaxes but never rewrites the decision).
    """
    if decision == "PASS":
        return False
    return not is_override_approved(override)


# ---------------------------------------------------------------------------
# Scan-path helpers (changed paths from the scope-filtered diff).
# ---------------------------------------------------------------------------
def _block_is_deletion(block: str) -> bool:
    """True when a diff block's post-image is ``/dev/null`` (pure deletion)."""
    for line in block.splitlines():
        if line.startswith("@@"):
            break
        if line.startswith("+++ "):
            return line == "+++ /dev/null"
    return False


def extract_scan_paths(diff_text: str) -> list[str]:
    """Return relative post-image paths with a real file target from a diff.

    Deletions (``+++ /dev/null``) are skipped because there is nothing to scan.
    Order is stable and de-duplicated. Paths are worktree-root relative.
    """
    if not diff_text:
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for block in re.split(r"(?m)^(?=diff --git )", diff_text):
        if not block:
            continue
        post = _diff_path_from_header(block)
        if not post:
            continue
        if _block_is_deletion(block):
            continue
        if post not in seen:
            seen.add(post)
            paths.append(post)
    return paths


def validate_scan_paths(paths: list[str]) -> None:
    """Fail-closed path validation: relative, no ``..``, no leading ``-``."""
    for path in paths:
        if not isinstance(path, str) or not path:
            raise QoderPreflightError("scan path must be a non-empty string")
        if path.startswith("/"):
            raise QoderPreflightError(f"scan path must be relative (got absolute): {path!r}")
        if path.startswith("-"):
            raise QoderPreflightError(f"scan path must not start with '-': {path!r}")
        if ".." in Path(path).parts:
            raise QoderPreflightError(f"scan path must not contain '..': {path!r}")


def _argv_total_bytes(cmd: list[str]) -> int:
    return sum(len(arg.encode("utf-8")) + 1 for arg in cmd)


def _argv_limit() -> int:
    env = os.environ.get("QODER_SECURITY_ARG_MAX_BYTES")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    try:
        return int(os.sysconf("SC_ARG_MAX")) - 4096
    except (ValueError, OSError):
        return 256 * 1024


# ---------------------------------------------------------------------------
# Preflight / CLI resolution.
# ---------------------------------------------------------------------------
def resolve_qoder_bin(env: dict[str, str] | None = None) -> Path | None:
    """Resolve the qoder CLI binary, or ``None`` when it cannot be found.

    Order: explicit ``QODER_SECURITY_BIN`` override (tests/injection), ``PATH``
    lookup, then the documented install locations. The on-disk install may be
    versioned (``qodercli-1.x.y``), so the known dir is globbed as a fallback.
    """
    env = dict(os.environ if env is None else env)
    explicit = env.get("QODER_SECURITY_BIN")
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None

    found = shutil.which("qodercli", path=env.get("PATH"))
    if found:
        return Path(found)

    home = Path(env.get("HOME") or os.path.expanduser("~"))
    candidates = [
        home / ".local" / "bin" / "qodercli",
        home / ".qoder" / "bin" / "qodercli" / "qodercli",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    versioned_dir = home / ".qoder" / "bin" / "qodercli"
    if versioned_dir.is_dir():
        for candidate in sorted(versioned_dir.glob("qodercli-*")):
            if candidate.is_file():
                return candidate
    return None


def probe_qoder_version(qoder_bin: Path, timeout: int = 60) -> tuple[bool, str]:
    """Run the local ``qodercli --version`` capability probe.

    This proves binary/version installation only; it does NOT prove auth or
    service readiness. Auth is verified by the first real scan (fail-closed).
    """
    try:
        proc = subprocess.run(
            [str(qoder_bin), "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "version probe timed out"
    if proc.returncode == 0:
        return True, (proc.stdout.strip() or proc.stderr.strip() or "")
    detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
    return False, detail


def build_scan_command(
    qoder_bin: Path,
    *,
    worktree_root: Path,
    report_file: Path,
    fail_on: str,
    wait_timeout: int,
    changed_paths: list[str],
    config_path: Path | None = None,
) -> list[str]:
    """Build the ``qodercli security scan`` argv per the re-frozen contract.

    Validates paths fail-closed and refuses to silently widen to ``--all`` on an
    argv overflow (raising ``QoderPreflightError`` instead).
    """
    validate_scan_paths(changed_paths)

    cmd = [
        str(qoder_bin),
        "--cwd", str(worktree_root),
        "security", "scan",
        "--report", f"sarif={report_file}",
        "--fail-on", fail_on,
        "--wait-timeout", str(wait_timeout),
    ]
    if config_path is not None:
        cmd += ["--config", str(config_path)]
    cmd += changed_paths

    if _argv_total_bytes(cmd) > _argv_limit():
        raise QoderPreflightError(
            "path_list_too_large: too many scan paths exceed the argv limit; "
            "refusing to silently fall back to --all"
        )
    return cmd


def run_qoder_scan(
    qoder_bin: Path,
    *,
    worktree_root: Path,
    report_file: Path,
    fail_on: str,
    wait_timeout: int,
    changed_paths: list[str],
    config_path: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, str, str]:
    """Run one ``qodercli security scan``; returns ``(exit_code, stdout, stderr)``.

    ``exit_code == -1`` is the sentinel for a process timeout (no exit code).
    The SARIF report is written by the scanner to ``report_file``.
    """
    cmd = build_scan_command(
        qoder_bin,
        worktree_root=worktree_root,
        report_file=report_file,
        fail_on=fail_on,
        wait_timeout=wait_timeout,
        changed_paths=changed_paths,
        config_path=config_path,
    )
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout_seconds}s"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _credits_signal(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in _CREDITS_SIGNALS) or (
        "额度" in text or "余额" in text
    )


def _auth_signal(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in _AUTH_SIGNALS)


def _timeout_signal(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in _TIMEOUT_SIGNALS)


def _network_signal(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in _NETWORK_SIGNALS)


def _fail_on_rejection(text: str) -> bool:
    lowered = text.lower()
    return "fail-on" in lowered or "fail_on" in lowered or "invalid value" in lowered


def classify_scanner_error(stderr: str) -> str | None:
    """Map scanner stderr to an existing error kind, or ``None``.

    Auth → ``auth_expired``; timeout → ``timeout``; credits → ``credits_exhausted``;
    network → ``preflight_failed`` (no dedicated scanner-network kind in the
    frozen enum). Returns ``None`` when nothing is recognizable.
    """
    if _auth_signal(stderr):
        return "auth_expired"
    if _timeout_signal(stderr):
        return "timeout"
    if _credits_signal(stderr):
        return "credits_exhausted"
    if _network_signal(stderr):
        return "preflight_failed"
    return None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def resolve_fail_on() -> str:
    raw = os.environ.get("QODER_SECURITY_FAIL_ON")
    return raw if raw in VALID_FAIL_ON else DEFAULT_FAIL_ON


def resolve_qoder_config() -> Path | None:
    raw = os.environ.get("QODER_SECURITY_CONFIG")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_file() else None


def resolve_qoder_level(repo_root: Path) -> str:
    """Return the configured (requested) qoder_security gate level, default L3."""
    for gate in get_gates(repo_root):
        if gate.get("kind") == "qoder_security":
            level = gate.get("level")
            if isinstance(level, str) and level.strip():
                return level
    return DEFAULT_LEVEL


def network_authorized(data: dict[str, Any]) -> bool:
    """Fail-closed network flag: anything but explicit ``true`` is unauthorized."""
    risk = data.get("risk")
    if not isinstance(risk, dict):
        return False
    return risk.get("network_authorized") is True


def resolve_worktree(data: dict[str, Any], repo_root: Path) -> Path:
    """Resolve the WP worktree directory for ``--cwd`` (defaults to main repo)."""
    git = data.get("git")
    value = git.get("worktree") if isinstance(git, dict) else None
    if not value or value == ".":
        return repo_root
    p = Path(value)
    return p if p.is_absolute() else repo_root / p


# ---------------------------------------------------------------------------
# SARIF report parsing.
# ---------------------------------------------------------------------------
def _check_external_refs(container: dict[str, Any]) -> None:
    """Fail closed on any external property file references (never read them)."""
    refs = container.get("externalPropertyFileReferences")
    if isinstance(refs, dict) and refs:
        raise QoderParseError(
            "external_sarif_properties_unsupported: "
            "externalPropertyFileReferences"
        )


def _index_rules(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules_by_id: dict[str, dict[str, Any]] = {}
    tool = run.get("tool")
    if not isinstance(tool, dict):
        return rules_by_id
    driver = tool.get("driver")
    if not isinstance(driver, dict):
        return rules_by_id
    rules = driver.get("rules")
    if not isinstance(rules, list):
        return rules_by_id
    for rule in rules:
        if isinstance(rule, dict):
            rule_id = rule.get("id")
            if isinstance(rule_id, str):
                rules_by_id[rule_id] = rule
    return rules_by_id


def _resolve_rule(
    result: dict[str, Any], rules_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    rule_id = result.get("ruleId")
    if isinstance(rule_id, str) and rule_id in rules_by_id:
        return rules_by_id[rule_id]
    return None


def _location_uri(loc: Any) -> str | None:
    if not isinstance(loc, dict):
        return None
    phys = loc.get("physicalLocation")
    if not isinstance(phys, dict):
        return None
    art = phys.get("artifactLocation")
    if not isinstance(art, dict):
        return None
    uri = art.get("uri")
    if isinstance(uri, str) and uri:
        return uri
    return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _artifact_uris(result: dict[str, Any]) -> tuple[str, ...]:
    uris: list[str] = []
    seen: set[str] = set()

    def add(uri: str | None) -> None:
        if uri and uri not in seen:
            seen.add(uri)
            uris.append(uri)

    for loc in _as_list(result.get("locations")):
        add(_location_uri(loc))
    for loc in _as_list(result.get("relatedLocations")):
        add(_location_uri(loc))
    for code_flow in _as_list(result.get("codeFlows")):
        if not isinstance(code_flow, dict):
            continue
        for thread_flow in _as_list(code_flow.get("threadFlows")):
            if not isinstance(thread_flow, dict):
                continue
            for step in _as_list(thread_flow.get("locations")):
                inner = step.get("location") if isinstance(step, dict) else step
                add(_location_uri(inner))
    return tuple(uris)


def _parse_sarif_result(
    result: dict[str, Any],
    rules_by_id: dict[str, dict[str, Any]],
    code_flow_count: int,
) -> ParsedFinding:
    rule = _resolve_rule(result, rules_by_id)
    severity = normalize_sarif_result_severity(result, rule)

    rule_id = ""
    raw_rule_id = result.get("ruleId")
    if isinstance(raw_rule_id, str):
        rule_id = raw_rule_id
    elif isinstance(rule, dict) and isinstance(rule.get("id"), str):
        rule_id = rule["id"]

    message = ""
    msg = result.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("text"), str) and msg["text"].strip():
        message = msg["text"].strip()

    paths = _artifact_uris(result)
    dataflow = f"{code_flow_count} codeflow(s)" if code_flow_count else ""
    suppressed = bool(_as_list(result.get("suppressions")))

    return ParsedFinding(
        severity=severity,
        rule_id=rule_id,
        message=message,
        paths=paths,
        dataflow=dataflow,
        suppressed=suppressed,
    )


def parse_sarif_report(text: str) -> list[ParsedFinding]:
    """Parse a SARIF report into normalized findings (fail-closed).

    Only SARIF ``version == "2.1.0"`` is accepted. Report-level, run-level, or
    driver-level ``externalPropertyFileReferences`` (any key) fail closed because
    we do not read external property files (would drop severity).
    """
    if not text.strip():
        raise QoderParseError("empty SARIF report")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QoderParseError(f"invalid JSON: {exc}") from None

    if not isinstance(obj, dict):
        raise QoderParseError("SARIF root must be an object")

    version = obj.get("version")
    if version != SARIF_VERSION:
        raise QoderParseError(f"unsupported_sarif_version: {version!r}")

    _check_external_refs(obj)

    runs = obj.get("runs")
    if not isinstance(runs, list):
        raise QoderParseError("SARIF runs must be a list")

    parsed: list[ParsedFinding] = []
    for run in runs:
        if not isinstance(run, dict):
            raise QoderParseError("SARIF run must be an object")
        _check_external_refs(run)
        tool = run.get("tool")
        if isinstance(tool, dict) and isinstance(tool.get("driver"), dict):
            _check_external_refs(tool["driver"])

        rules_by_id = _index_rules(run)
        results = run.get("results")
        if results is None:
            continue
        if not isinstance(results, list):
            raise QoderParseError("SARIF run.results must be a list")
        for result in results:
            if not isinstance(result, dict):
                raise QoderParseError("SARIF result must be an object")
            code_flow_count = len(_as_list(result.get("codeFlows")))
            parsed.append(_parse_sarif_result(result, rules_by_id, code_flow_count))

    return parsed


def read_sarif_report(report_file: Path) -> list[ParsedFinding]:
    if not report_file.is_file():
        raise QoderParseError(f"SARIF report file missing: {report_file}")
    return parse_sarif_report(report_file.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Scope attribution + decision (report + exit code cross-check).
# ---------------------------------------------------------------------------
def _normalize_uri(uri: str) -> str:
    p = uri.replace("\\", "/")
    if p.startswith("file://"):
        p = p[len("file://"):]
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def _uri_matches_changed(uri: str, changed_paths: set[str]) -> bool:
    fp = _normalize_uri(uri)
    if not fp:
        return False
    for cp in changed_paths:
        if fp == cp or fp.endswith("/" + cp) or cp.endswith("/" + fp):
            return True
    return False


def attribute_scope(parsed: list[ParsedFinding], changed_paths: list[str]) -> list[Finding]:
    """Convert parsed SARIF findings to findings with in/out-of-scope attribution.

    A finding is in-scope when any of its artifact locations (primary,
    related, codeFlows/threadFlows) matches a changed path; otherwise it is
    recorded as out-of-scope. Scope is informational metadata only and never
    suppresses blocking.
    """
    normalized_changed = {_normalize_uri(p) for p in changed_paths}
    findings: list[Finding] = []
    for p in parsed:
        in_scope = any(
            _uri_matches_changed(uri, normalized_changed) for uri in p.paths
        )
        findings.append(
            Finding(
                category=p.rule_id,
                severity=p.severity,
                file=p.paths[0] if p.paths else "",
                dataflow=p.dataflow,
                summary=p.message,
                scope="in_scope" if in_scope else "out_of_scope",
                suppressed=p.suppressed,
            )
        )
    return findings


def compute_scan_decision(
    findings: list[Finding],
    *,
    exit_code: int,
    fail_on: str,
    stderr: str = "",
) -> ScanDecision:
    """Combine SARIF findings with the scanner exit code (the state-decision table).

    Report-missing / parse failures are handled by the caller (they always map to
    ERROR). This function assumes the report parsed successfully.
    """
    in_scope_low_count = sum(
        1 for f in findings if f.severity == "low" and f.scope == "in_scope"
    )
    blocking_found = _has_blocking(findings)

    if exit_code == 0:
        if blocking_found:
            extra: dict[str, Any] = {}
            if fail_on in ("medium", "high"):
                extra["sanity_mismatch"] = True
            if in_scope_low_count:
                extra["low_findings_count"] = in_scope_low_count
            return ScanDecision("FINDINGS", extra=extra)
        extra = {}
        if in_scope_low_count:
            extra["low_findings_count"] = in_scope_low_count
        return ScanDecision("PASS", extra=extra)

    # exit_code != 0
    if blocking_found:
        return ScanDecision(
            "FINDINGS",
            extra={"exit_code": exit_code, "scanner_exit_indicated_findings": True},
        )

    kind = classify_scanner_error(stderr)
    extra = {"exit_code": exit_code}
    if kind is not None:
        message = f"scanner error (exit {exit_code}): {stderr[:500]}"
        return ScanDecision("ERROR", error_kind=kind, error_message=message, extra=extra)

    return ScanDecision(
        "ERROR",
        error_kind="preflight_failed",
        error_message=(
            f"exit_without_blocking_findings: scanner exited {exit_code} with no "
            f"blocking finding"
        ),
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Status write.
# ---------------------------------------------------------------------------
def write_qoder_security_block(
    status_file: Path,
    *,
    decision: str,
    findings: list[Finding],
    level: str,
    error_kind: str | None = None,
    error_message: str | None = None,
    reviewed_at: str | None = None,
    detail: str | None = None,
    requested_level: str | None = None,
    scanner_reported_level: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Write (or refresh) the ``qoder_security`` block in the status JSON.

    ``error`` is present only when ``decision == ERROR``. An existing human
    ``override`` is preserved verbatim so a later engine run never clobbers a
    recorded override; the engine itself never fabricates one. ``level`` carries
    the *requested* level (L3 honesty: never claims enforcement).
    """
    data = load_status_json(status_file)

    existing = data.get("qoder_security")
    existing_override = None
    if isinstance(existing, dict) and isinstance(existing.get("override"), dict):
        existing_override = existing["override"]

    block: dict[str, Any] = {
        "decision": decision,
        "findings": [f.to_dict() for f in findings],
        "level": level,
        "requested_level": requested_level or level,
    }
    if detail is not None:
        block["detail"] = detail
    if scanner_reported_level is not None:
        block["scanner_reported_level"] = scanner_reported_level
    if extra:
        block.update(extra)
    if decision == "ERROR":
        kind = error_kind if error_kind in ERROR_KINDS else "preflight_failed"
        block["error"] = {"kind": kind, "message": error_message or ""}
    if existing_override is not None:
        block["override"] = existing_override

    data["qoder_security"] = block
    ts = data.get("timestamps")
    if isinstance(ts, dict):
        ts["updated_at"] = reviewed_at or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    status_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _record_decision(
    status_file: Path,
    decision: str,
    findings: list[Finding],
    level: str,
    *,
    error_kind: str | None = None,
    error_message: str | None = None,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    write_qoder_security_block(
        status_file,
        decision=decision,
        findings=findings,
        level=level,
        error_kind=error_kind,
        error_message=error_message,
        detail=detail,
        extra=extra,
    )
    print(f"QODER_SECURITY_DECISION={decision}")


# ---------------------------------------------------------------------------
# Engine entry point.
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: gate.qoder_security <work-package-status.json>", file=sys.stderr)
        return 64

    status_arg = argv[0]
    repo_root = main_repo()
    iterations_dir_path = iterations_dir()
    validator = _PACKAGE_DIR / "validate_wp_status.py"

    # Resolve the status path against the main repo root, not cwd (a worktree).
    if status_arg.startswith("/"):
        status_file = Path(status_arg)
    else:
        status_file = repo_root / status_arg

    if not status_file.is_file():
        raise GateError(
            f"status file not found at {status_file} "
            f"(resolved against main repo root {repo_root})"
        )
    if "/.worktrees/" in str(status_file):
        raise GateError(
            f"status file resolves inside a worktree ({status_file}); "
            "pass the main-repo copy (single source of truth)"
        )

    gate_log(f"using status file {status_file} (main repo root: {repo_root})")
    run_validator(validator, status_file)

    schema_version = read_field(validator, status_file, "schema_version")
    if schema_version != "agentic-wp-status/v2":
        raise GateError(
            f"qoder security gate requires schema v2, got {schema_version}"
        )

    data = load_status_json(status_file)

    wp_id = read_field(validator, status_file, "work_package_id")
    iteration_id = read_field(validator, status_file, "iteration_id")
    base_commit = read_field(validator, status_file, "git.base_commit")
    head_commit = read_field(validator, status_file, "git.commit")
    branch = read_field(validator, status_file, "git.branch")
    base_branch = read_field(validator, status_file, "git.base_branch") or "main"

    if not base_commit or not head_commit:
        raise GateError("git.base_commit and git.commit are required for the diff")
    if not branch:
        raise GateError(
            "git.branch is required to resolve the diff endpoint (branch tip)"
        )

    diff_text, _diff_start, tip_commit = compute_wp_diff(
        repo_root,
        validator,
        status_file,
        iterations_dir_path,
        base_commit=base_commit,
        head_commit=head_commit,
        branch=branch,
        base_branch=base_branch,
        iteration_id=iteration_id,
        wp_id=wp_id,
    )

    level = resolve_qoder_level(repo_root)
    worktree = resolve_worktree(data, repo_root)

    # ------------------------------------------------------------------
    # Compute the scope-filtered changed paths (scan targets). No scan target
    # (empty diff or pure deletions) is a PASS — no qoder invocation at all.
    # This is a pure-diff conclusion and must be decided BEFORE the network and
    # worktree-HEAD preflights: when nothing is scanned there is nothing to
    # exfiltrate and no file version to trust-check, so those fail-closed guards
    # only apply once there is at least one real scan path.
    # ------------------------------------------------------------------
    changed_paths = extract_scan_paths(diff_text)
    if not changed_paths:
        detail = "deleted_only_no_scan_target" if diff_text else "no_scan_target"
        gate_log(f"no scan target ({detail}); recording PASS")
        _record_decision(status_file, "PASS", [], level, detail=detail)
        return 0

    # ------------------------------------------------------------------
    # External-service boundary: refuse to exfiltrate paths unless the WP
    # explicitly authorized the network. This is fail-closed, not a crash.
    # No qoder invocation (not even the local --version probe) happens.
    # ------------------------------------------------------------------
    if not network_authorized(data):
        gate_log("risk.network_authorized is false; refusing external qoder scan")
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="network_not_authorized",
            error_message=(
                "risk.network_authorized is false; qoder is an external service "
                "and the changed paths were not sent"
            ),
        )
        return 0

    # ------------------------------------------------------------------
    # Worktree-tip consistency preflight: the scan must read the *current*
    # full file contents at the reviewed tip, so prove the worktree HEAD is
    # exactly the tip commit before any qoder invocation. A stale, missing,
    # or silently-fell-back-to-main worktree fails closed — never scan a
    # version other than the one the diff was computed against.
    # ------------------------------------------------------------------
    try:
        worktree_head = git_output(worktree, "rev-parse", "HEAD")
    except GateError:
        gate_log(
            f"cannot resolve worktree HEAD at {worktree}; "
            f"refusing to scan (expected reviewed tip {tip_commit})"
        )
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="preflight_failed",
            error_message=(
                f"worktree_head_mismatch: cannot resolve worktree HEAD at "
                f"{worktree} (expected reviewed tip {tip_commit}); refusing "
                f"to scan a stale or missing worktree"
            ),
        )
        return 0

    if worktree_head != tip_commit:
        gate_log(
            f"worktree HEAD {worktree_head} != reviewed tip {tip_commit}; "
            f"refusing to scan a stale tree"
        )
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="preflight_failed",
            error_message=(
                f"worktree_head_mismatch: worktree HEAD {worktree_head} != "
                f"reviewed tip commit {tip_commit}; refusing to scan a stale tree"
            ),
        )
        return 0

    # ------------------------------------------------------------------
    # Scanned-path cleanliness preflight (fail-closed): the scan input must be
    # the exact full content at the reviewed tip, not "tip + uncommitted local
    # edits". HEAD==tip only proves committed history; a tracked-modified
    # changed path still reads dirty content while HEAD stays at tip. So prove
    # the *scanned paths only* are clean before any qoder invocation. Scope is
    # deliberately limited to ``changed_paths``: unrelated untracked files are
    # never scanned and must not trip this gate (avoid false positives).
    # ------------------------------------------------------------------
    try:
        dirty_paths = git_output(
            worktree, "status", "--porcelain", "--", *changed_paths
        )
    except GateError as exc:
        gate_log(
            f"cannot check scanned-path cleanliness at {worktree}; "
            f"refusing to scan ({exc})"
        )
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="preflight_failed",
            error_message=str(exc),
        )
        return 0

    if dirty_paths:
        summary = " ".join(dirty_paths.splitlines())
        gate_log(
            f"scanned path(s) differ from reviewed tip {tip_commit}; "
            f"refusing to scan dirty input: {summary}"
        )
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="preflight_failed",
            error_message=(
                f"worktree_not_clean: {summary}; refusing to scan paths that "
                f"differ from reviewed tip {tip_commit}"
            ),
        )
        return 0

    # ------------------------------------------------------------------
    # Local capability probe: binary existence + ``--version``. This proves
    # installation only; it does not prove auth (which is verified by the first
    # real scan, below).
    # ------------------------------------------------------------------
    qoder_bin = resolve_qoder_bin()
    if qoder_bin is None:
        gate_log("qoder CLI binary not found; recording preflight_failed")
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="preflight_failed",
            error_message="qoder CLI binary not found",
        )
        return 0

    version_ok, version_detail = probe_qoder_version(qoder_bin)
    if not version_ok:
        gate_log(f"qoder CLI --version probe failed: {version_detail}")
        _record_decision(
            status_file,
            "ERROR",
            [],
            level,
            error_kind="preflight_failed",
            error_message=f"qoder CLI --version failed: {version_detail}",
        )
        return 0

    fail_on = resolve_fail_on()
    wait_timeout = _env_int("QODER_SECURITY_WAIT_TIMEOUT", DEFAULT_WAIT_TIMEOUT_SECONDS)
    timeout_seconds = _env_int("QODER_SECURITY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    config_path = resolve_qoder_config()

    with tempfile.TemporaryDirectory() as tmp:
        report_file = Path(tmp) / "qoder-report.sarif"

        # ------------------------------------------------------------------
        # Worktree cleanliness: qoder must not mutate source. Snapshot before
        # and after; any change is a fail-closed ERROR.
        # ------------------------------------------------------------------
        try:
            before = git_output(worktree, "status", "--porcelain")
        except GateError as exc:
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind="preflight_failed",
                error_message=str(exc),
            )
            return 0

        def _run_once(fail_on: str) -> tuple[int, str, str]:
            return run_qoder_scan(
                qoder_bin,
                worktree_root=worktree,
                report_file=report_file,
                fail_on=fail_on,
                wait_timeout=wait_timeout,
                changed_paths=changed_paths,
                config_path=config_path,
                timeout_seconds=timeout_seconds,
            )

        try:
            exit_code, stdout, stderr = _run_once(fail_on)
        except QoderPreflightError as exc:
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind="preflight_failed",
                error_message=str(exc),
            )
            return 0

        # Optional one-shot fallback when this binary rejects ``--fail-on none``.
        if fail_on == "none" and exit_code != 0 and _fail_on_rejection(stderr):
            gate_warn("--fail-on none rejected by scanner; retrying with --fail-on medium")
            fail_on = "medium"
            try:
                exit_code, stdout, stderr = _run_once(fail_on)
            except QoderPreflightError as exc:
                _record_decision(
                    status_file,
                    "ERROR",
                    [],
                    level,
                    error_kind="preflight_failed",
                    error_message=str(exc),
                )
                return 0

        try:
            after = git_output(worktree, "status", "--porcelain")
        except GateError as exc:
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind="preflight_failed",
                error_message=str(exc),
            )
            return 0
        if before != after:
            gate_log("qoder scan mutated the worktree; recording scanner_mutated_worktree")
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind="preflight_failed",
                error_message=(
                    "scanner_mutated_worktree: qoder modified tracked or untracked "
                    "files during the scan"
                ),
            )
            return 0

        if exit_code == -1:
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind="timeout",
                error_message=f"qoder scan timed out after {timeout_seconds}s",
            )
            return 0

        # ------------------------------------------------------------------
        # Read + parse the SARIF report (fail-closed; never stdout).
        # ------------------------------------------------------------------
        if not report_file.is_file():
            kind = classify_scanner_error(stderr) or "parse_failed"
            message = (
                f"scan failed (exit {exit_code}): {stderr[:500]}"
                if kind != "parse_failed"
                else f"SARIF report file missing: {report_file}"
            )
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind=kind,
                error_message=message,
            )
            return 0

        try:
            parsed = read_sarif_report(report_file)
        except QoderParseError as exc:
            _record_decision(
                status_file,
                "ERROR",
                [],
                level,
                error_kind="parse_failed",
                error_message=str(exc),
            )
            return 0

        findings = attribute_scope(parsed, changed_paths)
        scan_decision = compute_scan_decision(
            findings, exit_code=exit_code, fail_on=fail_on, stderr=stderr
        )

        _record_decision(
            status_file,
            scan_decision.decision,
            findings,
            level,
            error_kind=scan_decision.error_kind,
            error_message=scan_decision.error_message,
            extra=scan_decision.extra,
        )
        gate_log(
            f"qoder_security block written to {status_file} "
            f"(decision={scan_decision.decision}, findings={len(findings)})"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

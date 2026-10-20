"""WP-03 REWORK: qoder security merge-gate engine — ``security scan`` adapter,
SARIF parsing, severity normalization, scope attribution, state-decision table,
and status-write behavior.

All tests are fixture-driven (a mock ``qodercli`` shell stub); no external scan
or network call is ever made. Pure helpers are unit-tested directly, and the
engine is exercised end-to-end against an isolated git repo via
``python3 -m agentic_loop.gate.qoder_security``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.gate.qoder_security import (  # noqa: E402
    Finding,
    QoderParseError,
    QoderPreflightError,
    attribute_scope,
    blocking,
    build_scan_command,
    classify_scanner_error,
    compute_decision,
    compute_scan_decision,
    extract_scan_paths,
    is_override_approved,
    normalize_sarif_result_severity,
    normalize_severity,
    parse_sarif_report,
    resolve_qoder_bin,
    validate_scan_paths,
    write_qoder_security_block,
)

ITERATION = "it-1"

ADD_DIFF = (
    "diff --git a/packages/x/q.py b/packages/x/q.py\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "--- /dev/null\n"
    "+++ b/packages/x/q.py\n"
    "@@ -0,0 +1 @@\n"
    "+x = 1\n"
)
DEL_DIFF = (
    "diff --git a/packages/x/old.py b/packages/x/old.py\n"
    "deleted file mode 100644\n"
    "index 1234567..0000000\n"
    "--- a/packages/x/old.py\n"
    "+++ /dev/null\n"
    "@@ -1 +0,0 @@\n"
    "-x = 1\n"
)
MOD_DIFF = (
    "diff --git a/packages/x/m.py b/packages/x/m.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/packages/x/m.py\n"
    "+++ b/packages/x/m.py\n"
    "@@ -1 +1 @@\n"
    "-x = 1\n"
    "+x = 2\n"
)


def _rule(**kwargs):
    return kwargs


def _result(**kwargs):
    return kwargs


# ---------------------------------------------------------------------------
# Pure helper unit tests.
# ---------------------------------------------------------------------------
def test_normalize_severity_maps_qoder_raw_to_three_levels():
    assert normalize_severity("critical") == "high"
    assert normalize_severity("high") == "high"
    assert normalize_severity("medium") == "medium"
    assert normalize_severity("low") == "low"
    assert normalize_severity("  HIGH ") == "high"
    assert normalize_severity("info") is None
    assert normalize_severity(3) is None
    assert normalize_severity(None) is None


def test_compute_decision_high_medium_findings_low_pass():
    low = Finding("c", "low", "f", "d", "s")
    medium = Finding("c", "medium", "f", "d", "s")
    high = Finding("c", "high", "f", "d", "s")
    out_of_scope_medium = Finding("c", "medium", "f", "d", "s", scope="out_of_scope")

    assert compute_decision([]) == "PASS"
    assert compute_decision([low]) == "PASS"
    assert compute_decision([low, low]) == "PASS"
    assert compute_decision([medium]) == "FINDINGS"
    assert compute_decision([high]) == "FINDINGS"
    assert compute_decision([low, high]) == "FINDINGS"
    # any high/medium finding blocks, even out-of-scope (fail-closed)
    assert compute_decision([out_of_scope_medium]) == "FINDINGS"


def test_override_and_blocking_state_machine():
    ok_override = {
        "approved": True,
        "approver": "human",
        "justification": "accepted risk",
        "reviewed_at": "2026-08-14T00:00:00Z",
    }
    assert is_override_approved(ok_override) is True
    assert is_override_approved(None) is False
    assert is_override_approved({}) is False
    assert is_override_approved({"approved": "true", "approver": "a",
                                 "justification": "j", "reviewed_at": "t"}) is False
    assert is_override_approved({"approved": True, "approver": "",
                                 "justification": "j", "reviewed_at": "t"}) is False

    assert blocking("PASS") is False
    assert blocking("PASS", None) is False
    assert blocking("FINDINGS") is True
    assert blocking("ERROR") is True
    assert blocking("FINDINGS", ok_override) is False
    assert blocking("ERROR", ok_override) is False


# ---------------------------------------------------------------------------
# Scan-path helpers.
# ---------------------------------------------------------------------------
def test_extract_scan_paths_skips_deletions_and_dedupes():
    assert extract_scan_paths("") == []
    assert extract_scan_paths(ADD_DIFF + DEL_DIFF + MOD_DIFF) == [
        "packages/x/q.py",
        "packages/x/m.py",
    ]
    assert extract_scan_paths(DEL_DIFF) == []
    assert extract_scan_paths(ADD_DIFF + ADD_DIFF) == ["packages/x/q.py"]


@pytest.mark.parametrize(
    "paths",
    [
        ["/abs/path.py"],
        ["../escape.py"],
        ["-leading.py"],
        ["a/../b.py"],
    ],
)
def test_validate_scan_paths_fails_closed(paths):
    with pytest.raises(QoderPreflightError):
        validate_scan_paths(paths)


def test_validate_scan_paths_accepts_relative_paths():
    validate_scan_paths(["a.py", "packages/x/q.py", "sub/-not-leading.py"])


# ---------------------------------------------------------------------------
# CLI adapter: build_scan_command.
# ---------------------------------------------------------------------------
def test_build_scan_command_new_frozen_contract(tmp_path):
    qoder_bin = Path("/opt/qodercli")
    worktree = Path("/repo/.worktrees/w")
    report = tmp_path / "qoder-report.sarif"
    cmd = build_scan_command(
        qoder_bin,
        worktree_root=worktree,
        report_file=report,
        fail_on="none",
        wait_timeout=300,
        changed_paths=["packages/a.py", "packages/b/c.py"],
    )
    assert cmd[0] == "/opt/qodercli"
    assert cmd[1:3] == ["--cwd", "/repo/.worktrees/w"]
    assert cmd[3:5] == ["security", "scan"]
    assert cmd[5:7] == ["--report", f"sarif={report}"]
    assert cmd[7:9] == ["--fail-on", "none"]
    assert cmd[9:11] == ["--wait-timeout", "300"]
    assert cmd[11:] == ["packages/a.py", "packages/b/c.py"]
    # no legacy flags remain
    assert "--permission-mode" not in cmd
    assert "--max-turns" not in cmd
    assert "-o" not in cmd
    assert "--attachment" not in cmd


def test_build_scan_command_optional_config(tmp_path):
    qoder_bin = Path("/opt/qodercli")
    cfg = tmp_path / "qodersec.toml"
    cmd = build_scan_command(
        qoder_bin,
        worktree_root=Path("/repo"),
        report_file=tmp_path / "r.sarif",
        fail_on="medium",
        wait_timeout=10,
        changed_paths=["a.py"],
        config_path=cfg,
    )
    assert cmd[-3:-1] == ["--config", str(cfg)]
    assert cmd[-1] == "a.py"


def test_build_scan_command_arg_overflow_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("QODER_SECURITY_ARG_MAX_BYTES", "50")
    qoder_bin = Path("/opt/qodercli")
    with pytest.raises(QoderPreflightError) as exc:
        build_scan_command(
            qoder_bin,
            worktree_root=Path("/repo"),
            report_file=tmp_path / "r.sarif",
            fail_on="none",
            wait_timeout=10,
            changed_paths=["packages/a.py", "packages/b.py"],
        )
    assert "path_list_too_large" in str(exc.value)


# ---------------------------------------------------------------------------
# SARIF severity normalization.
# ---------------------------------------------------------------------------
def test_security_severity_numeric_buckets():
    assert normalize_sarif_result_severity({"level": "note", "properties": {"security-severity": "9.8"}}, None) == "high"
    assert normalize_sarif_result_severity({"level": "note", "properties": {"security-severity": "7.0"}}, None) == "high"
    assert normalize_sarif_result_severity({"level": "note", "properties": {"security-severity": "4.0"}}, None) == "medium"
    assert normalize_sarif_result_severity({"level": "note", "properties": {"security-severity": "0.5"}}, None) == "low"
    # numeric (not string) is also accepted
    assert normalize_sarif_result_severity({"level": "note", "properties": {"security-severity": 9.5}}, None) == "high"


def test_security_severity_zero_falls_back_to_level():
    result = {"properties": {"security-severity": "0.0"}, "level": "error"}
    assert normalize_sarif_result_severity(result, None) == "high"
    result["level"] = "note"
    assert normalize_sarif_result_severity(result, None) == "low"


@pytest.mark.parametrize("bad", ["-1", "10.1", "abc", "nan", "inf", True])
def test_security_severity_invalid_fails_closed(bad):
    with pytest.raises(QoderParseError):
        normalize_sarif_result_severity({"properties": {"security-severity": bad}}, None)


def test_sarif_level_mapping_and_defaults():
    assert normalize_sarif_result_severity({"level": "error"}, None) == "high"
    assert normalize_sarif_result_severity({"level": "warning"}, None) == "medium"
    assert normalize_sarif_result_severity({"level": "note"}, None) == "low"
    assert normalize_sarif_result_severity({"level": "none"}, None) == "low"
    # missing level → default warning → medium
    assert normalize_sarif_result_severity({}, None) == "medium"
    # rule defaultConfiguration.level used when result.level missing
    rule = _rule(defaultConfiguration={"level": "error"})
    assert normalize_sarif_result_severity({}, rule) == "high"


def test_sarif_unknown_level_fails_closed():
    with pytest.raises(QoderParseError) as exc:
        normalize_sarif_result_severity({"level": "weird"}, None)
    assert "unknown_sarif_level" in str(exc.value)


def test_sarif_categorical_severity_and_take_highest():
    # categorical critical → high
    result = {"level": "note", "properties": {"severity": "critical"}}
    assert normalize_sarif_result_severity(result, None) == "high"
    # security-severity 9.8 (high) must not be downgraded by level=note
    result = {"level": "note", "properties": {"security-severity": "9.8"}}
    assert normalize_sarif_result_severity(result, None) == "high"
    # unknown categorical value fails closed
    with pytest.raises(QoderParseError):
        normalize_sarif_result_severity({"properties": {"severity": "weird"}}, None)


def test_security_severity_rule_high_not_masked_by_result_low():
    result = _result(properties={"security-severity": "1.0"}, level="note")
    rule = _rule(properties={"security-severity": "9.8"})
    assert normalize_sarif_result_severity(result, rule) == "high"


def test_security_severity_result_high_not_masked_by_rule_low():
    result = _result(properties={"security-severity": "9.8"}, level="note")
    rule = _rule(properties={"security-severity": "1.0"})
    assert normalize_sarif_result_severity(result, rule) == "high"


@pytest.mark.parametrize(
    "result_props,rule_props",
    [
        ({"security-severity": "1.0"}, {"security-severity": "abc"}),
        ({"security-severity": "abc"}, {"security-severity": "1.0"}),
    ],
)
def test_security_severity_invalid_in_either_source_fails_closed(
    result_props, rule_props
):
    result = _result(properties=result_props, level="note")
    rule = _rule(properties=rule_props)
    with pytest.raises(QoderParseError):
        normalize_sarif_result_severity(result, rule)


def test_categorical_severity_rule_high_not_masked_by_result_low():
    result = _result(properties={"severity": "low"}, level="note")
    rule = _rule(properties={"severity": "high"})
    assert normalize_sarif_result_severity(result, rule) == "high"


@pytest.mark.parametrize(
    "result_props,rule_props",
    [
        ({"severity": "bogus"}, {"severity": "low"}),
        ({"severity": "low"}, {"severity": "bogus"}),
    ],
)
def test_categorical_severity_invalid_in_either_source_fails_closed(
    result_props, rule_props
):
    result = _result(properties=result_props, level="note")
    rule = _rule(properties=rule_props)
    with pytest.raises(QoderParseError):
        normalize_sarif_result_severity(result, rule)


# ---------------------------------------------------------------------------
# SARIF report parsing.
# ---------------------------------------------------------------------------
def _sarif_doc(results, *, version="2.1.0", external=None, runs=None):
    if runs is None:
        runs = [{"tool": {"driver": {"name": "qoder"}}, "results": results}]
    doc = {"version": version, "runs": runs}
    if external is not None:
        doc["externalPropertyFileReferences"] = external
    return json.dumps(doc)


def test_parse_sarif_report_success():
    doc = _sarif_doc([
        {"ruleId": "rule-1", "level": "error", "message": {"text": "sql injection"},
         "locations": [{"physicalLocation": {"artifactLocation": {"uri": "a.py"}}}],
         "suppressions": [{"kind": "inSource"}]},
        {"ruleId": "rule-2", "level": "note", "message": {"text": "low"},
         "locations": [{"physicalLocation": {"artifactLocation": {"uri": "b.py"}}}]},
    ])
    parsed = parse_sarif_report(doc)
    assert len(parsed) == 2
    assert parsed[0].severity == "high"
    assert parsed[0].rule_id == "rule-1"
    assert parsed[0].message == "sql injection"
    assert parsed[0].paths == ("a.py",)
    assert parsed[0].suppressed is True
    assert parsed[1].severity == "low"


def test_parse_sarif_report_empty_runs_is_passable():
    assert parse_sarif_report(_sarif_doc([])) == []


@pytest.mark.parametrize(
    "doc,expected",
    [
        ("", "empty SARIF report"),
        ("not json", "invalid JSON"),
        (_sarif_doc([], version="2.0.0"), "unsupported_sarif_version"),
        ('{"version":"2.1.0","runs":{}}', "runs must be a list"),
        (_sarif_doc("not-a-list"), "run.results must be a list"),
        (_sarif_doc([{"ruleId": "r", "level": "weird"}]), "unknown_sarif_level"),
        (_sarif_doc([{"ruleId": "r", "properties": {"security-severity": "99"}}]), "invalid_severity"),
    ],
)
def test_parse_sarif_report_fails_closed(doc, expected):
    with pytest.raises(QoderParseError) as exc:
        parse_sarif_report(doc)
    assert expected in str(exc.value)


def test_parse_sarif_report_external_refs_fail_closed():
    doc = _sarif_doc([], external={"results": [{"location": "x"}]})
    with pytest.raises(QoderParseError) as exc:
        parse_sarif_report(doc)
    assert "external_sarif_properties_unsupported" in str(exc.value)

    # run-level externalPropertyFileReferences also fail closed
    runs = [{"tool": {"driver": {"name": "q"}}, "results": [],
             "externalPropertyFileReferences": {"rules": []}}]
    with pytest.raises(QoderParseError) as exc:
        parse_sarif_report(_sarif_doc([], runs=runs))
    assert "external_sarif_properties_unsupported" in str(exc.value)

    # any external property key (not just results/rules) now fails closed
    doc = _sarif_doc([], external={"conversion": {"tool": {"driver": {"name": "x"}}}})
    with pytest.raises(QoderParseError) as exc:
        parse_sarif_report(doc)
    assert "external_sarif_properties_unsupported" in str(exc.value)


def test_parse_sarif_rule_metadata_security_severity():
    runs = [{
        "tool": {"driver": {"name": "q", "rules": [
            {"id": "rule-1", "properties": {"security-severity": "9.1"},
             "defaultConfiguration": {"level": "note"}},
        ]}},
        "results": [{"ruleId": "rule-1", "message": {"text": "x"}}],
    }]
    parsed = parse_sarif_report(_sarif_doc([], runs=runs))
    assert parsed[0].severity == "high"


# ---------------------------------------------------------------------------
# Scope attribution.
# ---------------------------------------------------------------------------
def test_attribute_scope_in_scope_and_out_of_scope():
    parsed = [
        _parsed("high", "a.py", paths=("a.py",)),
        _parsed("high", "b.py", paths=("unrelated.py",)),
        _parsed("high", "no-loc", paths=()),
    ]
    findings = attribute_scope(parsed, ["a.py"])
    assert [f.scope for f in findings] == ["in_scope", "out_of_scope", "out_of_scope"]
    assert compute_decision(findings) == "FINDINGS"


def test_attribute_scope_matches_related_and_absolute_uris():
    parsed = [
        _parsed("medium", "x", paths=("src/gate/q.py",)),
        _parsed("medium", "y", paths=("file:///repo/packages/a.py",)),
    ]
    findings = attribute_scope(parsed, ["packages/a.py", "packages/agentic-loop/src/gate/q.py"])
    assert [f.scope for f in findings] == ["in_scope", "in_scope"]


def _parsed(severity, rule_id, paths=(), dataflow="", suppressed=False):
    from agentic_loop.gate.qoder_security import ParsedFinding
    return ParsedFinding(severity, rule_id, "m", tuple(paths), dataflow, suppressed)


# ---------------------------------------------------------------------------
# State-decision table (exit code × parsed findings).
# ---------------------------------------------------------------------------
def _f(sev, scope="in_scope"):
    return Finding("c", sev, "f", "d", "s", scope=scope)


def test_scan_decision_exit0_adopts_parser():
    assert compute_scan_decision([], exit_code=0, fail_on="none").decision == "PASS"
    assert compute_scan_decision([_f("low")], exit_code=0, fail_on="none").decision == "PASS"
    d = compute_scan_decision([_f("low")], exit_code=0, fail_on="none")
    assert d.extra["low_findings_count"] == 1
    assert compute_scan_decision([_f("high")], exit_code=0, fail_on="none").decision == "FINDINGS"


def test_scan_decision_exit_nonzero_with_blocking_is_findings():
    d = compute_scan_decision([_f("high")], exit_code=1, fail_on="none")
    assert d.decision == "FINDINGS"
    assert d.extra["exit_code"] == 1
    assert d.extra["scanner_exit_indicated_findings"] is True


def test_scan_decision_exit_nonzero_without_blocking_is_error():
    d = compute_scan_decision([], exit_code=1, fail_on="none", stderr="scan failed")
    assert d.decision == "ERROR"
    assert d.error_kind == "preflight_failed"
    assert "exit_without_blocking_findings" in d.error_message


def test_scan_decision_exit_nonzero_auth_maps_to_auth_expired():
    d = compute_scan_decision([], exit_code=2, fail_on="none", stderr="auth expired")
    assert d.decision == "ERROR"
    assert d.error_kind == "auth_expired"


def test_scan_decision_exit_nonzero_timeout_maps_to_timeout():
    d = compute_scan_decision([], exit_code=2, fail_on="none", stderr="scan timed out")
    assert d.decision == "ERROR"
    assert d.error_kind == "timeout"


def test_scan_decision_exit0_medium_fail_on_blocking_records_sanity_mismatch():
    d = compute_scan_decision([_f("high")], exit_code=0, fail_on="medium")
    assert d.decision == "FINDINGS"
    assert d.extra["sanity_mismatch"] is True
    # with --fail-on none there is no sanity mismatch (exit 0 is expected)
    d2 = compute_scan_decision([_f("high")], exit_code=0, fail_on="none")
    assert "sanity_mismatch" not in d2.extra


def test_classify_scanner_error():
    assert classify_scanner_error("auth expired") == "auth_expired"
    assert classify_scanner_error("timed out") == "timeout"
    assert classify_scanner_error("quota exhausted") == "credits_exhausted"
    assert classify_scanner_error("connection refused") == "preflight_failed"
    assert classify_scanner_error("") is None


# ---------------------------------------------------------------------------
# Status-write unit tests.
# ---------------------------------------------------------------------------
def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_qoder_security_block_shapes(tmp_path):
    status = tmp_path / "WP-01.status.json"
    status.write_text(json.dumps({"timestamps": {}}))

    write_qoder_security_block(
        status,
        decision="FINDINGS",
        findings=[Finding("injection", "high", "a.py", "x", "sql")],
        level="L3",
        extra={"low_findings_count": 0},
    )
    block = _load(status)["qoder_security"]
    assert block["decision"] == "FINDINGS"
    assert block["level"] == "L3"
    assert block["requested_level"] == "L3"
    assert block["findings"] == [{
        "category": "injection", "severity": "high", "file": "a.py",
        "dataflow": "x", "summary": "sql", "scope": "in_scope",
        "suppressed": False,
    }]
    assert block["low_findings_count"] == 0
    assert "error" not in block
    assert "override" not in block


def test_write_qoder_security_error_block_and_override_preserved(tmp_path):
    status = tmp_path / "WP-01.status.json"
    status.write_text(json.dumps({"timestamps": {}}))

    write_qoder_security_block(
        status,
        decision="ERROR",
        findings=[],
        level="L3",
        error_kind="timeout",
        error_message="took too long",
    )
    block = _load(status)["qoder_security"]
    assert block["decision"] == "ERROR"
    assert block["error"] == {"kind": "timeout", "message": "took too long"}

    override = {
        "approved": True, "approver": "human",
        "justification": "accepted", "reviewed_at": "2026-08-14T00:00:00Z",
    }
    data = _load(status)
    data["qoder_security"]["override"] = override
    status.write_text(json.dumps(data))

    write_qoder_security_block(
        status,
        decision="FINDINGS",
        findings=[Finding("x", "medium", "f", "d", "s")],
        level="L3",
    )
    block = _load(status)["qoder_security"]
    assert block["decision"] == "FINDINGS"
    assert block["override"] == override


def test_write_qoder_security_unknown_error_kind_falls_back(tmp_path):
    status = tmp_path / "WP-01.status.json"
    status.write_text(json.dumps({"timestamps": {}}))
    write_qoder_security_block(
        status, decision="ERROR", findings=[], level="L3", error_kind="bogus",
    )
    assert _load(status)["qoder_security"]["error"]["kind"] == "preflight_failed"


def test_write_qoder_security_detail_present(tmp_path):
    status = tmp_path / "WP-01.status.json"
    status.write_text(json.dumps({"timestamps": {}}))
    write_qoder_security_block(
        status, decision="PASS", findings=[], level="L3",
        detail="deleted_only_no_scan_target",
    )
    assert _load(status)["qoder_security"]["detail"] == "deleted_only_no_scan_target"


# ---------------------------------------------------------------------------
# End-to-end engine against an isolated git repo + mock qoder.
# ---------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    _git(r, "config", "user.email", "t@e.com")
    _git(r, "config", "user.name", "T")
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")
    _git(r, "branch", "-M", "main")
    return r


def make_qoder_mock(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    mock = bindir / "qodercli"
    mock.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "if [[ -n \"${MOCK_QODER_CALLED_FILE:-}\" ]]; then\n"
        "  touch \"${MOCK_QODER_CALLED_FILE}\"\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"--version\" ]]; then\n"
        "  if [[ \"${MOCK_QODER_VERSION_FAIL:-0}\" == \"1\" ]]; then\n"
        "    echo \"qodercli: cannot run\" >&2\n"
        "    exit 1\n"
        "  fi\n"
        "  echo \"qodercli 1.1.21\"\n"
        "  exit 0\n"
        "fi\n"
        "if [[ -n \"${MOCK_QODER_ARGV_FILE:-}\" ]]; then\n"
        "  printf '%s\\n' \"$0 $*\" >> \"${MOCK_QODER_ARGV_FILE}\"\n"
        "fi\n"
        "cwd=\"\"; report=\"\"; fail_on=\"\"; prev=\"\"\n"
        "for arg in \"$@\"; do\n"
        "  case \"$prev\" in\n"
        "    --cwd) cwd=\"$arg\" ;;\n"
        "    --report) report=\"$arg\" ;;\n"
        "    --fail-on) fail_on=\"$arg\" ;;\n"
        "  esac\n"
        "  prev=\"$arg\"\n"
        "done\n"
        "if [[ -n \"${MOCK_QODER_SCAN_SLEEP:-}\" && \"${MOCK_QODER_SCAN_SLEEP}\" != \"0\" ]]; then\n"
        "  sleep \"${MOCK_QODER_SCAN_SLEEP}\"\n"
        "fi\n"
        "if [[ \"${MOCK_QODER_AUTH_FAIL:-0}\" == \"1\" ]]; then\n"
        "  echo \"auth expired\" >&2\n"
        "  exit 2\n"
        "fi\n"
        "if [[ \"${MOCK_QODER_SCAN_EXIT:-0}\" != \"0\" ]]; then\n"
        "  echo \"${MOCK_QODER_SCAN_STDERR:-scan failed}\" >&2\n"
        "  exit \"${MOCK_QODER_SCAN_EXIT}\"\n"
        "fi\n"
        "if [[ \"${MOCK_QODER_REJECT_FAIL_ON_NONE:-0}\" == \"1\" && \"$fail_on\" == \"none\" ]]; then\n"
        "  echo \"invalid value 'none' for --fail-on\" >&2\n"
        "  exit 2\n"
        "fi\n"
        "if [[ -n \"${MOCK_QODER_MUTATE_FILE:-}\" && -n \"$cwd\" ]]; then\n"
        "  touch \"$cwd/${MOCK_QODER_MUTATE_FILE}\"\n"
        "fi\n"
        "file=\"${report#sarif=}\"\n"
        "if [[ -z \"$file\" || \"$file\" == \"$report\" ]]; then\n"
        "  echo \"mock: --report must be sarif=<file>\" >&2\n"
        "  exit 2\n"
        "fi\n"
        "mkdir -p \"$(dirname \"$file\")\"\n"
        "sarif=\"${MOCK_QODER_SARIF-}\"\n"
        "if [[ -z \"$sarif\" ]]; then\n"
        "  sarif='{\"version\":\"2.1.0\",\"runs\":[]}'\n"
        "fi\n"
        "printf '%s' \"$sarif\" > \"$file\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    mock.chmod(0o755)
    return mock


CHANGED_PATH = "packages/agentic-loop/src/agentic_loop/gate/q.py"


def _setup_wp(repo: Path) -> tuple[str, str, str, str]:
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    p = repo / CHANGED_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "impl")
    tip = _git(repo, "rev-parse", "HEAD")
    rel = f"docs/plans/{ITERATION}/WP-01.status.json"
    return base, tip, rel, CHANGED_PATH


def _write_status(repo: Path, rel: str, *, base: str, tip: str,
                  network: bool = True, branch: str = "feat/x") -> Path:
    data = {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-01",
        "iteration_id": ITERATION,
        "phase": "P0",
        "state": "READY_FOR_REVIEW",
        "role": "Developer",
        "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"},
        "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "main", "base_commit": base, "branch": branch,
                "worktree": ".", "commit": tip},
        "scope": {"allowed_paths": ["packages/"], "forbidden_paths": []},
        "risk": {"production_writes_authorized": False, "network_authorized": network,
                 "real_notifications_authorized": False,
                 "irreversible_actions_authorized": False},
        "evidence": {"tests": [{"cmd": "pytest", "exit_code": 0}]},
        "review": {"decision": "ACCEPT"},
        "consult": {"decision": None},
        "timestamps": {},
    }
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    # WP-01: the status-source predicate reads the authoritative branch from the
    # PLAN status beside the judged file, so the fixture must supply one. It
    # declares the branch this repo actually holds ("main", renamed in `repo`).
    (f.parent / "PLAN-01.status.json").write_text(json.dumps({
        "schema_version": "agentic-plan-status/v1",
        "plan_id": "PLAN-01",
        "iteration_id": ITERATION,
        "state": "ACTIVE",
        "title": "fixture plan",
        # The branch this repo ACTUALLY holds right now: these fixtures check
        # out a feature branch, so a hardcoded "main" would not match the holder
        # and the predicate would correctly refuse.
        "git": {"base_branch": _git(repo, "branch", "--show-current").strip()
                               or "main",
                "target_branch": "main"},
        "work_packages": ["WP-01"],
        "timestamps": {"created_at": "2026-01-01T00:00:00Z",
                       "updated_at": "2026-01-01T00:00:00Z"},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


def run_qoder_gate(repo: Path, status_rel: str, mock: Path, extra_env=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["QODER_SECURITY_BIN"] = str(mock)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "agentic_loop.gate.qoder_security", status_rel],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )


def _qoder_block(repo: Path, status_rel: str) -> dict:
    return json.loads((repo / status_rel).read_text(encoding="utf-8"))["qoder_security"]


def _loc(uri):
    return {"physicalLocation": {"artifactLocation": {"uri": uri}}}


def test_e2e_argv_shape_asserted(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_ARGV_FILE": str(argv_file)})
    assert res.returncode == 0, res.stderr
    lines = argv_file.read_text().splitlines()
    # last line is the single scan invocation (version probe is not recorded)
    assert len(lines) == 1
    argv = lines[0].split(" ")
    assert argv[0].endswith("/qodercli")
    assert argv[1:3] == ["--cwd", str(repo)]
    assert argv[3:5] == ["security", "scan"]
    assert argv[5] == "--report"
    assert argv[6].startswith("sarif=")
    assert argv[7:9] == ["--fail-on", "none"]
    assert argv[9] == "--wait-timeout"
    assert relpath in argv


def test_e2e_high_and_medium_are_findings(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    sarif = json.dumps({
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "q"}}, "results": [
            {"ruleId": "injection", "level": "error", "message": {"text": "sql"},
             "locations": [_loc(relpath)]},
            {"ruleId": "info", "level": "note", "message": {"text": "low"},
             "locations": [_loc(relpath)]},
        ]}],
    })
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_SARIF": sarif})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "FINDINGS"
    assert {f["severity"] for f in block["findings"]} == {"high", "low"}
    assert "QODER_SECURITY_DECISION=FINDINGS" in res.stdout


def test_e2e_security_severity_rule_high_beats_result_low(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    sarif = json.dumps({
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "q", "rules": [
                {"id": "rule-high", "properties": {"security-severity": "9.8"}},
            ]}},
            "results": [
                {"ruleId": "rule-high", "level": "note",
                 "properties": {"security-severity": "1.0"},
                 "message": {"text": "sql injection"},
                 "locations": [_loc(relpath)]},
            ],
        }],
    })
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_SARIF": sarif})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "FINDINGS"
    assert block["findings"][0]["severity"] == "high"


def test_e2e_only_low_is_pass(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    sarif = json.dumps({
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "q"}}, "results": [
            {"ruleId": "info", "level": "note", "message": {"text": "low"},
             "locations": [_loc(relpath)]},
        ]}],
    })
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_SARIF": sarif})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "PASS"
    assert block["low_findings_count"] == 1
    assert len(block["findings"]) == 1


def test_e2e_no_findings_is_pass(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock)
    assert res.returncode == 0, res.stderr
    assert _qoder_block(repo, rel)["decision"] == "PASS"


def test_e2e_worktree_head_matches_tip_not_blocked(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_ARGV_FILE": str(argv_file)})
    assert res.returncode == 0, res.stderr
    # the new worktree-tip preflight must not block a matching checkout
    assert argv_file.exists()
    assert relpath in argv_file.read_text()
    assert _qoder_block(repo, rel)["decision"] == "PASS"


def test_e2e_worktree_head_mismatch_fails_closed(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    # check out main (an earlier commit) so the worktree HEAD != reviewed tip
    _git(repo, "checkout", "-q", "main")
    _write_status(repo, rel, base=base, tip=tip, branch="feat/x")
    mock = make_qoder_mock(tmp_path)
    marker = tmp_path / "called"
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_CALLED_FILE": str(marker)})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "preflight_failed"
    assert "worktree_head_mismatch" in block["error"]["message"]
    # no qoder invocation happened at all (not even the local --version probe)
    assert not marker.exists()


def test_e2e_dirty_changed_path_fails_closed_before_scan(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    # make the scanned changed path dirty (tracked modification, not committed),
    # while HEAD still equals tip — the new pre-scan cleanliness gate must fail
    # closed before any qoder invocation.
    p = repo / relpath
    p.write_text("x = 999\n")
    mock = make_qoder_mock(tmp_path)
    marker = tmp_path / "called"
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {
        "MOCK_QODER_CALLED_FILE": str(marker),
        "MOCK_QODER_ARGV_FILE": str(argv_file),
    })
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "preflight_failed"
    assert "worktree_not_clean" in block["error"]["message"]
    # no qoder invocation happened at all (not even the local --version probe)
    assert not marker.exists()
    assert not argv_file.exists()


def test_e2e_unrelated_untracked_file_does_not_block_scan(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    # an untracked file that is NOT one of the scanned changed paths must not
    # trip the cleanliness gate (scope is limited to changed_paths).
    (repo / "scratch.txt").write_text("not scanned\n")
    mock = make_qoder_mock(tmp_path)
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_ARGV_FILE": str(argv_file)})
    assert res.returncode == 0, res.stderr
    assert relpath in argv_file.read_text()
    assert _qoder_block(repo, rel)["decision"] == "PASS"


def test_e2e_out_of_scope_high_still_blocks(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    sarif = json.dumps({
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "q"}}, "results": [
            {"ruleId": "injection", "level": "error", "message": {"text": "x"},
             "locations": [_loc("unrelated.py")]},
        ]}],
    })
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_SARIF": sarif})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "FINDINGS"
    assert block["findings"][0]["scope"] == "out_of_scope"


def test_e2e_network_not_authorized_refuses_scan(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip, network=False)
    mock = make_qoder_mock(tmp_path)
    marker = tmp_path / "called"
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_CALLED_FILE": str(marker)})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "network_not_authorized"
    assert not marker.exists()


def test_e2e_auth_expired(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_AUTH_FAIL": "1"})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "auth_expired"


def test_e2e_binary_missing_preflight_failed(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    res = run_qoder_gate(
        repo, rel, Path("/nonexistent/qodercli"), {"QODER_SECURITY_BIN": "/nonexistent/qodercli"}
    )
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "preflight_failed"


def test_e2e_version_probe_fails_preflight(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_VERSION_FAIL": "1"})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "preflight_failed"


def test_e2e_parse_failed(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_SARIF": "not json"})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "parse_failed"


def test_e2e_report_missing_parse_failed(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_SCAN_EXIT": "2"})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "parse_failed"


def test_e2e_timeout(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock, {
        "MOCK_QODER_SCAN_SLEEP": "3",
        "QODER_SECURITY_TIMEOUT_SECONDS": "1",
    })
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "timeout"


def test_e2e_scanner_mutated_worktree(repo, tmp_path):
    base, tip, rel, _ = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    res = run_qoder_gate(repo, rel, mock, {"MOCK_QODER_MUTATE_FILE": "mutated.txt"})
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "ERROR"
    assert block["error"]["kind"] == "preflight_failed"
    assert "scanner_mutated_worktree" in block["error"]["message"]


def test_e2e_deleted_only_is_pass(repo, tmp_path):
    # a file exists in base and is deleted on the branch → pure deletion diff
    f = repo / "packages" / "gone.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add gone")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feat/del")
    f.unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete gone")
    tip = _git(repo, "rev-parse", "HEAD")
    rel = f"docs/plans/{ITERATION}/WP-01.status.json"
    _write_status(repo, rel, base=base, tip=tip, branch="feat/del")
    mock = make_qoder_mock(tmp_path)
    marker = tmp_path / "called"
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {
        "MOCK_QODER_CALLED_FILE": str(marker),
        "MOCK_QODER_ARGV_FILE": str(argv_file),
    })
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "PASS"
    assert block["detail"] == "deleted_only_no_scan_target"
    # no qoder invocation at all (not even the local --version probe)
    assert not marker.exists()
    assert not argv_file.exists()


def test_e2e_deleted_only_network_false_still_pass(repo, tmp_path):
    # deleted-only WP (no scan target) must reach the fixed PASS even when
    # network is unauthorized: the network gate guards only real scan paths.
    f = repo / "packages" / "gone.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add gone")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feat/del")
    f.unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete gone")
    tip = _git(repo, "rev-parse", "HEAD")
    rel = f"docs/plans/{ITERATION}/WP-01.status.json"
    _write_status(repo, rel, base=base, tip=tip, branch="feat/del", network=False)
    mock = make_qoder_mock(tmp_path)
    marker = tmp_path / "called"
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {
        "MOCK_QODER_CALLED_FILE": str(marker),
        "MOCK_QODER_ARGV_FILE": str(argv_file),
    })
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "PASS"
    assert block["detail"] == "deleted_only_no_scan_target"
    assert not marker.exists()
    assert not argv_file.exists()


def test_e2e_deleted_only_worktree_stale_still_pass(repo, tmp_path):
    # deleted-only WP must reach the fixed PASS even when the worktree HEAD is
    # stale (HEAD != reviewed tip): the worktree-tip gate guards only real scan
    # paths and there is nothing to scan here.
    f = repo / "packages" / "gone.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add gone")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feat/del")
    f.unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete gone")
    tip = _git(repo, "rev-parse", "HEAD")
    # checkout main (an earlier commit) so worktree HEAD != reviewed tip
    _git(repo, "checkout", "-q", "main")
    rel = f"docs/plans/{ITERATION}/WP-01.status.json"
    _write_status(repo, rel, base=base, tip=tip, branch="feat/del")
    mock = make_qoder_mock(tmp_path)
    marker = tmp_path / "called"
    argv_file = tmp_path / "argv.txt"
    res = run_qoder_gate(repo, rel, mock, {
        "MOCK_QODER_CALLED_FILE": str(marker),
        "MOCK_QODER_ARGV_FILE": str(argv_file),
    })
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "PASS"
    assert block["detail"] == "deleted_only_no_scan_target"
    assert not marker.exists()
    assert not argv_file.exists()


def test_e2e_fail_on_none_fallback_to_medium(repo, tmp_path):
    base, tip, rel, relpath = _setup_wp(repo)
    _write_status(repo, rel, base=base, tip=tip)
    mock = make_qoder_mock(tmp_path)
    argv_file = tmp_path / "argv.txt"
    sarif = json.dumps({
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "q"}}, "results": [
            {"ruleId": "injection", "level": "error", "message": {"text": "sql"},
             "locations": [_loc(relpath)]},
        ]}],
    })
    res = run_qoder_gate(repo, rel, mock, {
        "MOCK_QODER_REJECT_FAIL_ON_NONE": "1",
        "MOCK_QODER_ARGV_FILE": str(argv_file),
        "MOCK_QODER_SARIF": sarif,
    })
    assert res.returncode == 0, res.stderr
    block = _qoder_block(repo, rel)
    assert block["decision"] == "FINDINGS"
    lines = argv_file.read_text().splitlines()
    assert len(lines) == 2  # first none (rejected), then medium
    assert "--fail-on medium" in lines[-1]


def test_e2e_usage_is_64(repo):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    res = subprocess.run(
        [sys.executable, "-m", "agentic_loop.gate.qoder_security"],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )
    assert res.returncode == 64
    assert "usage:" in res.stderr

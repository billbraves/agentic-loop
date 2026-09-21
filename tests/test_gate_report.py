"""WP-01: compact gate-report layer over the structured gate-result model.

Two kinds of tests:

1. **Characterization tests** (the brief's hardest DoD): pin that the new
   report's *judgment* — the PASS/FAIL verdict and the exit code — is byte-for-
   byte identical to the runner's ``StageRunResult.blocked()`` /
   ``exit_code()``. The report is only allowed to change *rendering*, never a
   decision. This is proven by building the exact same ``GateResult`` fixtures
   as ``test_gate_runner.py``, feeding them to both the runner's
   ``run_stage`` and the report, and asserting the verdicts agree across every
   combination of decisions / blocking flags / unknown decisions.

2. **New-behaviour tests**: the summary line is compact and colorless, mentions
   only executed checks, emits no per-gate lines on success, surfaces a locator
   (command / exit code) on failure, and offloads the full plan + failure
   detail to a file whose path the summary line names.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.runner.gate_runner import (  # noqa: E402
    DECISION_ERROR,
    DECISION_FAIL,
    DECISION_PASS,
    GateResult,
    StageRunResult,
)
from agentic_loop.gate.report import (  # noqa: E402
    detail_text,
    exit_code,
    is_blocked,
    render_report,
    summary_line,
    write_report,
)


def _result(name, decision, blocking=True, detail="", kind="command", stage="pre_review"):
    """A single gate result dict in the runner's ``GateResult.to_dict()`` shape."""
    return {
        "name": name,
        "kind": kind,
        "stage": stage,
        "decision": decision,
        "blocking": blocking,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Characterization: the report never changes the verdict / exit code
# ---------------------------------------------------------------------------


def _authoritative_verdict(results):
    """The runner's own verdict for a set of results, as ground truth.

    Rebuilds ``GateResult`` objects (matching how the runner normalizes them)
    and returns ``(blocked, exit_code)`` from ``StageRunResult``.
    """
    gate_results = [
        GateResult(
            name=r["name"],
            kind=r["kind"],
            stage=r["stage"],
            decision=r["decision"],
            blocking=r["blocking"],
            detail=r["detail"],
        )
        for r in results
    ]
    srr = StageRunResult(stage="pre_review", gates=gate_results)
    return srr.blocked(), srr.exit_code()


def test_characterization_verdict_matches_runner_all_combinations():
    """For every blocking/decision combination, report verdict == runner verdict."""
    decisions = [DECISION_PASS, DECISION_FAIL, DECISION_ERROR, "FINDINGS", "bogus"]
    cases = []
    for d in decisions:
        for blocking in (True, False):
            cases.append(([("a", d, blocking)], d, blocking))
    # multi-gate mixes: all-pass, one blocking fail, non-blocking fail among passes
    cases += [
        ([("a", DECISION_PASS, True), ("b", DECISION_PASS, True)], "multi", None),
        (
            [
                ("a", DECISION_PASS, True),
                ("b", DECISION_FAIL, True),
                ("c", DECISION_PASS, True),
            ],
            "multi",
            None,
        ),
        (
            [
                ("a", DECISION_PASS, True),
                ("b", DECISION_FAIL, False),
                ("c", DECISION_PASS, True),
            ],
            "multi",
            None,
        ),
    ]
    for gates_spec, _d, _b in cases:
        results = [
            _result(name, dec, blocking)
            for (name, dec, blocking) in gates_spec
        ]
        runner_blocked, runner_rc = _authoritative_verdict(results)
        assert is_blocked(results) == runner_blocked, results
        assert exit_code(results) == runner_rc, results
        report = render_report(results)
        assert report["blocked"] == runner_blocked, results
        assert report["exit_code"] == runner_rc, results


def test_characterization_non_blocking_fail_not_blocked():
    """A non-blocking FAIL must not change the verdict (parity with runner)."""
    results = [
        _result("pytest", DECISION_PASS, True, "ran 1 command(s)"),
        _result("lint", DECISION_FAIL, False, "command failed (exit 1): lint"),
    ]
    assert is_blocked(results) is False
    assert exit_code(results) == 0
    assert _authoritative_verdict(results) == (False, 0)


def test_characterization_unknown_decision_fails_closed():
    """Unknown/malformed decisions must read as ERROR (block if blocking)."""
    results = [_result("g", "bogus", True, "")]
    assert is_blocked(results) is True
    assert exit_code(results) == 1


# ---------------------------------------------------------------------------
# New behaviour: compact summary + detail offload
# ---------------------------------------------------------------------------


def test_summary_success_is_compact_and_colorless():
    results = [
        _result("scope", DECISION_PASS, True, "scope clean"),
        _result("pytest", DECISION_PASS, True, "ran 1 command(s)"),
        _result("lint", DECISION_PASS, True, "ran 1 command(s)"),
    ]
    line = summary_line(results)
    assert line == "✓ 3 gates passed"
    # no per-gate detail leaked into the success summary
    assert "scope" not in line
    assert "pytest" not in line
    assert "lint" not in line


def test_summary_mentions_only_executed_checks():
    # Two executed checks only -> the summary counts exactly two.
    results = [
        _result("a", DECISION_PASS, True, "ok"),
        _result("b", DECISION_PASS, True, "ok"),
    ]
    assert summary_line(results) == "✓ 2 gates passed"
    # A single executed check renders singular.
    assert summary_line([_result("a", DECISION_PASS, True, "ok")]) == "✓ 1 gate passed"


def test_summary_failure_includes_locator():
    results = [
        _result("scope", DECISION_PASS, True, "scope clean"),
        _result("pytest", DECISION_FAIL, True, "command failed (exit 1): python3 -m pytest tests"),
    ]
    line = summary_line(results)
    assert line.startswith("✗ 1/2 gates passed")
    # locator: cheapest failing gate name + first detail line (command / exit code)
    assert "pytest: command failed (exit 1): python3 -m pytest tests" in line


def test_summary_names_detail_path_when_given():
    results = [_result("pytest", DECISION_FAIL, True, "command failed (exit 1): pytest")]
    line = summary_line(results, detail_path=Path("/tmp/gate-report.txt"))
    assert "details: /tmp/gate-report.txt" in line


def test_detail_text_contains_full_plan_and_detail():
    results = [
        _result("scope", DECISION_PASS, True, "scope clean"),
        _result("pytest", DECISION_FAIL, True, "command failed (exit 1): pytest\nextra line"),
    ]
    text = detail_text(results)
    # full plan (both executed gates) present with decisions + detail
    assert "[PASS] scope" in text
    assert "[FAIL] pytest" in text
    assert "command failed (exit 1): pytest" in text
    assert "extra line" in text


def test_write_report_returns_summary_with_path_and_writes_file(tmp_path):
    results = [
        _result("scope", DECISION_PASS, True, "scope clean"),
        _result("pytest", DECISION_FAIL, True, "command failed (exit 2): pytest"),
    ]
    target = tmp_path / "nested" / "gate-report.txt"
    line = write_report(results, target)
    assert str(target) in line
    assert target.is_file()
    # on-disk file carries the full plan + failure detail, not the summary-only form
    content = target.read_text(encoding="utf-8")
    assert "[FAIL] pytest" in content
    assert "command failed (exit 2): pytest" in content


def test_render_report_shape_and_empty_gates():
    report = render_report([])
    assert report["blocked"] is False
    assert report["exit_code"] == 0
    assert report["summary"] == "✓ 0 gates passed"
    assert report["detail"] == ""

"""WP-02 gate runner: deterministic §3.4 scheduling + generic result model.

Unit tests over the pure runner helpers and the stage executor:

- §3.4 frozen ordering (first_match / overlay mixed, path-order invariance,
  first-occurrence de-dup, declaration-order interleaving not apply grouping);
- ``blocking=false`` records FAIL but does not block / change exit code;
- unmatched pass vs. empty-rules fail-closed;
- pytest rc 4/5 skip vs. non-pytest rc 4/5 fatal (quality-gate.sh parity);
- qoder_judge enabled -> ``unsupported-kind`` fail-closed;
- qoder ``FINDINGS`` -> generic ``FAIL`` normalization;
- merge stage stops after the first blocking failure.
"""
from __future__ import annotations

import itertools
import json
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
    normalize_decision,
    plan_commands,
    run_stage,
    write_gates_to_status,
)


def gate(name, kind="command", stage="pre_review", *, apply="first_match",
         blocking=True, enabled=True, rules=None, **extra):
    d = {
        "name": name,
        "kind": kind,
        "stage": stage,
        "apply": apply,
        "blocking": blocking,
        "enabled": enabled,
    }
    d.update(extra)
    if kind == "command" and rules is not None:
        d["rule"] = rules
    return d


def rule(match, run):
    return {"match": match, "run": run}


# ---------------------------------------------------------------------------
# §3.4 ordering
# ---------------------------------------------------------------------------

def test_first_match_single_gate_parity():
    g = gate("t", rules=[
        rule("packages/engine/**", ["E", "B"]),
        rule("packages/data-app/**", ["D", "B"]),
    ])
    assert plan_commands([g], "pre_review", ["packages/engine/x.py"]) == ["E", "B"]
    assert plan_commands([g], "pre_review", ["packages/data-app/y.py"]) == ["D", "B"]
    assert plan_commands(
        [g], "pre_review", ["packages/engine/x.py", "packages/data-app/y.py"]
    ) == ["E", "B", "D"]


def test_overlay_all_matching_rules_contribute():
    g = gate("cross", apply="overlay", rules=[
        rule("skills/**", ["F"]),
        rule("skills/ad/**", ["C"]),
    ])
    # both rules match a skills/ad change under overlay
    assert plan_commands([g], "pre_review", ["skills/ad/x.py"]) == ["F", "C"]
    # only the broad rule matches
    assert plan_commands([g], "pre_review", ["skills/other/y.py"]) == ["F"]


def test_interleaves_declaration_order_not_apply_grouping():
    fm = gate("specific", apply="first_match", rules=[rule("skills/**", ["S"])])
    ov = gate("crosscut", apply="overlay", rules=[rule("skills/**", ["X", "Y"])])

    # declaration order [fm, ov] -> [S, X, Y]; grouping overlay-first would give
    # [X, Y, S], which the frozen algorithm forbids.
    assert plan_commands([fm, ov], "pre_review", ["skills/a.py"]) == ["S", "X", "Y"]
    # re-declared [ov, fm] -> [X, Y, S] (first occurrence follows declaration).
    assert plan_commands([ov, fm], "pre_review", ["skills/a.py"]) == ["X", "Y", "S"]


def test_global_first_occurrence_dedup_across_gates():
    fm = gate("a", rules=[rule("src/**", ["C", "SHARED"])])
    ov = gate("b", apply="overlay", rules=[rule("src/**", ["SHARED", "D"])])
    assert plan_commands([fm, ov], "pre_review", ["src/x.py"]) == ["C", "SHARED", "D"]


def test_plan_is_path_order_invariant():
    g = gate("t", rules=[
        rule("a/**", ["A"]),
        rule("b/**", ["B"]),
        rule("c/**", ["C"]),
    ])
    paths = ["b/x.py", "a/y.py", "c/z.py"]
    for perm in itertools.permutations(paths):
        assert plan_commands([g], "pre_review", list(perm)) == ["A", "B", "C"]


def test_plan_is_idempotent():
    fm = gate("specific", rules=[rule("skills/**", ["S"])])
    ov = gate("cross", apply="overlay", rules=[rule("skills/**", ["F", "C"])])
    first = plan_commands([fm, ov], "pre_review", ["skills/x.py"])
    second = plan_commands([fm, ov], "pre_review", ["skills/x.py"])
    assert first == second == ["S", "F", "C"]


# ---------------------------------------------------------------------------
# blocking semantics
# ---------------------------------------------------------------------------

def test_blocking_true_failure_blocks():
    g = gate("t", rules=[rule("src/**", ["sh -c 'exit 1'"])])
    res = run_stage([g], "pre_review", ["src/x.py"], run_command=lambda cmd: 1)
    assert res.exit_code() == 1
    assert res.blocked() is True
    assert res.gates[0].decision == DECISION_FAIL
    assert res.gates[0].blocking is True


def test_blocking_false_failure_recorded_but_not_blocking():
    g = gate("t", blocking=False, rules=[rule("src/**", ["sh -c 'exit 1'"])])
    res = run_stage([g], "pre_review", ["src/x.py"], run_command=lambda cmd: 1)
    assert res.exit_code() == 0
    assert res.blocked() is False
    assert res.gates[0].decision == DECISION_FAIL
    assert res.gates[0].blocking is False


@pytest.mark.parametrize("rc", [4, 5])
def test_pytest_rc4_5_skip(rc):
    g = gate("t", rules=[rule("src/**", ["pytest -q whatever"])])
    res = run_stage([g], "pre_review", ["src/x.py"], run_command=lambda cmd: rc)
    assert res.exit_code() == 0
    assert res.gates[0].decision == DECISION_PASS
    assert "skip" in res.gates[0].detail


@pytest.mark.parametrize("rc", [4, 5])
def test_non_pytest_rc4_5_fatal(rc):
    g = gate("t", rules=[rule("src/**", ["npm run build"])])
    res = run_stage([g], "pre_review", ["src/x.py"], run_command=lambda cmd: rc)
    assert res.exit_code() == 1
    assert res.gates[0].decision == DECISION_FAIL


# ---------------------------------------------------------------------------
# unmatched pass vs empty-rules fail-closed
# ---------------------------------------------------------------------------

def test_unmatched_pass():
    g = gate("t", rules=[rule("src/**", ["run"])])
    res = run_stage([g], "pre_review", ["docs/x.md"], run_command=lambda cmd: 0)
    assert res.exit_code() == 0
    assert res.gates[0].decision == DECISION_PASS
    assert "unmatched" in res.gates[0].detail


def test_command_gate_empty_rules_fails_closed():
    g = gate("t", rules=[])
    res = run_stage([g], "pre_review", ["docs/x.md"], run_command=lambda cmd: 0)
    assert res.exit_code() == 1
    assert res.gates[0].decision == DECISION_ERROR
    assert "no rules" in res.gates[0].detail


# ---------------------------------------------------------------------------
# qoder_judge + unsupported kind + executor normalization
# ---------------------------------------------------------------------------

def test_qoder_judge_enabled_fails_closed_unsupported():
    g = gate("judge", kind="qoder_judge", stage="pre_review")
    res = run_stage([g], "pre_review", ["x"], run_command=lambda cmd: 0)
    assert res.exit_code() == 1
    assert res.gates[0].decision == DECISION_ERROR
    assert "unsupported-kind" in res.gates[0].detail
    assert res.gates[0].blocking is True


def test_qoder_judge_disabled_is_skipped():
    g = gate("judge", kind="qoder_judge", stage="pre_review", enabled=False)
    res = run_stage([g], "pre_review", ["x"], run_command=lambda cmd: 0)
    assert res.gates == []
    assert res.exit_code() == 0


def test_findings_normalizes_to_fail():
    def qs_executor(g, ctx):
        return GateResult(
            name="qs", kind="qoder_security", stage="merge",
            decision="FINDINGS", blocking=True,
            detail="findings: high: injection (qoder-level detail preserved)",
        )

    g = gate("qs", kind="qoder_security", stage="merge")
    res = run_stage([g], "merge", [], executors={"qoder_security": qs_executor})
    assert res.gates[0].decision == DECISION_FAIL
    assert "high" in res.gates[0].detail
    assert res.exit_code() == 1


def test_normalize_decision_mapping():
    assert normalize_decision("FINDINGS") == DECISION_FAIL
    assert normalize_decision("PASS") == DECISION_PASS
    assert normalize_decision("FAIL") == DECISION_FAIL
    assert normalize_decision("ERROR") == DECISION_ERROR
    assert normalize_decision("BOGUS") == DECISION_ERROR


def test_default_codex_executor_fails_closed_unwired():
    g = gate("codex_signoff", kind="codex", stage="merge")
    res = run_stage([g], "merge", [], run_command=lambda cmd: 0)
    assert res.exit_code() == 1
    assert res.gates[0].decision == DECISION_ERROR
    assert "executor_not_wired" in res.gates[0].detail


# ---------------------------------------------------------------------------
# stage ordering + filtering
# ---------------------------------------------------------------------------

def test_merge_stage_stops_after_first_blocking_failure():
    called = []

    def codex_exec(g, ctx):
        called.append("codex")
        return GateResult(
            name="codex", kind="codex", stage="merge",
            decision=DECISION_FAIL, blocking=True, detail="rework",
        )

    def qs_exec(g, ctx):
        called.append("qoder_security")
        return GateResult(
            name="qs", kind="qoder_security", stage="merge",
            decision=DECISION_PASS, blocking=True, detail="ok",
        )

    gates = [
        gate("codex_signoff", kind="codex", stage="merge"),
        gate("qoder_security", kind="qoder_security", stage="merge"),
    ]
    res = run_stage(
        gates, "merge", [],
        executors={"codex": codex_exec, "qoder_security": qs_exec},
    )
    assert called == ["codex"]
    assert res.exit_code() == 1
    assert [g.name for g in res.gates] == ["codex_signoff"]


def test_stage_filtering_runs_only_requested_stage():
    called = []

    def qs_exec(g, ctx):
        called.append("qoder_security")
        return GateResult(
            name="qs", kind="qoder_security", stage="merge",
            decision=DECISION_PASS, blocking=True, detail="ok",
        )

    pre = gate("pre", rules=[rule("src/**", ["A"])])
    merge = gate("merge_gate", kind="qoder_security", stage="merge")
    res = run_stage(
        [pre, merge], "pre_review", ["src/x.py"],
        run_command=lambda cmd: 0,
        executors={"qoder_security": qs_exec},
    )
    assert called == []
    assert [g.name for g in res.gates] == ["pre"]
    assert res.exit_code() == 0


# ---------------------------------------------------------------------------
# result model shape + status write
# ---------------------------------------------------------------------------

def test_result_model_shape():
    g = gate("t", rules=[rule("src/**", ["run"])])
    res = run_stage([g], "pre_review", ["src/x.py"], run_command=lambda cmd: 0)
    d = res.to_dict()
    assert set(d) == {"stage", "blocked", "gates"}
    gate_dict = d["gates"][0]
    assert set(gate_dict) == {
        "name", "kind", "stage", "decision", "blocking", "detail",
    }
    assert gate_dict["decision"] == DECISION_PASS


def test_write_gates_to_status(tmp_path):
    g = gate("t", rules=[rule("src/**", ["run"])])
    res = run_stage([g], "pre_review", ["src/x.py"], run_command=lambda cmd: 0)
    status = tmp_path / "s.json"
    status.write_text(json.dumps({"work_package_id": "WP-02"}), encoding="utf-8")
    write_gates_to_status(status, res)
    data = json.loads(status.read_text(encoding="utf-8"))
    assert data["work_package_id"] == "WP-02"
    assert data["gates"][0]["decision"] == DECISION_PASS

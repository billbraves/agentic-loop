"""WP-02 execution-level global first-occurrence de-duplication.

The §3.4 frozen algorithm guarantees a shared command string is executed exactly
once across the whole stage, attributed to the *first* gate (declaration order)
that plans it. ``plan_commands`` already models this for the pure planner; these
tests pin the *execution path* (``run_stage`` -> ``_run_command_gate``) so the
runner's actual executed command sequence matches the planner element-for-element.

A command shared by two same-stage command gates must run exactly once, and a
gate whose commands were all already run by an earlier gate must still produce a
``PASS`` result with the first-occurrence-dedup detail (never re-running and
never double-blaming the later gate).
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.runner.gate_runner import (  # noqa: E402
    DECISION_FAIL,
    DECISION_PASS,
    plan_commands,
    run_stage,
)


def _gate(name, apply="first_match", *, blocking=True, rules=None):
    d = {
        "name": name,
        "kind": "command",
        "stage": "pre_review",
        "apply": apply,
        "blocking": blocking,
        "enabled": True,
    }
    if rules is not None:
        d["rule"] = rules
    return d


def _rule(match, run):
    return {"match": match, "run": run}


def _recorder(executed, rc_by_cmd=None):
    """A run_command that records every command it is asked to execute."""

    def run(cmd):
        executed.append(cmd)
        if rc_by_cmd:
            return rc_by_cmd.get(cmd, 0)
        return 0

    return run


# ---------------------------------------------------------------------------
# 1. a shared command runs exactly once across two same-stage command gates
# ---------------------------------------------------------------------------

def test_shared_command_runs_once_across_gates():
    fm = _gate("a", rules=[_rule("src/**", ["C", "SHARED"])])
    ov = _gate("b", apply="overlay", rules=[_rule("src/**", ["SHARED", "D"])])
    changed = ["src/x.py"]

    executed: list[str] = []
    res = run_stage([fm, ov], "pre_review", changed, run_command=_recorder(executed))

    assert executed == ["C", "SHARED", "D"]
    assert [g.name for g in res.gates] == ["a", "b"]
    assert res.gates[0].decision == DECISION_PASS
    assert res.gates[1].decision == DECISION_PASS
    assert res.exit_code() == 0


def test_gate_whose_commands_all_already_executed_passes_with_dedup_detail():
    fm = _gate("a", rules=[_rule("src/**", ["C", "SHARED"])])
    ov = _gate("b", apply="overlay", rules=[_rule("src/**", ["SHARED", "C"])])
    changed = ["src/x.py"]

    executed: list[str] = []
    res = run_stage([fm, ov], "pre_review", changed, run_command=_recorder(executed))

    assert executed == ["C", "SHARED"]
    assert res.gates[1].decision == DECISION_PASS
    assert "already executed" in res.gates[1].detail


# ---------------------------------------------------------------------------
# 2. run_stage execution sequence == plan_commands sequence
# ---------------------------------------------------------------------------

def test_execution_sequence_matches_plan_commands():
    gates = [
        _gate("a", rules=[_rule("src/**", ["A", "B"])]),
        _gate("b", apply="overlay", rules=[_rule("src/**", ["B", "C"])]),
        _gate("c", rules=[_rule("src/**", ["D", "A"])]),
    ]
    changed = ["src/x.py"]

    executed: list[str] = []
    res = run_stage(gates, "pre_review", changed, run_command=_recorder(executed))

    assert executed == plan_commands(gates, "pre_review", changed)
    assert executed == ["A", "B", "C", "D"]
    assert [g.decision for g in res.gates] == [DECISION_PASS] * 3
    assert res.exit_code() == 0


def test_execution_sequence_matches_plan_commands_declaration_order():
    # Reversing declaration order must reverse the attribution of shared commands
    # in BOTH the planner and the executor.
    fm = _gate("specific", rules=[_rule("skills/**", ["S"])])
    ov = _gate("crosscut", apply="overlay", rules=[_rule("skills/**", ["X", "Y"])])

    for gates in ([fm, ov], [ov, fm]):
        executed: list[str] = []
        res = run_stage(
            gates, "pre_review", ["skills/a.py"], run_command=_recorder(executed)
        )
        assert executed == plan_commands(gates, "pre_review", ["skills/a.py"])
        assert [g.decision for g in res.gates] == [DECISION_PASS] * 2


# ---------------------------------------------------------------------------
# 3. first-occurrence gate fails; later gate must not re-run the shared command
# ---------------------------------------------------------------------------

def test_first_occurrence_failure_not_reblamed_in_later_gate():
    fm = _gate(
        "a", blocking=False, rules=[_rule("src/**", ["SHARED"])],
    )
    ov = _gate(
        "b", apply="overlay", rules=[_rule("src/**", ["SHARED", "D"])],
    )
    changed = ["src/x.py"]

    executed: list[str] = []
    res = run_stage(
        [fm, ov], "pre_review", changed,
        run_command=_recorder(executed, rc_by_cmd={"SHARED": 1}),
    )

    # SHARED ran exactly once (by the first gate), D ran once (by the later gate).
    assert executed == ["SHARED", "D"]
    assert res.gates[0].decision == DECISION_FAIL
    assert res.gates[0].blocking is False
    # The later gate is only accountable for D; SHARED is attributed to fm.
    assert res.gates[1].decision == DECISION_PASS
    # fm is non-blocking, so the stage still exits 0.
    assert res.exit_code() == 0

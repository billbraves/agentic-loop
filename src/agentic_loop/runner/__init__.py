"""agentic_loop.runner — unified ``[[gate]]`` execution and scheduling.

This subpackage is the gate *runner* (WP-02): it reads the normalized
``[[gate]]`` array produced by :mod:`agentic_loop.resolve_paths`, filters by
``stage``, executes command-kind gates with the exact command/exit-code
semantics of ``quality-gate.sh``, applies the §3.4 frozen ordering algorithm
for ``first_match``/``overlay`` mixing, and normalizes every gate's outcome
into the generic ``gates[]`` result model.

The runner deliberately does NOT implement the qoder security engine (WP-03)
nor the codex merge engine; those non-command kinds are wired through injectable
executors so this package stays decoupled from WP-03 landing.
"""
from __future__ import annotations

from agentic_loop.runner.gate_runner import (
    DECISION_ERROR,
    DECISION_FAIL,
    DECISION_PASS,
    QODER_FINDINGS,
    GateResult,
    RunContext,
    StageRunResult,
    normalize_decision,
    plan_commands,
    run_stage,
    write_gates_to_status,
)

__all__ = [
    "DECISION_ERROR",
    "DECISION_FAIL",
    "DECISION_PASS",
    "QODER_FINDINGS",
    "GateResult",
    "RunContext",
    "StageRunResult",
    "normalize_decision",
    "plan_commands",
    "run_stage",
    "write_gates_to_status",
]

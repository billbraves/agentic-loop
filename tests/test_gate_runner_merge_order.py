"""WP-02 merge-stage canonical order (brief Required #6).

``run_stage`` must run merge-stage gates in the canonical credit-safe sequence
``codex -> qoder_security -> qoder_judge`` regardless of how the config declares
them, so a blocking failure in an earlier gate never burns credits in a later
one. The re-order is *stable* (same-kind gates keep declaration order) and
applies to the merge stage only: ``pre_review`` keeps its declaration order so
the §3.4 frozen command de-duplication semantics are untouched.

These tests use injectable executors that record the call order, so no real
codex/qoder engine (WP-03) or ``.agentic/config.toml`` is involved.
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
    GateResult,
    run_stage,
)


def _gate(name, kind, stage="merge", *, blocking=True, enabled=True):
    return {
        "name": name,
        "kind": kind,
        "stage": stage,
        "blocking": blocking,
        "enabled": enabled,
    }


def _exec(decision, detail="ok"):
    """Return an executor that returns ``decision`` and records its gate name."""

    def fn(gate, ctx):
        return GateResult(
            name=gate["name"],
            kind=gate["kind"],
            stage=gate["stage"],
            decision=decision,
            blocking=True,
            detail=detail,
        )

    return fn


def test_merge_canonical_order_codex_before_qoder_security():
    called: list[str] = []
    gates = [
        _gate("qoder_security", "qoder_security"),  # declared FIRST (bad order)
        _gate("codex_signoff", "codex"),            # declared SECOND
    ]
    executors = {
        "codex": _exec(DECISION_PASS),
        "qoder_security": _exec(DECISION_PASS),
    }
    # wrap the executors so they also record call order
    def record(kind):
        def fn(gate, ctx):
            called.append(gate["name"])
            return executors[kind](gate, ctx)
        return fn

    res = run_stage(
        gates, "merge", [],
        executors={"codex": record("codex"), "qoder_security": record("qoder_security")},
    )
    assert called == ["codex_signoff", "qoder_security"]
    assert [g.name for g in res.gates] == ["codex_signoff", "qoder_security"]
    assert res.exit_code() == 0


def test_merge_codex_blocking_fail_skips_qoder_security():
    called: list[str] = []

    def codex_exec(gate, ctx):
        called.append("codex")
        return GateResult(
            name="codex", kind="codex", stage="merge",
            decision=DECISION_FAIL, blocking=True, detail="rework",
        )

    def qs_exec(gate, ctx):
        called.append("qoder_security")
        return GateResult(
            name="qs", kind="qoder_security", stage="merge",
            decision=DECISION_PASS, blocking=True, detail="ok",
        )

    gates = [
        _gate("qoder_security", "qoder_security"),  # declared FIRST (bad order)
        _gate("codex_signoff", "codex"),
    ]
    res = run_stage(
        gates, "merge", [],
        executors={"codex": codex_exec, "qoder_security": qs_exec},
    )
    # codex runs first (canonical order) and blocks, so qoder_security never runs.
    assert called == ["codex"]
    assert res.exit_code() == 1
    assert [g.name for g in res.gates] == ["codex_signoff"]


def test_merge_same_kind_preserves_declaration_order():
    called: list[str] = []
    gates = [
        _gate("codex_a", "codex"),
        _gate("codex_b", "codex"),
    ]
    executors = {
        "codex": lambda gate, ctx: (
            called.append(gate["name"])
            or GateResult(
                name=gate["name"], kind="codex", stage="merge",
                decision=DECISION_PASS, blocking=True, detail="ok",
            )
        ),
    }
    res = run_stage(gates, "merge", [], executors=executors)
    assert called == ["codex_a", "codex_b"]
    assert [g.name for g in res.gates] == ["codex_a", "codex_b"]
    assert res.exit_code() == 0


def test_merge_unlisted_kind_sorts_after_listed_kinds():
    called: list[str] = []
    gates = [
        {
            "name": "cmd",
            "kind": "command",
            "stage": "merge",
            "blocking": True,
            "enabled": True,
            "rule": [{"match": "src/**", "run": ["true"]}],
        },
        _gate("codex_signoff", "codex"),
    ]
    executors = {
        "codex": lambda gate, ctx: (
            called.append(gate["name"])
            or GateResult(
                name=gate["name"], kind="codex", stage="merge",
                decision=DECISION_PASS, blocking=True, detail="ok",
            )
        ),
    }
    res = run_stage(
        gates, "merge", ["src/x.py"],
        executors=executors,
        run_command=lambda cmd: 0,
    )
    assert called == ["codex_signoff"]
    assert [g.name for g in res.gates] == ["codex_signoff", "cmd"]
    assert res.exit_code() == 0


def test_pre_review_keeps_declaration_order_not_reordered():
    """pre_review must NOT be re-ordered even if kinds suggest a merge order."""
    called: list[str] = []
    gates = [
        _gate("qs_first", "qoder_security", stage="pre_review"),
        _gate("codex_second", "codex", stage="pre_review"),
    ]
    executors = {
        "qoder_security": lambda gate, ctx: (
            called.append(gate["name"])
            or GateResult(
                name=gate["name"], kind="qoder_security", stage="pre_review",
                decision=DECISION_PASS, blocking=True, detail="ok",
            )
        ),
        "codex": lambda gate, ctx: (
            called.append(gate["name"])
            or GateResult(
                name=gate["name"], kind="codex", stage="pre_review",
                decision=DECISION_PASS, blocking=True, detail="ok",
            )
        ),
    }
    res = run_stage(gates, "pre_review", [], executors=executors)
    assert called == ["qs_first", "codex_second"]
    assert [g.name for g in res.gates] == ["qs_first", "codex_second"]
    assert res.exit_code() == 0

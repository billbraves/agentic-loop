#!/usr/bin/env python3
"""Compact gate-report layer (WP-01).

Converts a structured gate-result set into a single summary line plus an
on-demand detail file, so N-way parallel lanes can read gate output at a
fraction of the token cost of the old line-by-line plan + raw stdout.

This module is a *pure reporting* layer: it never changes a judgment. It only
reads a structured result (the ``gates[]`` shape produced by
``runner.gate_runner.GateResult.to_dict()``) and derives two things from it:

- the **verdict** (blocked / exit code), computed byte-for-byte against the
  runner's ``StageRunResult.blocked()`` / ``exit_code()`` semantics; and
- the **rendering** (summary + detail file), which is the only part this WP
  changes.

The three design principles are borrowed (not copied) from lobehub's
``check/report.ts``: compact and colorless for agents, summary line mentions
only checks that actually ran, and large content (the full plan and any failure
detail) is written to a file whose path is named on the summary line.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence

# Generic gate decisions (runner.gate_runner.DECISIONS). qoder_security's
# specialized ``FINDINGS`` is normalized to FAIL upstream, so the report only
# ever sees these three.
PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"
_DECISIONS = (PASS, FAIL, ERROR)


def normalize_decision(raw: Any) -> str:
    """Map an executor decision onto PASS/FAIL/ERROR; unknown -> ERROR.

    Mirrors ``runner.gate_runner.normalize_decision`` (which also maps the
    qoder ``FINDINGS`` sub-state to FAIL) so the report can never *upgrade* a
    malformed decision into PASS. Anything outside the closed enum fails closed.
    """
    if raw in _DECISIONS:
        return raw
    return ERROR


def is_blocked(gates: Sequence[Dict[str, Any]]) -> bool:
    """True when any *blocking* gate did not PASS (fail-closed).

    This is the exact predicate ``runner.gate_runner.StageRunResult.blocked()``
    uses: a non-blocking FAIL records but never blocks. The report must never
    diverge from it, otherwise a compact output would silently change the merge
    verdict — the one thing this WP is forbidden to touch.
    """
    return any(
        bool(g.get("blocking")) and normalize_decision(g.get("decision")) != PASS
        for g in gates
    )


def exit_code(gates: Sequence[Dict[str, Any]]) -> int:
    """Exit code identical to ``StageRunResult.exit_code()``: 1 if blocked else 0."""
    return 1 if is_blocked(gates) else 0


def _executed(gates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The checks that actually ran: every gate present in ``gates[]``.

    The runner already drops disabled gates and only appends an entry per
    executed gate, so "presence in the list" == "executed". The report never
    invents a check that did not run; it only counts what it was given.
    """
    return list(gates)


def _counts(gates: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """Per-decision counts over executed gates (closed enum, unknown -> ERROR)."""
    counts = {PASS: 0, FAIL: 0, ERROR: 0}
    for g in gates:
        counts[normalize_decision(g.get("decision"))] += 1
    return counts


def summary_line(
    gates: Sequence[Dict[str, Any]],
    *,
    detail_path: Optional[Path] = None,
) -> str:
    """One compact, colorless summary line for a gate run.

    Success: only counts, no per-gate detail — e.g. ``✓ 3 gates passed``.
    Failure: a brief locator (cheapest failing gate's detail carries command /
    exit code) plus the detail-file path — e.g.
    ``✗ 2/3 gates passed · pytest: command failed (exit 1): … · details: <path>``.

    ``detail_path``, when given, is appended so the consumer knows where the
    full plan and failure detail live without having to read them inline.
    """
    counts = _counts(gates)
    total = len(_executed(gates))
    passed = counts[PASS]

    if not is_blocked(gates):
        line = f"✓ {total} gate{'s' if total != 1 else ''} passed"
        if counts[ERROR]:
            line += f" · {counts[ERROR]} error"
        if counts[FAIL]:
            line += f" · {counts[FAIL]} non-blocking failure"
    else:
        line = f"✗ {passed}/{total} gate{'s' if total != 1 else ''} passed"
        locator = _failure_locator(gates)
        if locator:
            line += f" · {locator}"
        else:
            line += " · failed"

    if detail_path is not None:
        line += f" · details: {detail_path}"
    return line


def _failure_locator(gates: Sequence[Dict[str, Any]]) -> str:
    """The cheapest failing gate's ``name`` + first line of ``detail``.

    ``detail`` already carries the actionable surface (``command failed (exit
    N): <cmd>`` for command gates; ``unsupported-kind`` / ``executor_not_wired``
    / security findings otherwise), so name + its first line is enough to locate
    a failure without dumping the full plan inline.
    """
    for g in gates:
        if normalize_decision(g.get("decision")) != PASS:
            name = str(g.get("name") or "<unnamed>")
            detail = (str(g.get("detail") or "")).splitlines()
            first = detail[0].strip() if detail and detail[0].strip() else ""
            if first:
                return f"{name}: {first}"
            return name
    return ""


def detail_text(gates: Sequence[Dict[str, Any]]) -> str:
    """The full plan + per-gate results (the "large content" this WP offloads).

    Includes every executed gate with its decision and full ``detail``, so a
    human (or an agent that *does* need the detail) can reconstruct the run
    from the file alone. On a clean run this is still the complete plan — the
    summary line never carries per-gate lines, only a pointer here.
    """
    if not gates:
        return ""
    lines: List[str] = []
    for g in gates:
        name = str(g.get("name") or "<unnamed>")
        kind = str(g.get("kind") or "")
        stage = str(g.get("stage") or "")
        decision = normalize_decision(g.get("decision"))
        blocking = "blocking" if g.get("blocking") else "non-blocking"
        header = f"[{decision}] {name}"
        if kind:
            header += f" (kind={kind}"
            header += f", stage={stage})" if stage else ")"
        header += f" {blocking}"
        lines.append(header)
        detail = str(g.get("detail") or "").strip()
        if detail:
            lines.extend("  " + ln for ln in detail.splitlines())
        else:
            lines.append("  <no detail>")
    return "\n".join(lines) + "\n"


def render_report(
    gates: Sequence[Dict[str, Any]],
    *,
    detail_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return ``{summary, detail, blocked, exit_code}`` for a gate run.

    ``summary`` is the one-line form; ``detail`` is the full plan text (intended
    for a file, not the terminal); ``blocked`` / ``exit_code`` are the preserved
    verdict. The caller wires rendering to stdout/file as it sees fit — this
    module never prints, so it is trivially testable and side-effect free.
    """
    return {
        "summary": summary_line(gates, detail_path=detail_path),
        "detail": detail_text(gates),
        "blocked": is_blocked(gates),
        "exit_code": exit_code(gates),
    }


def write_report(
    gates: Sequence[Dict[str, Any]],
    detail_path: Path,
) -> str:
    """Write the full plan + failure detail to ``detail_path`` and return the
    summary line (which names that path). The on-disk file is plain text so it
    stays agent- and grep-friendly; JSON is avoided to keep it colorless."""
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(detail_text(gates), encoding="utf-8")
    return summary_line(gates, detail_path=detail_path)

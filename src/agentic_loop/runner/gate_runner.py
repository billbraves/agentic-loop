#!/usr/bin/env python3
"""Unified ``[[gate]]`` runner + overlay scheduling + generic result model.

WP-02 implements the *execution and scheduling* layer over the WP-01 reader.
It consumes the normalized ``[[gate]]`` array (``resolve_paths.get_gates()``),
filters by ``stage``, and runs each gate in declaration order:

- ``kind=command`` gates are executed with the exact command/exit-code
  semantics of ``quality-gate.sh`` (pytest rc 4/5 = skip, any other non-zero
  from a non-pytest command = fatal), preserving the §3.4 frozen ordering
  algorithm for ``first_match``/``overlay`` mixing and global first-occurrence
  de-duplication.
- ``kind=qoder_judge`` is a reserved placeholder: any *enabled* qoder_judge
  gate is fail-closed with ``unsupported-kind`` (§6), never silently skipped or
  passed.
- ``kind=codex`` / ``kind=qoder_security`` are wired through injectable
  executors. WP-03 supplies the real qoder security engine as
  ``agentic_loop.gate.qoder_security``; until then the default executor
  fail-closes with ``executor_not_wired`` so an unimplemented executor can never
  read as PASS.

Every executed gate is normalized into the generic result model
``{name, kind, stage, decision(PASS/FAIL/ERROR), blocking, detail}`` and the
runner summarizes them as ``gates[]``. The qoder-specific ``FINDINGS`` sub-state
is mapped to generic ``FAIL`` (the qoder gate keeps its fine-grained findings in
``detail``, while ``gates[].decision`` is normalized — spec §3.3 enum note), so
blocking is judged on exactly one enum.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agentic_loop.resolve_paths import get_gates
from agentic_loop.resolve_paths import main_repo

DECISION_PASS = "PASS"
DECISION_FAIL = "FAIL"
DECISION_ERROR = "ERROR"
DECISIONS = (DECISION_PASS, DECISION_FAIL, DECISION_ERROR)

# qoder_security's specialized decision: high/medium findings cause a blocking
# failure. It is a sub-state of generic FAIL, not a fourth enum member.
QODER_FINDINGS = "FINDINGS"

VALID_KINDS = ("command", "codex", "qoder_security", "qoder_judge")

RunCommand = Callable[[str], int]
Executor = Callable[[dict[str, Any], "RunContext"], "GateResult"]


@dataclass
class RunContext:
    """Read-only execution context handed to injectable executors."""

    changed_paths: list[str]
    repo: Path | None = None


@dataclass
class GateResult:
    """Generic per-gate outcome (spec §3.3 result model)."""

    name: str
    kind: str
    stage: str
    decision: str
    blocking: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "stage": self.stage,
            "decision": self.decision,
            "blocking": self.blocking,
            "detail": self.detail,
        }


@dataclass
class StageRunResult:
    """Runner summary for one ``stage``: the ``gates[]`` array plus blocked."""

    stage: str
    gates: list[GateResult]

    def blocked(self) -> bool:
        """True when any *blocking* gate did not PASS (fail-closed)."""
        return any(g.blocking and g.decision != DECISION_PASS for g in self.gates)

    def exit_code(self) -> int:
        return 1 if self.blocked() else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "blocked": self.blocked(),
            "gates": [g.to_dict() for g in self.gates],
        }


# ---------------------------------------------------------------------------
# §3.4 frozen ordering algorithm (pure, deterministic)
# ---------------------------------------------------------------------------


def _prefix(match: str) -> str:
    """Mirror ``quality-gate.sh``'s rule-prefix normalization."""
    m = match.strip()
    for suffix in ("/**", "/*"):
        if m.endswith(suffix):
            return m[: -len(suffix)]
    return m


def _matches(path: str, match: str) -> bool:
    """Prefix predicate byte-for-byte aligned with ``quality-gate.sh``."""
    prefix = _prefix(match).rstrip("/")
    if not prefix:
        return True
    return path == prefix or path.startswith(prefix + "/")


def _select_rules(
    rules: Sequence[dict[str, Any]],
    changed_paths: Sequence[str],
    apply: str,
) -> list[bool]:
    """Select rules for one command gate per §3.4 step ②.

    ``first_match``: each changed path contributes only the FIRST rule it
    matches (declaration order = precedence). ``overlay``: every rule matching
    at least one changed path contributes. The returned mask is always in rule
    declaration order.
    """
    selected = [False] * len(rules)
    if apply == "overlay":
        for idx, rule in enumerate(rules):
            match = str(rule.get("match", ""))
            if any(_matches(path, match) for path in changed_paths):
                selected[idx] = True
    else:  # first_match (default)
        for path in changed_paths:
            for idx, rule in enumerate(rules):
                if _matches(path, str(rule.get("match", ""))):
                    selected[idx] = True
                    break
    return selected


def _dedup(commands: Sequence[str]) -> list[str]:
    """Global first-occurrence de-duplication (quality-gate.sh parity)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for cmd in commands:
        if cmd not in seen:
            seen.add(cmd)
            ordered.append(cmd)
    return ordered


def plan_commands(
    gates: Sequence[dict[str, Any]],
    stage: str,
    changed_paths: Sequence[str],
) -> list[str]:
    """Return the ordered, de-duplicated command plan for a stage.

    Frozen §3.4 algorithm:

    1. walk the stage's command-kind gates in *declaration order*
       (``first_match`` and ``overlay`` are mixed — NOT re-sorted by apply);
    2. per gate, ``first_match`` keeps the first rule each changed path hits,
       ``overlay`` keeps every matching rule;
    3. append commands in that traversal order, then de-duplicate by first
       occurrence of the command string.

    The result is a deterministic function of the declaration order.
    """
    candidates: list[str] = []
    for gate in gates:
        if gate.get("kind") != "command" or gate.get("stage") != stage:
            continue
        rules = gate.get("rule") or []
        if not isinstance(rules, list):
            continue
        selected = _select_rules(
            rules, changed_paths, gate.get("apply", "first_match")
        )
        for idx in range(len(rules)):
            if not selected[idx]:
                continue
            for cmd in rules[idx].get("run", []) or []:
                candidates.append(cmd)
    return _dedup(candidates)


# ---------------------------------------------------------------------------
# Executors (injectable; non-command kinds are placeholders in this WP)
# ---------------------------------------------------------------------------


def _codex_wiring(gate: dict[str, Any], ctx: RunContext) -> GateResult:
    """Codex merge engine is orchestrated outside this runner in this WP."""
    return GateResult(
        name=gate.get("name", "codex"),
        kind="codex",
        stage=gate.get("stage", "merge"),
        decision=DECISION_ERROR,
        blocking=bool(gate.get("blocking", True)),
        detail="executor_not_wired: codex executor must be injected by the caller",
    )


def _qoder_security_wiring(gate: dict[str, Any], ctx: RunContext) -> GateResult:
    """Deferred-import the WP-03 engine; fail-closed until it lands.

    WP-03 provides ``agentic_loop.gate.qoder_security.run``. The deferred import
    keeps this runner decoupled from WP-03: when the engine is absent (as in this
    WP), the gate returns ERROR rather than a fabricated PASS.
    """
    try:
        from agentic_loop.gate.qoder_security import run as qoder_run  # type: ignore
    except ImportError:
        return GateResult(
            name=gate.get("name", "qoder_security"),
            kind="qoder_security",
            stage=gate.get("stage", "merge"),
            decision=DECISION_ERROR,
            blocking=bool(gate.get("blocking", True)),
            detail=(
                "executor_not_wired: qoder_security engine not available "
                "(WP-03 pending)"
            ),
        )
    return qoder_run(gate, ctx)  # type: ignore


def _default_executor(kind: str) -> Executor:
    if kind == "qoder_security":
        return _qoder_security_wiring
    if kind == "codex":
        return _codex_wiring
    raise KeyError(kind)


def normalize_decision(raw: str) -> str:
    """Map an executor decision onto the generic PASS/FAIL/ERROR enum.

    qoder_security's ``FINDINGS`` is a specialized sub-state of FAIL: the qoder
    gate keeps its fine-grained findings in ``detail`` while ``gates[].decision``
    normalizes to FAIL (§3.3 enum note). Unknown values fail-closed to ERROR so
    a malformed executor can never read as PASS.
    """
    if raw == QODER_FINDINGS:
        return DECISION_FAIL
    if raw in DECISIONS:
        return raw
    return DECISION_ERROR


def _default_run_command(cmd: str) -> int:
    return subprocess.run(["bash", "-c", cmd]).returncode


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _run_command_gate(
    gate: dict[str, Any],
    ctx: RunContext,
    run_command: RunCommand,
    executed: set[str],
) -> GateResult:
    name = gate.get("name") or "command"
    stage = gate.get("stage") or ""
    blocking = bool(gate.get("blocking", True))
    rules = gate.get("rule") or []
    if not isinstance(rules, list):
        rules = []

    if not rules:
        # §3.3/§10.1: a command gate that defines no rules must fail-closed,
        # never silently PASS on an undefined plan.
        return GateResult(
            name=name,
            kind="command",
            stage=stage,
            decision=DECISION_ERROR,
            blocking=blocking,
            detail="no rules defined (fail-closed)",
        )

    plan = plan_commands([gate], stage, ctx.changed_paths)
    if not plan:
        # unmatched pass: rules exist but none matched the changed set.
        return GateResult(
            name=name,
            kind="command",
            stage=stage,
            decision=DECISION_PASS,
            blocking=blocking,
            detail="no rule matched changed paths (unmatched pass)",
        )

    # §3.4 step ③ global first-occurrence de-dup is enforced at EXECUTION time:
    # this gate only runs commands it plans that an earlier gate has not already
    # run. The command's outcome belongs to its first-occurring gate; later gates
    # skip it rather than re-running or re-blaming it.
    new_commands = [cmd for cmd in plan if cmd not in executed]
    if not new_commands:
        return GateResult(
            name=name,
            kind="command",
            stage=stage,
            decision=DECISION_PASS,
            blocking=blocking,
            detail=(
                "all commands already executed by an earlier gate "
                "(first-occurrence dedup)"
            ),
        )

    skipped = 0
    for cmd in new_commands:
        executed.add(cmd)
        rc = run_command(cmd)
        if rc == 0:
            continue
        # pytest rc 4 (no target) / 5 (no tests) = skip, scoped to pytest only —
        # mirrors the old run_pytest_dir semantics verbatim.
        if "pytest" in cmd and rc in (4, 5):
            skipped += 1
            continue
        return GateResult(
            name=name,
            kind="command",
            stage=stage,
            decision=DECISION_FAIL,
            blocking=blocking,
            detail=f"command failed (exit {rc}): {cmd}",
        )

    detail = f"ran {len(new_commands)} command(s)"
    if skipped:
        detail += f"; skipped {skipped} (no tests/target)"
    return GateResult(
        name=name,
        kind="command",
        stage=stage,
        decision=DECISION_PASS,
        blocking=blocking,
        detail=detail,
    )


def _run_gate(
    gate: dict[str, Any],
    ctx: RunContext,
    executors: Mapping[str, Executor],
    run_command: RunCommand,
    executed: set[str],
) -> GateResult:
    name = gate.get("name") or "<unnamed>"
    kind = gate.get("kind")
    stage = gate.get("stage") or ""
    blocking = bool(gate.get("blocking", True))

    if kind == "command":
        return _run_command_gate(gate, ctx, run_command, executed)

    if kind == "qoder_judge":
        # §6: any enabled qoder_judge gate is fail-closed. The kind is a reserved
        # schema placeholder this iteration; it must never read as PASS.
        return GateResult(
            name=name,
            kind=kind,
            stage=stage,
            decision=DECISION_ERROR,
            blocking=True,
            detail=(
                "unsupported-kind: qoder_judge executor is not implemented "
                "in this iteration"
            ),
        )

    if kind not in ("codex", "qoder_security"):
        return GateResult(
            name=name,
            kind=kind or "<unknown>",
            stage=stage,
            decision=DECISION_ERROR,
            blocking=blocking,
            detail=f"unsupported-kind: {kind!r}",
        )

    executor = executors.get(kind) or _default_executor(kind)
    result = executor(gate, ctx)
    return GateResult(
        name=name,
        kind=kind,
        stage=stage,
        decision=normalize_decision(result.decision),
        blocking=blocking,
        detail=result.detail,
    )


# merge stage canonical order: a blocking failure in an earlier gate must
# never enter (and spend credits on) a later gate (brief Required #6).
_MERGE_STAGE_KIND_ORDER = {"codex": 0, "qoder_security": 1, "qoder_judge": 2}


def _canonical_merge_order(
    gates: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Re-order a merge stage's gates into the canonical credit-safe sequence.

    Required #6: ``codex_signoff`` runs before ``qoder_security`` (and both
    before ``qoder_judge``) regardless of how the config declares them. The sort
    is stable — gates of the same kind keep their declaration order — and kinds
    not listed in ``_MERGE_STAGE_KIND_ORDER`` (e.g. ``command``) sort after the
    listed kinds while preserving their own declaration order.
    """
    def key(index: int) -> tuple[int, int]:
        kind = gates[index].get("kind")
        return (
            _MERGE_STAGE_KIND_ORDER.get(kind, len(_MERGE_STAGE_KIND_ORDER)),
            index,
        )

    return [gates[i] for i in sorted(range(len(gates)), key=key)]


def run_stage(
    gates: Sequence[dict[str, Any]],
    stage: str,
    changed_paths: Sequence[str],
    executors: Mapping[str, Executor] | None = None,
    run_command: RunCommand | None = None,
) -> StageRunResult:
    """Run every enabled gate of ``stage``.

    ``pre_review`` runs in declaration order (the §3.4 frozen command
    de-duplication relies on declaration precedence). ``merge`` is re-ordered
    into the canonical credit-safe sequence (``codex`` before
    ``qoder_security`` before ``qoder_judge``; Required #6), independent of how
    the config declares the gates.

    Fail-closed: the first *blocking* gate whose decision != PASS stops the stage
    (so a failed merge pre-order never enters a later, credit-consuming gate).
    Non-blocking failures are recorded in ``gates[]`` but neither stop the stage
    nor change the exit code.
    """
    resolved_executors: Mapping[str, Executor] = executors or {}
    resolved_run: RunCommand = run_command or _default_run_command
    ctx = RunContext(changed_paths=list(changed_paths))

    # Stage-level first-occurrence set shared by every command gate in this stage.
    executed: set[str] = set()
    results: list[GateResult] = []

    stage_gates: Sequence[dict[str, Any]] = [
        gate for gate in gates if gate.get("stage") == stage
    ]
    if stage == "merge":
        stage_gates = _canonical_merge_order(stage_gates)

    for gate in stage_gates:
        if not bool(gate.get("enabled", True)):
            continue
        result = _run_gate(gate, ctx, resolved_executors, resolved_run, executed)
        results.append(result)
        if result.blocking and result.decision != DECISION_PASS:
            break

    return StageRunResult(stage=stage, gates=results)


def write_gates_to_status(status_file: Path, result: StageRunResult) -> None:
    """Persist ``gates[]`` into a status JSON (schema validation is WP-04's job).

    Reads-modifies-writes the file in place, preserving all other top-level
    fields. This WP only produces the in-memory result model + this write; the
    status schema's ``gates[]`` acceptance is coordinated with WP-04.
    """
    data = json.loads(status_file.read_text(encoding="utf-8"))
    data["gates"] = [g.to_dict() for g in result.gates]
    status_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI (used by scripts/agentic/gate-runner.sh)
# ---------------------------------------------------------------------------


def _read_changed_paths(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic-gate-runner")
    parser.add_argument(
        "--stage", choices=("pre_review", "merge"), default="pre_review"
    )
    parser.add_argument(
        "--paths",
        help="file with changed paths, one per line ('-' or omitted = stdin)",
    )
    parser.add_argument(
        "--status",
        help="optional status.json to receive the normalized gates[] array",
    )
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    repo = main_repo()
    gates = get_gates(repo)

    if args.paths and args.paths != "-":
        changed = _read_changed_paths(Path(args.paths).read_text(encoding="utf-8"))
    else:
        changed = _read_changed_paths(sys.stdin.read())

    result = run_stage(gates, args.stage, changed)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if args.status:
        write_gates_to_status(Path(args.status), result)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

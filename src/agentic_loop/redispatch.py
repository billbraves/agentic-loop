#!/usr/bin/env python3
"""Engine-orchestrated automatic redispatch with triple guards.

This is the P4 generalization of ``scripts/agentic/redispatch.sh``. The bash
script is now a thin shell that execs this module. All safety semantics are
migrated verbatim: resolver-driven root resolution, status validation,
circuit-breaker, probe, heartbeat, continuation prompt, and dispatch.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

# Make ``adapters/`` and ``independence.py`` importable on the bare python3 path.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ImplementResult
from agentic_loop.adapters.kimi import KimiAdapter
from agentic_loop.independence import evaluate
from agentic_loop.resolve_paths import get_roles
from agentic_loop.resolve_paths import iterations_dir
from agentic_loop.resolve_paths import main_repo


def _err(message: str) -> None:
    print(f"REDISPATCH_ERROR: {message}", file=sys.stderr)


def _log(message: str) -> None:
    print(f"REDISPATCH: {message}", file=sys.stderr)


def _run_validator(validator: Path, status_file: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(validator), str(status_file)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise ValueError(err)


def _read_field(validator: Path, status_file: Path, dotted: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(validator), str(status_file), "--field", dotted],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise ValueError(f"field read failed for {dotted}: {err}")
    return proc.stdout.strip()


def _git_output(worktree: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(worktree), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return f"git {' '.join(args)} failed"
    return proc.stdout


def _load_count(data: dict[str, Any]) -> int:
    executor = data.get("executor")
    if not isinstance(executor, dict):
        raise ValueError("executor block missing")
    count = executor.get("redispatch_count")
    if count is None:
        return 0
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(
            f"executor.redispatch_count must be a non-negative integer, got {count!r}"
        )
    return count


class ProbeFailedError(Exception):
    """Raised when no developer adapter passes the probe guard."""


def _resolve_developer(
    roles_config: dict[str, Any] | list[str] | str | None,
    registry: dict[str, Any] | None = None,
    probe: bool = True,
) -> tuple[Adapter, list[str]]:
    """Resolve the developer adapter from config, with optional fallback probing.

    ``registry`` is a mapping from adapter name to a zero-argument factory. It is
    exposed for injection in unit tests (e.g. a stub ``claude`` adapter).
    """
    if registry is None:
        registry = {
            "kimi": lambda: KimiAdapter(kimi_bin=os.environ.get("KIMI_BIN", "kimi")),
        }

    reasons: list[str] = []
    value: Any = None
    if isinstance(roles_config, dict):
        value = roles_config.get("developer")
    else:
        value = roles_config

    candidates: list[str] = []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)

    if not candidates:
        reasons.append("config roles.developer unavailable; falling back to built-in kimi")
        fallback = registry["kimi"]()
        if probe and not fallback.probe():
            reasons.append("built-in kimi probe failed")
            raise ProbeFailedError("; ".join(reasons))
        return fallback, reasons

    for candidate in candidates:
        factory = registry.get(candidate)
        if factory is None:
            reasons.append(f"unknown developer adapter '{candidate}'")
            continue
        adapter = factory()
        if probe:
            if adapter.probe():
                return adapter, reasons
            reasons.append(f"developer adapter '{candidate}' probe failed; falling back")
        else:
            return adapter, reasons

    reasons.append("all configured developer adapters failed probe; falling back to built-in kimi")
    fallback = registry["kimi"]()
    if probe and not fallback.probe():
        reasons.append("built-in kimi probe failed")
        raise ProbeFailedError("; ".join(reasons))
    return fallback, reasons


def _build_prompt(
    worktree: Path,
    log_path: Path | None,
    work_package_id: str,
    state: str,
    review_notes: str,
    remaining_risks: Any,
) -> str:
    porcelain = _git_output(worktree, "status", "--porcelain")
    diffstat = _git_output(worktree, "diff", "--stat")

    if log_path is not None and log_path.is_file():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            log_tail = "\n".join(lines[-40:])
        except OSError:
            log_tail = "tail failed"
    else:
        log_tail = "(log file not available)"

    if state == "BLOCKED":
        risks_text = json.dumps(remaining_risks, ensure_ascii=False) if isinstance(remaining_risks, (list, tuple, dict)) else str(remaining_risks or "(none recorded)")
        reason = f"BLOCKED state; remaining risks: {risks_text}"
    else:
        reason = f"REWORK state; review notes: {review_notes or '(none recorded)'}"

    return f"""# Continuation prompt for {work_package_id}

## Reason for redispatch
{reason}

## Current worktree status
```
{porcelain}
```

## Worktree diff --stat
```
{diffstat}
```

## Recent log tail (last 40 lines)
```
{log_tail}
```

## Hard requirements
- First inspect existing changes in the worktree (do not start from an empty tree).
- Continue the fix from where it was left off.
- Do not restart from scratch.
- Do not re-edit existing fixtures or status files.
"""


def _dispatch(
    adapter: Adapter,
    worktree: Path,
    brief: str,
    prompt: str,
    dry_run: bool,
) -> ImplementResult:
    try:
        return adapter.implement(
            worktree=str(worktree),
            brief=brief,
            prompt=prompt,
            dry_run=dry_run,
        )
    except Exception as exc:
        return ImplementResult(
            dispatched=False,
            exit_code=None,
            output=str(exc),
            command=(),
            dry_run=dry_run,
        )


def _rate_independence(
    reviewer_adapter: Adapter,
    consultant_adapter: Adapter,
    min_independence: str = "strong",
) -> tuple[str, list[str]]:
    """Rate reviewer/consultant independence and tag weak-attested when appropriate."""
    reviewer_id = reviewer_adapter.identity()
    consultant_id = consultant_adapter.identity()
    capabilities = consultant_adapter.capabilities()
    level, reasons = evaluate(
        reviewer_id=reviewer_id,
        consultant_id=consultant_id,
        capabilities=capabilities,
        min_independence=min_independence,
        implementer_id=None,
    )
    if level == "weak" and reviewer_id.tool == consultant_id.tool:
        reasons.append(
            "same adapter tool for reviewer and consultant; "
            "independence is attested not engine-proven"
        )
    return level, reasons


def write_consult_independence(
    status_file: Path,
    level: str,
    reasons: list[str],
    reviewed_by: str = "engine",
    reviewed_at: str | None = None,
) -> None:
    """Persist the engine-rated independence level into ``consult.independence``."""
    if reviewed_at is None:
        reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = json.loads(status_file.read_text(encoding="utf-8"))
    consult = data.get("consult", {})
    if not isinstance(consult, dict):
        consult = {}
    consult["decision"] = consult.get("decision")
    consult["reviewed_by"] = reviewed_by
    consult["reviewed_at"] = reviewed_at
    consult["notes"] = "\n".join(reasons)
    consult["independence"] = level
    data["consult"] = consult
    ts = data.get("timestamps")
    if isinstance(ts, dict):
        ts["updated_at"] = reviewed_at
    status_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def rate_and_write_consult_independence(
    status_file: Path,
    reviewer_adapter: Adapter,
    consultant_adapter: Adapter,
    min_independence: str = "strong",
    reviewed_by: str = "engine",
    reviewed_at: str | None = None,
) -> tuple[str, list[str]]:
    """Engine-side weak-orchestration rating + persistence helper (testable)."""
    level, reasons = _rate_independence(
        reviewer_adapter, consultant_adapter, min_independence
    )
    write_consult_independence(status_file, level, reasons, reviewed_by, reviewed_at)
    return level, reasons


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("REDISPATCH_ERROR: usage: redispatch.py <status.json>", file=sys.stderr)
        return 64

    status_arg = argv[0]

    repo_root = main_repo()
    iterations_dir_path = iterations_dir()
    # Sibling module inside the agentic_loop package (moved in WP-18).
    validator = Path(__file__).resolve().parent / "validate_wp_status.py"
    lock_sh = repo_root / "scripts" / "agentic" / "lock.sh"

    if status_arg.startswith("/"):
        status_file = Path(status_arg)
    else:
        status_file = repo_root / status_arg

    if not status_file.is_file():
        _err(f"status file not found at {status_file}")
        return 2

    try:
        _run_validator(validator, status_file)
    except ValueError as exc:
        _err(f"invalid status file: {exc}")
        return 2

    try:
        iteration_id = _read_field(validator, status_file, "iteration_id")
        work_package_id = _read_field(validator, status_file, "work_package_id")
        worktree_raw = _read_field(validator, status_file, "git.worktree")
        log_path_raw = _read_field(validator, status_file, "executor.log_path")
        state = _read_field(validator, status_file, "state")
        review_notes = _read_field(validator, status_file, "review.notes")
        remaining_risks_raw = _read_field(
            validator, status_file, "evidence.remaining_risks"
        )
    except ValueError as exc:
        _err(f"failed to read status field: {exc}")
        return 2

    if not worktree_raw:
        _err("git.worktree is required")
        return 2

    worktree = Path(worktree_raw)
    if not worktree.is_absolute():
        worktree = repo_root / worktree_raw

    log_path: Path | None = None
    if log_path_raw:
        log_path = Path(log_path_raw)
        if not log_path.is_absolute():
            log_path = repo_root / log_path_raw

    try:
        remaining_risks = json.loads(remaining_risks_raw)
    except Exception:
        remaining_risks = remaining_risks_raw or []

    # Step 3: Guard ③ circuit-breaker (front-most).
    try:
        redispatch_max = int(os.environ.get("REDISPATCH_MAX", "1"))
    except ValueError:
        redispatch_max = 1

    try:
        status_data = json.loads(status_file.read_text(encoding="utf-8"))
        count = _load_count(status_data)
    except Exception as exc:
        _err(f"failed to read status: {exc}")
        return 2

    if count >= redispatch_max:
        print(
            f"REDISPATCH_STOP: circuit-breaker (count={count} >= max={redispatch_max})"
        )
        return 0

    # Step 4: Guard ① probe.
    probe_cmd = os.environ.get("PROBE_CMD")
    adapter: Adapter | None = None
    if probe_cmd is not None:
        print(f"REDISPATCH_PROBE: {probe_cmd}", file=sys.stderr)
        proc = subprocess.run(
            ["bash", "-c", probe_cmd],
            capture_output=True,
            text=True,
        )
        probe_out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            print(
                "REDISPATCH_STOP: probe failed (non-zero exit) — 不重派,查根因"
            )
            print(f"  probe output: {probe_out}", file=sys.stderr)
            return 0
        if "PROBE_OK" not in probe_out:
            print(
                "REDISPATCH_STOP: probe failed (output missing PROBE_OK) — 不重派,查根因"
            )
            print(f"  probe output: {probe_out}", file=sys.stderr)
            return 0
    else:
        try:
            adapter, _ = _resolve_developer(get_roles(), probe=True)
        except ProbeFailedError:
            print("REDISPATCH_STOP: probe failed — 不重派,查根因")
            return 0
        print(f"REDISPATCH_PROBE: adapter={adapter.name}", file=sys.stderr)

    # Step 5: Guard ② heartbeat (INV-5 owner贯通).
    hb_proc = subprocess.run(
        [
            "bash",
            str(lock_sh),
            "heartbeat",
            "--kind",
            "wp",
            "--key",
            f"{iteration_id}__{work_package_id}",
        ],
        capture_output=True,
        text=True,
    )
    hb_out = (hb_proc.stdout or "") + (hb_proc.stderr or "")
    if not hb_out.strip().startswith("HEARTBEAT_OK"):
        print("REDISPATCH_STOP: heartbeat lost (被接管?) — 不重派")
        print(f"  heartbeat output: {hb_out.strip()}", file=sys.stderr)
        return 0

    # Step 6: Do not clean worktree; keep half-finished work for idempotent continuation.

    # Step 7: Build continuation prompt and persist it for audit.
    iteration_dir = iterations_dir_path / iteration_id
    iteration_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = _build_prompt(
        worktree, log_path, work_package_id, state, review_notes, remaining_risks
    )
    prompt_path = iteration_dir / f"{work_package_id}-redispatch-prompt.md"
    prompt_path.write_text(prompt_text, encoding="utf-8")

    # Resolve adapter for dispatch if the probe guard took the legacy bash path.
    if adapter is None:
        adapter, _ = _resolve_developer(get_roles(), probe=False)

    dry_run = os.environ.get("REDISPATCH_DRY_RUN", "0") == "1"
    brief_path = iteration_dir / f"{work_package_id}-brief.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else ""

    result = _dispatch(adapter, worktree, brief, prompt_text, dry_run)

    if dry_run:
        data = {
            "status": "DRY_RUN",
            "command": list(result.command),
            "prompt_path": str(prompt_path),
        }
        print(json.dumps(data, ensure_ascii=False))
        return 0

    if not result.dispatched:
        _err("dispatch command failed")
        print(result.output, file=sys.stderr)
        return 2

    print(f"REDISPATCH_EXEC: {shlex.join(result.command)}", file=sys.stderr)
    print(f"REDISPATCH_EXEC_OUTPUT: {result.output}", file=sys.stderr)

    # Increment redispatch_count only after confirming the dispatch succeeded.
    new_count = count + 1
    status_data = json.loads(status_file.read_text(encoding="utf-8"))
    status_data.setdefault("executor", {})["redispatch_count"] = new_count
    ts = status_data.get("timestamps")
    if isinstance(ts, dict):
        ts["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status_file.write_text(
        json.dumps(status_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"REDISPATCH_OK count={new_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

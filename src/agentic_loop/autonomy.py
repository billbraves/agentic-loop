#!/usr/bin/env python3
"""Autonomy policy engine — turn the ask/ultra model into a per-action gate.

Consumes the project's ``[autonomy]`` config (``resolve_paths.get_autonomy``) and
maps each orchestration action to ``AUTO`` or ``STOP``. This is the machine
check behind "maximize automation inside the safety boundary": an orchestrator
(or a wrapper) asks ``agentic autonomy <action>`` before committing to a step,
and the answer is deterministic from config.

Fail-closed semantics:

- an action in ``always_stop`` is ALWAYS ``STOP`` (hard boundary), even in
  ``ultra`` mode;
- otherwise an action is ``AUTO`` only when ``default_mode == "ultra"`` AND the
  action is listed in ``ultra_auto``;
- everything else — including an unknown action — is ``STOP``.

Opt-in: a project that does not define an ``[autonomy]`` section is NOT gated
(``configured()`` returns False) so existing projects keep their current
behavior until they explicitly adopt the section. The CLI prints
``AUTONOMY_NOT_CONFIGURED`` in that case (exit 0).
"""
from __future__ import annotations

import argparse
import sys

from agentic_loop.resolve_paths import _load_config
from agentic_loop.resolve_paths import get_autonomy
from agentic_loop.resolve_paths import main_repo

# Frozen action categories (kept in sync with resolve_paths.DEFAULT_AUTONOMY).
ULTRA_AUTO_ACTIONS = frozenset(
    {
        "local_edit",
        "test_run",
        "worktree_lifecycle",
        "dispatch_developer",
        "review",
        "merge_gate",
        "local_merge_no_ff",
        "finalize_merge",
    }
)
ALWAYS_STOP_ACTIONS = frozenset(
    {
        "push",
        "feishu_send",
        "production_write",
        "cron_change",
        "release_deploy",
        "credential_rw",
        "irreversible_git",
    }
)
SOFT_LIMIT_SIGNALS = frozenset({"frozen_hard", "rework_twice", "circuit_breaker"})

AUTO = "AUTO"
STOP = "STOP"

STOP_RC = 3


def known_actions() -> frozenset:
    """All recognized action categories (soft-limit signals are not actions)."""
    return ULTRA_AUTO_ACTIONS | ALWAYS_STOP_ACTIONS


def configured(repo=None) -> bool:
    """True when the project explicitly defines an ``[autonomy]`` section.

    The gate is opt-in: absent ``[autonomy]`` means "no autonomy policy", which
    callers treat as "not gated" for backward compatibility.
    """
    data = _load_config(repo or main_repo())
    return bool(data and isinstance(data.get("autonomy"), dict))


def decide(action: str, autonomy: dict) -> str:
    """Return ``AUTO``/``STOP`` for one action under an ``[autonomy]`` config.

    Fail-closed: unknown actions and anything not explicitly auto-approved in
    ``ultra`` mode resolve to ``STOP``.
    """
    if action in autonomy.get("always_stop", []):
        return STOP
    if autonomy.get("default_mode") == "ultra" and action in autonomy.get(
        "ultra_auto", []
    ):
        return AUTO
    return STOP


def is_soft_limit_signal(signal: str, autonomy: dict) -> bool:
    """True when ``signal`` is declared in ``[autonomy].soft_limit_signals``.

    Soft-limit signals (frozen_hard / rework_twice / circuit_breaker) are the
    "stop and escalate" events an executor already detects; this predicate lets
    the orchestrator classify a reported signal against the policy instead of
    hard-coding the list.
    """
    return signal in autonomy.get("soft_limit_signals", [])


def _signal_main(signal: str) -> int:
    """``agentic autonomy signal <signal>`` — classify one soft-limit signal."""
    repo = main_repo()
    if not configured(repo):
        print("SOFT_LIMIT_NOT_CONFIGURED {}".format(signal))
        return 0
    if is_soft_limit_signal(signal, get_autonomy(repo)):
        print("SOFT_LIMIT_ENABLED {}".format(signal))
        return 0
    print("SOFT_LIMIT_DISABLED {}".format(signal))
    return STOP_RC


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if len(argv) >= 2 and argv[0] == "signal":
        return _signal_main(argv[1])

    ap = argparse.ArgumentParser(prog="agentic autonomy")
    ap.add_argument("action", help="action category (or: signal <signal>)")
    args = ap.parse_args(argv)

    repo = main_repo()
    if not configured(repo):
        print("AUTONOMY_NOT_CONFIGURED {}".format(args.action))
        return 0

    verdict = decide(args.action, get_autonomy(repo))
    print("AUTONOMY_{} {}".format(verdict, args.action))
    return 0 if verdict == AUTO else STOP_RC


if __name__ == "__main__":
    raise SystemExit(main())

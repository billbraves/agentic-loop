from __future__ import annotations

"""Engine-side triple-level independence rating (INV-1 v4).

Pure functions: no I/O, no status writes, no network calls. Consumers (WP-10)
compare the returned ``level`` with ``min_independence`` via
``meets_threshold()``.
"""

from typing import List
from typing import Tuple

from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity


# Ordered from strongest to weakest. ``none`` is the fail-closed floor.
INDEPENDENCE_LEVELS: Tuple[str, ...] = ("strong", "weak", "none")
_LEVEL_RANK = {"strong": 2, "weak": 1, "none": 0}


def _model_of(identity: AgentIdentity | None) -> str | None:
    """Engine-observed model id, or None if the signal is missing."""
    return identity.model if identity is not None else None


def _model_known(identity: AgentIdentity | None) -> bool:
    return identity is not None and identity.model is not None


def _same_model(a: AgentIdentity | None, b: AgentIdentity | None) -> bool:
    """True only when engine has observed both models and they are equal."""
    return _model_known(a) and _model_known(b) and a.model == b.model  # type: ignore[union-attr]


def _different_model(a: AgentIdentity | None, b: AgentIdentity | None) -> bool:
    """True only when engine has observed both models and they differ."""
    return _model_known(a) and _model_known(b) and a.model != b.model  # type: ignore[union-attr]


def _weak_engine_enforced(capabilities: AdapterCapabilities | None) -> Tuple[bool, List[str]]:
    """Check the engine-enforced weak conditions.

    In WP-09 the adapter-attested conditions (fresh session/context,
    adversarial prompt) are represented by the input parameters/capabilities
    because no separate attestation structure exists yet. Missing required
    capability flags therefore manifest as missing attestation in this WP.
    """
    reasons: List[str] = []
    ok = True
    if capabilities is None:
        ok = False
        reasons.append("consultant capabilities missing")
    else:
        if not capabilities.sandbox_enforced:
            ok = False
            reasons.append("consultant sandbox_enforced=False (engine-enforced)")
        if not capabilities.structured_output:
            ok = False
            reasons.append("consultant structured_output=False (engine-enforced)")
    return ok, reasons


def evaluate(
    reviewer_id: AgentIdentity | None,
    consultant_id: AgentIdentity | None,
    capabilities: AdapterCapabilities | None,
    min_independence: str,
    *,
    implementer_id: AgentIdentity | None = None,
) -> Tuple[str, List[str]]:
    """Rate the independence of the two signatures.

    Parameters
    ----------
    reviewer_id:
        Engine-observed identity of the reviewer. ``None`` means the reviewer
        is the human orchestrator (Claude Code) without an adapter identity.
        This triggers the bootstrap exception documented in P3-scope-freeze.
    consultant_id:
        Engine-observed identity of the consultant.
    capabilities:
        Consultant capabilities (engine-enforced weak conditions).
    min_independence:
        Configured threshold (``strong|weak|none``). Accepted for API symmetry
        with WP-10 but not used here; compare the returned ``level`` with
        ``meets_threshold()``.
    implementer_id:
        Used in the degraded path when ``reviewer_id`` is ``None``.

    Returns
    -------
    (level, reasons): ``level`` is one of ``strong``, ``weak``, ``none``.
    ``reasons`` lists the engine-enforced and adapter-attested observations.
    """
    # ``min_independence`` is intentionally not used inside this pure rating
    # function; threshold comparison is performed by ``meets_threshold()``.
    _ = min_independence

    reasons: List[str] = []

    # Determine the comparison base. Bootstrap exception: reviewer identity is
    # unavailable because the orchestrator is a human/ad-hoc reviewer. In that
    # case we fall back to implementer_id (degraded path) if provided.
    if reviewer_id is None:
        reasons.append("reviewer identity unavailable (orchestrator, attested not engine-proven)")
        if implementer_id is not None:
            reasons.append("degraded path: comparing consultant vs implementer")
            compare_against = implementer_id
        else:
            reasons.append("no implementer fallback available")
            compare_against = None
        bootstrap = True
    else:
        compare_against = reviewer_id
        bootstrap = False

    consultant_model = _model_of(consultant_id)

    # ---- strong -----------------------------------------------------------
    # Engine-observed model ids differ. In bootstrap mode this is
    # ``strong-attested`` because the reviewer dimension is not engine-proven.
    if _different_model(consultant_id, compare_against):
        other_model = _model_of(compare_against)
        reasons.append(
            f"engine-observed models differ: consultant={consultant_model} vs "
            f"{'implementer' if bootstrap else 'reviewer'}={other_model}"
        )
        if bootstrap:
            reasons.append("level=strong-attested: reviewer=orchestrator, attested not engine-proven")
        return "strong", reasons

    # ---- weak -------------------------------------------------------------
    # Same observed model and engine-enforced weak conditions are satisfied.
    weak_ok, weak_reasons = _weak_engine_enforced(capabilities)
    reasons.extend(weak_reasons)

    if _same_model(consultant_id, compare_against) and weak_ok:
        if bootstrap:
            reasons.append(
                f"same model with weak conditions met; consultant={consultant_model}"
            )
            reasons.append("level=weak-attested: reviewer=orchestrator, attested not engine-proven")
        else:
            reasons.append(
                f"same model with weak conditions met; consultant={consultant_model}"
            )
        return "weak", reasons

    # ---- none (fail-closed floor) -----------------------------------------
    if not _model_known(consultant_id):
        reasons.append("consultant model not observed by engine")
    if compare_against is not None and not _model_known(compare_against):
        reasons.append(
            f"{'implementer' if bootstrap else 'reviewer'} model not observed by engine"
        )
    if _model_known(consultant_id) and compare_against is not None and _model_of(compare_against) is None:
        # Already covered above, but keep for explicitness.
        pass
    if _model_known(consultant_id) and compare_against is not None and _model_known(compare_against):
        # Both models are known and equal; weak conditions failed, reasons already logged.
        pass

    reasons.append("fail-closed: independence level none")
    return "none", reasons


def meets_threshold(level: str, min_independence: str) -> bool:
    """Return ``True`` iff ``level`` satisfies ``min_independence``.

    Ordering: strong > weak > none. ``none`` is the fail-closed floor: an
    actual level of ``none`` never meets any threshold, including ``none``.
    Unknown levels are treated as ``none`` (fail-closed).
    """
    if level == "none" or level not in _LEVEL_RANK:
        return False
    return _LEVEL_RANK[level] >= _LEVEL_RANK.get(min_independence, 0)

"""WP-08 characterization + reverse tests for ``evaluate()`` independence rating.

The WP-08 fix is a *gate-level admission* change only: it widens *when* the
degraded path (consultant vs implementer, both engine-observed) is entered,
from ``review.decision == "N/A"`` to ``N/A`` or ``ACCEPT``. It deliberately does
NOT touch ``independence.evaluate()`` itself, so these tests pin (characterize)
the existing branch outputs and their ``reasons`` to prove no rating result was
changed — only the admission condition was widened.

Pure functions everywhere: no I/O, no clock, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ReviewerAttestation
from agentic_loop.independence import evaluate
from agentic_loop.independence import meets_threshold


def ident(tool: str, model: str | None) -> AgentIdentity:
    return AgentIdentity(tool=tool, model=model)


def caps() -> AdapterCapabilities:
    return AdapterCapabilities(sandbox_enforced=True, structured_output=True)


def attestation(
    *, fresh_session: bool = True, adversarial_prompt: bool = True
) -> ReviewerAttestation:
    return ReviewerAttestation(
        reviewer_role="orchestrator",
        reviewer_tool="claude-code",
        fresh_session=fresh_session,
        adversarial_prompt=adversarial_prompt,
        attested_by="orchestrator",
        attested_at="2026-09-13T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Characterization: pin the existing evaluate() branch outputs verbatim.
#
# WP-08 changes ONLY the gate admission condition; evaluate() is not modified,
# so every one of these must hold true both before and after the fix.
# ---------------------------------------------------------------------------

def test_characterize_strong_different_models():
    # Non-bootstrap: reviewer and consultant have DIFFERENT observed models.
    reviewer = ident("claude", "deepseek-v4-pro")
    consultant = ident("codex", "deepseek-v4-pro")  # never strong: same below
    # Use a genuinely different model for the consultant to reach strong.
    level, reasons = evaluate(
        reviewer_id=reviewer,
        consultant_id=ident("codex", "deepseek-reasoner"),
        capabilities=caps(),
        min_independence="weak",
    )
    assert level == "strong"
    assert any("engine-observed models differ" in r for r in reasons)
    assert not any("strong-attested" in r for r in reasons)  # non-bootstrap


def test_characterize_weak_same_model_non_bootstrap():
    reviewer = ident("claude", "deepseek-v4-pro")
    consultant = ident("codex", "deepseek-v4-pro")
    level, reasons = evaluate(
        reviewer_id=reviewer,
        consultant_id=consultant,
        capabilities=caps(),
        min_independence="weak",
    )
    assert level == "weak"
    assert any("same model with weak conditions met" in r for r in reasons)
    # Non-bootstrap weak must NOT carry the "weak-attested" suffix.
    assert not any("weak-attested" in r for r in reasons)


def test_characterize_weak_attested_bootstrap():
    # True bootstrap: reviewer None, no implementer, valid attestation.
    consultant = ident("codex", None)
    level, reasons = evaluate(
        None,
        consultant,
        caps(),
        "strong",
        attestation=attestation(),
    )
    assert level == "weak"
    assert any("weak-attested" in r for r in reasons)
    assert any("reviewer attestation present and complete" in r for r in reasons)


def test_characterize_weak_degraded_same_model():
    # Degraded: reviewer None, implementer present, same observed model as
    # consultant. This is the path WP-08 widens admission to — but the rating
    # logic itself is unchanged.
    consultant = ident("codex", "deepseek-v4-pro")
    implementer = ident("kimi", "deepseek-v4-pro")
    level, reasons = evaluate(
        None,
        consultant,
        caps(),
        "weak",
        implementer_id=implementer,
        attestation=attestation(fresh_session=False),  # irrelevant on degraded
    )
    assert level == "weak"
    assert any("degraded path: comparing consultant vs implementer" in r for r in reasons)
    assert any("same model with weak conditions met" in r for r in reasons)


def test_characterize_none_missing_attestation():
    # True bootstrap with no attestation fail-closes to none.
    consultant = ident("codex", None)
    level, reasons = evaluate(None, consultant, caps(), "strong")
    assert level == "none"
    assert any("reviewer attestation missing" in r for r in reasons)
    assert any("fail-closed: independence level none" in r for r in reasons)


def test_characterize_none_attestation_adversarial_false():
    consultant = ident("codex", None)
    level, reasons = evaluate(
        None,
        consultant,
        caps(),
        "strong",
        attestation=attestation(adversarial_prompt=False),
    )
    assert level == "none"
    assert any("reviewer attestation incomplete or conditions false" in r for r in reasons)


def test_characterize_none_unknown_implementer_model():
    # Degraded path where the implementer's model is not engine-observed must
    # fail-closed to none rather than silently rating weak (fail-closed floor).
    consultant = ident("codex", "deepseek-v4-pro")
    implementer = ident("kimi", None)  # model not observed
    level, _ = evaluate(
        None, consultant, caps(), "weak", implementer_id=implementer
    )
    assert level == "none"


# ---------------------------------------------------------------------------
# Reverse tests: prove the fix did NOT turn into a bypass.
# ---------------------------------------------------------------------------

def test_reverse_same_model_never_meets_strong():
    # min_independence="strong" must still reject a same-model degraded rating.
    level, _ = evaluate(
        None,
        ident("codex", "deepseek-v4-pro"),
        caps(),
        "strong",
        implementer_id=ident("kimi", "deepseek-v4-pro"),
    )
    assert level == "weak"  # same model -> never strong
    assert meets_threshold(level, "strong") is False


def test_reverse_attestation_adversarial_false_fail_closed():
    att = attestation(adversarial_prompt=False)
    assert att.adversarial_prompt is False
    assert att.is_valid() is False  # strict: adversarial_prompt is not True


def test_reverse_attestation_missing_adversarial_fail_closed():
    # A missing adversarial_prompt (None) must not pass the strict is True gate.
    # Construct with adversarial_prompt explicitly None to emulate a missing
    # JSON field that read_attestation() passes through verbatim.
    att_missing = ReviewerAttestation(
        reviewer_role="orchestrator",
        reviewer_tool="claude-code",
        fresh_session=True,
        adversarial_prompt=None,  # type: ignore[arg-type]
        attested_by="orchestrator",
    )
    assert att_missing.is_valid() is False


def test_reverse_is_valid_is_strict_identity_not_truthy():
    # ``is True`` is deliberate: 1 and "true" must be rejected, not coerced.
    assert ReviewerAttestation(
        reviewer_role="r", reviewer_tool="t",
        fresh_session=1,  # type: ignore[arg-type]
        adversarial_prompt=True, attested_by="r",
    ).is_valid() is False
    assert ReviewerAttestation(
        reviewer_role="r", reviewer_tool="t",
        fresh_session=True, adversarial_prompt="true",  # type: ignore[arg-type]
        attested_by="r",
    ).is_valid() is False


def test_reverse_evaluate_is_pure_no_strong_same_model():
    # Same-model signatures can never rate strong, even with a valid
    # attestation, in the degraded path (attestation never upgrades).
    level, _ = evaluate(
        None,
        ident("codex", "deepseek-v4-pro"),
        caps(),
        "strong",
        implementer_id=ident("kimi", "deepseek-v4-pro"),
        attestation=attestation(),
    )
    assert level == "weak"
    assert level != "strong"

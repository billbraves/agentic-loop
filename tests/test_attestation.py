"""WP-07 truth-table tests for the structured reviewer attestation.

``evaluate()`` is a pure function, so these tests pin the exact rating
transition the brief requires:

- complete attestation + all conditions true  -> ``weak`` (weak-attested);
- missing attestation                        -> ``none`` (fail-closed, stricter
  than the former text-only bootstrap override);
- incomplete attestation / false condition   -> ``none``;
- ``_different_model`` hit                   -> ``strong`` (unchanged, never
  influenced by attestation).

No real codex / network / file I/O.
"""
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ReviewerAttestation
from agentic_loop.independence import evaluate


def make_identity(tool: str, model: str | None = None) -> AgentIdentity:
    return AgentIdentity(tool=tool, model=model)


def strong_caps() -> AdapterCapabilities:
    return AdapterCapabilities(sandbox_enforced=True, structured_output=True)


def complete_attestation(**over) -> ReviewerAttestation:
    kwargs = dict(
        reviewer_role="orchestrator",
        reviewer_tool="claude-code",
        fresh_session=True,
        adversarial_prompt=True,
        attested_by="orchestrator",
        attested_at="2026-08-13T00:00:00Z",
    )
    kwargs.update(over)
    return ReviewerAttestation(**kwargs)


# ---------------------------------------------------------------------------
# ReviewerAttestation dataclass contract
# ---------------------------------------------------------------------------
def test_reviewer_attestation_frozen():
    attestation = complete_attestation()
    assert attestation.reviewer_role == "orchestrator"
    assert attestation.attested_at is not None
    with pytest.raises(FrozenInstanceError):
        attestation.fresh_session = False


def test_reviewer_attestation_complete_and_valid():
    attestation = complete_attestation()
    assert attestation.is_complete() is True
    assert attestation.is_valid() is True


def test_reviewer_attestation_incomplete_on_empty_required_field():
    attestation = complete_attestation(reviewer_role="")
    assert attestation.is_complete() is False
    assert attestation.is_valid() is False


def test_reviewer_attestation_incomplete_on_missing_attested_by():
    attestation = complete_attestation(attested_by="   ")
    assert attestation.is_complete() is False
    assert attestation.is_valid() is False


def test_reviewer_attestation_invalid_when_fresh_session_false():
    attestation = complete_attestation(fresh_session=False)
    assert attestation.is_complete() is True
    assert attestation.is_valid() is False


def test_reviewer_attestation_invalid_when_adversarial_prompt_false():
    attestation = complete_attestation(adversarial_prompt=False)
    assert attestation.is_complete() is True
    assert attestation.is_valid() is False


def test_reviewer_attestation_invalid_when_fresh_session_is_string_false():
    # strict-bool: bool("false") would be True, but is_valid must reject it.
    attestation = complete_attestation(fresh_session="false")  # type: ignore[arg-type]
    assert attestation.is_complete() is True
    assert attestation.is_valid() is False


def test_reviewer_attestation_invalid_when_adversarial_prompt_is_string_true():
    attestation = complete_attestation(adversarial_prompt="true")  # type: ignore[arg-type]
    assert attestation.is_complete() is True
    assert attestation.is_valid() is False


def test_reviewer_attestation_invalid_when_conditions_are_none():
    attestation = complete_attestation(fresh_session=None, adversarial_prompt=None)  # type: ignore[arg-type]
    assert attestation.is_complete() is True
    assert attestation.is_valid() is False


def test_reviewer_attestation_invalid_when_fresh_session_is_int():
    attestation = complete_attestation(fresh_session=1)  # type: ignore[arg-type]
    assert attestation.is_valid() is False


# ---------------------------------------------------------------------------
# Truth table: bootstrap path (reviewer_id is None, no implementer fallback)
# ---------------------------------------------------------------------------
def test_attestation_complete_conditions_true_rates_weak_attested():
    # Mirrors the real gate.py bootstrap path: consultant identity has no
    # engine-observable model (CodexAdapter().identity() -> model=None).
    consultant = make_identity("codex", None)
    level, reasons = evaluate(
        None,
        consultant,
        strong_caps(),
        "strong",
        attestation=complete_attestation(),
    )
    assert level == "weak"
    assert any("weak-attested" in r for r in reasons)
    assert any("reviewer attestation present and complete" in r for r in reasons)


def test_attestation_missing_fail_closed_to_none():
    consultant = make_identity("codex", None)
    level, reasons = evaluate(None, consultant, strong_caps(), "strong")
    assert level == "none"
    assert any("reviewer attestation missing" in r for r in reasons)


def test_attestation_partial_field_missing_fail_closed_to_none():
    consultant = make_identity("codex", None)
    attestation = complete_attestation(reviewer_tool="")
    level, reasons = evaluate(
        None,
        consultant,
        strong_caps(),
        "strong",
        attestation=attestation,
    )
    assert level == "none"
    assert any("reviewer attestation incomplete" in r for r in reasons)


def test_attestation_condition_false_fail_closed_to_none():
    consultant = make_identity("codex", None)
    attestation = complete_attestation(fresh_session=False)
    level, reasons = evaluate(
        None,
        consultant,
        strong_caps(),
        "strong",
        attestation=attestation,
    )
    assert level == "none"
    assert any("reviewer attestation incomplete" in r for r in reasons)


def test_attestation_missing_stronger_than_old_text_override():
    # The former bootstrap override would upgrade none->weak without any
    # attestation. The new logic must NOT do that: missing attestation stays
    # none at the pure-function level.
    consultant = make_identity("codex", "gpt-5.5")
    level, _ = evaluate(None, consultant, strong_caps(), "strong")
    assert level == "none"
    assert level != "weak"


# ---------------------------------------------------------------------------
# Invariants: strong path is verbatim-unchanged, attestation never upgrades.
# ---------------------------------------------------------------------------
def test_bootstrap_strong_path_unchanged_with_attestation():
    implementer = make_identity("kimi", "kimi-k2")
    consultant = make_identity("codex", "gpt-5.5")
    level, reasons = evaluate(
        None,
        consultant,
        strong_caps(),
        "strong",
        implementer_id=implementer,
        attestation=complete_attestation(),
    )
    assert level == "strong"
    assert any("strong-attested" in r for r in reasons)


def test_attestation_never_rates_strong_true_bootstrap():
    # In the true bootstrap path (no implementer fallback) there is no engine
    # model comparison, so a valid attestation can only ever yield weak or none,
    # never strong. This is the honesty invariant: attestation is not engine
    # proof of distinct models.
    consultant = make_identity("codex", "gpt-5.5")
    level, _ = evaluate(
        None,
        consultant,
        strong_caps(),
        "strong",
        attestation=complete_attestation(),
    )
    assert level != "strong"


def test_degraded_path_ignores_attestation_for_model_comparison():
    # reviewer=None + implementer present: the rating is model-comparison
    # driven, so an (even invalid) attestation does not change the outcome.
    implementer = make_identity("kimi", "shared-model")
    consultant = make_identity("codex", "shared-model")
    level, _ = evaluate(
        None,
        consultant,
        strong_caps(),
        "weak",
        implementer_id=implementer,
        attestation=complete_attestation(fresh_session=False),
    )
    assert level == "weak"

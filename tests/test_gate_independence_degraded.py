"""WP-08 gate-level admission tests: the degraded path now admits ACCEPT.

The one hard change of WP-08 is a single admission condition inside
``agentic_loop.gate``: the degraded consultant-vs-implementer independence path
is entered when ``review.decision`` is ``N/A`` **or** ``ACCEPT``, instead of
only ``N/A``.

Two pure helpers capture that behavior so it can be pinned without reproducing
the whole ``main()`` git/validator/codex pipeline:

- ``_should_populate_implementer(review_decision)`` — the *admission* predicate
  (widened from N/A to N/A or ACCEPT);
- ``_resolve_implementer_identity(executor_tool, repo_root, binding)`` — builds
  the implementer's engine-observed identity; returns ``None`` when the
  developer role's binding carries no identity_model, so the caller falls back
  to the weaker bootstrap (attestation) path instead of entering the degraded
  path with an unobserved model.

No git/validator/codex I/O.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.gate import _resolve_implementer_identity
from agentic_loop.gate import _should_populate_implementer


EXAMPLE = (
    Path(__file__).resolve().parents[1] / "examples" / "config.single-deepseek.toml"
)


# ---------------------------------------------------------------------------
# Admission predicate truth table.
# ---------------------------------------------------------------------------

def test_admit_accept():
    # The core WP-08 behavioral change: ACCEPT is now admitted to the degraded
    # path (previously only N/A was).
    assert _should_populate_implementer("ACCEPT") is True


def test_admit_na_still_admitted():
    # The pre-existing N/A behavior is preserved (no regression).
    assert _should_populate_implementer("N/A") is True


def test_admit_rework_not_admitted():
    # A REWORK decision does not reach the independence rating at all (the gate
    # fails earlier on precondition, or the consultant returns REWORK), so the
    # predicate is definitively False outside N/A/ACCEPT.
    assert _should_populate_implementer("REWORK") is False


def test_admit_consult_not_admitted():
    assert _should_populate_implementer("CONSULT") is False


@pytest.mark.parametrize("value", ["", "accept", "ACCEPt", "N/A ", None])
def test_admit_noncanonical_values_fail_closed(value):
    # Only the exact canonical tokens are admitted; anything else is False so
    # the gate can never be tricked into the degraded path by a malformed value.
    assert _should_populate_implementer(value) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Implementer identity resolution: model observed vs. not observed.
# ---------------------------------------------------------------------------

class _Binding:
    def __init__(self, identity_model):
        self.identity_model = identity_model


def test_resolve_implementer_identity_has_model():
    ident = _resolve_implementer_identity("kimi-cli", _Binding("deepseek-v4-pro"))
    assert ident is not None
    assert ident.tool == "kimi-cli"
    assert ident.model == "deepseek-v4-pro"


def test_resolve_implementer_identity_falls_back_none_without_binding():
    # No developer binding -> no engine-observed model -> None, so the caller
    # falls back to bootstrap rather than entering degraded half-observed.
    assert _resolve_implementer_identity("kimi-cli", None) is None


def test_resolve_implementer_identity_falls_back_none_without_model():
    # A binding with a missing/empty identity_model must also yield None.
    assert _resolve_implementer_identity("kimi-cli", _Binding(None)) is None


# ---------------------------------------------------------------------------
# Corollary: the degraded path is only entered when both models are observable;
# otherwise ACCEPT falls back to bootstrap (attestation), which is unchanged.
# ---------------------------------------------------------------------------

def test_accept_with_model_is_degraded_not_bootstrap():
    # With an engine-observed implementer model, ACCEPT routes into degraded, so
    # ``is_bootstrap_normal`` is False (the weaker self-attestation path is NOT
    # taken).
    implementer = _resolve_implementer_identity(
        "kimi-cli", _Binding("deepseek-v4-pro")
    )
    is_bootstrap_normal = "ACCEPT" == "ACCEPT" and implementer is None
    assert is_bootstrap_normal is False


def test_accept_without_model_falls_back_to_bootstrap():
    # Without an engine-observed implementer model, ACCEPT keeps implementer_id
    # None, so the bootstrap (attestation) path is still available — the same
    # behavior as before WP-08 for repos with no provider binding.
    implementer = _resolve_implementer_identity("kimi-cli", None)
    is_bootstrap_normal = "ACCEPT" == "ACCEPT" and implementer is None
    assert is_bootstrap_normal is True


# ---------------------------------------------------------------------------
# Forward end-to-end (pure): ACCEPT + same-model consultant/implementer, with a
# real single-provider binding, rates ``weak`` via the degraded path (not
# bootstrap-attested), and ``meets_threshold(weak, weak)`` lets the gate pass.
# ---------------------------------------------------------------------------

def test_forward_accept_same_model_rates_weak_degraded(tmp_path):
    import subprocess

    from agentic_loop import resolve_paths as rp
    from agentic_loop.adapters.codex import CodexAdapter
    from agentic_loop.independence import evaluate, meets_threshold

    # Reproduce the real single-provider profile so developer and consultant
    # resolve to the SAME identity model (deepseek-v4-pro).
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    a = tmp_path / ".agentic"
    a.mkdir()
    (a / "config.toml").write_text(
        EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8"
    )

    _, developer_binding = rp.resolve_role_binding("developer", repo=tmp_path)
    _, consultant_binding = rp.resolve_role_binding("consultant", repo=tmp_path)

    # The gate's ACCEPT path resolves the implementer identity from the developer
    # binding (model observed), and the consultant identity from its binding.
    implementer_id = _resolve_implementer_identity("kimi-cli", developer_binding)
    assert implementer_id is not None
    assert implementer_id.model == "deepseek-v4-pro"

    consultant_adapter = CodexAdapter(binding=consultant_binding)
    consultant_id = consultant_adapter.identity()
    assert consultant_id.model == "deepseek-v4-pro"

    # reviewer_id is None (orchestrator without adapter identity) -> the
    # bootstrap exception routes into the degraded path because implementer_id
    # is present and both models are engine-observed and equal.
    level, reasons = evaluate(
        reviewer_id=None,
        consultant_id=consultant_id,
        capabilities=consultant_adapter.capabilities(),
        min_independence="weak",
        implementer_id=implementer_id,
        attestation=None,
    )
    assert level == "weak"
    assert meets_threshold(level, "weak") is True
    # The trail proves this is the degraded path (consultant vs implementer),
    # not the bootstrap attestation path.
    assert any("degraded path: comparing consultant vs implementer" in r for r in reasons)
    assert any("same model with weak conditions met" in r for r in reasons)
    assert not any("reviewer attestation" in r for r in reasons)

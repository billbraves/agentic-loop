"""WP-04: ``validate_wp_status`` qoder_security schema + validator migration.

Locks the frozen version boundary (``agentic-wp-status/v3`` adds the qoder
security third signature as a *required* top-level block, v2 stays frozen without
it), the block's content checks (decision enum, ERROR error-kind/message,
findings severity, override four-field fail-closed), and the extra-key regression
guard. Historical MERGED v2 statuses are re-validated in place.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.validate_wp_status import (  # noqa: E402
    _override_dict_is_legal,
    _override_is_legal,
    _qoder_security_satisfied,
    validate,
)

# Test file: packages/agentic-loop/tests/test_validate_wp_status_qoder.py
# parents: tests -> agentic-loop -> packages -> repo root.
REPO = Path(__file__).resolve().parents[3]

V2 = "agentic-wp-status/v2"
V3 = "agentic-wp-status/v3"

FINDING = {
    "category": "xss",
    "severity": "high",
    "file": "a.py",
    "dataflow": None,
    "summary": "xss",
    "scope": "in_scope",
    "suppressed": False,
}


def make_status(schema_version: str = V2, **overrides: object) -> dict:
    """Build a minimally valid DRAFT status for the given schema version."""
    data: dict = {
        "schema_version": schema_version,
        "work_package_id": "WP-TEST",
        "iteration_id": "iter-test",
        "phase": "P1",
        "state": "DRAFT",
        "role": "Developer",
        "executor": {"tool": "unassigned"},
        "orchestrator": {"tool": "claude-code"},
        "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "main"},
        "scope": {"allowed_paths": [], "forbidden_paths": []},
        "risk": {},
        "evidence": {},
        "review": {},
        "timestamps": {},
    }
    if schema_version in (V2, V3):
        data["consult"] = {}
    data.update(overrides)
    return data


def legal_qoder(**extra: object) -> dict:
    """A structurally complete, legal qoder_security block (PASS, no findings)."""
    block: dict = {
        "decision": "PASS",
        "findings": [],
        "level": "L3",
        "requested_level": "L3",
    }
    block.update(extra)
    return block


def make_merge_status(
    schema_version: str,
    state: str,
    qoder_security: object = None,
    **overrides: object,
) -> dict:
    """Build a merge-state status satisfying every gate except the qoder gate.

    review=ACCEPT, consult=ACCEPT (v2/v3), git complete (base_commit/branch/
    worktree/commit), scope.allowed_paths non-empty, evidence.tests non-empty,
    executor assigned. ``qoder_security`` is added when not None so the caller
    controls the v3 third signature; extra overrides are applied last.
    """
    data = make_status(
        schema_version,
        state=state,
        executor={"tool": "kimi-cli"},
        review={"decision": "ACCEPT"},
        git={
            "base_branch": "main",
            "base_commit": "abc123",
            "branch": "feat/x",
            "worktree": ".worktrees/x",
            "commit": "deadbeef",
        },
        scope={"allowed_paths": ["packages/agentic-loop/src"], "forbidden_paths": []},
        evidence={"tests": [{"exit_code": 0}]},
    )
    if schema_version in (V2, V3):
        data["consult"] = {"decision": "ACCEPT"}
    if qoder_security is not None:
        data["qoder_security"] = qoder_security
    data.update(overrides)
    return data


def test_v2_without_qoder_is_valid() -> None:
    assert validate(make_status(V2)) == []


def test_v2_with_legal_qoder_is_valid() -> None:
    errors = validate(make_status(V2, qoder_security=legal_qoder()))
    assert errors == []


def test_v2_with_invalid_qoder_rejected_by_content() -> None:
    errors = validate(make_status(V2, qoder_security=legal_qoder(decision="MAYBE")))
    assert any("qoder_security.decision is invalid" in error for error in errors)


def test_v3_without_qoder_rejected() -> None:
    errors = validate(make_status(V3))
    assert any("qoder_security" in error for error in errors)


def test_v3_with_legal_qoder_passes() -> None:
    errors = validate(make_status(V3, qoder_security=legal_qoder()))
    assert errors == []


def test_decision_invalid_rejected() -> None:
    errors = validate(make_status(V3, qoder_security=legal_qoder(decision="MAYBE")))
    assert any("qoder_security.decision is invalid" in error for error in errors)


def test_error_decision_requires_complete_error() -> None:
    # Missing error object.
    errors = validate(
        make_status(V3, qoder_security={"decision": "ERROR", "findings": []})
    )
    assert any("qoder_security.error must be an object" in error for error in errors)

    # Kind not in the six ERROR_KINDS.
    errors = validate(
        make_status(
            V3,
            qoder_security={
                "decision": "ERROR",
                "findings": [],
                "error": {"kind": "bogus", "message": "x"},
            },
        )
    )
    assert any("qoder_security.error.kind is invalid" in error for error in errors)

    # Empty message.
    errors = validate(
        make_status(
            V3,
            qoder_security={
                "decision": "ERROR",
                "findings": [],
                "error": {"kind": "auth_expired", "message": "   "},
            },
        )
    )
    assert any("qoder_security.error.message" in error for error in errors)


def test_error_decision_valid_passes() -> None:
    errors = validate(
        make_status(
            V3,
            qoder_security={
                "decision": "ERROR",
                "findings": [],
                "level": "L3",
                "requested_level": "L3",
                "error": {"kind": "auth_expired", "message": "expired"},
            },
        )
    )
    assert errors == []


def test_non_error_decision_with_malformed_error_rejected() -> None:
    # brief §52: error is a structured field. A present error must satisfy the
    # kind-enum + non-empty-message contract regardless of decision, so a PASS
    # decision cannot smuggle a malformed error past the schema.
    errors = validate(
        make_status(
            V3,
            qoder_security={
                "decision": "PASS",
                "findings": [],
                "level": "L3",
                "error": {"kind": "bogus", "message": ""},
            },
        )
    )
    assert any("qoder_security.error.kind is invalid" in error for error in errors)
    assert any("qoder_security.error.message" in error for error in errors)


def test_non_error_decision_without_error_is_legal() -> None:
    # error is only required when decision=ERROR. A PASS block omitting error is
    # legal (this is the common case; legal_qoder() itself omits error).
    errors = validate(
        make_status(
            V3,
            qoder_security={
                "decision": "PASS",
                "findings": [],
                "level": "L3",
            },
        )
    )
    assert errors == []


def test_findings_severity_invalid_rejected() -> None:
    for severity in ("critical", "sev1"):
        findings = [dict(FINDING, severity=severity)]
        errors = validate(
            make_status(
                V3,
                qoder_security=legal_qoder(decision="FINDINGS", findings=findings),
            )
        )
        assert any("severity is invalid" in error for error in errors), severity


def test_findings_severity_valid_passes() -> None:
    for severity in ("high", "medium", "low"):
        findings = [dict(FINDING, severity=severity)]
        errors = validate(
            make_status(
                V3,
                qoder_security=legal_qoder(decision="FINDINGS", findings=findings),
            )
        )
        assert errors == [], severity


def _findings_errors(findings: list[dict]) -> list[str]:
    """Validate a v3 FINDINGS block built from ``findings`` and return errors."""
    return validate(
        make_status(
            V3,
            qoder_security=legal_qoder(decision="FINDINGS", findings=findings),
        )
    )


def test_finding_missing_category_rejected() -> None:
    finding = {k: v for k, v in FINDING.items() if k != "category"}
    errors = _findings_errors([finding])
    assert any("findings[0].category" in error for error in errors)


def test_finding_empty_category_rejected() -> None:
    errors = _findings_errors([{**FINDING, "category": ""}])
    assert any("findings[0].category" in error for error in errors)


@pytest.mark.parametrize("field", ["file", "summary"])
def test_finding_missing_file_or_summary_rejected(field: str) -> None:
    finding = {k: v for k, v in FINDING.items() if k != field}
    errors = _findings_errors([finding])
    assert any(f"findings[0].{field}" in error for error in errors)


def test_finding_dataflow_non_null_non_string_rejected() -> None:
    errors = _findings_errors([{**FINDING, "dataflow": 123}])
    assert any("findings[0].dataflow" in error for error in errors)


def test_finding_dataflow_null_is_legal() -> None:
    # dataflow is nullable; None is an accepted value. The key must be present
    # (see test_finding_dataflow_missing_rejected), but a present None passes.
    assert _findings_errors([{**FINDING, "dataflow": None}]) == []


def test_finding_dataflow_missing_rejected() -> None:
    # brief §51 lists dataflow in the frozen finding structure; the key must be
    # present (value str|null). A finding lacking the key is rejected.
    finding = {k: v for k, v in FINDING.items() if k != "dataflow"}
    errors = _findings_errors([finding])
    assert any("findings[0].dataflow" in error for error in errors)


@pytest.mark.parametrize(
    "finding",
    [
        {k: v for k, v in FINDING.items() if k != "scope"},
        {**FINDING, "scope": ""},
    ],
)
def test_finding_scope_optional_not_gated(finding: dict) -> None:
    # round-5: scope is an engine runtime field, not in brief §51's frozen
    # validator contract. Absent or empty scope must not be rejected.
    assert _findings_errors([finding]) == []


@pytest.mark.parametrize(
    "finding",
    [
        {k: v for k, v in FINDING.items() if k != "suppressed"},
        {**FINDING, "suppressed": "false"},
    ],
)
def test_finding_suppressed_optional_not_gated(finding: dict) -> None:
    # round-5: suppressed is an engine runtime field, not in brief §51. Its
    # absence or non-bool value must not be rejected by the validator.
    assert _findings_errors([finding]) == []


def test_block_level_missing_rejected() -> None:
    qoder = legal_qoder()
    del qoder["level"]
    errors = validate(make_status(V3, qoder_security=qoder))
    assert any("qoder_security.level must be a non-empty string" in error for error in errors)


def test_block_level_empty_rejected() -> None:
    errors = validate(make_status(V3, qoder_security=legal_qoder(level="  ")))
    assert any("qoder_security.level must be a non-empty string" in error for error in errors)


def test_block_requested_level_optional_not_gated() -> None:
    # round-5: requested_level is an engine runtime field, not in brief §51.
    # A block without it must still validate (level alone satisfies the brief).
    qoder = legal_qoder()
    del qoder["requested_level"]
    assert validate(make_status(V3, qoder_security=qoder)) == []


def test_v3_minimal_brief_51_qoder_passes() -> None:
    # round-5 direct lock: a v3 qoder_security block carrying only the brief
    # §51 authorized fields (decision, findings[category/severity/file/
    # dataflow/summary], level) validates cleanly even though engine runtime
    # fields scope/suppressed/requested_level are absent.
    qoder = {
        "decision": "FINDINGS",
        "findings": [
            {
                "category": "xss",
                "severity": "high",
                "file": "a.py",
                "dataflow": None,
                "summary": "xss",
            }
        ],
        "level": "L3",
    }
    assert validate(make_status(V3, qoder_security=qoder)) == []


def test_finding_full_fields_passes() -> None:
    # FINDING carries every required field; it must still be accepted as-is.
    assert _findings_errors([FINDING]) == []


def test_override_legal_passes() -> None:
    override = {
        "approved": True,
        "approver": "human",
        "justification": "approved",
        "reviewed_at": "2026-08-14",
    }
    errors = validate(
        make_status(V3, qoder_security=legal_qoder(override=override))
    )
    assert errors == []


@pytest.mark.parametrize(
    "override",
    [
        {"approved": True, "justification": "j", "reviewed_at": "2026-08-14"},
        {"approved": False, "approver": "a", "justification": "j", "reviewed_at": "2026-08-14"},
        {"approved": True, "approver": " ", "justification": "j", "reviewed_at": "2026-08-14"},
        {"approved": True, "approver": "a", "justification": "j"},
    ],
)
def test_override_incomplete_rejected(override: dict) -> None:
    errors = validate(
        make_status(V3, qoder_security=legal_qoder(override=override))
    )
    assert any("qoder_security.override" in error for error in errors)


def test_override_helpers_agree_with_consult_shape() -> None:
    # The shared helper must treat a consult-wrapped override and a raw qoder
    # override identically (same strictness, fail-closed).
    cases = [
        None,
        {},
        {"approved": True, "approver": "a", "justification": "j", "reviewed_at": "t"},
        {"approved": False, "approver": "a", "justification": "j", "reviewed_at": "t"},
        {"approved": True, "approver": " ", "justification": "j", "reviewed_at": "t"},
    ]
    for override in cases:
        assert _override_is_legal({"override": override}) is _override_dict_is_legal(
            override
        )


def test_qoder_security_satisfied_hook() -> None:
    # The validator-level predicate WP-05 will consume: PASS or approved override.
    assert _qoder_security_satisfied(legal_qoder()) is True
    assert (
        _qoder_security_satisfied(
            legal_qoder(
                decision="FINDINGS",
                findings=[FINDING],
                override={
                    "approved": True,
                    "approver": "a",
                    "justification": "j",
                    "reviewed_at": "t",
                },
            )
        )
        is True
    )
    assert _qoder_security_satisfied(legal_qoder(decision="FINDINGS", findings=[FINDING])) is False
    assert _qoder_security_satisfied(legal_qoder(decision="ERROR")) is False
    assert _qoder_security_satisfied(None) is False


def test_extra_key_check_not_broken() -> None:
    # A real illegal extra key is still rejected.
    errors = validate(make_status(V2, bogus_key="x"))
    assert any("unknown top-level fields: bogus_key" in error for error in errors)

    # And a legal qoder_security block must NOT be reported as an extra key.
    errors = validate(make_status(V3, qoder_security=legal_qoder()))
    assert not any("unknown top-level fields" in error for error in errors)


def test_v3_merge_state_qoder_findings_no_override_rejected() -> None:
    # round-3 defect lock: a v3 status may not enter a merge state while its
    # qoder_security decision is an unapproved FINDINGS.
    errors = validate(
        make_merge_status(
            V3,
            "APPROVED_FOR_MERGE",
            qoder_security=legal_qoder(decision="FINDINGS", findings=[FINDING]),
        )
    )
    assert any(
        "qoder_security must be PASS or carry a complete approved override"
        in error
        for error in errors
    )


def test_v3_merge_state_qoder_error_no_override_rejected() -> None:
    # A structurally legal ERROR block still blocks the merge without override.
    qoder = {
        "decision": "ERROR",
        "findings": [],
        "level": "L3",
        "requested_level": "L3",
        "error": {"kind": "auth_expired", "message": "expired"},
    }
    errors = validate(
        make_merge_status(V3, "APPROVED_FOR_MERGE", qoder_security=qoder)
    )
    assert any(
        "qoder_security must be PASS or carry a complete approved override"
        in error
        for error in errors
    )


def test_v3_merge_state_qoder_pass_passes() -> None:
    errors = validate(
        make_merge_status(V3, "APPROVED_FOR_MERGE", qoder_security=legal_qoder())
    )
    assert errors == []


def test_v3_merge_state_qoder_findings_approved_override_passes() -> None:
    override = {
        "approved": True,
        "approver": "human",
        "justification": "approved",
        "reviewed_at": "2026-08-14",
    }
    qoder = legal_qoder(
        decision="FINDINGS", findings=[FINDING], override=override
    )
    errors = validate(
        make_merge_status(V3, "APPROVED_FOR_MERGE", qoder_security=qoder)
    )
    assert errors == []


def test_v3_merged_state_qoder_findings_no_override_rejected() -> None:
    # MERGED (and RELEASED) enforce the same third signature, not only
    # APPROVED_FOR_MERGE.
    data = make_merge_status(
        V3,
        "MERGED",
        qoder_security=legal_qoder(decision="FINDINGS", findings=[FINDING]),
    )
    data["git"]["merged_commit"] = "merged123"
    errors = validate(data)
    assert any(
        "qoder_security must be PASS or carry a complete approved override"
        in error
        for error in errors
    )


def test_v2_merge_state_without_qoder_still_passes() -> None:
    # v2 stays double-sign only: a missing qoder_security block must not be
    # newly required or gated by the v3-only branch.
    errors = validate(make_merge_status(V2, "APPROVED_FOR_MERGE"))
    assert errors == []


@pytest.mark.parametrize("wp", ["WP-01", "WP-02", "WP-03"])
def test_historical_v2_statuses_valid(wp: str) -> None:
    path = (
        REPO
        / "docs"
        / "plans"
        / "agentic-gate-unification-v1"
        / "work-packages"
        / f"{wp}.status.json"
    )
    if not path.is_file():
        pytest.skip(f"{wp}.status.json not present")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert validate(data) == []


# ---------------------------------------------------------------------------
# scope.allowed_paths / scope.forbidden_paths must be prefix-reducible.
#
# Scope matching is a prefix predicate. An entry containing a wildcard that is
# not a trailing '/**' or '/*' can never match a real path, so a forbidden
# entry like '*.env' forbids nothing while looking active in the status file.
# Reject at authoring time rather than enforce nothing at gate time.
# ---------------------------------------------------------------------------
def _scope_errors(**scope: object) -> list[str]:
    base = {"allowed_paths": [], "forbidden_paths": []}
    base.update(scope)
    return validate(make_status(scope=base))


@pytest.mark.parametrize("field", ["allowed_paths", "forbidden_paths"])
@pytest.mark.parametrize(
    "pattern",
    ["*.env", "a/*/b", "a*b", "docs/**/plans", "src/?.py", "src/[ab]/x.py"],
)
def test_non_prefix_wildcard_rejected(field: str, pattern: str) -> None:
    errors = _scope_errors(**{field: [pattern]})
    assert any(
        f"scope.{field} entry" in e and "not a path prefix" in e for e in errors
    ), errors


@pytest.mark.parametrize("field", ["allowed_paths", "forbidden_paths"])
@pytest.mark.parametrize("pattern", ["/", "**", "./", "/**", "./**"])
def test_whole_repo_entry_rejected(field: str, pattern: str) -> None:
    errors = _scope_errors(**{field: [pattern]})
    assert any(
        f"scope.{field} entry" in e and "whole repository" in e for e in errors
    ), errors


@pytest.mark.parametrize("field", ["allowed_paths", "forbidden_paths"])
@pytest.mark.parametrize("pattern", ["", "   "])
def test_blank_entry_rejected(field: str, pattern: str) -> None:
    errors = _scope_errors(**{field: [pattern]})
    assert any(f"scope.{field} contains a blank entry" in e for e in errors), errors


@pytest.mark.parametrize("field", ["allowed_paths", "forbidden_paths"])
@pytest.mark.parametrize(
    "pattern",
    [
        "skills",
        "skills/",
        "skills/**",
        "skills/*",
        "./skills/**",
        "qoder_agent/harness/ontology",
        ".env",
        "docs/plans/harness-architecture/**",
    ],
)
def test_prefix_reducible_entries_accepted(field: str, pattern: str) -> None:
    """The supported spellings must pass: bare prefix, trailing slash, './'
    prefix, and the two glob suffixes. A dotfile is a legal prefix too — the
    '[' / '?' / '*' rejection must not catch a plain '.env'."""
    errors = _scope_errors(**{field: [pattern]})
    assert not any(f"scope.{field}" in e for e in errors), errors

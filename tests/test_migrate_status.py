"""Tests for `agentic migrate-status` (legacy .wp status -> v2)."""
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import migrate_status as ms  # noqa: E402

LEGACY = {
    "wp_id": "WP-22",
    "title": "接入 entity_scenario_tag 反向能力",
    "state": "DONE",
    "executor": {"tool": "kimi-cli", "session": "s1"},
    "orchestrator": {"tool": "claude-code", "session": "s2"},
    "reviewer": {"tool": "claude-code", "session": "s3"},
    "git": {
        "base_commit": "cd713ca",
        "branch": "feature/wp22-entity-scenario-tag",
        "worktree": "../wp22-entity-scenario-tag",
        "commit": "d74ed3e",
    },
    "brief": {"path": "docs/wp/WP-22.brief.md", "sha256": "abc"},
    "scope": {"allowed_paths": ["skills/ad/optimization/**"], "forbidden_paths": [".ci"]},
    "risk": {
        "production_writes": "FORBIDDEN",
        "network": "FORBIDDEN",
        "notifications": "FORBIDDEN",
        "data_access": "READ_ONLY",
    },
    "concerns": ["merged on 2026-08-13"],
    "blocker": None,
    "timestamps": {"dispatched_at": "2026-08-13T11:28:06Z"},
}


def test_dispatched_maps_and_preserves_mechanical_fields():
    legacy = dict(LEGACY, state="DISPATCHED")
    new, warnings = ms.migrate(legacy, iteration_id="iter-1")
    assert new["schema_version"] == "agentic-wp-status/v2"
    assert new["work_package_id"] == "WP-22"
    assert new["iteration_id"] == "iter-1"
    assert new["state"] == "DISPATCHED"
    assert new["role"] == "Developer"
    assert new["git"]["base_commit"] == "cd713ca"
    assert new["git"]["base_branch"] == "main"
    assert new["scope"]["allowed_paths"] == ["skills/ad/optimization/**"]
    assert new["risk"]["data_access"] == "READ_ONLY"
    # dropped fields produce warnings
    assert any("title" in w for w in warnings)
    assert any("brief" in w for w in warnings)


def test_done_without_merged_commit_maps_to_ready_for_review():
    new, warnings = ms.migrate(LEGACY, iteration_id="iter-1")
    assert new["state"] == "READY_FOR_REVIEW"
    assert "merged_commit" not in new["git"]
    assert any("review.decision=ACCEPT" in w for w in warnings)


def test_done_with_merged_commit_maps_to_merged():
    new, warnings = ms.migrate(LEGACY, iteration_id="iter-1", merged_commit="aadbee4")
    assert new["state"] == "MERGED"
    assert new["git"]["merged_commit"] == "aadbee4"


def test_blocked_maps_directly():
    legacy = dict(LEGACY, state="BLOCKED", blocker="waiting on data")
    new, warnings = ms.migrate(legacy, iteration_id="iter-1")
    assert new["state"] == "BLOCKED"
    assert any("blocker" in w for w in warnings)


def test_unknown_state_raises():
    with pytest.raises(ValueError):
        ms.migrate(dict(LEGACY, state="BOGUS"), iteration_id="iter-1")


def test_roundtrip_output_is_valid_json():
    new, _ = ms.migrate(LEGACY, iteration_id="iter-1")
    assert json.loads(json.dumps(new)) == new

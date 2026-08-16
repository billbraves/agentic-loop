"""Tests for `agentic init` + `agentic contract check/diff` (WP-21).

All filesystem effects are confined to pytest tmp_path; the repo's own contracts
are never touched.
"""
import io
from contextlib import redirect_stdout, redirect_stderr

import pytest

from agentic_loop import cli, contract_cmd, contract_render, init_cmd


def _init(tmp_path, *extra):
    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = cli.main(["init", "--dir", str(tmp_path), "--non-interactive", *extra])
    return rc, buf.getvalue(), err.getvalue()


def _check(tmp_path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["contract", "check", "--dir", str(tmp_path)])
    return rc, buf.getvalue()


def _diff(tmp_path, *extra):
    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = cli.main(["contract", "diff", "--dir", str(tmp_path), *extra])
    return rc, buf.getvalue(), err.getvalue()


def test_init_writes_config_contracts_skeleton_and_stamp(tmp_path):
    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    assert (tmp_path / ".agentic" / "config.toml").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / "docs" / "agentic" / "OPERATING_MODEL.md").is_file()
    assert (tmp_path / "docs" / "plans").is_dir()
    assert (tmp_path / ".agentic" / "locks").is_dir()

    # stamp header present on each rendered contract, no unfilled placeholders
    for rel in ("AGENTS.md", "CLAUDE.md", "docs/agentic/OPERATING_MODEL.md"):
        text = (tmp_path / rel).read_text(encoding="utf-8")
        assert "agentic-contract:" in text
        assert "${" not in text and "$contract" not in text

    # locks are gitignored
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert init_cmd.GITIGNORE_LOCKS_LINE in gi.splitlines()


def test_init_scaffolds_reference_templates(tmp_path):
    assert _init(tmp_path)[0] == 0
    status = tmp_path / "docs" / "agentic" / "templates" / "STATUS.json"
    brief = tmp_path / "docs" / "agentic" / "templates" / "WORK_PACKAGE.md"
    assert status.is_file()
    assert brief.is_file()

    import json
    data = json.loads(status.read_text(encoding="utf-8"))
    # the skeleton is a valid v2 DRAFT starting point (schema_version + state + role)
    assert data["schema_version"] == "agentic-wp-status/v2"
    assert data["state"] == "DRAFT"
    assert data["role"] == "Developer"
    assert "consult" in data


def test_init_rerun_refuses_without_force(tmp_path):
    assert _init(tmp_path)[0] == 0
    rc, _out, err = _init(tmp_path)
    assert rc == 1
    assert "INIT_REFUSED" in err


def test_init_refuse_path_writes_nothing(tmp_path):
    # A single pre-existing managed file must abort init BEFORE any write:
    # no config, no other contracts, no skeleton dirs, no .gitignore mutation.
    (tmp_path / "AGENTS.md").write_text("pre-existing\n", encoding="utf-8")
    rc, _out, err = _init(tmp_path)
    assert rc == 1
    assert "INIT_REFUSED: AGENTS.md" in err
    # nothing else created
    assert not (tmp_path / ".agentic" / "config.toml").exists()
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / "docs" / "agentic" / "OPERATING_MODEL.md").exists()
    assert not (tmp_path / ".agentic" / "locks").exists()
    assert not (tmp_path / "docs" / "plans").exists()
    assert not (tmp_path / ".gitignore").exists()
    # the pre-existing file is untouched
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "pre-existing\n"


def test_init_force_overwrites(tmp_path):
    assert _init(tmp_path)[0] == 0
    (tmp_path / "AGENTS.md").write_text("hand-edited\n", encoding="utf-8")
    rc, out, _ = _init(tmp_path, "--force")
    assert rc == 0, out
    assert "hand-edited" not in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_init_gitignore_not_duplicated(tmp_path):
    assert _init(tmp_path)[0] == 0
    assert _init(tmp_path, "--force")[0] == 0
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert gi.count(init_cmd.GITIGNORE_LOCKS_LINE) == 1


def test_check_in_sync_after_init(tmp_path):
    assert _init(tmp_path)[0] == 0
    rc, out = _check(tmp_path)
    assert rc == 0
    assert out.count("IN_SYNC") == 3
    assert "CONFIG_DRIFT" not in out


def test_check_config_drift(tmp_path):
    assert _init(tmp_path)[0] == 0
    cfg = tmp_path / ".agentic" / "config.toml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            'adapter = "codex"', 'adapter = "gemini"'
        ),
        encoding="utf-8",
    )
    rc, out = _check(tmp_path)
    assert rc == contract_cmd.DRIFT_RC
    assert "CONFIG_DRIFT" in out


def test_check_template_outdated(tmp_path):
    assert _init(tmp_path)[0] == 0
    agents = tmp_path / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    stale = text.replace(
        "template_version={}".format(contract_render.CONTRACT_TEMPLATE_VERSION),
        "template_version=0",
        1,
    )
    agents.write_text(stale, encoding="utf-8")
    rc, out = _check(tmp_path)
    assert rc == contract_cmd.DRIFT_RC
    assert "TEMPLATE_OUTDATED" in out


def test_diff_prints_then_apply_restores_in_sync(tmp_path):
    assert _init(tmp_path)[0] == 0
    cfg = tmp_path / ".agentic" / "config.toml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            'adapter = "codex"', 'adapter = "gemini"'
        ),
        encoding="utf-8",
    )
    # drift present -> diff prints a non-empty change
    rc, out, _ = _diff(tmp_path)
    assert rc == 0
    assert "CONTRACT_DIFF:" in out
    assert "changed" in out

    # apply writes back + re-stamps
    rc, out, _ = _diff(tmp_path, "--apply")
    assert rc == 0
    assert "CONTRACT_APPLIED:" in out

    rc, out = _check(tmp_path)
    assert rc == 0
    assert out.count("IN_SYNC") == 3


def test_diff_unchanged_when_in_sync(tmp_path):
    assert _init(tmp_path)[0] == 0
    rc, out, _ = _diff(tmp_path)
    assert rc == 0
    assert out.count("unchanged") == 3
    assert "changed" not in out.replace("unchanged", "")


def test_check_without_config_is_usage_error(tmp_path):
    rc, _ = _check(tmp_path)
    assert rc == 2


def test_seed_config_from_file(tmp_path):
    seed = tmp_path / "seed.toml"
    seed.write_text(
        '[project]\niterations_dir = "docs/plans"\n[roles]\nconsultant = "codex"\n',
        encoding="utf-8",
    )
    rc, out, _ = _init(tmp_path, "--config", str(seed))
    assert rc == 0, out
    assert 'consultant = "codex"' in (
        tmp_path / ".agentic" / "config.toml"
    ).read_text(encoding="utf-8")
    assert _check(tmp_path)[0] == 0

"""Tests for WP-07: `agentic init` scaffolds the optional .githooks pre-push
gate trigger without enabling it or overwriting user content.

All filesystem effects are confined to pytest tmp_path; the repo's own hooks are
never touched.
"""
import io
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import cli, init_cmd


def _init(tmp_path, *extra):
    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = cli.main(["init", "--dir", str(tmp_path), "--non-interactive", *extra])
    return rc, buf.getvalue(), err.getvalue()


def test_init_writes_prepush_and_install_script(tmp_path):
    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    pre_push = tmp_path / init_cmd.GITHOOKS_REL
    install = tmp_path / init_cmd.INSTALL_SH_REL
    assert pre_push.is_file()
    assert install.is_file()

    # Both are executable so the user can run the hook and ./install.sh directly.
    assert (pre_push.stat().st_mode & 0o111) != 0
    assert (install.stat().st_mode & 0o111) != 0

    install_text = install.read_text(encoding="utf-8")
    assert "git config core.hooksPath .githooks" in install_text


def test_init_does_not_auto_enable_hooks_path(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    # init lays files down but must never run `git config`; the hooksPath value
    # stays unset until the user explicitly runs install.sh.
    r = subprocess.run(
        ["git", "-C", str(tmp_path), "config", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)


def test_init_preserves_existing_hook_and_reports_conflict(tmp_path):
    pre_push = tmp_path / ".githooks" / "pre-push"
    pre_push.parent.mkdir(parents=True)
    custom = "#!/usr/bin/env bash\necho user-custom\n"
    pre_push.write_text(custom, encoding="utf-8")
    pre_push.chmod(0o755)

    rc, out, err = _init(tmp_path)
    assert rc == 0, out

    # The user's custom hook is untouched.
    assert pre_push.read_text(encoding="utf-8") == custom
    assert "INIT_HOOK_CONFLICT" in err
    assert init_cmd.GITHOOKS_REL in err

    # install.sh is a separate generated file and is still scaffolded.
    assert (tmp_path / init_cmd.INSTALL_SH_REL).is_file()


def test_init_preserves_existing_install_script(tmp_path):
    install = tmp_path / "install.sh"
    install.write_text("#!/usr/bin/env bash\necho custom installer\n", encoding="utf-8")

    rc, out, err = _init(tmp_path)
    assert rc == 0, out
    assert install.read_text(encoding="utf-8") == "#!/usr/bin/env bash\necho custom installer\n"
    assert "INIT_HOOK_CONFLICT" in err
    # The hook is still scaffolded even though install.sh already existed.
    assert (tmp_path / init_cmd.GITHOOKS_REL).is_file()


def test_prepush_template_delegates_to_gate_runner_pre_review(tmp_path):
    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    text = (tmp_path / init_cmd.GITHOOKS_REL).read_text(encoding="utf-8")

    # The hook must call the unified gate runner for stage=pre_review, not
    # re-implement gate decision logic.
    assert "gate-runner.sh" in text
    assert "pre_review" in text
    assert '"$runner" "$status_file" pre_review' in text
    # The framework-installed equivalent entry delegates to the engine.
    assert "agentic_loop.runner.gate_runner" in text
    assert "--stage pre_review" in text


def test_prepush_template_fail_closed_when_active_wp_but_runner_missing(tmp_path):
    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    text = (tmp_path / init_cmd.GITHOOKS_REL).read_text(encoding="utf-8")

    # No active WP: ordinary pushes stay skipped (exit 0). This branch must not
    # be changed into a block for a plain push.
    no_active_idx = text.index("PRE_PUSH_SKIP: no active work-package status")
    no_active_block = text[no_active_idx:]
    runner_lookup_idx = no_active_block.index('runner="$repo_root')
    assert "exit 0" in no_active_block[:runner_lookup_idx]
    assert "exit 2" not in no_active_block[:runner_lookup_idx]

    # Active WP + both runner entry points missing: fail closed (exit 2). The
    # message must name the active WP and both missing runner entry points.
    fail_idx = text.index("PRE_PUSH_FAIL:")
    fail_block = text[fail_idx:]
    base_ref_idx = fail_block.index("base_ref=")
    assert "exit 2" in fail_block[:base_ref_idx]
    assert "exit 0" not in fail_block[:base_ref_idx]
    assert "active work-package" in fail_block[:base_ref_idx]
    assert "$status_file" in fail_block[:base_ref_idx]
    assert "scripts/agentic/gate-runner.sh" in fail_block[:base_ref_idx]
    assert "agentic_loop.runner.gate_runner" in fail_block[:base_ref_idx]


def test_prepush_template_resolves_worktree_toplevel_not_common_dir(tmp_path):
    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    text = (tmp_path / init_cmd.GITHOOKS_REL).read_text(encoding="utf-8")

    # repo_root must be the toplevel of the worktree being pushed, so a
    # linked-worktree push discovers the status/runner in the worktree copy
    # rather than the main repository. Using dirname(git-common-dir) resolves to
    # the MAIN repo root in a linked worktree and is the defect this guards.
    assert 'repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"' in text
    assert "--git-common-dir" not in text
    assert 'dirname "$(cd "$_gcd"' not in text


def test_prepush_hook_targets_current_worktree_status_in_linked_worktree(tmp_path):
    """Behavioral guard: in a linked worktree the hook must discover the status
    that lives in the worktree copy and exec the runner, not resolve against the
    main repo (which would miss the status and wrongly skip the push)."""
    main = tmp_path / "main"
    main.mkdir()
    run = lambda *a, **k: subprocess.run(a, check=True, capture_output=True, text=True, **k)
    run("git", "init", "-q", "-b", "main", str(main))
    run("git", "-C", str(main), "config", "user.email", "t@t")
    run("git", "-C", str(main), "config", "user.name", "t")
    (main / "seed").write_text("seed\n", encoding="utf-8")
    run("git", "-C", str(main), "add", "-A")
    run("git", "-C", str(main), "commit", "-qm", "seed")

    # Add a linked worktree on a feature branch, then scaffold the hook INTO the
    # worktree (the copy being pushed).
    wt = tmp_path / "wt"
    branch = "feat/wp-demo"
    run("git", "-C", str(main), "worktree", "add", "-q", "-b", branch, str(wt))
    rc, out, _ = _init(wt)
    assert rc == 0, out

    # The status for this branch lives in the WORKTREE copy only.
    status = wt / "docs" / "plans" / "iter" / "work-packages" / "WP.status.json"
    status.parent.mkdir(parents=True)
    import json
    status.write_text(json.dumps({
        "state": "READY_FOR_REVIEW",
        "git": {"branch": branch, "base_branch": "main"},
    }), encoding="utf-8")

    # A fake gate-runner records the status path it was handed, in the worktree.
    runner = wt / "scripts" / "agentic" / "gate-runner.sh"
    runner.parent.mkdir(parents=True)
    sentinel = wt / "runner-was-called.txt"
    runner.write_text(
        "#!/usr/bin/env bash\nprintf '%s' \"$1\" > '{}'\nexit 0\n".format(sentinel),
        encoding="utf-8",
    )
    runner.chmod(0o755)

    hook = wt / ".githooks" / "pre-push"
    assert hook.is_file()
    r = subprocess.run(
        ["bash", str(hook)], cwd=str(wt), capture_output=True, text=True,
    )
    # Hook must have hit the runner (exit 0 from fake), not skipped.
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "PRE_PUSH_SKIP" not in r.stderr, r.stderr
    assert sentinel.is_file(), r.stderr
    # And it handed the runner the worktree copy's status, not a main-repo path.
    handed = sentinel.read_text(encoding="utf-8")
    assert handed == str(status), handed


def test_init_does_not_touch_claude_settings(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    seeded = '{"seed": true}\n'
    settings.write_text(seeded, encoding="utf-8")

    rc, out, _ = _init(tmp_path)
    assert rc == 0, out

    assert settings.read_text(encoding="utf-8") == seeded
    assert not (tmp_path / ".claude" / "settings.local.json").exists()

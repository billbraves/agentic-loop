"""WP-02 thin shell entry wiring: ``gate-runner.sh`` must pass ``--status``.

Finding #1 (round-2 rework): the shell accepted and validated
``<work-package-status.json>`` but never forwarded it to the runner, so the
``gates[]`` write path (``write_gates_to_status``) was structurally unreachable
from the shell entry. This test pins the fix at the shell boundary.

The test runs the real ``scripts/agentic/gate-runner.sh`` against a temporary git
repo + temporary status.json, with a stub ``python3`` on ``PATH`` that:

- fakes ``agentic_loop.validate_wp_status`` (exit 0 / base branch),
- records the exact ``agentic_loop.runner.gate_runner`` argv, and
- writes a ``gates[]`` key back into the ``--status`` file (mirroring the real
  runner's read-modify-write).

Together with ``test_gate_runner.py::test_write_gates_to_status`` (which covers
the real ``write_gates_to_status``), this proves the shell actually forwards the
status path so ``gates[]`` can land in the validated status file.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _resolve_wrapper(name: str) -> Path:
    """Locate a wrapper shell in either layout.

    Prefers the bundled copy under this package (parents[1] = package root),
    falling back to the monorepo dogfood copy under ``scripts/agentic/``
    (parents[3] = monorepo root). Runnable both inside the monorepo and in the
    standalone extracted repo.
    """
    here = Path(__file__).resolve()
    bundled = here.parents[1] / "src" / "agentic_loop" / "wrappers" / name
    if bundled.is_file():
        return bundled
    return here.parents[3] / "scripts" / "agentic" / name


STUB_PYTHON3 = """#!/usr/bin/env bash
# Stub python3 for the gate-runner.sh wiring test.
{
  printf 'CALL:'
  printf ' <%s>' "$@"
  printf '\\n'
} >> "${STUB_ARGS_FILE:?}"

module=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "-m" ]]; then
    module="$arg"
  fi
  prev="$arg"
done

case "$module" in
  agentic_loop.validate_wp_status)
    field=0
    for arg in "$@"; do
      if [[ "$field" == "1" ]]; then
        printf '%s\\n' "main"
        exit 0
      fi
      if [[ "$arg" == "--field" ]]; then
        field=1
      fi
    done
    exit 0
    ;;
  agentic_loop.runner.gate_runner)
    status=""
    prev=""
    for arg in "$@"; do
      if [[ "$prev" == "--status" ]]; then
        status="$arg"
      fi
      prev="$arg"
    done
    if [[ -n "$status" ]]; then
      printf '%s\\n' \
        '{"work_package_id":"WP-02","git":{"base_branch":"main"},"gates":[{"name":"stub","kind":"command","stage":"pre_review","decision":"PASS","blocking":true,"detail":"stub"}]}' \
        > "$status"
    fi
    printf '%s\\n' '{}'
    exit 0
    ;;
esac
exit 0
"""


def _init_git_repo(root: Path) -> None:
    """Create a git repo with a committed ``main`` branch so the shell's
    base-ref resolution and changed-path plumbing succeed."""
    init = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=root, capture_output=True, text=True,
    )
    if init.returncode != 0:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=root, check=True, capture_output=True,
        )
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=root, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=root, check=True, capture_output=True,
    )
    (root / "tracked.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=root, check=True, capture_output=True,
    )


def test_shell_entry_passes_status_and_writes_gates(tmp_path):
    shell = _resolve_wrapper("gate-runner.sh")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python3"
    stub.write_text(STUB_PYTHON3, encoding="utf-8")
    stub.chmod(0o755)

    _init_git_repo(tmp_path)

    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps({"work_package_id": "WP-02", "git": {"base_branch": "main"}}),
        encoding="utf-8",
    )
    args_log = tmp_path / "args.log"
    args_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_ARGS_FILE"] = str(args_log)

    proc = subprocess.run(
        ["bash", str(shell), str(status_file), "pre_review"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    # The runner invocation must forward --status <status_file>.
    lines = args_log.read_text(encoding="utf-8").splitlines()
    runner_lines = [ln for ln in lines if "agentic_loop.runner.gate_runner" in ln]
    assert runner_lines, f"runner was not invoked; calls: {lines}"
    runner_call = runner_lines[-1]
    assert "--status" in runner_call
    assert str(status_file) in runner_call
    assert "--stage" in runner_call and "pre_review" in runner_call

    # After the shell entry, the validated status.json carries a gates[] key.
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert "gates" in data
    assert data["gates"][0]["name"] == "stub"

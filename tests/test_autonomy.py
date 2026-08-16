"""Tests for the [autonomy] policy engine (agentic autonomy)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import autonomy as au  # noqa: E402


# --- pure decide() semantics -------------------------------------------------


def test_decide_always_stop_wins_even_in_ultra():
    cfg = {"default_mode": "ultra", "always_stop": ["push"], "ultra_auto": ["push"]}
    assert au.decide("push", cfg) == "STOP"


def test_decide_ultra_auto_approved_in_ultra():
    cfg = {"default_mode": "ultra", "always_stop": [], "ultra_auto": ["finalize_merge"]}
    assert au.decide("finalize_merge", cfg) == "AUTO"


def test_decide_ask_mode_stops_even_for_ultra_auto_action():
    cfg = {"default_mode": "ask", "always_stop": [], "ultra_auto": ["finalize_merge"]}
    assert au.decide("finalize_merge", cfg) == "STOP"


def test_decide_unknown_action_stops_fail_closed():
    cfg = {"default_mode": "ultra", "always_stop": [], "ultra_auto": ["local_edit"]}
    assert au.decide("bogus_action", cfg) == "STOP"


def test_known_actions_and_soft_limit_signals_disjoint():
    assert au.known_actions().isdisjoint(au.SOFT_LIMIT_SIGNALS)


def test_is_soft_limit_signal_pure():
    cfg = {"soft_limit_signals": ["frozen_hard", "rework_twice", "circuit_breaker"]}
    assert au.is_soft_limit_signal("frozen_hard", cfg) is True
    assert au.is_soft_limit_signal("circuit_breaker", cfg) is True
    assert au.is_soft_limit_signal("bogus", cfg) is False
    assert au.is_soft_limit_signal("frozen_hard", {}) is False


def test_cli_signal_not_configured(repo):
    res = _run_signal(repo, "circuit_breaker")
    assert res.returncode == 0
    assert "SOFT_LIMIT_NOT_CONFIGURED circuit_breaker" in res.stdout


def test_cli_signal_enabled_by_default_soft_limit_signals(repo):
    # [autonomy] present but soft_limit_signals omitted -> merges DEFAULT_AUTONOMY's
    # default list, which declares circuit_breaker.
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ask"\n', encoding="utf-8"
    )
    res = _run_signal(repo, "circuit_breaker")
    assert res.returncode == 0
    assert "SOFT_LIMIT_ENABLED circuit_breaker" in res.stdout


def test_cli_signal_disabled_when_not_declared(repo):
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ask"\nsoft_limit_signals = ["frozen_hard"]\n',
        encoding="utf-8",
    )
    res = _run_signal(repo, "circuit_breaker")
    assert res.returncode == au.STOP_RC
    assert "SOFT_LIMIT_DISABLED circuit_breaker" in res.stdout


def test_redispatch_soft_limit_note(repo):
    from agentic_loop.redispatch import _soft_limit_note

    # no [autonomy] -> not-configured
    assert _soft_limit_note("circuit_breaker", repo) == "not-configured"

    # [autonomy] with default soft_limit_signals -> enabled
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ask"\n', encoding="utf-8"
    )
    assert _soft_limit_note("circuit_breaker", repo) == "enabled"

    # [autonomy] excluding circuit_breaker -> disabled
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ask"\nsoft_limit_signals = ["frozen_hard"]\n',
        encoding="utf-8",
    )
    assert _soft_limit_note("circuit_breaker", repo) == "disabled"


# --- CLI over a tmp git repo -------------------------------------------------


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *a], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    _git(r, "config", "user.email", "t@e.com")
    _git(r, "config", "user.name", "T")
    (r / ".agentic").mkdir()
    (r / "seed.txt").write_text("s\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")
    _git(r, "branch", "-M", "main")
    return r


def _run(repo: Path, action: str):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "agentic_loop.autonomy", action],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )


def _run_signal(repo: Path, signal: str):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "agentic_loop.autonomy", "signal", signal],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )


def test_cli_not_configured_returns_not_configured(repo):
    res = _run(repo, "finalize_merge")
    assert res.returncode == 0
    assert "AUTONOMY_NOT_CONFIGURED finalize_merge" in res.stdout


def test_cli_ask_mode_stops(repo):
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ask"\n', encoding="utf-8"
    )
    res = _run(repo, "finalize_merge")
    assert res.returncode == au.STOP_RC
    assert "AUTONOMY_STOP finalize_merge" in res.stdout


def test_cli_ultra_auto_approves(repo):
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ultra"\nultra_auto = ["finalize_merge"]\n',
        encoding="utf-8",
    )
    res = _run(repo, "finalize_merge")
    assert res.returncode == 0
    assert "AUTONOMY_AUTO finalize_merge" in res.stdout


def test_cli_always_stop_wins_in_ultra(repo):
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ultra"\nultra_auto = ["push"]\nalways_stop = ["push"]\n',
        encoding="utf-8",
    )
    res = _run(repo, "push")
    assert res.returncode == au.STOP_RC
    assert "AUTONOMY_STOP push" in res.stdout


# --- gate engine hard-wire (merge_gate) -------------------------------------


def test_gate_enforce_autonomy_opt_in(tmp_path, monkeypatch):
    from agentic_loop.gate import _enforce_autonomy

    cfg = tmp_path / ".agentic" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)

    # no [autonomy] -> no-op (backward compatible)
    _enforce_autonomy(tmp_path)

    # ask mode -> STOP (SystemExit code 3)
    cfg.write_text('[autonomy]\ndefault_mode = "ask"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        _enforce_autonomy(tmp_path)
    assert ei.value.code == au.STOP_RC

    # human-approved override -> proceeds
    monkeypatch.setenv("AGENTIC_AUTONOMY_APPROVE", "1")
    _enforce_autonomy(tmp_path)
    monkeypatch.delenv("AGENTIC_AUTONOMY_APPROVE")

    # ultra + merge_gate in ultra_auto -> proceeds
    cfg.write_text(
        '[autonomy]\ndefault_mode = "ultra"\nultra_auto = ["merge_gate"]\n',
        encoding="utf-8",
    )
    _enforce_autonomy(tmp_path)

    # ultra + merge_gate in always_stop -> hard STOP
    cfg.write_text(
        '[autonomy]\ndefault_mode = "ultra"\nultra_auto = ["merge_gate"]\n'
        'always_stop = ["merge_gate"]\n',
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as ei:
        _enforce_autonomy(tmp_path)
    assert ei.value.code == au.STOP_RC


def test_mode_show_and_switch(repo):
    (repo / ".agentic" / "config.toml").write_text(
        '[autonomy]\ndefault_mode = "ultra"\n', encoding="utf-8"
    )
    # 显示
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    res = subprocess.run(
        [sys.executable, "-m", "agentic_loop.autonomy", "mode"],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )
    assert "AUTONOMY_MODE ultra" in res.stdout

    # 切 ask
    res = subprocess.run(
        [sys.executable, "-m", "agentic_loop.autonomy", "mode", "ask"],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )
    assert res.returncode == 0
    assert "AUTONOMY_MODE_SET ask" in res.stdout
    assert 'default_mode = "ask"' in (repo / ".agentic" / "config.toml").read_text()

    # 切回 ultra
    subprocess.run(
        [sys.executable, "-m", "agentic_loop.autonomy", "mode", "ultra"],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )
    assert 'default_mode = "ultra"' in (repo / ".agentic" / "config.toml").read_text()


def test_mode_set_creates_section_if_absent(repo):
    # 没有 [autonomy] 段时，mode 切换应追加该段
    (repo / ".agentic" / "config.toml").write_text(
        '[project]\niterations_dir = "docs/plans"\n', encoding="utf-8"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    res = subprocess.run(
        [sys.executable, "-m", "agentic_loop.autonomy", "mode", "ultra"],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )
    assert res.returncode == 0
    text = (repo / ".agentic" / "config.toml").read_text()
    assert "[autonomy]" in text
    assert 'default_mode = "ultra"' in text

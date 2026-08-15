from __future__ import annotations

import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import bootstrap_cmd

PROVIDERS_CONFIG = """\
[providers.deepseek]
anthropic_base_url = "https://api.deepseek.com/anthropic"
openai_base_url    = "https://api.deepseek.com/v1"
api_key_env        = "DEEPSEEK_API_KEY"
identity_model     = "deepseek-v4-pro"
[providers.deepseek.selectors]
kimi   = "deepseek/v4-pro"
codex  = "deepseek-v4-pro"
claude = "deepseek-v4-pro"

[roles]
developer  = { adapter = "kimi",   provider = "deepseek" }
reviewer   = { adapter = "claude", provider = "deepseek" }
consultant = { adapter = "codex",  provider = "deepseek" }
"""


def _mk_repo(tmp_path, config_text):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    a = tmp_path / ".agentic"
    a.mkdir()
    (a / "config.toml").write_text(config_text, encoding="utf-8")
    return tmp_path


def _fake_bin(dir_: Path, name: str, body: str) -> str:
    p = dir_ / name
    p.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body), encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_plan_marks_missing_for_install(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    monkeypatch.setattr(bootstrap_cmd.shutil, "which", lambda n: None)  # nothing installed
    plan = bootstrap_cmd.plan_bootstrap(repo, adapter_names=["claude", "kimi", "codex"])
    assert set(plan.to_install) == {"claude", "kimi", "codex"}


def test_plan_marks_present_for_probe_not_install(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    monkeypatch.setattr(bootstrap_cmd.shutil, "which", lambda n: "/usr/bin/" + n)
    plan = bootstrap_cmd.plan_bootstrap(repo, adapter_names=["claude", "kimi", "codex"])
    assert plan.to_install == []
    assert {n for n, _b in plan.to_probe} == {"claude", "kimi", "codex"}


def test_missing_key_reported(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(bootstrap_cmd.shutil, "which", lambda n: "/usr/bin/" + n)
    plan = bootstrap_cmd.plan_bootstrap(repo, adapter_names=["claude", "kimi", "codex"])
    assert "DEEPSEEK_API_KEY" in plan.missing_key


def test_dry_run_prints_no_install_no_sentinel(tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    monkeypatch.setattr(bootstrap_cmd.shutil, "which", lambda n: None)
    monkeypatch.chdir(repo)
    called = {"install": False, "probe": False}
    monkeypatch.setattr(bootstrap_cmd, "_run_install",
                        lambda *a, **k: called.__setitem__("install", True))
    monkeypatch.setattr(bootstrap_cmd, "_probe_one",
                        lambda *a, **k: called.__setitem__("probe", True))
    rc = bootstrap_cmd.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert called["install"] is False           # never installs
    assert called["probe"] is False             # never sends sentinel
    assert "brew install --cask codex" in out
    assert "npm install -g @anthropic-ai/claude-code" in out
    assert "uv tool install kimi-cli" in out


def test_installed_but_incompatible_fail_closed(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    monkeypatch.chdir(repo)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # all three "installed" but ignore injection -> probe_injection must fail.
    for n in ("claude", "kimi", "codex"):
        _fake_bin(bindir, n, 'echo "legacy, ignores injection"; exit 0\n')
    monkeypatch.setattr(bootstrap_cmd.shutil, "which",
                        lambda n: str(bindir / n) if (bindir / n).exists() else None)
    monkeypatch.setenv("CLAUDE_BIN", str(bindir / "claude"))
    monkeypatch.setenv("KIMI_BIN", str(bindir / "kimi"))
    monkeypatch.setenv("CODEX_BIN", str(bindir / "codex"))
    rc = bootstrap_cmd.main(["--yes"])
    assert rc != 0                              # fail-closed


def test_no_qoder_in_install_commands():
    assert "qoder" not in bootstrap_cmd.INSTALL_COMMANDS
    assert set(bootstrap_cmd.INSTALL_COMMANDS) == {"claude", "kimi", "codex"}


def test_missing_installs_with_yes(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path, PROVIDERS_CONFIG)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    monkeypatch.chdir(repo)
    # nothing installed -> every CLI must go through main()'s install branch
    monkeypatch.setattr(bootstrap_cmd.shutil, "which", lambda n: None)
    installed = []
    monkeypatch.setattr(bootstrap_cmd, "_run_install",
                        lambda name: (installed.append(name), 0)[1])
    # freshly-installed CLIs then pass the real-injection probe so main() reaches OK
    monkeypatch.setattr(bootstrap_cmd, "_probe_one", lambda name, binding: True)
    rc = bootstrap_cmd.main(["--yes"])
    assert rc == 0                                  # install branch ran, probe passed
    assert set(installed) == {"claude", "kimi", "codex"}  # _run_install called per missing CLI

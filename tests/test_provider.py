"""Tests for `agentic provider` switch (official <-> DeepSeek)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import provider  # noqa: E402


@pytest.fixture
def codex(tmp_path, monkeypatch):
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    monkeypatch.setattr(provider, "CODEX_CFG", cfg)
    monkeypatch.setattr(provider, "CODEX_BAK", Path(str(cfg) + ".official.bak"))
    return cfg


@pytest.fixture
def kimi(tmp_path, monkeypatch):
    cfg = tmp_path / ".kimi" / "config.toml"
    cfg.parent.mkdir(parents=True)
    monkeypatch.setattr(provider, "KIMI_CFG", cfg)
    monkeypatch.setattr(provider, "KIMI_BAK", Path(str(cfg) + ".official.bak"))
    return cfg


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_codex_deepseek_switches_stale_official_model(codex):
    # 官方 model 已从 gpt-5.5 升级为 gpt-5.6-sol：必须仍能切到 DeepSeek。
    _write(codex, 'model = "gpt-5.6-sol"\nmodel_provider = "openai"\n')
    assert provider._switch_codex_deepseek() is True
    text = codex.read_text(encoding="utf-8")
    assert 'model = "deepseek-v4-pro"' in text
    assert Path(str(codex) + ".official.bak").read_text(encoding="utf-8").strip() == "gpt-5.6-sol"


def test_codex_official_restores_from_backup(codex):
    _write(codex, 'model = "deepseek-v4-pro"\n')
    Path(str(codex) + ".official.bak").write_text("gpt-5.6-sol\n", encoding="utf-8")
    assert provider._switch_codex_official() is True
    assert 'model = "gpt-5.6-sol"' in codex.read_text(encoding="utf-8")


def test_codex_deepseek_noop_when_already_deepseek(codex):
    _write(codex, 'model = "deepseek-v4-pro"\n')
    assert provider._switch_codex_deepseek() is False


def test_codex_official_noop_without_backup(codex):
    _write(codex, 'model = "gpt-5.6-sol"\n')
    assert provider._switch_codex_official() is False


def test_kimi_deepseek_switches(kimi):
    _write(kimi, 'default_model = "kimi-code/kimi-for-coding"\n')
    assert provider._switch_kimi_deepseek() is True
    assert 'default_model = "deepseek/v4-pro"' in kimi.read_text(encoding="utf-8")


def test_main_reports_unchanged_when_noop(codex, capsys):
    _write(codex, 'model = "deepseek-v4-pro"\n')
    assert provider.main(["codex-deepseek"]) == 0
    out, err = capsys.readouterr()
    assert "未修改" in err


def test_warn_if_kimi_running(capsys, monkeypatch):
    monkeypatch.setattr(
        provider, "_running_kimi_processes", lambda: ["12345 Kimi Code"]
    )
    provider._warn_if_kimi_running()
    err = capsys.readouterr().err
    assert "kimi" in err.lower()
    assert "/model" in err


def test_no_warn_when_kimi_not_running(capsys, monkeypatch):
    monkeypatch.setattr(provider, "_running_kimi_processes", list)
    provider._warn_if_kimi_running()
    assert capsys.readouterr().err == ""


def test_main_kimi_switch_warns_when_kimi_running(kimi, capsys, monkeypatch):
    _write(kimi, 'default_model = "kimi-code/k3"\n')
    monkeypatch.setattr(
        provider, "_running_kimi_processes", lambda: ["12345 Kimi Code"]
    )
    assert provider.main(["kimi-deepseek"]) == 0
    out, err = capsys.readouterr()
    assert "kimi → DeepSeek" in out
    assert "正在运行的 kimi" in err


def test_main_kimi_switch_no_warn_when_kimi_not_running(kimi, capsys, monkeypatch):
    _write(kimi, 'default_model = "kimi-code/k3"\n')
    monkeypatch.setattr(provider, "_running_kimi_processes", list)
    assert provider.main(["kimi-deepseek"]) == 0
    out, err = capsys.readouterr()
    assert "kimi → DeepSeek" in out
    assert "正在运行的 kimi" not in err

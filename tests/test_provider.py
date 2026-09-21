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
    text = kimi.read_text(encoding="utf-8")
    assert 'default_model = "deepseek/v4-pro"' in text
    # 切换必须同时补齐 model/provider 段，否则 kimi 校验 default_model 找不到
    # 对应 model 会拒绝启动（本次故障根因）。
    assert '[models."deepseek/v4-pro"]' in text
    assert 'model = "deepseek-v4-pro"' in text
    assert "[providers.deepseek]" in text


def test_kimi_deepseek_repairs_missing_model_block(kimi, monkeypatch):
    """回归：default_model 已是 deepseek/v4-pro 但缺 model 段的坏配置。

    这是 `agentic provider kimi-deepseek` 早先留下的实际坏状态：只写了
    default_model，从未建 [models."deepseek/v4-pro"]，导致 kimi 启动即报
    `Default model deepseek/v4-pro not found in models`。修复后本函数须
    幂等补齐两段，并把「已修复」如实报告为 True（而非旧的 noop False）。
    """
    monkeypatch.setattr(provider, "_deepseek_key", lambda: "sk-test")
    _write(
        kimi,
        'default_model = "deepseek/v4-pro"\n'
        '[models."kimi-code/k3"]\n'
        'provider = "managed:kimi-code"\n'
        'model = "k3"\n'
        "max_context_size = 1048576\n"
        '[providers."managed:kimi-code"]\n'
        'type = "kimi"\n'
        'base_url = "https://api.kimi.com/coding/v1"\n'
        'api_key = ""\n',
    )
    assert provider._switch_kimi_deepseek() is True
    text = kimi.read_text(encoding="utf-8")
    assert '[models."deepseek/v4-pro"]' in text
    assert "[providers.deepseek]" in text
    # 只有一份 provider 段——已存在时不得重复追加。
    assert text.count("[providers.deepseek]") == 1


def test_kimi_deepseek_reuses_existing_provider(kimi, monkeypatch):
    """provider.deepseek 已存在时，补 model 段但不重复追加 provider。"""
    monkeypatch.setattr(provider, "_deepseek_key", lambda: "sk-test")
    _write(
        kimi,
        'default_model = "kimi-code/k3"\n'
        '[models."kimi-code/k3"]\n'
        'provider = "managed:kimi-code"\n'
        'model = "k3"\n'
        "max_context_size = 1048576\n"
        "[providers.deepseek]\n"
        'type = "openai_legacy"\n'
        'base_url = "https://api.deepseek.com/v1"\n'
        'api_key = "sk-existing"\n',
    )
    assert provider._switch_kimi_deepseek() is True
    text = kimi.read_text(encoding="utf-8")
    assert '[models."deepseek/v4-pro"]' in text
    assert text.count("[providers.deepseek]") == 1
    # 不覆盖已有 key。
    assert 'api_key = "sk-existing"' in text


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


@pytest.fixture
def claude(tmp_path, monkeypatch):
    """隔离 ~/.claude/settings.json，避免组合开关测试触碰真实文件。"""
    cfg = tmp_path / ".claude" / "settings.json"
    cfg.parent.mkdir(parents=True)
    monkeypatch.setattr(provider, "CLAUDE_CFG", cfg)
    monkeypatch.setattr(provider, "CLAUDE_BAK", Path(str(cfg) + ".official.bak"))
    return cfg


def test_main_official_executes_all_targets(codex, kimi, claude, capsys, monkeypatch):
    """回归：any(fn() for ...) 短路曾导致 codex 成功后 kimi/claude 从未执行。"""
    monkeypatch.setattr(provider, "_running_kimi_processes", list)
    _write(codex, 'model = "deepseek-v4-pro"\n')
    Path(str(codex) + ".official.bak").write_text("gpt-5.6-sol\n", encoding="utf-8")
    _write(kimi, 'default_model = "deepseek/v4-pro"\n')
    Path(str(kimi) + ".official.bak").write_text("kimi-code/k3\n", encoding="utf-8")
    _write(claude, "{}\n")
    assert provider.main(["official"]) == 0
    assert 'model = "gpt-5.6-sol"' in codex.read_text(encoding="utf-8")
    assert 'default_model = "kimi-code/k3"' in kimi.read_text(encoding="utf-8")


def test_main_official_reports_targets_without_backup(codex, kimi, claude, capsys,
                                                      monkeypatch):
    """部分成功时，未切换的 target 必须在 stderr 逐项列出并给出手动恢复指引。"""
    monkeypatch.setattr(provider, "_running_kimi_processes", list)
    _write(codex, 'model = "deepseek-v4-pro"\n')
    Path(str(codex) + ".official.bak").write_text("gpt-5.6-sol\n", encoding="utf-8")
    _write(kimi, 'default_model = "deepseek/v4-pro"\n')  # 旧版本硬编码切的，无 .bak
    _write(claude, "{}\n")  # claude 也无 .bak
    assert provider.main(["official"]) == 0
    out, err = capsys.readouterr()
    assert "已切回官方" in out  # codex 部分成功
    assert 'model = "gpt-5.6-sol"' in codex.read_text(encoding="utf-8")
    assert 'default_model = "deepseek/v4-pro"' in kimi.read_text(encoding="utf-8")
    assert "kimi 未切换" in err
    assert "claude 未切换" in err
    assert ".official.bak" in err

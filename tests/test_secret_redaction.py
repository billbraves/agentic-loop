from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.secret_redaction import redact, redact_env_value


def test_redact_replaces_secret():
    out = redact("token=sk-abc123 rest", ["sk-abc123"])
    assert "sk-abc123" not in out
    assert "***REDACTED***" in out


def test_redact_ignores_empty_secret():
    out = redact("nothing to hide", ["", None])  # type: ignore[list-item]
    assert out == "nothing to hide"


def test_redact_multiple_occurrences():
    out = redact("sk-x and again sk-x", ["sk-x"])
    assert out.count("***REDACTED***") == 2
    assert "sk-x" not in out


def test_redact_env_value(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-LEAK")
    out = redact_env_value("Authorization: Bearer sk-LEAK", "DEEPSEEK_API_KEY")
    assert "sk-LEAK" not in out
    assert "***REDACTED***" in out


def test_redact_env_value_missing_env_is_noop(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    out = redact_env_value("no key set", "DEEPSEEK_API_KEY")
    assert out == "no key set"

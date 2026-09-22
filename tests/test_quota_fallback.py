from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.quota_fallback import is_quota_error


def test_matches_chinese_quota_terms():
    assert is_quota_error("错误：账户额度不足，请充值") is True
    assert is_quota_error("套餐已用尽") is True
    assert is_quota_error("配额超限") is True


def test_matches_english_quota_terms():
    assert is_quota_error("Error: insufficient balance") is True
    assert is_quota_error("quota exceeded for this key") is True
    assert is_quota_error("HTTP 429 Too Many Requests") is True
    assert is_quota_error("payment required (402)") is True


def test_case_insensitive():
    assert is_quota_error("QUOTA EXCEEDED") is True
    assert is_quota_error("Insufficient Balance") is True


def test_negative_cases_return_false():
    assert is_quota_error("ModuleNotFoundError: no module named foo") is False
    assert is_quota_error("AssertionError: expected 3 got 4") is False
    assert is_quota_error("PROBE_OK") is False
    assert is_quota_error("") is False


def test_ambiguous_phrases_are_not_quota_errors():
    """codex rev1 finding #1：默认模式收窄后，普通错误里含 insufficient/exceeded/
    credit/billing/rate_limit/429/balance/out of 等歧义词但**无账户/额度语境**时，
    必须判为 False。否则 wrapper 会误触发 flash 重派，掩盖真实错误（AGENTS.md §7）。
    本用例是「过宽判定」变异方向的承重锁（对应 brief Acceptance tests §3）。
    """
    assert is_quota_error("test count exceeded") is False
    assert is_quota_error("insufficient permissions to read /etc/shadow") is False
    assert is_quota_error("billing module failed to import") is False
    assert is_quota_error("credit card processor returned error 500") is False
    assert is_quota_error("AssertionError: rate_limit should be 5, got 3") is False
    assert is_quota_error("port 429 is not available") is False
    assert is_quota_error("balance sheet report generated") is False
    assert is_quota_error("out of memory") is False


def test_custom_patterns_override_defaults():
    # 自定义清单生效时，默认清单不再参与匹配。
    assert is_quota_error("quota exceeded", patterns=["credit"]) is False
    assert is_quota_error("out of credit", patterns=["credit"]) is True


def test_bad_regex_pattern_is_skipped_not_raised():
    """codex rev2 finding #3：config 覆盖可能引入语法非法正则。真正的 re.error 防线
    在 is_quota_error 的 `except re.error: continue`（不是 load_quota_patterns——后者
    只读 config、不编译正则）。坏正则必须被跳过而非抛出，且同列表中合法正则仍生效。
    本用例是 INV-2「坏正则跳过」方向的承重锁：删 is_quota_error 的 except re.error
    → 本用例抛 re.error 转红（对应 brief 映射表 INV-2 与 C1 mutation-probe）。
    """
    # 坏正则 "[" 被跳过，合法正则 \bquota\b 仍命中 → True（不抛异常）
    assert is_quota_error("quota exceeded", patterns=["[", r"\bquota\b"]) is True
    # 只有坏正则、无合法命中 → False（跳过而非崩溃）
    assert is_quota_error("unrelated output", patterns=["["]) is False
    # 坏正则 "(" 跳过，合法语境正则不匹配该串 → False
    assert is_quota_error("insufficient balance", patterns=["(", r"balance\W{0,10}credit"]) is False


from agentic_loop.quota_fallback import DEFAULT_QUOTA_PATTERNS, load_quota_patterns


def _write_cfg(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / ".agentic" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body, encoding="utf-8")
    return tmp_path


def test_load_patterns_returns_defaults_when_no_config(tmp_path):
    assert load_quota_patterns(repo=tmp_path) == DEFAULT_QUOTA_PATTERNS


def test_load_patterns_reads_override(tmp_path):
    repo = _write_cfg(tmp_path, '[quota_fallback]\npatterns = ["额度", "quota", "429"]\n')
    assert load_quota_patterns(repo=repo) == ("额度", "quota", "429")


def test_load_patterns_fails_safe_on_bad_override(tmp_path):
    # patterns 非字符串列表 / 空列表 → 回落默认，绝不抛到派发主链。
    repo = _write_cfg(tmp_path, '[quota_fallback]\npatterns = []\n')
    assert load_quota_patterns(repo=repo) == DEFAULT_QUOTA_PATTERNS
    repo2 = _write_cfg(tmp_path / "b", '[quota_fallback]\npatterns = "额度"\n')
    assert load_quota_patterns(repo=repo2) == DEFAULT_QUOTA_PATTERNS


def test_load_patterns_fails_safe_on_malformed_toml(tmp_path):
    """codex rev3 finding #1：让 INV-2(a) 的 except Exception 承重变异可执行。
    现有 fails_safe_on_bad_override 只测空列表/错误类型（都是合法 TOML，走 isinstance
    fall-through，不触发 except Exception）。畸形 TOML（未闭合表头）才会让 _load_config
    的 tomllib.load 抛 TOMLDecodeError → load_quota_patterns 的 except Exception 必须
    吞掉并回落 DEFAULT，绝不抛进派发主链。承重变异：删 except Exception → 本用例转红。
    """
    repo = _write_cfg(tmp_path, '[quota_fallback\npatterns = ["额度"\n')  # 未闭合表头+未闭合数组
    assert load_quota_patterns(repo=repo) == DEFAULT_QUOTA_PATTERNS

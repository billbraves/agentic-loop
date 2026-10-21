from __future__ import annotations

import sys
import traceback
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from agentic_loop.quota_fallback import (
    CATEGORY_AUTH_CONFIG,
    CATEGORY_QUOTA,
    CATEGORY_SERVER,
    CATEGORY_TASK,
    CATEGORY_TRANSPORT,
    FALLBACK_CATEGORIES,
    classify_failure,
    is_quota_error,
)

# ---- 可回退：真实报错原文 + 中英文额度文案 ----
QUOTA_SAMPLES = [
    # 2026-10-20 实测未命中原模式表的真实 kimi 上游报错
    "403 access_terminated_error (weekly usage limit)",
    "402 Monthly request limit exceeded (reason: MONTHLY_REQUEST_COUNT)",
    # 中文
    "当前套餐额度不足，请升级",
    "API 配额已用尽",
    "账户余额不足",
    # 英文
    "You exceeded your current quota, please check your plan",
    "insufficient balance",
    "Your credit balance is too low",
    "429 Too Many Requests",
    "Rate limit exceeded, retry later",
    "weekly usage limit reached, resets on Monday",
    "402 Payment Required",
    # WP-01 consult finding 2: HTTP status-code syntax variants of an
    # explicit 429 (version / error / status wording, separators).
    "Error: HTTP 429",
    "direct tool-free finalization HTTP 429",
    "Error: HTTP/1.1 429 Too Many Requests",
    "HTTP error 429",
    "HTTP status: 429",
]

TRANSPORT_SAMPLES = [
    "Connection reset by peer",
    "[Errno 54] Connection reset by peer",
    "ConnectionRefusedError: [Errno 61] Connection refused",
    "getaddrinfo failed: nodename nor servname provided",
    "Temporary failure in name resolution",
    "ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
    "proxy CONNECT failed: tunnel connection failed",
    "HTTPSConnectionPool(host='api.example.com', port=443): Read timed out",
    "requests.exceptions.ConnectionError: connection aborted",
]

SERVER_SAMPLES = [
    "HTTP 503 Service Unavailable",
    "HTTP/1.1 502 Bad Gateway",
    "Error: 500 Internal Server Error",
    "status: 504",
    "upstream 502 bad gateway",
    # any 5xx, not only 500/502/503/504 (codex rev2 F4)
    "HTTP 507 Insufficient Storage",
    "HTTP 529 overloaded",
]

# ---- 不可回退：任务 / 鉴权 / 配置 ----
AUTH_CONFIG_SAMPLES = [
    "LLM not set",
    "Error: 401 Unauthorized",
    "403 Forbidden",
    "invalid api key",
    "FileNotFoundError: [Errno 2] No such file or directory: 'kimi'",
    "PermissionError: [Errno 13] Permission denied: '/usr/local/bin/kimi'",
    "Error: model gpt-9 not found",
    "TypeError: unexpected keyword argument 'foo'",
]

TASK_SAMPLES = [
    "3 failed, 2 passed in 1.20s",
    "ruff check failed: F401 unused import",
    "agent stopped: BLOCKED awaiting human decision",
    "assert 500 == 503",
    "server listening on port 5000",
    "Page 502 of the report could not be rendered",
    "FAILED tests/test_x.py::test_y - AssertionError",
    "exit status 1",
]


@pytest.mark.parametrize("output", QUOTA_SAMPLES)
def test_real_quota_errors_are_quota(output):
    assert classify_failure(output, 1) == CATEGORY_QUOTA
    # Legacy redispatch predicate must keep firing on the same evidence.
    assert is_quota_error(output) is True


@pytest.mark.parametrize("output", TRANSPORT_SAMPLES)
def test_transport_errors_are_transport(output):
    assert classify_failure(output, 1) == CATEGORY_TRANSPORT


@pytest.mark.parametrize("output", SERVER_SAMPLES)
def test_upstream_5xx_are_server(output):
    assert classify_failure(output, 1) == CATEGORY_SERVER


@pytest.mark.parametrize("output", AUTH_CONFIG_SAMPLES)
def test_auth_and_config_errors_are_not_fallback_eligible(output):
    assert classify_failure(output, 1) == CATEGORY_AUTH_CONFIG
    assert CATEGORY_AUTH_CONFIG not in FALLBACK_CATEGORIES


@pytest.mark.parametrize("output", TASK_SAMPLES)
def test_task_failures_are_not_fallback_eligible(output):
    assert classify_failure(output, 1) == CATEGORY_TASK
    assert CATEGORY_TASK not in FALLBACK_CATEGORIES


def test_task_failure_with_quota_word_in_test_name_stays_task():
    # Ambiguous English words alone must not trigger failover.
    assert classify_failure("assert response.status == 429", 1) == CATEGORY_TASK
    assert classify_failure("expected 402 but got 200", 1) == CATEGORY_TASK
    assert classify_failure("test_rate_limit_is_exceeded FAILED", 1) == CATEGORY_TASK


def test_exit_code_alone_never_means_infrastructure():
    # A plain non-zero exit is a task failure, not a provider failure.
    assert classify_failure("", 1) == CATEGORY_TASK
    assert classify_failure("", None) == CATEGORY_TASK
    # 127 = the shell could not exec the child: configuration, not provider.
    assert classify_failure("", 127) == CATEGORY_AUTH_CONFIG


def test_quota_beats_bare_403():
    # 403 is an auth marker, but a quota reason behind it must win.
    assert classify_failure("403 access_terminated_error (weekly usage limit)", 1) == (
        CATEGORY_QUOTA)


def test_fallback_categories_are_exactly_infrastructure():
    assert FALLBACK_CATEGORIES == {
        CATEGORY_QUOTA, CATEGORY_TRANSPORT, CATEGORY_SERVER}


def test_custom_patterns_override_defaults():
    assert classify_failure("everything is fine", 1,
                            quota_patterns=[r"everything is fine"]) == CATEGORY_QUOTA
    # A custom list fully replaces the defaults: a real quota line no longer matches.
    assert classify_failure("429 Too Many Requests", 1,
                            quota_patterns=[r"never-matches"]) == CATEGORY_TASK


def test_bad_custom_regex_does_not_crash():
    assert classify_failure("429 Too Many Requests", 1,
                            quota_patterns=["("]) == CATEGORY_TASK
    assert is_quota_error("429 Too Many Requests", ["("]) is False


def test_is_quota_error_empty_output_is_false():
    assert is_quota_error("") is False


# ---------------------------------------------------------------------------
# codex rev2 rework r1 regression matrix
#
# M8  remove the task veto                  -> test_mixed_log_task_evidence...
# M9  earliest match instead of newest line -> test_mixed_log_auth_error_wins...
# M10 bare ``access_terminated_error``      -> test_access_terminated_error...
# M11 restore ``[^\n]{0,20}``               -> test_unrelated_credit_score...
# M12 restrict 5xx to 500/502/503/504       -> SERVER_SAMPLES (507/529)
# M13 continue scanning past task evidence   -> test_multiline_pytest_log...
# M14 unanchored ``\b\d+\s+failed\b``         -> test_provider_retry_line...
# ---------------------------------------------------------------------------
MIXED_TASK_LOG = (
    "FAILED tests/test_api.py::test_retry - "
    "AssertionError: HTTP 503 Service Unavailable"
)
MIXED_AUTH_LOG = "HTTP 503 Service Unavailable; retrying\nError: 401 Unauthorized"


def test_mixed_log_task_evidence_vetoes_infrastructure_marker():
    """M8: without the task veto this line classifies ``server`` and fails over."""
    assert classify_failure(MIXED_TASK_LOG, 1) == CATEGORY_TASK
    assert is_quota_error(MIXED_TASK_LOG) is False


def test_mixed_log_newest_line_decides_the_category():
    """M9: scanning oldest-first would return ``server`` from the first line."""
    assert classify_failure(MIXED_AUTH_LOG, 1) == CATEGORY_AUTH_CONFIG


def test_server_positive_control_still_detected():
    assert classify_failure("HTTP 503 Service Unavailable", 1) == CATEGORY_SERVER
    assert classify_failure("Error: 401 Unauthorized", 1) == CATEGORY_AUTH_CONFIG


def test_access_terminated_error_requires_quota_context():
    """M10: bare ``access_terminated_error`` must not be quota."""
    # control: real upstream message carries the quota context
    assert classify_failure(
        "403 access_terminated_error (weekly usage limit)", 1) == CATEGORY_QUOTA
    assert is_quota_error("403 access_terminated_error (weekly usage limit)") is True
    # F2: an account termination is auth/config, not quota -> no failover
    disabled = "403 access_terminated_error: account disabled by administrator"
    assert classify_failure(disabled, 1) == CATEGORY_AUTH_CONFIG
    assert is_quota_error(disabled) is False
    # control: monthly request limit is still quota
    assert classify_failure(
        "402 Monthly request limit exceeded (reason: MONTHLY_REQUEST_COUNT)", 1
    ) == CATEGORY_QUOTA


def test_unrelated_credit_score_text_is_not_quota():
    """M11: ``[^\n]{0,20}`` would match ``credit score is too low``."""
    assert is_quota_error("AssertionError: credit score is too low") is False
    assert classify_failure(
        "AssertionError: credit score is too low", 1) == CATEGORY_TASK
    # genuine credit-balance wording must keep matching
    assert is_quota_error("Your credit balance is too low") is True
    assert classify_failure("Your credit balance is too low", 1) == CATEGORY_QUOTA
    assert is_quota_error("insufficient balance") is True


@pytest.mark.parametrize("output", [
    "HTTP 507 Insufficient Storage",
    "HTTP 529 overloaded",
    "HTTP 503 Service Unavailable",
])
def test_any_upstream_5xx_is_server(output):
    """M12: enumerating only 500/502/503/504 turns 507/529 red."""
    assert classify_failure(output, 1) == CATEGORY_SERVER


@pytest.mark.parametrize("output", [
    "assert 500 == 503",
    "server listening on port 5000",
])
def test_5xx_generalization_does_not_hit_bare_numbers(output):
    """F4: no bare ``5\\d\\d`` pattern; the context requirement stays."""
    assert classify_failure(output, 1) == CATEGORY_TASK


# ---------------------------------------------------------------------------
# Terminal-task semantics for multi-line logs (classifier follow-up r2)
#
# A task-evidence line is the terminal cause, not the absence of evidence: the
# newest-first scan must stop there instead of reaching back to an older
# infrastructure marker.
# ---------------------------------------------------------------------------
MULTILINE_PYTEST_LOG = (
    "print('HTTP 503 Service Unavailable')\n"
    "FAILED tests/test_api.py::test_retry - AssertionError\n"
    "3 failed, 2 passed in 1.20s"
)
MULTILINE_TRACEBACK_LOG = (
    "HTTP 503 Service Unavailable\n"
    "Traceback (most recent call last):\n"
    '  File "x.py", line 1\n'
    "AssertionError: boom"
)


def test_multiline_pytest_log_is_task_not_server():
    """M13: continuing past task evidence reaches the older ``HTTP 503``."""
    assert classify_failure(MULTILINE_PYTEST_LOG, 1) == CATEGORY_TASK
    assert CATEGORY_TASK not in FALLBACK_CATEGORIES
    # each task-evidence line is terminal on its own
    assert classify_failure(
        "HTTP 503 Service Unavailable\n"
        "FAILED tests/test_api.py::test_retry - AssertionError", 1) == CATEGORY_TASK
    assert classify_failure(
        "HTTP 503 Service Unavailable\n3 failed, 2 passed in 1.20s",
        1) == CATEGORY_TASK


def test_multiline_traceback_is_task_not_server():
    """M13: a terminal task traceback must not be masked by an earlier 503."""
    assert classify_failure(MULTILINE_TRACEBACK_LOG, 1) == CATEGORY_TASK
    assert classify_failure(
        "HTTP 503 Service Unavailable\nAssertionError: boom", 1) == CATEGORY_TASK


def test_newer_terminal_quota_line_wins_over_older_task_evidence():
    """Control: older task evidence does not veto a newer terminal quota error."""
    output = (
        "3 failed, 2 passed in 1.20s\n"
        "403 access_terminated_error (weekly usage limit)"
    )
    assert classify_failure(output, 1) == CATEGORY_QUOTA
    assert is_quota_error(output) is True
    assert CATEGORY_QUOTA in FALLBACK_CATEGORIES


def test_provider_retry_line_is_server_not_task_evidence():
    """M14: an unanchored ``\\b\\d+\\s+failed\\b`` swallows retry lines as task."""
    assert classify_failure("2 retries failed: HTTP 503", 1) == CATEGORY_SERVER
    # Only the unanchored form swallows a mid-line retry counter as task evidence.
    assert classify_failure(
        "attempt 2 failed: HTTP 503 Service Unavailable",
        1) == CATEGORY_SERVER
    assert classify_failure("HTTP 503 Service Unavailable\n2 retries failed",
                            1) == CATEGORY_SERVER
    # the real pytest summary (line-anchored) stays task evidence
    assert classify_failure("3 failed, 2 passed in 1.20s", 1) == CATEGORY_TASK
    assert classify_failure("    3 failed, 2 passed in 1.20s", 1) == CATEGORY_TASK
    # lint failures keep their task-evidence role
    assert classify_failure("ruff check failed: F401", 1) == CATEGORY_TASK


# ---------------------------------------------------------------------------
# codex consult r2 regression matrix
#
# M15 banner-decorated pytest summary       -> test_banner_decorated_pytest...
# M16 auth after 5xx on the same line       -> test_final_auth_on_same_line...
# M17 bare ``usage`` context for 403        -> test_access_terminated_error...
# M18 dropping bare ``credit`` from quota   -> test_singular_credit...
# ---------------------------------------------------------------------------
BANNER_PYTEST_LOG = (
    "E   AssertionError: boom\n"
    "captured stdout:\n"
    "HTTP 503 Service Unavailable\n"
    "==== 3 failed, 2 passed in 1.20s ===="
)


def test_banner_decorated_pytest_summary_is_terminal_task_evidence():
    """M15: ``^\\s*\\d+ failed`` misses pytest's ``==== 3 failed ====`` banner."""
    assert classify_failure(BANNER_PYTEST_LOG, 1) == CATEGORY_TASK
    assert classify_failure(
        "HTTP 503 Service Unavailable\n==== 3 failed, 2 passed ====",
        1) == CATEGORY_TASK
    assert CATEGORY_TASK not in FALLBACK_CATEGORIES


def test_final_auth_error_on_same_line_beats_earlier_5xx():
    """M16: server-before-auth ordering masks the terminal 401 on one line."""
    assert classify_failure(
        "HTTP 503 Service Unavailable; retry failed: Error: 401 Unauthorized",
        1) == CATEGORY_AUTH_CONFIG
    assert CATEGORY_AUTH_CONFIG not in FALLBACK_CATEGORIES
    # control: a pure 5xx line still falls back
    assert classify_failure("HTTP 503 Service Unavailable", 1) == CATEGORY_SERVER


def test_access_terminated_error_usage_policy_is_auth_not_quota():
    """M17: bare ``usage`` matches ``usage policy violation`` as quota."""
    policy = ("403 access_terminated_error: "
              "account disabled for usage policy violation")
    assert classify_failure(policy, 1) == CATEGORY_AUTH_CONFIG
    assert is_quota_error(policy) is False
    # controls: real quota wordings keep matching
    for message in (
        "403 access_terminated_error (weekly usage limit)",
        "access_terminated_error (quota exhausted)",
        "access_terminated_error (request limit exceeded)",
    ):
        assert is_quota_error(message) is True, message
        assert classify_failure(message, 1) == CATEGORY_QUOTA


def test_singular_credit_expressions_keep_legacy_quota_routing():
    """M18: binding ``credit`` to ``credit balance`` drops baseline hits."""
    for message in ("insufficient credit", "credit exhausted"):
        assert is_quota_error(message) is True, message
        assert classify_failure(message, 1) == CATEGORY_QUOTA
    # the r1 counterexample must stay non-quota
    assert is_quota_error("AssertionError: credit score is too low") is False


# ---------------------------------------------------------------------------
# Traceback block (codex consult r3, r4, r5)
#
# A task script that raises leaves a traceback in its output. The task failed,
# even if the exception message quotes an upstream 5xx; re-running on another
# provider cannot help and would mask the real failure. A traceback has no end
# marker, so provider-looking lines after it cannot be proven to be independent
# output (they may be a multi-line exception message). They are therefore task:
# the fail-safe direction of invariant 2.
# ---------------------------------------------------------------------------
TASK_503_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "task.py", line 3, in <module>\n'
    "    main()\n"
    "RuntimeError: HTTP 503 Service Unavailable"
)


def test_terminal_traceback_with_generic_503_is_task():
    """M20: without the block rule the RuntimeError line classifies server."""
    assert classify_failure(TASK_503_TRACEBACK, 1) == CATEGORY_TASK
    assert CATEGORY_TASK not in FALLBACK_CATEGORIES


def test_provider_looking_line_after_a_traceback_is_fail_safe_task():
    """M21: content cannot prove a later line is independent provider output."""
    for tail in (
        "403 access_terminated_error (weekly usage limit)",
        "Error: 401 Unauthorized",
        "Error: HTTP 503 Service Unavailable",
    ):
        output = (
            "Traceback (most recent call last):\n"
            '  File "task.py", line 3, in <module>\n'
            "    main()\n"
            "AssertionError: boom\n"
            f"{tail}"
        )
        assert classify_failure(output, 1) == CATEGORY_TASK, tail
        assert classify_failure(_prefixed(output), 1) == CATEGORY_TASK, tail
    assert classify_failure("lint failed", 1) == CATEGORY_TASK


# ---------------------------------------------------------------------------
# Traceback block robustness (codex consult r4, r5)
#
# r4 reproduced two ways a real task traceback still fell over:
#   1. every line carries a log prefix (``[2026-10-20 08:00:00] ``);
#   2. a legal multi-line exception message (``RuntimeError("...\\nHTTP 503")``).
# r5 showed that provider-style text inside such a message is indistinguishable
# from newer provider output, so the content-based override was removed.
# ---------------------------------------------------------------------------
def _prefixed(text: str, prefix: str = "[2026-10-20 08:00:00] ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def test_timestamped_traceback_is_task():
    """M24: prefix handling must keep a timestamped traceback terminal."""
    assert classify_failure(_prefixed(TASK_503_TRACEBACK), 1) == CATEGORY_TASK
    assert classify_failure(
        _prefixed(TASK_503_TRACEBACK, "2026-10-20T08:00:00Z "), 1
    ) == CATEGORY_TASK
    providerish = (
        "Traceback (most recent call last):\n"
        '  File "task.py", line 3, in <module>\n'
        "RuntimeError: Error: HTTP 503 Service Unavailable"
    )
    assert classify_failure(_prefixed(providerish), 1) == CATEGORY_TASK


def test_multiline_exception_message_with_503_is_task():
    """M24: the second unindented line is the exception message, not output."""
    output = (
        "Traceback (most recent call last):\n"
        '  File "task.py", line 5, in <module>\n'
        '    raise RuntimeError("task request failed\\nHTTP 503 "\n'
        '                       "Service Unavailable")\n'
        "RuntimeError: task request failed\n"
        "HTTP 503 Service Unavailable"
    )
    assert classify_failure(output, 1) == CATEGORY_TASK
    assert classify_failure(_prefixed(output), 1) == CATEGORY_TASK


def test_real_multiline_exception_with_provider_text_is_task():
    """r5 #1: a real format_exception message may quote provider syntax."""
    for message in ("Error: HTTP 503 Service Unavailable",
                    "403 access_terminated_error (weekly usage limit)"):
        try:
            raise RuntimeError("task request failed\n" + message)
        except RuntimeError:
            output = "".join(traceback.format_exception(*sys.exc_info()))
        assert classify_failure(output, 1) == CATEGORY_TASK, message
        assert classify_failure(_prefixed(output), 1) == CATEGORY_TASK, message


def test_timestamped_pytest_summary_is_task():
    """M22: the anchored summary pattern needs the log prefix stripped."""
    output = _prefixed(
        "HTTP 503 Service Unavailable\n==== 3 failed, 2 passed ====")
    assert classify_failure(output, 1) == CATEGORY_TASK
    assert classify_failure(
        _prefixed("HTTP 503 Service Unavailable\n3 failed, 2 passed"), 1
    ) == CATEGORY_TASK


# ---------------------------------------------------------------------------
# Direct-finalization path hardening (WP-01, 2026-10-21-consult-llm-failover)
#
# The gate consult runs codex with ``direct_finalization=True``; its failures
# surface as one-line exec errors. Explicit ``HTTP 429``, ``transport failure``
# and ``requires ..._API_KEY in env`` must classify quota / transport /
# auth_config respectively — while ``http_429`` test names and ``port 429``
# stay task (the http context requirement must not match across ``_``).
# ---------------------------------------------------------------------------
def test_direct_call_path_explicit_http_429_is_quota():
    """Positive control: an explicit HTTP 429 (no rate-limit wording) is quota."""
    assert classify_failure("codex exec failed (exit 1, attempt 1): Error: HTTP 429",
                            1) == CATEGORY_QUOTA
    assert classify_failure("Error: HTTP 429 Too Many Requests", 1) == CATEGORY_QUOTA
    assert is_quota_error("Error: HTTP 429") is True
    assert CATEGORY_QUOTA in FALLBACK_CATEGORIES


def test_direct_call_path_transport_failure_is_transport():
    assert classify_failure(
        "codex exec failed (exit 1, attempt 1): transport failure: "
        "URLError(error)", 1) == CATEGORY_TRANSPORT
    assert classify_failure("transport failure: connection reset by peer",
                            1) == CATEGORY_TRANSPORT


def test_direct_call_path_requires_api_key_in_env_is_auth_config():
    # auth/config: never fallback-eligible, and the env var NAME is matched,
    # never a key value.
    assert classify_failure("requires $DEEPSEEK_API_KEY in env", 1) == (
        CATEGORY_AUTH_CONFIG)
    assert classify_failure(
        "codex exec failed (exit 1, attempt 1): requires ANTHROPIC_API_KEY in env",
        1) == CATEGORY_AUTH_CONFIG
    assert CATEGORY_AUTH_CONFIG not in FALLBACK_CATEGORIES


def test_http_429_in_test_name_or_port_stays_task():
    """Negative: no http/status context — a test name or a port is not quota."""
    assert classify_failure(
        "FAILED tests/test_api.py::test_http_429_retry - AssertionError",
        1) == CATEGORY_TASK
    assert classify_failure("server listening on port 429", 1) == CATEGORY_TASK
    assert classify_failure("binding to localhost:429 ok", 1) == CATEGORY_TASK
    assert is_quota_error("test_http_429_retry") is False


def test_http_status_code_syntax_does_not_match_port_429():
    """WP-01 consult finding 2: HTTP text + ``port 429`` in one line is a
    task log (the old loose regex matched arbitrary text between ``HTTP`` and
    ``429``)."""
    line = "HTTP server listening on port 429"
    assert classify_failure(line, 1) == CATEGORY_TASK
    assert is_quota_error(line) is False
    assert CATEGORY_TASK not in FALLBACK_CATEGORIES

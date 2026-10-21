#!/usr/bin/env python3
"""Pure failure classification for developer-dispatch fallback.

Two layers, both pure string predicates (no I/O):

* ``classify_failure(output, exit_code)`` split a failed developer dispatch into
  ``quota`` / ``transport`` / ``server`` / ``auth_config`` / ``task``, scanning
  the merged log line by line newest-first. A line that carries explicit
  task-failure evidence is the **terminal cause**, so the scan returns ``task``
  right there instead of looking further back (a multi-line pytest log that
  quotes ``HTTP 503`` and then ends in ``FAILED ... AssertionError`` is a task
  failure, not a provider failure). Only the first three are
  *infrastructure* causes that may trigger a single-hop failover to the back
  LLM; ``auth_config`` and ``task`` must be reported as-is so the engine never
  masks a real failure (AGENTS.md §7).
* ``is_quota_error(output, patterns)`` is the legacy quota-only predicate kept
  for ``agentic redispatch`` (zero behavioural regression); it now delegates to
  the same quota pattern table.

``load_quota_patterns`` reads an optional project-config override and fails safe
to the built-in defaults. Neither imports git/subprocess nor touches status; the
dispatch layer (redispatch / dispatch) owns all side effects.

Trust boundary (brief rev7 §R2a): custom patterns come from the project config
and are treated as operator-trusted; never inject untrusted/user-controlled
regexes into them (no scan-window limit is imposed on full-text re.search).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Sequence

CATEGORY_QUOTA = "quota"
CATEGORY_TRANSPORT = "transport"
CATEGORY_SERVER = "server"
CATEGORY_AUTH_CONFIG = "auth_config"
CATEGORY_TASK = "task"

#: Causes the caller MAY answer with one hop to the back LLM. Everything else
#: (auth/config/task) is reported unchanged, never retried on another provider.
FALLBACK_CATEGORIES: frozenset[str] = frozenset(
    {CATEGORY_QUOTA, CATEGORY_TRANSPORT, CATEGORY_SERVER}
)

# 大小写不敏感；覆盖中英常见额度措辞 + HTTP 429/402。正向命中才触发回退，
# 避免把普通失败（编译/测试错误）误判为额度问题而掩盖真实错误（AGENTS.md §7）。
# codex rev1 finding #1：ambiguous 词（insufficient/exceeded/credit/billing/rate.?limit）
# 必须与账户/额度名词共现，不得裸匹配；429/402 也需与额度/付费语境共现，
# 避免命中端口号/行数。收窄后仍保留中文语义明确词的裸匹配（额度/配额/套餐/余额不足）。
DEFAULT_QUOTA_PATTERNS: tuple[str, ...] = (
    # 中文：语义明确，保留裸匹配
    r"额度", r"配额", r"套餐", r"余额不足",
    # 英文：quota 语义明确，保留裸匹配
    r"\bquota\b",
    # 英文：ambiguous 形容词/动词必须与账户/额度名词紧邻共现。
    # 恢复 baseline 的 ``\W{0,10}`` / ``\W{0,20}``（codex rev2 F3）：``[^\n]`` 会跨过
    # 任意单词，令 ``AssertionError: credit score is too low`` 误判额度，改变
    # ``agentic redispatch`` 路由。``\W`` 不跨词，故裸 ``credit`` 仍不会命中
    # ``credit score is too low``（``score is`` 是词），同时保留 baseline 对
    # ``insufficient credit`` / ``credit exhausted`` 的识别（codex r2 blocking #4）。
    r"(insufficient|exceeded|exhausted|depleted|out of|no remaining|used up|not enough)\W{0,10}(balance|credit|credits|funds|quota|allowance|budget|subscription)",
    r"(balance|credit|credits|funds|quota|allowance|budget|subscription)\W{0,20}(insufficient|exceeded|exhausted|depleted|too low|not enough|used up|out of|empty|zero)",
    # ``credit balance`` 句式（系动词夹在中间，上面的紧邻模式够不着）：
    # ``Your credit balance is too low`` 是真实上游原文，必须保持命中。
    r"\bcredit\s+balance\b[^\n]{0,20}\b(too\s+low|low|insufficient|exhausted|exceeded|depleted|empty|zero|not\s+enough)\b",
    # HTTP 状态码 + 额度/付费语境（避免 429 命中端口号、402 命中行号）
    # 直接调用路径的显式 ``HTTP 429``：无 “too many requests” 文案时也须识别为额度。
    # HTTP 与 429 之间只允许：可选版本号（``HTTP/1.1``）、可选 ``error``/
    # ``status``/``status code``、可选分隔符（空白/``:``/``-``/``=``）——
    # HTTP 状态码语法，不得夹任意文本（WP-01 consult finding 2）：
    # ``HTTP server listening on port 429`` 是任务日志，不是额度。
    # ``http_429`` 测试名不算额度（``\bhttp\b`` 不跨 ``_``）。
    r"\bhttp(?:/\d(?:\.\d+)?)?(?:\s+(?:error|status(?:\s+code)?))?(?:\s*[:\-=]?\s*)\b429\b",
    r"\b429\b.{0,80}(too many requests|rate.?limit|quota|usage)",
    r"(too many requests|rate.?limit).{0,80}\b429\b",
    r"\b402\b.{0,80}(payment|billing|quota|balance|credit|subscription)",
    r"(payment|billing).{0,20}\b402\b",
    # 明确的付费/订阅/限速短语
    r"payment\s+required",
    r"too\s+many\s+requests",
    r"rate.?limit\s+(exceeded|reached|hit|exhausted)",
    r"(subscription|payment)\s+(expired|overdue|failed|required)",
    r"weekly.{0,15}(usage|quota|limit).{0,25}(reached|exceeded|reset)",
    r"daily.{0,15}(usage|quota|limit).{0,25}(reached|exceeded|reset)",
    # 真实上游报错（2026-10-20 实测未命中原表的原文）：
    #   ``403 access_terminated_error (weekly usage limit)``
    #   ``402 Monthly request limit exceeded (reason: MONTHLY_REQUEST_COUNT)``
    # codex rev2 F2：``access_terminated_error`` 单独出现只是**鉴权终止**，
    # 必须同一行 80 字符内带**额度语义**才算额度。裸 ``usage`` 不够：
    # ``403 access_terminated_error: account disabled for usage policy violation``
    # 是账户被禁用，不是额度耗尽（codex r2 blocking #3）。
    r"access_terminated_error[^\n]{0,80}(?:weekly|monthly|daily)[^\n]{0,40}(?:usage|quota|request|limit|credit|balance)",
    r"access_terminated_error[^\n]{0,80}(?:usage|quota|request)\s+limit",
    r"access_terminated_error[^\n]{0,80}(?:quota|balance|credits?)[^\n]{0,20}(?:exceeded|exhausted|reached|insufficient|depleted|empty|zero)",
    r"\bmonthly_request_count\b",
    r"(weekly|monthly|daily)\s+(usage|quota|request)\s+limit",
    r"(usage|request)\s+limit\s+(reached|exceeded|hit)",
)

# 传输层不可用：连接被重置/拒绝、DNS、TLS、代理、连接超时。
# 只匹配**连接语境**的 timeout，裸 "timed out" 不匹配——pytest 超时属于任务失败。
DEFAULT_TRANSPORT_PATTERNS: tuple[str, ...] = (
    r"connection\s+reset(\s+by\s+peer)?",
    r"\beconnreset\b",
    r"connection\s+(refused|aborted|closed|error|broken)",
    r"\beconnrefused\b",
    r"\bepipe\b",
    r"broken\s+pipe",
    r"remote\s+end\s+closed\s+connection",
    r"network\s+is\s+unreachable",
    r"no\s+route\s+to\s+host",
    r"temporary\s+failure\s+in\s+name\s+resolution",
    r"name\s+or\s+service\s+not\s+known",
    r"nodename\s+nor\s+servname",
    r"getaddrinfo\s+failed",
    r"(could\s+not|failed\s+to)\s+resolve\s+host",
    r"\bdns\b[^\n]{0,40}(fail|error|resolve|lookup|timeout|timed\s*out)",
    r"(ssl|tls)[^\n]{0,40}(error|fail|handshake|alert|verify)",
    r"certificate\s+verif(y|ication)\s+failed",
    r"certificate_verify_failed",
    r"\bssl\w*error\b",
    r"(proxy|tunnel)[^\n]{0,40}(error|fail|refused|reset|timeout|timed\s*out)",
    r"connect\s+tunnel\s+failed",
    # 直接调用路径的显式措辞（WP-01）：``transport failure: URLError ...``。
    r"transport\s+failure",
    r"(connection|connect|request|read)[^\n]{0,20}timed?\s*out",
    r"(connection|connect|network|request)[^\n]{0,20}timeout",
    r"\betimedout\b",
    r"(max\s+retries\s+exceeded|too\s+many\s+retries)",
    r"upstream\s+(connect\s+error|request\s+timeout|timed\s*out)",
    r"network\s+(error|unreachable|timeout|timed\s*out)",
    r"tls\s+handshake\s+failure",
)

# 上游 5xx：必须带 HTTP/status/服务名语境，避免误命中普通测试输出里的裸数字
# （``port 5000``、``assert 500 == 503``、``page 502``）。
# codex rev2 F4：任意 5xx（``5\d\d``）都是上游故障，不只 500/502/503/504 ——
# ``507 Insufficient Storage`` / ``529 overloaded`` 同样是可回退的服务端错误。
# 仍然**不**加裸 ``\b5\d\d\b``：语境（http/status/api/provider/upstream 或错误短语）
# 是必须的，否则 ``port 5000`` / ``assert 500 == 503`` 会误触发回退。
DEFAULT_SERVER_PATTERNS: tuple[str, ...] = (
    r"\bhttp(?:/\d(?:\.\d)?)?[^\n]{0,20}?\b5\d\d\b",
    r"\bstatus(?:\s+code)?\s*[:=]\s*5\d\d\b",
    r"\b5\d\d\b[^\n]{0,40}?(?:internal server error|bad gateway|service unavailable|gateway time-?out|upstream)",
    r"(?:internal server error|bad gateway|service unavailable|gateway time-?out)",
    r"\b(?:api|provider|upstream)[^\n]{0,20}?\b5\d\d\b",
)

# 鉴权/配置错误：无额度语境的 401/403、``LLM not set``、CLI 缺失
# （FileNotFoundError / PermissionError）、模型或参数不存在。
# 这些对 fallback 同样致命（同一 CLI、同一 worktree），绝不回退。
DEFAULT_AUTH_CONFIG_PATTERNS: tuple[str, ...] = (
    r"\bllm\s+not\s+set\b",
    r"\b(?:401|403)\b",
    r"unauthori[sz]ed",
    r"forbidden",
    r"invalid\s+api[\s_-]?key",
    r"api[\s_-]?key[^\n]{0,20}(missing|not\s+set|invalid|required)",
    # 直接调用路径的显式措辞（WP-01）：``requires $DEEPSEEK_API_KEY in env``——
    # 只匹配 env 变量名语境，绝不回显 key 值。
    r"requires\s+\S*API_KEY\s+in\s+env",
    r"authentication\s+(failed|error|required)",
    r"permission\s+denied",
    r"\bpermissionerror\b",
    r"\bfilenotfounderror\b",
    r"file\s+not\s+found\s+error",
    r"no\s+such\s+file\s+or\s+directory",
    r"command\s+not\s+found",
    r"model[^\n]{0,30}(not\s+found|does\s+not\s+exist|is\s+not\s+supported|unknown)",
    r"(invalid|unknown|unsupported)[\s_-]*(model|parameter|argument|request)",
    r"invalid_request_error",
    r"missing\s+required\s+(parameter|field)",
    r"unexpected\s+(keyword\s+)?argument",
    r"config(uration)?\s+(error|invalid|not\s+found)",
)

#: Exit code the shell uses for "command not found": the process never started,
#: which is a configuration failure, never a provider/quota failure.
_SHELL_COMMAND_NOT_FOUND = 127

# 任务失败证据（codex rev2 F1）：携带下列标记的行是**任务**失败行，即使同一行
# 也引用了 HTTP 状态码（``FAILED ... - AssertionError: HTTP 503``）。测试/lint
# 失败才是终态根因，不能因为日志里出现基础设施字样而掩盖它（AGENTS.md §7）。
# 命中即为终态：``classify_failure`` 立即返回 ``task``，不再回看更早的行——
# 多行 pytest 日志先引用 ``HTTP 503``、末尾才给出 ``FAILED ... AssertionError``，
# 结论必须是 task，而不是往前捞到基础设施字样。
# 大小写敏感：``FAILED`` 是 pytest 的固定大写，``3 failed`` 是 pytest 汇总的固定
# 小写；大小写不敏感会把 ``payment failed`` 这类真实额度措辞一起否决。
TASK_EVIDENCE_PATTERNS: tuple[str, ...] = (
    r"(?:^|\s)FAILED(?:\s|$)",           # pytest 失败行 ``FAILED tests/...``
    r"AssertionError",                    # pytest/assert 失败异常名
    r"Traceback\s+\(most\s+recent\s+call\s+last\)",
    r"^\s*E\s{2,}\S",                    # pytest 的 ``E   ...`` 错误前缀
    r"ruff\s+check\s+failed",             # lint 失败
    r"\blint\s+failed\b",
    # pytest 汇总行 ``3 failed, 2 passed``：必须行首锚定（允许前导空白与
    # pytest 的 ``====`` 横幅装饰），否则 ``attempt 2 failed: HTTP 503``
    # 这类上游重试行会被当成任务证据（codex r2 blocking #1）。
    r"^\s*=*\s*\d+\s+failed\b",
)


_TRACEBACK_HEADER = re.compile(
    r"Traceback\s+\(most\s+recent\s+call\s+last\)")

# 日志前缀（``[2026-10-20 08:00:00] ``、``2026-10-20T08:00:00Z `` 等）会遮蔽
# 行首锚定的任务证据（``==== 3 failed``）。统一剥掉再做行扫描；只吃掉前缀后的
# 一个分隔空白，保留栈帧自身的缩进（codex r5 #2）。
_LOG_PREFIX = re.compile(
    r"^\s*(?:"
    r"\[[^\]\n]{1,64}\]"
    r"|\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?"
    r")[ \t]"
)


def _strip_log_prefix(line: str) -> str:
    return _LOG_PREFIX.sub("", line, count=1)


def _ends_in_traceback(lines: Sequence[str]) -> bool:
    """True when the output ends inside a Python traceback (a task failure).

    A traceback has no end marker: its exception message may span any number of
    unindented lines, and those lines may quote provider-looking text
    (``RuntimeError("task failed\\nError: HTTP 503")``). Content therefore
    cannot prove that a later line is independent provider output; treating it
    as such let task failures fall over (codex r4/r5). Any traceback header with
    output after it is task — the fail-safe direction of invariant 2: a genuine
    provider failure printed after a traceback forgoes the fallback, but a task
    failure is never masked.
    """
    header = next((i for i in range(len(lines) - 1, -1, -1)
                   if _TRACEBACK_HEADER.search(lines[i])), None)
    if header is None:
        return False
    return any(line.strip() for line in lines[header + 1:])


def _matches(output: str, patterns: Sequence[str]) -> bool:
    """True iff any pattern matches ``output`` (case-insensitive, regex-safe)."""
    return _search(output, patterns, re.IGNORECASE)


def _matches_exact_case(output: str, patterns: Sequence[str]) -> bool:
    """True iff any pattern matches ``output`` case-sensitively (regex-safe)."""
    return _search(output, patterns, 0)


def _search(output: str, patterns: Sequence[str], flags: int) -> bool:
    for p in patterns:
        try:
            if re.search(p, output, flags):
                return True
        except re.error:
            # 坏正则（来自 config 覆盖）跳过而非崩溃（fail-safe）。
            continue
    return False


def _classify_line(
    line: str, quota_patterns: Sequence[str]
) -> str | None:
    """Category for one output line, or ``None`` when the line carries no evidence.

    A line with explicit task evidence reports ``task`` directly: the test/lint
    failure is the terminal cause even if the same line (or an earlier line)
    quotes a 503. Otherwise the priority order is quota -> auth/config ->
    transport -> server: quota before a bare 403 because Kimi reports quota as
    ``403 access_terminated_error``; auth/config before the infrastructure
    categories so a final ``401`` on the same line as an earlier ``503`` is not
    masked (codex r2 blocking #2).
    """
    if _matches_exact_case(line, TASK_EVIDENCE_PATTERNS):
        return CATEGORY_TASK
    for patterns, category in (
        (quota_patterns, CATEGORY_QUOTA),
        (DEFAULT_AUTH_CONFIG_PATTERNS, CATEGORY_AUTH_CONFIG),
        (DEFAULT_TRANSPORT_PATTERNS, CATEGORY_TRANSPORT),
        (DEFAULT_SERVER_PATTERNS, CATEGORY_SERVER),
    ):
        if _matches(line, patterns):
            return category
    return None


def classify_failure(
    output: str,
    exit_code: int | None,
    *,
    quota_patterns: Sequence[str] | None = None,
) -> str:
    """Classify a failed dispatch into one of the five categories. Pure.

    Lines are scanned **newest first**: the last real error line decides, so a
    task log that merely mentions an infrastructure string in its middle does not
    trigger failover, and a later auth error is not masked by an earlier 5xx.
    Priority within a line: quota wins over a bare 403 (Kimis ``weekly usage
    limit`` arrives as 403 ``access_terminated_error``), then auth/config, then
    transport, then server; everything else is ``task``.

    A line that carries task evidence (``FAILED ...``, ``AssertionError``, a
    traceback header, a pytest summary ``3 failed, 2 passed``) is itself the
    terminal cause and returns ``task`` immediately: the scan does not continue
    into older lines, so a multi-line pytest log quoting ``HTTP 503`` before its
    ``FAILED``/``AssertionError`` lines is still a task failure. Because the scan
    is newest-first, a terminal quota/auth/server line *newer* than the last task
    evidence still wins.

    A traceback block is also ``task``: the task's own code raised, even when
    the exception text quotes an infrastructure string such as
    ``RuntimeError: HTTP 503``. The block tolerates timestamped log prefixes and
    multi-line exception messages; because a traceback has no end marker,
    provider-looking lines after it cannot be proven independent, so they do not
    override it (fail-safe).

    ``exit_code`` is only used for the shell's 127 ("command not found"), i.e.
    the child never ran, and only when no line matched. A generic non-zero exit
    is NOT infrastructure: task failures must be reported as-is (AGENTS.md §7).
    Empty output + no exit code therefore classify as ``task`` (fail-safe: no
    failover).
    """
    text = output or ""
    # Log-line prefixes carry no classification meaning; strip them before the
    # structural traceback check and the line scan (codex r4 blocking #1).
    lines = [_strip_log_prefix(line) for line in text.splitlines()]
    # A terminal traceback is a task failure even when its exception message
    # quotes an infrastructure string (``RuntimeError: HTTP 503``): the task's
    # own code raised, so re-running on another provider cannot help and would
    # mask the real failure (invariant 2, codex consult r3/r4).
    if _ends_in_traceback(lines):
        return CATEGORY_TASK
    quota = (DEFAULT_QUOTA_PATTERNS if quota_patterns is None
             else tuple(quota_patterns))
    for line in reversed(lines):
        if not line.strip():
            continue
        category = _classify_line(line, quota)
        if category is not None:
            return category
    if exit_code == _SHELL_COMMAND_NOT_FOUND:
        return CATEGORY_AUTH_CONFIG
    return CATEGORY_TASK


def is_quota_error(output: str, patterns: Sequence[str] | None = None) -> bool:
    """True iff ``output`` matches any quota pattern (case-insensitive). Pure.

    空输出 → False。坏的正则（来自 config 覆盖）跳过而非崩溃（fail-safe）。
    Legacy predicate kept verbatim for ``agentic redispatch``.
    """
    if not output:
        return False
    return _matches(output, DEFAULT_QUOTA_PATTERNS if patterns is None
                    else tuple(patterns))


def load_quota_patterns(repo: Path | None = None) -> tuple[str, ...]:
    """读可选 ``[quota_fallback] patterns``；缺省/坏配置回落 DEFAULT（fail-safe）。

    直读 ``_load_config``（避开 CONFIG_SECTIONS 白名单过滤）；任何异常都回落默认，
    绝不把解析失败抛进派发主链。
    """
    try:
        from agentic_loop.resolve_paths import _load_config, main_repo

        repo = repo or main_repo()
        data: Any = _load_config(repo) or {}
        section = data.get("quota_fallback") if isinstance(data, dict) else None
        if isinstance(section, dict):
            pats = section.get("patterns")
            if (isinstance(pats, (list, tuple)) and pats
                    and all(isinstance(x, str) and x for x in pats)):
                return tuple(pats)
    except Exception as exc:
        # codex impl-rev1 #8 / brief rev7 §R2b：配置故障不静默吞——回落 DEFAULT 前
        # 打一行脱敏诊断（固定文案 + 异常类名），绝不含 config 原文/路径/密钥值。
        print(
            "load_quota_patterns: quota_fallback config unreadable "
            f"({type(exc).__name__}); falling back to built-in defaults",
            file=sys.stderr,
        )
    return DEFAULT_QUOTA_PATTERNS

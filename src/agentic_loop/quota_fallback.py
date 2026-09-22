#!/usr/bin/env python3
"""Pure quota-exhaustion detection for developer-dispatch fallback.

`is_quota_error` is a pure string predicate (no I/O). `load_quota_patterns`
reads an optional project-config override and fails safe to built-in defaults.
Neither imports git/subprocess nor touches status; the dispatch layer
(redispatch) owns all side effects.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

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
    # 英文：ambiguous 形容词/动词必须与账户/额度名词近距共现
    r"(insufficient|exceeded|exhausted|depleted|out of|no remaining|used up|not enough)\W{0,10}(balance|credit|credits|funds|quota|allowance|budget|subscription)",
    r"(balance|credit|credits|funds|quota|allowance|budget|subscription)\W{0,20}(insufficient|exceeded|exhausted|depleted|too low|not enough|used up|out of|empty|zero)",
    # HTTP 状态码 + 额度/付费语境（避免 429 命中端口号、402 命中行号）
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
)


def is_quota_error(output: str, patterns: Sequence[str] | None = None) -> bool:
    """True iff ``output`` matches any quota pattern (case-insensitive). Pure.

    空输出 → False。坏的正则（来自 config 覆盖）跳过而非崩溃（fail-safe）。
    """
    if not output:
        return False
    pats = DEFAULT_QUOTA_PATTERNS if patterns is None else tuple(patterns)
    for p in pats:
        try:
            if re.search(p, output, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False

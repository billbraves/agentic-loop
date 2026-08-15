from __future__ import annotations

import os

_PLACEHOLDER = "***REDACTED***"


def redact(text: str, secrets: list[str]) -> str:
    """Replace each non-empty secret value with a fixed placeholder."""
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, _PLACEHOLDER)
    return out


def redact_env_value(text: str, api_key_env: str) -> str:
    """Redact the value of ``os.environ[api_key_env]`` from ``text``."""
    value = os.environ.get(api_key_env)
    return redact(text, [value]) if value else text

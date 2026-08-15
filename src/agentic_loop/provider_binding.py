from __future__ import annotations

from dataclasses import dataclass

# claude/kimi 走 anthropic 兼容端；codex 走 openai 兼容端。
_ANTHROPIC_ADAPTERS = {"claude", "kimi"}
_OPENAI_ADAPTERS = {"codex"}


class ProviderConfigError(ValueError):
    """provider binding 构造失败（缺必需字段）。消息绝不含 key 值。"""


@dataclass(frozen=True)
class ProviderBinding:
    provider: str
    anthropic_base_url: str | None
    openai_base_url: str | None
    identity_model: str      # canonical，只喂 INV-1 identity
    cli_selector: str        # 该 adapter 的 -m/--model 串，只拼命令
    api_key_env: str         # 环境变量名；adapter 运行时读，绝不持久化明文


def build_binding(*, adapter: str, provider_cfg: dict) -> ProviderBinding:
    """从 provider 配置段为某 adapter 构造 binding。

    按 adapter 校验必需 base_url；缺失 fail-closed 并脱敏报错（不回显 key）。
    """
    identity_model = provider_cfg.get("identity_model")
    api_key_env = provider_cfg.get("api_key_env")
    selectors = provider_cfg.get("selectors") or {}
    cli_selector = selectors.get(adapter)
    anthropic_base_url = provider_cfg.get("anthropic_base_url")
    openai_base_url = provider_cfg.get("openai_base_url")

    if not identity_model:
        raise ProviderConfigError(
            f"provider config missing identity_model for adapter {adapter!r}"
        )
    if not api_key_env:
        raise ProviderConfigError(
            f"provider config missing api_key_env for adapter {adapter!r}"
        )
    if not cli_selector:
        raise ProviderConfigError(
            f"provider config missing selectors[{adapter!r}]"
        )
    if adapter in _ANTHROPIC_ADAPTERS and not anthropic_base_url:
        raise ProviderConfigError(
            f"adapter {adapter!r} requires anthropic_base_url"
        )
    if adapter in _OPENAI_ADAPTERS and not openai_base_url:
        raise ProviderConfigError(
            f"adapter {adapter!r} requires openai_base_url"
        )

    return ProviderBinding(
        provider=provider_cfg.get("_name", "deepseek"),
        anthropic_base_url=anthropic_base_url,
        openai_base_url=openai_base_url,
        identity_model=identity_model,
        cli_selector=cli_selector,
        api_key_env=api_key_env,
    )

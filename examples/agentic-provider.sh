#!/usr/bin/env bash
# agentic-provider.sh —— 一键切换 codex/kimi 手动 CLI 的默认 provider（官方 ↔ DeepSeek）
#
# 背景：agentic 的 DeepSeek 是「运行时注入」，只在 agentic 派发（gate/redispatch/评审）
# 时生效，不碰各 CLI 的全局配置。本脚本切的是「手动跑 codex/kimi」时的默认 provider，
# 用于官方 key 撞限额（codex 5 小时 / kimi 星期）时一键切 DeepSeek 兜底。
#
# 用法：
#   ./agentic-provider.sh deepseek    # codex/kimi 手动 CLI 切到 DeepSeek
#   ./agentic-provider.sh official    # 切回官方（codex=gpt-5.5 / kimi=kimi-code）
#   ./agentic-provider.sh status      # 看当前默认 provider
#
# 也可 source 进 ~/.zshrc 当函数用（见 docs/QUICKSTART.zh-CN.md §1.3）。
# macOS 用 BSD sed（-i ''）；GNU/Linux 用 -i。按系统自动选。
set -euo pipefail

CODEX_CFG="${CODEX_CFG:-$HOME/.codex/config.toml}"
KIMI_CFG="${KIMI_CFG:-$HOME/.kimi/config.toml}"
TARGET="${1:-status}"

# 选 sed 的 -i 写法
if sed --version >/dev/null 2>&1; then
  SED_I=(sed -i)          # GNU
else
  SED_I=(sed -i '')       # BSD/macOS
fi

codex_model() { grep '^model' "$CODEX_CFG" 2>/dev/null | head -1 || echo "(无 codex config)"; }
kimi_model()  { grep '^default_model' "$KIMI_CFG" 2>/dev/null | head -1 || echo "(无 kimi config)"; }

case "$TARGET" in
  deepseek)
    "${SED_I[@]}" 's/^model = "gpt-5.5"/model = "deepseek-v4-pro"/' "$CODEX_CFG"
    "${SED_I[@]}" 's#^default_model = "kimi-code/kimi-for-coding"#default_model = "deepseek/v4-pro"#' "$KIMI_CFG"
    echo "✓ 已切到 DeepSeek"
    ;;
  official)
    "${SED_I[@]}" 's/^model = "deepseek-v4-pro"/model = "gpt-5.5"/' "$CODEX_CFG"
    "${SED_I[@]}" 's#^default_model = "deepseek/v4-pro"#default_model = "kimi-code/kimi-for-coding"#' "$KIMI_CFG"
    echo "✓ 已切回官方"
    ;;
  status|*)
    echo "codex: $(codex_model)"
    echo "kimi:  $(kimi_model)"
    ;;
esac

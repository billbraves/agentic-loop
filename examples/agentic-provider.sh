#!/usr/bin/env bash
# agentic-provider.sh —— 一键切换 codex/kimi/claude 手动 CLI 的默认 provider（官方 ↔ DeepSeek）
#
# 背景：agentic 的 DeepSeek 是「运行时注入」，只在 agentic 派发（gate/redispatch/评审）
# 时生效，不碰各 CLI 的全局配置。本脚本切的是「手动跑 codex/kimi/claude」时的默认
# provider，用于官方 key 撞限额（codex 5 小时 / kimi 星期）时一键切 DeepSeek 兜底。
#
# 用法（全切 + 独立切）：
#   ./agentic-provider.sh deepseek          # 三个都切 DeepSeek
#   ./agentic-provider.sh official          # 三个都切回官方
#   ./agentic-provider.sh codex-deepseek    # 只切 codex → DeepSeek
#   ./agentic-provider.sh codex-official    # 只切 codex → 官方
#   ./agentic-provider.sh kimi-deepseek     # 只切 kimi → DeepSeek
#   ./agentic-provider.sh kimi-official     # 只切 kimi → 官方
#   ./agentic-provider.sh claude-deepseek   # 只切 claude → DeepSeek
#   ./agentic-provider.sh claude-official   # 只切 claude → 官方
#   ./agentic-provider.sh status            # 看当前默认 provider
#
# 也可 source 进 ~/.zshrc 当函数用（见 docs/QUICKSTART.zh-CN.md §1.3）。
# macOS 用 BSD sed（-i ''）；GNU/Linux 用 -i。按系统自动选。
set -euo pipefail

CODEX_CFG="${CODEX_CFG:-$HOME/.codex/config.toml}"
KIMI_CFG="${KIMI_CFG:-$HOME/.kimi/config.toml}"
CLAUDE_CFG="${CLAUDE_CFG:-$HOME/.claude/settings.json}"
CLAUDE_BAK="${CLAUDE_CFG}.official.bak"
TARGET="${1:-status}"

# 选 sed 的 -i 写法
if sed --version >/dev/null 2>&1; then
  SED_I=(sed -i)          # GNU
else
  SED_I=(sed -i '')       # BSD/macOS
fi

# 确保 DEEPSEEK_API_KEY 可用（当前 shell 没设则从 ~/.zshrc 读）
if [[ -z "${DEEPSEEK_API_KEY:-}" ]] && [[ -f "$HOME/.zshrc" ]]; then
  export DEEPSEEK_API_KEY="$(grep '^export DEEPSEEK_API_KEY=' "$HOME/.zshrc" | sed 's/^export DEEPSEEK_API_KEY=//')"
fi

codex_model()  { grep '^model' "$CODEX_CFG" 2>/dev/null | head -1 || echo "(无 codex config)"; }
kimi_model()   { grep '^default_model' "$KIMI_CFG" 2>/dev/null | head -1 || echo "(无 kimi config)"; }
claude_model() {
  python3 - "$CLAUDE_CFG" 2>/dev/null <<'PY' || echo "(无 claude config)"
import json, sys
d = json.load(open(sys.argv[1]))
e = d.get("env", {})
print("ANTHROPIC_MODEL=%s BASE_URL=%s" % (e.get("ANTHROPIC_MODEL", "?"), e.get("ANTHROPIC_BASE_URL", "?")))
PY
}

switch_codex_deepseek() { "${SED_I[@]}" 's/^model = "gpt-5.5"/model = "deepseek-v4-pro"/' "$CODEX_CFG"; }
switch_codex_official() { "${SED_I[@]}" 's/^model = "deepseek-v4-pro"/model = "gpt-5.5"/' "$CODEX_CFG"; }
switch_kimi_deepseek()  { "${SED_I[@]}" 's#^default_model = "kimi-code/kimi-for-coding"#default_model = "deepseek/v4-pro"#' "$KIMI_CFG"; }
switch_kimi_official()  { "${SED_I[@]}" 's#^default_model = "deepseek/v4-pro"#default_model = "kimi-code/kimi-for-coding"#' "$KIMI_CFG"; }

switch_claude_deepseek() {
  python3 - "$CLAUDE_CFG" "$CLAUDE_BAK" "$DEEPSEEK_API_KEY" <<'PY'
import json, os, shutil, sys
cfg, bak, key = sys.argv[1:4]
if not os.path.exists(bak):
    shutil.copy(cfg, bak)   # 备份官方/中转配置，供切回
data = json.load(open(cfg))
env = data.setdefault("env", {})
env["ANTHROPIC_BASE_URL"] = "https://api.deepseek.com/anthropic"
env["ANTHROPIC_AUTH_TOKEN"] = key
env["ANTHROPIC_MODEL"] = "deepseek-v4-pro"
env.pop("ANTHROPIC_API_KEY", None)   # DeepSeek 走 AUTH_TOKEN，移除官方 API_KEY
json.dump(data, open(cfg, "w"), indent=2, ensure_ascii=False)
PY
}

switch_claude_official() {
  [[ -f "$CLAUDE_BAK" ]] && cp "$CLAUDE_BAK" "$CLAUDE_CFG"
}

case "$TARGET" in
  deepseek)
    switch_codex_deepseek; switch_kimi_deepseek; switch_claude_deepseek
    echo "✓ codex+kimi+claude 已切 DeepSeek"
    ;;
  official)
    switch_codex_official; switch_kimi_official; switch_claude_official
    echo "✓ codex+kimi+claude 已切回官方"
    ;;
  codex-deepseek)  switch_codex_deepseek;  echo "✓ codex → DeepSeek"; ;;
  codex-official)  switch_codex_official;  echo "✓ codex → 官方"; ;;
  kimi-deepseek)   switch_kimi_deepseek;   echo "✓ kimi → DeepSeek"; ;;
  kimi-official)   switch_kimi_official;   echo "✓ kimi → 官方"; ;;
  claude-deepseek) switch_claude_deepseek; echo "✓ claude → DeepSeek"; ;;
  claude-official) switch_claude_official; echo "✓ claude → 官方"; ;;
  status|*)
    echo "codex:  $(codex_model)"
    echo "kimi:   $(kimi_model)"
    echo "claude: $(claude_model)"
    ;;
esac

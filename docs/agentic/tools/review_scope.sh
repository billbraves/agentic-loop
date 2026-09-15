#!/bin/bash
# 编排者验收工具：范围核验（缺陷 B8 的修正版）
#
# B8：用「上一轮执行者 commit」当基线，会把两轮之间编排者自己的 merge
# （A24：把 plan 分支合进 worktree 让冻结 Brief 可达）带进来的 docs 改动
# 误报成执行者越界（假阳性）。
#
# 正确口径：只看执行者本轮 commit 自身的改动面，即
#   <派发时 worktree HEAD>..<执行者 commit>
# 派发点从 status 的 git.dispatch_commit 读取；缺失时**拒绝猜测**（fail-closed），
# 因为猜错基线正是 B8 本身。
#
# 用法：review_scope.sh <worktree> <status.json> <allowed-regex>
#   allowed-regex：允许改动的路径白名单（ERE，锚定整行）
set -uo pipefail

WT=${1:?worktree path}
STATUS=${2:?status.json path}
ALLOWED=${3:?allowed-paths ERE}

fail=0

# --- 1. 取派发点。缺失即失败，不退化成 base_commit，也不猜 HEAD^ ---
DISPATCH=$(python3 - "$STATUS" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("", end="")
    sys.exit(0)
print(d.get("git", {}).get("dispatch_commit") or "", end="")
PY
)
EXEC_COMMIT=$(python3 - "$STATUS" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("", end=""); sys.exit(0)
print(d.get("git", {}).get("commit") or "", end="")
PY
)

if [ -z "$DISPATCH" ]; then
  echo "SCOPE_UNVERIFIABLE: git.dispatch_commit 缺失于 $STATUS"
  echo "  范围核验必须以派发时 worktree HEAD 为基线（缺陷 B8）。"
  echo "  git.base_commit 记的是主区基线，在有 A24 merge 时与派发点不同，不可替代。"
  exit 3
fi
if [ -z "$EXEC_COMMIT" ]; then
  echo "SCOPE_UNVERIFIABLE: git.commit 缺失于 $STATUS"
  exit 3
fi

# --- 2. 基线与执行者 commit 都必须在这个 worktree 里可解析 ---
for ref in "$DISPATCH" "$EXEC_COMMIT"; do
  if ! git -C "$WT" cat-file -e "${ref}^{commit}" 2>/dev/null; then
    echo "SCOPE_UNVERIFIABLE: $ref 在 $WT 中不可解析"
    exit 3
  fi
done

# --- 3. 派发点必须是执行者 commit 的祖先，否则区间无意义 ---
if ! git -C "$WT" merge-base --is-ancestor "$DISPATCH" "$EXEC_COMMIT"; then
  echo "SCOPE_UNVERIFIABLE: $DISPATCH 不是 $EXEC_COMMIT 的祖先"
  exit 3
fi

RANGE="${DISPATCH}..${EXEC_COMMIT}"
echo "范围核验区间: $RANGE  (派发点..执行者 commit)"
git -C "$WT" diff --stat "$RANGE"

# --- 4. 越界判定 ---
OUT=$(git -C "$WT" diff --name-only "$RANGE" | grep -vE "$ALLOWED" || true)
if [ -z "$OUT" ]; then
  printf "  ✅ 无越界（白名单: %s）\n" "$ALLOWED"
else
  echo "  ❌ 越界文件："
  # 附带责任归属，便于分辨假阳性
  while IFS= read -r f; do
    who=$(git -C "$WT" log --format='%h %an' -1 "$RANGE" -- "$f")
    printf "     %-60s %s\n" "$f" "$who"
  done <<< "$OUT"
  fail=1
fi

# --- 5. 正面对照：本区间必须确实有改动，否则「无越界」是空验证 ---
N=$(git -C "$WT" diff --name-only "$RANGE" | wc -l | tr -d ' ')
if [ "$N" = "0" ]; then
  echo "  ⚠️  SCOPE_VACUOUS: 区间内 0 个文件改动——「无越界」不成立为证据"
  fail=1
else
  echo "  ✅ 区间内 $N 个文件改动（判定具备区分力）"
fi

[ $fail -eq 0 ] && echo "SCOPE_OK" || echo "SCOPE_VIOLATION"
exit $fail

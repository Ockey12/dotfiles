#!/bin/bash
# AGENTS.mdを各ツールのグローバル指示ファイルにシンボリックリンクするスクリプト

# 実行する方法
# 1. `chmod +x ./link-agents.sh`
# 2. `./link-agents.sh`

SOURCE_FILE="$(cd "$(dirname "$0")" && pwd)/AGENTS.md"

TARGETS=(
  "$HOME/.agents/AGENTS.md"
  "$HOME/.claude/CLAUDE.md"
)

for target in "${TARGETS[@]}"; do
  if [ -L "$target" ]; then
    echo "[skip] $target (already symlinked)"
  elif [ -e "$target" ]; then
    echo "[skip] $target (already exists, not a symlink)"
  else
    mkdir -p "$(dirname "$target")"
    ln -s "$SOURCE_FILE" "$target"
    echo "[link] $target -> $SOURCE_FILE"
  fi
done

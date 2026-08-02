#!/bin/bash
# skills サブディレクトリを各ツールの skills ディレクトリにシンボリックリンクするスクリプト

# 実行する方法
# 1. `chmod +x ./link-skills.sh`
# 2. `./link-skills.sh`

SKILLS_DIR="$(cd "$(dirname "$0")/skills" && pwd)"
XCODE_SKILLS_DIR="$SKILLS_DIR/xcode-skills"

TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.agents/skills"
  "$HOME/.cursor/skills-cursor"
)

link_skills_in() {
  local source_dir="$1"

  for skill in "$source_dir"/*/; do
    [ -f "$skill/SKILL.md" ] || continue

    skill_name=$(basename "$skill")
    for target in "${TARGETS[@]}"; do
      link="$target/$skill_name"
      if [ -L "$link" ]; then
        echo "[skip] $link (already symlinked)"
      elif [ -e "$link" ]; then
        echo "[skip] $link (already exists, not a symlink)"
      else
        mkdir -p "$target"
        ln -s "$skill" "$link"
        echo "[link] $link -> $skill"
      fi
    done
  done
}

link_skills_in "$SKILLS_DIR"
link_skills_in "$XCODE_SKILLS_DIR"

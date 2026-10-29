#!/bin/zsh
# Kept so the Obsidian buttons that call it keep working; everything lives in sync.sh now.
exec "$(dirname "$0")/sync.sh" "$@"

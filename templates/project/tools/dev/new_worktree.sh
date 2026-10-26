#!/bin/bash
# One task = one branch + one worktree, ready to run the game and the tests:
#   tools/dev/new_worktree.sh <name>   -> .claude/worktrees/<name> on branch task/<name> (from HEAD)
# The import cache (.godot, ignored by git) is copied so the worktree runs at once.
# On macOS/APFS the copy is copy-on-write (seconds, no disk).
set -e
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
NAME=${1:?usage: new_worktree.sh <name>}
DIR=.claude/worktrees/$NAME
git worktree add -b "task/$NAME" "$DIR" HEAD
if [ -d .godot ]; then
	mkdir -p "$DIR/.godot"
	for item in .godot/*; do
		cp -cpR "$item" "$DIR/.godot/" 2>/dev/null || cp -pR "$item" "$DIR/.godot/"
	done
fi
if [ -n "$GODOT" ]; then
	"$GODOT" --headless --audio-driver Dummy --path "$DIR" --import > /dev/null 2>&1 || true
fi
echo "$PWD/$DIR"

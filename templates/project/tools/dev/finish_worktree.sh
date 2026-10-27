#!/bin/bash
# Merges a finished task branch into the current branch and removes its worktree:
#   tools/dev/finish_worktree.sh <name>
# --no-ff keeps one merge commit per task, so a task can be found and reverted alone.
set -e
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
NAME=${1:?usage: finish_worktree.sh <name>}
DIR=.claude/worktrees/$NAME
if [ -n "$(git -C "$DIR" status --porcelain)" ]; then
	echo "Uncommitted changes in $DIR; commit or discard them first." >&2
	exit 1
fi
# RPCs the branch removed, moved or changed (vs where it forked) break multiplayer silently.
if [ -f tools/dev/rpc_check.py ] && [ "${RPC_OK:-0}" != 1 ]; then
	"$PYTHON" -I tools/dev/rpc_check.py --base "$(git merge-base HEAD "task/$NAME")" --head "task/$NAME" || {
		echo "Not merged. If the RPC change is intended: RPC_OK=1 $0 $NAME" >&2; exit 1; }
fi
git merge --no-ff "task/$NAME" -m "Merge task/$NAME"
chmod -R u+w "$DIR" 2>/dev/null || true
git worktree remove --force "$DIR"
git branch -d "task/$NAME"
# New class_names/assets from the branch: refresh the import cache of this checkout.
if [ -n "$GODOT" ]; then
	"$GODOT" --headless --audio-driver Dummy --path . --import > /dev/null 2>&1 || true
fi

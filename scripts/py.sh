#!/bin/bash
# Runs a kit Python script with the first Python 3 that works: python3, python, py.
# Windows often has no real python3 (only the Microsoft Store alias), so the hook
# and skills go through this instead of calling python3 directly.
for c in python3 python py; do
	if "$c" -c "import sys; sys.exit(sys.version_info < (3, 8))" > /dev/null 2>&1; then exec "$c" -I "$@"; fi
done
echo "godot-claude-kit: Python 3 not found (install it from https://www.python.org)" >&2
exit 1

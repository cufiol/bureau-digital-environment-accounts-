#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PORT="${BUREAU_PORTAL_PORT:-8000}"
EXISTING_PIDS="$(lsof -t -nP -iTCP:${PORT} -sTCP:LISTEN 2>/dev/null)"
if [ -n "$EXISTING_PIDS" ]; then
	echo "Stopping existing portal listener on port ${PORT}..."
	for pid in ${(f)EXISTING_PIDS}; do
		kill "$pid" 2>/dev/null || true
	done
	sleep 1
fi

exec python3 -u "$SCRIPT_DIR/server.py"

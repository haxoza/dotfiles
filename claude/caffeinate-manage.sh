#!/usr/bin/env bash
set -e

# Manages caffeinate lifecycle across multiple Claude Code sessions.
# Uses per-session caffeinate processes tied to the parent PID via -w flag,
# so they self-terminate if the terminal (e.g. Ghostty) is closed abruptly.
# SessionEnd hook provides eager cleanup for graceful exits.

SESSIONS_DIR="$HOME/.claude/caffeinate-sessions"
ACTION="${1:?Usage: caffeinate-manage.sh start|stop}"

# Parse session_id from JSON on stdin (hook input)
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | grep -o '"session_id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
  exit 0
fi

mkdir -p "$SESSIONS_DIR"

start_caffeinate() {
  # Clean up stale sessions whose parent PIDs are no longer alive
  for f in "$SESSIONS_DIR"/*; do
    [ -f "$f" ] || continue
    stored_pid=$(cat "$f" 2>/dev/null || true)
    caff_pid=$(echo "$stored_pid" | head -1)
    if [ -n "$caff_pid" ] && ! kill -0 "$caff_pid" 2>/dev/null; then
      rm -f "$f"
    fi
  done

  # Start a caffeinate process tied to our parent PID (the shell/terminal).
  # When the parent dies (e.g. Ghostty closed), caffeinate exits automatically.
  caffeinate -ims -w "$PPID" </dev/null >/dev/null 2>&1 &
  CAFF_PID=$!

  # Record the caffeinate PID for this session
  echo "$CAFF_PID" > "$SESSIONS_DIR/$SESSION_ID"
}

stop_caffeinate() {
  session_file="$SESSIONS_DIR/$SESSION_ID"
  if [ -f "$session_file" ]; then
    caff_pid=$(cat "$session_file" 2>/dev/null || true)
    if [ -n "$caff_pid" ]; then
      kill "$caff_pid" 2>/dev/null || true
    fi
    rm -f "$session_file"
  fi
}

case "$ACTION" in
  start) start_caffeinate ;;
  stop)  stop_caffeinate ;;
  *)     echo "Usage: caffeinate-manage.sh start|stop" >&2; exit 1 ;;
esac

#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check if web-app deps installed
if [ ! -d "node_modules" ]; then
    echo "⚠️  Web-app dependencies not installed. Running setup first..."
    ./setup.sh
fi

# Check terminal-server deps (dev-only, see ADR-0003)
TERMINAL_AVAILABLE=1
if [ ! -d "terminal-server/node_modules" ]; then
    echo "⚠️  terminal-server dependencies not installed."
    echo "   Skipping embedded terminal. Run ./setup.sh to enable it."
    TERMINAL_AVAILABLE=0
fi

# Stale token file from a previous (older) run — best-effort cleanup; the
# v0.2 terminal-server no longer writes this file.
rm -f .terminal-token

echo "🚀 Starting Lyra Knowledge Base..."
echo "   http://localhost:4321"
if [ "$TERMINAL_AVAILABLE" = "1" ]; then
    echo "   (embedded terminal: ws://127.0.0.1:4322)"
fi
echo ""

# Open browser after short delay
(sleep 2 && open "http://localhost:4321" 2>/dev/null || xdg-open "http://localhost:4321" 2>/dev/null) &

# Track child PIDs so we kill them on Ctrl+C
TERMINAL_PID=""

cleanup() {
    if [ -n "$TERMINAL_PID" ] && kill -0 "$TERMINAL_PID" 2>/dev/null; then
        kill "$TERMINAL_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# Start terminal-server in the background (dev-only)
if [ "$TERMINAL_AVAILABLE" = "1" ]; then
    (cd terminal-server && node index.mjs) &
    TERMINAL_PID=$!
fi

# Astro dev server (foreground)
pnpm dev

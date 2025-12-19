#!/bin/bash
# ============================================================================
# Start Autonomous Brain Daemon (Manual Mode)
# ============================================================================
#
# This script starts the daemon manually without systemd.
# Use this for testing or if you don't want auto-start on boot.
#
# Usage: bash start_daemon_manual.sh
# ============================================================================

echo "🤖 Starting Autonomous Brain Daemon (Manual Mode)"
echo "=================================================="
echo ""

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Activate venv if exists
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if daemon already running
if [ -f "autonomous_daemon.pid" ]; then
    PID=$(cat autonomous_daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Daemon already running (PID: $PID)"
        echo "   Stop it first: kill $PID"
        exit 1
    else
        echo "🧹 Cleaning up stale PID file..."
        rm autonomous_daemon.pid
    fi
fi

echo "🚀 Starting daemon..."
echo ""

# Start daemon
python -m companion_baas.autonomous.start_daemon &

DAEMON_PID=$!
echo "✅ Daemon started with PID: $DAEMON_PID"
echo ""
echo "📊 Dashboard: http://localhost:8888"
echo "📝 Logs: tail -f autonomous_daemon.log"
echo ""
echo "🛑 To stop: kill $DAEMON_PID"
echo ""

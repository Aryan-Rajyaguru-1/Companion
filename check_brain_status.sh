#!/bin/bash
echo "=== Daemon Status ==="
if [ -f autonomous_daemon.pid ]; then
    PID=$(cat autonomous_daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Daemon running (PID: $PID)"
    else
        echo "❌ Daemon not running (stale PID file)"
    fi
else
    echo "❌ No PID file found"
fi

echo ""
echo "=== Recent Self-Awareness Activity ==="
tail -200 autonomous_daemon.log | grep -E "(Brain analyzing|✅.*response|self-assessment|identified.*needs|Gemini|OpenRouter)" | tail -15

echo ""
echo "=== Dashboard ==="
echo "http://localhost:8888"

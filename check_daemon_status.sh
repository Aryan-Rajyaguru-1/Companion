#!/bin/bash
# Check Autonomous Brain Daemon Status

echo "🤖 Autonomous Brain Daemon - Status Check"
echo "=========================================="
echo ""

# Check if PID file exists
if [ -f "autonomous_daemon.pid" ]; then
    PID=$(cat autonomous_daemon.pid)
    echo "📋 PID File: $PID"
    
    # Check if process is running
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Status: RUNNING"
        echo ""
        
        # Get process info
        echo "📊 Process Info:"
        ps -p $PID -o pid,ppid,user,%cpu,%mem,etime,cmd
        echo ""
        
        # Check dashboard
        if curl -s http://localhost:8888 > /dev/null 2>&1; then
            echo "✅ Dashboard: http://localhost:8888 (accessible)"
        else
            echo "⚠️  Dashboard: Not accessible yet (may be starting)"
        fi
        echo ""
        
        # Show recent logs
        echo "📝 Recent Logs:"
        tail -n 10 autonomous_daemon.log 2>/dev/null || echo "   No logs yet"
        
    else
        echo "❌ Status: NOT RUNNING (stale PID file)"
        rm autonomous_daemon.pid
    fi
else
    echo "❌ Status: NOT RUNNING"
    echo "   No PID file found"
    echo ""
    echo "💡 Start with: bash start_daemon_manual.sh"
fi

echo ""
echo "🎯 Control Commands:"
echo "   • View logs: tail -f autonomous_daemon.log"
echo "   • Stop daemon: kill $PID"
echo "   • Dashboard: http://localhost:8888"

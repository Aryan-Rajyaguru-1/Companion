#!/bin/bash
# ============================================================================
# Autonomous Brain Daemon - Installation Script
# ============================================================================
# 
# This script installs the Autonomous Brain Daemon as a systemd service
# that runs 24/7 and auto-starts on PC boot.
#
# Usage: sudo bash install_daemon.sh
# ============================================================================

set -e

echo "🤖 Autonomous Brain Daemon - Installation"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root: sudo bash install_daemon.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
echo "👤 Installing for user: $ACTUAL_USER"

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Project directory: $PROJECT_DIR"

# Get Python path from venv
VENV_DIR="$PROJECT_DIR/.venv"
if [ -d "$VENV_DIR" ]; then
    PYTHON_PATH="$VENV_DIR/bin/python"
    echo "🐍 Using venv Python: $PYTHON_PATH"
else
    PYTHON_PATH="$(which python3)"
    echo "🐍 Using system Python: $PYTHON_PATH"
fi

# Create log directory
LOG_DIR="/var/log/companion-brain"
echo "📝 Creating log directory: $LOG_DIR"
mkdir -p "$LOG_DIR"
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$LOG_DIR"

# Update service file with actual paths
SERVICE_FILE="$PROJECT_DIR/companion-brain-daemon.service"
TEMP_SERVICE="/tmp/companion-brain-daemon.service"

echo "⚙️  Configuring service file..."
sed "s|%USER%|$ACTUAL_USER|g" "$SERVICE_FILE" | \
sed "s|%PROJECT_DIR%|$PROJECT_DIR|g" | \
sed "s|%PYTHON_PATH%|$PYTHON_PATH|g" > "$TEMP_SERVICE"

# Copy service file to systemd
SYSTEMD_SERVICE="/etc/systemd/system/companion-brain-daemon.service"
echo "📋 Installing service to: $SYSTEMD_SERVICE"
cp "$TEMP_SERVICE" "$SYSTEMD_SERVICE"
rm "$TEMP_SERVICE"

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable service (auto-start on boot)
echo "✅ Enabling auto-start on boot..."
systemctl enable companion-brain-daemon

# Start service
echo "🚀 Starting daemon..."
systemctl start companion-brain-daemon

# Show status
echo ""
echo "✅ Installation complete!"
echo ""
echo "📊 Service Status:"
systemctl status companion-brain-daemon --no-pager -l
echo ""
echo "🎯 Useful Commands:"
echo "  • Check status:    sudo systemctl status companion-brain-daemon"
echo "  • Stop daemon:     sudo systemctl stop companion-brain-daemon"
echo "  • Start daemon:    sudo systemctl start companion-brain-daemon"
echo "  • Restart daemon:  sudo systemctl restart companion-brain-daemon"
echo "  • View logs:       sudo journalctl -u companion-brain-daemon -f"
echo "  • Disable auto-start: sudo systemctl disable companion-brain-daemon"
echo ""
echo "📊 Dashboard: http://localhost:8888"
echo ""
echo "🎉 Your Autonomous Brain is now running 24/7!"

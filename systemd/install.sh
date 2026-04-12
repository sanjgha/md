#!/bin/bash
# Installation script for market data systemd services

set -e

SERVICES_DIR="/home/ubuntu/projects/md/systemd"
SYSTEMD_DIR="/etc/systemd/system"
SERVICES=("market-data-fetch" "market-data-scan" "market-data-analyze")

echo "🚀 Installing Market Data Systemd Services..."
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run this script with sudo:"
    echo "   sudo $0"
    exit 1
fi

# Copy service files
echo "📋 Copying service files to $SYSTEMD_DIR..."
for service in "${SERVICES[@]}"; do
    cp "$SERVICES_DIR/$service.service" "$SYSTEMD_DIR/"
    echo "   ✅ Copied $service.service"
done

# Reload systemd
echo
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo
echo "🔧 Enabling services to start on boot..."
for service in "${SERVICES[@]}"; do
    systemctl enable "$service.service"
    echo "   ✅ Enabled $service"
done

# Start services
echo
echo "▶️  Starting services..."
for service in "${SERVICES[@]}"; do
    systemctl start "$service.service"
    echo "   ✅ Started $service"
done

echo
echo "✅ Installation complete!"
echo
echo "📊 Service Status:"
systemctl status "${SERVICES[@]/%/.service}" --no-pager
echo
echo "📝 View logs with:"
echo "   sudo journalctl -u market-data-fetch.service -f"
echo "   sudo journalctl -u market-data-scan.service -f"
echo "   sudo journalctl -u market-data-analyze.service -f"
echo
echo "📖 See $SERVICES_DIR/README.md for full documentation"

#!/bin/bash
#
# Installation script for Kubernetes Avahi Advertiser Service
#
# This script installs the avahi-k8s-advertiser as a systemd service
# on the Kubernetes host machine.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Installation paths
INSTALL_BIN="/usr/local/bin/avahi_k8s_advertiser.py"
SYSTEMD_SERVICE="/etc/systemd/system/avahi-k8s-advertiser.service"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Kubernetes Avahi Advertiser Installer${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# Check if required files exist
if [ ! -f "$SCRIPT_DIR/avahi_k8s_advertiser.py" ]; then
    echo -e "${RED}Error: avahi_k8s_advertiser.py not found in current directory${NC}"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/avahi-k8s-advertiser.service" ]; then
    echo -e "${RED}Error: avahi-k8s-advertiser.service not found in current directory${NC}"
    exit 1
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 not found. Installing...${NC}"
    apt-get update
    apt-get install -y python3 python3-pip
fi

# Check if Avahi is installed
if ! command -v avahi-daemon &> /dev/null; then
    echo -e "${YELLOW}Avahi daemon not found. Installing...${NC}"
    apt-get update
    apt-get install -y avahi-daemon avahi-utils
fi

# Install Python kubernetes library via apt
echo -e "${GREEN}Installing Python kubernetes library...${NC}"
apt-get install -y python3-kubernetes

# Copy Python script
echo -e "${GREEN}Installing Python script to $INSTALL_BIN...${NC}"
cp "$SCRIPT_DIR/avahi_k8s_advertiser.py" "$INSTALL_BIN"
chmod +x "$INSTALL_BIN"

# Copy systemd service file
echo -e "${GREEN}Installing systemd service to $SYSTEMD_SERVICE...${NC}"
cp "$SCRIPT_DIR/avahi-k8s-advertiser.service" "$SYSTEMD_SERVICE"

# Create necessary directories
echo -e "${GREEN}Ensuring required directories exist...${NC}"
mkdir -p /etc/avahi/services
touch /etc/avahi/hosts

# Reload systemd
echo -e "${GREEN}Reloading systemd daemon...${NC}"
systemctl daemon-reload

# Enable the service
echo -e "${GREEN}Enabling avahi-k8s-advertiser service...${NC}"
systemctl enable avahi-k8s-advertiser

# Start the service
echo -e "${GREEN}Starting avahi-k8s-advertiser service...${NC}"
systemctl start avahi-k8s-advertiser

# Wait a moment for the service to start
sleep 2

# Check service status
echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo

if systemctl is-active --quiet avahi-k8s-advertiser; then
    echo -e "${GREEN}✓ Service is running${NC}"
    echo
    echo "Service status:"
    systemctl status avahi-k8s-advertiser --no-pager -l
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo
    echo "Service status:"
    systemctl status avahi-k8s-advertiser --no-pager -l
    echo
    echo -e "${YELLOW}Check logs with:${NC}"
    echo "  sudo journalctl -u avahi-k8s-advertiser -n 50"
    exit 1
fi

echo
echo -e "${GREEN}Useful commands:${NC}"
echo "  Start service:   sudo systemctl start avahi-k8s-advertiser"
echo "  Stop service:    sudo systemctl stop avahi-k8s-advertiser"
echo "  Restart service: sudo systemctl restart avahi-k8s-advertiser"
echo "  View status:     sudo systemctl status avahi-k8s-advertiser"
echo "  View logs:       sudo journalctl -u avahi-k8s-advertiser -f"
echo

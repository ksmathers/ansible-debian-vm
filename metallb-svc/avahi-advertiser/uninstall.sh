#!/bin/bash
#
# Uninstallation script for Kubernetes Avahi Advertiser Service
#
# This script removes the avahi-k8s-advertiser systemd service
# from the Kubernetes host machine.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_BIN="/usr/local/bin/avahi_k8s_advertiser.py"
SYSTEMD_SERVICE="/etc/systemd/system/avahi-k8s-advertiser.service"

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Kubernetes Avahi Advertiser Uninstaller${NC}"
echo -e "${YELLOW}========================================${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# Ask for confirmation
read -p "Are you sure you want to uninstall avahi-k8s-advertiser? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Stop the service
if systemctl is-active --quiet avahi-k8s-advertiser; then
    echo -e "${YELLOW}Stopping avahi-k8s-advertiser service...${NC}"
    systemctl stop avahi-k8s-advertiser
fi

# Disable the service
if systemctl is-enabled --quiet avahi-k8s-advertiser 2>/dev/null; then
    echo -e "${YELLOW}Disabling avahi-k8s-advertiser service...${NC}"
    systemctl disable avahi-k8s-advertiser
fi

# Remove systemd service file
if [ -f "$SYSTEMD_SERVICE" ]; then
    echo -e "${YELLOW}Removing systemd service file...${NC}"
    rm "$SYSTEMD_SERVICE"
fi

# Remove Python script
if [ -f "$INSTALL_BIN" ]; then
    echo -e "${YELLOW}Removing Python script...${NC}"
    rm "$INSTALL_BIN"
fi

# Reload systemd
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl daemon-reload

# Ask about cleaning up Avahi configuration
echo
read -p "Do you want to clean up Avahi hosts and service files created by this service? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Clean up Avahi hosts file
    if [ -f "/etc/avahi/hosts" ]; then
        echo -e "${YELLOW}Cleaning up /etc/avahi/hosts...${NC}"
        sed -i '/# Managed by k8s-avahi-advertiser/d' /etc/avahi/hosts
    fi
    
    # Remove service files
    echo -e "${YELLOW}Removing Avahi service files...${NC}"
    rm -f /etc/avahi/services/k8s-*.service
    
    # Restart Avahi daemon
    if systemctl is-active --quiet avahi-daemon; then
        echo -e "${YELLOW}Restarting Avahi daemon...${NC}"
        systemctl restart avahi-daemon
    fi
fi

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Uninstallation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "${GREEN}avahi-k8s-advertiser has been removed from your system.${NC}"
echo

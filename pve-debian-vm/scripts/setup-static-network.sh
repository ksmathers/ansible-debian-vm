#!/bin/bash
# Configure static IP network interface
# This script is called from preseed late_command when static IP is needed

set -e

STATIC_IP="$1"
GATEWAY="$2"
NETMASK="$3"
DNS_SERVER="$4"

if [ -z "$STATIC_IP" ] || [ -z "$GATEWAY" ] || [ -z "$NETMASK" ] || [ -z "$DNS_SERVER" ]; then
    echo "Error: Missing network configuration parameters"
    echo "Usage: $0 <static_ip> <gateway> <netmask> <dns_server>"
    exit 1
fi

echo "Configuring static IP: $STATIC_IP"

# Create network interfaces configuration for static IP
cat > /etc/network/interfaces << EOF
# This file describes the network interfaces available on your system
# and how to activate them. For more information, see interfaces(5).

source /etc/network/interfaces.d/*

# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface
auto ens18
iface ens18 inet static
  address $STATIC_IP
  netmask $NETMASK
  gateway $GATEWAY
  dns-nameservers $DNS_SERVER
EOF

echo "Static IP network configuration completed"
echo "IP: $STATIC_IP, Gateway: $GATEWAY, DNS: $DNS_SERVER"
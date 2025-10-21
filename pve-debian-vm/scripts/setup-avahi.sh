#!/bin/bash
# Configure Avahi daemon for mDNS/Bonjour .local domain resolution
# This script is called from preseed late_command

set -e

HOSTNAME="$1"
if [ -z "$HOSTNAME" ]; then
    HOSTNAME="debian-vm"
fi

echo "Setting up Avahi daemon configuration for hostname: $HOSTNAME"

# Create systemd override to delay Avahi startup until network is fully ready
mkdir -p /etc/systemd/system/avahi-daemon.service.d
cat > /etc/systemd/system/avahi-daemon.service.d/network-delay.conf << EOF
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
# Add a small delay to ensure both IPv4 and IPv6 are fully configured
ExecStartPre=/bin/sleep 3
EOF

# Create avahi-daemon configuration
cat > /etc/avahi/avahi-daemon.conf << EOF
[server]
host-name=$HOSTNAME
domain-name=local
use-ipv4=yes
use-ipv6=yes
allow-interfaces=ens18
check-response-ttl=no
use-iff-running=no
enable-dbus=yes
# Prevent hostname conflicts by being more tolerant of network changes
disallow-other-stacks=no
allow-point-to-point=no

[publish]
disable-publishing=no
publish-addresses=yes
publish-hinfo=yes
publish-workstation=yes
publish-domain=yes
publish-dns-servers=no
publish-resolv-conf-dns-servers=no

[reflector]
enable-reflector=no

[rlimits]
rlimit-core=0
rlimit-data=4194304
rlimit-fsize=0
rlimit-nofile=768
rlimit-stack=4194304
rlimit-nproc=3
EOF

echo "Avahi daemon configuration completed for $HOSTNAME.local"
echo "Service will be enabled automatically on first boot"
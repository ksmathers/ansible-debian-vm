#!/bin/bash
# Configure Avahi daemon for mDNS/Bonjour .local domain resolution
# This script is called from preseed late_command

set -e

HOSTNAME="$1"
if [ -z "$HOSTNAME" ]; then
    HOSTNAME="debian-vm"
fi

echo "Setting up Avahi daemon for hostname: $HOSTNAME"

# Enable avahi-daemon service
systemctl enable avahi-daemon

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
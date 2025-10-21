#!/bin/bash
# Configure SSH with key-based authentication
# This script is called from preseed late_command

set -e

SSH_PUBLIC_KEY="$1"
if [ -z "$SSH_PUBLIC_KEY" ]; then
    echo "Error: SSH public key not provided"
    exit 1
fi

echo "Configuring SSH with key-based authentication"

# Add debian user to sudo group for service management
usermod -aG sudo debian
echo "Added debian user to sudo group"

# Configure passwordless sudo for debian user (needed for automated service deployment)
echo "debian ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/debian
chmod 440 /etc/sudoers.d/debian
echo "Configured passwordless sudo for debian user"

# Enable SSH service
systemctl enable ssh

# Configure SSH daemon - SSH remains key-only for security
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#AuthorizedKeysFile/AuthorizedKeysFile/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Console/TTY access remains available with password for troubleshooting
# (This is the default behavior - console login uses /etc/passwd passwords)
echo "Note: Console (tty) password login remains enabled for troubleshooting"
echo "SSH access is restricted to key authentication only"

# Setup SSH keys for root user
mkdir -p /root/.ssh
chmod 700 /root/.ssh
echo "$SSH_PUBLIC_KEY" > /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

# Setup SSH keys for debian user
mkdir -p /home/debian/.ssh
chmod 700 /home/debian/.ssh
chown debian:debian /home/debian/.ssh
echo "$SSH_PUBLIC_KEY" > /home/debian/.ssh/authorized_keys
chmod 600 /home/debian/.ssh/authorized_keys
chown debian:debian /home/debian/.ssh/authorized_keys

echo "SSH configuration completed with key-based authentication"
echo "Console/TTY login: Both 'root' and 'debian' users can login via console with password"
echo "SSH network login: Key authentication only (passwords disabled for security)"
echo "Troubleshooting: Use ProxmoxVE console if network is unavailable"
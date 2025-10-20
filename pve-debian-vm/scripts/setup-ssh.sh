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

# Enable SSH service
systemctl enable ssh

# Configure SSH daemon
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#AuthorizedKeysFile/AuthorizedKeysFile/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

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
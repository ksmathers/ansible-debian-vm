#!/bin/bash

# Helper script to find VM IP address
# Usage: ./find-vm-ip.sh <vm_name_or_id> <proxmox_node>
# Example: ./find-vm-ip.sh debian-vm-1760927704 victor.ank.com

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <vm_name_or_id> <proxmox_node>"
    echo "Example: $0 debian-vm-1760927704 victor.ank.com"
    echo "         $0 163 victor.ank.com"
    exit 1
fi

VM_IDENTIFIER="$1"
PROXMOX_NODE="$2"

echo "Finding IP address for VM: $VM_IDENTIFIER on node: $PROXMOX_NODE"
echo "========================================"

# First, get the VM ID if a name was provided
if [[ "$VM_IDENTIFIER" =~ ^[0-9]+$ ]]; then
    VM_ID="$VM_IDENTIFIER"
    echo "Using VM ID: $VM_ID"
else
    echo "Looking up VM ID for name: $VM_IDENTIFIER"
    VM_ID=$(ssh root@$PROXMOX_NODE "qm list | grep '$VM_IDENTIFIER' | awk '{print \$1}'")
    if [ -z "$VM_ID" ]; then
        echo "Error: VM '$VM_IDENTIFIER' not found"
        exit 1
    fi
    echo "Found VM ID: $VM_ID"
fi

# Get VM status
echo "Checking VM status..."
VM_STATUS=$(ssh root@$PROXMOX_NODE "qm status $VM_ID" | awk '{print $2}')
echo "VM Status: $VM_STATUS"

if [ "$VM_STATUS" != "running" ]; then
    echo "Warning: VM is not running"
    exit 1
fi

# Method 1: Try QEMU guest agent first (if available)
echo ""
echo "Method 1: Checking QEMU guest agent..."
if ssh root@$PROXMOX_NODE "qm guest cmd $VM_ID network-get-interfaces" 2>/dev/null | grep -q "ip-address"; then
    echo "QEMU guest agent available:"
    VM_IP=$(ssh root@$PROXMOX_NODE "qm guest cmd $VM_ID network-get-interfaces" | grep -A5 '"name": "e' | grep '"ip-address"' | grep -v '127.0.0.1' | head -1 | sed 's/.*"ip-address": "\([^"]*\)".*/\1/')
    if [ -n "$VM_IP" ]; then
        echo "VM IP Address: $VM_IP"
        echo ""
        echo "You can now SSH to your VM:"
        echo "  ssh root@$VM_IP"
        echo "  ssh debian@$VM_IP"
        exit 0
    fi
else
    echo "QEMU guest agent not available or not responding"
fi

# Method 2: Get MAC address and search ARP table
echo ""
echo "Method 2: Using MAC address lookup..."
MAC_ADDRESS=$(ssh root@$PROXMOX_NODE "qm config $VM_ID | grep 'net0:' | sed 's/.*virtio=\([^,]*\).*/\1/'")
if [ -n "$MAC_ADDRESS" ]; then
    echo "VM MAC Address: $MAC_ADDRESS"
    
    # Check local ARP table first
    echo "Searching local ARP table..."
    VM_IP=$(arp -a | grep -i "$MAC_ADDRESS" | sed 's/.*(\([^)]*\)).*/\1/' | head -1)
    if [ -n "$VM_IP" ]; then
        echo "Found VM IP Address: $VM_IP"
        echo ""
        echo "You can now SSH to your VM:"
        echo "  ssh root@$VM_IP"
        echo "  ssh debian@$VM_IP"
        exit 0
    fi
    
    # Check Proxmox host neighbor table as fallback
    echo "Searching Proxmox host neighbor table..."
    VM_IP=$(ssh root@$PROXMOX_NODE "ip neigh | grep -i '$MAC_ADDRESS' | grep -v 'fe80' | awk '{print \$1}'" | head -1)
    if [ -n "$VM_IP" ]; then
        echo "Found VM IP Address: $VM_IP"
        echo ""
        echo "You can now SSH to your VM:"
        echo "  ssh root@$VM_IP"
        echo "  ssh debian@$VM_IP"
        exit 0
    fi
fi

# Method 3: Network scan as last resort
echo ""
echo "Method 3: Network scanning (this may take a moment)..."
NETWORK=$(ssh root@$PROXMOX_NODE "ip route | grep vmbr0 | grep '/24' | awk '{print \$1}'" | head -1)
if [ -n "$NETWORK" ]; then
    echo "Scanning network: $NETWORK"
    echo "Looking for SSH services..."
    
    # Scan for SSH on the network and try to match
    ssh root@$PROXMOX_NODE "nmap -p 22 --open $NETWORK 2>/dev/null | grep -B2 'open'" | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+' | while read ip; do
        echo "Found SSH service at: $ip"
        echo "Try: ssh root@$ip or ssh debian@$ip"
    done
else
    echo "Could not determine network range"
fi

echo ""
echo "If none of the above methods worked, try:"
echo "1. Wait a few minutes for the VM to fully boot"
echo "2. Check the Proxmox web interface console"
echo "3. Manually scan your network for new devices"
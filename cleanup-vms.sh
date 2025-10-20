#!/bin/bash

# Cleanup script for stuck VMs
# Usage: ./cleanup-vms.sh <proxmox-host> [vm-ids...]

if [ $# -lt 1 ]; then
    echo "Usage: $0 <proxmox-host> [vm-ids...]"
    echo "Example: $0 victor.ank.com 170 458 734"
    exit 1
fi

PROXMOX_HOST="$1"
shift

# If no VM IDs provided, use the known stuck ones
if [ $# -eq 0 ]; then
    VM_IDS=(170 458 734)
else
    VM_IDS=("$@")
fi

echo "🧹 Cleaning up stuck VMs on $PROXMOX_HOST..."
echo "VMs to clean: ${VM_IDS[*]}"
echo

for VM_ID in "${VM_IDS[@]}"; do
    echo "Processing VM $VM_ID..."
    
    # Stop the VM if running
    echo "  Stopping VM $VM_ID..."
    ssh root@$PROXMOX_HOST "qm stop $VM_ID" 2>/dev/null || echo "    VM $VM_ID was not running or doesn't exist"
    
    # Wait a moment for clean shutdown
    sleep 2
    
    # Force stop if still running
    echo "  Force stopping VM $VM_ID..."
    ssh root@$PROXMOX_HOST "qm stop $VM_ID --skiplock" 2>/dev/null || true
    
    # Remove the VM completely
    echo "  Destroying VM $VM_ID..."
    ssh root@$PROXMOX_HOST "qm destroy $VM_ID --purge --skiplock" 2>/dev/null || echo "    VM $VM_ID was already removed or doesn't exist"
    
    # Clean up custom ISO if it exists
    echo "  Cleaning up custom ISO for VM $VM_ID..."
    ssh root@$PROXMOX_HOST "rm -f /var/lib/vz/template/iso/debian-custom-${VM_ID}.iso" 2>/dev/null || true
    
    echo "  ✅ VM $VM_ID cleanup completed"
    echo
done

echo "🎉 Cleanup completed!"
echo
echo "Current VMs on $PROXMOX_HOST:"
ssh root@$PROXMOX_HOST "qm list"
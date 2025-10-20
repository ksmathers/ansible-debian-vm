#!/bin/bash

# ProxmoxVE Debian VM Creation Script
# Usage: ./install.sh <project_dir> <target_node>
# Example: ./install.sh pve-debian-vm tango.ank.com

set -e

# Check if correct number of arguments provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <project_directory> <target_node>"
    echo "Example: $0 pve-debian-vm tango.ank.com"
    echo ""
    echo "Available nodes:"
    echo "  - tango.ank.com"
    echo "  - victor.ank.com"  
    echo "  - xray.ank.com"
    exit 1
fi

PROJECT_DIR="$1"
TARGET_NODE="$2"

# Validate project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory '$PROJECT_DIR' does not exist"
    exit 1
fi

# Validate target node
case "$TARGET_NODE" in
    "tango.ank.com"|"victor.ank.com"|"xray.ank.com")
        echo "Creating VM on node: $TARGET_NODE"
        ;;
    *)
        echo "Error: Invalid target node '$TARGET_NODE'"
        echo "Valid nodes are: tango.ank.com, victor.ank.com, xray.ank.com"
        exit 1
        ;;
esac

# Check if ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "Error: ansible-playbook command not found"
    echo "Please install Ansible first:"
    echo "  brew install ansible"
    exit 1
fi

# Check if SSH key exists
if [ ! -f ~/.ssh/id_ed25519 ]; then
    echo "Error: SSH private key not found at ~/.ssh/id_ed25519"
    exit 1
fi

# Check if required files exist in project directory
REQUIRED_FILES=("inventory.yml" "create-vm.yml" "vars.yml" "preseed.cfg" "ansible.cfg")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        echo "Error: Required file '$file' not found in '$PROJECT_DIR'"
        exit 1
    fi
done

# Change to project directory
cd "$PROJECT_DIR"

echo "========================================"
echo "ProxmoxVE Debian VM Creation"
echo "========================================"
echo "Project Directory: $PROJECT_DIR"
echo "Target Node: $TARGET_NODE"
echo "Timestamp: $(date)"
echo "========================================"

# Run the Ansible playbook
echo "Running Ansible playbook..."
ansible-playbook create-vm.yml \
    --extra-vars "target_host=$TARGET_NODE" \
    --limit "$TARGET_NODE" \
    -v

echo "========================================"
echo "VM creation process completed!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. The VM is now installing Debian automatically"
echo "2. Installation will take approximately 10-15 minutes"
echo "3. You can monitor progress in the ProxmoxVE web interface"
echo "4. Once complete, you can SSH to the VM with:"
echo "   - root:debian or debian:debian"
echo ""
echo "To check VM status:"
echo "ssh root@$TARGET_NODE 'qm list'"
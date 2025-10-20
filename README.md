# ProxmoxVE Debian VM Creation with Ansible

This project automates the creation of Debian VMs on a ProxmoxVE cluster using Ansible.

## Features

- Automated Debian VM creation on any ProxmoxVE node
- Custom ISO creation with preseed configuration for unattended installation
- Configurable VM specifications (CPU, memory, disk, network)
- Uses ProxmoxVE API tokens for authentication
- SSH key-based authentication to nodes

## Prerequisites

1. **Ansible**: Install Ansible on your local machine
   ```bash
   brew install ansible
   ```

2. **SSH Access**: SSH private key at `~/.ssh/id_ed25519` with access to ProxmoxVE nodes

3. **ProxmoxVE API Token**: Available via keyring (`keyring get proxmoxve ansible@pve`)

4. **Debian ISO**: Mounted on ProxmoxVE cluster as shared storage `drivep-public`

## File Structure

```
ansible-debian-vm/
├── install.sh              # Main execution script
└── pve-debian-vm/
    ├── ansible.cfg          # Ansible configuration
    ├── inventory.yml        # ProxmoxVE nodes inventory
    ├── create-vm.yml        # Main playbook
    ├── vars.yml             # VM configuration variables
    └── preseed.cfg          # Debian preseed configuration
```

## Usage

Run the installation script with the project directory and target node:

```bash
./install.sh pve-debian-vm <target_node>
```

### Examples

```bash
# Create VM on tango node
./install.sh pve-debian-vm tango.ank.com

# Create VM on victor node
./install.sh pve-debian-vm victor.ank.com

# Create VM on xray node
./install.sh pve-debian-vm xray.ank.com
```

## Available Nodes

- `tango.ank.com`
- `victor.ank.com`
- `xray.ank.com`

## VM Configuration

Default VM specifications (configurable in `vars.yml`):

- **Memory**: 2048 MB
- **CPU**: 2 cores, 1 socket
- **Disk**: 20GB (qcow2 format)
- **Network**: Connected to vmbr0 bridge
- **Storage**: local-lvm

## Installation Process

1. **VM Creation**: Creates a new VM with unique ID on the specified node
2. **Custom ISO**: Extracts Debian ISO from shared storage and creates custom ISO with preseed
3. **Automated Installation**: Boots VM with custom ISO for unattended Debian installation
4. **Cleanup**: Removes temporary files after VM creation

## Default Credentials

After installation completes (10-15 minutes):

- **Root access**: `root` / `debian`
- **User access**: `debian` / `debian`

## Monitoring

You can monitor the installation progress through:

1. **ProxmoxVE Web Interface**: Console tab of the VM
2. **SSH to node**: `ssh root@<node> 'qm list'` to see VM status

## Customization

### VM Specifications

Edit `pve-debian-vm/vars.yml` to modify:
- CPU cores and memory
- Disk size and storage
- Network bridge
- VM naming

### Installation Settings

Edit `pve-debian-vm/preseed.cfg` to modify:
- User accounts and passwords
- Network configuration
- Package selection
- Post-installation commands

### Node Configuration

Edit `pve-debian-vm/inventory.yml` to:
- Add/remove ProxmoxVE nodes
- Modify SSH settings
- Update API credentials

## Troubleshooting

1. **SSH Key Issues**: Ensure `~/.ssh/id_ed25519` exists and has proper permissions
2. **API Access**: Verify ProxmoxVE API token with `keyring get proxmoxve ansible@pve`
3. **Debian ISO**: Check that Debian ISO exists in `/mnt/pve/drivep-public` on nodes
4. **VM ID Conflicts**: Script automatically handles ID conflicts by incrementing

## Security Notes

- API tokens are stored in system keyring
- SSH keys should be properly secured
- Default passwords should be changed after VM creation
- Consider using SSH key authentication instead of passwords for production use
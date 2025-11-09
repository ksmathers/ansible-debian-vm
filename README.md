# ProxmoxVE Debian VM Creation and Service Deployment

This project automates the creation of Debian VMs on a ProxmoxVE cluster and deployment of services using Ansible. It supports both VM creation and post-installation service deployment through a unified Python interface.

## Features

### VM Creation
- Automated Debian VM creation on any ProxmoxVE node
- Custom ISO creation with preseed configuration for unattended installation
- Hostname-based DNS resolution with automatic static IP configuration
- Configurable VM specifications (CPU, memory, disk, network)
- mDNS/Avahi support for `.local` domain advertisement
- Console password authentication with SSH key-only network access
- sudo configuration for service deployment readiness

### Service Deployment
- Post-VM-creation service installation (e.g., minikube)
- Modular service deployment architecture
- Automated inventory generation for service targets

### Enhanced Features
- Dual operation modes with intelligent directory detection
- Comprehensive dry-run capability with configuration preview
- Modern password hashing with yescrypt/SHA-512 support
- Modular shell script architecture for maintainability
- SSH key-based authentication with console fallback

## Prerequisites

1. **Ansible**: Install Ansible on your local machine
   ```bash
   brew install ansible
   ```

2. **SSH Access**: SSH private key at `~/.ssh/id_ed25519` with access to ProxmoxVE nodes

3. **ProxmoxVE API Token**: Available via keyring (`keyring get proxmoxve ansible@pve`)
   ```bash
   keyring set proxmoxve ansible@pve <<'END'
   { 
      "token-id": "ansible@pve!automation", 
      "secret": "replace-with-your-secret", 
      "expire": "never",
      "endpoints": [ "tango.ank.com", "victor.ank.com", "xray.ank.com", "zulu.ank.com" ], 
      "user": "ansible@pve" 
   }
   END
   ```

4. **Python 3**: Required for the installation script
   ```bash
   # Usually pre-installed on macOS/Linux
   python3 --version
   ```

5. **Debian ISO**: Mounted on ProxmoxVE cluster as shared storage `drivep-public`

## File Structure

```
ansible-debian-vm/
├── install.py              # Main Python automation tool
├── install.sh              # Legacy shell script (deprecated)
├── cleanup-vms.sh          # VM cleanup utility
├── README.md               # Project documentation
├── pve-debian-vm/          # VM creation configuration
│   ├── ansible.cfg         # Ansible configuration
│   ├── inventory.yml       # ProxmoxVE nodes inventory
│   ├── create-vm.yml       # VM creation playbook
│   ├── vars.yml            # VM configuration variables
│   ├── preseed.cfg.j2      # Debian preseed template (Jinja2)
│   ├── requirements.yml    # Ansible collection requirements
│   └── scripts/            # Modular configuration scripts
│       ├── setup-ssh.sh    # SSH and sudo configuration
│       ├── setup-avahi.sh  # mDNS/Avahi setup
│       └── setup-static-network.sh  # Static network configuration
├── minikube-svc/           # Minikube Kubernetes cluster service
│   ├── ansible.cfg         # Service-specific Ansible config
│   ├── install-minikube.yml # Minikube installation playbook
│   └── inventory.yml.j2    # Dynamic inventory template
└── metallb-svc/            # MetalLB LoadBalancer service  
    ├── ansible.cfg         # Service-specific Ansible config
    ├── install-metallb.yml # MetalLB installation playbook
    ├── inventory.yml.j2    # Dynamic inventory template
    └── README.md           # Detailed MetalLB documentation
```

## Usage

The Python automation tool supports two operation modes based on directory naming conventions:

### VM Creation Mode
Create new VMs using directories ending in `-vm`:

```bash
./install.py [OPTIONS] <project_directory> <target_node>
```

### Service Deployment Mode  
Deploy services to existing VMs using directories ending in `-svc`:

```bash

./install.py [OPTIONS] <service_name> <target_hostname>
```

### Options

- `--hostname=HOSTNAME`: Set VM hostname (enables DNS resolution and static IP)
- `--mem=SIZE`: Memory allocation (default: 2048M, examples: 4G, 8192M)
- `--disk=SIZE`: Disk size (default: 20G, examples: 100G, 2T)  
- `--cpus=NUM`: CPU cores (default: 2)
- `--vmid=NUM`: Specify VM ID (100-999). If not provided, auto-generated
- `--password=PASS`: Console password (default: debian)
- `--secure`: Store password in keyring, show secret name instead of actual password
- `--dry-run`: Preview configuration without execution

### Examples

#### VM Creation
```bash
# Basic VM creation
./install.py pve-debian-vm victor.ank.com

# VM with hostname and static IP (DNS resolution)
./install.py --hostname=jinx.ank.com pve-debian-vm victor.ank.com

# VM with specific ID for organized management
./install.py --hostname=web.ank.com --vmid=200 pve-debian-vm victor.ank.com

# VM with custom password stored securely in keyring
./install.py --hostname=secure.ank.com --password=mypassword --secure pve-debian-vm victor.ank.com

# High-spec VM with custom configuration
./install.py --hostname=gpu.ank.com --mem=8G --disk=100G --cpus=4 --vmid=300 pve-debian-vm tango.ank.com

# Preview configuration without creating VM
./install.py --hostname=test.ank.com --vmid=150 --dry-run pve-debian-vm victor.ank.com
```

#### Service Deployment
```bash
# Deploy minikube to existing VM
./install.py minikube-svc jinx.ank.com

# Preview service deployment
./install.py --dry-run minikube-svc jinx.ank.com

# Deploy MetalLB LoadBalancer to existing minikube cluster
./install.py metallb-svc jinx.ank.com

# Deploy MetalLB with custom IP range and test service
./install.py --metallb-ip-range=192.168.1.200-192.168.1.210 --test-service metallb-svc jinx.ank.com
```

## Available Services

### minikube-svc
Deploys a complete minikube Kubernetes cluster configured with `--driver=none` for maximum performance and NodePort service exposure.

**Features:**
- Container runtime: containerd
- Networking: CNI plugins
- Auto-start: systemd service 
- Remote access: kubectl configuration
- Service exposure: NodePort

**Usage:**
```bash
./install.py minikube-svc <hostname>
```

### metallb-svc  
Adds MetalLB LoadBalancer support to existing minikube clusters, enabling services to receive external IP addresses directly accessible from the host network.

**Prerequisites:** Existing minikube cluster (deployed via minikube-svc)

**Features:**
- LoadBalancer IP assignment
- Layer 2 (ARP) networking
- Automatic IP range calculation
- Custom IP range support
- Optional test service deployment

**Usage:**
```bash
# Basic installation with auto-calculated IP range
./install.py metallb-svc <hostname>

# Custom IP range
./install.py --metallb-ip-range=<start-ip>-<end-ip> metallb-svc <hostname>

# Include test service
./install.py --test-service metallb-svc <hostname>
```

## Available Nodes

- `tango.ank.com`
- `victor.ank.com` 
- `xray.ank.com`

## Network Configuration

### Static IP Assignment
When `--hostname` is provided and the hostname resolves to an IP address:
- **Gateway**: 10.0.42.1
- **Netmask**: 255.255.255.0  
- **DNS**: 10.0.42.1
- **Static IP**: Resolved from hostname DNS lookup

### DHCP Configuration
When `--hostname` is not provided or doesn't resolve:
- Automatic DHCP configuration
- Dynamic IP assignment from router

### mDNS Support
All VMs automatically advertise themselves as `<vmname>.local` via Avahi daemon for local network discovery.

## VM Configuration

Default VM specifications (configurable via command-line options):

- **Memory**: 2048 MB
- **CPU**: 2 cores, 1 socket
- **Disk**: 20GB (qcow2 format)
- **Network**: Connected to vmbr0 bridge
- **Storage**: local-lvm

## Installation Process

### VM Creation Workflow
1. **Hostname Resolution**: DNS lookup for static IP configuration (if applicable)
2. **VM Creation**: Creates a new VM with unique ID on the specified node
3. **Custom ISO**: Extracts Debian ISO and creates custom ISO with preseed configuration
4. **Automated Installation**: Boots VM with custom ISO for unattended Debian installation
5. **Configuration**: Applies SSH keys, sudo setup, mDNS, and network configuration
6. **Cleanup**: Removes temporary files after VM creation

### Service Deployment Workflow
1. **Target Validation**: Verifies target VM accessibility via SSH
2. **Inventory Generation**: Creates dynamic Ansible inventory for target
3. **Service Installation**: Executes service-specific Ansible playbook
4. **Verification**: Confirms successful service deployment

## Authentication & Security

### SSH Access
- **Network SSH**: Key-based authentication only (passwords disabled)
- **SSH Keys**: Automatically deployed from `~/.ssh/id_ed25519.pub`
- **sudo Access**: debian user configured with passwordless sudo for service deployment

### Console Access
- **Console Login**: Password authentication enabled for troubleshooting  
- **Root Access**: Available via console with configurable password
- **User Access**: `debian` user with configurable password (default: debian)

### Password Security
- **Default Mode**: Console credentials (username/password) displayed in configuration summary for convenience
- **Secure Mode** (`--secure`): Credentials stored in system keyring as JSON and secret name displayed instead
  ```bash
  # Install keyring support if needed
  pip3 install keyring
  
  # Use secure mode for production environments
  ./install.py --password=mypassword --secure --hostname=prod.ank.com pve-debian-vm victor.ank.com
  
  # Credentials retrieval from keyring (stored as JSON)
  python3 -c "
  import keyring, json
  creds = json.loads(keyring.get_password('proxmoxve-vm-console', 'vm-console-prod'))
  print(f'Username: {creds[\"username\"]}')
  print(f'Password: {creds[\"password\"]}')
  "
  ```
- **JSON Format**: Credentials stored as `{"username": "debian", "password": "yourpassword"}` for future extensibility
- **Keyring Storage**: Credentials stored under service `proxmoxve-vm-console` with VM-specific names

### mDNS Discovery
VMs advertise themselves as `<vmname>.local` for easy local network discovery without DNS configuration.

## Monitoring

You can monitor the installation progress through:

1. **ProxmoxVE Web Interface**: Console tab of the VM shows installation progress
2. **SSH to node**: `ssh root@<node> 'qm list'` to see VM status
3. **mDNS Discovery**: `ping <vmname>.local` once installation completes
4. **SSH Test**: `ssh debian@<hostname>` for connectivity verification

## Customization

### VM Specifications
Use command-line options to customize:
```bash
./install.py --mem=8G --disk=100G --cpus=4 --hostname=custom.ank.com pve-debian-vm victor.ank.com
```

### Advanced VM Configuration
Edit `pve-debian-vm/vars.yml` to modify:
- Storage backend selection
- Network bridge configuration  
- VM naming patterns
- ISO source locations

### Installation Settings
Edit `pve-debian-vm/preseed.cfg.j2` (Jinja2 template) to modify:
- Package selection
- Post-installation commands
- Network configuration templates
- User account settings

### Service Deployment
Create new service directories ending in `-svc`:
1. Create directory: `mkdir my-service-svc`
2. Add `ansible.cfg`, playbook, and inventory template
3. Deploy: `./install.py my-service-svc target.hostname.com`

### Node Configuration
Edit `pve-debian-vm/inventory.yml` to:
- Add/remove ProxmoxVE nodes
- Modify SSH settings
- Update connection parameters

## Troubleshooting

### Common Issues

1. **SSH Key Issues**: Ensure `~/.ssh/id_ed25519` exists and has proper permissions (600)
2. **API Access**: Verify ProxmoxVE API token with `keyring get proxmoxve ansible@pve`
3. **Debian ISO**: Check that Debian ISO exists in `/mnt/pve/drivep-public` on nodes
4. **VM ID Conflicts**: Script automatically handles ID conflicts by incrementing
5. **Hostname Resolution**: Use `--dry-run` to preview network configuration
6. **Service Deployment**: Ensure target VM is accessible via SSH before deployment

### Python Dependencies
```bash
# Install required Python packages
pip3 install jinja2

# For secure credential storage
pip3 install keyring
```

### Credential Management
When using `--secure` mode, credentials are stored in the system keyring and can be retrieved programmatically:

```bash
# List all stored VM credentials
python3 -c "
import keyring
# Note: This requires platform-specific keyring backends
# On macOS: uses Keychain, on Linux: uses various backends
"

# Retrieve specific VM credentials
python3 -c "
import keyring, json
secret_name = 'vm-console-myvm'  # Replace with your VM's secret name
creds_json = keyring.get_password('proxmoxve-vm-console', secret_name)
if creds_json:
    creds = json.loads(creds_json)
    print(f'VM: {secret_name}')
    print(f'Username: {creds[\"username\"]}')
    print(f'Password: {creds[\"password\"]}')
else:
    print(f'No credentials found for {secret_name}')
"

# Delete stored credentials
python3 -c "
import keyring
keyring.delete_password('proxmoxve-vm-console', 'vm-console-myvm')
print('Credentials deleted')
"
```

### Directory Naming
- VM creation: Directory must end with `-vm` (e.g., `pve-debian-vm`)
- Service deployment: Directory must end with `-svc` (e.g., `minikube-svc`)

### Network Connectivity
```bash
# Test hostname resolution
nslookup your-hostname.ank.com

# Test mDNS resolution  
ping vmname.local

# Test SSH connectivity
ssh -o ConnectTimeout=5 debian@target-host
```

## Migration from install.sh

The legacy `install.sh` script is deprecated. To migrate:

1. **Replace calls**: Change `./install.sh` to `./install.py`
2. **Add options**: Use `--hostname`, `--mem`, etc. instead of editing config files
3. **New features**: Take advantage of service deployment and dry-run capabilities

### Legacy to Modern Examples
```bash
# Old approach
./install.sh pve-debian-vm victor.ank.com

# New approach with enhanced features  
./install.py --hostname=myvm.ank.com --mem=4G pve-debian-vm victor.ank.com
```

## Security Notes

- **API Tokens**: Stored securely in system keyring
- **SSH Keys**: Automatically deployed, should be properly secured (600 permissions)  
- **Password Security**: Console passwords should be changed after VM creation for production
- **Network Security**: SSH network access is key-only; passwords disabled for remote connections
- **sudo Access**: debian user has passwordless sudo for service deployment automation
- **mDNS Security**: Consider firewall rules for .local domain advertisement in production networks

## Project Evolution

This project has evolved from a simple shell script to a comprehensive Python-based automation framework:

- **v1**: Basic shell script VM creation
- **v2**: Enhanced shell script with options and error handling  
- **v3**: Complete Python rewrite with dual operation modes
- **v4**: Service deployment framework and advanced networking features

The Python implementation provides better maintainability, error handling, and extensibility for future enhancements.
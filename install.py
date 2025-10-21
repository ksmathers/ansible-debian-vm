#!/usr/bin/env python3
"""
ProxmoxVE Debian VM Creation and Service Deployment Tool

This script supports two operation modes:
1. VM Creation: ./install.py [OPTIONS] <project_directory> <target_node>
2. Service Deployment: ./install.py [OPTIONS] <service_name> <target_hostname>

Examples:
  VM Creation:      ./install.py --hostname=jinx.ank.com --mem=4G pve-debian-vm tango.ank.com
  Service Deploy:   ./install.py minikube-svc jinx.ank.com
"""

import argparse
import os
import sys
import subprocess
import socket
import re
import crypt
import secrets
import string
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from jinja2 import Template


class VMManager:
    """Main class for VM creation and service deployment operations."""
    
    # Default configuration values
    DEFAULT_MEMORY = 2048  # MB
    DEFAULT_CPU_CORES = 2
    DEFAULT_DISK_SIZE = 20  # GB
    DEFAULT_PASSWORD = "debian"
    
    # Valid Proxmox nodes
    VALID_NODES = ["tango.ank.com", "victor.ank.com", "xray.ank.com"]
    
    def __init__(self):
        self.operation_mode = None
        self.project_dir = None
        self.target_node = None
        self.service_name = None
        self.target_hostname = None
        
        # VM configuration
        self.hostname = None
        self.vm_id = None
        self.memory_mb = self.DEFAULT_MEMORY
        self.cpu_cores = self.DEFAULT_CPU_CORES
        self.disk_size_gb = self.DEFAULT_DISK_SIZE
        self.console_password = self.DEFAULT_PASSWORD
        self.secure_mode = False
        self.password_secret_name = None
        self.dry_run = False
        
        # Network configuration
        self.vm_ip = ""
        self.use_static_ip = False
        self.vm_short_name = ""

    def parse_arguments(self):
        """Parse command line arguments and determine operation mode."""
        parser = argparse.ArgumentParser(
            description="ProxmoxVE Debian VM Creation and Service Deployment Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Operation Modes:
  VM Creation:      %(prog)s [OPTIONS] <project_directory> <target_node>
  Service Deploy:   %(prog)s [OPTIONS] <service_name> <target_hostname>

Examples:
  %(prog)s --hostname=jinx.ank.com --mem=4G pve-debian-vm tango.ank.com
  %(prog)s minikube-svc jinx.ank.com

Available nodes: tango.ank.com, victor.ank.com, xray.ank.com

Network Configuration:
  Static IP: Gateway 10.0.42.1, Netmask 255.255.255.0
  DHCP: Automatic configuration when hostname doesn't resolve
            """
        )
        
        # Optional arguments
        parser.add_argument(
            "--hostname", 
            help="VM hostname (e.g., jinx.ank.com). If hostname resolves to IP, static network config will be used"
        )
        parser.add_argument(
            "--mem", 
            default=f"{self.DEFAULT_MEMORY}M",
            help=f"Memory size (default: {self.DEFAULT_MEMORY}M). Examples: 4G, 2048M"
        )
        parser.add_argument(
            "--disk", 
            default=f"{self.DEFAULT_DISK_SIZE}G",
            help=f"Disk size (default: {self.DEFAULT_DISK_SIZE}G). Examples: 100G, 2T"
        )
        parser.add_argument(
            "--cpus", 
            type=int, 
            default=self.DEFAULT_CPU_CORES,
            help=f"Number of CPU cores (default: {self.DEFAULT_CPU_CORES})"
        )
        parser.add_argument(
            "--password", 
            default=self.DEFAULT_PASSWORD,
            help=f"Console password for debian user (default: {self.DEFAULT_PASSWORD}). Used for console login when SSH is not available"
        )
        parser.add_argument(
            "--vmid",
            type=int,
            help="Specify VM ID (100-999). If not provided, a random ID will be generated automatically"
        )
        parser.add_argument(
            "--secure",
            action="store_true",
            help="Store console password in keyring and show secret name instead of actual password"
        )
        parser.add_argument(
            "--dry-run", 
            action="store_true",
            help="Show what would be done without executing"
        )
        
        # Positional arguments
        parser.add_argument(
            "package_name",
            help="Project directory (for VM creation) or service name (for service deployment)"
        )
        parser.add_argument(
            "host_name",
            help="Target node (for VM creation) or target hostname (for service deployment)"
        )
        
        args = parser.parse_args()
        
        # Determine operation mode based on directory naming convention
        if Path(args.package_name).is_dir():
            if args.package_name.endswith('-svc'):
                # Service Deployment mode: directory ending in '-svc'
                self.operation_mode = "service-deployment" 
                self.service_name = args.package_name
                self.target_hostname = args.host_name
                self.project_dir = self.service_name
                
            elif args.package_name.endswith('-vm'):
                # VM Creation mode: directory ending in '-vm'
                self.operation_mode = "vm-creation"
                self.project_dir = args.package_name
                self.target_node = args.host_name
                
                if self.target_node not in self.VALID_NODES:
                    print(f"Error: Invalid target node '{self.target_node}'")
                    print(f"Valid nodes are: {', '.join(self.VALID_NODES)}")
                    sys.exit(1)
                    
            else:
                print(f"Error: Directory '{args.package_name}' must end with '-vm' (for VM creation) or '-svc' (for service deployment)")
                print("Examples: pve-debian-vm (VM creation), minikube-svc (service deployment)")
                sys.exit(1)
                
        else:
            print(f"Error: Directory '{args.package_name}' does not exist")
            print("For VM creation, provide a directory ending in '-vm' (e.g., pve-debian-vm)")
            print("For service deployment, provide a directory ending in '-svc' (e.g., minikube-svc)")
            sys.exit(1)
        
        # Process optional arguments
        self.hostname = args.hostname
        self.console_password = args.password
        self.dry_run = args.dry_run
        self.secure_mode = args.secure
        self.cpu_cores = args.cpus
        
        # Process VM ID with validation
        if args.vmid is not None:
            if args.vmid < 100 or args.vmid > 999:
                print(f"Error: VM ID must be between 100 and 999 (provided: {args.vmid})")
                sys.exit(1)
            self.vm_id = args.vmid
        else:
            self.vm_id = None  # Will be generated automatically by Ansible
        
        # Handle secure password storage
        if self.secure_mode:
            self.setup_secure_password()
        
        # Convert memory and disk sizes
        self.memory_mb = self.convert_memory_to_mb(args.mem)
        self.disk_size_gb = self.convert_disk_to_gb(args.disk)

    def convert_memory_to_mb(self, mem_str: str) -> int:
        """Convert memory string to megabytes."""
        match = re.match(r'^(\d+)([GgMm]?)$', mem_str)
        if not match:
            print(f"Error: Invalid memory format '{mem_str}'. Use format like '4G' or '2048M'.")
            sys.exit(1)
            
        value = int(match.group(1))
        unit = match.group(2).lower() if match.group(2) else 'm'
        
        if unit == 'g':
            return value * 1024
        elif unit == 'm':
            return value
        else:
            print(f"Error: Invalid memory unit '{unit}'. Use G for gigabytes or M for megabytes.")
            sys.exit(1)

    def convert_disk_to_gb(self, disk_str: str) -> int:
        """Convert disk string to gigabytes."""
        match = re.match(r'^(\d+)([GgTt]?)$', disk_str)
        if not match:
            print(f"Error: Invalid disk format '{disk_str}'. Use format like '100G' or '2T'.")
            sys.exit(1)
            
        value = int(match.group(1))
        unit = match.group(2).lower() if match.group(2) else 'g'
        
        if unit == 't':
            return value * 1024
        elif unit == 'g':
            return value
        else:
            print(f"Error: Invalid disk unit '{unit}'. Use G for gigabytes or T for terabytes.")
            sys.exit(1)

    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """Try to resolve hostname to IP address. Returns IP if successful, None if not."""
        try:
            ip = socket.gethostbyname(hostname)
            return ip
        except socket.gaierror:
            return None

    def hash_password(self, password: str) -> str:
        """Generate password hash for preseed configuration."""
        try:
            # Use mkpasswd if available (for yescrypt support)
            result = subprocess.run(
                ["mkpasswd", "--method=sha-512", password],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to openssl (widely available and reliable)
            try:
                result = subprocess.run(
                    ["openssl", "passwd", "-6", password],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError:
                # Final fallback to Python's crypt module
                salt_chars = string.ascii_letters + string.digits + "./"
                salt = ''.join(secrets.choice(salt_chars) for _ in range(16))
                return crypt.crypt(password, f"$6${salt}$")

    def extract_vm_id_from_output(self, ansible_output: str) -> Optional[int]:
        """Extract VM ID from Ansible output."""
        # Look for patterns like 'vm_id": 245' or 'VM ID: 245'
        import re
        patterns = [
            r'"vm_id":\s*["\']?(\d+)["\']?',  # JSON-style output
            r'VM ID:\s*(\d+)',                # Display message
            r'"ansible_facts":\s*{\s*"vm_id":\s*["\']?(\d+)["\']?'  # Ansible facts
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ansible_output)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None

    def setup_secure_password(self):
        """Store console credentials as JSON in keyring and set up secret name for display."""
        try:
            import keyring
            import json
            
            # Generate a unique secret name based on VM info
            if self.hostname:
                secret_name = f"vm-console-{self.hostname.split('.')[0]}"
            else:
                secret_name = f"vm-console-{self.vm_short_name or 'debian-vm'}"
            
            # Create credentials object with username and password
            credentials = {
                "username": "debian",  # Default VM username
                "password": self.console_password
            }
            
            # Store credentials as JSON in keyring
            keyring.set_password("proxmoxve-vm-console", secret_name, json.dumps(credentials))
            self.password_secret_name = secret_name
            
            print(f"Console credentials stored securely in keyring as: {secret_name}")
            print(f"  Username: {credentials['username']}")
            print(f"  Password: [stored securely]")
            
        except ImportError:
            print("Error: keyring module not available. Install with: pip install keyring")
            print("Falling back to showing actual password.")
            self.secure_mode = False
        except Exception as e:
            print(f"Error storing password in keyring: {e}")
            print("Falling back to showing actual password.")
            self.secure_mode = False

    def validate_environment(self):
        """Check that all required tools and files are available."""
        # Check if ansible is installed
        if not subprocess.run(["which", "ansible-playbook"], 
                            capture_output=True, text=True).returncode == 0:
            print("Error: ansible-playbook command not found")
            print("Please install Ansible first:")
            print("  brew install ansible")
            sys.exit(1)
        
        # Check if SSH key exists
        ssh_key_path = Path.home() / ".ssh" / "id_ed25519"
        if not ssh_key_path.exists():
            print(f"Error: SSH private key not found at {ssh_key_path}")
            sys.exit(1)
        
        # Check required files exist in project directory
        if self.operation_mode == "vm-creation":
            required_files = ["inventory.yml", "create-vm.yml", "vars.yml", "preseed.cfg.j2", "ansible.cfg"]
            for file in required_files:
                file_path = Path(self.project_dir) / file
                if not file_path.exists():
                    print(f"Error: Required file '{file}' not found in '{self.project_dir}'")
                    sys.exit(1)

    def process_hostname(self):
        """Process hostname and determine network configuration."""
        if self.hostname:
            print(f"Processing hostname: {self.hostname}")
            
            # Try to resolve the hostname to an IP address
            self.vm_ip = self.resolve_hostname(self.hostname)
            if self.vm_ip:
                self.use_static_ip = True
                print(f"Will use static IP configuration: {self.vm_ip}")
                print("Gateway: 10.0.42.1, Netmask: 255.255.255.0")
            else:
                self.use_static_ip = False
                print("Hostname did not resolve - will use DHCP configuration")
                self.vm_ip = ""
            
            # Extract short hostname (everything before first dot)
            self.vm_short_name = self.hostname.split('.')[0]
        else:
            print("No hostname specified - will use default hostname 'debian-vm'")
            self.vm_short_name = "debian-vm"
            self.use_static_ip = False
            self.vm_ip = ""

    def print_configuration(self):
        """Print current configuration summary."""
        print("=" * 40)
        if self.dry_run:
            print(f"DRY RUN - {self.operation_mode.replace('-', ' ').title()}")
        else:
            print(f"{self.operation_mode.replace('-', ' ').title()}")
        print("=" * 40)
        
        print(f"Project Directory: {self.project_dir}")
        
        if self.operation_mode == "vm-creation":
            print(f"Target Node: {self.target_node}")
            if self.hostname:
                print(f"Hostname: {self.hostname}")
                if self.use_static_ip:
                    print(f"Network: Static IP ({self.vm_ip})")
                    print("Gateway: 10.0.42.1, Netmask: 255.255.255.0")
                else:
                    print("Network: DHCP (hostname did not resolve)")
            else:
                print("Hostname: debian-vm (default)")
                print("Network: DHCP (default)")
            print(f"Memory: {self.memory_mb}MB")
            print(f"CPU Cores: {self.cpu_cores}")
            print(f"Disk Size: {self.disk_size_gb}GB")
            if self.vm_id is not None:
                print(f"VM ID: {self.vm_id} (specified)")
            else:
                print("VM ID: Auto-generated")
        else:
            print(f"Service: {self.service_name}")
            print(f"Target Hostname: {self.target_hostname}")
        
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def generate_config_summary(self, ansible_vm_id: Optional[int] = None):
        """Generate human-readable configuration summary for dry run."""
        print("\n" + "=" * 50)
        print("CONFIGURATION SUMMARY")
        print("=" * 50)
        print(f"Virtual Machine Name: {self.vm_short_name}")
        if self.hostname:
            print(f"Fully Qualified Domain Name: {self.hostname}")
        print(f"Target Proxmox Node: {self.target_node}")
        if self.vm_id is not None:
            print(f"VM ID: {self.vm_id} (user-specified)")
        elif ansible_vm_id is not None:
            print(f"VM ID: {ansible_vm_id} (auto-generated)")
        else:
            print("VM ID: Auto-generated by Ansible")
        print(f"Memory Allocation: {self.memory_mb} MB ({self.memory_mb/1024:.1f} GB)")
        print(f"CPU Cores: {self.cpu_cores}")
        print(f"Disk Size: {self.disk_size_gb} GB")
        
        if self.use_static_ip:
            print(f"Network Configuration: Static")
            print(f"  IP Address: {self.vm_ip}")
            print(f"  Gateway: 10.0.42.1")
            print(f"  Netmask: 255.255.255.0")
            print(f"  DNS: 10.0.42.1")
        else:
            print(f"Network Configuration: DHCP")
        
        # Display console credentials based on security mode
        if self.secure_mode and self.password_secret_name:
            print(f"Console Credentials: Stored in keyring as '{self.password_secret_name}' (username: debian)")
        else:
            print(f"Console Credentials: debian / {self.console_password}")
        
        print(f"SSH Access: Key-based authentication only")
        print(f"mDNS/Avahi: Enabled ({self.vm_short_name}.local)")
        print("=" * 50)

    def run_vm_creation(self):
        """Execute VM creation workflow."""
        # Change to project directory
        os.chdir(self.project_dir)
        
        # Generate password hash
        console_password_hash = self.hash_password(self.console_password)
        
        # Prepare ansible command
        ansible_cmd = [
            "ansible-playbook", "create-vm.yml",
            "--extra-vars", f"target_host={self.target_node}",
            "--extra-vars", f"vm_memory={self.memory_mb}",
            "--extra-vars", f"vm_cores={self.cpu_cores}",
            "--extra-vars", f"vm_disk_size={self.disk_size_gb}",
            "--extra-vars", f"vm_hostname={self.vm_short_name}",
            "--extra-vars", f"vm_fqdn={self.hostname or ''}",
            "--extra-vars", f"vm_static_ip={self.vm_ip}",
            "--extra-vars", f"vm_use_static_ip={str(self.use_static_ip).lower()}",
            "--extra-vars", f"console_password_hash={console_password_hash}",
        ]
        
        # Add VM ID if specified by user
        if self.vm_id is not None:
            ansible_cmd.extend(["--extra-vars", f"user_vm_id={self.vm_id}"])
        
        ansible_cmd.extend([
            "--limit", self.target_node,
            "-v"
        ])
        
        if self.dry_run:
            print("\nGenerating VM configuration preview...")
            ansible_cmd.extend(["--extra-vars", "dry_run_mode=true", "--check"])
        else:
            print("Running Ansible playbook...")
        
        # Execute ansible command and capture output
        result = subprocess.run(ansible_cmd, capture_output=True, text=True)
        
        # Print Ansible output
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if self.dry_run:
            # Extract VM ID from Ansible output for display
            generated_vm_id = self.extract_vm_id_from_output(result.stdout)
            print("\nThis is a dry run - no VM will be created.")
            print("Remove --dry-run to execute the actual deployment.")
            self.generate_config_summary(generated_vm_id)
        elif result.returncode == 0:
            self.print_completion_message()
        else:
            print("Error: Ansible playbook failed")
            sys.exit(1)

    def generate_service_inventory(self):
        """Generate inventory.yml for service deployment from template."""
        # Files are in the service directory relative to the current working directory
        inventory_template_path = Path("inventory.yml.j2")
        inventory_output_path = Path("inventory.yml")
        
        if not inventory_template_path.exists():
            print(f"Error: Inventory template not found: {inventory_template_path.absolute()}")
            sys.exit(1)
        
        # Read template
        with open(inventory_template_path, 'r') as f:
            template_content = f.read()
        
        # Render template with target hostname
        template = Template(template_content)
        rendered_content = template.render(target_hostname=self.target_hostname)
        
        # Write rendered inventory
        with open(inventory_output_path, 'w') as f:
            f.write(rendered_content)
        
        print(f"Generated inventory file: {inventory_output_path}")

    def run_service_deployment(self):
        """Execute service deployment workflow."""
        print(f"Deploying {self.service_name} service to {self.target_hostname}...")
        
        # Change to service directory
        os.chdir(self.project_dir)
        
        # Generate inventory file from template
        self.generate_service_inventory()
        
        # Determine playbook file based on service
        playbook_map = {
            "minikube-svc": "install-minikube.yml"
        }
        
        playbook_file = playbook_map.get(self.service_name)
        if not playbook_file:
            print(f"Error: Unknown service '{self.service_name}'")
            print(f"Available services: {', '.join(playbook_map.keys())}")
            sys.exit(1)
        
        playbook_path = Path(playbook_file)
        if not playbook_path.exists():
            print(f"Error: Playbook not found: {playbook_path.absolute()}")
            sys.exit(1)
        
        # Prepare ansible command
        ansible_cmd = [
            "ansible-playbook", str(playbook_file),
            "-i", "inventory.yml",
            "-v"
        ]
        
        if self.dry_run:
            print(f"\n[DRY RUN] Would deploy {self.service_name} to {self.target_hostname}")
            print(f"Playbook: {playbook_file}")
            ansible_cmd.extend(["--check"])
            print(f"Command: {' '.join(ansible_cmd)}")
        else:
            print(f"Running service deployment playbook: {playbook_file}")
        
        # Execute ansible command
        result = subprocess.run(ansible_cmd)
        
        if result.returncode == 0:
            if not self.dry_run:
                self.print_service_completion_message()
        else:
            print("Error: Service deployment failed")
            sys.exit(1)

    def print_completion_message(self):
        """Print completion message with next steps."""
        print("=" * 40)
        print("VM creation process completed!")
        print("=" * 40)
        print("\nNext steps:")
        print("1. The VM is now installing Debian automatically")
        print("2. Installation will take approximately 10-15 minutes")
        print("3. You can monitor progress in the ProxmoxVE web interface")
        print("4. Once complete, find the VM IP address:")
        print(f"   ./find-vm-ip.sh <vm-name> {self.target_node}")
        print("5. Then SSH to the VM using your SSH key:")
        print("   ssh root@<vm-ip>")
        print("   ssh debian@<vm-ip>")
        print("\nQuick commands:")
        print(f"  Check VM status: ssh root@{self.target_node} 'qm list'")
        print(f"  Find VM IP:      ./find-vm-ip.sh $(ssh root@{self.target_node} 'qm list | tail -1 | awk \"{{print \\$2}}\"') {self.target_node}")
        print("\nNote: SSH password authentication is disabled for security")

    def print_service_completion_message(self):
        """Print service deployment completion message."""
        print("=" * 50)
        print(f"{self.service_name.upper()} deployment completed!")
        print("=" * 50)
        
        if self.service_name == "minikube-svc":
            print("\nMinikube has been installed successfully!")
            print("\nNext steps:")
            print(f"1. SSH to the VM: ssh debian@{self.target_hostname}")
            print("2. Start minikube: minikube start --driver=docker")
            print("3. Check status: minikube status")
            print("4. Use kubectl: kubectl get nodes")
            print("\nNote: You may need to log out and back in for docker group membership to take effect.")
            print("\nUseful commands:")
            print("  minikube dashboard    # Open Kubernetes dashboard")
            print("  kubectl cluster-info  # Show cluster information")
            print("  minikube stop         # Stop the cluster")
        else:
            print(f"\nService '{self.service_name}' has been deployed to {self.target_hostname}")
        
        print(f"\nSSH access: ssh debian@{self.target_hostname}")

    def run(self):
        """Main execution flow."""
        self.parse_arguments()
        self.validate_environment()
        
        if self.operation_mode == "vm-creation":
            self.process_hostname()
            self.print_configuration()
            self.run_vm_creation()
        else:
            self.print_configuration()
            self.run_service_deployment()


def main():
    """Entry point."""
    try:
        vm_manager = VMManager()
        vm_manager.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
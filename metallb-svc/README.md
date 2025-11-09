# MetalLB Service Deployment

This directory contains Ansible scripts to add MetalLB LoadBalancer support to an existing minikube cluster deployed with the `minikube-svc` service.

## Prerequisites

- An existing minikube cluster installed via `./install.py minikube-svc <hostname>`
- The target VM must be accessible via SSH with key authentication
- The minikube cluster must be running with `--driver=none`

## Quick Start

### Basic Installation

Deploy MetalLB with default IP range (automatically calculated based on host network):

```bash
./install.py metallb-svc <hostname>
```

### Custom IP Range

Specify a custom IP range for LoadBalancer services:

```bash
./install.py --metallb-ip-range=192.168.1.200-192.168.1.210 metallb-svc <hostname>
```

### With Test Service

Deploy MetalLB and create a test nginx LoadBalancer service:

```bash
./install.py --test-service metallb-svc <hostname>
```

### Combined Options

```bash
./install.py --metallb-ip-range=10.0.42.200-10.0.42.220 --test-service metallb-svc jinx.ank.com
```

## What It Does

The MetalLB service deployment:

1. **Verifies Prerequisites**: Checks that minikube is running and kubectl connectivity works
2. **Enables MetalLB**: Activates the MetalLB addon in minikube
3. **Configures IP Pool**: Sets up IP address pool for LoadBalancer services
4. **Network Setup**: Enables IP forwarding and configures Layer 2 advertisement
5. **Verification**: Tests MetalLB installation and displays configuration
6. **Optional Testing**: Deploys a test nginx service to verify LoadBalancer functionality

## IP Range Planning

### Default Behavior
If no `--metallb-ip-range` is specified, the system automatically calculates a range:
- Uses the host's network subnet
- Assigns IPs .200-.220 in that subnet
- Example: If host is 192.168.1.50, range becomes 192.168.1.200-192.168.1.220

### Custom Range Requirements
When specifying a custom IP range:
- Must be on the same subnet as the target host
- Should not conflict with DHCP assignments
- Must be accessible from your local network
- Format: `start_ip-end_ip` (e.g., `192.168.1.200-192.168.1.210`)

### Network Examples
```bash
# For host 10.0.42.100, use range in same subnet:
./install.py --metallb-ip-range=10.0.42.200-10.0.42.220 metallb-svc jinx.ank.com

# For host 192.168.1.50, use range in same subnet:  
./install.py --metallb-ip-range=192.168.1.200-192.168.1.210 metallb-svc myhost.local
```

## Usage After Installation

### Create a LoadBalancer Service

1. **Deploy an application**:
   ```bash
   kubectl create deployment nginx --image=nginx
   ```

2. **Expose as LoadBalancer**:
   ```bash
   kubectl expose deployment nginx --type=LoadBalancer --port=80
   ```

3. **Check assigned IP**:
   ```bash
   kubectl get svc nginx
   ```

4. **Access the service**:
   ```bash
   curl http://<EXTERNAL-IP>
   ```

### Management Commands

```bash
# List LoadBalancer services
kubectl get svc --field-selector spec.type=LoadBalancer

# Check MetalLB status
kubectl get pods -n metallb-system

# View IP address pools  
kubectl get ipaddresspool -n metallb-system

# Check MetalLB logs
kubectl logs -n metallb-system -l app=metallb

# View Layer 2 advertisements
kubectl get l2advertisement -n metallb-system
```

## Configuration Details

### MetalLB Components
- **Namespace**: `metallb-system`
- **IP Pool Name**: `default-pool`
- **Protocol**: Layer 2 (ARP-based)
- **Configuration**: CRD-based (IPAddressPool + L2Advertisement)

### Network Requirements
- **IP Forwarding**: Enabled on the host
- **Subnet**: LoadBalancer IPs must be on same subnet as host
- **Access**: IPs are directly accessible without port forwarding
- **Firewall**: May require firewall rules for external access

## Troubleshooting

### Check MetalLB Status
```bash
# SSH to the target host
ssh debian@<hostname>

# Check MetalLB pods
sudo kubectl get pods -n metallb-system -o wide

# Check configuration
sudo kubectl get ipaddresspool,l2advertisement -n metallb-system
```

### Common Issues

1. **LoadBalancer stays in Pending state**:
   - Check MetalLB pods are running: `kubectl get pods -n metallb-system`
   - Verify IP pool configuration: `kubectl describe ipaddresspool -n metallb-system`
   - Check MetalLB logs: `kubectl logs -n metallb-system -l app=metallb`

2. **IP not accessible**:
   - Ensure IP range is on same subnet as host
   - Check firewall rules on host and network
   - Verify no IP conflicts with DHCP

3. **Installation fails**:
   - Ensure minikube is running: `sudo minikube status`
   - Check kubectl connectivity: `sudo kubectl get nodes`
   - Verify sufficient permissions

### Test Service

The optional test service creates:
- Deployment: `metallb-test-nginx` 
- Service: `metallb-test-nginx` (LoadBalancer type)
- Image: `nginx:alpine` (lightweight)

Clean up test service:
```bash
kubectl delete deployment,svc metallb-test-nginx
```

## Examples

### Example 1: Basic Setup
```bash
# Deploy MetalLB with automatic IP range
./install.py metallb-svc myhost.example.com

# Create and expose an app
kubectl create deployment whoami --image=containous/whoami
kubectl expose deployment whoami --type=LoadBalancer --port=80

# Get external IP
kubectl get svc whoami
```

### Example 2: Web Server with Custom Range
```bash  
# Deploy with specific IP range
./install.py --metallb-ip-range=192.168.1.100-192.168.1.105 metallb-svc webserver.local

# Deploy nginx with custom config
kubectl create configmap nginx-config --from-literal=default.conf='
server {
    listen 80;
    location / {
        return 200 "Hello from LoadBalancer!";
        add_header Content-Type text/plain;
    }
}'

kubectl create deployment nginx --image=nginx
kubectl set volume deployment nginx --add --name=config --mount-path=/etc/nginx/conf.d --configmap-name=nginx-config
kubectl expose deployment nginx --type=LoadBalancer --port=80
```

### Example 3: Development Environment
```bash
# Deploy with test service for validation
./install.py --test-service --metallb-ip-range=10.0.42.150-10.0.42.160 metallb-svc dev.ank.com

# After validation, clean up test service and deploy your apps
kubectl delete deployment,svc metallb-test-nginx
```

## Integration with minikube-svc

This service is designed to work with clusters created by `minikube-svc`:
- Uses the same SSH key and user (debian)  
- Works with existing kubectl remote access setup
- Compatible with minikube systemd service
- Preserves existing cluster configuration

## Files

- `install-metallb.yml` - Main Ansible playbook
- `ansible.cfg` - Ansible configuration
- `inventory.yml.j2` - Inventory template (generated automatically)
- `README.md` - This documentation

## Notes

- MetalLB uses Layer 2 mode for maximum compatibility
- IPs are advertised via ARP on the local network segment
- No BGP configuration required
- Works with existing network infrastructure
- LoadBalancer IPs are directly routable (no NAT/port forwarding needed)
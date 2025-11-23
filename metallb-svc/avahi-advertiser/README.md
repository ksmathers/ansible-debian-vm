# Kubernetes Avahi Advertiser

Automatically advertises Kubernetes services via Avahi/mDNS as `.local` domain names.

## Overview

This systemd service runs on the Kubernetes host machine and watches Kubernetes services to automatically create Avahi advertisements:

- **LoadBalancer services**: Creates A records in `/etc/avahi/hosts` (hostname → IP mapping)
- **NodePort services**: Creates service records in `/etc/avahi/services` (mDNS-SD for service discovery)

Services become accessible via mDNS names like `jellyfin.local`, `wikijs.local`, etc.

## Features

- Runs as a systemd service on the Kubernetes host
- Automatic A records for LoadBalancer services with MetalLB IPs
- Automatic service records for NodePort services
- Configurable via Kubernetes annotations
- Support for custom service types and TXT records
- Automatic cleanup when services are deleted
- Systemd integration with automatic restart on failure
- Logging via journald

## Requirements

- Kubernetes cluster (minikube or similar)
- Avahi daemon running on the host
- MetalLB or similar LoadBalancer implementation (for LoadBalancer services)
- Python 3.7+
- Root access for installation

## Quick Installation

The easiest way to install is using the provided installation script:

```bash
# Run the installer (requires root)
sudo ./install.sh
```

This will automatically:
- Install system dependencies (Python, Avahi)
- Install Python packages
- Copy files to the correct locations
- Enable and start the systemd service

## Manual Installation

If you prefer to install manually:

### 1. Install System Dependencies

```bash
# Install Python and Avahi
sudo apt-get update
sudo apt-get install -y python3 python3-pip avahi-daemon avahi-utils
```

### 2. Install Python Dependencies

```bash
# Install required Python packages
sudo pip3 install -r requirements.txt
```

### 3. Copy Service Files

```bash
# Copy the Python script to /usr/local/bin
sudo cp avahi_k8s_advertiser.py /usr/local/bin/
sudo chmod +x /usr/local/bin/avahi_k8s_advertiser.py

# Copy the systemd service file
sudo cp avahi-k8s-advertiser.service /etc/systemd/system/
```

### 4. Enable and Start the Service

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable avahi-k8s-advertiser

# Start the service
sudo systemctl start avahi-k8s-advertiser

# Check service status
sudo systemctl status avahi-k8s-advertiser
```

### 5. Verify Installation

```bash
# View service logs
sudo journalctl -u avahi-k8s-advertiser -f

# Check Avahi hosts file
cat /etc/avahi/hosts

# List advertised services
avahi-browse -a
```

## Service Management

```bash
# Start the service
sudo systemctl start avahi-k8s-advertiser

# Stop the service
sudo systemctl stop avahi-k8s-advertiser

# Restart the service
sudo systemctl restart avahi-k8s-advertiser

# Check service status
sudo systemctl status avahi-k8s-advertiser

# View logs
sudo journalctl -u avahi-k8s-advertiser -f

# View logs since last boot
sudo journalctl -u avahi-k8s-advertiser -b
```

## Configuration

### Kubernetes Access

The service uses the host's kubeconfig to access the Kubernetes API. By default, it looks for:
- `/root/.kube/config` (when running as root via systemd)
- `~/.kube/config` (when running manually)

### Environment Variables

The following environment variables can be configured in the systemd service file:

- `AVAHI_HOSTS_FILE`: Path to Avahi hosts file (default: `/etc/avahi/hosts`)
- `AVAHI_SERVICES_DIR`: Directory for Avahi service files (default: `/etc/avahi/services`)
- `LOG_LEVEL`: Logging level (default: `INFO`, options: `DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Service Annotations

Services are automatically advertised if they are of type `LoadBalancer` and have an assigned IP.

Control advertisement behavior with annotations:

```yaml
metadata:
  annotations:
    # Disable advertisement for this service
    avahi.local/enabled: "false"
    
    # Custom advertised name (default: service name)
    avahi.local/name: "myservice"
    
    # Custom service type (default: _http._tcp)
    avahi.local/service-type: "_https._tcp"
    
    # Add TXT records
    avahi.local/txt-path: "/api"
    avahi.local/txt-version: "1.0"
```

## Examples

### LoadBalancer Service (creates A record)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: jellyfin
  namespace: jellyfin
  annotations:
    avahi.local/name: "jellyfin"
spec:
  type: LoadBalancer
  selector:
    app: jellyfin
  ports:
  - port: 8096
    targetPort: 8096
```

This creates an A record: `jellyfin.local → 192.168.x.x` (MetalLB IP)
Accessible at: `http://jellyfin.local:8096`

### NodePort Service (creates service record)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-app
  namespace: default
  annotations:
    avahi.local/name: "webapp"
    avahi.local/service-type: "_http._tcp"
    avahi.local/txt-path: "/api"
spec:
  type: NodePort
  selector:
    app: web-app
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30080
```

This creates a service record for mDNS-SD, advertised on port 30080

## Troubleshooting

### Service won't start

```bash
# Check service status and logs
sudo systemctl status avahi-k8s-advertiser
sudo journalctl -u avahi-k8s-advertiser -n 50

# Common issues:
# - Missing Python dependencies: sudo pip3 install -r requirements.txt
# - Missing kubeconfig: Ensure /root/.kube/config exists
# - Permission issues: Ensure script is executable
```

### Services not being advertised

```bash
# Check if service is running
sudo systemctl status avahi-k8s-advertiser

# Check logs for errors
sudo journalctl -u avahi-k8s-advertiser -f

# Verify Avahi is running
sudo systemctl status avahi-daemon

# Check if Avahi hosts file is being updated
cat /etc/avahi/hosts | grep "Managed by k8s-avahi-advertiser"
```

### Manual testing

```bash
# Run the script manually (for debugging)
sudo /usr/local/bin/avahi_k8s_advertiser.py

# Test with increased logging
sudo LOG_LEVEL=DEBUG /usr/local/bin/avahi_k8s_advertiser.py
```

### Restart Avahi daemon

If services aren't resolving, try restarting Avahi:

```bash
sudo systemctl restart avahi-daemon
```

## Uninstallation

### Quick Uninstall

Use the provided uninstall script:

```bash
# Run the uninstaller (requires root)
sudo ./uninstall.sh
```

The script will:
- Stop and disable the service
- Remove installed files
- Optionally clean up Avahi configuration

### Manual Uninstall

If you prefer to uninstall manually:

```bash
# Stop and disable the service
sudo systemctl stop avahi-k8s-advertiser
sudo systemctl disable avahi-k8s-advertiser

# Remove service files
sudo rm /etc/systemd/system/avahi-k8s-advertiser.service
sudo rm /usr/local/bin/avahi_k8s_advertiser.py

# Reload systemd
sudo systemctl daemon-reload

# Clean up Avahi hosts (optional)
sudo sed -i '/# Managed by k8s-avahi-advertiser/d' /etc/avahi/hosts

# Remove service files created by the advertiser
sudo rm /etc/avahi/services/k8s-*.service
```

## License

GPLv2

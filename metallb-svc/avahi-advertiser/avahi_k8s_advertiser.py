#!/usr/bin/env python3
"""
Kubernetes to Avahi Advertiser

Watches Kubernetes services and automatically creates Avahi advertisements:
- LoadBalancer services: A records in /etc/avahi/hosts (hostname → IP)
- NodePort services: Service records in /etc/avahi/services (mDNS-SD)
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

# Configuration
AVAHI_HOSTS_FILE = Path(os.getenv("AVAHI_HOSTS_FILE", "/etc/avahi/hosts"))
AVAHI_SERVICES_DIR = Path(os.getenv("AVAHI_SERVICES_DIR", "/etc/avahi/services"))
ANNOTATION_PREFIX = "avahi.local/"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MANAGED_HOSTS_MARKER = "# Managed by k8s-avahi-advertiser"

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AvahiServiceFile:
    """Represents an Avahi service definition file (for mDNS-SD)."""
    
    def __init__(self, name: str, ip: str, port: int, 
                 service_type: str = "_http._tcp", txt_records: Optional[Dict[str, str]] = None):
        self.name = name
        self.ip = ip
        self.port = port
        self.service_type = service_type
        self.txt_records = txt_records or {}
    
    def to_xml(self) -> str:
        """Generate Avahi service XML for mDNS-SD (NodePort services)."""
        txt_records_xml = ""
        if self.txt_records:
            txt_records_xml = "\n".join(
                f'    <txt-record>{key}={value}</txt-record>'
                for key, value in self.txt_records.items()
            )
        
        # For NodePort services, we don't specify host-name (uses local hostname)
        xml = f"""<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">{self.name}</name>
  <service>
    <type>{self.service_type}</type>
    <port>{self.port}</port>
"""
        if txt_records_xml:
            xml += txt_records_xml + "\n"
        
        xml += """  </service>
</service-group>
"""
        return xml
    
    def filename(self) -> str:
        """Generate safe filename for this service."""
        # Replace invalid characters for filenames
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in self.name.lower())
        return f"k8s-{safe_name}.service"


class KubernetesAvahiAdvertiser:
    """Watches Kubernetes services and manages Avahi advertisements."""
    
    def __init__(self):
        self.services_dir = AVAHI_SERVICES_DIR
        self.hosts_file = AVAHI_HOSTS_FILE
        self.managed_files = set()
        self.managed_hosts: Set[str] = set()
        self.needs_reload = False
        # Track hostname/service name to namespace/service mappings for conflict detection
        self.hostname_map: Dict[str, str] = {}  # hostname -> "namespace/service"
        self.service_name_map: Dict[str, str] = {}  # service_filename -> "namespace/service"
        
        # Load Kubernetes configuration
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            try:
                config.load_kube_config()
                logger.info("Loaded kubeconfig configuration")
            except config.ConfigException:
                logger.error("Could not load Kubernetes configuration")
                sys.exit(1)
        
        self.v1 = client.CoreV1Api()
        
        # Ensure Avahi hosts file exists and is writable
        if not self.hosts_file.exists():
            logger.warning(f"Avahi hosts file does not exist, will create: {self.hosts_file}")
            try:
                self.hosts_file.touch()
            except Exception as e:
                logger.error(f"Cannot create Avahi hosts file: {e}")
                sys.exit(1)
        
        if not os.access(self.hosts_file, os.W_OK):
            logger.error(f"Avahi hosts file is not writable: {self.hosts_file}")
            sys.exit(1)
        
        # Ensure Avahi services directory exists and is writable
        if not self.services_dir.exists():
            logger.error(f"Avahi services directory does not exist: {self.services_dir}")
            sys.exit(1)
        
        if not os.access(self.services_dir, os.W_OK):
            logger.error(f"Avahi services directory is not writable: {self.services_dir}")
            sys.exit(1)
        
        logger.info(f"Avahi hosts file: {self.hosts_file}")
        logger.info(f"Avahi services directory: {self.services_dir}")
        
        # Load existing managed hosts
        self._load_managed_hosts()
    
    def reload_avahi_daemon(self):
        """Reload avahi-daemon to pick up configuration changes."""
        if not self.needs_reload:
            return
        
        try:
            result = subprocess.run(
                ["systemctl", "reload", "avahi-daemon"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("Successfully reloaded avahi-daemon")
                self.needs_reload = False
            else:
                logger.error(f"Failed to reload avahi-daemon: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            logger.error("Timeout while reloading avahi-daemon")
        except Exception as e:
            logger.error(f"Error reloading avahi-daemon: {e}")
    
    def get_service_annotations(self, service) -> Dict[str, str]:
        """Extract avahi-related annotations from service."""
        annotations = {}
        if service.metadata.annotations:
            for key, value in service.metadata.annotations.items():
                if key.startswith(ANNOTATION_PREFIX):
                    short_key = key[len(ANNOTATION_PREFIX):]
                    annotations[short_key] = value
        return annotations
    
    def _load_managed_hosts(self):
        """Load existing managed host entries from hosts file."""
        if not self.hosts_file.exists():
            return
        
        try:
            with open(self.hosts_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if MANAGED_HOSTS_MARKER in line:
                        # Extract hostname from comment
                        parts = line.split()
                        if len(parts) >= 3:  # IP hostname # marker
                            self.managed_hosts.add(parts[1])
        except Exception as e:
            logger.warning(f"Failed to load existing managed hosts: {e}")
    
    def should_advertise(self, service) -> bool:
        """Determine if service should be advertised via Avahi."""
        # Advertise LoadBalancer services (as A records) or NodePort services (as service records)
        if service.spec.type not in ["LoadBalancer", "NodePort"]:
            return False
        
        # LoadBalancer must have an assigned external IP
        if service.spec.type == "LoadBalancer":
            if not service.status.load_balancer.ingress:
                return False
        
        # Check if explicitly disabled
        if service.metadata.annotations:
            if service.metadata.annotations.get(f"{ANNOTATION_PREFIX}enabled", "true").lower() == "false":
                return False
        
        return True
    
    def create_host_record(self, k8s_service):
        """Create Avahi A record for LoadBalancer service."""
        name = k8s_service.metadata.name
        namespace = k8s_service.metadata.namespace
        
        # Get LoadBalancer IP
        if not k8s_service.status.load_balancer.ingress:
            logger.warning(f"LoadBalancer service {namespace}/{name} has no IP assigned yet")
            return
        
        ip = k8s_service.status.load_balancer.ingress[0].ip
        
        # Get hostname from annotation or use service name
        annotations = self.get_service_annotations(k8s_service)
        hostname = annotations.get("name", name)
        hostname_fqdn = f"{hostname}.local"
        
        # Check for conflicts with existing services
        current_service_key = f"{namespace}/{name}"
        if hostname_fqdn in self.hostname_map:
            existing_service = self.hostname_map[hostname_fqdn]
            if existing_service != current_service_key:
                logger.error(
                    f"⚠️  HOSTNAME CONFLICT: LoadBalancer service {current_service_key} "
                    f"wants to use hostname '{hostname_fqdn}' which is already claimed by {existing_service}. "
                    f"The previous service's A record will be overwritten. "
                    f"Consider using avahi.local/name annotation to specify unique hostnames."
                )
        
        # Read existing hosts file
        existing_lines = []
        if self.hosts_file.exists():
            try:
                with open(self.hosts_file, 'r') as f:
                    existing_lines = f.readlines()
            except Exception as e:
                logger.error(f"Failed to read hosts file: {e}")
                return
        
        # Remove any existing entry for this hostname
        new_lines = [line for line in existing_lines 
                     if not (MANAGED_HOSTS_MARKER in line and hostname in line)]
        
        # Add new entry
        new_entry = f"{ip} {hostname}.local {MANAGED_HOSTS_MARKER} ({namespace}/{name})\n"
        new_lines.append(new_entry)
        
        # Write back to hosts file
        try:
            with open(self.hosts_file, 'w') as f:
                f.writelines(new_lines)
            
            self.managed_hosts.add(hostname_fqdn)
            self.hostname_map[hostname_fqdn] = current_service_key
            self.needs_reload = True
            logger.info(f"Created Avahi A record: {hostname_fqdn} → {ip} ({namespace}/{name})")
        
        except Exception as e:
            logger.error(f"Failed to write hosts file: {e}")
    
    def create_service_record(self, k8s_service):
        """Create Avahi service record for NodePort service."""
        name = k8s_service.metadata.name
        namespace = k8s_service.metadata.namespace
        
        # Get primary port (first port in the list)
        if not k8s_service.spec.ports:
            logger.warning(f"Service {namespace}/{name} has no ports defined")
            return
        
        port = k8s_service.spec.ports[0].node_port
        if not port:
            logger.warning(f"NodePort service {namespace}/{name} has no nodePort assigned")
            return
        
        # Get service type from annotation or default to HTTP
        annotations = self.get_service_annotations(k8s_service)
        service_type = annotations.get("service-type", "_http._tcp")
        advertise_name = annotations.get("name", name)
        
        # Generate filename early for conflict checking
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in advertise_name.lower())
        filename = f"k8s-{safe_name}.service"
        
        # Check for conflicts with existing services
        current_service_key = f"{namespace}/{name}"
        if filename in self.service_name_map:
            existing_service = self.service_name_map[filename]
            if existing_service != current_service_key:
                logger.error(
                    f"⚠️  SERVICE NAME CONFLICT: NodePort service {current_service_key} "
                    f"wants to use service name '{advertise_name}' (file: {filename}) which is already "
                    f"claimed by {existing_service}. The previous service definition will be overwritten. "
                    f"Consider using avahi.local/name annotation to specify unique service names."
                )
        
        # Extract TXT records from annotations
        txt_records = {}
        for key, value in annotations.items():
            if key.startswith("txt-"):
                txt_key = key[4:]  # Remove "txt-" prefix
                txt_records[txt_key] = value
        
        # Create service file
        avahi_service = AvahiServiceFile(
            name=advertise_name,
            ip="",  # NodePort services don't need IP in service record
            port=port,
            service_type=service_type,
            txt_records=txt_records
        )
        
        filepath = self.services_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                f.write(avahi_service.to_xml())
            
            self.managed_files.add(filename)
            self.service_name_map[filename] = current_service_key
            self.needs_reload = True
            logger.info(f"Created Avahi service record: {filename} for {namespace}/{name} at {advertise_name}.local:{port}")
        
        except Exception as e:
            logger.error(f"Failed to create Avahi service file {filename}: {e}")
    
    def create_avahi_advertisement(self, k8s_service):
        """Create appropriate Avahi advertisement based on service type."""
        if k8s_service.spec.type == "LoadBalancer":
            self.create_host_record(k8s_service)
        elif k8s_service.spec.type == "NodePort":
            self.create_service_record(k8s_service)
    
    def remove_host_record(self, k8s_service):
        """Remove Avahi A record for service."""
        name = k8s_service.metadata.name
        namespace = k8s_service.metadata.namespace
        
        annotations = self.get_service_annotations(k8s_service)
        hostname = annotations.get("name", name)
        hostname_fqdn = f"{hostname}.local"
        
        # Read existing hosts file
        if not self.hosts_file.exists():
            return
        
        try:
            with open(self.hosts_file, 'r') as f:
                existing_lines = f.readlines()
            
            # Remove entries for this hostname
            new_lines = [line for line in existing_lines 
                         if not (MANAGED_HOSTS_MARKER in line and hostname in line)]
            
            # Write back if anything changed
            if len(new_lines) < len(existing_lines):
                with open(self.hosts_file, 'w') as f:
                    f.writelines(new_lines)
                
                self.managed_hosts.discard(hostname_fqdn)
                # Remove from hostname map
                current_service_key = f"{namespace}/{name}"
                if hostname_fqdn in self.hostname_map and self.hostname_map[hostname_fqdn] == current_service_key:
                    del self.hostname_map[hostname_fqdn]
                self.needs_reload = True
                logger.info(f"Removed Avahi A record: {hostname_fqdn} ({namespace}/{name})")
        
        except Exception as e:
            logger.error(f"Failed to remove host record: {e}")
    
    def remove_service_record(self, k8s_service):
        """Remove Avahi service file for Kubernetes service."""
        name = k8s_service.metadata.name
        namespace = k8s_service.metadata.namespace
        
        annotations = self.get_service_annotations(k8s_service)
        advertise_name = annotations.get("name", name)
        
        # Generate filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in advertise_name.lower())
        filename = f"k8s-{safe_name}.service"
        filepath = self.services_dir / filename
        
        if filepath.exists():
            try:
                filepath.unlink()
                self.managed_files.discard(filename)
                # Remove from service name map
                current_service_key = f"{namespace}/{name}"
                if filename in self.service_name_map and self.service_name_map[filename] == current_service_key:
                    del self.service_name_map[filename]
                self.needs_reload = True
                logger.info(f"Removed Avahi service record: {filename} for {namespace}/{name}")
            except Exception as e:
                logger.error(f"Failed to remove Avahi service file {filename}: {e}")
    
    def remove_avahi_advertisement(self, k8s_service):
        """Remove appropriate Avahi advertisement based on service type."""
        # Try to remove both types since we might not know which was created
        if k8s_service.spec.type == "LoadBalancer":
            self.remove_host_record(k8s_service)
        elif k8s_service.spec.type == "NodePort":
            self.remove_service_record(k8s_service)
    
    def sync_existing_services(self):
        """Sync all existing LoadBalancer and NodePort services."""
        logger.info("Syncing existing services...")
        
        try:
            services = self.v1.list_service_for_all_namespaces()
            
            for service in services.items:
                if self.should_advertise(service):
                    self.create_avahi_advertisement(service)
            
            # Reload avahi-daemon if any changes were made
            self.reload_avahi_daemon()
        
        except ApiException as e:
            logger.error(f"Failed to list services: {e}")
    
    def watch_services(self):
        """Watch for service changes and update Avahi accordingly."""
        logger.info("Starting to watch Kubernetes services...")
        
        w = watch.Watch()
        
        while True:
            try:
                for event in w.stream(self.v1.list_service_for_all_namespaces, timeout_seconds=0):
                    event_type = event['type']
                    service = event['object']
                    name = service.metadata.name
                    namespace = service.metadata.namespace
                    
                    logger.debug(f"Event: {event_type} for {namespace}/{name}")
                    
                    if event_type in ['ADDED', 'MODIFIED']:
                        if self.should_advertise(service):
                            self.create_avahi_advertisement(service)
                        else:
                            # Remove if it was previously advertised
                            self.remove_avahi_advertisement(service)
                    
                    elif event_type == 'DELETED':
                        self.remove_avahi_advertisement(service)
                    
                    # Reload avahi-daemon if any changes were made
                    self.reload_avahi_daemon()
            
            except ApiException as e:
                if e.status == 410:
                    # Resource version is too old, restart watch
                    logger.warning("Watch expired, restarting...")
                    continue
                else:
                    logger.error(f"API exception while watching services: {e}")
                    time.sleep(5)
            
            except Exception as e:
                logger.error(f"Unexpected error while watching services: {e}")
                time.sleep(5)
    
    def run(self):
        """Main run loop."""
        logger.info("Kubernetes Avahi Advertiser starting...")
        
        # Initial sync
        self.sync_existing_services()
        
        # Start watching
        self.watch_services()


def main():
    """Entry point."""
    advertiser = KubernetesAvahiAdvertiser()
    advertiser.run()


if __name__ == "__main__":
    main()

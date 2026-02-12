import docker
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ContainerInspector:
    """Inspect running ContainerLab containers and discover their ports"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            self.client = None
    
    def get_containerlab_containers(self, topology_name: Optional[str] = None) -> List[Dict]:
        """Get all running ContainerLab containers"""
        if not self.client:
            return []
        
        containers = []
        try:
            # Try multiple detection methods
            
            # Method 1: Try with containerlab label
            filters = {'label': 'containerlab'}
            labeled_containers = self.client.containers.list(filters=filters)
            
            # Method 2: If no labeled containers, try by name pattern (clab-)
            if not labeled_containers:
                logger.info("No containers with 'containerlab' label, trying name pattern...")
                all_containers = self.client.containers.list()
                labeled_containers = [c for c in all_containers if c.name.startswith('clab-')]
                logger.info(f"Found {len(labeled_containers)} containers with 'clab-' prefix")
            
            # Method 3: If topology_name provided, filter by that
            if topology_name:
                labeled_containers = [c for c in labeled_containers 
                                    if topology_name in c.name]
            
            for container in labeled_containers:
                container_info = self._extract_container_info(container)
                containers.append(container_info)
                
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            import traceback
            traceback.print_exc()
        
        return containers
    
    def _extract_container_info(self, container) -> Dict:
        """Extract relevant information from a container"""
        # Get container details
        details = container.attrs
        
        # Extract port mappings
        port_mappings = self._extract_port_mappings(details)
        
        # Get container name and parse node name
        full_name = container.name
        node_name = full_name  # Default to full name
        
        # Try to parse ContainerLab naming patterns
        # Common patterns: clab-{topology}-{node} or just {node}
        if full_name.startswith('clab-'):
            # Format: clab-{topology}-{node}
            parts = full_name.split('-', 2)
            if len(parts) >= 3:
                node_name = parts[2]  # Get node part
            elif len(parts) == 2:
                node_name = parts[1]
        
        # Log for debugging
        logger.info(f"Container: {full_name} -> Node: {node_name}")
        
        return {
            'container_id': container.id[:12],
            'container_name': full_name,
            'node_name': node_name,
            'status': container.status,
            'ports': port_mappings,
            'labels': details.get('Config', {}).get('Labels', {}),
            'image': details.get('Config', {}).get('Image', '')
        }
    
    def _extract_port_mappings(self, details: Dict) -> Dict[str, int]:
        """Extract port mappings from container details"""
        ports = {}
        
        try:
            network_settings = details.get('NetworkSettings', {})
            port_bindings = network_settings.get('Ports', {})
            
            if not port_bindings:
                logger.warning(f"No port bindings found for container")
                return ports
            
            for container_port, host_bindings in port_bindings.items():
                if not host_bindings:
                    continue
                    
                # Extract port number from format "9090/tcp"
                container_port_num = container_port.split('/')[0]
                
                # Get the host port
                host_port = host_bindings[0].get('HostPort')
                
                if host_port:
                    host_port_int = int(host_port)
                    
                    # Map container ports to service names
                    if container_port_num == '9090':
                        ports['prometheus'] = host_port_int
                        ports['prometheus_container_port'] = 9090
                        logger.info(f"Found Prometheus: {container_port_num} -> {host_port_int}")
                    elif container_port_num == '3000':
                        ports['grafana'] = host_port_int
                        ports['grafana_container_port'] = 3000
                        logger.info(f"Found Grafana: {container_port_num} -> {host_port_int}")
                    else:
                        ports[f'port_{container_port_num}'] = host_port_int
                        
        except Exception as e:
            logger.error(f"Error extracting ports: {e}")
            import traceback
            traceback.print_exc()
        
        return ports
    
    def get_node_urls(self, container_info: Dict, monitoring_config: Dict) -> Dict[str, str]:
        """Generate URLs for accessing node monitoring"""
        import urllib.parse
        
        urls = {}
        node_name = container_info.get('node_name', '')
        
        # Check if Grafana is enabled (preferred)
        central_grafana = monitoring_config.get('central_grafana', {})
        if central_grafana.get('enabled', False):
            host = central_grafana.get('host', 'localhost')
            port = central_grafana.get('port', 3000)
            dashboard_uid = central_grafana.get('dashboard_uid', '')
            
            if dashboard_uid:
                # Create Grafana URL with node variable
                #urls['grafana'] = f"http://{host}:{port}/d/{dashboard_uid}/emulation?var-Node={node_name}&from=now-1h&to=now"
                urls['grafana'] = f"http://172.22.174.53:{port}/d/{dashboard_uid}/emulation?var-Node={node_name}&from=now-1h&to=now"
                urls['monitoring'] = urls['grafana']  # Primary link
        
        # Also keep Prometheus link as backup
        central_prom = monitoring_config.get('central_prometheus', {})
        if central_prom.get('enabled', False):
            host = central_prom.get('host', 'localhost')
            port = central_prom.get('port', 9091)
            
            query = f'emulation_node_cpu_percent{{container_node="{node_name}"}}'
            encoded_query = urllib.parse.quote(query)
            
            #urls['prometheus'] = f"http://{host}:{port}/graph?g0.expr={encoded_query}&g0.tab=0&g0.range_input=1h"
            urls['prometheus'] = f"http://172.22.174.53:{port}/graph?g0.expr={encoded_query}&g0.tab=0&g0.range_input=1h"
            
            
        
        return urls
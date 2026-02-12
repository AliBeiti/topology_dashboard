import yaml
from pathlib import Path
from typing import Dict, List, Optional

class TopologyParser:
    """Parse ContainerLab topology files"""
    
    def __init__(self, topology_file: str):
        self.topology_file = Path(topology_file)
        self.topology_data = None
        
    def parse(self) -> Dict:
        """Parse the topology file and extract node information"""
        if not self.topology_file.exists():
            raise FileNotFoundError(f"Topology file not found: {self.topology_file}")
        
        with open(self.topology_file, 'r') as f:
            self.topology_data = yaml.safe_load(f)
        
        return self._extract_nodes_and_links()
    
    def _extract_nodes_and_links(self) -> Dict:
        """Extract nodes and links from topology data"""
        topology = self.topology_data.get('topology', {})
        nodes_data = topology.get('nodes', {})
        links_data = topology.get('links', [])
        
        nodes = []
        for node_name, node_config in nodes_data.items():
            node_info = {
                'id': node_name,
                'label': node_name,
                'kind': node_config.get('kind', 'unknown'),
                'image': node_config.get('image', ''),
                'type': self._determine_node_type(node_config)
            }
            nodes.append(node_info)
        
        links = []
        for link in links_data:
            endpoints = link.get('endpoints', [])
            if len(endpoints) >= 2:
                # Parse endpoint format: "node:interface"
                source = endpoints[0].split(':')[0]
                target = endpoints[1].split(':')[0]
                links.append({
                    'source': source,
                    'target': target
                })
        
        return {
            'nodes': nodes,
            'links': links,
            'name': self.topology_data.get('name', 'Unknown Topology')
        }
    
    def _determine_node_type(self, node_config: Dict) -> str:
        """Determine node type based on configuration"""
        kind = node_config.get('kind', '')
        image = node_config.get('image', '').lower()
        
        # Routers
        if 'frr' in image or 'router' in image:
            return 'router'
        
        # K3s/Serf nodes (monitoring targets)
        if 'k3s' in image or 'serf' in image:
            return 'k3s-node'
        
        # Switches
        if 'switch' in image or kind == 'vr-sros':
            return 'switch'
        
        # Linux containers
        if kind == 'linux':
            return 'linux-container'
        
        return 'generic-node'
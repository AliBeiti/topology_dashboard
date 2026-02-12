from flask import Flask,request, render_template, jsonify, send_from_directory
import yaml
import logging
from pathlib import Path
from utils.topology_parser import TopologyParser
from utils.container_inspector import ContainerInspector
import json
import subprocess
import psutil
import os

BASE_DIR = Path(__file__).parent
VIRTUAL_POD_MANAGER_PATH = BASE_DIR / 'scripts' / 'virtual_pod_manager.py'
WORKLOAD_TEMPLATES_DIR = BASE_DIR / 'workload_templates'
VIRTUAL_PODS_REGISTRY = BASE_DIR / 'virtual_pods' / 'registry.json' 
LIQO_CONNECTIONS_FILE = BASE_DIR / 'virtual_pods' / 'liqo_connections.json'

# Create directories if they don't exist
WORKLOAD_TEMPLATES_DIR.mkdir(exist_ok=True)
(BASE_DIR / 'virtual_pods').mkdir(exist_ok=True)

def load_liqo_connections():
    """Load Liqo connections from file"""
    if LIQO_CONNECTIONS_FILE.exists():
        with open(LIQO_CONNECTIONS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_liqo_connections(connections):
    """Save Liqo connections to file"""
    with open(LIQO_CONNECTIONS_FILE, 'w') as f:
        json.dump(connections, f, indent=2)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='')

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize utilities
topology_parser = TopologyParser(config['containerlab']['topology_file'])
container_inspector = ContainerInspector()

@app.route('/')
def index():
    """Serve the main page"""
    return send_from_directory('static', 'index.html')

@app.route('/api/topology')
def get_topology():
    """Get topology structure with container information"""
    try:
        logger.info("Starting topology generation...")
        
       
        topology = topology_parser.parse()
        logger.info(f"Found {len(topology['nodes'])} nodes in topology")
        
        
        containers = container_inspector.get_containerlab_containers()
        logger.info(f"Found {len(containers)} running containers")
        
        
        monitoring_config = config.get('monitoring', {})
        
        
        container_map = {c['node_name']: c for c in containers}
        
        
        for node in topology['nodes']:
            node_name = node['id']
            
            if node_name in container_map:
                container = container_map[node_name]
                node['container'] = {
                    'status': container['status'],
                    'ports': container['ports'],
                    'urls': container_inspector.get_node_urls(
                        container,
                        monitoring_config
                    )
                }
            else:
                node['container'] = {
                    'status': 'not_found',
                    'ports': {},
                    'urls': {}
                }
        
        return jsonify(topology)
    
    except Exception as e:
        logger.error(f"Error generating topology: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500  

@app.route('/api/containers')
def get_containers():
    """Get all running ContainerLab containers"""
    try:
        containers = container_inspector.get_containerlab_containers()
        return jsonify({'containers': containers})
    except Exception as e:
        logger.error(f"Error getting containers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/api/port-mappings')
def get_port_mappings():
    """Get detailed port mapping information for all containers"""
    try:
        containers = container_inspector.get_containerlab_containers()
        
        mappings = []
        for container in containers:
            mapping = {
                'node_name': container['node_name'],
                'container_name': container['container_name'],
                'status': container['status'],
                'port_mappings': []
            }
            
            for service, host_port in container['ports'].items():
                if '_container_port' not in service:
                    container_port = container['ports'].get(f'{service}_container_port', 'unknown')
                    mapping['port_mappings'].append({
                        'service': service,
                        'container_port': container_port,
                        'host_port': host_port,
                        'mapping': f"{container_port} -> {host_port}"
                    })
            
            mappings.append(mapping)
        
        return jsonify({
            'vm_prometheus_port': config.get('monitoring', {}).get('vm_prometheus_port'),
            'container_mappings': mappings
        })
    
    except Exception as e:
        logger.error(f"Error getting port mappings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/node/<node_name>/cluster-info')
def get_cluster_info(node_name):
    """Get K3s cluster information from a specific node"""
    try:
        # Map node name to container name
        container_name = f"clab-emulation-{node_name}"
        
        # Get namespaces
        result = subprocess.run(
            ['docker', 'exec', container_name,'k3s', 'kubectl', 'get', 'namespaces', '-o', 'json'],
            capture_output=True, text=True, timeout=10
        )
        namespaces_data = json.loads(result.stdout) if result.returncode == 0 else {}
        
        # Get nodes
        result = subprocess.run(
            ['docker', 'exec', container_name,'k3s', 'kubectl', 'get', 'nodes', '-o', 'json'],
            capture_output=True, text=True, timeout=10
        )
        nodes_data = json.loads(result.stdout) if result.returncode == 0 else {}
        
        # Get pods from all namespaces
        result = subprocess.run(
            ['docker', 'exec', container_name,'k3s', 'kubectl', 'get', 'pods', '--all-namespaces', '-o', 'json'],
            capture_output=True, text=True, timeout=10
        )
        pods_data = json.loads(result.stdout) if result.returncode == 0 else {}
        
        # Parse and format the data
        namespaces = [ns['metadata']['name'] for ns in namespaces_data.get('items', [])]
        
        nodes = []
        for node in nodes_data.get('items', []):
            nodes.append({
                'name': node['metadata']['name'],
                'status': node['status']['conditions'][-1]['type'] if node.get('status', {}).get('conditions') else 'Unknown',
                'type': 'kwok' if 'kwok' in node['metadata'].get('labels', {}).get('type', '') else 'real'
            })
        
        pods_by_namespace = {}
        for pod in pods_data.get('items', []):
            ns = pod['metadata']['namespace']
            if ns not in pods_by_namespace:
                pods_by_namespace[ns] = []
            
            pods_by_namespace[ns].append({
                'name': pod['metadata']['name'],
                'status': pod['status'].get('phase', 'Unknown'),
                'node': pod['spec'].get('nodeName', 'N/A')
            })
        
        return jsonify({
            'node_name': node_name,
            'namespaces': namespaces,
            'nodes': nodes,
            'pods_by_namespace': pods_by_namespace,
            'total_pods': len(pods_data.get('items', []))
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout querying cluster'}), 504
    except Exception as e:
        logger.error(f"Error getting cluster info: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/node/<node_name>/timeseries')
def get_node_timeseries(node_name):
    """Get time-series metrics for a specific node (both emulation and real)"""
    try:
        import requests
        from datetime import datetime, timedelta
        
        metric_type = request.args.get('metric', 'cpu')
        window = request.args.get('window', '5m')  # Default 5 minutes
        
        # Map metric types to Prometheus metric names
        metric_map = {
            'cpu': 'cpu_percent',
            'psi': 'psi_percent',
            'power': 'power_watts',
            'memory': 'memory_percent'
        }
        
        base_metric = metric_map.get(metric_type, 'cpu_percent')
        
        # Get Prometheus URL from config
        prom_config = config.get('monitoring', {}).get('central_prometheus', {})
        prom_host = prom_config.get('host', 'localhost')
        prom_port = prom_config.get('port', 9091)
        
        # Calculate time range based on window parameter
        end_time = datetime.now()
        if window.endswith('m'):
            minutes = int(window[:-1])
            start_time = end_time - timedelta(minutes=minutes)
        elif window.endswith('h'):
            hours = int(window[:-1])
            start_time = end_time - timedelta(hours=hours)
        else:
            start_time = end_time - timedelta(minutes=5)
        
        # Fetch both emulation and real metrics
        datasets = {}
        
        for prefix in ['emulation_node', 'real_node']:
            metric_name = f'{prefix}_{base_metric}'
            query = f'{metric_name}{{container_node="{node_name}"}}'
            prom_url = f'http://{prom_host}:{prom_port}/api/v1/query_range'
            
            params = {
                'query': query,
                'start': start_time.timestamp(),
                'end': end_time.timestamp(),
                'step': '15s'
            }
            
            response = requests.get(prom_url, params=params, timeout=10)
            prom_data = response.json()
            
            if prom_data.get('status') == 'success':
                results = prom_data.get('data', {}).get('result', [])
                if results:
                    values = results[0].get('values', [])
                    timestamps = [v[0] for v in values]
                    data_points = [float(v[1]) for v in values]
                    
                    datasets[prefix] = {
                        'timestamps': timestamps,
                        'values': data_points
                    }
        
        if datasets:
            return jsonify({
                'datasets': datasets,
                'metric': metric_type,
                'node': node_name
            })
        
        return jsonify({'error': 'No data found'}), 404
        
    except Exception as e:
        logger.error(f"Error fetching timeseries: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/nodes/current-load')
def get_nodes_current_load():
    """Get current CPU load for all nodes (max in last hour)"""
    try:
        import requests
        
        # Get Prometheus URL from config
        prom_config = config.get('monitoring', {}).get('central_prometheus', {})
        prom_host = prom_config.get('host', 'localhost')
        prom_port = prom_config.get('port', 9091)
        
        # Query for max CPU in last hour for all nodes
        # query = 'max_over_time(emulation_node_cpu_percent[1h])'
        query = 'emulation_node_cpu_percent'
        prom_url = f'http://{prom_host}:{prom_port}/api/v1/query'
        
        params = {'query': query}
        
        response = requests.get(prom_url, params=params, timeout=10)
        prom_data = response.json()
        
        node_loads = {}
        
        if prom_data.get('status') == 'success':
            results = prom_data.get('data', {}).get('result', [])
            for result in results:
                metric = result.get('metric', {})
                node_name = metric.get('container_node')
                value = float(result.get('value', [0, 0])[1])
                
                if node_name:
                    node_loads[node_name] = {
                        'cpu_max': round(value, 2),
                        'color': get_load_color(value)
                    }
        
        return jsonify({'node_loads': node_loads})
        
    except Exception as e:
        logger.error(f"Error fetching node loads: {e}")
        return jsonify({'error': str(e)}), 500

def get_load_color(cpu_percent):
    """Determine color based on CPU percentage"""
    if cpu_percent < 20:
        return 'green'
    elif cpu_percent <= 60:
        return 'amber'
    else:
        return 'red'


@app.route('/api/node/<node_name>/pod/<namespace>/<pod_name>/timeseries')
def get_pod_timeseries(node_name, namespace, pod_name):
    """Get time-series metrics for a specific pod from annotations"""
    try:
        import requests
        from datetime import datetime, timedelta
        
        metric_type = request.args.get('metric', 'cpu')
        window = request.args.get('window', '5m')
        
        # Map metric types to Prometheus metric names
        metric_map = {
            'cpu': 'cpu_percent',
            'psi': 'psi_percent',
            'power': 'power_watts',
            'memory': 'memory_percent'
        }
        
        base_metric = metric_map.get(metric_type, 'cpu_percent')
        
        # Get Prometheus URL from config
        prom_config = config.get('monitoring', {}).get('central_prometheus', {})
        prom_host = prom_config.get('host', 'localhost')
        prom_port = prom_config.get('port', 9091)
        
        # Calculate time range
        end_time = datetime.now()
        if window.endswith('m'):
            minutes = int(window[:-1])
            start_time = end_time - timedelta(minutes=minutes)
        elif window.endswith('h'):
            hours = int(window[:-1])
            start_time = end_time - timedelta(hours=hours)
        else:
            start_time = end_time - timedelta(minutes=5)
        
        # Query pod-level metrics
        # Format: emulation_pod_{metric}
        metric_name = f'emulation_pod_{base_metric}'
        query = f'{metric_name}{{container_node="{node_name}",namespace="{namespace}",pod="{pod_name}"}}'
        prom_url = f'http://{prom_host}:{prom_port}/api/v1/query_range'
        
        params = {
            'query': query,
            'start': start_time.timestamp(),
            'end': end_time.timestamp(),
            'step': '15s'
        }
        
        response = requests.get(prom_url, params=params, timeout=10)
        prom_data = response.json()
        
        if prom_data.get('status') == 'success':
            results = prom_data.get('data', {}).get('result', [])
            if results:
                values = results[0].get('values', [])
                timestamps = [v[0] for v in values]
                data_points = [float(v[1]) for v in values]
                
                return jsonify({
                    'timestamps': timestamps,
                    'values': data_points,
                    'metric': metric_type,
                    'pod': pod_name,
                    'namespace': namespace
                })
        
        return jsonify({'error': 'No data found'}), 404
        
    except Exception as e:
        logger.error(f"Error fetching pod timeseries: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/status')
def get_system_status():
    """Get host system CPU and RAM usage"""
    try:
        # Get CPU and RAM metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Get disk usage for root partition
        disk = psutil.disk_usage('/')
        
        return jsonify({
            'cpu': {
                'percent': round(cpu_percent, 1),
                'cores': psutil.cpu_count()
            },
            'memory': {
                'percent': round(memory.percent, 1),
                'used_gb': round(memory.used / (1024**3), 2),
                'total_gb': round(memory.total / (1024**3), 2)
            },
            'disk': {
                'percent': round(disk.percent, 1),
                'used_gb': round(disk.used / (1024**3), 2),
                'total_gb': round(disk.total / (1024**3), 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching system status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/virtual-pods', methods=['GET'])
def list_virtual_pods():
    """List all virtual pods from registry"""
    try:
        if VIRTUAL_PODS_REGISTRY.exists():
            with open(VIRTUAL_PODS_REGISTRY, 'r') as f:
                registry = json.load(f)
            return jsonify(registry)
        else:
            return jsonify({'virtual_pods': []})
            
    except Exception as e:
        logger.error(f"Error listing virtual pods: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/virtual-pods/create', methods=['POST'])
def create_virtual_pod():
    """Create a new virtual pod"""
    try:
        data = request.json
        
        # Validate required fields
        required = ['source_node', 'dest_node', 'workload_file']
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Build full path to workload file
        workload_path = WORKLOAD_TEMPLATES_DIR / data['workload_file']
        
        if not workload_path.exists():
            return jsonify({'error': f'Workload template not found: {data["workload_file"]}'}), 404
        
        # Build command
        cmd = [
            'python3', str(VIRTUAL_POD_MANAGER_PATH), 'create',
            '--source-node', data['source_node'],
            '--dest-node', data['dest_node'],
            '--workload', str(workload_path),
            '--interval', str(data.get('interval', 5))
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(BASE_DIR)  # Run from flask app directory
        )
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Virtual pod created successfully',
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout creating virtual pod'}), 504
    except Exception as e:
        logger.error(f"Error creating virtual pod: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/virtual-pods/<pod_id>', methods=['DELETE'])
def delete_virtual_pod(pod_id):
    """Delete a virtual pod"""
    try:
        result = subprocess.run(
            ['python3', str(VIRTUAL_POD_MANAGER_PATH), 'delete', '--id', pod_id],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(BASE_DIR)
        )
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Virtual pod {pod_id} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr
            }), 500
            
    except Exception as e:
        logger.error(f"Error deleting virtual pod: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/workload-templates', methods=['GET'])
def get_workload_templates():
    """Get available workload templates"""
    try:
        templates = []
        
        if WORKLOAD_TEMPLATES_DIR.exists():
            for file in WORKLOAD_TEMPLATES_DIR.glob('*.json'):
                # Try to read template to get metadata
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                        time_points = len(data.get('time_series', []))
                        
                    templates.append({
                        'name': file.stem,
                        'filename': file.name,
                        'time_points': time_points
                    })
                except:
                    templates.append({
                        'name': file.stem,
                        'filename': file.name,
                        'time_points': 0
                    })
        
        return jsonify({'templates': templates})
        
    except Exception as e:
        logger.error(f"Error getting workload templates: {e}")
        return jsonify({'error': str(e)}), 500
    

def save_liqo_connections(connections):
    """Save Liqo connections to file"""
    with open(LIQO_CONNECTIONS_FILE, 'w') as f:
        json.dump(connections, f, indent=2)

@app.route('/api/liqo-connections', methods=['GET'])
def get_liqo_connections():
    """Get all Liqo connections"""
    try:
        connections = load_liqo_connections()
        return jsonify({'connections': connections})
    except Exception as e:
        logger.error(f"Error getting Liqo connections: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/liqo-connections', methods=['POST'])
def add_liqo_connection():
    """Add a new Liqo connection"""
    try:
        data = request.json
        connections = load_liqo_connections()
        
        # Prevent duplicates
        exists = any(
            c['from'] == data['from'] and c['to'] == data['to']
            for c in connections
        )
        
        if not exists:
            connections.append({
                'from': data['from'],
                'to': data['to']
            })
            save_liqo_connections(connections)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding Liqo connection: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/liqo-connections', methods=['DELETE'])
def remove_liqo_connection():
    """Remove a Liqo connection"""
    try:
        data = request.json
        connections = load_liqo_connections()
        
        connections = [
            c for c in connections
            if not (
                (c['from'] == data['from'] and c['to'] == data['to']) or
                (c['from'] == data['to'] and c['to'] == data['from'])
            )
        ]
        
        save_liqo_connections(connections)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error removing Liqo connection: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/node/<node_name>/emulation-config')
def get_emulation_config(node_name):
    """Get emulation config resources for a node"""
    try:
        container_name = f"clab-emulation-{node_name}"
        
        result = subprocess.run(
            ['docker', 'exec', container_name, 
             'cat', '/opt/annotations/emulation_config.json'],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({'error': 'Config file not found'}), 404
        
        config = json.loads(result.stdout)
        node_config = config.get('node_config', {})
        
        if node_config.get('mode') == 'single':
            node = node_config.get('single_node', {})
            resources = [{
                'name': node.get('name'),
                'cpu': node.get('cpu'),
                'memory': node.get('memory')
            }]
        else:
            resources = [
                {
                    'name': n.get('name'),
                    'cpu': n.get('cpu'),
                    'memory': n.get('memory')
                }
                for n in node_config.get('per_namespace_nodes', {}).values()
            ]
        
        return jsonify({'resources': resources})
        
    except Exception as e:
        logger.error(f"Error getting emulation config: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    server_config = config.get('server', {})
    app.run(
        host=server_config.get('host', '0.0.0.0'),
        port=server_config.get('port', 8080),
        debug=server_config.get('debug', True)
    )


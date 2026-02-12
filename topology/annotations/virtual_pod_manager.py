#!/usr/bin/env python3
"""
Virtual Pod Manager (Host VM Version)
Manages virtual pods across ContainerLab nodes using docker exec.
Runs from host VM without needing kubeconfig files.
"""

import json
import sys
import os
import argparse
import subprocess
from datetime import datetime
from typing import Dict, Optional, List
import time


class VirtualPodManager:
    """Manage virtual pod creation, tracking, and cleanup via docker exec"""
    
    def __init__(self, registry_file: str = "virtual_pods/registry.json",
                 virtual_pods_dir: str = "virtual_pods",
                 container_prefix: str = "clab-emulation"):
        self.registry_file = registry_file
        self.virtual_pods_dir = virtual_pods_dir
        self.container_prefix = container_prefix
        self.registry = {"virtual_pods": []}
        
        # Ensure directory exists on host
        os.makedirs(self.virtual_pods_dir, exist_ok=True)
        
        self.load_registry()
    
    def get_container_name(self, node_name: str) -> str:
        """Convert node name to container name"""
        return f"{self.container_prefix}-{node_name}"
    
    def docker_exec(self, node_name: str, command: List[str], 
                   detached: bool = False, input_data: str = None) -> subprocess.CompletedProcess:
        """Execute command in container via docker exec"""
        container = self.get_container_name(node_name)
        
        docker_cmd = ['docker', 'exec']
        if detached:
            docker_cmd.append('-d')
        if input_data:
            docker_cmd.append('-i')
        
        docker_cmd.append(container)
        docker_cmd.extend(command)
        
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                input=input_data,
                check=False
            )
            return result
        except Exception as e:
            print(f"Error executing docker command: {e}")
            raise
    
    def load_registry(self):
        """Load or create registry file"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r') as f:
                    self.registry = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Invalid registry file, creating new one")
                self.registry = {"virtual_pods": []}
        else:
            self.save_registry()
    
    def save_registry(self):
        """Save registry to file"""
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, indent=2, fp=f)
    
    def get_next_pod_id(self) -> int:
        """Get next available pod ID"""
        if not self.registry['virtual_pods']:
            return 1
        
        max_id = max(int(vp['id'].split('-')[-1]) for vp in self.registry['virtual_pods'])
        return max_id + 1
    
    def ensure_namespace(self, node_name: str, namespace: str = "liqo") -> bool:
        """Create namespace if it doesn't exist"""
        # Check if namespace exists
        result = self.docker_exec(
            node_name,
            ['k3s', 'kubectl', 'get', 'namespace', namespace]
        )
        
        if result.returncode == 0:
            print(f"  ✓ Namespace '{namespace}' exists on {node_name}")
            return True
        
        # Create namespace
        ns_manifest = f"""
apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
"""
        
        result = self.docker_exec(
            node_name,
            ['k3s', 'kubectl', 'apply', '-f', '-'],
            input_data=ns_manifest
        )
        
        if result.returncode == 0:
            print(f"  ✓ Created namespace '{namespace}' on {node_name}")
            return True
        else:
            print(f"  ✗ Failed to create namespace on {node_name}: {result.stderr}")
            return False
    
    def create_kwok_pod(self, node_name: str, pod_name: str, namespace: str,
                       kwok_node: str, annotations: Dict[str, str]) -> bool:
        """Create a KWOK pod via kubectl"""
        
        # Build annotations string
        annotations_json = json.dumps(annotations)
        
        pod_manifest = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {namespace}
  labels:
    app: {pod_name}
    emulation.k8s.io/pod: "true"
    emulation.liqo.k8s.io/virtual: "true"
  annotations: {annotations_json}
spec:
  nodeName: {kwok_node}
  tolerations:
  - key: kwok.x-k8s.io/node
    operator: Exists
    effect: NoSchedule
  containers:
  - name: {pod_name}
    image: fake-image:latest
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 1000m
        memory: 512Mi
"""
        
        result = self.docker_exec(
            node_name,
            ['k3s', 'kubectl', 'apply', '-f', '-'],
            input_data=pod_manifest
        )
        
        if result.returncode == 0:
            return True
        else:
            print(f"  ✗ Failed to create pod: {result.stderr}")
            return False
    
    def create_json_file_in_container(self, node_name: str, filepath: str, 
                                     content: Dict) -> bool:
        """Create JSON file inside container"""
        json_content = json.dumps(content, indent=2)
        
        # Ensure directory exists
        dir_path = os.path.dirname(filepath)
        self.docker_exec(
            node_name,
            ['mkdir', '-p', dir_path]
        )
        
        # Write file
        result = self.docker_exec(
            node_name,
            ['bash', '-c', f'cat > {filepath}'],
            input_data=json_content
        )
        
        return result.returncode == 0
    
    def start_replayer_in_container(self, node_name: str, json_file: str, 
                                   interval: int = 5) -> Optional[str]:
        """Start replayer process inside container"""
        
        cmd = [
            'bash', '-c',
            f'cd /opt/annotations && nohup python3 replay_virtual_pod.py '
            f'--config {json_file} --interval {interval} --loop '
            f'> /tmp/replayer-{os.path.basename(json_file)}.log 2>&1 & echo $!'
        ]
        
        result = self.docker_exec(node_name, cmd)
        
        if result.returncode == 0:
            pid = result.stdout.strip()
            print(f"  ✓ Started replayer in {node_name} (PID: {pid})")
            return pid
        else:
            print(f"  ✗ Failed to start replayer: {result.stderr}")
            return None
    
    def load_workload_template(self, workload_file: str) -> Dict:
        """Load workload template from host"""
        try:
            with open(workload_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Workload file not found: {workload_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in workload file: {e}")
            sys.exit(1)
    
    def create_virtual_pod(self, source_node: str, dest_node: str,
                          workload_file: str, interval: int = 5) -> bool:
        """
        Create a virtual pod pair (source placeholder + destination with replay)
        
        Args:
            source_node: Clab node name (e.g., 'serf1')
            dest_node: Clab node name (e.g., 'serf2')
            workload_file: JSON file with time series data (on host)
            interval: Replay interval in seconds
        """
        
        print("="*70)
        print("CREATING VIRTUAL POD")
        print("="*70)
        
        # Generate pod ID and names
        pod_id = self.get_next_pod_id()
        pod_id_str = f"vp-{pod_id:03d}"
        base_name = f"virtual-pod-{pod_id:03d}"
        source_pod_name = f"{base_name}-source"
        dest_pod_name = f"{base_name}-dest"
        
        # KWOK node name (same in all clusters)
        kwok_node = "emulation-node-1"
        
        print(f"\nVirtual Pod ID: {pod_id_str}")
        print(f"Source: {source_node} (container: {self.get_container_name(source_node)})")
        print(f"  Pod: liqo/{source_pod_name} on KWOK node {kwok_node}")
        print(f"Destination: {dest_node} (container: {self.get_container_name(dest_node)})")
        print(f"  Pod: liqo/{dest_pod_name} on KWOK node {kwok_node}")
        
        # Load workload template
        print("\n1. Loading workload template...")
        workload_data = self.load_workload_template(workload_file)
        print(f"  ✓ Loaded {len(workload_data.get('time_series', []))} time points")
        
        # Ensure liqo namespace on both nodes
        print("\n2. Ensuring liqo namespace...")
        if not self.ensure_namespace(source_node, "liqo"):
            return False
        if not self.ensure_namespace(dest_node, "liqo"):
            return False
        
        # Create source placeholder pod
        print("\n3. Creating source placeholder pod...")
        source_annotations = {
            "emulation.liqo.k8s.io/is-virtual": "true",
            "emulation.liqo.k8s.io/role": "source",
            "emulation.liqo.k8s.io/destination-node": dest_node,
            "emulation.liqo.k8s.io/destination-pod": dest_pod_name,
            "emulation.liqo.k8s.io/virtual-pod-id": pod_id_str,
            "emulation.metrics.k8s.io/cpu": "0m",
            "emulation.metrics.k8s.io/memory": "0Mi",
            "emulation.metrics.k8s.io/power": "0.0",
            "emulation.metrics.k8s.io/psi": "0.0",
            "emulation.metrics.k8s.io/timestamp": datetime.now().isoformat()
        }
        
        if not self.create_kwok_pod(source_node, source_pod_name, "liqo", 
                                    kwok_node, source_annotations):
            print("✗ Failed to create source pod")
            return False
        
        print(f"  ✓ Created source placeholder: liqo/{source_pod_name} on {source_node}")
        
        # Create destination pod
        print("\n4. Creating destination pod...")
        dest_annotations = {
            "emulation.liqo.k8s.io/is-virtual": "true",
            "emulation.liqo.k8s.io/role": "destination",
            "emulation.liqo.k8s.io/source-node": source_node,
            "emulation.liqo.k8s.io/source-pod": source_pod_name,
            "emulation.liqo.k8s.io/virtual-pod-id": pod_id_str,
            "emulation.metrics.k8s.io/cpu": "0m",
            "emulation.metrics.k8s.io/memory": "0Mi",
            "emulation.metrics.k8s.io/power": "0.0",
            "emulation.metrics.k8s.io/psi": "0.0",
            "emulation.metrics.k8s.io/timestamp": datetime.now().isoformat()
        }
        
        if not self.create_kwok_pod(dest_node, dest_pod_name, "liqo", 
                                    kwok_node, dest_annotations):
            print("✗ Failed to create destination pod")
            # Cleanup source pod
            self.docker_exec(
                source_node,
                ['k3s', 'kubectl', 'delete', 'pod', source_pod_name, '-n', 'liqo', '--force']
            )
            return False
        
        print(f"  ✓ Created destination pod: liqo/{dest_pod_name} on {dest_node}")
        
        # Generate time series JSON for destination node
        print("\n5. Generating time series configuration...")
        json_filename = f"{pod_id_str}.json"
        json_path_in_container = f"/opt/annotations/virtual_pods/{json_filename}"
        
        virtual_pod_config = {
            "pod_name": dest_pod_name,
            "namespace": "liqo",
            "source_node": source_node,
            "destination_node": dest_node,
            "time_series": workload_data.get("time_series", [])
        }
        
        if not self.create_json_file_in_container(dest_node, json_path_in_container, 
                                                  virtual_pod_config):
            print("✗ Failed to create JSON file")
            # Cleanup
            self.docker_exec(source_node, ['k3s', 'kubectl', 'delete', 'pod', 
                                          source_pod_name, '-n', 'liqo', '--force'])
            self.docker_exec(dest_node, ['k3s', 'kubectl', 'delete', 'pod', 
                                        dest_pod_name, '-n', 'liqo', '--force'])
            return False
        
        print(f"  ✓ Created: {json_path_in_container} on {dest_node}")
        
        # Start replayer on destination node
        print("\n6. Starting metrics replayer...")
        replayer_pid = self.start_replayer_in_container(dest_node, json_path_in_container, interval)
        
        if not replayer_pid:
            print("✗ Failed to start replayer")
            # Cleanup
            self.docker_exec(source_node, ['k3s', 'kubectl', 'delete', 'pod', 
                                          source_pod_name, '-n', 'liqo', '--force'])
            self.docker_exec(dest_node, ['k3s', 'kubectl', 'delete', 'pod', 
                                        dest_pod_name, '-n', 'liqo', '--force'])
            self.docker_exec(dest_node, ['rm', '-f', json_path_in_container])
            return False
        
        # Add to registry
        print("\n7. Updating registry...")
        virtual_pod_entry = {
            "id": pod_id_str,
            "source_node": source_node,
            "source_pod_name": source_pod_name,
            "dest_node": dest_node,
            "dest_pod_name": dest_pod_name,
            "namespace": "liqo",
            "kwok_node": kwok_node,
            "time_series_file": json_path_in_container,
            "workload_file": workload_file,
            "created_at": datetime.now().isoformat(),
            "status": "running",
            "replayer_pid": replayer_pid,
            "interval": interval
        }
        
        self.registry['virtual_pods'].append(virtual_pod_entry)
        self.save_registry()
        
        print("  ✓ Registry updated")
        
        print("\n" + "="*70)
        print("SUCCESS")
        print("="*70)
        print(f"\nVirtual pod created successfully!")
        print(f"  ID: {pod_id_str}")
        print(f"  Source: {source_node}/liqo/{source_pod_name}")
        print(f"  Destination: {dest_node}/liqo/{dest_pod_name}")
        print(f"  Replayer PID: {replayer_pid}")
        
        return True
    
    def list_virtual_pods(self):
        """List all virtual pods"""
        print("="*70)
        print("VIRTUAL PODS")
        print("="*70)
        
        if not self.registry['virtual_pods']:
            print("\nNo virtual pods found.")
            return
        
        for vp in self.registry['virtual_pods']:
            print(f"\nID: {vp['id']}")
            print(f"  Source: {vp['source_node']}/liqo/{vp['source_pod_name']}")
            print(f"  Destination: {vp['dest_node']}/liqo/{vp['dest_pod_name']}")
            print(f"  Status: {vp['status']}")
            print(f"  Created: {vp['created_at']}")
            print(f"  Replayer PID: {vp.get('replayer_pid', 'N/A')}")
    
    def delete_virtual_pod(self, pod_id: str):
        """Delete a virtual pod and cleanup resources"""
        print("="*70)
        print(f"DELETING VIRTUAL POD: {pod_id}")
        print("="*70)
        
        # Find pod in registry
        vp = None
        for virtual_pod in self.registry['virtual_pods']:
            if virtual_pod['id'] == pod_id:
                vp = virtual_pod
                break
        
        if not vp:
            print(f"\n✗ Virtual pod {pod_id} not found in registry")
            return False
        
        # Stop replayer process on destination node
        print("\n1. Stopping replayer process...")
        if vp.get('replayer_pid'):
            result = self.docker_exec(
                vp['dest_node'],
                ['kill', vp['replayer_pid']]
            )
            if result.returncode == 0:
                print(f"  ✓ Terminated process {vp['replayer_pid']} on {vp['dest_node']}")
            else:
                print(f"  ⚠ Process may already be stopped")
        
        # Delete source pod
        print("\n2. Deleting source pod...")
        result = self.docker_exec(
            vp['source_node'],
            ['k3s', 'kubectl', 'delete', 'pod', vp['source_pod_name'], 
             '-n', 'liqo', '--force', '--grace-period=0']
        )
        if result.returncode == 0:
            print(f"  ✓ Deleted {vp['source_node']}/liqo/{vp['source_pod_name']}")
        else:
            print(f"  ⚠ Source pod may not exist")
        
        # Delete destination pod
        print("\n3. Deleting destination pod...")
        result = self.docker_exec(
            vp['dest_node'],
            ['k3s', 'kubectl', 'delete', 'pod', vp['dest_pod_name'], 
             '-n', 'liqo', '--force', '--grace-period=0']
        )
        if result.returncode == 0:
            print(f"  ✓ Deleted {vp['dest_node']}/liqo/{vp['dest_pod_name']}")
        else:
            print(f"  ⚠ Destination pod may not exist")
        
        # Delete time series file
        print("\n4. Cleaning up files...")
        result = self.docker_exec(
            vp['dest_node'],
            ['rm', '-f', vp['time_series_file']]
        )
        if result.returncode == 0:
            print(f"  ✓ Deleted {vp['time_series_file']} on {vp['dest_node']}")
        
        # Remove from registry
        print("\n5. Updating registry...")
        self.registry['virtual_pods'] = [
            p for p in self.registry['virtual_pods'] if p['id'] != pod_id
        ]
        self.save_registry()
        print("  ✓ Registry updated")
        
        print("\n" + "="*70)
        print("SUCCESS")
        print("="*70)
        print(f"\nVirtual pod {pod_id} deleted successfully!")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Manage virtual pods for Liqo emulation (Host VM version)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create virtual pod from serf1 to serf2
  python3 virtual_pod_manager.py create \
    --source-node serf1 \
    --dest-node serf2 \
    --workload workload_templates/workload-light.json \
    --interval 5
  
  # List all virtual pods
  python3 virtual_pod_manager.py list
  
  # Delete virtual pod
  python3 virtual_pod_manager.py delete --id vp-001

Workload JSON format (on host VM):
  {
    "time_series": [
      {"cpu": 500, "memory": 256, "power": 12.5, "psi": 5.2},
      {"cpu": 600, "memory": 280, "power": 14.0, "psi": 6.1}
    ]
  }

Note: Run this script from the host VM, not inside containers.
      Node names are clab node names (serf1, serf2, etc.)
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new virtual pod')
    create_parser.add_argument('--source-node', required=True,
                              help='Source clab node name (e.g., serf1)')
    create_parser.add_argument('--dest-node', required=True,
                              help='Destination clab node name (e.g., serf2)')
    create_parser.add_argument('--workload', required=True,
                              help='Path to workload time series JSON file (on host)')
    create_parser.add_argument('--interval', type=int, default=5,
                              help='Replay interval in seconds (default: 5)')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all virtual pods')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a virtual pod')
    delete_parser.add_argument('--id', required=True,
                               help='Virtual pod ID (e.g., vp-001)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create manager
    manager = VirtualPodManager()
    
    # Execute command
    if args.command == 'create':
        success = manager.create_virtual_pod(
            source_node=args.source_node,
            dest_node=args.dest_node,
            workload_file=args.workload,
            interval=args.interval
        )
        sys.exit(0 if success else 1)
    
    elif args.command == 'list':
        manager.list_virtual_pods()
    
    elif args.command == 'delete':
        success = manager.delete_virtual_pod(args.id)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
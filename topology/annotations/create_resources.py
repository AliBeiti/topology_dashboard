#!/usr/bin/env python3
"""
KWOK Resource Creator
Creates nodes, namespaces, and pods from emulation_config.json
Designed for k3s clusters with KWOK installed.
"""

import json
import subprocess
import sys
import time
import argparse
from typing import Dict, List, Set


class KWOKResourceCreator:
    """Create KWOK nodes and pods from configuration"""
    
    def __init__(self, config_file: str, dry_run: bool = False):
        self.config_file = config_file
        self.dry_run = dry_run
        self.config = None
        self.kubectl_cmd = None
        self._find_kubectl()
    
    def _find_kubectl(self):
        """Find kubectl or k3s kubectl command"""
        # Try regular kubectl first
        try:
            subprocess.run(['kubectl', 'version', '--client'], 
                         capture_output=True, check=True, timeout=5)
            self.kubectl_cmd = ['kubectl']
            return
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Try k3s kubectl
        try:
            subprocess.run(['/usr/local/bin/k3s', 'kubectl', 'version', '--client'], 
                         capture_output=True, check=True, timeout=5)
            self.kubectl_cmd = ['/usr/local/bin/k3s', 'kubectl']
            return
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        print("Error: Neither 'kubectl' nor 'k3s kubectl' found")
        sys.exit(1)
        
    def load_config(self):
        """Load emulation configuration"""
        print("="*70)
        print("LOADING CONFIGURATION")
        print("="*70)
        
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            print(f"✓ Loaded: {self.config_file}")
            print(f"  - Pods: {self.config['metadata']['total_pods']}")
            print(f"  - Namespaces: {self.config['metadata']['total_namespaces']}")
            print(f"  - Node mode: {self.config['node_config']['mode']}")
            
        except FileNotFoundError:
            print(f"Error: Config file not found: {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def run_kubectl(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute kubectl command"""
        cmd = self.kubectl_cmd + args
        
        if self.dry_run:
            print(f"[DRY-RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='', stderr='')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                print(f"Error executing: {' '.join(cmd)}")
                print(f"stdout: {e.stdout}")
                print(f"stderr: {e.stderr}")
                raise
            return e
    
    def resource_exists(self, resource_type: str, name: str, namespace: str = None) -> bool:
        """Check if a Kubernetes resource exists"""
        args = ['get', resource_type, name]
        if namespace:
            args.extend(['-n', namespace])
        args.append('--ignore-not-found')
        
        result = self.run_kubectl(args, check=False)
        return result.returncode == 0 and name in result.stdout
    
    def get_existing_resources(self, resource_type: str, namespace: str = None) -> Set[str]:
        """Get set of existing resource names"""
        args = ['get', resource_type, '-o', 'jsonpath={.items[*].metadata.name}']
        if namespace:
            args.extend(['-n', namespace])
        
        result = self.run_kubectl(args, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return set(result.stdout.strip().split())
        return set()
    
    def create_node(self, node_name: str, cpu: str, memory: str):
        """Create a KWOK node with specified resources"""
        
        # Check if node already exists
        if self.resource_exists('node', node_name):
            print(f"  ⚠ Node '{node_name}' already exists, skipping")
            return
        
        # KWOK node manifest
        node_manifest = {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": node_name,
                "annotations": {
                    "node.alpha.kubernetes.io/ttl": "0",
                    "kwok.x-k8s.io/node": "fake"
                },
                "labels": {
                    "beta.kubernetes.io/arch": "amd64",
                    "beta.kubernetes.io/os": "linux",
                    "kubernetes.io/arch": "amd64",
                    "kubernetes.io/hostname": node_name,
                    "kubernetes.io/os": "linux",
                    "kubernetes.io/role": "agent",
                    "node-role.kubernetes.io/agent": "",
                    "type": "kwok",
                    "emulation.k8s.io/node": "true"
                }
            },
            "spec": {
                "taints": [
                    {
                        "effect": "NoSchedule",
                        "key": "kwok.x-k8s.io/node",
                        "value": "fake"
                    }
                ]
            },
            "status": {
                "allocatable": {
                    "cpu": cpu,
                    "memory": memory,
                    "pods": "110"
                },
                "capacity": {
                    "cpu": cpu,
                    "memory": memory,
                    "pods": "110"
                },
                "nodeInfo": {
                    "architecture": "amd64",
                    "bootID": "",
                    "containerRuntimeVersion": "kwok-v0.7.0",
                    "kernelVersion": "",
                    "kubeProxyVersion": "fake",
                    "kubeletVersion": "fake",
                    "machineID": "",
                    "operatingSystem": "linux",
                    "osImage": "",
                    "systemUUID": ""
                },
                "phase": "Running",
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "KubeletReady",
                        "message": "kubelet is posting ready status"
                    },
                    {
                        "type": "MemoryPressure",
                        "status": "False",
                        "reason": "KubeletHasSufficientMemory",
                        "message": "kubelet has sufficient memory available"
                    },
                    {
                        "type": "DiskPressure",
                        "status": "False",
                        "reason": "KubeletHasNoDiskPressure",
                        "message": "kubelet has no disk pressure"
                    },
                    {
                        "type": "PIDPressure",
                        "status": "False",
                        "reason": "KubeletHasSufficientPID",
                        "message": "kubelet has sufficient PID available"
                    },
                    {
                        "type": "NetworkUnavailable",
                        "status": "False",
                        "reason": "RouteCreated",
                        "message": "RouteController created a route"
                    }
                ]
            }
        }
        
        # Create node using kubectl apply
        manifest_json = json.dumps(node_manifest)
        
        if not self.dry_run:
            process = subprocess.Popen(
                self.kubectl_cmd + ['apply', '-f', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=manifest_json)
            
            if process.returncode != 0:
                print(f"  ✗ Failed to create node '{node_name}'")
                print(f"    Error: {stderr}")
                return
        
        print(f"  ✓ Created node '{node_name}' (CPU: {cpu}, Memory: {memory})")
    
    def create_nodes(self):
        """Create KWOK nodes based on configuration"""
        print("\n" + "="*70)
        print("CREATING NODES")
        print("="*70)
        
        node_config = self.config['node_config']
        
        if node_config['mode'] == 'single':
            # Create single node
            node = node_config['single_node']
            print(f"Mode: Single node")
            self.create_node(node['name'], node['cpu'], node['memory'])
            
        else:  # per-namespace
            # Create one node per namespace
            print(f"Mode: Per-namespace nodes")
            per_ns = node_config['per_namespace_nodes']
            
            for ns, node in per_ns.items():
                self.create_node(node['name'], node['cpu'], node['memory'])
        
        # Wait for nodes to be ready
        if not self.dry_run:
            print("\nWaiting for nodes to be ready...")
            time.sleep(2)
            
            result = self.run_kubectl(['get', 'nodes', '-l', 'type=kwok'])
            print(result.stdout)
    
    def create_namespaces(self):
        """Create namespaces"""
        print("\n" + "="*70)
        print("CREATING NAMESPACES")
        print("="*70)
        
        existing_namespaces = self.get_existing_resources('namespace')
        
        for ns in self.config['namespaces']:
            if ns in existing_namespaces:
                print(f"  ⚠ Namespace '{ns}' already exists, skipping")
                continue
            
            if not self.dry_run:
                self.run_kubectl(['create', 'namespace', ns])
            
            print(f"  ✓ Created namespace '{ns}'")
    
    def get_node_for_namespace(self, namespace: str) -> str:
        """Get the node name for a given namespace based on config"""
        node_config = self.config['node_config']
        
        if node_config['mode'] == 'single':
            return node_config['single_node']['name']
        else:
            return node_config['per_namespace_nodes'][namespace]['name']
    
    def create_pod(self, pod_info: Dict, node_name: str):
        """Create a pod assigned to a specific node"""
        
        namespace = pod_info['namespace']
        pod_name = pod_info['pod_name']
        
        # Check if pod already exists
        if self.resource_exists('pod', pod_name, namespace):
            return False  # Already exists
        
        # Pod manifest
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "namespace": namespace,
                "labels": {
                    "app": pod_name,
                    "emulation.k8s.io/pod": "true"
                },
                "annotations": {
                    "emulation.k8s.io/source": "kwok-metrics-emulator"
                }
            },
            "spec": {
                "nodeName": node_name,
                "tolerations": [
                    {
                        "key": "kwok.x-k8s.io/node",
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                ],
                "containers": [
                    {
                        "name": pod_name,
                        "image": "fake-image:latest",
                        "resources": {
                            "requests": {
                                "cpu": "100m",
                                "memory": "128Mi"
                            },
                            "limits": {
                                "cpu": "1000m",
                                "memory": "512Mi"
                            }
                        }
                    }
                ]
            }
        }
        
        # Create pod using kubectl apply
        manifest_json = json.dumps(pod_manifest)
        
        if not self.dry_run:
            process = subprocess.Popen(
                self.kubectl_cmd + ['apply', '-f', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=manifest_json)
            
            if process.returncode != 0:
                print(f"    ✗ Failed to create pod '{namespace}/{pod_name}'")
                print(f"      Error: {stderr}")
                return False
        
        return True  # Successfully created
    
    def create_pods(self):
        """Create all pods"""
        print("\n" + "="*70)
        print("CREATING PODS")
        print("="*70)
        
        total_pods = len(self.config['pods'])
        created_count = 0
        skipped_count = 0
        
        for pod_info in self.config['pods']:
            namespace = pod_info['namespace']
            pod_name = pod_info['pod_name']
            node_name = self.get_node_for_namespace(namespace)
            
            # Check if already exists
            if self.resource_exists('pod', pod_name, namespace):
                skipped_count += 1
                continue
            
            if self.create_pod(pod_info, node_name):
                created_count += 1
                if created_count % 10 == 0:
                    print(f"  Progress: {created_count}/{total_pods} pods created...")
        
        print(f"\n✓ Pod creation complete:")
        print(f"  - Created: {created_count}")
        print(f"  - Skipped (already exist): {skipped_count}")
        print(f"  - Total: {total_pods}")
        
        # Wait for pods to be ready
        if not self.dry_run and created_count > 0:
            print("\nWaiting for pods to be ready...")
            time.sleep(3)
            
            print("\nPod status by namespace:")
            for ns in self.config['namespaces']:
                result = self.run_kubectl(['get', 'pods', '-n', ns, '--no-headers'])
                pod_count = len([line for line in result.stdout.strip().split('\n') if line])
                print(f"  {ns}: {pod_count} pods")
    
    def verify_resources(self):
        """Verify created resources"""
        print("\n" + "="*70)
        print("VERIFICATION")
        print("="*70)
        
        # Check nodes
        print("\nNodes:")
        result = self.run_kubectl(['get', 'nodes', '-l', 'type=kwok', '-o', 'wide'])
        print(result.stdout)
        
        # Check namespaces
        print("\nNamespaces:")
        for ns in self.config['namespaces']:
            exists = self.resource_exists('namespace', ns)
            status = "✓" if exists else "✗"
            print(f"  {status} {ns}")
        
        # Check pod counts
        print("\nPod counts by namespace:")
        for ns in self.config['namespaces']:
            pods = self.get_existing_resources('pod', ns)
            print(f"  {ns}: {len(pods)} pods")
    
    def delete_resources(self):
        """Delete all created resources"""
        print("\n" + "="*70)
        print("DELETING RESOURCES")
        print("="*70)
        
        # Delete pods by namespace
        print("\nDeleting pods...")
        for ns in self.config['namespaces']:
            pods = self.get_existing_resources('pod', ns)
            if pods:
                print(f"  Deleting {len(pods)} pods in namespace '{ns}'...")
                if not self.dry_run:
                    self.run_kubectl(['delete', 'pods', '--all', '-n', ns, '--force', '--grace-period=0'])
        
        # Delete namespaces
        print("\nDeleting namespaces...")
        for ns in self.config['namespaces']:
            if self.resource_exists('namespace', ns):
                print(f"  Deleting namespace '{ns}'...")
                if not self.dry_run:
                    self.run_kubectl(['delete', 'namespace', ns])
        
        # Delete nodes
        print("\nDeleting nodes...")
        node_config = self.config['node_config']
        
        if node_config['mode'] == 'single':
            node_name = node_config['single_node']['name']
            if self.resource_exists('node', node_name):
                print(f"  Deleting node '{node_name}'...")
                if not self.dry_run:
                    self.run_kubectl(['delete', 'node', node_name])
        else:
            for ns, node in node_config['per_namespace_nodes'].items():
                node_name = node['name']
                if self.resource_exists('node', node_name):
                    print(f"  Deleting node '{node_name}'...")
                    if not self.dry_run:
                        self.run_kubectl(['delete', 'node', node_name])
        
        print("\n✓ Resource deletion complete")


def main():
    parser = argparse.ArgumentParser(
        description='Create KWOK nodes and pods from emulation config',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create resources
  python3 create_resources.py --config emulation_config.json
  
  # Dry-run (show what would be created)
  python3 create_resources.py --config emulation_config.json --dry-run
  
  # Delete all resources
  python3 create_resources.py --config emulation_config.json --delete
  
  # Verify existing resources
  python3 create_resources.py --config emulation_config.json --verify-only
        """
    )
    
    parser.add_argument('--config', required=True,
                       help='Path to emulation_config.json')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be created without actually creating')
    parser.add_argument('--delete', action='store_true',
                       help='Delete all resources created from this config')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify existing resources, do not create')
    
    args = parser.parse_args()
    
    # Create resource manager
    creator = KWOKResourceCreator(args.config, args.dry_run)
    
    # Load configuration
    creator.load_config()
    
    if args.delete:
        # Delete mode
        confirm = input("\n⚠ This will delete all resources from this config. Continue? (yes/no): ")
        if confirm.lower() == 'yes':
            creator.delete_resources()
        else:
            print("Aborted.")
        return
    
    if args.verify_only:
        # Verify only
        creator.verify_resources()
        return
    
    # Create mode
    print("\n" + "="*70)
    print("KWOK RESOURCE CREATOR")
    print("="*70)
    
    if args.dry_run:
        print("⚠ DRY-RUN MODE - No resources will be created")
    
    # Create resources
    creator.create_nodes()
    creator.create_namespaces()
    creator.create_pods()
    
    # Verify
    creator.verify_resources()
    
    print("\n" + "="*70)
    print("SUCCESS")
    print("="*70)
    print("\nResources created successfully!")
    print("\nNext steps:")
    print("  1. Verify: kubectl get nodes -l type=kwok")
    print("  2. Verify: kubectl get pods --all-namespaces")
    print(f"  3. Run replayer: python3 replay_metrics.py --config {args.config}")


if __name__ == '__main__':
    main()
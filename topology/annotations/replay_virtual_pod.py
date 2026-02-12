#!/usr/bin/env python3
"""
Virtual Pod Metrics Replayer
Replays time-series metrics for a single virtual pod (Liqo emulation).
Reads from a standalone JSON file and updates pod annotations.
"""

import json
import sys
import time
import argparse
from datetime import datetime
from typing import Dict

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
except ImportError:
    print("Error: kubernetes Python client not installed")
    print("Install with: pip install kubernetes")
    sys.exit(1)


class VirtualPodReplayer:
    """Replay metrics for a single virtual pod"""
    
    def __init__(self, pod_config_file: str, interval: int = 5, loop: bool = False):
        self.pod_config_file = pod_config_file
        self.interval = interval
        self.loop = loop
        self.pod_config = None
        self.k8s_client = None
        self.annotation_keys = {
            'cpu': 'emulation.metrics.k8s.io/cpu',
            'memory': 'emulation.metrics.k8s.io/memory',
            'power': 'emulation.metrics.k8s.io/power',
            'psi': 'emulation.metrics.k8s.io/psi',
            'timestamp': 'emulation.metrics.k8s.io/timestamp'
        }
        
        self.init_k8s_client()
        self.load_config()
    
    def init_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            import os
            
            # Check for K3s config
            k3s_config = '/etc/rancher/k3s/k3s.yaml'
            if os.path.exists(k3s_config):
                if 'KUBECONFIG' not in os.environ:
                    os.environ['KUBECONFIG'] = k3s_config
            
            config.load_kube_config()
            self.k8s_client = client.CoreV1Api()
            
            # Test connection
            self.k8s_client.list_namespace(limit=1)
            print("✓ Kubernetes API connection established")
            
        except Exception as e:
            print(f"Error: Failed to initialize Kubernetes client: {e}")
            sys.exit(1)
    
    def load_config(self):
        """Load virtual pod configuration"""
        print("="*70)
        print("LOADING VIRTUAL POD CONFIGURATION")
        print("="*70)
        
        try:
            with open(self.pod_config_file, 'r') as f:
                self.pod_config = json.load(f)
            
            print(f"✓ Loaded: {self.pod_config_file}")
            print(f"  - Pod: {self.pod_config['namespace']}/{self.pod_config['pod_name']}")
            print(f"  - Source node: {self.pod_config.get('source_node', 'N/A')}")
            print(f"  - Destination node: {self.pod_config.get('destination_node', 'N/A')}")
            print(f"  - Time points: {len(self.pod_config['time_series'])}")
            print(f"  - Interval: {self.interval} seconds")
            print(f"  - Loop mode: {'enabled' if self.loop else 'disabled'}")
            
        except FileNotFoundError:
            print(f"Error: Config file not found: {self.pod_config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)
        except KeyError as e:
            print(f"Error: Missing required field in config: {e}")
            sys.exit(1)
    
    def verify_pod(self) -> bool:
        """Verify the pod exists"""
        namespace = self.pod_config['namespace']
        pod_name = self.pod_config['pod_name']
        
        try:
            self.k8s_client.read_namespaced_pod(name=pod_name, namespace=namespace)
            print(f"\n✓ Pod {namespace}/{pod_name} found")
            return True
        except ApiException as e:
            if e.status == 404:
                print(f"\n✗ Pod {namespace}/{pod_name} not found")
            else:
                print(f"\n✗ Error checking pod: {e.reason}")
            return False
    
    def update_pod_annotations(self, time_index: int) -> bool:
        """Update pod annotations for a specific time point"""
        namespace = self.pod_config['namespace']
        pod_name = self.pod_config['pod_name']
        time_series = self.pod_config['time_series']
        
        # Check bounds
        if time_index >= len(time_series):
            print(f"  ✗ Time index {time_index} out of range")
            return False
        
        metrics = time_series[time_index]
        
        # Build annotations
        annotations = {
            self.annotation_keys['cpu']: f"{metrics['cpu']}m",
            self.annotation_keys['memory']: f"{metrics['memory']}Mi",
            self.annotation_keys['power']: f"{metrics['power']}",
            self.annotation_keys['psi']: f"{metrics['psi']}",
            self.annotation_keys['timestamp']: datetime.now().isoformat(),
            'emulation.metrics.k8s.io/time_index': str(time_index)
        }
        
        # Prepare patch
        patch = {
            "metadata": {
                "annotations": annotations
            }
        }
        
        try:
            self.k8s_client.patch_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=patch
            )
            return True
            
        except ApiException as e:
            print(f"  ✗ Failed to update pod: {e.reason}")
            return False
    
    def replay_timepoint(self, time_index: int) -> bool:
        """Replay metrics for a specific time point"""
        time_point = time_index + 1
        total_points = len(self.pod_config['time_series'])
        
        print(f"[Time {time_point}/{total_points}] Updating...", end='', flush=True)
        
        start_time = time.time()
        success = self.update_pod_annotations(time_index)
        elapsed = time.time() - start_time
        
        status = "✓" if success else "✗"
        print(f" {status} ({elapsed:.3f}s)")
        
        return success
    
    def run(self):
        """Main replay loop"""
        print("\n" + "="*70)
        print("STARTING VIRTUAL POD REPLAY")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        total_time_points = len(self.pod_config['time_series'])
        iteration = 0
        
        try:
            while True:
                iteration += 1
                
                if self.loop and iteration > 1:
                    print(f"\n{'='*70}")
                    print(f"LOOP ITERATION {iteration}")
                    print(f"{'='*70}")
                
                # Replay all time points
                for time_index in range(total_time_points):
                    self.replay_timepoint(time_index)
                    
                    # Sleep until next time point (except for last point)
                    if time_index < total_time_points - 1:
                        time.sleep(self.interval)
                
                # If not looping, break after first iteration
                if not self.loop:
                    break
                
                # If looping, restart
                print(f"\n⏳ Completed iteration {iteration}. Restarting in {self.interval}s...")
                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("REPLAY INTERRUPTED")
            print("="*70)
            print(f"Completed {iteration} iteration(s)")
            print(f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n" + "="*70)
        print("REPLAY COMPLETE")
        print("="*70)
        print(f"Total iterations: {iteration}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(
        description='Replay metrics for a single virtual pod',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Replay once with 5-second intervals
  python3 replay_virtual_pod.py --config virtual_pods/pod-001.json --interval 5
  
  # Continuous replay (loop mode)
  python3 replay_virtual_pod.py --config virtual_pods/pod-001.json --interval 5 --loop
  
  # Verify pod only
  python3 replay_virtual_pod.py --config virtual_pods/pod-001.json --verify-only

Virtual Pod JSON Format:
  {
    "pod_name": "virtual-pod-001",
    "namespace": "sa",
    "source_node": "emulation-node-1",
    "destination_node": "emulation-node-2",
    "time_series": [
      {"cpu": 500, "memory": 256, "power": 12.5, "psi": 5.2},
      {"cpu": 600, "memory": 280, "power": 14.0, "psi": 6.1}
    ]
  }
        """
    )
    
    parser.add_argument('--config', required=True,
                       help='Path to virtual pod JSON config file')
    parser.add_argument('--interval', type=int, default=5,
                       help='Seconds between time points (default: 5)')
    parser.add_argument('--loop', action='store_true',
                       help='Loop replay continuously')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify pod exists, do not replay')
    
    args = parser.parse_args()
    
    if args.interval < 1:
        print("Error: Interval must be at least 1 second")
        sys.exit(1)
    
    # Create replayer
    replayer = VirtualPodReplayer(args.config, args.interval, args.loop)
    
    # Verify pod exists
    if not replayer.verify_pod():
        print("\n✗ Cannot proceed - pod not found")
        sys.exit(1)
    
    if args.verify_only:
        sys.exit(0)
    
    # Start replay
    print("\n" + "="*70)
    print("Press Ctrl+C to stop")
    print("="*70)
    time.sleep(1)
    
    replayer.run()


if __name__ == '__main__':
    main()
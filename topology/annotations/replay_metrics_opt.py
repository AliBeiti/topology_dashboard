#!/usr/bin/env python3
"""
Optimized Metrics Replayer
Replays historical metrics with minimal CPU overhead using Kubernetes Python client.
Uses concurrent batch updates instead of sequential kubectl subprocess calls.
"""

import json
import sys
import time
import argparse
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
except ImportError:
    print("Error: kubernetes Python client not installed")
    print("Install with: pip install kubernetes --break-system-packages")
    sys.exit(1)


class OptimizedMetricsReplayer:
    """Replay time-series metrics using Kubernetes API directly"""
    
    def __init__(self, config_file: str, interval: int = 30, loop: bool = False, workers: int = 10):
        self.config_file = config_file
        self.interval = interval
        self.loop = loop
        self.workers = workers
        self.config = None
        self.annotation_keys = None
        self.k8s_client = None
        self.stats_lock = Lock()
        self.stats = {'success': 0, 'failed': 0}
        
    def load_config(self):
        """Load emulation configuration"""
        print("="*70)
        print("LOADING CONFIGURATION")
        print("="*70)
        
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            self.annotation_keys = self.config['emulation']['annotation_keys']
            
            print(f"✓ Loaded: {self.config_file}")
            print(f"  - Pods: {self.config['metadata']['total_pods']}")
            print(f"  - Time points: {self.config['metadata']['time_points']}")
            print(f"  - Interval: {self.interval} seconds")
            print(f"  - Loop mode: {'enabled' if self.loop else 'disabled'}")
            print(f"  - Worker threads: {self.workers}")
            print(f"\nAnnotation keys:")
            for metric, key in self.annotation_keys.items():
                print(f"  {metric:12s}: {key}")
            
        except FileNotFoundError:
            print(f"Error: Config file not found: {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def init_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            # Try in-cluster config first
            try:
                config.load_incluster_config()
                print("✓ Using in-cluster Kubernetes config")
            except config.ConfigException:
                # Fall back to kubeconfig
                config.load_kube_config()
                print("✓ Using kubeconfig")
            
            self.k8s_client = client.CoreV1Api()
            
            # Test connection
            self.k8s_client.list_namespace(limit=1)
            print("✓ Kubernetes API connection established")
            
        except Exception as e:
            print(f"Error: Failed to initialize Kubernetes client: {e}")
            sys.exit(1)
    
    def update_pod_annotations_api(self, namespace: str, pod_name: str, annotations: Dict[str, str]) -> bool:
        """Update pod annotations using Kubernetes API"""
        try:
            # Prepare patch
            patch = {
                "metadata": {
                    "annotations": annotations
                }
            }
            
            # Apply patch
            self.k8s_client.patch_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=patch
            )
            
            return True
            
        except ApiException as e:
            if e.status != 404:  # Ignore not found errors
                print(f"  ✗ API error updating {namespace}/{pod_name}: {e.reason}")
            return False
        except Exception as e:
            print(f"  ✗ Error updating {namespace}/{pod_name}: {e}")
            return False
    
    def update_single_pod(self, pod_info: Dict, time_index: int) -> bool:
        """Update a single pod - designed for concurrent execution"""
        namespace = pod_info['namespace']
        pod_name = pod_info['pod_name']
        time_series = pod_info['time_series']
        
        # Check bounds
        if time_index >= len(time_series):
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
        
        # Update pod
        success = self.update_pod_annotations_api(namespace, pod_name, annotations)
        
        # Update stats
        with self.stats_lock:
            if success:
                self.stats['success'] += 1
            else:
                self.stats['failed'] += 1
        
        return success
    
    def replay_timepoint(self, time_index: int) -> int:
        """Replay metrics for a specific time point using concurrent updates"""
        
        time_point = time_index + 1
        total_pods = len(self.config['pods'])
        
        # Reset stats
        with self.stats_lock:
            self.stats = {'success': 0, 'failed': 0}
        
        print(f"\n[Time {time_point}/{self.config['metadata']['time_points']}] ", end='', flush=True)
        print(f"Updating {total_pods} pods...", end='', flush=True)
        
        start_time = time.time()
        
        # Use ThreadPoolExecutor for concurrent updates
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Submit all pod updates
            futures = {
                executor.submit(self.update_single_pod, pod_info, time_index): pod_info
                for pod_info in self.config['pods']
            }
            
            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    pod_info = futures[future]
                    print(f"\n  ✗ Exception for {pod_info['namespace']}/{pod_info['pod_name']}: {e}")
        
        elapsed = time.time() - start_time
        
        with self.stats_lock:
            success_count = self.stats['success']
            fail_count = self.stats['failed']
        
        print(f" Done in {elapsed:.2f}s (✓ {success_count}, ✗ {fail_count})")
        
        return success_count
    
    def run(self):
        """Main replay loop"""
        print("\n" + "="*70)
        print("STARTING OPTIMIZED METRICS REPLAY")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        total_time_points = self.config['metadata']['time_points']
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
                    success = self.replay_timepoint(time_index)
                    
                    if success == 0:
                        print("\n⚠  Warning: No pods updated successfully")
                    
                    # Sleep until next time point (except for last point)
                    if time_index < total_time_points - 1:
                        time.sleep(self.interval)
                
                # If not looping, break after first iteration
                if not self.loop:
                    break
                
                # If looping, add a small delay before restarting
                print(f"\n⏳ Completed iteration {iteration}. Restarting in {self.interval} seconds...")
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
    
    def verify_pods(self):
        """Verify that all pods exist before starting replay"""
        print("\n" + "="*70)
        print("VERIFYING PODS")
        print("="*70)
        
        total_pods = len(self.config['pods'])
        found_count = 0
        missing_pods = []
        
        # Group by namespace for efficiency
        namespaces = {}
        for pod_info in self.config['pods']:
            ns = pod_info['namespace']
            if ns not in namespaces:
                namespaces[ns] = []
            namespaces[ns].append(pod_info['pod_name'])
        
        # Check each namespace
        for namespace, pod_names in namespaces.items():
            try:
                pod_list = self.k8s_client.list_namespaced_pod(namespace=namespace)
                existing_pods = {pod.metadata.name for pod in pod_list.items}
                
                for pod_name in pod_names:
                    if pod_name in existing_pods:
                        found_count += 1
                    else:
                        missing_pods.append(f"{namespace}/{pod_name}")
            
            except ApiException as e:
                print(f"  ✗ Error checking namespace {namespace}: {e.reason}")
                missing_pods.extend([f"{namespace}/{name}" for name in pod_names])
        
        print(f"\nPod verification:")
        print(f"  Found: {found_count}/{total_pods}")
        
        if missing_pods:
            print(f"  Missing: {len(missing_pods)}")
            print(f"\n⚠  Missing pods:")
            for pod in missing_pods[:10]:
                print(f"    - {pod}")
            if len(missing_pods) > 10:
                print(f"    ... and {len(missing_pods) - 10} more")
            
            return False
        
        print(f"\n✓ All pods found and ready for replay")
        return True
    
    def show_sample_annotations(self):
        """Show sample annotations for first pod"""
        print("\n" + "="*70)
        print("SAMPLE ANNOTATIONS (First Pod, Time 1)")
        print("="*70)
        
        if not self.config['pods']:
            print("No pods in configuration")
            return
        
        pod_info = self.config['pods'][0]
        metrics = pod_info['time_series'][0]
        
        print(f"\nPod: {pod_info['namespace']}/{pod_info['pod_name']}")
        print(f"\nAnnotations that will be set:")
        print(f"  {self.annotation_keys['cpu']:45s} = {metrics['cpu']}m")
        print(f"  {self.annotation_keys['memory']:45s} = {metrics['memory']}Mi")
        print(f"  {self.annotation_keys['power']:45s} = {metrics['power']}")
        print(f"  {self.annotation_keys['psi']:45s} = {metrics['psi']}")
        print(f"  {self.annotation_keys['timestamp']:45s} = <current-time>")


def main():
    parser = argparse.ArgumentParser(
        description='Optimized replay of time-series metrics to pod annotations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default mode (30 second intervals, 10 workers)
  python3 replay_metrics_optimized.py --config emulation_config.json
  
  # Fast replay with more workers
  python3 replay_metrics_optimized.py --config emulation_config.json --interval 5 --workers 20
  
  # Loop mode (continuous replay)
  python3 replay_metrics_optimized.py --config emulation_config.json --loop
  
  # Verify pods only
  python3 replay_metrics_optimized.py --config emulation_config.json --verify-only

Installation:
  pip install kubernetes --break-system-packages
        """
    )
    
    parser.add_argument('--config', required=True,
                       help='Path to emulation_config.json')
    parser.add_argument('--interval', type=int, default=30,
                       help='Seconds between time points (default: 30)')
    parser.add_argument('--loop', action='store_true',
                       help='Loop replay continuously (default: single run)')
    parser.add_argument('--workers', type=int, default=10,
                       help='Number of concurrent worker threads (default: 10)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify pods exist, do not start replay')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.interval < 1:
        print("Error: Interval must be at least 1 second")
        sys.exit(1)
    
    if args.workers < 1 or args.workers > 50:
        print("Error: Workers must be between 1 and 50")
        sys.exit(1)
    
    # Create replayer
    replayer = OptimizedMetricsReplayer(args.config, args.interval, args.loop, args.workers)
    
    # Load configuration
    replayer.load_config()
    
    # Initialize Kubernetes client
    replayer.init_k8s_client()
    
    # Show sample annotations
    replayer.show_sample_annotations()
    
    # Verify pods
    all_found = replayer.verify_pods()
    
    if args.verify_only:
        if all_found:
            print("\n✓ Verification successful")
            sys.exit(0)
        else:
            print("\n✗ Verification failed - some pods missing")
            sys.exit(1)
    
    if not all_found:
        response = input("\n⚠  Some pods are missing. Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(1)
    
    # Start replay
    print("\n" + "="*70)
    print("Press Ctrl+C to stop")
    print("="*70)
    time.sleep(2)
    
    replayer.run()


if __name__ == '__main__':
    main()
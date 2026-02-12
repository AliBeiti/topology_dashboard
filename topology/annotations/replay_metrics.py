#!/usr/bin/env python3
"""
Optimized Metrics Replayer with Rate Limiting
Uses Kubernetes Python client with controlled concurrency and connection reuse.
"""

import json
import sys
import time
import argparse
from typing import Dict, List
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Semaphore
import queue

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
except ImportError:
    print("Error: kubernetes Python client not installed")
    print("Install with: pip install kubernetes")
    sys.exit(1)


class RateLimitedMetricsReplayer:
    """Replay metrics with rate limiting and connection reuse"""
    
    def __init__(self, config_file: str, interval: int = 30, loop: bool = False, 
                 max_concurrent: int = 5, batch_size: int = 10):
        self.config_file = config_file
        self.interval = interval
        self.loop = loop
        self.max_concurrent = max_concurrent  # Max concurrent API calls
        self.batch_size = batch_size  # Pods per batch
        self.config = None
        self.annotation_keys = None
        self.k8s_client = None
        self.stats_lock = Lock()
        self.stats = {'success': 0, 'failed': 0}
        self.semaphore = Semaphore(max_concurrent)
        
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
            print(f"  - Namespaces: {self.config['metadata']['total_namespaces']}")
            print(f"  - Time points: {self.config['metadata']['time_points']}")
            print(f"  - Interval: {self.interval} seconds")
            print(f"  - Max concurrent: {self.max_concurrent}")
            print(f"  - Batch size: {self.batch_size}")
            print(f"  - Loop mode: {'enabled' if self.loop else 'disabled'}")
            
        except FileNotFoundError:
            print(f"Error: Config file not found: {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def init_k8s_client(self):
        """Initialize Kubernetes client with connection pooling"""
        try:
            import os
            
            # Check if we're in a K3s environment
            k3s_config = '/etc/rancher/k3s/k3s.yaml'
            if os.path.exists(k3s_config):
                if 'KUBECONFIG' not in os.environ:
                    os.environ['KUBECONFIG'] = k3s_config
            
            # Load config
            config.load_kube_config()
            
            # Create API client with connection pooling
            api_config = client.Configuration.get_default_copy()
            api_config.connection_pool_maxsize = self.max_concurrent * 2
            
            # Create client with custom config
            api_client = client.ApiClient(configuration=api_config)
            self.k8s_client = client.CoreV1Api(api_client=api_client)
            
            # Test connection
            self.k8s_client.list_namespace(limit=1)
            print("✓ Kubernetes API connection established")
            
        except Exception as e:
            print(f"Error: Failed to initialize Kubernetes client: {e}")
            sys.exit(1)
    
    def update_pod_batch(self, pod_batch: List[Dict], time_index: int) -> int:
        """Update a batch of pods with rate limiting"""
        
        # Acquire semaphore to limit concurrent operations
        self.semaphore.acquire()
        
        try:
            success_count = 0
            
            for pod_info in pod_batch:
                namespace = pod_info['namespace']
                pod_name = pod_info['pod_name']
                time_series = pod_info['time_series']
                
                # Check bounds
                if time_index >= len(time_series):
                    continue
                
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
                    # Apply patch
                    self.k8s_client.patch_namespaced_pod(
                        name=pod_name,
                        namespace=namespace,
                        body=patch
                    )
                    success_count += 1
                    
                except ApiException as e:
                    if e.status != 404:
                        pass  # Silently ignore errors to reduce logging overhead
                except Exception:
                    pass
            
            with self.stats_lock:
                self.stats['success'] += success_count
                self.stats['failed'] += len(pod_batch) - success_count
            
            return success_count
            
        finally:
            # Release semaphore
            self.semaphore.release()
    
    def replay_timepoint(self, time_index: int) -> Dict[str, int]:
        """Replay metrics for a specific time point with batching"""
        
        time_point = time_index + 1
        total_pods = len(self.config['pods'])
        
        # Reset stats
        with self.stats_lock:
            self.stats = {'success': 0, 'failed': 0}
        
        print(f"\n[Time {time_point}/{self.config['metadata']['time_points']}] ", end='', flush=True)
        
        start_time = time.time()
        
        # Split pods into batches
        pod_batches = []
        for i in range(0, len(self.config['pods']), self.batch_size):
            pod_batches.append(self.config['pods'][i:i + self.batch_size])
        
        # Process batches with limited concurrency
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {
                executor.submit(self.update_pod_batch, batch, time_index): batch
                for batch in pod_batches
            }
            
            # Wait for completion
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    pass  # Errors already tracked in update_pod_batch
        
        elapsed = time.time() - start_time
        
        with self.stats_lock:
            success = self.stats['success']
            failed = self.stats['failed']
        
        print(f"Updated {total_pods} pods in {elapsed:.2f}s (✓ {success}, ✗ {failed})")
        
        return self.stats.copy()
    
    def run(self):
        """Main replay loop"""
        print("\n" + "="*70)
        print("STARTING RATE-LIMITED REPLAY")
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
                    self.replay_timepoint(time_index)
                    
                    # Sleep until next time point
                    if time_index < total_time_points - 1:
                        time.sleep(self.interval)
                
                if not self.loop:
                    break
                
                print(f"\n⏳ Completed iteration {iteration}. Restarting in {self.interval}s...")
                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("REPLAY INTERRUPTED")
            print("="*70)
        
        print("\n" + "="*70)
        print("REPLAY COMPLETE")
        print("="*70)
        print(f"Total iterations: {iteration}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def verify_pods(self):
        """Quick pod verification"""
        print("\n" + "="*70)
        print("VERIFYING PODS")
        print("="*70)
        
        try:
            # Just check first pod of each namespace
            namespaces = set(p['namespace'] for p in self.config['pods'])
            
            for ns in namespaces:
                self.k8s_client.list_namespaced_pod(namespace=ns, limit=1)
            
            print(f"✓ All {len(namespaces)} namespaces accessible")
            return True
            
        except Exception as e:
            print(f"✗ Verification failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Rate-limited metrics replay with optimal CPU usage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Conservative (low CPU)
  python3 replay_metrics_final.py --config emulation_config.json --max-concurrent 3 --batch-size 15
  
  # Balanced (recommended)
  python3 replay_metrics_final.py --config emulation_config.json --max-concurrent 5 --batch-size 10
  
  # Fast interval with loop
  python3 replay_metrics_final.py --config emulation_config.json --interval 10 --loop --max-concurrent 5

Tuning:
  - max-concurrent: Number of simultaneous API calls (lower = less CPU)
  - batch-size: Pods per batch (higher = fewer threads, lower CPU)
  - Start with max-concurrent=3, batch-size=20 for lowest CPU
        """
    )
    
    parser.add_argument('--config', required=True,
                       help='Path to emulation_config.json')
    parser.add_argument('--interval', type=int, default=30,
                       help='Seconds between time points (default: 30)')
    parser.add_argument('--loop', action='store_true',
                       help='Loop replay continuously')
    parser.add_argument('--max-concurrent', type=int, default=5,
                       help='Max concurrent API calls (default: 5, lower for less CPU)')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Pods per batch (default: 10, higher for less CPU)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify connection')
    
    args = parser.parse_args()
    
    if args.interval < 1:
        print("Error: Interval must be at least 1 second")
        sys.exit(1)
    
    if args.max_concurrent < 1 or args.max_concurrent > 20:
        print("Error: max-concurrent must be between 1 and 20")
        sys.exit(1)
    
    if args.batch_size < 1 or args.batch_size > 50:
        print("Error: batch-size must be between 1 and 50")
        sys.exit(1)
    
    # Create replayer
    replayer = RateLimitedMetricsReplayer(
        args.config, 
        args.interval, 
        args.loop,
        args.max_concurrent,
        args.batch_size
    )
    
    replayer.load_config()
    replayer.init_k8s_client()
    
    if args.verify_only:
        replayer.verify_pods()
        sys.exit(0)
    
    replayer.verify_pods()
    
    print("\n" + "="*70)
    print("Press Ctrl+C to stop")
    print("="*70)
    time.sleep(2)
    
    replayer.run()


if __name__ == '__main__':
    main()
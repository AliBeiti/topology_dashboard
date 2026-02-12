# Kubernetes Workload Emulation & Topology Viewer

A system for emulating Kubernetes workloads and visualizing ContainerLab topologies with real-time metrics monitoring and Liqo-style virtual pod management.

## Overview

This project enables cost-effective research by creating digital twins of server workloads using KWOK and ContainerLab. It replays real metrics (CPU, memory, power, PSI) through emulated pods with an interactive web interface for monitoring and management.

## Prerequisites

- Ubuntu 24.04 (or similar Linux)
- Docker
- ContainerLab
- Python 3.8+
- Prometheus
```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip jq

# Install Python packages
cd flask-app
pip install -r requirements.txt
```

## Quick Start

### 1. Deploy ContainerLab Topology
```bash
cd topology
sudo clab deploy -t emulation.yaml
```

### 2. Start Prometheus
```bash
cd topology
prometheus --config.file=prometheus.yml --web.listen-address=:9091 &
cd ..
```

### 3. Setup Workload Emulation

<!-- 🔴 EDIT: Adjust NUM_NODES if different from 11 -->

Run this script to setup emulation on all nodes:
```bash
#!/bin/bash
# scripts/setup_emulation.sh

NUM_NODES=11

for i in $(seq 1 $NUM_NODES); do
    echo "Setting up serf${i}..."
    
    # Create KWOK resources
    docker exec clab-emulation-serf${i} bash -c \
        "cd /opt/annotations && python3 create_resources.py --config emulation_config.json"
    
    # Start metrics replay
    docker exec -d clab-emulation-serf${i} bash -c \
        "cd /opt/annotations && python3 replay_metrics.py --config emulation_config.json --interval 5 --loop"
    
    # Start metrics exporter
    docker exec -d clab-emulation-serf${i} bash -c \
        "cd /opt/annotations && python3 expose_metrics.py --config emulation_config.json --port 9090 --update-interval 2"
    
    echo "✓ serf${i} complete"
    sleep 2
done

echo "Waiting for services to start..."
sleep 30

# Verify Prometheus targets
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="kwok-emulation") | {instance: .labels.instance, health: .health}'
```

Make executable and run:
```bash
chmod +x scripts/setup_emulation.sh
./scripts/setup_emulation.sh
```

### 4. Start Web Application
```bash
cd flask-app
python3 app.py
```

Access UI at: **http://localhost:8080**

## Features

- **Topology Visualization**: Interactive network graph with real-time node status
- **Metrics Monitoring**: View CPU, memory, PSI, and power metrics per pod/node
- **Liqo Connections**: Create virtual connections between K3s clusters
- **Virtual Pods**: Simulate cross-cluster pod offloading with animations
- **Time-series Comparison**: Side-by-side emulated vs. real metrics

## Usage

### View Metrics
1. Click any serf node to see cluster details
2. Click metric buttons (📊 CPU, 💾 Memory, ⚡ PSI, 🔋 Power)
3. Select time range (5min, 15min, 1h, 2h)

### Create Liqo Connection
1. Right-click source node → **"Liqo Connect"**
2. Click destination node
3. Green dashed line appears

### Create Virtual Pod
1. Right-click source node → **"Create Pod"**
2. Click destination node (must have Liqo connection)
3. Select workload template
4. Watch pod transfer animation

### Manage Virtual Pods
- View all virtual pods in sidebar
- Click ℹ️ to see details
- Click 🗑️ to delete

## Configuration

<!-- 🔴 EDIT: Adjust these files if needed -->

**Flask App** (`flask-app/config.yaml`):
```yaml
containerlab:
  topology_file: "../topology/emulation.yaml"

monitoring:
  central_prometheus:
    host: "localhost"
    port: 9091

server:
  host: "0.0.0.0"
  port: 8080
```

**Prometheus** (`topology/prometheus.yml`):
- Edit `targets` list to match your number of serf nodes

## Project Structure
```
.
├── topology/
│   ├── emulation.yaml          # ContainerLab topology
│   └── prometheus.yml         # Prometheus config
├── flask-app/
│   ├── app.py                 # Flask application
│   ├── config.yaml            # App config
│   ├── requirements.txt       # Python deps
│   ├── static/                # UI files
│   ├── scripts/               # Virtual pod manager
│   └── workload_templates/    # Workload profiles
└── scripts/
    └── setup_emulation.sh     # Emulation setup
```

## Cleanup
```bash
# Stop emulation on all nodes
for i in {1..11}; do
    docker exec clab-emulation-serf${i} pkill -f replay_metrics.py
    docker exec clab-emulation-serf${i} pkill -f expose_metrics.py
done

# Destroy topology
cd topology
sudo clab destroy -t emulation.yaml
```

## Troubleshooting

**No metrics appearing?**
```bash
# Check if exporters are running
docker exec clab-emulation-serf1 ps aux | grep expose_metrics

# Test exporter directly
docker exec clab-emulation-serf1 curl http://localhost:9090/metrics
```

**Topology not loading?**
```bash
# Verify ContainerLab is running
sudo clab inspect

# Check Flask app health
curl http://localhost:8080/api/health
```

## Credits

<!-- 🔴 EDIT: Add your details -->

**Project**: EMULATE - Energy-aware P2P Resource Marketplace for Kubernetes  
**Institution**: FH Dortmund  
**Contact**: ali.beitiaydenlou@fh-dortmund.de 
**Funded by**: IPCEI-CIS and BMWE

## License

<!-- 🔴 EDIT: Add your license -->
<!-- [Your License] -->
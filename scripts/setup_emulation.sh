# Complete setup loop for all serf containers (no copying needed)
for i in {1..11}; do
    echo "========================================="
    echo "Setting up serf${i}..."
    echo "========================================="
    
    # 1. Create KWOK resources
    docker exec clab-emulation-serf${i} bash -c "cd /opt/annotations && python3 create_resources.py --config emulation_config.json"
    
    # 2. Start replay script in background
    docker exec -d clab-emulation-serf${i} bash -c "cd /opt/annotations && python3 replay_metrics.py --config emulation_config.json --interval 5 --loop --max-concurrent 3 --batch-size 20"
    
    # 3. Start exporter in background
    docker exec -d clab-emulation-serf${i} bash -c "cd /opt/annotations && python3 expose_metrics.py --config emulation_config.json --port 9090 --update-interval 2"
    
    echo "✓ serf${i} setup complete"
    sleep 2
done

echo ""
echo "========================================="
echo "All nodes configured!"
echo "========================================="
echo "Waiting 30 seconds for services to start..."
sleep 30

# Verify all targets are up in Prometheus
echo "Checking Prometheus targets..."
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="kwok-emulation") | {instance: .labels.instance, health: .health}'
#!/bin/bash

echo "=========================================="
echo "Deploying 10-node topology with 2 routers"
echo "=========================================="

echo "[1/4] Deploying containers..."
sudo clab deploy -t emulation.yml

echo ""
echo "[2/4] Waiting for containers (60 seconds)..."
sleep 60

echo ""
echo "[3/4] Configuring client IPs and routes..."

# Switch A: serf1–serf10 (10.1.0.x)
for i in {1..10}; do
  docker exec clab-extended50-serf${i} ip addr add 10.1.0.${i}/24 dev eth1 2>/dev/null || true
  docker exec clab-extended50-serf${i} ip link set eth1 up
  docker exec clab-extended50-serf${i} ip route add 10.0.0.0/8 via 10.1.0.254 dev eth1 2>/dev/null || true
done

# Switch B: serf11–serf20 (10.2.0.x)
for i in {11..20}; do
  j=$((i-10))
  docker exec clab-extended50-serf${i} ip addr add 10.2.0.${j}/24 dev eth1 2>/dev/null || true
  docker exec clab-extended50-serf${i} ip link set eth1 up
  docker exec clab-extended50-serf${i} ip route add 10.0.0.0/8 via 10.2.0.254 dev eth1 2>/dev/null || true
done

# Switch C: serf21–serf30 (10.3.0.x)
for i in {21..30}; do
  j=$((i-20))
  docker exec clab-extended50-serf${i} ip addr add 10.3.0.${j}/24 dev eth1 2>/dev/null || true
  docker exec clab-extended50-serf${i} ip link set eth1 up
  docker exec clab-extended50-serf${i} ip route add 10.0.0.0/8 via 10.3.0.254 dev eth1 2>/dev/null || true
done

# Switch D: serf31–serf40 (10.4.0.x)
for i in {31..40}; do
  j=$((i-30))
  docker exec clab-extended50-serf${i} ip addr add 10.4.0.${j}/24 dev eth1 2>/dev/null || true
  docker exec clab-extended50-serf${i} ip link set eth1 up
  docker exec clab-extended50-serf${i} ip route add 10.0.0.0/8 via 10.4.0.254 dev eth1 2>/dev/null || true
done

# Switch E: serf41–serf50 (10.5.0.x)
for i in {41..50}; do
  j=$((i-40))
  docker exec clab-extended50-serf${i} ip addr add 10.5.0.${j}/24 dev eth1 2>/dev/null || true
  docker exec clab-extended50-serf${i} ip link set eth1 up
  docker exec clab-extended50-serf${i} ip route add 10.0.0.0/8 via 10.5.0.254 dev eth1 2>/dev/null || true
done

echo ""
echo "[4/4] Starting FRR on routers..."
docker exec clab-extended50-R1 sysctl -w net.ipv4.ip_forward=1
docker exec clab-extended50-R2 sysctl -w net.ipv4.ip_forward=1
docker exec clab-extended50-R1 /usr/lib/frr/frrinit.sh start
docker exec clab-extended50-R2 /usr/lib/frr/frrinit.sh start

sleep 10

echo "Done!"

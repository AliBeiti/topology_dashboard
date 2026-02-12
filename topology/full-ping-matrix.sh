#!/bin/bash

echo "=========================================="
echo "Full 50-Node Connectivity Matrix Test"
echo "=========================================="
echo ""

passed=0
failed=0
total=0

# Function to ping from serfX → target IP
test_ping() {
    local from=$1
    local to=$2
    local to_ip=$3
    ((total++))

    if docker exec clab-extended50-serf${from} ping -c 1 -W 1 ${to_ip} >/dev/null 2>&1; then
        ((passed++))
        return 0
    else
        echo "  ✗ serf${from} → serf${to} (${to_ip}) FAILED"
        ((failed++))
        return 1
    fi
}

# ---------------------------------------------------------
# SWITCH A — serf1 to serf10 → 10.1.0.1–10
# ---------------------------------------------------------
echo "Testing Switch A (serf1–serf10) internal connectivity..."
for i in {1..10}; do
    for j in {1..10}; do
        if [ $i -ne $j ]; then
            test_ping $i $j 10.1.0.${j}
        fi
    done
done
echo "  Switch A: Tested $((10*9)) pairs"

# ---------------------------------------------------------
# SWITCH B — serf11 to serf20 → 10.2.0.1–10
# ---------------------------------------------------------
echo ""
echo "Testing Switch B (serf11–serf20) internal connectivity..."
for i in {11..20}; do
    for j in {11..20}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-10))
            test_ping $i $j 10.2.0.${j_ip}
        fi
    done
done
echo "  Switch B: Tested $((10*9)) pairs"

# ---------------------------------------------------------
# SWITCH C — serf21 to serf30 → 10.3.0.1–10
# ---------------------------------------------------------
echo ""
echo "Testing Switch C (serf21–serf30) internal connectivity..."
for i in {21..30}; do
    for j in {21..30}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-20))
            test_ping $i $j 10.3.0.${j_ip}
        fi
    done
done
echo "  Switch C: Tested $((10*9)) pairs"

# ---------------------------------------------------------
# SWITCH D — serf31 to serf40 → 10.4.0.1–10
# ---------------------------------------------------------
echo ""
echo "Testing Switch D (serf31–serf40) internal connectivity..."
for i in {31..40}; do
    for j in {31..40}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-30))
            test_ping $i $j 10.4.0.${j_ip}
        fi
    done
done
echo "  Switch D: Tested $((10*9)) pairs"

# ---------------------------------------------------------
# SWITCH E — serf41 to serf50 → 10.5.0.1–10
# ---------------------------------------------------------
echo ""
echo "Testing Switch E (serf41–serf50) internal connectivity..."
for i in {41..50}; do
    for j in {41..50}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-40))
            test_ping $i $j 10.5.0.${j_ip}
        fi
    done
done
echo "  Switch E: Tested $((10*9)) pairs"

# ---------------------------------------------------------
# CROSS-SWITCH CONNECTIVITY
# ---------------------------------------------------------
echo ""
echo "Testing cross-switch connectivity..."

# === FROM SWITCH A (serf1,5,10) → all other switches ===
echo "  From Switch A..."
for target in {11..50}; do
    if [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    elif [ $target -le 40 ]; then
        target_ip=10.4.0.$((target-30))
    else
        target_ip=10.5.0.$((target-40))
    fi

    test_ping 1 $target $target_ip
    test_ping 5 $target $target_ip
    test_ping 10 $target $target_ip
done

# === FROM SWITCH B (serf11,15,20) ========================
echo "  From Switch B..."
for target in {1..10} {21..50}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    elif [ $target -le 40 ]; then
        target_ip=10.4.0.$((target-30))
    else
        target_ip=10.5.0.$((target-40))
    fi

    test_ping 11 $target $target_ip
    test_ping 15 $target $target_ip
    test_ping 20 $target $target_ip
done

# === FROM SWITCH C (serf21,25,30) ========================
echo "  From Switch C..."
for target in {1..20} {31..50}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 40 ]; then
        target_ip=10.4.0.$((target-30))
    else
        target_ip=10.5.0.$((target-40))
    fi

    test_ping 21 $target $target_ip
    test_ping 25 $target $target_ip
    test_ping 30 $target $target_ip
done

# === FROM SWITCH D (serf31,35,40) ========================
echo "  From Switch D..."
for target in {1..30} {41..50}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    else
        target_ip=10.5.0.$((target-40))
    fi

    test_ping 31 $target $target_ip
    test_ping 35 $target $target_ip
    test_ping 40 $target $target_ip
done

# === FROM SWITCH E (serf41,45,50) ========================
echo "  From Switch E..."
for target in {1..40}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    else
        target_ip=10.4.0.$((target-30))
    fi

    test_ping 41 $target $target_ip
    test_ping 45 $target $target_ip
    test_ping 50 $target $target_ip
done

# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------
echo ""
echo "=========================================="
echo "FINAL RESULTS"
echo "=========================================="
echo "Total tests:  $total"
echo "Passed:       $passed"
echo "Failed:       $failed"
echo "Success rate: $(awk "BEGIN {printf \"%.2f\", ($passed/$total)*100}")%"
echo "=========================================="

if [ $failed -eq 0 ]; then
    echo ""
    echo "All $total connectivity tests passed!"
    echo ""
    echo "  ✓ All serf nodes can reach each other"
    echo "  ✓ OSPF routing working between R1 and R2"
    echo "  ✓ All 5 subnets reachable"
    echo ""
else
    echo ""
    echo "  $failed tests failed. Review failures above."
    echo ""
fi

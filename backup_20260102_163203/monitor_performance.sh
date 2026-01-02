#!/bin/bash
# Performance monitoring script for Jetson

echo "========================================="
echo "  Edge Video Agent - Performance Monitor"
echo "========================================="
echo ""

# Check if running on Jetson
if [ -f /etc/nv_tegra_release ]; then
    echo "Platform: NVIDIA Jetson"
    cat /etc/nv_tegra_release | head -n 1
    echo ""
    
    echo "Current Power Mode:"
    sudo nvpmodel -q 2>/dev/null || echo "nvpmodel not available"
    echo ""
    
    echo "GPU/CPU Stats (5 samples):"
    echo "-------------------------------------------"
    sudo tegrastats --interval 1000 --stop 5 2>/dev/null || {
        echo "tegrastats not available"
        echo "Alternative: Install jetson-stats (sudo pip3 install jetson-stats)"
        echo "Then run: sudo jtop"
    }
    echo ""
else
    echo "Platform: Not a Jetson device"
    echo ""
fi

echo "Python Process Stats:"
echo "-------------------------------------------"
ps aux | head -n 1
ps aux | grep python | grep -v grep | grep -v "ps aux"
echo ""

echo "Memory Usage:"
echo "-------------------------------------------"
free -h
echo ""

echo "Disk Usage:"
echo "-------------------------------------------"
df -h | grep -E "Filesystem|/dev/mmcblk0p1|/dev/nvme"
echo ""

echo "Network Connections (RTSP):"
echo "-------------------------------------------"
netstat -tn 2>/dev/null | grep :554 || echo "No RTSP connections found"
echo ""

echo "Application Logs (last 10 lines):"
echo "-------------------------------------------"
if [ -d "logs" ]; then
    for log in logs/*.log; do
        if [ -f "$log" ]; then
            echo "=== $(basename $log) ==="
            tail -n 10 "$log"
            echo ""
        fi
    done
else
    echo "No log directory found"
fi

echo "========================================="
echo "  For continuous monitoring, use:"
echo "    sudo tegrastats"
echo "  or"
echo "    sudo jtop  (install: sudo pip3 install jetson-stats)"
echo "========================================="

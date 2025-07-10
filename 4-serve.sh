#!/bin/bash

echo "=== Starting Firecracker Terminal Service ==="

# Check if required files exist
if [ ! -f "./bin/vmlinux" ]; then
    echo "Error: vmlinux not found. Please run 2-setup.sh first."
    exit 1
fi

if [ ! -f "./bin/rootfs.img" ]; then
    echo "Error: rootfs.img not found. Please run 2-setup.sh first."
    exit 1
fi

if [ ! -f "./firecracker-terminal.py" ]; then
    echo "Error: firecracker-terminal.py not found."
    exit 1
fi

# Check if network is set up
if ! ip link show ftap0 > /dev/null 2>&1; then
    echo "Warning: ftap0 interface not found. Please run 2-setup.sh to set up network."
    exit 1
fi

# Start the Python terminal service
echo "Starting Firecracker Terminal Service..."
echo "This will start the web-based terminal service."
echo "Press Ctrl+C to stop."
echo ""

# Allow passing email restrictions as argument
if [ -n "$1" ]; then
    echo "Starting with email restrictions: $1"
    python3 firecracker-terminal.py --authorized-emails="$1"
else
    echo "Starting without email restrictions (all authenticated users allowed)"
    python3 firecracker-terminal.py
fi

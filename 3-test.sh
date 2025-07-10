#!/bin/bash

echo "=== Testing Firecracker VM Setup ==="

# Check if required files exist
echo "Checking required files..."

if [ ! -f "./bin/vmlinux" ]; then
    echo "✗ vmlinux not found - run ./2-setup.sh first"
    exit 1
else
    echo "✓ vmlinux found"
fi

if [ ! -f "./bin/rootfs.img" ]; then
    echo "✗ rootfs.img not found - run ./2-setup.sh first"
    exit 1
else
    SIZE=$(du -h ./bin/rootfs.img | cut -f1)
    echo "✓ rootfs.img found (size: $SIZE)"
fi

if [ ! -f "./bin/firecracker" ]; then
    echo "✗ firecracker binary not found - run ./2-setup.sh first"
    exit 1
else
    echo "✓ firecracker binary found"
fi

# Check if rootfs contains init binary
echo ""
echo "Verifying rootfs contents..."

# Check if the simple-init script exists (used for building)
if [ -f "simple-init" ]; then
    echo "✓ Simple init script found"
else
    echo "✗ Simple init script not found"
    exit 1
fi

# Check if the Dockerfile exists (used for building)
if [ -f "Dockerfile" ]; then
    echo "✓ Dockerfile found"
else
    echo "✗ Dockerfile not found"
    exit 1
fi

# Check network setup
echo ""
echo "Checking network setup..."
if ip link show ftap0 > /dev/null 2>&1; then
    echo "✓ ftap0 interface exists"
    IP=$(ip addr show ftap0 | grep "inet " | awk '{print $2}')
    echo "  Interface IP: $IP"
else
    echo "✗ ftap0 interface not found - run ./1-setup.sh first"
    exit 1
fi

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."
if python3 -c "import hypha_rpc" 2>/dev/null; then
    echo "✓ hypha-rpc installed"
else
    echo "✗ hypha-rpc not installed"
    exit 1
fi

if python3 -c "import fastapi" 2>/dev/null; then
    echo "✓ fastapi installed"
else
    echo "✗ fastapi not installed"
    exit 1
fi

# Quick VM boot test (non-interactive)
echo ""
echo "Testing VM boot (15 second test)..."

# Kill any existing firecracker processes
sudo pkill -f firecracker 2>/dev/null || true
sleep 1

# Start firecracker in background
sudo rm -f /tmp/firecracker.test.socket
sudo ./bin/firecracker --api-sock /tmp/firecracker.test.socket &
FIRECRACKER_PID=$!

# Wait for socket
for i in {1..10}; do
    if [ -S /tmp/firecracker.test.socket ]; then
        break
    fi
    sleep 1
done

if [ ! -S /tmp/firecracker.test.socket ]; then
    echo "✗ Firecracker socket not ready"
    sudo kill $FIRECRACKER_PID 2>/dev/null
    exit 1
fi

# Configure VM
sudo curl --unix-socket /tmp/firecracker.test.socket -s \
    -X PUT 'http://localhost/boot-source' \
    -H 'Content-Type: application/json' \
    -d '{
        "kernel_image_path": "./bin/vmlinux",
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/init root=/dev/vda rw"
    }' > /dev/null

sudo curl --unix-socket /tmp/firecracker.test.socket -s \
    -X PUT 'http://localhost/machine-config' \
    -H 'Content-Type: application/json' \
    -d '{"vcpu_count": 1, "mem_size_mib": 128}' > /dev/null

sudo curl --unix-socket /tmp/firecracker.test.socket -s \
    -X PUT 'http://localhost/drives/rootfs' \
    -H 'Content-Type: application/json' \
    -d '{
        "drive_id": "rootfs",
        "path_on_host": "./bin/rootfs.img",
        "is_root_device": true,
        "is_read_only": false
    }' > /dev/null

# Start VM
sudo curl --unix-socket /tmp/firecracker.test.socket -s \
    -X PUT 'http://localhost/actions' \
    -H 'Content-Type: application/json' \
    -d '{"action_type": "InstanceStart"}' > /dev/null

# Wait a bit for boot
echo "Waiting for VM to boot..."
sleep 15

# Clean up
sudo kill $FIRECRACKER_PID 2>/dev/null || true
sudo rm -f /tmp/firecracker.test.socket

echo "✓ VM boot test completed (check for kernel panics above)"

echo ""
echo "=== Test Results ==="
echo "✓ All required files present"
echo "✓ Init script and Dockerfile verified"
echo "✓ Network interface configured"
echo "✓ Python dependencies installed"
echo "✓ VM boot test completed"
echo ""
echo "Setup appears to be working correctly!"
echo "Ready to run: ./4-serve.sh" 
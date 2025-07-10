#!/bin/bash

echo "=== Manual Firecracker VM Start (for testing) ==="

# Check if required files exist
if [ ! -f "./bin/vmlinux" ]; then
    echo "Error: vmlinux not found. Please run 2-setup.sh first."
    exit 1
fi

if [ ! -f "./bin/rootfs.img" ]; then
    echo "Error: rootfs.img not found. Please run 2-setup.sh first."
    exit 1
fi

if [ ! -f "./bin/firecracker" ]; then
    echo "Error: firecracker binary not found in bin. Please run 2-setup.sh first."
    exit 1
fi

# Check if network is set up
if ! ip link show ftap0 > /dev/null 2>&1; then
    echo "Warning: ftap0 interface not found. Please run 2-setup.sh to set up network."
    exit 1
fi

# Start firecracker in the background
echo "Starting firecracker process..."

# Remove any existing socket
sudo rm -f /tmp/firecracker.socket

# Start firecracker
sudo ./bin/firecracker --api-sock /tmp/firecracker.socket &
FIRECRACKER_PID=$!

# Wait for socket to be ready
echo "Waiting for firecracker to be ready..."
for i in {1..10}; do
    if [ -S /tmp/firecracker.socket ]; then
        echo "Firecracker ready!"
        break
    fi
    sleep 1
done

if [ ! -S /tmp/firecracker.socket ]; then
    echo "Error: Firecracker socket not ready"
    sudo kill $FIRECRACKER_PID 2>/dev/null
    exit 1
fi

# Configure and boot the VM
echo "Configuring and booting VM..."

# Configure boot source
echo "Setting boot source..."
sudo curl --unix-socket /tmp/firecracker.socket -i \
    -X PUT 'http://localhost/boot-source' \
    -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "kernel_image_path": "./bin/vmlinux",
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/init root=/dev/vda rw ip=172.16.0.2::172.16.0.1:255.255.255.0::eth0:off"
    }'

# Configure machine
echo "Setting machine config..."
sudo curl --unix-socket /tmp/firecracker.socket -i \
    -X PUT 'http://localhost/machine-config' \
    -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "vcpu_count": 2,
        "mem_size_mib": 256
    }'

# Configure network
echo "Setting network config..."
sudo curl --unix-socket /tmp/firecracker.socket -i \
    -X PUT 'http://localhost/network-interfaces/eth0' \
    -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "iface_id": "eth0",
        "host_dev_name": "ftap0"
    }'

# Configure drive
echo "Setting drive config..."
sudo curl --unix-socket /tmp/firecracker.socket -i \
    -X PUT 'http://localhost/drives/rootfs' \
    -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "drive_id": "rootfs",
        "path_on_host": "./bin/rootfs.img",
        "is_root_device": true,
        "is_read_only": false
    }'

# Start the VM
echo "Starting VM..."
sudo curl --unix-socket /tmp/firecracker.socket -i \
    -X PUT 'http://localhost/actions' \
    -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "action_type": "InstanceStart"
    }'

echo ""
echo "VM is starting! You should see boot messages above."
echo "VM IP: 172.16.0.2"
echo "Host IP: 172.16.0.1"
echo ""
echo "To connect to the VM console, the output is already shown above."
echo "To stop the VM, press Ctrl+C or run: sudo kill $FIRECRACKER_PID"
echo ""
echo "Firecracker process PID: $FIRECRACKER_PID"

# Keep the script running so you can see VM output
wait $FIRECRACKER_PID

#!/bin/bash

echo "=== Setting up Firecracker environment ==="

# Create directories
echo "Creating directories..."
mkdir -p ./bin

# Download and setup Firecracker binary
echo "Downloading Firecracker binary..."
cd ./bin
curl -fsSL -o ./firecracker.tgz https://github.com/firecracker-microvm/firecracker/releases/download/v1.12.1/firecracker-v1.12.1-x86_64.tgz
tar -xzf firecracker.tgz
cp release-v1.12.1-x86_64/firecracker-v1.12.1-x86_64 firecracker
rm -rf ./release-v1.12.1-x86_64
chmod +x ./firecracker

# Download sample kernel and rootfs for testing
echo "Downloading sample kernel and rootfs..."
curl -fsSL -o ./hello-vmlinux.bin https://s3.amazonaws.com/spec.ccfc.min/img/hello/kernel/hello-vmlinux.bin
curl -fsSL -o ./hello-rootfs.ext4 https://s3.amazonaws.com/spec.ccfc.min/img/hello/fsfiles/hello-rootfs.ext4

cd ../

# Download the proper kernel for the bin directory
echo "Downloading kernel..."
cd ./bin
curl -o vmlinux -S -L "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64/vmlinux-5.10.223"

# Build the rootfs using the modular build script
echo "Building rootfs from Docker with custom init binary..."
cd ../
if [ -f "./build-rootfs.sh" ]; then
    echo "Using modular build-rootfs.sh script..."
    ./build-rootfs.sh -d ./Dockerfile -o ./bin/rootfs.img -t alexellis2/custom-init -s 5G
else
    echo "ERROR: build-rootfs.sh not found! Please run this script from the hypha-terminal directory."
    exit 1
fi

# Verify final rootfs.img file
echo "Verifying rootfs.img file..."
if [ -f ./bin/rootfs.img ]; then
    SIZE=$(du -h ./bin/rootfs.img | cut -f1)
    echo "✓ rootfs.img created successfully (size: $SIZE)"
else
    echo "ERROR: rootfs.img not created!"
    exit 1
fi

# Network setup for firecracker-terminal.py
echo "Setting up network for Firecracker VMs..."

# Kill any existing firecracker processes to avoid conflicts
pkill -f "firecracker.*api-sock" 2>/dev/null || true

# Remove existing ftap0 interface if it exists
sudo ip link set ftap0 down 2>/dev/null || true
sudo ip link delete ftap0 2>/dev/null || true

# Create the tap interface and configure it
sudo ip tuntap add dev ftap0 mode tap user $USER
sudo ip addr add 172.16.0.1/24 dev ftap0
sudo ip link set ftap0 up

# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Get the main network interface
IFNAME=$(ip route | grep default | awk '{print $5}' | head -n1)
if [ -z "$IFNAME" ]; then
    echo "Warning: Could not detect main network interface, defaulting to eth0"
    IFNAME="eth0"
fi
echo "Using network interface: $IFNAME"

# Add masquerading rules (only if not already exists)
if ! sudo iptables -t nat -C POSTROUTING -o $IFNAME -j MASQUERADE 2>/dev/null; then
    echo "Adding masquerading rules..."
    sudo iptables -t nat -A POSTROUTING -o $IFNAME -j MASQUERADE
    sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i ftap0 -o $IFNAME -j ACCEPT
else
    echo "Masquerading rules already exist"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --user hypha-rpc==0.20.39 fastapi uvicorn

echo "=== Setup complete! ==="
echo ""
echo "✓ Firecracker binary: ./bin/firecracker"
echo "✓ VM kernel: ./bin/vmlinux"
echo "✓ VM rootfs: ./bin/rootfs.img (with init binary)"
echo "✓ Network: ftap0 interface (172.16.0.1/24)"
echo "✓ Python deps: hypha-rpc, fastapi, uvicorn"
echo ""
echo "VM Configuration:"
echo "- Host IP: 172.16.0.1"
echo "- VM IP range: 172.16.0.2+"
echo "- VM specs: 2 vCPUs, 256MB RAM, 5GB disk"
echo "- OS: Alpine Linux with data science environment"
echo "- User: scientist (with Python venv activated)"
echo ""
echo "Ready to run: ./4-serve.sh"
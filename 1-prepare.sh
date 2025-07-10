#!/bin/bash

echo "=== Preparing host machine for Firecracker ==="

# Check if virtualization is supported
echo "Checking CPU virtualization support..."
if [ $(grep -cw vmx /proc/cpuinfo) -eq 0 ]; then
    echo "ERROR: CPU virtualization not supported or enabled"
    exit 1
fi
echo "✓ CPU virtualization supported"

# Update system and install required packages
echo "Installing required packages..."
sudo apt-get update && sudo apt-get install -y \
    qemu-kvm \
    docker.io \
    curl \
    git \
    build-essential \
    golang-go \
    iptables

# Setup KVM permissions
echo "Setting up KVM permissions..."
sudo setfacl -m u:${USER}:rw /dev/kvm

# Add user to docker group
echo "Adding user to docker group..."
sudo usermod -aG docker $USER

# Test KVM access
if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    echo "✓ KVM access: OK"
else
    echo "✗ KVM access: FAIL"
    exit 1
fi

# Start docker service
echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Test docker access
if docker ps > /dev/null 2>&1; then
    echo "✓ Docker access: OK"
else
    echo "✗ Docker access: FAIL - you may need to log out and back in"
    echo "  Or run: newgrp docker"
fi

echo "=== Host preparation complete! ==="
echo "Note: If Docker access failed, please log out and back in, then continue with 1-setup.sh"

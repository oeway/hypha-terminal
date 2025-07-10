#!/bin/bash

# Cloud Hypervisor VM Terminal Complete Setup Script
# This script sets up everything needed for the Cloud Hypervisor VM Terminal

set -e  # Exit on any error

echo "🔥 Cloud Hypervisor VM Terminal Setup"
echo "====================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    error "This script should not be run as root. Please run as regular user."
fi

# Check if we have sudo access
if ! sudo -v; then
    error "This script requires sudo access. Please ensure you can run sudo commands."
fi

# Check if we're in the right directory
if [ ! -f "cloud-hypervisor-terminal.py" ]; then
    error "Please run this script from the cloud-hypervisor directory"
fi

info "Starting Cloud Hypervisor VM Terminal setup..."
echo ""

# Step 1: Install system dependencies
info "Step 1: Installing system dependencies..."
sudo apt update
sudo apt install -y \
    build-essential \
    flex \
    bison \
    libssl-dev \
    libelf-dev \
    qemu-utils \
    wget \
    git \
    python3-pip \
    iptables \
    net-tools \
    bridge-utils || error "Failed to install system dependencies"

success "System dependencies installed"

# Step 2: Create bin directory
info "Step 2: Setting up directory structure..."
mkdir -p bin
success "Directory structure created"

# Step 3: Download Cloud Hypervisor binary
info "Step 3: Installing Cloud Hypervisor binary..."
if [ ! -f "bin/cloud-hypervisor" ]; then
    wget -O bin/cloud-hypervisor https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v42.0/cloud-hypervisor-static
    chmod +x bin/cloud-hypervisor
    success "Cloud Hypervisor binary downloaded"
else
    success "Cloud Hypervisor binary already exists"
fi

# Step 4: Build optimized kernel
info "Step 4: Building Cloud Hypervisor optimized kernel..."
if [ ! -f "bin/vmlinux-ch" ]; then
    if [ ! -d "linux-cloud-hypervisor" ]; then
        git clone --depth 1 https://github.com/cloud-hypervisor/linux.git -b ch-6.12.8 linux-cloud-hypervisor
    fi
    
    cd linux-cloud-hypervisor
    make ch_defconfig
    KCFLAGS="-Wa,-mx86-used-note=no" make bzImage -j$(nproc)
    cp arch/x86/boot/compressed/vmlinux.bin ../bin/vmlinux-ch
    cd ..
    success "Cloud Hypervisor kernel built successfully"
else
    success "Cloud Hypervisor kernel already exists"
fi

# Step 5: Download Ubuntu cloud image
info "Step 5: Setting up Ubuntu cloud image..."
if [ ! -f "bin/ubuntu-rootfs.img" ]; then
    if [ ! -f "ubuntu-cloud-focal.img" ]; then
        wget -O ubuntu-cloud-focal.img https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img
    fi
    
    qemu-img convert -f qcow2 -O raw ubuntu-cloud-focal.img bin/ubuntu-rootfs.img
    success "Ubuntu cloud image prepared"
else
    success "Ubuntu cloud image already exists"
fi

# Step 6: Install Python dependencies
info "Step 6: Installing Python dependencies..."
pip3 install --user aiohttp aiofiles websockets || error "Failed to install Python dependencies"
success "Python dependencies installed"

# Step 7: Set up TAP networking
info "Step 7: Setting up TAP networking..."
# Create TAP interface if it doesn't exist
if ! ip link show ch-tap0 &> /dev/null; then
    sudo ip tuntap add dev ch-tap0 mode tap
    sudo ip addr add 172.20.0.1/24 dev ch-tap0
    sudo ip link set ch-tap0 up
    success "TAP interface created"
else
    success "TAP interface already exists"
fi

# Enable IP forwarding
sudo sysctl net.ipv4.ip_forward=1 > /dev/null

# Set up NAT rules
if ! sudo iptables -t nat -C POSTROUTING -s 172.20.0.0/24 -j MASQUERADE 2>/dev/null; then
    sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/24 -j MASQUERADE
    success "NAT rules configured"
else
    success "NAT rules already configured"
fi

# Step 8: Set permissions
info "Step 8: Setting file permissions..."
chmod +x *.sh
chmod +x bin/cloud-hypervisor
success "File permissions set"

# Step 9: Verify setup
info "Step 9: Verifying setup..."
echo ""
echo "📋 Setup Verification:"
echo "---------------------"

# Check files
if [ -f "bin/cloud-hypervisor" ]; then
    echo "✅ Cloud Hypervisor binary: $(ls -lh bin/cloud-hypervisor | awk '{print $5}')"
else
    echo "❌ Cloud Hypervisor binary: Missing"
fi

if [ -f "bin/vmlinux-ch" ]; then
    echo "✅ Cloud Hypervisor kernel: $(ls -lh bin/vmlinux-ch | awk '{print $5}')"
else
    echo "❌ Cloud Hypervisor kernel: Missing"
fi

if [ -f "bin/ubuntu-rootfs.img" ]; then
    echo "✅ Ubuntu rootfs: $(ls -lh bin/ubuntu-rootfs.img | awk '{print $5}')"
else
    echo "❌ Ubuntu rootfs: Missing"
fi

# Check network
if ip link show ch-tap0 &> /dev/null; then
    echo "✅ TAP interface: ch-tap0 configured"
else
    echo "❌ TAP interface: Not configured"
fi

# Check Python dependencies
if python3 -c "import aiohttp, aiofiles, websockets" 2>/dev/null; then
    echo "✅ Python dependencies: Installed"
else
    echo "❌ Python dependencies: Missing"
fi

echo ""
success "Setup completed successfully!"
echo ""
echo "🚀 Next Steps:"
echo "1. Run './run-service.sh' to start the service"
echo "2. Or run 'python3 test-vm-simple.py' to test VM functionality"
echo "3. Check the README.md for detailed usage instructions"
echo ""
echo "📊 System Status:"
echo "- VM Terminal: Ready"
echo "- Network: TAP interface (172.20.0.1/24)"
echo "- Kernel: Cloud Hypervisor optimized"
echo "- Rootfs: Ubuntu 20.04 LTS"
echo "" 
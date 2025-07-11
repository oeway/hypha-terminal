#!/bin/bash

# Cloud Hypervisor Terminal Service Launcher
echo "🔥 Starting Cloud Hypervisor Terminal Service..."
echo "================================================"

# Check if we're in the right directory
if [ ! -f "cloud-hypervisor-terminal.py" ]; then
    echo "❌ Error: Please run this script from the cloud-hypervisor directory"
    exit 1
fi

# Check if setup has been completed
if [ ! -f "bin/cloud-hypervisor" ] || [ ! -f "bin/vmlinux-ch" ] || [ ! -f "bin/ubuntu-rootfs.img" ]; then
    echo "❌ Error: Setup incomplete. Please run ./setup-complete.sh first"
    echo ""
    echo "Missing files:"
    [ ! -f "bin/cloud-hypervisor" ] && echo "  - bin/cloud-hypervisor"
    [ ! -f "bin/vmlinux-ch" ] && echo "  - bin/vmlinux-ch"
    [ ! -f "bin/ubuntu-rootfs.img" ] && echo "  - bin/ubuntu-rootfs.img"
    echo ""
    echo "Run: ./setup-complete.sh"
    exit 1
fi

# Set up authorized users from environment variable or prompt
if [ -z "$AUTHORIZED_EMAILS" ]; then
    echo "⚠️  No authorized emails specified."
    echo "   You can either:"
    echo "   1. Set environment variable: export AUTHORIZED_EMAILS=\"your-email@example.com\""
    echo "   2. Or run: AUTHORIZED_EMAILS=\"your-email@example.com\" ./run-service.sh"
    echo ""
    read -p "Enter your email address: " USER_EMAIL
    if [ -z "$USER_EMAIL" ]; then
        echo "❌ Error: Email address required"
        exit 1
    fi
    AUTHORIZED_EMAILS="$USER_EMAIL"
fi

echo "🔧 Setting up network infrastructure..."
echo "   - TAP interface: ch-tap0"
echo "   - Network range: 172.20.0.0/24"
echo "   - Host IP: 172.20.0.1"
echo ""

# Ensure TAP interface is up
if ! ip link show ch-tap0 &> /dev/null; then
    echo "⚠️  TAP interface not found. Setting up networking..."
    sudo ip tuntap add dev ch-tap0 mode tap
    sudo ip addr add 172.20.0.1/24 dev ch-tap0
    sudo ip link set ch-tap0 up
    
    # Enable IP forwarding
    sudo sysctl net.ipv4.ip_forward=1 > /dev/null
    
    # Set up NAT
    if ! sudo iptables -t nat -C POSTROUTING -s 172.20.0.0/24 -j MASQUERADE 2>/dev/null; then
        sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/24 -j MASQUERADE
    fi
    
    echo "✅ Network setup completed"
else
    echo "✅ Network already configured"
fi

echo "👥 Authorized users: $AUTHORIZED_EMAILS"
echo ""

echo "🚀 Starting service..."
echo "   - Service will register with Hypha server"
echo "   - You'll get a login URL in your browser"
echo "   - Web client will be available after login"
echo ""

echo "📱 Instructions:"
echo "   1. Wait for login URL to appear"
echo "   2. Open the login URL in your browser"
echo "   3. Complete authentication"
echo "   4. Access the web client at the provided URL"
echo ""

echo "🔧 Service Information:"
echo "   - Python service: cloud-hypervisor-terminal.py"
echo "   - VM kernel: vmlinux-ch (Cloud Hypervisor optimized)"
echo "   - VM rootfs: ubuntu-rootfs.img (Ubuntu 20.04 LTS)"
echo "   - Network: TAP interface with NAT"
echo ""

echo "Starting in 3 seconds..."
echo "Press Ctrl+C to cancel..."
sleep 3

# Check Python dependencies
if ! python3 -c "import aiohttp, aiofiles, websockets" 2>/dev/null; then
    echo "❌ Error: Python dependencies missing"
    echo "   Please install: pip3 install --user aiohttp aiofiles websockets"
    exit 1
fi

# Run the service
echo "🚀 Launching Cloud Hypervisor Terminal Service..."
echo "================================================"
python3 cloud-hypervisor-terminal.py --authorized-emails "$AUTHORIZED_EMAILS" 
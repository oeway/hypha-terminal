# Cloud Hypervisor VM Terminal

A complete Cloud Hypervisor-based virtual machine terminal service that provides web-based VM access through Hypha integration.

## 🚀 Quick Start

```bash
# 1. Navigate to the cloud-hypervisor directory
cd /path/to/workspace/hypha-terminal/cloud-hypervisor

# 2. Run the setup script to build everything
./setup-complete.sh

# 3. Start the service
./run-service.sh
```

## 📋 Prerequisites

- Linux system with KVM support
- Python 3.8+
- Root/sudo access for network setup
- Internet connection for downloading components

### Required System Packages
```bash
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
    python3-pip
```

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloud Hypervisor VM Terminal             │
├─────────────────────────────────────────────────────────────┤
│ Web Client (HTML/JS) ←→ Python Service ←→ Cloud Hypervisor │
│       ↓                      ↓                    ↓         │
│   User Interface      Hypha Integration      VM Management   │
│                              ↓                              │
│                    Network: TAP Interface                   │
│                     (172.20.0.0/24)                        │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Components

### Core Files
- `cloud-hypervisor-terminal.py` - Main Python service
- `cloud-hypervisor-index.html` - Web client interface
- `setup-complete.sh` - Complete setup script
- `run-service.sh` - Service launcher

### Binary Assets (`bin/` directory)
- `cloud-hypervisor` - Cloud Hypervisor binary
- `vmlinux-ch` - Cloud Hypervisor optimized kernel
- `ubuntu-rootfs.img` - Ubuntu 20.04 root filesystem

### Build Scripts
- `download-kernel.sh` - Downloads and builds CH kernel
- `build-rootfs.sh` - Builds custom rootfs from Dockerfile
- `build-vm-image.sh` - Complete VM image builder

## 🛠️ Installation Guide

### Method 1: Complete Setup (Recommended)
```bash
# Clone or navigate to the directory
cd cloud-hypervisor

# Run the complete setup script
./setup-complete.sh

# This will:
# 1. Install Cloud Hypervisor binary
# 2. Download and build optimized kernel
# 3. Download Ubuntu cloud image
# 4. Set up TAP networking
# 5. Install Python dependencies
```

### Method 2: Manual Setup
```bash
# 1. Install Cloud Hypervisor
wget https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v42.0/cloud-hypervisor-static
chmod +x cloud-hypervisor-static
mkdir -p bin
mv cloud-hypervisor-static bin/cloud-hypervisor

# 2. Build optimized kernel
git clone --depth 1 https://github.com/cloud-hypervisor/linux.git -b ch-6.12.8 linux-cloud-hypervisor
cd linux-cloud-hypervisor
make ch_defconfig
KCFLAGS="-Wa,-mx86-used-note=no" make bzImage -j$(nproc)
cp arch/x86/boot/compressed/vmlinux.bin ../bin/vmlinux-ch
cd ..

# 3. Download Ubuntu cloud image
wget https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img
qemu-img convert -f qcow2 -O raw focal-server-cloudimg-amd64.img bin/ubuntu-rootfs.img

# 4. Install Python dependencies
pip3 install aiohttp aiofiles websockets
```

## 🌐 Network Configuration

The system uses TAP networking with the following configuration:
- **TAP Interface**: `ch-tap0`
- **Host IP**: `172.20.0.1/24`
- **VM IP Range**: `172.20.0.100-172.20.0.200`
- **Gateway**: `172.20.0.1`

### Network Setup (Automatic)
The service automatically configures networking when started:
```bash
# TAP interface creation
sudo ip tuntap add dev ch-tap0 mode tap
sudo ip addr add 172.20.0.1/24 dev ch-tap0
sudo ip link set ch-tap0 up

# IP forwarding and NAT
sudo sysctl net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -s 172.20.0.0/24 -j MASQUERADE
```

## 🚀 Usage

### Starting the Service
```bash
# Basic start
./run-service.sh

# With specific authorized emails
AUTHORIZED_EMAILS="user1@example.com,user2@example.com" ./run-service.sh

# Development mode (verbose logging)
python3 cloud-hypervisor-terminal.py --authorized-emails "your-email@example.com" --debug
```

### Web Interface
1. Start the service
2. Open the provided login URL in your browser
3. Complete Hypha authentication
4. Access the VM terminal through the web interface

### VM Configuration Options
The service supports various VM configurations:
```python
# Example VM recipe
{
    "name": "Development VM",
    "cpus": 2,
    "memory": "1G",
    "use_firmware": False,  # Use direct kernel boot
    "python_packages": ["numpy", "requests"],
    "startup_script": "echo 'VM ready'"
}
```

## 🧪 Testing

### Quick Test
```bash
# Test basic VM functionality
python3 test-vm-simple.py

# Complete functionality test
python3 test-vm-complete.py
```

### Manual Testing
```bash
# Start a test VM
python3 -c "
from cloud_hypervisor_terminal import CloudHypervisorTerminal
terminal = CloudHypervisorTerminal()
result = terminal.create_terminal('test-user', {
    'name': 'Test VM',
    'cpus': 1,
    'memory': '512M'
})
print(f'VM created: {result}')
"
```

## 📊 Performance & Specifications

### VM Specifications
- **CPU**: 1-8 cores (configurable)
- **Memory**: 512MB-16GB (configurable)
- **Storage**: 2.2GB Ubuntu root filesystem
- **Network**: Full internet access via NAT
- **Boot Time**: ~3-5 seconds

### Host Requirements
- **CPU**: 2+ cores recommended
- **Memory**: 2GB+ available RAM
- **Storage**: 3GB+ free space
- **Network**: Internet connectivity

## 🔧 Troubleshooting

### Common Issues

#### 1. VM Boot Failures
```bash
# Check kernel and rootfs
ls -la bin/
# Should show: vmlinux-ch, ubuntu-rootfs.img

# Verify file sizes
du -sh bin/*
# vmlinux-ch should be ~8MB
# ubuntu-rootfs.img should be ~617MB
```

#### 2. Network Issues
```bash
# Check TAP interface
ip addr show ch-tap0

# Test connectivity
ping 172.20.0.1

# Check forwarding
cat /proc/sys/net/ipv4/ip_forward
```

#### 3. Permission Errors
```bash
# Ensure proper permissions
chmod +x *.sh
chmod +x bin/cloud-hypervisor

# Check sudo access
sudo -v
```

### Debug Mode
```bash
# Enable verbose logging
python3 cloud-hypervisor-terminal.py --debug --authorized-emails "your-email"
```

## 🔒 Security Considerations

### Access Control
- Email-based authorization through Hypha
- Isolated VM environments
- Network isolation through TAP interfaces

### VM Security
- No direct host access from VMs
- Sandboxed execution environment
- Network traffic routing through host

## 📝 Development

### File Structure
```
cloud-hypervisor/
├── bin/                          # Binary assets
│   ├── cloud-hypervisor         # CH binary
│   ├── vmlinux-ch              # Optimized kernel
│   └── ubuntu-rootfs.img       # Root filesystem
├── cloud-hypervisor-terminal.py # Main service
├── cloud-hypervisor-index.html  # Web client
├── setup-complete.sh           # Setup script
├── run-service.sh             # Service launcher
├── test-vm-simple.py          # Basic tests
├── test-vm-complete.py        # Complete tests
└── README.md                  # This file
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is part of the Hypha terminal ecosystem. See the main repository for licensing information.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the test scripts for examples
3. Check the main Hypha repository for general issues

## 🔄 Updates

### Latest Changes
- ✅ Cloud Hypervisor optimized kernel (v6.12.8+)
- ✅ Ubuntu 20.04 LTS cloud image integration
- ✅ TAP networking with internet access
- ✅ Direct kernel boot (no EFI issues)
- ✅ Comprehensive testing suite
- ✅ Automated setup and deployment

### Version History
- **v2.0**: Cloud Hypervisor kernel integration
- **v1.5**: Ubuntu cloud image support
- **v1.0**: Initial release with custom rootfs 
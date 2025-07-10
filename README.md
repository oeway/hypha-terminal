# Firecracker Terminal Service

A web-based terminal service that creates isolated microVMs using AWS Firecracker. Each terminal session runs in its own secure microVM with networking capabilities, providing a Python data science environment accessible through a web interface.

## 🚀 Features

- **Isolated microVMs**: Each terminal session runs in its own Firecracker microVM
- **Web-based interface**: Access terminals through any web browser
- **Authentication**: Secure access via Hypha server authentication
- **Data science environment**: Pre-installed Python packages (numpy, pandas, matplotlib, etc.)
- **Multi-user support**: Multiple users can have multiple terminal sessions
- **Network isolation**: Each VM has its own network stack with internet access
- **Resource efficient**: Lightweight VMs with minimal overhead

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ or similar Linux distribution
- **CPU**: x86_64 processor with virtualization support (Intel VT-x or AMD-V)
- **RAM**: Minimum 4GB, recommended 8GB+ for multiple VMs
- **Storage**: At least 10GB free space
- **Network**: Internet connection for downloading components

### Required Software
- Docker
- KVM/QEMU virtualization
- curl, wget, git
- Python 3.8+
- Linux kernel headers

## 🚀 Quick Start

Get up and running in 4 simple steps:

```bash
# Clone the repository
git clone <repository-url>
cd hypha-terminal

# 1. Prepare host system (install dependencies, setup permissions)
./1-prepare.sh

# 2. Build everything (download Firecracker, build kernel, create rootfs)
./2-setup.sh

# 3. Test everything works (validate setup, test VM boot)
./3-test.sh

# 4. Start the service (launch web interface)
./4-serve.sh
```

After setup, access the web interface at the URL shown in the terminal output.

## 📋 Script Organization

The scripts are numbered in logical execution order:

- **1-prepare.sh** - Host system preparation (prerequisites)
- **2-setup.sh** - Environment build (download, build, configure)
- **3-test.sh** - Validation testing (verify everything works)
- **4-serve.sh** - Service launch (production deployment)
- **9-debug.sh** - Manual VM debugging (troubleshooting tool)

This ordering ensures you can follow the numbered sequence for a complete setup, with debugging tools clearly separated.

## 📖 Detailed Setup Guide

### Step 1: Host Preparation

```bash
./1-prepare.sh
```

This script performs the following actions:
- **CPU Check**: Verifies virtualization support (Intel VT-x or AMD-V)
- **Package Installation**: Installs KVM, Docker, and required utilities
- **Permission Setup**: Adds user to `kvm` and `docker` groups
- **Service Start**: Enables and starts Docker service

**Important**: If Docker access fails, log out and back in to refresh group permissions.

### Step 2: Environment Build

```bash
./2-setup.sh
```

This script builds the complete environment:

1. **Firecracker Binary**: Downloads official Firecracker v1.10.0
2. **Linux Kernel**: Downloads pre-built kernel optimized for Firecracker
3. **Custom Rootfs**: Uses multi-stage Docker build to create filesystem with:
   - Go init binary (required for Firecracker boot)
   - Alpine Linux base system
   - Python data science environment
   - User account (`scientist`) with pre-configured environment
4. **Network Setup**: Creates `ftap0` interface with NAT masquerading
5. **Validation**: Verifies init binary is present in rootfs

### Step 3: Validation Testing

```bash
./3-test.sh
```

Comprehensive validation includes:
- **File Existence**: Verifies all required binaries and images exist
- **Init Binary**: Confirms Go init binary is present in rootfs
- **Network**: Tests network interface configuration
- **Python Environment**: Validates Python packages are installed
- **VM Boot Test**: Performs actual VM boot test with 15-second timeout

### Step 4: Service Launch

```bash
./4-serve.sh [authorized-emails]
```

Launches the web service with optional email restrictions:

```bash
# Allow all authenticated users
./4-serve.sh

# Restrict to specific emails
./4-serve.sh "user1@example.com,user2@example.com"
```

## 🛠️ Building Custom Rootfs

### Using the Modular Script

The `build-rootfs.sh` script provides flexible rootfs creation:

```bash
# Basic usage with defaults
./build-rootfs.sh

# Custom Dockerfile and output
./build-rootfs.sh -d ./my-custom.dockerfile -o ./my-rootfs.img

# Full customization
./build-rootfs.sh \
  --dockerfile ./Dockerfile.custom \
  --output ./production-rootfs.img \
  --size 10G \
  --tag my-custom-image \
  --workdir .

# Skip init verification (for non-Firecracker images)
./build-rootfs.sh --no-verify-init -d ./Dockerfile.web -o ./web-rootfs.img
```

### Script Options

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --dockerfile` | Path to Dockerfile | `./Dockerfile` |
| `-o, --output` | Output rootfs.img filename | `./rootfs.img` |
| `-s, --size` | Size of rootfs image | `5G` |
| `-t, --tag` | Docker image tag | `custom-rootfs` |
| `-w, --workdir` | Working directory | `.` |
| `--verify-init` | Verify init binary presence | `true` |
| `--no-verify-init` | Skip init verification | `false` |
| `-h, --help` | Show help message | - |

### Build Process

The script automatically:
1. **Docker Build**: Builds image from specified Dockerfile
2. **Container Export**: Exports filesystem to tar archive
3. **Init Verification**: Confirms init binary is present (if enabled)
4. **Image Creation**: Creates and formats ext4 disk image
5. **Filesystem Extraction**: Mounts and extracts rootfs to disk
6. **Permission Fix**: Sets correct ownership on final image

## 🔧 Manual VM Testing & Debugging

For debugging and development:

```bash
./9-debug.sh
```

This script:
- Manually starts a single Firecracker VM
- Shows VM console output directly
- Useful for troubleshooting boot issues
- Allows interaction with VM via serial console
- Numbered 9 to indicate it's a debugging tool (not part of main workflow)

## 🏗️ Architecture

### Network Configuration
- **Host Network**: 172.16.0.1/24
- **VM Network**: 172.16.0.2+ (assigned dynamically)
- **Interface**: `ftap0` bridge with NAT masquerading
- **Internet Access**: Full internet connectivity via NAT

### VM Specifications
- **CPU**: 2 vCPUs
- **Memory**: 256MB RAM
- **Storage**: 5GB disk image
- **OS**: Alpine Linux 3.20
- **Init**: Custom Go binary for Firecracker compatibility

### Software Stack
- **Firecracker**: v1.10.0 for VM management
- **Kernel**: Linux 5.10.223 optimized for Firecracker
- **Python**: 3.11+ with virtual environment
- **Packages**: numpy, pandas, scipy, matplotlib, seaborn, ipython, hypha-rpc

## 📁 File Structure

After setup completion:

```
hypha-terminal/
├── 1-prepare.sh              # Host preparation script
├── 2-setup.sh                # Environment build script
├── 3-test.sh                 # Validation test script
├── 4-serve.sh                # Service launch script
├── 9-debug.sh                # Manual VM debugging script
├── build-rootfs.sh           # Modular rootfs builder
├── firecracker-terminal.py   # Main service application
├── firecracker-index.html    # Web interface
├── Dockerfile                # Multi-stage build definition
├── simple-init               # Simple shell init script
└── bin/                      # VM components
    ├── firecracker           # Firecracker binary
    ├── vmlinux               # Linux kernel
    ├── rootfs.img            # Root filesystem (5GB)
    └── simple-init           # Init script for VM
```

## 🖥️ Usage Guide

### Web Interface Access
1. Run `./4-serve.sh` to start the service
2. Note the URL displayed in the terminal output
3. Open the URL in your web browser
4. Authenticate using Hypha server credentials

### Terminal Operations
- **Create Terminal**: Click "Create New Terminal" button
- **Multiple Sessions**: Each user can have multiple terminals
- **Command Execution**: Type commands normally in the terminal
- **Session Isolation**: Each terminal runs in its own VM

### Python Environment
Each VM comes with a pre-configured Python environment:
```bash
# Python is ready to use
python3 --version

# Virtual environment is activated
which python

# Data science packages are installed
python -c "import numpy, pandas, matplotlib; print('All packages available')"
```

## 🔍 Critical Requirements

### Docker Build with Simple Init
The `Dockerfile` uses a simple shell-based init script:

```dockerfile
FROM alpine:3.20
# ... install packages ...
COPY simple-init /init
RUN chmod +x /init
# ... rest of setup ...
```

### Init Script Requirement
- **Critical**: The `/init` script must be present in the rootfs
- **Without it**: VMs will fail with kernel panic: "Requested init /init failed (error -2)"
- **Verification**: The `build-rootfs.sh` script automatically verifies init script presence

## 🚨 Troubleshooting

### Common Issues

#### 1. Kernel Panic: "init failed (error -2)"
**Cause**: Missing init binary in rootfs
**Solution**: 
```bash
# Rebuild with proper Dockerfile
./build-rootfs.sh -o ./bin/rootfs.img

# Verify init binary is present
tar -tf ./rootfs.tar | grep '^init$'
```

#### 2. Network Interface Busy
**Cause**: Previous firecracker processes still running
**Solution**:
```bash
# Kill old processes
sudo pkill firecracker

# Reset network interface
sudo ip link delete ftap0
./2-setup.sh  # Re-run setup
```

#### 3. Permission Denied on rootfs.img
**Cause**: Incorrect file ownership
**Solution**:
```bash
# Fix ownership
sudo chown $USER:$USER ./bin/rootfs.img
```

#### 4. CPU Virtualization Not Supported
**Cause**: Hardware virtualization disabled
**Solution**:
```bash
# Check virtualization support
cat /proc/cpuinfo | grep -E "(vmx|svm)"

# Enable in BIOS/UEFI if not shown
# For VMs: Enable nested virtualization
```

#### 5. Docker Permission Denied
**Cause**: User not in docker group
**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then test
docker run hello-world
```

### Debugging Commands

```bash
# Check Firecracker processes
ps aux | grep firecracker

# Check network interface
ip addr show ftap0

# Test VM boot manually
./9-debug.sh

# Validate complete setup
./3-test.sh

# Check init binary in rootfs
tar -tf ./rootfs.tar | grep '^init$'

# Mount rootfs for inspection
sudo mkdir /tmp/rootfs
sudo mount -o loop ./bin/rootfs.img /tmp/rootfs
ls -la /tmp/rootfs/
sudo umount /tmp/rootfs
```

## 🔒 Security Considerations

### VM Isolation
- Each VM runs in its own isolated environment
- No shared filesystem between VMs
- Network isolation with controlled internet access

### Authentication
- Uses Hypha server for user authentication
- Optional email-based access control
- Secure token-based session management

### Resource Limits
- VMs are limited to 256MB RAM and 2 vCPUs
- 5GB disk space per VM
- Network bandwidth shared among all VMs

## 🚀 Advanced Usage

### Custom Environments
Create specialized environments by modifying the Dockerfile:

```dockerfile
# Add custom packages
RUN apk add --no-cache nodejs npm

# Install additional Python packages
RUN pip install tensorflow pytorch

# Custom user setup
RUN adduser -D -s /bin/bash customuser
```

### Production Deployment
For production use:

```bash
# Create production rootfs
./build-rootfs.sh \
  --dockerfile ./Dockerfile.production \
  --output ./production-rootfs.img \
  --size 10G \
  --tag production-env

# Deploy with email restrictions
./4-serve.sh "admin@company.com,user1@company.com"
```

### Monitoring and Logging
- VM logs are available through the web interface
- Firecracker process logs in system journal
- Network traffic monitored via `ftap0` interface

## 🛠️ Development

### Contributing
1. Fork the repository
2. Create feature branches
3. Test with `./4-test.sh`
4. Submit pull requests

### Testing
```bash
# Run full test suite
./3-test.sh

# Test individual components
./build-rootfs.sh --help
docker build -f ./Dockerfile .

# Manual VM testing
./9-debug.sh
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- AWS Firecracker team for the excellent virtualization platform
- Alpine Linux for the lightweight base image
- Hypha project for authentication infrastructure
- Alex Ellis for the original firecracker-init-lab

---

For questions, issues, or contributions, please open an issue on the project repository. 
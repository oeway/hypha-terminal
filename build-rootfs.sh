#!/bin/bash

# Script to build a rootfs image from a Dockerfile
# Usage: ./build-rootfs.sh [options]
# Options:
#   -d, --dockerfile PATH    Path to Dockerfile (default: ./Dockerfile)
#   -o, --output FILE        Output rootfs.img filename (default: ./rootfs.img)
#   -s, --size SIZE          Size of rootfs image (default: 5G)
#   -t, --tag TAG            Docker image tag (default: custom-rootfs)
#   -w, --workdir DIR        Working directory (default: current directory)
#   --verify-init            Verify init binary is present (default: true)
#   -h, --help               Show this help message

set -e

# Default values
DOCKERFILE="./Dockerfile"
OUTPUT="./rootfs.img"
SIZE="5G"
TAG="custom-rootfs"
WORKDIR="."
VERIFY_INIT=true

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Build a rootfs image from a Dockerfile"
    echo ""
    echo "Options:"
    echo "  -d, --dockerfile PATH    Path to Dockerfile (default: ./Dockerfile)"
    echo "  -o, --output FILE        Output rootfs.img filename (default: ./rootfs.img)"
    echo "  -s, --size SIZE          Size of rootfs image (default: 5G)"
    echo "  -t, --tag TAG            Docker image tag (default: custom-rootfs)"
    echo "  -w, --workdir DIR        Working directory (default: current directory)"
    echo "  --verify-init            Verify init binary is present (default: true)"
    echo "  --no-verify-init         Skip init binary verification"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -d ./Dockerfile.basic -o basic-rootfs.img"
    echo "  $0 --dockerfile ./custom.dockerfile --output /tmp/my-rootfs.img --size 10G"
    echo "  $0 -o ./bin/production-rootfs.img"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -s|--size)
            SIZE="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -w|--workdir)
            WORKDIR="$2"
            shift 2
            ;;
        --verify-init)
            VERIFY_INIT=true
            shift
            ;;
        --no-verify-init)
            VERIFY_INIT=false
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

echo "=== Building rootfs from Docker container ==="
echo "Dockerfile: $DOCKERFILE"
echo "Output: $OUTPUT"
echo "Size: $SIZE"
echo "Tag: $TAG"
echo "Working directory: $WORKDIR"
echo "Verify init binary: $VERIFY_INIT"
echo ""

# Change to working directory
cd "$WORKDIR"

# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo "ERROR: Dockerfile not found at: $DOCKERFILE"
    exit 1
fi

# Verify Dockerfile contains multi-stage build for init (if verification enabled)
if [ "$VERIFY_INIT" = true ]; then
    echo "Verifying Dockerfile contains multi-stage build for init binary..."
    if grep -q "FROM golang.*as build" "$DOCKERFILE"; then
        echo "✓ Dockerfile contains multi-stage build for init binary"
    else
        echo "WARNING: Dockerfile may be missing multi-stage build for init binary!"
        echo "Expected pattern: 'FROM golang.*as build'"
        echo "This may cause VMs to fail with kernel panic if init binary is missing."
        echo ""
    fi
fi

# Build the Docker image
echo "Building Docker image from $DOCKERFILE..."
docker build -f "$DOCKERFILE" -t "$TAG" .

# Verify the image was built successfully
if [ $? -ne 0 ]; then
    echo "ERROR: Docker build failed!"
    exit 1
fi

echo "✓ Docker image built successfully: $TAG"

# Extract rootfs from Docker container
echo "Extracting rootfs from Docker container..."
CONTAINER_NAME="extract-$(date +%s)"
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Get the absolute path for the tar file
TAR_FILE="${OUTPUT%.*}.tar"
rm -rf "$TAR_FILE" 2>/dev/null || true

docker create --name "$CONTAINER_NAME" "$TAG"
docker export "$CONTAINER_NAME" -o "$TAR_FILE"
docker rm -f "$CONTAINER_NAME"

echo "✓ Rootfs extracted to: $TAR_FILE"

# Verify the init binary is in the rootfs (if verification enabled)
if [ "$VERIFY_INIT" = true ]; then
    echo "Verifying init binary is present in rootfs..."
    if tar -tf "$TAR_FILE" | grep -q "^init$"; then
        echo "✓ Init binary found in rootfs"
    else
        echo "ERROR: Init binary not found in rootfs!"
        echo "This means the Dockerfile multi-stage build failed or doesn't include init."
        echo "VMs built with this rootfs will fail to boot with kernel panic."
        exit 1
    fi
fi

# Create the rootfs disk image
echo "Creating ${SIZE} rootfs disk image: $OUTPUT"
rm -rf "$OUTPUT" 2>/dev/null || true
sudo fallocate -l "$SIZE" "$OUTPUT"
sudo mkfs.ext4 "$OUTPUT"

# Mount and extract rootfs
echo "Mounting and extracting rootfs to disk image..."
TMP=$(mktemp -d)
echo "Temporary mount point: $TMP"
sudo mount -o loop "$OUTPUT" "$TMP"
sudo tar -xf "$TAR_FILE" -C "$TMP"
sudo umount "$TMP"
rm -rf "$TMP"

# Fix permissions
echo "Fixing permissions on rootfs image..."
sudo chown $USER:$USER "$OUTPUT"

# Verify final rootfs.img file
if [ -f "$OUTPUT" ]; then
    SIZE_ACTUAL=$(du -h "$OUTPUT" | cut -f1)
    echo "✓ Rootfs image created successfully: $OUTPUT (size: $SIZE_ACTUAL)"
else
    echo "ERROR: Rootfs image not created: $OUTPUT"
    exit 1
fi

echo ""
echo "=== Build complete! ==="
echo "✓ Docker image: $TAG"
echo "✓ Rootfs tar: $TAR_FILE"
echo "✓ Rootfs image: $OUTPUT"
if [ "$VERIFY_INIT" = true ]; then
    echo "✓ Init binary verified"
fi
echo ""
echo "You can now use $OUTPUT as a rootfs for Firecracker VMs." 
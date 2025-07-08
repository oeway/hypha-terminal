mkdir -p ./bin
cd ./bin
curl -fsSL -o ./firecracker.tgz https://github.com/firecracker-microvm/firecracker/releases/download/v1.12.1/firecracker-v1.12.1-x86_64.tgz
tar -xzf firecracker.tgz
cp release-v1.12.1-x86_64/firecracker-v1.12.1-x86_64 firecracker
rm -rf ./release-v1.12.1-x86_64
chmod +x ./firecracker
curl -fsSL -o ./hello-vmlinux.bin https://s3.amazonaws.com/spec.ccfc.min/img/hello/kernel/hello-vmlinux.bin
curl -fsSL -o ./hello-rootfs.ext4 https://s3.amazonaws.com/spec.ccfc.min/img/hello/fsfiles/hello-rootfs.ext4
cd ../
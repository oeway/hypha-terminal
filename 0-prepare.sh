grep -cw vmx /proc/cpuinfo
sudo apt-get update && sudo apt-get install qemu-kvm -y
sudo setfacl -m u:${USER}:rw /dev/kvm
[ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "OK" || echo "FAIL"

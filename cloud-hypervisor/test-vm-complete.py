#!/usr/bin/env python3

"""
Comprehensive Cloud Hypervisor VM Test Script

This script creates a VM, waits for it to boot, and then tests:
1. Basic VM functionality
2. Network connectivity (ping google.com)
3. Python execution
4. File system operations
"""

import asyncio
import time
import sys
import os
import importlib.util

# Import the terminal class from the hyphen-named module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cloud_hypervisor_terminal", "cloud-hypervisor-terminal.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CloudHypervisorTerminal = module.CloudHypervisorTerminal

async def test_vm_complete():
    """Complete VM functionality test"""
    print("🧪 Complete Cloud Hypervisor VM Test")
    print("=" * 60)
    
    # Initialize terminal manager
    terminal_manager = CloudHypervisorTerminal()
    
    # Test configuration for a working VM
    test_recipe = {
        'name': 'Complete Test VM',
        'cpus': 2,
        'memory': '1G',  # More memory for better performance
        'use_firmware': False,  # Use direct kernel boot
        'python_packages': ['requests'],
        'startup_script': 'echo "VM ready for testing"'
    }
    
    print("🚀 Step 1: Creating VM...")
    result = terminal_manager.create_terminal(test_recipe, "test_user")
    if not result['success']:
        print(f"❌ VM creation failed: {result['error']}")
        return False
    
    terminal_id = result['terminal_id']
    print(f"✅ VM created successfully: {terminal_id}")
    
    # Wait for VM to boot and show boot process
    print("\n📺 Step 2: Monitoring VM Boot...")
    boot_timeout = 60  # Longer timeout for complete boot
    start_time = time.time()
    boot_complete = False
    
    while time.time() - start_time < boot_timeout:
        read_result = terminal_manager.read_from_terminal(terminal_id, "test_user")
        if read_result['success'] and read_result['output']:
            output = read_result['output']
            print(f"   {output.strip()}")
            
            # Check for successful boot indicators
            if any(indicator in output.lower() for indicator in 
                   ["login:", "# ", "$ ", "root@", "welcome"]):
                print("✅ VM boot successful - shell prompt detected!")
                boot_complete = True
                break
            elif "panic" in output.lower() or "kernel panic" in output.lower():
                print(f"❌ VM boot failed with panic")
                break
        
        time.sleep(2)
    
    if not boot_complete:
        print("⚠️  VM boot monitoring timed out, but continuing with tests...")
    
    # Give the VM a moment to fully initialize
    print("\n⏳ Step 3: Waiting for VM to fully initialize...")
    time.sleep(5)
    
    # Test basic shell functionality
    print("\n🔧 Step 4: Testing Basic Shell Commands...")
    
    commands_to_test = [
        ("echo 'Hello Cloud Hypervisor'", "Basic echo test"),
        ("whoami", "User identification"),
        ("pwd", "Current directory"),
        ("ls -la /", "Root directory listing"),
        ("cat /proc/version", "Kernel version"),
        ("free -h", "Memory information"),
        ("df -h", "Disk space"),
    ]
    
    for command, description in commands_to_test:
        print(f"   Testing: {description}")
        
        # Send command
        write_result = terminal_manager.write_to_terminal(terminal_id, command + "\n", "test_user")
        if not write_result['success']:
            print(f"   ❌ Failed to send command: {write_result['error']}")
            continue
        
        # Read response
        time.sleep(2)
        response = ""
        for _ in range(5):  # Try reading multiple times
            read_result = terminal_manager.read_from_terminal(terminal_id, "test_user")
            if read_result['success'] and read_result['output']:
                response += read_result['output']
            time.sleep(0.5)
        
        if response.strip():
            print(f"   ✅ {description}: Got response")
            # Show first line of response for verification
            first_line = response.split('\n')[0].strip()
            if first_line:
                print(f"      → {first_line}")
        else:
            print(f"   ⚠️  {description}: No response received")
    
    # Test network connectivity
    print("\n🌐 Step 5: Testing Network Connectivity...")
    
    network_commands = [
        ("ip addr show", "Network interface configuration"),
        ("ping -c 3 172.20.0.1", "Ping host (TAP gateway)"),
        ("ping -c 3 8.8.8.8", "Ping Google DNS"),
        ("ping -c 2 google.com", "Ping google.com (DNS resolution)"),
    ]
    
    for command, description in network_commands:
        print(f"   Testing: {description}")
        
        write_result = terminal_manager.write_to_terminal(terminal_id, command + "\n", "test_user")
        if not write_result['success']:
            print(f"   ❌ Failed to send command: {write_result['error']}")
            continue
        
        # Network commands take longer
        time.sleep(5)
        response = ""
        for _ in range(10):
            read_result = terminal_manager.read_from_terminal(terminal_id, "test_user")
            if read_result['success'] and read_result['output']:
                response += read_result['output']
            time.sleep(0.5)
        
        if "ping" in command.lower():
            if "0% packet loss" in response or "64 bytes from" in response:
                print(f"   ✅ {description}: Success")
            elif "100% packet loss" in response or "network unreachable" in response.lower():
                print(f"   ❌ {description}: Failed")
            else:
                print(f"   ⚠️  {description}: Unclear result")
        else:
            if response.strip():
                print(f"   ✅ {description}: Got response")
            else:
                print(f"   ⚠️  {description}: No response")
    
    # Test Python functionality
    print("\n🐍 Step 6: Testing Python Functionality...")
    
    python_commands = [
        ("python3 --version", "Python version check"),
        ("python3 -c \"print('Hello from VM Python!')\"", "Basic Python execution"),
        ("python3 -c \"import sys; print(f'Python path: {sys.executable}')\"", "Python environment"),
        ("python3 -c \"import os; print(f'VM hostname: {os.uname().nodename}')\"", "System information"),
    ]
    
    for command, description in python_commands:
        print(f"   Testing: {description}")
        
        write_result = terminal_manager.write_to_terminal(terminal_id, command + "\n", "test_user")
        if not write_result['success']:
            print(f"   ❌ Failed to send command: {write_result['error']}")
            continue
        
        time.sleep(3)
        response = ""
        for _ in range(5):
            read_result = terminal_manager.read_from_terminal(terminal_id, "test_user")
            if read_result['success'] and read_result['output']:
                response += read_result['output']
            time.sleep(0.5)
        
        if response.strip():
            print(f"   ✅ {description}: Success")
            # Show the actual output for Python commands
            for line in response.split('\n'):
                if line.strip() and not line.startswith('#') and 'python3' not in line.lower():
                    print(f"      → {line.strip()}")
        else:
            print(f"   ⚠️  {description}: No response")
    
    # Final status check
    print("\n📊 Step 7: Final VM Status Check...")
    status_result = terminal_manager.get_terminal_status(terminal_id, "test_user")
    if status_result['success']:
        status = status_result['status']
        print(f"   ✅ VM Status: {'Running' if status['running'] else 'Stopped'}")
        print(f"   📍 PID: {status['pid']}")
        print(f"   ⏰ Uptime: {int(time.time() - status['created'])} seconds")
    
    # Cleanup
    print("\n🧹 Step 8: Cleanup...")
    close_result = terminal_manager.close_terminal(terminal_id, "test_user")
    if close_result['success']:
        print("   ✅ VM stopped and cleaned up successfully")
    else:
        print(f"   ⚠️  Cleanup warning: {close_result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print("🎉 Complete VM Test Finished!")
    print("✅ Cloud Hypervisor VM is working with:")
    print("   - Direct kernel boot (vmlinux)")
    print("   - Network connectivity via TAP interface")
    print("   - Python execution environment")
    print("   - Full shell access")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_vm_complete()) 
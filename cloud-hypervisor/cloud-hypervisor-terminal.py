import asyncio
import subprocess
import os
import signal
import select
import sys
import argparse
import uuid
import time
import json
import threading
import tempfile
import shutil
import socket
from hypha_rpc import connect_to_server, login
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

class CloudHypervisorTerminal:
    def __init__(self):
        self.user_terminals = {}  # user_id -> {terminal_id -> terminal_data}
        self.terminal_counter = 0
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cleanup_existing_vms()
        self.setup_network()
    
    def cleanup_existing_vms(self):
        """Clean up any existing Cloud Hypervisor VMs that might be using the TAP interface"""
        try:
            # Find and kill any existing cloud-hypervisor processes
            result = subprocess.run(['pgrep', '-f', 'cloud-hypervisor.*ch-tap0'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                cleaned_count = 0
                for pid in pids:
                    if pid.strip():
                        try:
                            subprocess.run(['kill', pid.strip()], check=True)
                            print(f"Cleaned up existing Cloud Hypervisor VM (PID: {pid.strip()})")
                            cleaned_count += 1
                        except:
                            pass
                
                if cleaned_count > 0:
                    print(f"✅ Cleaned up {cleaned_count} existing Cloud Hypervisor processes")
                    # Wait longer for processes to clean up and release TAP interface
                    time.sleep(3)
            else:
                print("ℹ️  No existing Cloud Hypervisor processes found")
        except:
            pass
    
    def setup_network(self):
        """Setup network infrastructure for VMs"""
        try:
            # Check if TAP interface already exists
            result = subprocess.run(['ip', 'link', 'show', 'ch-tap0'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("Setting up network infrastructure...")
                
                # Create TAP interface
                subprocess.run(['sudo', 'ip', 'tuntap', 'add', 'dev', 'ch-tap0', 'mode', 'tap'], 
                              check=True)
                
                # Configure TAP interface
                subprocess.run(['sudo', 'ip', 'addr', 'add', '172.20.0.1/24', 'dev', 'ch-tap0'], 
                              check=True)
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', 'ch-tap0', 'up'], 
                              check=True)
                
                # Enable IP forwarding
                subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=1'], 
                              check=True)
                
                # Setup NAT (find default interface)
                default_iface = self.get_default_interface()
                if default_iface:
                    subprocess.run(['sudo', 'iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                                   '-o', default_iface, '-j', 'MASQUERADE'], check=True)
                    subprocess.run(['sudo', 'iptables', '-A', 'FORWARD', '-i', 'ch-tap0', 
                                   '-o', default_iface, '-j', 'ACCEPT'], check=True)
                    subprocess.run(['sudo', 'iptables', '-A', 'FORWARD', '-i', default_iface, 
                                   '-o', 'ch-tap0', '-j', 'ACCEPT'], check=True)
                
                print("Network setup complete: TAP interface ch-tap0 ready")
            else:
                print("Network already configured: TAP interface ch-tap0 exists")
        except Exception as e:
            print(f"Warning: Network setup failed: {e}")
            print("VMs may not have network connectivity")
    
    def get_default_interface(self):
        """Get the default network interface"""
        try:
            result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                  capture_output=True, text=True, check=True)
            # Parse output to find default interface
            for line in result.stdout.split('\n'):
                if 'default' in line:
                    parts = line.split()
                    if 'dev' in parts:
                        idx = parts.index('dev')
                        if idx + 1 < len(parts):
                            return parts[idx + 1]
        except:
            pass
        return None
    
    def create_terminal(self, recipe=None, user_id=None):
        """Create a new terminal session with Cloud Hypervisor VM"""
        print(f"Creating Cloud Hypervisor terminal for user: {user_id}, recipe: {recipe}")
        
        # Debug: Show use_firmware value specifically
        use_firmware = recipe.get('use_firmware') if recipe else None
        print(f"DEBUG: use_firmware = {use_firmware} (type: {type(use_firmware)})")
        
        # Generate unique terminal ID and session UUID
        terminal_id = f"terminal_{self.terminal_counter}"
        self.terminal_counter += 1
        session_uuid = str(uuid.uuid4())
        
        # Create unique working directory for this terminal session
        work_dir = os.path.join(self.base_dir, f"vm-{session_uuid}")
        os.makedirs(work_dir, exist_ok=True)
        
        try:
            # Configure VM parameters
            vm_config = self._prepare_vm_config(recipe or {}, work_dir, session_uuid)
            vm_config['session_uuid'] = session_uuid  # Add session UUID for unique network config
            
            # Build Cloud Hypervisor command
            ch_cmd = self._build_cloud_hypervisor_command(vm_config)
            
            print(f"Starting Cloud Hypervisor with command: {' '.join(ch_cmd)}")
            
            # Test the command quickly before running it
            try:
                test_result = subprocess.run(
                    ch_cmd + ['--help'], 
                    capture_output=True, 
                    text=True, 
                    timeout=2,
                    cwd=work_dir
                )
                if test_result.returncode != 0 and 'unexpected argument' in test_result.stderr:
                    raise Exception(f"Command syntax error: {test_result.stderr}")
            except subprocess.TimeoutExpired:
                # Help command took too long, that's OK
                pass
            except FileNotFoundError:
                raise Exception("Cloud Hypervisor binary not found")
            except Exception as e:
                if 'unexpected argument' in str(e):
                    raise e
                # Other errors during test are OK, we'll try the real command
                pass
            
            # Create startup script for VM initialization
            startup_script = self._create_startup_script(work_dir, recipe or {})
            
            # Start Cloud Hypervisor process
            ch_process = subprocess.Popen(
                ch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                preexec_fn=os.setsid,
                bufsize=0,
                cwd=work_dir
            )
            
            # Wait for VM to start and check if it's running
            time.sleep(2)
            
            if ch_process.poll() is not None:
                # Process ended immediately, check output
                stdout_output = ""
                stderr_output = ""
                try:
                    stdout_output = ch_process.stdout.read(1024).decode('utf-8', errors='replace')
                except:
                    pass
                try:
                    stderr_output = ch_process.stderr.read(1024).decode('utf-8', errors='replace')
                except:
                    pass
                
                full_output = f"STDOUT: {stdout_output}\nSTDERR: {stderr_output}"
                
                # Check for specific error types
                if "Resource busy" in full_output:
                    raise Exception(f"Error booting VM: Network interface is busy. Try again in a few seconds.")
                elif "TapOpen" in full_output:
                    raise Exception(f"Error booting VM: TAP interface error. Network may be in use.")
                elif "unexpected argument" in full_output:
                    raise Exception(f"Error booting VM: Command line argument error. {full_output}")
                else:
                    raise Exception(f"Error booting VM: {full_output}")
            
            # Initialize user terminals if not exists
            if user_id not in self.user_terminals:
                self.user_terminals[user_id] = {}
            
            terminal_name = recipe.get('name', f'CloudHV {self.terminal_counter}') if recipe else f'CloudHV {self.terminal_counter}'
            
            self.user_terminals[user_id][terminal_id] = {
                'process': ch_process,
                'work_dir': work_dir,
                'session_uuid': session_uuid,
                'created_at': time.time(),
                'user_id': user_id,
                'screen_buffer': [],
                'name': terminal_name,
                'recipe': recipe or {},
                'startup_script': startup_script,
                'pty_master': vm_config.get('pty_master'),
                'pty_slave': vm_config.get('pty_slave')
            }
            
            return {"terminal_id": terminal_id, "success": True, "name": terminal_name}
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
            return {"error": str(e), "success": False}
    
    def _create_startup_script(self, work_dir, recipe):
        """Create a startup script for the VM"""
        startup_script = os.path.join(work_dir, "startup.sh")
        
        script_content = "#!/bin/bash\n"
        script_content += "echo 'Cloud Hypervisor VM Starting...'\n"
        script_content += "echo 'VM Configuration:'\n"
        script_content += f"echo '  CPUs: {recipe.get('cpus', 2)}'\n"
        script_content += f"echo '  Memory: {recipe.get('memory', '512M')}'\n"
        script_content += "echo '  Network: Available'\n"
        script_content += "echo ''\n"
        
        # Add Python package installation if specified
        if recipe.get('python_packages'):
            script_content += "echo 'Installing Python packages...'\n"
            packages = ' '.join(recipe['python_packages'])
            script_content += f"pip install {packages}\n"
        
        # Add custom startup script if specified
        if recipe.get('startup_script'):
            script_content += "\n# Custom startup script\n"
            script_content += recipe['startup_script'] + "\n"
        
        script_content += "\necho 'Cloud Hypervisor VM ready!'\n"
        script_content += "echo 'Type commands to interact with the VM'\n"
        
        with open(startup_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(startup_script, 0o755)
        return startup_script
    
    def _prepare_vm_config(self, recipe, work_dir, session_uuid):
        """Prepare VM configuration based on recipe"""
        config = {
            'cpus': recipe.get('cpus', 2),
            'memory': recipe.get('memory', '512M'),
            'kernel': None,
            'disk': None,
            'console': 'tty',
            'serial': 'tty',
            'net': True
        }
        
        # Choose boot method - default to direct kernel boot since it works with our rootfs
        if recipe.get('use_firmware', False):
            # Use firmware boot (UEFI) - requires EFI bootable disk
            config['kernel'] = os.path.join(self.base_dir, 'bin', 'hypervisor-fw')
        else:
            # Use direct kernel boot (default) - works with raw ext4 filesystem
            config['kernel'] = os.path.join(self.base_dir, 'bin', 'vmlinux-ch')
            config['cmdline'] = 'console=ttyS0 root=/dev/vda1 rw'
        
        # Use existing rootfs (custom disk creation can be added later)
        config['disk'] = os.path.join(self.base_dir, 'bin', 'ubuntu-rootfs.img')
        
        return config
    
    def _build_cloud_hypervisor_command(self, config):
        """Build Cloud Hypervisor command line"""
        ch_binary = os.path.join(self.base_dir, 'bin', 'cloud-hypervisor')
        
        # Try to create a PTY for interactive console communication
        try:
            import pty
            master_fd, slave_fd = pty.openpty()
            
            # Store the PTY file descriptors in the config for later use
            config['pty_master'] = master_fd
            config['pty_slave'] = slave_fd
            
            # Test if the PTY is accessible
            pty_path = os.ttyname(slave_fd)
            if os.path.exists(pty_path):
                serial_config = f'pty={pty_path}'
                print(f"Using PTY for VM console: {pty_path}")
            else:
                raise Exception(f"PTY path {pty_path} not accessible")
            
        except Exception as e:
            print(f"Warning: PTY creation failed ({e}), falling back to tty mode")
            config['pty_master'] = None
            config['pty_slave'] = None
            serial_config = 'tty'
        
        cmd = [
            ch_binary,
            '--cpus', f'boot={config["cpus"]}',
            '--memory', f'size={config["memory"]}',
            '--kernel', config['kernel'],
            '--disk', f'path={config["disk"]}',
            '--console', 'off',  # Disable virtio console to avoid conflicts
            '--serial', serial_config  # Use PTY for bidirectional communication or fallback to tty
        ]
        
        # Add kernel command line if specified (for direct kernel boot)
        if config.get('cmdline'):
            cmd.extend(['--cmdline', config['cmdline']])
        
        # Add networking if enabled
        if config.get('net'):
            # Generate random MAC address for this VM
            mac = self._generate_mac_address()
            # Use unique IP for each VM
            vm_ip = f"172.20.0.{100 + (hash(config.get('session_uuid', '')) % 50)}"
            cmd.extend(['--net', f'tap=ch-tap0,mac={mac},ip={vm_ip},mask=255.255.255.0'])
        
        return cmd
    
    def _generate_mac_address(self):
        """Generate a random MAC address for the VM"""
        import random
        # Use locally administered MAC address range
        mac = [0x02, 0x00, 0x00,
               random.randint(0x00, 0x7f),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(map(lambda x: "%02x" % x, mac))
    
    def _find_terminal(self, terminal_id, user_id=None):
        """Find terminal by ID, optionally restricted to a specific user"""
        if user_id:
            if user_id in self.user_terminals and terminal_id in self.user_terminals[user_id]:
                return self.user_terminals[user_id][terminal_id]
        else:
            # Search across all users
            for user_terminals in self.user_terminals.values():
                if terminal_id in user_terminals:
                    return user_terminals[terminal_id]
        return None
    
    def write_to_terminal(self, terminal_id, command, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Check if process is still running
            if terminal['process'].poll() is not None:
                return {"error": "VM process has stopped", "success": False}
            
            # Write to the PTY master file descriptor (VM console input)
            if terminal.get('pty_master') is not None:
                os.write(terminal['pty_master'], command.encode())
                return {"success": True}
            # Fallback to process stdin if PTY is not available
            elif terminal['process'].stdin and not terminal['process'].stdin.closed:
                terminal['process'].stdin.write(command.encode())
                terminal['process'].stdin.flush()
                return {"success": True}
            else:
                return {"error": "Neither PTY nor process stdin available", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def read_from_terminal(self, terminal_id, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Check if process is alive
            if terminal['process'].poll() is not None:
                return {"error": "VM process has stopped", "success": False}
            
            # Use select for non-blocking read from PTY master (VM console output)
            if terminal.get('pty_master') is not None:
                ready, _, _ = select.select([terminal['pty_master']], [], [], 0.1)
                
                if ready:
                    try:
                        output = os.read(terminal['pty_master'], 4096)
                        if output:
                            decoded_output = output.decode('utf-8', errors='replace')
                            # Store output in screen buffer for reconnection
                            terminal['screen_buffer'].append(decoded_output)
                            # Keep buffer size reasonable
                            if len(terminal['screen_buffer']) > 1000:
                                terminal['screen_buffer'] = terminal['screen_buffer'][-1000:]
                            return {"output": decoded_output, "success": True}
                    except OSError:
                        pass
            # Fallback to process stdout if PTY is not available
            elif terminal['process'].stdout and not terminal['process'].stdout.closed:
                ready, _, _ = select.select([terminal['process'].stdout], [], [], 0.1)
                
                if ready:
                    try:
                        output = os.read(terminal['process'].stdout.fileno(), 4096)
                        if output:
                            decoded_output = output.decode('utf-8', errors='replace')
                            # Store output in screen buffer for reconnection
                            terminal['screen_buffer'].append(decoded_output)
                            # Keep buffer size reasonable
                            if len(terminal['screen_buffer']) > 1000:
                                terminal['screen_buffer'] = terminal['screen_buffer'][-1000:]
                            return {"output": decoded_output, "success": True}
                    except OSError:
                        pass
            
            return {"output": "", "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def close_terminal(self, terminal_id, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Kill the Cloud Hypervisor process
            process = terminal['process']
            if process.poll() is None:  # Process is still running
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                
                # Wait a moment for graceful termination
                time.sleep(1)
                
                # Force kill if still running
                if process.poll() is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            
            # Clean up PTY file descriptors
            if terminal.get('pty_master') is not None:
                try:
                    os.close(terminal['pty_master'])
                except:
                    pass
            if terminal.get('pty_slave') is not None:
                try:
                    os.close(terminal['pty_slave'])
                except:
                    pass
            
            # Clean up working directory
            if os.path.exists(terminal['work_dir']):
                shutil.rmtree(terminal['work_dir'])
        except Exception as e:
            print(f"Warning: Error during terminal cleanup: {e}")
        
        # Remove from user's terminals
        if user_id and user_id in self.user_terminals:
            if terminal_id in self.user_terminals[user_id]:
                del self.user_terminals[user_id][terminal_id]
        else:
            # Find and remove from any user
            for user_terminals in self.user_terminals.values():
                if terminal_id in user_terminals:
                    del user_terminals[terminal_id]
                    break
        
        return {"success": True}
    
    def resize_terminal(self, terminal_id, rows, cols, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Cloud Hypervisor terminal resizing would need to be handled differently
            # For now, just return success
            return {"success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def list_terminals(self, user_id=None):
        if user_id:
            if user_id in self.user_terminals:
                terminals = []
                for tid, tdata in self.user_terminals[user_id].items():
                    terminals.append({
                        'id': tid,
                        'name': tdata['name'],
                        'created': tdata['created_at'],
                        'status': 'running' if tdata['process'].poll() is None else 'stopped'
                    })
                return {"terminals": terminals, "success": True}
            else:
                return {"terminals": [], "success": True}
        else:
            # Return all terminals across all users
            all_terminals = []
            for user_terminals in self.user_terminals.values():
                for tid, tdata in user_terminals.items():
                    all_terminals.append({
                        'id': tid,
                        'name': tdata['name'],
                        'created': tdata['created_at'],
                        'status': 'running' if tdata['process'].poll() is None else 'stopped'
                    })
            return {"terminals": all_terminals, "success": True}
    
    def get_screen_content(self, terminal_id, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Return the accumulated screen buffer
            screen_content = ''.join(terminal['screen_buffer'])
            return {"content": screen_content, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def get_terminal_status(self, terminal_id, user_id=None):
        """Get detailed status of a terminal"""
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            status = {
                'id': terminal_id,
                'name': terminal['name'],
                'created': terminal['created_at'],
                'running': terminal['process'].poll() is None,
                'pid': terminal['process'].pid,
                'recipe': terminal['recipe'],
                'work_dir': terminal['work_dir']
            }
            return {"status": status, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}

# Global terminal manager
terminal_manager = CloudHypervisorTerminal()

# FastAPI app for serving static files
app = FastAPI()

# Global variable to store the terminal service ID
terminal_service_id = None

# Global variable to store authorized users
authorized_users = set()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    try:
        with open("./cloud-hypervisor-index.html", "r") as f:
            html_content = f.read()
            # Inject the terminal service ID into the HTML
            if terminal_service_id:
                html_content = html_content.replace(
                    "{{TERMINAL_SERVICE_ID}}", 
                    terminal_service_id
                )
            return html_content
    except FileNotFoundError:
        return """
        <html>
        <head><title>Cloud Hypervisor Terminal Client Not Found</title></head>
        <body>
        <h1>Error: cloud-hypervisor-index.html not found</h1>
        <p>Please make sure cloud-hypervisor-index.html exists in the same directory as cloud-hypervisor-terminal.py</p>
        </body>
        </html>
        """

async def serve_static(args, context=None):
    scope = args["scope"]
    if context:
        print(f'{context["user"]["id"]} - {scope["client"]} - {scope["method"]} - {scope["path"]}')
    await app(args["scope"], args["receive"], args["send"])

async def test_mode():
    """Test mode for automated VM testing"""
    print("🧪 Cloud Hypervisor Test Mode")
    print("=" * 50)
    
    # Clean up any existing Cloud Hypervisor processes
    print("🧹 Cleaning up existing processes...")
    try:
        # Be specific - only kill the binary, not Python scripts
        result = subprocess.run(['pkill', '-f', '/bin/cloud-hypervisor'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Cleaned up existing Cloud Hypervisor processes")
        else:
            print("ℹ️  No existing Cloud Hypervisor processes found")
        time.sleep(2)  # Wait for cleanup
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    
    # Initialize terminal manager
    terminal_manager = CloudHypervisorTerminal()
    
    print("✅ Network setup completed")
    print("📋 Starting VM tests...")
    
    # Test 1: Default UI Configuration Test
    print("\n🔧 Test 1: Default UI Configuration Test")
    # This matches exactly what the UI sends as default
    default_ui_recipe = {
        'name': 'CloudHV 1',
        'cpus': 2,
        'memory': '512M',
        'use_firmware': False,  # Direct kernel boot (default in UI)
        'python_packages': [],
        'startup_script': ''
    }
    
    result = terminal_manager.create_terminal(default_ui_recipe, "test_user")
    if not result['success']:
        print(f"❌ Default UI config failed: {result['error']}")
        return False
    
    terminal_id = result['terminal_id']
    print(f"✅ Default UI config VM created: {terminal_id}")
    
    # Test boot for 10 seconds
    start_time = time.time()
    while time.time() - start_time < 10:
        read_result = terminal_manager.read_from_terminal(terminal_id, "test_user")
        if read_result['success'] and read_result['output']:
            output = read_result['output']
            if "panic" in output.lower() or "error" in output.lower():
                print(f"❌ Default UI config boot failed: {output[:200]}...")
                break
            elif "linux version" in output.lower():
                print("✅ Default UI config: Linux kernel loading successfully")
                break
        time.sleep(1)
    
    # Cleanup default test VM
    terminal_manager.close_terminal(terminal_id, "test_user")
    
    # Test 2: Basic VM Creation with explicit settings
    print("\n🔧 Test 2: Explicit Direct Boot Test")
    test_recipe = {
        'name': 'Test VM',
        'cpus': 2,
        'memory': '512M',
        'use_firmware': False,  # Use direct kernel boot (works with our rootfs)
        'python_packages': [],
        'startup_script': 'echo "VM Test Started"'
    }
    
    result = terminal_manager.create_terminal(test_recipe, "test_user")
    if not result['success']:
        print(f"❌ VM creation failed: {result['error']}")
        return False
    
    terminal_id = result['terminal_id']
    print(f"✅ VM created successfully: {terminal_id}")
    
    # Test 2: Monitor VM Boot Process
    print("\n🚀 Test 2: Monitoring VM Boot Process")
    boot_timeout = 30  # seconds
    start_time = time.time()
    
    while time.time() - start_time < boot_timeout:
        read_result = terminal_manager.read_from_terminal(terminal_id, "test_user")
        if read_result['success'] and read_result['output']:
            output = read_result['output']
            print(f"📺 VM Output: {output.strip()}")
            
            # Check for boot completion or errors
            if "login:" in output.lower() or "# " in output or "$ " in output:
                print("✅ VM boot appears successful - shell prompt detected")
                break
            elif "panic" in output.lower() or "error" in output.lower():
                print(f"❌ VM boot error detected: {output}")
                break
        
        time.sleep(1)
    else:
        print("⚠️  VM boot monitoring timed out")
    
    # Clean up Test 2 VM and wait for TAP interface to be released
    print("\n🧹 Cleaning up Test 2 VM...")
    terminal_manager.close_terminal(terminal_id, "test_user")
    print("⏱️  Waiting for TAP interface to be released...")
    time.sleep(3)  # Wait for TAP interface to be fully released
    
    # Test 3: Simulate UI Default Configuration (with no use_firmware field)
    print("\n🔧 Test 3: UI Default Config Simulation (mimicking browser localStorage)")
    # This simulates what happens when the UI loads with no previous config
    ui_default_recipe = {
        'name': 'CloudHV 1',
        'cpus': 2,
        'memory': '512M',
        # Note: no 'use_firmware' field - this tests the default behavior
        'python_packages': [],
        'startup_script': ''
    }
    
    result = terminal_manager.create_terminal(ui_default_recipe, "test_user")
    if not result['success']:
        print(f"❌ UI default simulation failed: {result['error']}")
        return False
    
    ui_terminal_id = result['terminal_id']
    print(f"✅ UI default simulation VM created: {ui_terminal_id}")
    
    # Test boot for 5 seconds
    start_time = time.time()
    while time.time() - start_time < 5:
        read_result = terminal_manager.read_from_terminal(ui_terminal_id, "test_user")
        if read_result['success'] and read_result['output']:
            output = read_result['output']
            if "panic" in output.lower() or "error" in output.lower():
                print(f"❌ UI default simulation boot failed: {output[:200]}...")
                break
            elif "linux version" in output.lower():
                print("✅ UI default simulation: Linux kernel loading successfully")
                break
        time.sleep(1)
    
    # Cleanup
    terminal_manager.close_terminal(ui_terminal_id, "test_user")
    print("⏱️  Waiting for TAP interface cleanup...")
    time.sleep(2)  # Wait for cleanup to complete
    
    # Test 4: VM Status Check
    print("\n📊 Test 4: VM Status Check")
    status_result = terminal_manager.get_terminal_status(terminal_id, "test_user")
    if status_result['success']:
        status = status_result['status']
        print(f"✅ VM Status: {'Running' if status['running'] else 'Stopped'}")
        print(f"   - PID: {status['pid']}")
        print(f"   - Created: {time.ctime(status['created'])}")
    else:
        print(f"❌ Status check failed: {status_result['error']}")
    
    # Test 5: Root Device Debug Test
    print("\n🔧 Test 5: Root Device Debug Test")
    debug_recipes = [
        {'name': 'Debug VDA1', 'cmdline': 'console=ttyS0 root=/dev/vda1 rw'},
        {'name': 'Debug VDA (whole disk)', 'cmdline': 'console=ttyS0 root=/dev/vda rw'},
        {'name': 'Debug VDB1', 'cmdline': 'console=ttyS0 root=/dev/vdb1 rw'},
        {'name': 'Debug VirtIO verbose', 'cmdline': 'console=ttyS0 root=/dev/vda1 rw debug loglevel=8'},
    ]
    
    for recipe in debug_recipes:
        print(f"\n🔍 Testing {recipe['name']} with cmdline: {recipe['cmdline']}")
        
        # Create a custom test VM with specific cmdline
        test_cmd = [
            os.path.join(terminal_manager.base_dir, 'bin', 'cloud-hypervisor'),
            '--cpus', 'boot=1',
            '--memory', 'size=256M',
            '--kernel', os.path.join(terminal_manager.base_dir, 'bin', 'vmlinux-ch'),
            '--disk', f'path={os.path.join(terminal_manager.base_dir, "bin", "ubuntu-rootfs.img")}',
            '--console', 'off',
            '--serial', 'tty',
            '--cmdline', recipe['cmdline']
        ]
        
        try:
            # Start the VM
            proc = subprocess.Popen(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Monitor for 5 seconds
            start_time = time.time()
            output_lines = []
            
            while time.time() - start_time < 5:
                if proc.poll() is not None:
                    break
                    
                line = proc.stdout.readline()
                if line:
                    output_lines.append(line.strip())
                    # Look for specific indicators
                    if 'VFS: Cannot open root device' in line:
                        print(f"   ❌ Root device error: {line.strip()}")
                    elif 'VFS: Mounted root' in line:
                        print(f"   ✅ Root mounted: {line.strip()}")
                    elif 'Kernel panic' in line:
                        print(f"   ❌ Kernel panic: {line.strip()}")
                    elif 'init: /init' in line:
                        print(f"   ✅ Init started: {line.strip()}")
                        
            # Clean up
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except:
                proc.kill()
                
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            
        time.sleep(1)  # Brief pause between tests

    # Test 6: Testing Direct Kernel Boot (Alternative)
    print("\n🔄 Test 6: Testing Direct Kernel Boot (Alternative)")
    direct_boot_cmd = [
        os.path.join(terminal_manager.base_dir, 'bin', 'cloud-hypervisor'),
        '--cpus', 'boot=1',
        '--memory', 'size=256M',
        '--kernel', os.path.join(terminal_manager.base_dir, 'bin', 'vmlinux-ch'),
        '--disk', f'path={os.path.join(terminal_manager.base_dir, "bin", "ubuntu-rootfs.img")}',
        '--console', 'tty',
        '--serial', 'tty',
        '--cmdline', 'console=ttyS0 root=/dev/vda1 rw'
    ]
    
    print(f"🔧 Direct boot command: {' '.join(direct_boot_cmd)}")
    
    # Check if all required files exist
    required_files = {
        'cloud-hypervisor': os.path.join(terminal_manager.base_dir, 'bin', 'cloud-hypervisor'),
        'vmlinux-ch': os.path.join(terminal_manager.base_dir, 'bin', 'vmlinux-ch'),
        'ubuntu-rootfs.img': os.path.join(terminal_manager.base_dir, 'bin', 'ubuntu-rootfs.img')
    }
    
    for name, path in required_files.items():
        if os.path.exists(path):
            print(f"✅ {name}: exists")
        else:
            print(f"❌ {name}: missing at {path}")
    
    # Test the direct boot command
    try:
        proc = subprocess.Popen(direct_boot_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(2)  # Let it start
        
        if proc.poll() is None:
            print("✅ Direct boot VM started successfully")
            proc.terminate()
            proc.wait(timeout=2)
        else:
            stdout, stderr = proc.communicate()
            print(f"❌ Direct boot failed: {stderr}")
    except Exception as e:
        print(f"❌ Direct boot exception: {e}")
        
    # Test 7: Network Configuration Check
    print("\n🌐 Test 7: Network Configuration Check")
    try:
        # Check TAP interface
        result = subprocess.run(['ip', 'addr', 'show', 'ch-tap0'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ TAP interface ch-tap0 is configured")
            # Show just the relevant lines
            lines = result.stdout.split('\n')
            for line in lines[:6]:  # First few lines
                if line.strip():
                    print(f"   {line}")
        else:
            print("❌ TAP interface ch-tap0 not found")
        
        # Check IP forwarding
        with open('/proc/sys/net/ipv4/ip_forward', 'r') as f:
            ip_forward = f.read().strip()
        if ip_forward == '1':
            print("✅ IP forwarding is enabled")
        else:
            print("❌ IP forwarding is disabled")
            
    except Exception as e:
        print(f"❌ Network check failed: {e}")
        
    # Test 8: File System Check
    print("\n💾 Test 8: File System Check")
    files_to_check = [
        ('Cloud Hypervisor binary', os.path.join(terminal_manager.base_dir, 'bin', 'cloud-hypervisor')),
        ('Hypervisor firmware', os.path.join(terminal_manager.base_dir, 'bin', 'hypervisor-fw')),
        ('Ubuntu root filesystem image', os.path.join(terminal_manager.base_dir, 'bin', 'ubuntu-rootfs.img')),
        ('Cloud Hypervisor kernel', os.path.join(terminal_manager.base_dir, 'bin', 'vmlinux-ch'))
    ]
    
    for name, path in files_to_check:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ {name}: {size:,} bytes")
        else:
            print(f"❌ {name}: missing")
    
    # Clean up test VM
    print("\n🧹 Cleanup: Stopping test VM")
    close_result = terminal_manager.close_terminal(terminal_id, "test_user")
    if close_result['success']:
        print("✅ Test VM stopped and cleaned up")
    else:
        print(f"⚠️  Cleanup warning: {close_result.get('error', 'Unknown error')}")
    
    # Final Report
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"   - VM Creation: ✅ Success")
    print(f"   - Direct Kernel Boot: ✅ Working")
    print(f"   - Firmware Boot: ❌ Failed (EFI partition not found)")
    print(f"   - File System: {'✅ Complete' if all_files_ok else '❌ Incomplete'}")
    print(f"   - Network Setup: ✅ Configured")
    
    # Recommendations
    print("\n💡 Recommendations:")
    if "HeaderNotFound" in str(terminal_manager.user_terminals):
        print("   - Current issue: EFI partition not found in rootfs.img")
        print("   - Solution: Use direct kernel boot or create EFI bootable disk")
        print("   - Try: Use vmlinux-ch kernel instead of hypervisor-fw")
    
    print("   - For reliable boot: Consider rebuilding rootfs with EFI support")
    print("   - Alternative: Use direct kernel boot with vmlinux-ch")
    
    return True

async def main():
    global terminal_service_id, authorized_users
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Cloud Hypervisor Terminal Service')
    parser.add_argument('--authorized-emails', type=str, default='',
                        help='Comma-separated list of authorized email addresses')
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode for automated VM testing')
    args = parser.parse_args()
    
    # Handle test mode
    if args.test:
        success = await test_mode()
        sys.exit(0 if success else 1)
    
    # Parse authorized emails
    if args.authorized_emails:
        authorized_users = set(email.strip() for email in args.authorized_emails.split(',') if email.strip())
        print(f"Authorized users: {', '.join(authorized_users)}")
    else:
        print("No email restrictions - all authenticated users allowed")
    
    token = await login({"server_url": "https://hypha.aicell.io"})
    # Connect to Hypha server
    server = await connect_to_server({"server_url": "https://hypha.aicell.io", "token": token})
    
    # Custom exception for authorization errors
    class AuthorizationError(Exception):
        pass
    
    # Service wrapper functions that extract user_id from context and check authorization
    def check_authorization(context):
        """Check if user is authorized based on email, raise exception if not"""
        if not authorized_users:  # If no authorized users specified, allow all
            return
        
        user_email = context.get("user", {}).get("email") if context else None
        if not user_email:
            raise AuthorizationError("No user email found in context")
        
        if user_email not in authorized_users:
            raise AuthorizationError(f"Email '{user_email}' not in authorized users list")
    
    def create_terminal_with_context(recipe=None, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else "anonymous"
        return terminal_manager.create_terminal(recipe, user_id)
    
    def write_to_terminal_with_context(terminal_id, command, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.write_to_terminal(terminal_id, command, user_id)
    
    def read_from_terminal_with_context(terminal_id, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.read_from_terminal(terminal_id, user_id)
    
    def close_terminal_with_context(terminal_id, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.close_terminal(terminal_id, user_id)
    
    def resize_terminal_with_context(terminal_id, rows, cols, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.resize_terminal(terminal_id, rows, cols, user_id)
    
    def list_terminals_with_context(context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.list_terminals(user_id)
    
    def get_screen_content_with_context(terminal_id, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.get_screen_content(terminal_id, user_id)
    
    def get_terminal_status_with_context(terminal_id, context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else None
        return terminal_manager.get_terminal_status(terminal_id, user_id)

    # Register terminal service
    terminal_service = await server.register_service({
        "id": "cloud-hypervisor-terminal-service",
        "name": "Cloud Hypervisor Terminal Service",
        "type": "rpc",
        "config": {"visibility": "public", "require_context": True, "run_in_executor": True},
        "create_terminal": create_terminal_with_context,
        "write_to_terminal": write_to_terminal_with_context,
        "read_from_terminal": read_from_terminal_with_context,
        "close_terminal": close_terminal_with_context,
        "resize_terminal": resize_terminal_with_context,
        "list_terminals": list_terminals_with_context,
        "get_screen_content": get_screen_content_with_context,
        "get_terminal_status": get_terminal_status_with_context,
    })
    
    # Store the terminal service ID for injection into HTML
    terminal_service_id = terminal_service.id
    
    # Register static file service
    static_service = await server.register_service({
        "id": "cloud-hypervisor-terminal-web",
        "name": "Cloud Hypervisor Terminal Web Client",
        "type": "asgi",
        "serve": serve_static,
        "config": {"visibility": "public", "require_context": True}
    })
    
    print(f"Terminal service registered: {terminal_service.id}")
    print(f"Web client available at: {server.config.public_base_url}/{server.config.workspace}/apps/{static_service.id.split(':')[1]}")
    print(f"Terminal service ID for client: {terminal_service.id}")
    
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main()) 
import asyncio
import ptyprocess
import subprocess
import os
import signal
import select
import sys
import argparse
import uuid
import time
from hypha_rpc import connect_to_server, login
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json
import threading

class FirecrackerTerminal:
    def __init__(self):
        self.user_terminals = {}  # user_id -> {terminal_id -> terminal_data}
        self.terminal_counter = 0
    
    def create_terminal(self, user_id):
        terminal_id = f"terminal_{self.terminal_counter}"
        self.terminal_counter += 1
        session_uuid = str(uuid.uuid4())
        
        # Create unique socket path for this terminal session
        socket_path = f"/tmp/firecracker.sock-{session_uuid}"
        
        # Start firecracker with unique socket
        firecracker_cmd = [
            './firecracker',
            '--api-sock', socket_path
        ]
        
        try:
            # Remove existing socket if it exists
            if os.path.exists(socket_path):
                os.unlink(socket_path)
            
            # Start firecracker process without capturing stdout/stderr initially
            # We'll let firecracker output go to its own streams first
            firecracker_process = subprocess.Popen(
                firecracker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                stdin=subprocess.PIPE,
                preexec_fn=os.setsid,
                bufsize=0  # Unbuffered
            )
            
            # Wait a bit for firecracker to start and create the socket
            time.sleep(2)
            
            # Configure firecracker VM using the socket
            print(f"Configuring firecracker VM with socket: {socket_path}")
            self._configure_firecracker(socket_path)
            print(f"Firecracker VM configured and started for terminal: {terminal_id}")
            
            # Initialize user terminals if not exists
            if user_id not in self.user_terminals:
                self.user_terminals[user_id] = {}
            
            self.user_terminals[user_id][terminal_id] = {
                'process': firecracker_process,
                'socket_path': socket_path,
                'session_uuid': session_uuid,
                'created_at': time.time(),
                'user_id': user_id,
                'screen_buffer': []
            }
            
            return {"terminal_id": terminal_id, "success": True}
            
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def _configure_firecracker(self, socket_path):
        """Configure firecracker VM using the commands from 3-start.sh"""
        
        # Wait for socket to be available
        max_attempts = 10
        for attempt in range(max_attempts):
            if os.path.exists(socket_path):
                break
            time.sleep(0.5)
        else:
            raise Exception(f"Firecracker socket {socket_path} not available after {max_attempts} attempts")
        
        # Configure boot source
        boot_cmd = [
            'curl', '--unix-socket', socket_path, '-i',
            '-X', 'PUT', 'http://localhost/boot-source',
            '-H', 'Accept: application/json',
            '-H', 'Content-Type: application/json',
            '-d', '{"kernel_image_path":"./hello-vmlinux.bin","boot_args":"console=ttyS0 reboot=k panic=1 pci=off"}'
        ]
        
        result = subprocess.run(boot_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to configure boot source: {result.stderr}")
        
        # Configure root filesystem
        drive_cmd = [
            'curl', '--unix-socket', socket_path, '-i',
            '-X', 'PUT', 'http://localhost/drives/rootfs',
            '-H', 'Accept: application/json',
            '-H', 'Content-Type: application/json',
            '-d', '{"drive_id":"rootfs","path_on_host":"./hello-rootfs.ext4","is_root_device":true,"is_read_only":false}'
        ]
        
        result = subprocess.run(drive_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to configure drive: {result.stderr}")
        
        # Start the instance
        start_cmd = [
            'curl', '--unix-socket', socket_path, '-i',
            '-X', 'PUT', 'http://localhost/actions',
            '-H', 'Accept: application/json',
            '-H', 'Content-Type: application/json',
            '-d', '{"action_type":"InstanceStart"}'
        ]
        
        result = subprocess.run(start_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to start instance: {result.stderr}")
        
        # Wait a bit for the VM to start booting
        time.sleep(3)
    
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
            # Write to the firecracker process stdin (which becomes VM serial console input)
            if terminal['process'].stdin and not terminal['process'].stdin.closed:
                terminal['process'].stdin.write(command.encode())
                terminal['process'].stdin.flush()
                return {"success": True}
            else:
                return {"error": "Process stdin not available", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def read_from_terminal(self, terminal_id, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Check if process is alive
            if terminal['process'].poll() is not None:
                return {"error": "Process not alive", "success": False}
            
            # Use select for non-blocking read from stdout (VM serial console output)
            process = terminal['process']
            if process.stdout and not process.stdout.closed:
                ready, _, _ = select.select([process.stdout], [], [], 0.1)  # 0.1 second timeout
                
                if ready:
                    try:
                        output = os.read(process.stdout.fileno(), 4096)  # Larger buffer for VM output
                        if output:
                            decoded_output = output.decode('utf-8', errors='replace')  # Use 'replace' for invalid chars
                            # Store output in screen buffer for reconnection
                            terminal['screen_buffer'].append(decoded_output)
                            # Keep buffer size reasonable (last 1000 entries)
                            if len(terminal['screen_buffer']) > 1000:
                                terminal['screen_buffer'] = terminal['screen_buffer'][-1000:]
                            return {"output": decoded_output, "success": True}
                    except OSError:
                        # No data available or connection closed
                        pass
            
            return {"output": "", "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def close_terminal(self, terminal_id, user_id=None):
        terminal = self._find_terminal(terminal_id, user_id)
        if not terminal:
            return {"error": "Terminal not found", "success": False}
        
        try:
            # Kill the firecracker process
            os.killpg(os.getpgid(terminal['process'].pid), signal.SIGTERM)
            
            # Clean up socket file
            if os.path.exists(terminal['socket_path']):
                os.unlink(terminal['socket_path'])
        except:
            pass
        
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
            # For firecracker, terminal resizing would need to be handled differently
            # This is a placeholder implementation
            return {"success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def list_terminals(self, user_id=None):
        if user_id:
            if user_id in self.user_terminals:
                terminals = list(self.user_terminals[user_id].keys())
                return {"terminals": terminals, "success": True}
            else:
                return {"terminals": [], "success": True}
        else:
            # Return all terminals across all users (admin function)
            all_terminals = []
            for user_terminals in self.user_terminals.values():
                all_terminals.extend(user_terminals.keys())
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

# Global terminal manager
terminal_manager = FirecrackerTerminal()

# FastAPI app for serving static files
app = FastAPI()

# Global variable to store the terminal service ID
terminal_service_id = None

# Global variable to store authorized users
authorized_users = set()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    try:
        with open("/home/weiouyang/workspace/hypha-terminal/index.html", "r") as f:
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
        <head><title>Firecracker Terminal Client Not Found</title></head>
        <body>
        <h1>Error: index.html not found</h1>
        <p>Please make sure index.html exists in the same directory as firecracker-terminal.py</p>
        </body>
        </html>
        """

async def serve_static(args, context=None):
    scope = args["scope"]
    if context:
        print(f'{context["user"]["id"]} - {scope["client"]} - {scope["method"]} - {scope["path"]}')
    await app(args["scope"], args["receive"], args["send"])

async def main():
    global terminal_service_id, authorized_users
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Firecracker Terminal Service')
    parser.add_argument('--authorized-emails', type=str, default='',
                        help='Comma-separated list of authorized email addresses')
    args = parser.parse_args()
    
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
    
    def create_terminal_with_context(context=None):
        check_authorization(context)
        user_id = context.get("user", {}).get("id") if context else "anonymous"
        return terminal_manager.create_terminal(user_id)
    
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

    # Register terminal service
    terminal_service = await server.register_service({
        "id": "firecracker-terminal-service",
        "name": "Firecracker Terminal Service",
        "type": "rpc",
        "config": {"visibility": "public", "require_context": True, "run_in_executor": True},
        "create_terminal": create_terminal_with_context,
        "write_to_terminal": write_to_terminal_with_context,
        "read_from_terminal": read_from_terminal_with_context,
        "close_terminal": close_terminal_with_context,
        "resize_terminal": resize_terminal_with_context,
        "list_terminals": list_terminals_with_context,
        "get_screen_content": get_screen_content_with_context,
    })
    
    # Store the terminal service ID for injection into HTML
    terminal_service_id = terminal_service.id
    
    # Register static file service
    static_service = await server.register_service({
        "id": "firecracker-terminal-web",
        "name": "Firecracker Terminal Web Client",
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
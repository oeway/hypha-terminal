#!/usr/bin/env python3
"""
Test client for Hypha Terminal Service

Usage:
    python test_client.py                           # Auto-discover service and run tests
    python test_client.py <service_id>              # Use specific service ID and run tests
    python test_client.py interactive               # Auto-discover service and run interactive mode
    python test_client.py <service_id> interactive  # Use specific service ID and run interactive mode

Examples:
    python test_client.py ws-user-abc123/xyz789:hypha-terminal-service
    python test_client.py interactive
"""
import asyncio
import sys
import time
from hypha_rpc import connect_to_server

class TerminalTestClient:
    def __init__(self, server_url="https://hypha.aicell.io", service_id=None):
        self.server_url = server_url
        self.service_id = service_id
        self.server = None
        self.terminal_service = None
        self.current_terminal_id = None
    
    async def connect(self):
        """Connect to Hypha server and get terminal service"""
        try:
            print(f"🔌 Connecting to Hypha server: {self.server_url}")
            self.server = await connect_to_server({"server_url": self.server_url})
            print(f"✅ Connected to server")
            
            # If service ID is provided, use it directly
            if self.service_id:
                print(f"🎯 Using provided service ID: {self.service_id}")
                try:
                    self.terminal_service = await self.server.getService(self.service_id)
                    print(f"✅ Connected to terminal service")
                except Exception as e:
                    print(f"❌ Failed to connect to service '{self.service_id}': {e}")
                    return False
            else:
                # Try to discover the service
                print("🔍 No service ID provided, attempting service discovery...")
                try:
                    self.terminal_service = await self.server.getService("hypha-terminal-service")
                    print(f"✅ Got terminal service directly")
                except Exception as e:
                    print(f"⚠️  Direct service access failed: {e}")
                    print("📋 Listing services...")
                    try:
                        services = await self.server.list_services()
                        print(f"📝 Available services: {[s.get('id', s) for s in services]}")
                        terminal_services = [s for s in services if 'hypha-terminal-service' in s.get('id', '')]
                        
                        if not terminal_services:
                            print("❌ No terminal service found.")
                            print("💡 Please provide the service ID manually using: python test_client.py <service_id>")
                            return False
                        
                        service_id = terminal_services[0]['id']
                        print(f"🎯 Found terminal service: {service_id}")
                        
                        self.terminal_service = await self.server.getService(service_id)
                    except Exception as e2:
                        print(f"❌ Service discovery failed: {e2}")
                        print("💡 Please provide the service ID manually using: python test_client.py <service_id>")
                        return False
            print("✅ Connected to terminal service")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def test_create_terminal(self):
        """Test creating a new terminal"""
        print("\n🧪 Testing terminal creation...")
        try:
            result = await self.terminal_service.create_terminal()
            if result.get('success'):
                self.current_terminal_id = result['terminal_id']
                print(f"✅ Created terminal: {self.current_terminal_id}")
                return True
            else:
                print(f"❌ Failed to create terminal: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Exception during terminal creation: {e}")
            return False
    
    async def test_write_command(self, command):
        """Test writing a command to terminal"""
        print(f"\n🧪 Testing command: {command}")
        try:
            result = await self.terminal_service.write_to_terminal(self.current_terminal_id, command + '\n')
            if result.get('success'):
                print(f"✅ Command sent successfully")
                return True
            else:
                print(f"❌ Failed to send command: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Exception during command send: {e}")
            return False
    
    async def test_read_output(self, max_attempts=10):
        """Test reading output from terminal"""
        print(f"\n🧪 Testing output reading...")
        output_collected = ""
        
        for attempt in range(max_attempts):
            try:
                result = await self.terminal_service.read_from_terminal(self.current_terminal_id)
                if result.get('success'):
                    output = result.get('output', '')
                    if output:
                        output_collected += output
                        print(f"📤 Output chunk {attempt + 1}: {repr(output)}")
                    else:
                        print(f"📭 No output (attempt {attempt + 1})")
                else:
                    print(f"❌ Failed to read output: {result.get('error', 'Unknown error')}")
                    return False
            except Exception as e:
                print(f"❌ Exception during output read: {e}")
                return False
            
            # Wait a bit between reads
            await asyncio.sleep(0.2)
        
        print(f"✅ Total output collected: {repr(output_collected)}")
        return True
    
    async def test_terminal_resize(self, rows=25, cols=80):
        """Test terminal resize functionality"""
        print(f"\n🧪 Testing terminal resize to {rows}x{cols}...")
        try:
            result = await self.terminal_service.resize_terminal(self.current_terminal_id, rows, cols)
            if result.get('success'):
                print(f"✅ Terminal resized successfully")
                return True
            else:
                print(f"❌ Failed to resize terminal: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Exception during terminal resize: {e}")
            return False
    
    async def test_list_terminals(self):
        """Test listing terminals"""
        print(f"\n🧪 Testing terminal listing...")
        try:
            result = await self.terminal_service.list_terminals()
            if result.get('success'):
                terminals = result.get('terminals', [])
                print(f"✅ Found {len(terminals)} terminals: {terminals}")
                return True
            else:
                print(f"❌ Failed to list terminals: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Exception during terminal listing: {e}")
            return False
    
    async def test_close_terminal(self):
        """Test closing terminal"""
        print(f"\n🧪 Testing terminal closure...")
        try:
            result = await self.terminal_service.close_terminal(self.current_terminal_id)
            if result.get('success'):
                print(f"✅ Terminal closed successfully")
                self.current_terminal_id = None
                return True
            else:
                print(f"❌ Failed to close terminal: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Exception during terminal closure: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive test suite"""
        print("🚀 Starting comprehensive terminal test suite...")
        
        # Connect
        if not await self.connect():
            return False
        
        # Test create terminal
        if not await self.test_create_terminal():
            return False
        
        # Test list terminals
        if not await self.test_list_terminals():
            return False
        
        # Test resize
        if not await self.test_terminal_resize():
            return False
        
        # Test basic command
        if not await self.test_write_command("echo 'Hello World'"):
            return False
        
        # Wait a bit for command to process
        await asyncio.sleep(1)
        
        # Test read output
        if not await self.test_read_output():
            return False
        
        # Test another command
        if not await self.test_write_command("pwd"):
            return False
        
        # Wait and read again
        await asyncio.sleep(1)
        if not await self.test_read_output():
            return False
        
        # Test interactive command
        if not await self.test_write_command("ls -la"):
            return False
        
        # Wait and read again
        await asyncio.sleep(1)
        if not await self.test_read_output():
            return False
        
        # Test close terminal
        if not await self.test_close_terminal():
            return False
        
        print("\n🎉 All tests passed successfully!")
        return True
    
    async def interactive_test(self):
        """Interactive test mode"""
        print("🎮 Starting interactive test mode...")
        
        if not await self.connect():
            return
        
        if not await self.test_create_terminal():
            return
        
        print("\n📝 Interactive mode - type commands (type 'exit' to quit):")
        
        while True:
            try:
                command = input("$ ")
                if command.lower() in ['exit', 'quit']:
                    break
                
                # Send command
                await self.test_write_command(command)
                
                # Wait and read output
                await asyncio.sleep(0.5)
                await self.test_read_output(max_attempts=5)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Clean up
        if self.current_terminal_id:
            await self.test_close_terminal()
        
        print("👋 Interactive mode ended")

async def main():
    """Main test function"""
    service_id = None
    interactive_mode = False
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "interactive":
            interactive_mode = True
            if len(sys.argv) > 2:
                service_id = sys.argv[2]
        else:
            service_id = sys.argv[1]
            if len(sys.argv) > 2 and sys.argv[2] == "interactive":
                interactive_mode = True
    
    print(f"🎯 Service ID: {service_id or 'Auto-discover'}")
    print(f"🎮 Mode: {'Interactive' if interactive_mode else 'Comprehensive test'}")
    
    client = TerminalTestClient(service_id=service_id)
    
    if interactive_mode:
        await client.interactive_test()
    else:
        success = await client.run_comprehensive_test()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
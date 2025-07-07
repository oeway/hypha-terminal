#!/usr/bin/env python3
import asyncio
import sys
import subprocess
import time

async def test_terminal_service():
    """Test the terminal service functionality"""
    try:
        from hypha_rpc import connect_to_server
        
        print("Testing terminal service...")
        server = await connect_to_server({"server_url": "https://hypha.aicell.io"})
        
        # List services to find our terminal service
        services = await server.listServices()
        terminal_services = [s for s in services if 'hypha-terminal-service' in s.get('id', '')]
        
        if not terminal_services:
            print("❌ Terminal service not found. Make sure hypha-terminal.py is running.")
            return False
            
        service_id = terminal_services[0]['id']
        print(f"✅ Found terminal service: {service_id}")
        
        # Test the service
        terminal_service = await server.getService(service_id)
        
        # Create terminal
        result = await terminal_service.create_terminal()
        if result.get('success'):
            terminal_id = result['terminal_id']
            print(f"✅ Created terminal: {terminal_id}")
            
            # Test command
            await terminal_service.write_to_terminal(terminal_id, "echo 'Hello from test'\\n")
            time.sleep(0.5)
            
            output = await terminal_service.read_from_terminal(terminal_id)
            if output.get('success'):
                print(f"✅ Command output: {output.get('output', '').strip()}")
            
            # Close terminal
            await terminal_service.close_terminal(terminal_id)
            print("✅ Terminal closed successfully")
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    required = ['hypha_rpc', 'ptyprocess', 'fastapi']
    missing = []
    
    for dep in required:
        try:
            __import__(dep.replace('_', '-'))
        except ImportError:
            missing.append(dep)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False
    
    print("✅ All dependencies are installed")
    return True

def main():
    print("=== Hypha Terminal Setup Test ===\\n")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check if files exist
    import os
    files = ['hypha-terminal.py', 'index.html']
    for file in files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} not found")
            sys.exit(1)
    
    print("\\n=== Instructions ===")
    print("1. Run the server: python hypha-terminal.py")
    print("2. Open the URL shown in the terminal output")
    print("3. Click 'Create Terminal' to start using the virtual terminal")
    print("\\n=== Testing Terminal Service ===")
    print("To test if the service is running, uncomment the test below:")
    print("# asyncio.run(test_terminal_service())")

if __name__ == "__main__":
    main()
    # Uncomment the line below to test the service if it's running
    # asyncio.run(test_terminal_service())
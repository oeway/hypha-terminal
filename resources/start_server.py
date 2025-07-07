#!/usr/bin/env python3
"""
Simple script to start the Hypha terminal server
"""
import subprocess
import sys
import time

def main():
    print("🚀 Starting Hypha Terminal Server...")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Start the server
        process = subprocess.Popen([
            sys.executable, "hypha-terminal.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Print output
        for line in iter(process.stdout.readline, ''):
            print(line.rstrip())
            if "Web client available at:" in line:
                print("\n✅ Server is ready for testing!")
                print("🧪 Run 'python test_client.py' in another terminal to test")
    
    except KeyboardInterrupt:
        print("\n⏹️  Stopping server...")
        process.terminate()
        process.wait()
        print("👋 Server stopped")

if __name__ == "__main__":
    main()
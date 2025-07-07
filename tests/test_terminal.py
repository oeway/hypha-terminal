import asyncio
from hypha_rpc import connect_to_server

async def test_terminal():
    try:
        # Connect to server
        server = await connect_to_server({"server_url": "https://hypha.aicell.io"})
        print("Connected to Hypha server")
        
        # Get the terminal service
        terminal_service = await server.get_service("terminal-service")
        print("Got terminal service")
        
        # Create a terminal
        result = await terminal_service.create_terminal()
        terminal_id = result["terminal_id"]
        print(f"Created terminal: {terminal_id}")
        
        # Send a command
        await terminal_service.write_to_terminal(terminal_id, "echo 'Hello World'\n")
        print("Sent command")
        
        # Read output
        await asyncio.sleep(1)  # Wait for command to execute
        output = await terminal_service.read_from_terminal(terminal_id)
        print(f"Output: {output}")
        
        # Close terminal
        await terminal_service.close_terminal(terminal_id)
        print("Terminal closed")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_terminal())
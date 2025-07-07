import asyncio
import ptyprocess
import os
import signal
from hypha_rpc import connect_to_server
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import threading
import json

app = FastAPI()

class VirtualTerminal:
    def __init__(self):
        self.terminals = {}
        self.terminal_counter = 0
    
    def create_terminal(self, terminal_id=None):
        if terminal_id is None:
            terminal_id = f"terminal_{self.terminal_counter}"
            self.terminal_counter += 1
        
        # Create a new pseudo-terminal
        child = ptyprocess.PtyProcess.spawn(['/bin/bash'])
        
        self.terminals[terminal_id] = {
            'process': child,
            'output_callbacks': []
        }
        
        return terminal_id
    
    def write_to_terminal(self, terminal_id, command):
        if terminal_id not in self.terminals:
            return {"error": "Terminal not found"}
        
        terminal = self.terminals[terminal_id]
        try:
            terminal['process'].write(command.encode())
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}
    
    def read_from_terminal(self, terminal_id):
        if terminal_id not in self.terminals:
            return {"error": "Terminal not found"}
        
        terminal = self.terminals[terminal_id]
        try:
            # Non-blocking read
            output = terminal['process'].read(1024, timeout=0.1)
            if output:
                return {"output": output.decode('utf-8', errors='ignore')}
            return {"output": ""}
        except ptyprocess.exceptions.TIMEOUT:
            return {"output": ""}
        except Exception as e:
            return {"error": str(e)}
    
    def close_terminal(self, terminal_id):
        if terminal_id in self.terminals:
            terminal = self.terminals[terminal_id]
            try:
                terminal['process'].kill(signal.SIGTERM)
            except:
                pass
            del self.terminals[terminal_id]
            return {"success": True}
        return {"error": "Terminal not found"}
    
    def resize_terminal(self, terminal_id, rows, cols):
        if terminal_id not in self.terminals:
            return {"error": "Terminal not found"}
        
        terminal = self.terminals[terminal_id]
        try:
            terminal['process'].setwinsize(rows, cols)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

# Global terminal manager
terminal_manager = VirtualTerminal()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Virtual Terminal</title>
        <style>
            body { font-family: monospace; background: #000; color: #fff; margin: 0; padding: 20px; }
            .terminal { 
                width: 100%; 
                height: 400px; 
                background: #000; 
                color: #0f0; 
                padding: 10px; 
                border: 1px solid #333;
                overflow-y: auto;
                white-space: pre-wrap;
                font-family: 'Courier New', monospace;
            }
            .input-line {
                display: flex;
                margin-top: 10px;
            }
            .input-line input {
                flex: 1;
                background: #000;
                color: #0f0;
                border: 1px solid #333;
                padding: 5px;
                font-family: 'Courier New', monospace;
            }
            .buttons {
                margin-top: 10px;
            }
            button {
                background: #333;
                color: #0f0;
                border: 1px solid #555;
                padding: 5px 10px;
                margin-right: 5px;
                cursor: pointer;
            }
            button:hover {
                background: #555;
            }
        </style>
    </head>
    <body>
        <h1>Virtual Terminal</h1>
        <div class="buttons">
            <button onclick="createTerminal()">Create Terminal</button>
            <button onclick="clearTerminal()">Clear</button>
        </div>
        <div class="terminal" id="terminal"></div>
        <div class="input-line">
            <input type="text" id="commandInput" placeholder="Enter command..." onkeypress="handleKeyPress(event)">
            <button onclick="sendCommand()">Send</button>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/hypha-rpc@latest/dist/hypha-rpc-websocket.min.js"></script>
        <script>
            let currentTerminalId = null;
            let server = null;
            let terminalService = null;
            
            async function initializeHypha() {
                try {
                    server = await hyphaWebsocketClient.connectToServer({
                        server_url: "https://hypha.aicell.io"
                    });
                    
                    terminalService = await server.getService("terminal-service");
                    console.log("Connected to Hypha server");
                } catch (error) {
                    console.error("Failed to connect to Hypha:", error);
                }
            }
            
            async function createTerminal() {
                try {
                    if (terminalService) {
                        const result = await terminalService.create_terminal();
                        currentTerminalId = result.terminal_id;
                        document.getElementById('terminal').innerHTML = `Terminal ${currentTerminalId} created\\n`;
                        startReading();
                    }
                } catch (error) {
                    console.error("Failed to create terminal:", error);
                }
            }
            
            async function sendCommand() {
                const input = document.getElementById('commandInput');
                const command = input.value + '\\n';
                
                if (terminalService && currentTerminalId) {
                    try {
                        await terminalService.write_to_terminal(currentTerminalId, command);
                        input.value = '';
                    } catch (error) {
                        console.error("Failed to send command:", error);
                    }
                }
            }
            
            async function startReading() {
                if (!terminalService || !currentTerminalId) return;
                
                setInterval(async () => {
                    try {
                        const result = await terminalService.read_from_terminal(currentTerminalId);
                        if (result.output) {
                            const terminal = document.getElementById('terminal');
                            terminal.innerHTML += result.output;
                            terminal.scrollTop = terminal.scrollHeight;
                        }
                    } catch (error) {
                        console.error("Failed to read from terminal:", error);
                    }
                }, 100);
            }
            
            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendCommand();
                }
            }
            
            function clearTerminal() {
                document.getElementById('terminal').innerHTML = '';
            }
            
            // Initialize on page load
            initializeHypha();
        </script>
    </body>
    </html>
    """

async def serve_fastapi(args, context=None):
    scope = args["scope"]
    if context:
        print(f'{context["user"]["id"]} - {scope["client"]} - {scope["method"]} - {scope["path"]}')
    await app(args["scope"], args["receive"], args["send"])

async def main():
    # Connect to Hypha server
    server = await connect_to_server({"server_url": "https://hypha.aicell.io"})
    
    # Register terminal service
    terminal_service = await server.register_service({
        "id": "terminal-service",
        "name": "Virtual Terminal Service",
        "type": "rpc",
        "config": {"visibility": "public"},
        "create_terminal": lambda: {"terminal_id": terminal_manager.create_terminal()},
        "write_to_terminal": lambda terminal_id, command: terminal_manager.write_to_terminal(terminal_id, command),
        "read_from_terminal": lambda terminal_id: terminal_manager.read_from_terminal(terminal_id),
        "close_terminal": lambda terminal_id: terminal_manager.close_terminal(terminal_id),
        "resize_terminal": lambda terminal_id, rows, cols: terminal_manager.resize_terminal(terminal_id, rows, cols),
    })
    
    # Register web interface
    web_service = await server.register_service({
        "id": "terminal-web",
        "name": "Virtual Terminal Web Interface",
        "type": "asgi",
        "serve": serve_fastapi,
        "config": {"visibility": "public", "require_context": True}
    })
    
    print(f"Terminal service registered: {terminal_service.id}")
    print(f"Web interface available at: {server.config.public_base_url}/{server.config.workspace}/apps/{web_service.id.split(':')[1]}")
    
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
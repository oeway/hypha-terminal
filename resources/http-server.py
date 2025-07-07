import asyncio
from hypha_rpc import connect_to_server
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>Cat</title></head>
        <body><img src="https://cataas.com/cat?type=square" alt="cat"></body>
    </html>
    """

@app.get("/api/v1/test")
async def test():
    return {"message": "Hello, it works!"}

async def serve_fastapi(args, context=None):
    # context can be used for authorization, e.g., checking the user's permission
    # e.g., check user id against a list of allowed users
    scope = args["scope"]
    print(f'{context["user"]["id"]} - {scope["client"]} - {scope["method"]} - {scope["path"]}')
    await app(args["scope"], args["receive"], args["send"])

async def main():
    # Connect to Hypha server
    server = await connect_to_server({"server_url": "https://hypha.aicell.io"})

    svc_info = await server.register_service({
        "id": "cat",
        "name": "cat",
        "type": "asgi",
        "serve": serve_fastapi,
        "config": {"visibility": "public", "require_context": True}
    })

    print(f"Access your app at:  {server.config.public_base_url}/{server.config.workspace}/apps/{svc_info['id'].split(':')[1]}")
    await server.serve()

asyncio.run(main())
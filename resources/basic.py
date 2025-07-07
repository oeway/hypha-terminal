import asyncio
from hypha_rpc import connect_to_server

async def start_server(server_url):
    server = await connect_to_server({"server_url": server_url})

    def hello(array, callback):
        print("Hello " , array)
        callback("Hello " + str(array))

    svc = await server.register_service({
        "name": "Hello World",
        "id": "hello-world",
        "config": {
            "visibility": "public"
        },
        "hello": hello,
    })

    print(f"Hello world service registered at workspace: {server.config.workspace}, id: {svc.id}")

    print(f'You can use this service using the service id: {svc.id}')

    print(f"You can also test the service via the HTTP proxy: {server_url}/{server.config.workspace}/services/{svc.id.split('/')[1]}/hello?name=John")

    # Keep the server running
    await server.serve()

if __name__ == "__main__":
    server_url = "https://hypha.aicell.io"
    asyncio.run(start_server(server_url))
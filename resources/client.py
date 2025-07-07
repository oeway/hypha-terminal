import asyncio
from hypha_rpc import connect_to_server
import numpy as np
async def main():
    server = await connect_to_server({"server_url": "https://hypha.aicell.io"})

    # Get an existing service
    # NOTE: You need to replace the service id with the actual id you obtained when registering the service
    svc = await server.get_service("ws-user-anonymouz-carnelian-reading-12256765/czgNfmHTLQ2yh7Akj7WRNe:hello-world")
    
    def callback(result):
        print("callback", result)
        
    ret = await svc.hello(np.array([1, 2, 3]), callback)
    print(ret)

if __name__ == "__main__":
    asyncio.run(main())
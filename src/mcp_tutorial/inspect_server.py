"""
Code for inspecting the capabilities of the MCP client
"""
# Imports
import anyio
from mcp import Client
from server import mcp

async def main() -> None:
    async with Client(mcp) as client:
        # Print all the capabilities of the mcp server
        print(client.server_capabilities.model_dump(exclude_none=True))

        # Print all the tool names from the server
        print([t.name for t in (await client.list_tools()).tools])

        # Print all the available resources on the server
        print([r.name for r in (await client.list_resource_templates()).resource_templates])

        # Print all the available prompts on the server
        print([p.name for p in (await client.list_prompts()).prompts])

        # Use the tools available on the server from the client
        c = await(client.call_tool(
            "add", 
            {"a":5, "b":9}
            )
        )
        print(f"Addition of 5 and 9 from server tool: {c.structured_content['result']}")

anyio.run(main)

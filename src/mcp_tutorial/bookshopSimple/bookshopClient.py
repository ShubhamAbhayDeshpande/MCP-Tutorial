"""
Program to inspect the working of """

from mcp import Client
from bookshopServer import mcp
import anyio

async def main():
    async with Client(mcp) as bookshopClient:
        
        result = await(bookshopClient.call_tool(
        "search_book", 
        arguments={"query":"Dune", "limit":5}
        )
    )
        print(result.content[0].text)

anyio.run(main)

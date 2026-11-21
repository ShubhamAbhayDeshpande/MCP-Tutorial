from mcp.server import MCPServer

# Create a demo MCP server named "Demo"
mcp = MCPServer("Demo")

"""
The SDK is so designed that the name of the tool becomes the name in json, docstrring becomes the description, and the schema of the tool 
becomes the type hint.

** Keep in mind that the tools and resources both live on the server for a reason. The host controlles which tools to use and which resources to add in 
the model context. The job of the server is to just expose the tools and resources. **

"""


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add the two integers given as inputs"""
    return a + b


"""The model only sees the infomration in the resource as a context. Client lists the resources and shows them to the model (or user program). 
The model then chooses the resource to be attached in the context. It did not run anything.  
"""


@mcp.resource("greetings://{name}")
def greetings(name: str) -> str:
    """Greet someone by name"""
    return f"Hello, {name}!"


@mcp.prompt()
def summerize(text: str) -> str:
    """Summerize a piece of text in one sentence"""
    return f"Summerize the following text in one sentence: \n\n{text}"


if __name__ == "__main__":
    mcp.run()

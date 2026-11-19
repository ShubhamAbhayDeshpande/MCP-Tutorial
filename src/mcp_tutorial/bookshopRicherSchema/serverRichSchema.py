"""
The richer schema in the server side tools and resources tells more about the what the input arguments are 
and how to use them to the AI model when the tools and resources are exposed to it."""

# Imports
from mcp.server import MCPServer
from typing import Annotated, Literal
from pydantic import Field

# Global constants
CATALOG = {"Dune":"Frank Herbert", 
             "Neuromancer": "William Gibson",
             "The Left Hand of Darkness": "ursula K. Le Guin"
            }

app = MCPServer("richBookshop")

@app.tool()
def search_book(
    query: Annotated[str, Field(description="Book title or book author's name to be searched")], 
    limit: Annotated[int, Field(ge=1, le=12, description="Maximum number of results that can be returned")]=10,
)-> list[str]:
    """Search for the book with author's name or the title of the book provided by the user"""
    query_lower = query.lower()
    hits = [t for t, a in CATALOG.items() if query_lower in t.lower() or query_lower in a.lower()]
    if not hits:
        return []
    return hits[:limit]
"""
MCP server called bookshop
"""

# Imports
from mcp.server import MCPServer

# Make a bookshop server
mcp = MCPServer("Bookshop")

CATALOG = {
    "Dune": "Frank Herbert",
    "Neuromancer": "William Gibson",
    "The Left Hand of Darkness": "ursula K. Le Guin",
}


# MCP  tool to search the book by title or an author
@mcp.tool()
def search_book(query: str, limit: int = 10):
    """Search the book with given title or author's name."""
    query_lower = query.lower()
    hits = [
        t
        for t, a in CATALOG.items()
        if query_lower in t.lower() or query_lower in a.lower()
    ]
    return hits[:10]


if __name__ == "__main__":
    mcp.run()

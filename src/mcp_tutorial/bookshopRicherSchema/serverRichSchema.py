"""
The richer schema in the server side tools and resources tells more about the what the input arguments are
and how to use them to the AI model when the tools and resources are exposed to it."""

# Imports
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from typing import Annotated, Literal
from pydantic import BaseModel, Field

# Global constants
CATALOG = {
    "Dune": "Frank Herbert",
    "Neuromancer": "William Gibson",
    "The Left Hand of Darkness": "ursula K. Le Guin",
}

# Writing a class 'Book' which is a derivative of the BaseModel class.
# The class has attributes title, author and year of publication


class Book(BaseModel):
    title: Annotated[str, Field("The title of the new book")]
    author: Annotated[str, Field("The athor of the book")]
    publication_year: Annotated[
        int, Field(ge=1450, description="The year in which the " "book was published")
    ]


app = MCPServer("richBookshop")


# The following tools also have titles and annotations.
# 'title' is what will be shown to the user in the UI.
# 'annotations' are hints to the client. They are only hints. Do not rely on
# the client to always honor them.
@app.tool(
    title="Search the book in the catalog.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def search_book(
    query: Annotated[
        str,
        Field(description="Book title or book author's name to be searched"),
    ],
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=12,
            description="Maximum number of results that can be returned",
        ),
    ] = 10,
) -> list[str]:
    """Search for the book with author's name or the title of the book provided by the user"""
    query_lower = query.lower()
    hits = [
        t
        for t, a in CATALOG.items()
        if query_lower in t.lower() or query_lower in a.lower()
    ]
    if not hits:
        return []
    return hits[:limit]


@app.tool(
    title="Add a new book to the catalog.",
    annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
)
def add_book(
    book: Annotated[
        Book,
        Field(
            "Object type book. A new book with the given information will be added to catalog."
        ),
    ],
) -> str:
    """Add a new book to the the catalog of books already present.

    Input: An object of type 'Book'
    Output: A string message that the new book is added.

    """
    CATALOG[book.title] = book.author
    return f"Added new book, {book.title} to the catalog."


@app.tool(
    title="Remove the item from the catalog",
    annotations=ToolAnnotations(
        read_only_hint=False, open_world_hint=False, destructive_hint=True
    ),
)
def remove_book(
    book_name: Annotated[
        str, Field("Name of the book to be " "removed from the catalog")
    ],
) -> dict:
    """Remove the book from the catalog."""
    #  If the user input is book's title:
    try:
        del CATALOG[book_name]
    except ValueError:
        print(f"The book: {book_name} is not in the catalog.")
    print(f"The book {book_name} has been removed from the catalog.")
    return CATALOG


@app.tool(
    title="Display the current catalog",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
    ),
)
def display_catalog() -> dict:
    print(f"Current catalog contains: {[titles for titles in CATALOG.keys()]}")
    return CATALOG

# MCP Python SDK: A 2-Hour Hands-On Tutorial

By the end you will have built an MCP server with **tools, resources and prompts**, used **structured output, errors, Context, progress and lifespan**, talked to it with the SDK's **Client** over stdio, HTTP and in memory, and **tested** it with pytest.

This tutorial follows the official docs for the **v2** SDK (<https://py.sdk.modelcontextprotocol.io/>). It uses `MCPServer` and `Client`.

## Schedule

| # | Part | Time |
|---|------|------|
| 0 | Setup | 10 min |
| 1 | The mental model | 5 min |
| 2 | Your first server | 15 min |
| 3 | Tools in depth | 20 min |
| 4 | Structured output and errors | 15 min |
| 5 | Resources | 10 min |
| 6 | Prompts | 5 min |
| 7 | Context, progress, lifespan | 15 min |
| 8 | The Client and transports | 15 min |
| 9 | Testing | 10 min |
| | **Total** | **~120 min** |

Work in one folder, for example `C:\workplace\MCP_Tutorial\work`. Type the code rather than pasting it. The type hints and autocomplete are part of the lesson.

---

## 0. Setup (10 min)

Requirements: Python 3.11+, and Node.js (`npx`) if you want the visual Inspector.

```powershell
mkdir work; cd work
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "mcp[cli]" pytest
mcp version
```

> **Version check.** This tutorial needs **mcp 2.x**. If `mcp version` prints `1.x`, run `pip install -U "mcp[cli]"`.
> In v1 the same ideas exist under different names: `from mcp.server.fastmcp import FastMCP` instead of `from mcp.server import MCPServer`, and no `Client` class (you use `ClientSession`). Everything else maps closely.

The `cli` extra gives you the `mcp` command:

| Command | What it does |
|---|---|
| `mcp dev server.py` | Run your server under the **MCP Inspector** (a web UI) |
| `mcp run server.py` | Import the file, find the server object, run it |
| `mcp install server.py` | Register it with Claude Desktop |

`mcp dev` and `mcp run` look for a module-level variable named `mcp`, `server` or `app`.

---

## 1. The mental model (5 min)

- **Host**: the LLM application (Claude Desktop, an IDE, an agent runtime).
- **Client**: lives inside the host and speaks MCP. One client per server.
- **Server**: what you build. It exposes things; it never talks to the model directly.

A server exposes exactly three kinds of things. They differ in **who decides to use them**:

| Primitive | Controlled by | What it is | Web analogy |
|---|---|---|---|
| **Tool** | the **model** | A function the model calls to act | `POST` |
| **Resource** | the **application** | Data loaded into the model's context | `GET` |
| **Prompt** | the **user** | A reusable message template picked by name | a slash command |

Remember this table; every later section is a variation on it.

The SDK's big idea: **your Python function is the declaration.** The name comes from the function name, the description from the docstring, and the schema from the type hints. You write no JSON Schema and no protocol code.

---

## 2. Your first server (15 min)

Create `server.py`:

```python
from mcp.server import MCPServer

mcp = MCPServer("Demo")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"


@mcp.prompt()
def summarize(text: str) -> str:
    """Summarize a piece of text in one sentence."""
    return f"Summarize the following text in one sentence:\n\n{text}"


if __name__ == "__main__":
    mcp.run()
```

### Try it in the Inspector

```powershell
mcp dev server.py
```

Open the URL it prints and walk through the tabs:

1. **Tools**: `add` has two required integer fields, built from `a: int, b: int`. Call it with 1 and 2 and you get `3`.
2. **Resources**: the list is empty. `greeting` is under **Resource Templates**, because `{name}` means there is no single resource until someone supplies a name. Read `greeting://World` and you get `Hello, World!`.
3. **Prompts**: `summarize` with one required `text` argument. Rendering it gives one `user` message.

### Capabilities: how the client knows what to ask for

On connect, the server declares its **capabilities** (which request families it answers). `MCPServer` does this for you. See it with a client. Create `inspect_server.py`:

```python
import anyio
from mcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:          # in-memory: no process, no port
        print(client.server_capabilities.model_dump(exclude_none=True))
        print([t.name for t in (await client.list_tools()).tools])
        print([t.uri_template for t in (await client.list_resource_templates()).resource_templates])
        print([p.name for p in (await client.list_prompts()).prompts])
        print(await client.call_tool("add", {"a": 1, "b": 2}))


anyio.run(main)
```

```powershell
python inspect_server.py
```

You should see `prompts`, `resources` and `tools` in the capabilities dict. There is no `completions`, because that needs a handler you write. The rule for anything optional is: register it and the capability appears.

**Checkpoint:** explain to yourself why `greeting` is not in `list_resources()`. (Answer: it has a `{name}` placeholder, so it is a *template*.)

---

## 3. Tools in depth (20 min)

Create a new `bookshop.py` and build it up step by step. (Re-run it with `mcp dev bookshop.py` after each step.)

### 3.1 Type hints are the input schema

```python
from mcp.server import MCPServer

mcp = MCPServer("Bookshop")

CATALOG = {
    "Dune": "Frank Herbert",
    "Neuromancer": "William Gibson",
    "The Left Hand of Darkness": "Ursula K. Le Guin",
}


@mcp.tool()
def search_books(query: str, limit: int = 10) -> list[str]:
    """Search the catalog by title or author."""
    needle = query.lower()
    hits = [t for t, a in CATALOG.items() if needle in t.lower() or needle in a.lower()]
    return hits[:limit]
```

The client receives this JSON Schema, generated from your signature:

```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string"},
    "limit": {"default": 10, "type": "integer"}
  },
  "required": ["query"]
}
```

- No default means required. A default means optional.
- The type hints are **the contract**. If a client sends `"limit": "ten"`, the SDK rejects it before your function runs.

### 3.2 Richer schemas: `Annotated` + `Field`, and `Literal`

Replace `search_books`:

```python
from typing import Annotated, Literal

from pydantic import Field


@mcp.tool()
def search_books(
    query: Annotated[str, Field(description="Title or author to search for.")],
    limit: Annotated[int, Field(ge=1, le=50, description="Maximum number of results.")] = 10,
    genre: Literal["fiction", "non-fiction", "poetry"] | None = None,
) -> list[str]:
    """Search the catalog by title or author."""
    needle = query.lower()
    hits = [t for t, a in CATALOG.items() if needle in t.lower() or needle in a.lower()]
    return hits[:limit]
```

- `Field(description=...)`: the model reads a per-argument description.
- `Field(ge=1, le=50)`: becomes `minimum`/`maximum` in the schema and is **enforced**. Call it with `limit=999` and the model gets `Input should be less than or equal to 50` as the tool result, so it can retry with a valid value.
- `Literal[...]`: becomes an enum.

### 3.3 A Pydantic model as a parameter

```python
from pydantic import BaseModel


class Book(BaseModel):
    title: str
    author: str
    year: int = Field(ge=1450, description="Year of first publication.")


@mcp.tool()
def add_book(book: Book) -> str:
    """Add a book to the catalog."""
    CATALOG[book.title] = book.author
    return f"Added {book.title!r} by {book.author} ({book.year})."
```

The model fills in a JSON object, and your function receives a real, validated `Book` instance.

### 3.4 `async def` vs `def`

Use `async def` when the tool does I/O (HTTP, database) and `await` inside it. A plain `def` also works: the SDK runs it in a thread so it does not block the server.

### 3.5 Titles and annotations

```python
from mcp.types import ToolAnnotations


@mcp.tool(
    title="Search the catalog",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def search_books(query: str) -> str:
    """Search the catalog by title or author."""
    return f"Found 3 books matching {query!r}."
```

- `title` is the human-readable name for UIs.
- Annotations are **hints** for clients ("this tool is read-only, so no need to ask the user first"). They are **not security**; never rely on a client honouring them.

### Exercise 3 (5 min)
Add a tool `remove_book(title: str)` with `destructive_hint=True`. In the Inspector, check which fields appear in its schema.

---

## 4. Structured output and errors (15 min)

### 4.1 The return annotation is the output schema

A tool result has two channels:

- `content`: text the **model** reads.
- `structured_content`: typed JSON for the **application** (your code).

Both come from the single value you `return`. Add to `bookshop.py`:

```python
class AuthorInfo(BaseModel):
    title: str
    author: str
    books_by_author: int = Field(description="How many catalog books share this author.")


@mcp.tool()
def get_author(title: str) -> AuthorInfo:
    """Look up the author of a book in the catalog."""
    author = CATALOG[title]
    count = sum(1 for a in CATALOG.values() if a == author)
    return AuthorInfo(title=title, author=author, books_by_author=count)


@mcp.tool()
def count_books() -> int:
    """How many books are in the catalog."""
    return len(CATALOG)
```

| Return type | `structured_content` |
|---|---|
| `BaseModel`, `TypedDict`, `@dataclass` | the object itself: `{"title": ..., ...}` |
| `int`, `str`, `float`, `bool`, `None` | wrapped: `{"result": 3}` |
| `list[...]` | wrapped: `{"result": [...]}`, and `content` gets one block per item |
| `dict[str, X]` | the dict itself, with no wrapper |

The output is **validated** against the schema before it leaves the server. If upstream data is missing a field, the call fails instead of returning a half-empty object.

### 4.2 Three ways a tool can fail

| You raise | Who sees it | Use when |
|---|---|---|
| `ToolError("msg")` | the **model** reads `msg` (`is_error=True`) | the model could have avoided it (wrong title, upstream timeout) |
| `MCPError(code, msg)` | the **protocol** (JSON-RPC error; the model sees nothing) | the request itself must be rejected (missing capability, wrong state) |
| any other exception | the model sees only `Error executing tool X`; you get the traceback in the log | a bug |

The deciding question is: **could a smarter model have avoided this?** If yes, raise `ToolError`.

Update `get_author`:

```python
from mcp.server.mcpserver.exceptions import ToolError


@mcp.tool()
def get_author(title: str) -> AuthorInfo:
    """Look up the author of a book in the catalog."""
    if title not in CATALOG:
        raise ToolError(f"No book titled {title!r} in the catalog.")
    author = CATALOG[title]
    count = sum(1 for a in CATALOG.values() if a == author)
    return AuthorInfo(title=title, author=author, books_by_author=count)
```

Add a deliberately buggy tool to see the third case:

```python
@mcp.tool()
def buggy_lookup(title: str) -> str:
    """Deliberately buggy: raises KeyError."""
    return CATALOG[title]
```

Call `get_author("Solaris")` and `buggy_lookup("Solaris")` in the Inspector and compare the messages. The first helps the model; the second reveals nothing.

> Never `return "error ..."` from a tool. A returned string has `is_error=False`, so it looks like success. Always `raise`.

### Exercise 4 (5 min)
Add a `Literal` `sort_by: Literal["title", "author"] = "title"` parameter to `search_books` and make it sort the results. Predict the schema first, then confirm it in the Inspector.

---

## 5. Resources (10 min)

A resource is data the **application** reads. It is addressed by **URI**, not by name. Create `resources_demo.py`:

```python
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

mcp = MCPServer("Bookshop")

CATALOG = {"Dune": "Frank Herbert", "Neuromancer": "William Gibson"}


@mcp.resource("catalog://titles")                       # concrete resource
def titles() -> str:
    """Every title in the catalog, one per line."""
    return "\n".join(sorted(CATALOG))


@mcp.resource("stats://catalog", mime_type="application/json")
def catalog_stats() -> dict[str, int]:                  # dict -> JSON text
    """Live counts for the catalog."""
    return {"books": len(CATALOG), "authors": len(set(CATALOG.values()))}


@mcp.resource("books://{title}")                        # template
def book(title: str) -> str:
    """The catalog entry for one book."""
    if title not in CATALOG:
        raise ResourceNotFoundError(f"No book titled {title!r} in the catalog.")
    return f"{title} by {CATALOG[title]}"
```

Key facts:

- **Concrete vs template**: a URI with `{param}` is a template. It appears under `resources/templates/list`, and one function serves every matching URI.
- **Names must match.** The `{title}` in the URI and the `title` parameter must be identical. A mismatch raises `ValueError` at import time.
- **Lazy**: your function runs on `resources/read`, never on `resources/list`.
- **Return types**: `str` becomes text, `bytes` becomes a base64 blob, and anything else (dict, list, model) becomes JSON text. `mime_type=` defaults to `text/plain` and is never guessed.
- **Not found**: raise `ResourceNotFoundError`.

### Exercise 5 (3 min)
Rename the `book` parameter to `name` (leave the URI alone), run `python resources_demo.py`, and read the import-time error.

---

## 6. Prompts (5 min)

A prompt is a template the **user** picks. Arguments are a flat list of **strings** (there is no JSON Schema). The returned text becomes a `user` message.

```python
from mcp.server import MCPServer
from mcp.server.mcpserver.prompts.base import AssistantMessage, Message, UserMessage
from typing import Annotated
from pydantic import Field

mcp = MCPServer("Code Helper")


@mcp.prompt(title="Code review")
def review_code(
    code: Annotated[str, Field(description="The code to review.")],
    language: Annotated[str, Field(description="Language of the code.")] = "python",
) -> str:
    """Review a piece of code."""
    return f"Please review this {language} code:\n\n{code}"


@mcp.prompt()
def debug_error(error: str) -> list[Message]:
    """Start a debugging conversation."""
    return [
        UserMessage("I'm seeing this error:"),
        UserMessage(error),
        AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]
```

- Returning a `list[Message]` seeds a whole conversation. A pre-filled `AssistantMessage` steers the model's next reply.
- A missing required argument fails the request itself with JSON-RPC error `-32602`. No model is in the loop, so nothing is "returned to the model".

**Checkpoint:** in your own words, why is a prompt *user*-controlled while a tool is *model*-controlled?

---

## 7. Context, progress, lifespan (15 min)

### 7.1 `Context`: ask for it by type

Declare a parameter annotated `Context`. The SDK injects it, the parameter name doesn't matter, and the model never sees it in the schema.

```python
from mcp.server import MCPServer
from mcp.server.mcpserver import Context

mcp = MCPServer("Bookshop")


@mcp.resource("catalog://genres")
def genres() -> str:
    """The genres the catalog is organised into."""
    return "fiction, non-fiction, poetry"


@mcp.tool()
async def describe_catalog(ctx: Context) -> str:
    """Describe how the catalog is organised."""
    [contents] = await ctx.read_resource("catalog://genres")   # tool reads its own resource
    return f"[request {ctx.request_id}] The catalog is organised into: {contents.content}"
```

What `ctx` gives you:

| Member | Purpose |
|---|---|
| `ctx.request_id` | id of the current request |
| `await ctx.read_resource(uri)` | read the server's own resources |
| `await ctx.report_progress(...)` | stream progress to the caller |
| `await ctx.elicit(...)` | pause and ask the user a question |
| `ctx.session` | send notifications (for example `send_tool_list_changed()`) |
| `ctx.headers` | HTTP request headers (`None` on stdio); client-supplied, so never trust them as identity |
| `ctx.request_context.lifespan_context` | whatever your lifespan yielded (see 7.3) |

`Context` is only injected into the function you registered. If a helper needs it, pass `ctx` down as an ordinary argument.

### 7.2 Progress

```python
@mcp.tool()
async def import_catalog(urls: list[str], ctx: Context) -> str:
    """Import book records from a list of catalog URLs."""
    for done, url in enumerate(urls, start=1):
        await ctx.report_progress(done, total=len(urls), message=f"Imported {url}")
    return f"Imported {len(urls)} records."
```

- `progress` must increase on every report. `total` and `message` are optional. Omit `total` if you don't know it.
- The **client** opts in per call (see Part 8 for the callback). If it doesn't, `report_progress` is a harmless no-op, so report unconditionally.

### 7.3 Lifespan: set up once, share everywhere

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


class Database:
    def __init__(self) -> None:
        self.connected = False


@dataclass
class AppContext:
    db: Database


database = Database()


@asynccontextmanager
async def app_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    database.connected = True            # startup: once, before the first request
    try:
        yield AppContext(db=database)
    finally:
        database.connected = False       # shutdown


mcp = MCPServer("Bookshop", lifespan=app_lifespan)


@mcp.tool()
def database_status(ctx: Context[AppContext]) -> str:
    """Report whether the database connection is up."""
    return "connected" if ctx.request_context.lifespan_context.db.connected else "disconnected"
```

- Code before `yield` is startup and the `finally` is shutdown. It runs **once** per server life, not per request.
- `Context[AppContext]` makes `lifespan_context` typed, so your editor autocompletes `.db`. A bare `Context` types it as `dict[str, Any]`.
- With no `lifespan=`, the default yields an empty `{}`, never `None`.

### 7.4 (Optional) Dynamic tools

```python
def recommend_book(genre: str) -> str:
    """Recommend a book in the given genre."""
    return f"In {genre}, try 'Dune'."


@mcp.tool()
async def enable_recommendations(ctx: Context) -> str:
    """Switch on the recommendation tool."""
    mcp.add_tool(recommend_book)
    await ctx.session.send_tool_list_changed()   # tells the client to re-run tools/list
    return "Recommendations are now available."
```

> On a 2026-07-28 connection, change notifications travel over a `subscriptions/listen` stream, and you use `await ctx.notify_tools_changed()` instead. See the docs' *Subscriptions* page.

### Exercise 7 (5 min)
Combine 7.2 and 7.3 in one file. Add a tool that counts how many times it has been called by storing a counter on the object the lifespan yields.

---

## 8. The Client and transports (15 min)

`Client` is how a Python program talks to an MCP server. It is one object with one lifecycle: `async with Client(...) as client:`.

### 8.1 What you can pass to `Client`

| Argument | Transport | Typical use |
|---|---|---|
| `"http://host:8000/mcp"` | Streamable HTTP | deployed servers |
| `StdioServerParameters(...)` | stdio subprocess | local servers (what hosts do) |
| the `MCPServer` object | in-memory | tests |
| a transport context manager, e.g. `streamable_http_client(...)` | custom | auth headers, proxies |

### 8.2 Server transports

`mcp.run()` defaults to **stdio**: it blocks and waits on stdin for a host to speak first. stdout is the wire, so never `print()` from a stdio server; use the `logging` module (it writes to stderr).

To serve over HTTP, name the transport in `run()` (transport options go to `run()`, **not** to `MCPServer(...)`):

```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8000)    # http://127.0.0.1:8000/mcp
```

Or from the CLI: `mcp run server.py --transport streamable-http`. (SSE is the old transport; don't build new things on it.)

### 8.3 Over HTTP

Put the server from Part 7 (progress, resource, tool) in `progress_server.py` and start it in **terminal 1**:

```powershell
python progress_server.py
```

First make sure its `__main__` block uses `transport="streamable-http"`. Then in **terminal 2**, create `client_http.py`:

```python
import anyio
from mcp import Client


async def show(progress: float, total: float | None, message: str | None) -> None:
    print(f"{message} ({progress}/{total})")


async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        print(client.server_info, client.protocol_version, client.instructions)

        result = await client.call_tool(
            "import_catalog",
            {"urls": ["https://example.com/a.json", "https://example.com/b.json"]},
            progress_callback=show,           # per call, never on Client(...)
        )
        print(result.structured_content)       # {'result': 'Imported 2 records.'}


anyio.run(main)
```

```powershell
python client_http.py
```

Expect one `show(...)` line per `report_progress` on the server, then the result. Delete `progress_callback=show` and rerun: the call still works and just prints no progress.

### 8.4 Over stdio (what Claude Desktop does)

```python
import sys
import anyio
from mcp import Client, StdioServerParameters


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["bookshop.py"])
    async with Client(params) as client:       # launches bookshop.py as a subprocess
        print([t.name for t in (await client.list_tools()).tools])
        print((await client.call_tool("count_books", {})).structured_content)


anyio.run(main)
```

The server must call `mcp.run()` (stdio is the default) under `if __name__ == "__main__":`.

### 8.5 Reading results correctly

```python
from mcp.types import TextContent

result = await client.call_tool("get_author", {"title": "Dune"})

if result.is_error:                       # ALWAYS check first
    ...
for block in result.content:              # a union of block types
    if isinstance(block, TextContent):    # narrow before using .text
        print(block.text)
print(result.structured_content)          # typed data for your code
```

- `is_error` is set for tool errors, bad arguments and even unknown tool names. These come back as results, not exceptions.
- A client method raises `MCPError` only when the server answers with a JSON-RPC error (for example reading a missing resource).

The other verbs: `list_resources()`, `list_resource_templates()`, `read_resource(uri)` (returns `.contents`), `list_prompts()`, `get_prompt(name, {"arg": "str"})` (returns `.messages`), and `complete(...)`. Every `list_*` takes `cursor=` and returns `next_cursor`; loop until it is `None`.

### 8.6 Plugging into a real host (5-minute read)

Connecting to a host just means telling it the **command that starts your server**:

```powershell
# Claude Desktop (writes claude_desktop_config.json for you)
mcp install server.py --name "Bookshop"

# Claude Code
claude mcp add bookshop -- uv run --with "mcp[cli]" mcp run C:\absolute\path\to\server.py
```

VS Code (`.vscode/mcp.json`):

```json
{
  "servers": {
    "bookshop": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--with", "mcp[cli]", "mcp", "run", "C:\\absolute\\path\\to\\server.py"]
    }
  }
}
```

Use **absolute paths**. A host starts your server from its own working directory with a minimal environment, so pass secrets with `mcp install -v KEY=VALUE` or the `env` field.

---

## 9. Testing (10 min)

Hand `Client` the server object and you get a fast in-memory test: no subprocess and no port. Create `test_bookshop.py` next to `bookshop.py`:

```python
import pytest
from mcp import Client

from bookshop import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_count_books_is_wrapped(client: Client):
    result = await client.call_tool("count_books", {})
    assert result.structured_content == {"result": 3}


@pytest.mark.anyio
async def test_get_author_structured(client: Client):
    result = await client.call_tool("get_author", {"title": "Dune"})
    assert not result.is_error
    assert result.structured_content["author"] == "Frank Herbert"


@pytest.mark.anyio
async def test_tool_error_is_readable_by_the_model(client: Client):
    result = await client.call_tool("get_author", {"title": "Solaris"})
    assert result.is_error
    assert "No book titled 'Solaris'" in result.content[0].text


@pytest.mark.anyio
async def test_validation_runs_before_the_function(client: Client):
    result = await client.call_tool("search_books", {"query": "dune", "limit": 999})
    assert result.is_error
    assert "less than or equal to 50" in result.content[0].text
```

```powershell
pytest -q
```

Notes:

- A failing **tool** is `is_error=True` with or without `raise_exceptions`.
- `raise_exceptions=True` matters for failures **outside** tool bodies. Normally the server sanitises those into a generic "Internal server error" (so crash details don't leak to remote callers). In tests you want the real message. It has no meaning in production code.
- `Client(mcp)` is protocol-era neutral by default. Pin `mode="legacy"` only when testing legacy-specific behaviour such as sampling or elicitation push.
- The test above assumes your `search_books` has the `Field(ge=1, le=50)` version from 3.2.

---

## Wrap-up

### Cheat sheet

```python
from mcp import Client, MCPError, StdioServerParameters
from mcp.server import MCPServer
from mcp.server.mcpserver import Context, Message, UserMessage
from mcp.server.mcpserver.exceptions import ToolError, ResourceNotFoundError

mcp = MCPServer("Name", instructions="...", lifespan=app_lifespan)

@mcp.tool()                      # model-controlled; schema from type hints
@mcp.resource("scheme://{x}")    # app-controlled; URI placeholders == params
@mcp.prompt()                    # user-controlled; string args; returns str | list[Message]

raise ToolError("model-readable")            # tool error (is_error=True)
raise MCPError(code, "protocol-level")       # JSON-RPC error
await ctx.report_progress(n, total=t, message="...")
mcp.run()                                    # stdio
mcp.run(transport="streamable-http")         # HTTP at /mcp
async with Client(url | StdioServerParameters | mcp) as client: ...
```

### Ideas to keep going

1. Build a server around something real, such as a local notes folder (resources), a search function (tool), and a "summarize note" prompt.
2. Read the docs pages this tutorial skipped:
   - **Elicitation / `Resolve`**: asking the user for input mid-call
   - **Completions**: argument autocomplete
   - **Cancellation**
   - **Logging**
   - **Deploy & scale** and **Add to an existing app** (ASGI/FastAPI)
   - **OAuth clients**
   - **Migration guide**: if you have v1 code
3. Docs index: <https://py.sdk.modelcontextprotocol.io/> (Get started, Servers, Inside your handler, Running your server, Clients).

### Self-check (can you answer these?)

1. Who controls tools, resources and prompts, and why does that matter?
2. Where do a tool's name, description and schema come from?
3. What is the difference between `content` and `structured_content`?
4. When do you raise `ToolError` vs `MCPError` vs let it crash?
5. Why does the `Context` parameter not appear in a tool's schema?
6. What does a lifespan run, how often, and how do handlers access what it yields?
7. Which transport would you use for a local desktop host vs a deployed service?
8. Why is `Client(mcp)` a good test harness?

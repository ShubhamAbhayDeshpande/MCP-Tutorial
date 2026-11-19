# MCP Tutorial Notes

Questions and answers from working through [Tutorial.md](Tutorial.md).

---

## 1. What does "your Python function is the declaration" mean?

> "Your Python function is the declaration. The name comes from the function name, the description from the docstring, and the schema from the type hints. You write no JSON Schema and no protocol code."

It means the MCP Python SDK reads your function and builds the tool's definition from it, so you don't write that definition by hand.

An MCP tool has to tell the model three things: its name, what it does, and what arguments it takes. Without the SDK you would write that out yourself as JSON Schema:

```json
{
  "name": "add",
  "description": "Add two numbers",
  "inputSchema": {
    "type": "object",
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "required": ["a", "b"]
  }
}
```

You would also have to write the code that handles protocol messages: listing tools, receiving calls and validating arguments.

With the SDK, you write only a normal function:

```python
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b
```

The SDK derives each part of the definition:

| Part of the tool | Where the SDK gets it |
|---|---|
| **Name** (`add`) | the function name |
| **Description** ("Add two numbers") | the docstring |
| **Input schema** (`a` and `b` are integers, both required) | the type hints and parameters |

The function is the only place you describe the tool. The SDK generates the JSON Schema and handles the protocol messages.

In practice, the docstring and type hints are what the model sees when it decides whether and how to call your tool. A vague docstring or a missing type hint makes the tool harder for the model to use.

---

## 2. Why are tools "controlled by the model"?

It means the **model decides when a tool gets called**. Neither the user nor the application triggers it directly.

How a tool call goes:

1. The client shows the model the list of available tools (name, description, schema).
2. The user asks something, e.g. "What's 17 + 25?"
3. The model reads the request and the tool descriptions and decides to call `add(a=17, b=25)`.
4. The client runs the call on your server and returns the result to the model.

Your code only declares what the tool can do. It never decides when it runs. That is why the docstring matters: it is how the model decides whether the tool fits the request.

| Primitive | Who decides to use it | Example |
|---|---|---|
| **Tool** | The model, mid-conversation, on its own judgment | The model decides it needs to call `add` |
| **Resource** | The application, which chooses what data to load into context | The app attaches a file or document |
| **Prompt** | The user, who explicitly picks it | Typing a slash command like `/summarize` |

A tool is like a `POST` because it performs an action, possibly with side effects. Because the model chooses to trigger it, clients usually ask the user to approve tool calls, especially risky ones.

"Always" is a little strong. It describes the design intent, and clients can add approval steps, but by the protocol's design the model is the one that invokes tools.

---

## 3. Why are resources "controlled by the application"?

Resources are application-controlled because the **host app** (the client, such as Claude Desktop or your own program) decides which resources to fetch and put into the model's context. The model doesn't ask for them.

How it works:

1. Your server declares resources, each identified by a URI, e.g. `file:///notes/todo.md` or `config://settings`.
2. The client lists them and shows them to the user, or picks them by its own rules.
3. The application reads the chosen resource and attaches its content to the conversation.
4. The model sees that data as context. It never "called" anything.

Examples of application control:

- The app shows a file picker, and the user selects resources to attach, much like attaching a file in a chat.
- The app auto-includes relevant resources by some rule, like "always load the project README".
- The app runs a search or indexing step and decides which resources are relevant.

The decision sits in the application's code, not in the model's reasoning.

| | Tool | Resource |
|---|---|---|
| Who triggers it | Model, mid-conversation | Application, before or around the model's turn |
| Purpose | Do something (action, computation) | Provide data (read-only context) |
| Side effects | Possible | Should be none |
| Web analogy | `POST` | `GET` |

Some clients also let the model read resources through a tool, which blurs the line. But in the protocol's design, resources are application-driven and tools are model-driven.

---

## 4. What does `inspect_server.py` do, and why is it `async`?

At the time of writing, [inspect_server.py](src/mcp_tutorial/inspect_server.py) contains only a docstring. The code comes from [Tutorial.md](Tutorial.md#L120-L142), section 2 ("Capabilities: how the client knows what to ask for").

```python
import anyio
from mcp import Client
from server import mcp

async def main() -> None:
    async with Client(mcp) as client:
        print(client.server_capabilities.model_dump(exclude_none=True))
        print([t.name for t in (await client.list_tools()).tools])
        print([t.uri_template for t in (await client.list_resource_templates()).resource_templates])
        print([p.name for p in (await client.list_prompts()).prompts])
        print(await client.call_tool("add", {"a": 1, "b": 2}))

anyio.run(main)
```

### What the code does

- **`from server import mcp`** imports the server object built in section 2.
- **`Client(mcp)`** connects a client directly to that server object in memory. There is no subprocess and no port.
- **`server_capabilities`** shows which request families the server answers (tools, resources, prompts). The client uses this to know what it can ask for.
- The **`list_*` calls** ask the server what tools, resource templates and prompts it exposes.
- **`call_tool("add", ...)`** calls the tool the way a model would.
- **`anyio.run(main)`** starts the async event loop and runs `main()`.

### Why `async`

The client talks to a server by sending a request and waiting for a reply. Even in memory, the MCP client is an async API, because over stdio or HTTP each call waits on I/O.

- `await` pauses your function while it waits, so the program can do other work instead of blocking.
- `async with` opens and closes the connection properly, even if an error occurs.
- `Client` is async, so any code that uses it must be too.

`anyio.run(main)` is the entry point. A normal script can't `await` at the top level, so it needs something to run the event loop.

For server-side tools (Tutorial section 3.4): use `async def` when the tool does I/O, and a plain `def` still works because the SDK runs it in a thread.

### Documentation

[Tutorial.md](Tutorial.md#L5) says it follows the official docs for the v2 Python SDK: <https://py.sdk.modelcontextprotocol.io/>. The code uses `MCPServer` and `Client` from that SDK. That has not been independently checked against the site.

### Gotcha

The tutorial names the server file `server.py`. If the file is misnamed (earlier it was `sever.py`), `from server import mcp` fails until the file is renamed or the import is changed to match.

---

## 5. Richer schemas (Tutorial section 3.2): what do `typing`, `pydantic`, `Annotated`, `Literal` and `Field` do?

```python
from typing import Annotated, Literal
from pydantic import Field

@mcp.tool()
def search_books(
    query: Annotated[str, Field(description="Title or author to search for.")],
    limit: Annotated[int, Field(ge=1, le=50, description="Maximum number of results.")] = 10,
    genre: Literal["fiction", "non-fiction", "poetry"] | None = None,
) -> list[str]:
    ...
```

### The two libraries

- **`typing`** is part of Python's standard library. It provides tools for writing precise type hints. Python doesn't enforce hints at runtime, but other code (like the MCP SDK) can read and act on them.
- **`pydantic`** is a third-party library, installed along with `mcp`. It validates data against type hints and generates JSON Schema from them. The SDK uses it to build the tool's input schema and check incoming arguments.

### The three imports

| Import | From | Role |
|---|---|---|
| `Annotated` | `typing` | Attach extra info to a type without changing the type |
| `Literal` | `typing` | Limit a value to specific choices (becomes an `enum`) |
| `Field` | `pydantic` | Hold the description and validation rules |

**`Annotated[type, extra_info]`**: `query` is still a `str`. The `Field(...)` is a note attached to it for tools that read it. Plain Python ignores the note.

**`Field(...)`**:

| Part | Effect |
|---|---|
| `description=...` | Text the model reads in the schema |
| `ge=1` | "greater than or equal to 1" → `minimum: 1` |
| `le=50` | "less than or equal to 50" → `maximum: 50` |

These rules are enforced. If the model sends `limit=999`, the SDK rejects it before the function runs and returns `Input should be less than or equal to 50`, so the model can retry. The `= 10` default sits outside `Annotated[...]` because it belongs to the parameter, not the type.

**`Literal[...]`**: `Literal["fiction", "non-fiction", "poetry"]` allows only those three strings. `| None` also allows `None`, and `= None` makes the argument optional.

### Resulting schema

```json
{
  "properties": {
    "query": {"type": "string", "description": "Title or author to search for."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10,
              "description": "Maximum number of results."},
    "genre": {"enum": ["fiction", "non-fiction", "poetry"], "default": null}
  },
  "required": ["query"]
}
```

Note: in the tutorial, `search_books` accepts `genre` but never uses it in the filter. It is there only to show the schema.

---

## 6. Can the client and server live in the same Python file?

Yes, but it can change how the program runs.

**In-memory client works**, as long as the client code is behind a guard and `mcp.run()` isn't also called on that path:

```python
async def main():
    async with Client(mcp) as client:
        print(await client.call_tool("add", {"a": 1, "b": 2}))

if __name__ == "__main__":
    anyio.run(main)
```

**Problems with other setups:**

1. **Hosts and the CLI import your file.** `mcp dev`, `mcp run` and Claude Desktop load the file to find `mcp`. Unguarded client code would run on every import.
2. **stdio: `print()` breaks the protocol.** stdout is the wire, so stray prints corrupt the message stream.
3. **A stdio client that launches its own file loops forever.** The subprocess runs the same file, which starts another client, which launches another subprocess. A `__main__` guard doesn't fix it, because the subprocess is also `__main__`.
4. **HTTP needs two processes anyway.** The server must already be running elsewhere.
5. **`mcp.run()` blocks.** It waits on stdin, so client code placed after it never runs.

**Recommendation:** keep them separate, as the tutorial does. The server file defines `mcp` and calls `mcp.run()` under `__main__`. The client or test file does `from server import mcp`, or connects by URL or command. A single file is only reasonable for a quick in-memory experiment.

---

## 7. Can I give user-defined input to a tool when writing the client?

Yes. The second argument of `call_tool` is a plain dict, so its values can come from `input()`, `argparse`, a file, a web form, etc. The server only sees the final dict.

```python
async def main() -> None:
    query = input("Search for: ")
    limit = int(input("Max results: "))     # input() returns str, so convert

    async with Client(mcp) as client:
        result = await client.call_tool("search_books", {"query": query, "limit": limit})
        if result.is_error:
            print("Error:", result.content[0].text)
        else:
            print(result.structured_content)

anyio.run(main)
```

**Things to know:**

- **Types matter.** `input()` always returns `str`. If the tool declares `limit: int`, send an `int`.
- **Server-side validation still applies.** `limit=999` with `Field(le=50)` comes back as `is_error=True` with `Input should be less than or equal to 50`.
- **Keys must match the tool's parameter names exactly.** Check them with `await client.list_tools()` and each tool's `input_schema`.
- **Always check `result.is_error`** before using the result.
- `input()` is fine in a client. It is only a problem inside a stdio *server*, where stdin and stdout carry the protocol.

**Generic client** that prompts for each field in the schema (roughly what the MCP Inspector does):

```python
tool = (await client.list_tools()).tools[0]
args = {}
for name, spec in tool.input_schema["properties"].items():
    raw = input(f"{name} ({spec.get('type')}): ")
    args[name] = int(raw) if spec.get("type") == "integer" else raw
result = await client.call_tool(tool.name, args)
```

In a real LLM-driven app, the model produces that dict itself, which is what "tools are model-controlled" means. A client using `input()` is you playing the model's role.

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

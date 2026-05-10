# revit-mcp

Connect **Autodesk Revit** to **Claude** (or any MCP-compatible AI client) so you can query and modify your Revit model in plain English.

```
Claude (claude.ai / Claude Code)
        ↕  MCP protocol (JSON-RPC over stdio)
revit_mcp_server.py   ← Python 3, runs on your machine
        ↕  HTTP REST  (localhost:7777)
RevitMCP.pushbutton   ← IronPython, runs inside Revit via pyRevit
        ↕  Revit API
Revit Model
```

---

## Repository structure

```
revit-mcp/
├── RevitMCP.pushbutton/
│   └── script.py          # pyRevit button — starts an HTTP server inside Revit
├── revit_mcp_server.py    # MCP server Claude talks to
├── requirements.txt
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Autodesk Revit 2019+ | Any version supported by pyRevit |
| [pyRevit](https://github.com/eirannejad/pyRevit) | Installed and loaded in Revit |
| Python 3.10+ | For `revit_mcp_server.py` (outside Revit) |
| Claude Code CLI *or* Claude Desktop | The MCP client |

---

## Setup

### 1 — Install the Python dependencies

```bash
pip install -r requirements.txt
```

### 2 — Add the pyRevit button

Copy the `RevitMCP.pushbutton` folder into your pyRevit extension, for example:

```
%APPDATA%\pyRevit\Extensions\YourExtension.extension\YourPanel.panel\RevitMCP.pushbutton\
```

Reload pyRevit (or restart Revit). A **RevitMCP** button will appear in the ribbon.

### 3 — Start the in-Revit server

1. Open Revit with a project loaded.
2. Click the **RevitMCP** ribbon button.  
   You will see in the pyRevit output:
   ```
   Revit MCP server started on http://localhost:7777/
   Available endpoints: GET /ping  GET /walls  GET /rooms  GET /counts  POST /rename_room
   ```
3. Click the button again at any time to **stop** the server.

### 4 — Register the MCP server with Claude

**Claude Code CLI** — add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "revit": {
      "command": "python",
      "args": ["C:/path/to/revit_mcp_server.py"]
    }
  }
}
```

**Claude Desktop** — go to **Settings → Integrations → Add MCP Server**:

| Field | Value |
|---|---|
| Name | `revit` |
| Command | `python` |
| Arguments | `C:/path/to/revit_mcp_server.py` |

### 5 — Test the connection

Start Claude and ask:

> *"How many walls are in my Revit model?"*  
> *"List all rooms with their areas."*  
> *"Rename room 123456 to 'Board Room'."*

---

## Available tools (exposed to Claude)

| Tool | Method | Description |
|---|---|---|
| `revit_ping` | GET `/ping` | Check Revit is reachable; returns document name |
| `revit_get_walls` | GET `/walls` | All walls with ID, name, length (m) |
| `revit_get_rooms` | GET `/rooms` | All rooms with ID, name, number, area (m²) |
| `revit_get_counts` | GET `/counts` | Element count per category |
| `revit_rename_room` | POST `/rename_room` | Rename a room by element ID |

---

## Extending the project

### Add a new read endpoint (pyRevit side)

```python
elif path == "doors" and method == "GET":
    doors = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).ToElements()
    body  = json.dumps([{"id": str(d.Id), "name": d.Name} for d in doors])
```

### Add the matching MCP tool (server side)

```python
types.Tool(
    name="revit_get_doors",
    description="Return all doors in the active Revit model.",
    inputSchema={"type": "object", "properties": {}, "required": []},
)
```

Then add `"revit_get_doors": "doors"` to the endpoint map in `call_tool`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Could not connect to Revit` | Click the RevitMCP button first; check port 7777 is not blocked |
| Button doesn't appear | Make sure the folder is inside a `.panel` folder and pyRevit is reloaded |
| IronPython `ImportError` | Verify the `clr.AddReference` calls match your .NET / Revit version |
| `401 Access is denied` on `HttpListener` | Run Revit as Administrator once, or reserve the URL: `netsh http add urlacl url=http://localhost:7777/ user=Everyone` |

---

## License

MIT

# revit-mcp

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![IronPython](https://img.shields.io/badge/IronPython-2.7-4B8BBE)
![Revit](https://img.shields.io/badge/Revit-2019+-0696D7?logo=autodesk&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-compatible-8A2BE2)
![License](https://img.shields.io/badge/License-MIT-22C55E)

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
   You will see in the pyRevit output panel:
   ```
   Revit MCP server started on http://localhost:7777/
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

> *"Give me a summary of my Revit model."*  
> *"List all rooms larger than 20 m²."*  
> *"What warnings does the model have?"*  
> *"Create a 5-metre wall on Level 1 from (0,0) to (5,0)."*

---

## Available tools

### Read tools

| Tool | Endpoint | Description |
|---|---|---|
| `revit_ping` | GET `/ping` | Check Revit is reachable; returns document name |
| `revit_get_model_summary` | GET `/model_summary` | Counts + levels + warning count in one call |
| `revit_get_counts` | GET `/counts` | Element count per category |
| `revit_get_levels` | GET `/levels` | All levels sorted by elevation (m) |
| `revit_get_walls` | GET `/walls` | All walls with ID, name, length (m) |
| `revit_get_rooms` | GET `/rooms` | All rooms with ID, name, number, area (m²) |
| `revit_get_sheets` | GET `/sheets` | All sheets with number and name |
| `revit_get_views` | GET `/views` | All views with type and sheet placement |
| `revit_get_families` | GET `/families` | Loaded families grouped by category |
| `revit_get_warnings` | GET `/warnings` | Active model warnings with failing element IDs |
| `revit_get_element` | GET `/element?id=X` | All parameters for a single element |
| `revit_find_elements` | POST `/find_elements` | Filter elements by category and parameter value |
| `revit_export_schedule` | GET `/schedule?name=X` | Schedule contents as a JSON table |

### Write tools

| Tool | Endpoint | Description |
|---|---|---|
| `revit_rename_room` | POST `/rename_room` | Rename a room by element ID |
| `revit_set_parameter` | POST `/set_parameter` | Set any writable parameter on any element |
| `revit_create_wall` | POST `/create_wall` | Create a straight wall between two points (metres) |
| `revit_create_room` | POST `/create_room` | Place a room at a 2D point on a level |
| `revit_delete_element` | POST `/delete_element` | Delete an element by ID |

---

## Example prompts

```
"Give me a full model summary."
"List all rooms on Level 2 with their areas."
"Find all walls with Comments parameter containing 'exterior'."
"Show me the Room Schedule as a table."
"What are the current model warnings?"
"What families are loaded in the Structural Columns category?"
"Rename room 334512 to 'Server Room'."
"Set the Comments parameter on element 445231 to 'To be demolished'."
"Create a 6-metre wall on Level 1 from coordinates (0,0) to (6,0)."
"Place a room on Level 1 at position (3, 4)."
```

---

## Extending the project

All endpoints follow the same two-step pattern:

**1 — Add an endpoint in `RevitMCP.pushbutton/script.py`** (IronPython, inside Revit):
```python
elif path == "doors" and method == "GET":
    doors = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).ToElements()
    body  = json.dumps([{"id": str(d.Id), "name": d.Name} for d in doors])
```

**2 — Add a matching tool in `revit_mcp_server.py`** (Python 3, outside Revit):
```python
types.Tool(
    name="revit_get_doors",
    description="Return all doors in the active Revit model.",
    inputSchema={"type": "object", "properties": {}, "required": []},
)
```
Then add `elif name == "revit_get_doors": data = await call_revit("doors")` in `call_tool`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Could not connect to Revit` | Click the RevitMCP button first; check port 7777 is not blocked by a firewall |
| Button doesn't appear in ribbon | Confirm the folder is inside a `.panel` folder and pyRevit has been reloaded |
| IronPython `ImportError` | Verify `clr.AddReference` calls match your .NET / Revit version |
| `401 Access is denied` on `HttpListener` | Run Revit as Administrator once, or reserve the URL: `netsh http add urlacl url=http://localhost:7777/ user=Everyone` |
| Write operation fails silently | Check the pyRevit output panel for the error message from the rolled-back transaction |

---

## License

MIT

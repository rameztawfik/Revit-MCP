"""
MCP server that exposes Revit model data to Claude (or any MCP client).

Runs on your machine (outside Revit) and communicates with the pyRevit
HTTP server running inside Revit on http://localhost:7777.

Usage:
    python revit_mcp_server.py

Register in ~/.claude.json:
    {
      "mcpServers": {
        "revit": {
          "command": "python",
          "args": ["/absolute/path/to/revit_mcp_server.py"]
        }
      }
    }
"""

import asyncio
import json

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

REVIT_BASE = "http://localhost:7777"

app = Server("revit-mcp")

_NOT_CONNECTED = (
    "Could not connect to Revit. Make sure:\n"
    "  1. Revit is open with a project loaded\n"
    "  2. You clicked the RevitMCP button to start the in-process server\n"
    "  3. The server is running on port 7777"
)


async def call_revit(
    endpoint: str,
    method: str = "GET",
    payload: dict | None = None,
    params: dict | None = None,
) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        if method == "POST":
            r = await client.post(f"{REVIT_BASE}/{endpoint}", json=payload)
        else:
            r = await client.get(f"{REVIT_BASE}/{endpoint}", params=params)
        r.raise_for_status()
        return r.json()


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Read tools ────────────────────────────────────────────────────────
        types.Tool(
            name="revit_ping",
            description="Check whether Revit is reachable and return the open document name. Call this first to confirm the connection.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_model_summary",
            description="Get a full overview of the Revit model in one call: document name, element counts by category, all levels with elevations, and total warning count. Good first message to understand the model.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_counts",
            description="Return the count of elements per major category (walls, floors, doors, windows, rooms, columns, ceilings, roofs).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_levels",
            description="Return all levels in the model sorted by elevation, with their element ID, name, and elevation in metres.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_walls",
            description="Return all walls in the active Revit model with their element ID, name, and length in metres.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_rooms",
            description="Return all rooms in the active Revit model with name, number, and area in m².",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_sheets",
            description="Return all sheets in the model with their element ID, sheet number, and name.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_views",
            description="Return all non-template views in the model with their type, and which sheet they are placed on (if any).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_families",
            description="Return all loaded families in the model grouped by category.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_warnings",
            description="Return all active model warnings with their description and the IDs of the failing elements.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="revit_get_element",
            description="Return the full parameter list for a single element by its Revit element ID. Use this to inspect any element in detail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Revit element ID (integer as string)"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="revit_find_elements",
            description=(
                "Filter elements by category and optionally by a parameter value. "
                "Supported categories: walls, floors, doors, windows, rooms, columns, ceilings, roofs, "
                "furniture, grids, levels, mechanical equipment, plumbing fixtures, lighting fixtures, stairs, railings. "
                "For numeric filters use min_value/max_value (Revit internal units — feet for lengths). "
                "For text filters use value (case-insensitive substring match)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category":  {"type": "string", "description": "Element category (e.g. 'rooms', 'walls')"},
                    "parameter": {"type": "string", "description": "Parameter name to filter on (optional)"},
                    "value":     {"type": "string", "description": "Substring to match against the parameter value (optional)"},
                    "min_value": {"type": "number", "description": "Minimum numeric parameter value (optional)"},
                    "max_value": {"type": "number", "description": "Maximum numeric parameter value (optional)"},
                },
                "required": ["category"],
            },
        ),
        types.Tool(
            name="revit_export_schedule",
            description="Return the contents of a named schedule as a JSON table with headers and rows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact name of the schedule view in Revit"},
                },
                "required": ["name"],
            },
        ),
        # ── Write tools ───────────────────────────────────────────────────────
        types.Tool(
            name="revit_rename_room",
            description="Rename a room in the active Revit model by its element ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id":   {"type": "string", "description": "Revit element ID of the room"},
                    "name": {"type": "string", "description": "New room name"},
                },
                "required": ["id", "name"],
            },
        ),
        types.Tool(
            name="revit_set_parameter",
            description=(
                "Set any writable parameter on any element by element ID. "
                "For Double parameters, supply the value in Revit internal units (feet for length, "
                "square feet for area). For String parameters supply a string. "
                "For Integer parameters supply an integer."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id":        {"type": "string", "description": "Revit element ID"},
                    "parameter": {"type": "string", "description": "Parameter name (as shown in Revit properties panel)"},
                    "value":     {"description": "New value (string, number, or integer depending on parameter type)"},
                },
                "required": ["id", "parameter", "value"],
            },
        ),
        types.Tool(
            name="revit_create_wall",
            description="Create a straight wall between two points on a given level. Coordinates are in metres.",
            inputSchema={
                "type": "object",
                "properties": {
                    "x1":       {"type": "number", "description": "Start X in metres"},
                    "y1":       {"type": "number", "description": "Start Y in metres"},
                    "x2":       {"type": "number", "description": "End X in metres"},
                    "y2":       {"type": "number", "description": "End Y in metres"},
                    "level_id": {"type": "string", "description": "Element ID of the base level"},
                    "height":   {"type": "number", "description": "Unconnected wall height in metres (default 3.0)"},
                },
                "required": ["x1", "y1", "x2", "y2", "level_id"],
            },
        ),
        types.Tool(
            name="revit_create_room",
            description="Place a room at a 2D point on a given level. The point must be inside a bounded area for the room to be valid.",
            inputSchema={
                "type": "object",
                "properties": {
                    "x":        {"type": "number", "description": "X coordinate in metres"},
                    "y":        {"type": "number", "description": "Y coordinate in metres"},
                    "level_id": {"type": "string", "description": "Element ID of the level"},
                },
                "required": ["x", "y", "level_id"],
            },
        ),
        types.Tool(
            name="revit_delete_element",
            description="Delete a single element from the model by its element ID. This action cannot be undone via Claude — use with care.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Revit element ID to delete"},
                },
                "required": ["id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        # Read tools
        if name == "revit_ping":
            data = await call_revit("ping")
        elif name == "revit_get_model_summary":
            data = await call_revit("model_summary")
        elif name == "revit_get_counts":
            data = await call_revit("counts")
        elif name == "revit_get_levels":
            data = await call_revit("levels")
        elif name == "revit_get_walls":
            data = await call_revit("walls")
        elif name == "revit_get_rooms":
            data = await call_revit("rooms")
        elif name == "revit_get_sheets":
            data = await call_revit("sheets")
        elif name == "revit_get_views":
            data = await call_revit("views")
        elif name == "revit_get_families":
            data = await call_revit("families")
        elif name == "revit_get_warnings":
            data = await call_revit("warnings")
        elif name == "revit_get_element":
            data = await call_revit("element", params={"id": arguments["id"]})
        elif name == "revit_find_elements":
            data = await call_revit("find_elements", method="POST", payload=arguments)
        elif name == "revit_export_schedule":
            data = await call_revit("schedule", params={"name": arguments["name"]})
        # Write tools
        elif name == "revit_rename_room":
            data = await call_revit("rename_room", method="POST", payload=arguments)
        elif name == "revit_set_parameter":
            data = await call_revit("set_parameter", method="POST", payload=arguments)
        elif name == "revit_create_wall":
            data = await call_revit("create_wall", method="POST", payload=arguments)
        elif name == "revit_create_room":
            data = await call_revit("create_room", method="POST", payload=arguments)
        elif name == "revit_delete_element":
            data = await call_revit("delete_element", method="POST", payload=arguments)
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    except httpx.ConnectError:
        return [types.TextContent(type="text", text=_NOT_CONNECTED)]
    except httpx.HTTPStatusError as e:
        return [types.TextContent(type="text", text=f"Revit returned an error: {e.response.text}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

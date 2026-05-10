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


async def call_revit(endpoint: str, method: str = "GET", payload: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        if method == "POST":
            r = await client.post(f"{REVIT_BASE}/{endpoint}", json=payload)
        else:
            r = await client.get(f"{REVIT_BASE}/{endpoint}")
        r.raise_for_status()
        return r.json()


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="revit_ping",
            description="Check whether Revit is reachable and return the open document name.",
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
            name="revit_get_counts",
            description="Return a count summary of major element categories (walls, floors, doors, windows, rooms, columns).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
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
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    _not_connected = (
        "Could not connect to Revit. Make sure:\n"
        "  1. Revit is open with a project loaded\n"
        "  2. You clicked the RevitMCP button to start the in-process server\n"
        "  3. The server is running on port 7777"
    )

    try:
        if name == "revit_ping":
            data = await call_revit("ping")
        elif name == "revit_get_walls":
            data = await call_revit("walls")
        elif name == "revit_get_rooms":
            data = await call_revit("rooms")
        elif name == "revit_get_counts":
            data = await call_revit("counts")
        elif name == "revit_rename_room":
            data = await call_revit("rename_room", method="POST", payload=arguments)
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    except httpx.ConnectError:
        return [types.TextContent(type="text", text=_not_connected)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

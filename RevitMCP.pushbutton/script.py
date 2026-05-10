# -*- coding: utf-8 -*-
# IronPython 2.7 (pyRevit) — no f-strings, no type hints
import clr
clr.AddReference('System')
clr.AddReference('System.Net')
clr.AddReference('System.Threading')
clr.AddReference('System.Web')

import System
import System.Net as Net
import System.Threading as Threading
import System.Text as Text
import json

from Autodesk.Revit.DB import (
    FilteredElementCollector, Wall, Transaction, ElementId,
    BuiltInParameter, BuiltInCategory
)
from pyrevit import revit

doc   = revit.doc
uidoc = revit.uidoc

# Global server state — toggled each time the button is clicked
_listener = None
_thread   = None

PORT = 7777


# ── Revit data helpers ───────────────────────────────────────────────────────

def get_all_walls():
    walls = FilteredElementCollector(doc).OfClass(Wall).ToElements()
    result = []
    for w in walls:
        try:
            name = w.Name
        except Exception:
            name = str(w.Id)
        param = w.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH)
        length_m = round(param.AsDouble() * 0.3048, 2) if param else None
        result.append({"id": str(w.Id), "name": name, "length_m": length_m})
    return result


def get_all_rooms():
    rooms = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .ToElements()
    )
    result = []
    for r in rooms:
        name   = r.get_Parameter(BuiltInParameter.ROOM_NAME).AsString()
        number = r.get_Parameter(BuiltInParameter.ROOM_NUMBER).AsString()
        area_p = r.get_Parameter(BuiltInParameter.ROOM_AREA)
        area   = round(area_p.AsDouble() * 0.0929, 2) if area_p else None
        result.append({"id": str(r.Id), "name": name, "number": number, "area_m2": area})
    return result


def get_element_count():
    categories = [
        ("Walls",   BuiltInCategory.OST_Walls),
        ("Floors",  BuiltInCategory.OST_Floors),
        ("Doors",   BuiltInCategory.OST_Doors),
        ("Windows", BuiltInCategory.OST_Windows),
        ("Rooms",   BuiltInCategory.OST_Rooms),
        ("Columns", BuiltInCategory.OST_StructuralColumns),
    ]
    return {
        label: len(FilteredElementCollector(doc).OfCategory(cat).ToElements())
        for label, cat in categories
    }


def rename_room(payload):
    elem_id = ElementId(int(payload["id"]))
    room    = doc.GetElement(elem_id)
    t = Transaction(doc, "MCP Rename Room")
    t.Start()
    room.get_Parameter(BuiltInParameter.ROOM_NAME).Set(str(payload["name"]))
    t.Commit()
    return {"status": "renamed", "id": payload["id"]}


# ── HTTP server ──────────────────────────────────────────────────────────────

def read_body(req):
    length     = req.ContentLength64
    buf        = System.Array[System.Byte](length)
    req.InputStream.Read(buf, 0, length)
    return Text.Encoding.UTF8.GetString(buf)


def handle_request(context):
    req  = context.Request
    resp = context.Response
    resp.ContentType = "application/json"
    resp.Headers.Add("Access-Control-Allow-Origin", "*")

    path   = req.Url.AbsolutePath.strip("/")
    method = req.HttpMethod.upper()

    try:
        if path == "ping" and method == "GET":
            body = json.dumps({"status": "ok", "document": doc.Title})

        elif path == "walls" and method == "GET":
            body = json.dumps(get_all_walls())

        elif path == "rooms" and method == "GET":
            body = json.dumps(get_all_rooms())

        elif path == "counts" and method == "GET":
            body = json.dumps(get_element_count())

        elif path == "rename_room" and method == "POST":
            payload = json.loads(read_body(req))
            body    = json.dumps(rename_room(payload))

        else:
            resp.StatusCode = 404
            body = json.dumps({"error": "Unknown endpoint: " + path})

    except Exception as ex:
        resp.StatusCode = 500
        body = json.dumps({"error": str(ex)})

    data = Text.Encoding.UTF8.GetBytes(body)
    resp.ContentLength64 = data.Length
    resp.OutputStream.Write(data, 0, data.Length)
    resp.OutputStream.Close()


def server_loop(listener):
    while True:
        try:
            context = listener.GetContext()
            handle_request(context)
        except Exception:
            break


# ── Toggle on button click ───────────────────────────────────────────────────

global _listener, _thread

if _listener is not None:
    _listener.Stop()
    _listener = None
    print("Revit MCP server STOPPED.")
else:
    _listener = Net.HttpListener()
    _listener.Prefixes.Add("http://localhost:{}/".format(PORT))
    _listener.Start()

    _thread = Threading.Thread(Threading.ThreadStart(lambda: server_loop(_listener)))
    _thread.IsBackground = True
    _thread.Start()

    print("Revit MCP server started on http://localhost:{}/".format(PORT))
    print("Available endpoints: GET /ping  GET /walls  GET /rooms  GET /counts  POST /rename_room")

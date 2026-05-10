# -*- coding: utf-8 -*-
# IronPython 2.7 (pyRevit) — no f-strings, no type hints
import clr
clr.AddReference('System')
clr.AddReference('System.Net')
clr.AddReference('System.Threading')

import System
import System.Net as Net
import System.Threading as Threading
import System.Text as Text
import json

from Autodesk.Revit.DB import (
    FilteredElementCollector, Wall, Transaction, ElementId,
    BuiltInParameter, BuiltInCategory, Level, Line, XYZ, UV,
    ViewSheet, View, Family, StorageType, ViewSchedule, SectionType,
)
from pyrevit import revit

doc   = revit.doc
uidoc = revit.uidoc

_listener = None
_thread   = None
PORT = 7777

# ── Unit conversion ──────────────────────────────────────────────────────────

def m_to_ft(m):
    return m / 0.3048

def ft_to_m(ft):
    return ft * 0.3048


# ── Category lookup table ────────────────────────────────────────────────────

CATEGORY_MAP = {
    "walls":                BuiltInCategory.OST_Walls,
    "floors":               BuiltInCategory.OST_Floors,
    "doors":                BuiltInCategory.OST_Doors,
    "windows":              BuiltInCategory.OST_Windows,
    "rooms":                BuiltInCategory.OST_Rooms,
    "columns":              BuiltInCategory.OST_StructuralColumns,
    "ceilings":             BuiltInCategory.OST_Ceilings,
    "roofs":                BuiltInCategory.OST_Roofs,
    "furniture":            BuiltInCategory.OST_Furniture,
    "grids":                BuiltInCategory.OST_Grids,
    "levels":               BuiltInCategory.OST_Levels,
    "mechanical equipment": BuiltInCategory.OST_MechanicalEquipment,
    "plumbing fixtures":    BuiltInCategory.OST_PlumbingFixtures,
    "lighting fixtures":    BuiltInCategory.OST_LightingFixtures,
    "stairs":               BuiltInCategory.OST_Stairs,
    "railings":             BuiltInCategory.OST_Railings,
}


# ── Read helpers ─────────────────────────────────────────────────────────────

def get_all_walls():
    walls = FilteredElementCollector(doc).OfClass(Wall).ToElements()
    result = []
    for w in walls:
        try:
            name = w.Name
        except Exception:
            name = str(w.Id)
        param    = w.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH)
        length_m = round(ft_to_m(param.AsDouble()), 2) if param else None
        result.append({"id": str(w.Id), "name": name, "length_m": length_m})
    return result


def get_all_rooms():
    rooms = (FilteredElementCollector(doc)
             .OfCategory(BuiltInCategory.OST_Rooms)
             .ToElements())
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
        ("Walls",    BuiltInCategory.OST_Walls),
        ("Floors",   BuiltInCategory.OST_Floors),
        ("Doors",    BuiltInCategory.OST_Doors),
        ("Windows",  BuiltInCategory.OST_Windows),
        ("Rooms",    BuiltInCategory.OST_Rooms),
        ("Columns",  BuiltInCategory.OST_StructuralColumns),
        ("Ceilings", BuiltInCategory.OST_Ceilings),
        ("Roofs",    BuiltInCategory.OST_Roofs),
    ]
    result = {}
    for label, cat in categories:
        result[label] = len(FilteredElementCollector(doc).OfCategory(cat).ToElements())
    return result


def get_all_levels():
    levels = FilteredElementCollector(doc).OfClass(Level).ToElements()
    result = []
    for lv in sorted(levels, key=lambda l: l.Elevation):
        result.append({
            "id":           str(lv.Id),
            "name":         lv.Name,
            "elevation_m":  round(ft_to_m(lv.Elevation), 3),
        })
    return result


def get_all_sheets():
    sheets = FilteredElementCollector(doc).OfClass(ViewSheet).ToElements()
    result = []
    for s in sheets:
        result.append({
            "id":     str(s.Id),
            "number": s.SheetNumber,
            "name":   s.Name,
        })
    return sorted(result, key=lambda x: x["number"])


def get_all_views():
    # Build a map of view_id -> sheet info
    sheet_map = {}
    for s in FilteredElementCollector(doc).OfClass(ViewSheet).ToElements():
        for vid in s.GetAllPlacedViews():
            sheet_map[vid.IntegerValue] = {
                "sheet_number": s.SheetNumber,
                "sheet_name":   s.Name,
            }

    views = FilteredElementCollector(doc).OfClass(View).ToElements()
    result = []
    for v in views:
        if v.IsTemplate:
            continue
        info = {
            "id":           str(v.Id),
            "name":         v.Name,
            "type":         str(v.ViewType),
            "sheet_number": None,
            "sheet_name":   None,
        }
        sheet_info = sheet_map.get(v.Id.IntegerValue)
        if sheet_info:
            info["sheet_number"] = sheet_info["sheet_number"]
            info["sheet_name"]   = sheet_info["sheet_name"]
        result.append(info)
    return result


def get_all_families():
    families = FilteredElementCollector(doc).OfClass(Family).ToElements()
    result = {}
    for f in families:
        try:
            cat_name = f.FamilyCategory.Name if f.FamilyCategory else "Uncategorized"
        except Exception:
            cat_name = "Uncategorized"
        if cat_name not in result:
            result[cat_name] = []
        result[cat_name].append(f.Name)
    return result


def get_element_by_id(elem_id_str):
    elem = doc.GetElement(ElementId(int(elem_id_str)))
    if elem is None:
        raise Exception("Element {} not found".format(elem_id_str))

    params = {}
    for p in elem.Parameters:
        try:
            name = p.Definition.Name
            if p.StorageType == StorageType.String:
                val = p.AsString()
            elif p.StorageType == StorageType.Integer:
                val = p.AsInteger()
            elif p.StorageType == StorageType.Double:
                val = round(p.AsDouble(), 6)
            elif p.StorageType == StorageType.ElementId:
                val = p.AsElementId().IntegerValue
            else:
                val = None
            if val is not None and name:
                params[name] = val
        except Exception:
            pass

    try:
        elem_name = elem.Name
    except Exception:
        elem_name = None

    return {
        "id":         elem_id_str,
        "name":       elem_name,
        "category":   elem.Category.Name if elem.Category else None,
        "parameters": params,
    }


def get_warnings():
    result = []
    for w in doc.GetWarnings():
        result.append({
            "description":      w.GetDescriptionText(),
            "failing_elements": [str(eid) for eid in w.GetFailingElements()],
        })
    return result


def get_model_summary():
    warnings = list(doc.GetWarnings())
    return {
        "document":      doc.Title,
        "path":          doc.PathName if doc.PathName else "(unsaved)",
        "counts":        get_element_count(),
        "levels":        get_all_levels(),
        "warning_count": len(warnings),
    }


def find_elements(payload):
    category_name = payload.get("category", "").lower()
    if category_name not in CATEGORY_MAP:
        raise Exception(
            "Unknown category '{}'. Supported: {}".format(
                category_name, ", ".join(sorted(CATEGORY_MAP.keys()))
            )
        )

    cat      = CATEGORY_MAP[category_name]
    elements = (FilteredElementCollector(doc)
                .OfCategory(cat)
                .WhereElementIsNotElementType()
                .ToElements())

    param_name = payload.get("parameter")
    match_val  = payload.get("value")
    min_val    = payload.get("min_value")
    max_val    = payload.get("max_value")

    result = []
    for elem in elements:
        if param_name:
            p = elem.LookupParameter(param_name)
            if p is None:
                continue
            if match_val is not None:
                pval = p.AsString() or p.AsValueString() or ""
                if str(match_val).lower() not in pval.lower():
                    continue
            elif min_val is not None or max_val is not None:
                pval = p.AsDouble()
                if min_val is not None and pval < float(min_val):
                    continue
                if max_val is not None and pval > float(max_val):
                    continue

        try:
            name = elem.Name
        except Exception:
            name = str(elem.Id)
        result.append({"id": str(elem.Id), "name": name})
    return result


def export_schedule(schedule_name):
    schedule = None
    for s in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements():
        if s.Name == schedule_name:
            schedule = s
            break
    if schedule is None:
        raise Exception("Schedule '{}' not found".format(schedule_name))

    table_data   = schedule.GetTableData()
    header_sec   = table_data.GetSectionData(SectionType.Header)
    body_sec     = table_data.GetSectionData(SectionType.Body)

    headers = []
    for c in range(header_sec.NumberOfColumns):
        try:
            headers.append(schedule.GetCellText(SectionType.Header, 0, c))
        except Exception:
            headers.append("")

    rows = []
    for r in range(body_sec.NumberOfRows):
        row = []
        for c in range(body_sec.NumberOfColumns):
            try:
                row.append(schedule.GetCellText(SectionType.Body, r, c))
            except Exception:
                row.append("")
        rows.append(row)

    return {"name": schedule_name, "headers": headers, "rows": rows}


# ── Write helpers ─────────────────────────────────────────────────────────────

def rename_room(payload):
    elem_id = ElementId(int(payload["id"]))
    room    = doc.GetElement(elem_id)
    t = Transaction(doc, "MCP Rename Room")
    t.Start()
    try:
        room.get_Parameter(BuiltInParameter.ROOM_NAME).Set(str(payload["name"]))
        t.Commit()
    except Exception as ex:
        t.Rollback()
        raise ex
    return {"status": "renamed", "id": payload["id"]}


def set_parameter(payload):
    elem_id    = ElementId(int(payload["id"]))
    param_name = payload["parameter"]
    value      = payload["value"]

    elem  = doc.GetElement(elem_id)
    param = elem.LookupParameter(param_name)
    if param is None:
        raise Exception("Parameter '{}' not found on element {}".format(param_name, payload["id"]))
    if param.IsReadOnly:
        raise Exception("Parameter '{}' is read-only".format(param_name))

    t = Transaction(doc, "MCP Set Parameter")
    t.Start()
    try:
        if param.StorageType == StorageType.String:
            param.Set(str(value))
        elif param.StorageType == StorageType.Integer:
            param.Set(int(value))
        elif param.StorageType == StorageType.Double:
            param.Set(float(value))
        elif param.StorageType == StorageType.ElementId:
            param.Set(ElementId(int(value)))
        t.Commit()
    except Exception as ex:
        t.Rollback()
        raise ex
    return {"status": "ok", "id": payload["id"], "parameter": param_name}


def create_wall(payload):
    x1 = float(payload["x1"])
    y1 = float(payload["y1"])
    x2 = float(payload["x2"])
    y2 = float(payload["y2"])
    level_id = ElementId(int(payload["level_id"]))
    height   = float(payload.get("height", 3.0))

    start = XYZ(m_to_ft(x1), m_to_ft(y1), 0)
    end   = XYZ(m_to_ft(x2), m_to_ft(y2), 0)
    line  = Line.CreateBound(start, end)

    t = Transaction(doc, "MCP Create Wall")
    t.Start()
    try:
        wall = Wall.Create(doc, line, level_id, False)
        wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM).Set(m_to_ft(height))
        t.Commit()
    except Exception as ex:
        t.Rollback()
        raise ex
    return {"status": "created", "id": str(wall.Id)}


def create_room(payload):
    x        = float(payload["x"])
    y        = float(payload["y"])
    level_id = ElementId(int(payload["level_id"]))
    level    = doc.GetElement(level_id)
    point    = UV(m_to_ft(x), m_to_ft(y))

    t = Transaction(doc, "MCP Create Room")
    t.Start()
    try:
        room = doc.Create.NewRoom(level, point)
        t.Commit()
    except Exception as ex:
        t.Rollback()
        raise ex
    return {"status": "created", "id": str(room.Id)}


def delete_element(payload):
    elem_id = ElementId(int(payload["id"]))
    t = Transaction(doc, "MCP Delete Element")
    t.Start()
    try:
        doc.Delete(elem_id)
        t.Commit()
    except Exception as ex:
        t.Rollback()
        raise ex
    return {"status": "deleted", "id": payload["id"]}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def read_body(req):
    length = req.ContentLength64
    buf    = System.Array[System.Byte](length)
    req.InputStream.Read(buf, 0, length)
    return Text.Encoding.UTF8.GetString(buf)


def send_response(resp, body, status=200):
    resp.StatusCode = status
    data = Text.Encoding.UTF8.GetBytes(body)
    resp.ContentLength64 = data.Length
    resp.OutputStream.Write(data, 0, data.Length)
    resp.OutputStream.Close()


def handle_request(context):
    req  = context.Request
    resp = context.Response
    resp.ContentType = "application/json"
    resp.Headers.Add("Access-Control-Allow-Origin", "*")

    path   = req.Url.AbsolutePath.strip("/")
    method = req.HttpMethod.upper()
    qs     = req.QueryString

    try:
        if method == "GET":
            if path == "ping":
                body = json.dumps({"status": "ok", "document": doc.Title})
            elif path == "walls":
                body = json.dumps(get_all_walls())
            elif path == "rooms":
                body = json.dumps(get_all_rooms())
            elif path == "counts":
                body = json.dumps(get_element_count())
            elif path == "levels":
                body = json.dumps(get_all_levels())
            elif path == "sheets":
                body = json.dumps(get_all_sheets())
            elif path == "views":
                body = json.dumps(get_all_views())
            elif path == "families":
                body = json.dumps(get_all_families())
            elif path == "warnings":
                body = json.dumps(get_warnings())
            elif path == "model_summary":
                body = json.dumps(get_model_summary())
            elif path == "element":
                elem_id = qs["id"]
                if not elem_id:
                    raise Exception("Missing query param: id")
                body = json.dumps(get_element_by_id(elem_id))
            elif path == "schedule":
                name = qs["name"]
                if not name:
                    raise Exception("Missing query param: name")
                body = json.dumps(export_schedule(name))
            else:
                send_response(resp, json.dumps({"error": "Unknown endpoint: " + path}), 404)
                return

        elif method == "POST":
            payload = json.loads(read_body(req))
            if path == "rename_room":
                body = json.dumps(rename_room(payload))
            elif path == "set_parameter":
                body = json.dumps(set_parameter(payload))
            elif path == "create_wall":
                body = json.dumps(create_wall(payload))
            elif path == "create_room":
                body = json.dumps(create_room(payload))
            elif path == "delete_element":
                body = json.dumps(delete_element(payload))
            elif path == "find_elements":
                body = json.dumps(find_elements(payload))
            else:
                send_response(resp, json.dumps({"error": "Unknown endpoint: " + path}), 404)
                return

        else:
            send_response(resp, json.dumps({"error": "Method not allowed"}), 405)
            return

        send_response(resp, body)

    except Exception as ex:
        send_response(resp, json.dumps({"error": str(ex)}), 500)


def server_loop(listener):
    while True:
        try:
            context = listener.GetContext()
            handle_request(context)
        except Exception:
            break


# ── Toggle on button click ────────────────────────────────────────────────────

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
    print("")
    print("  READ   GET  /ping            check connection + document name")
    print("  READ   GET  /model_summary   counts + levels + warnings in one call")
    print("  READ   GET  /counts          element counts by category")
    print("  READ   GET  /levels          all levels with elevation")
    print("  READ   GET  /walls           all walls with length")
    print("  READ   GET  /rooms           all rooms with area")
    print("  READ   GET  /sheets          all sheets")
    print("  READ   GET  /views           all views with sheet placement")
    print("  READ   GET  /families        loaded families by category")
    print("  READ   GET  /warnings        active model warnings")
    print("  READ   GET  /element?id=X    all parameters for one element")
    print("  READ   GET  /schedule?name=X schedule data as JSON table")
    print("  READ   POST /find_elements   filter elements by category + parameter")
    print("  WRITE  POST /rename_room     rename a room by element ID")
    print("  WRITE  POST /set_parameter   set any parameter on any element")
    print("  WRITE  POST /create_wall     create a wall between two points")
    print("  WRITE  POST /create_room     place a room on a level")
    print("  WRITE  POST /delete_element  delete an element by ID")

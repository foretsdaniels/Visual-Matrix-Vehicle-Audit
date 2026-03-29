"""ZPL label generator for Zebra ZP450, 4"x8" labels (812x1624 dots at 203 DPI)."""
from __future__ import annotations

import re
import zipfile
import io
from datetime import datetime
from typing import Optional

from app.parser import RoomEntry
from app.scope import build_label_preview_lines, scope_label

# ---------------------------------------------------------------------------
# Label dimensions
# ---------------------------------------------------------------------------
LABEL_WIDTH = 812   # dots
LABEL_HEIGHT = 1624  # dots
LEFT_MARGIN = 20
RIGHT_MARGIN = 20
TOP_MARGIN = 15
BOTTOM_MARGIN = 20
USABLE_WIDTH = LABEL_WIDTH - LEFT_MARGIN - RIGHT_MARGIN   # 772 dots
BODY_X = LEFT_MARGIN
VEHICLE_INDENT = 20  # extra x for vehicle sub-lines

# ---------------------------------------------------------------------------
# Font definitions: (font_cmd, line_height_dots)
# ^A0N,height,width — Zebra scalable font
# ---------------------------------------------------------------------------
FONTS = {
    "normal": {
        "title":   ("^A0N,28,24", 34),
        "prop":    ("^A0N,20,17", 25),
        "scope":   ("^A0N,20,17", 25),
        "ts":      ("^A0N,18,15", 23),
        "note":    ("^A0N,16,14", 21),
        "sep":     (None, 8),           # separator line
        "room":    ("^A0N,20,17", 25),
        "vehicle": ("^A0N,18,15", 23),
    },
    "compact": {
        "title":   ("^A0N,22,18", 27),
        "prop":    ("^A0N,16,14", 21),
        "scope":   ("^A0N,16,14", 21),
        "ts":      ("^A0N,14,12", 19),
        "note":    ("^A0N,13,11", 18),
        "sep":     (None, 6),
        "room":    ("^A0N,16,14", 20),
        "vehicle": ("^A0N,14,12", 18),
    },
}

# Character width estimates per font mode (dots per char, approximate)
CHAR_WIDTH = {
    "normal": {"room": 10, "vehicle": 9},
    "compact": {"room": 8, "vehicle": 7},
}

MAX_CHARS = {
    mode: {
        kind: USABLE_WIDTH // CHAR_WIDTH[mode][kind]
        for kind in ("room", "vehicle")
    }
    for mode in ("normal", "compact")
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(text: str) -> str:
    """Remove ZPL control chars and non-printable characters."""
    text = text.replace("^", "").replace("~", "").replace("\n", " ").replace("\r", "")
    # Keep printable ASCII (32-126) and common extended chars
    return re.sub(r"[^\x20-\x7E]", "", text)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + ">"


def _header_height(mode: str, has_property: bool, has_departures: bool, is_multi: bool) -> int:
    f = FONTS[mode]
    h = TOP_MARGIN
    h += f["title"][1]   # "Parking Audit"
    if has_property:
        h += f["prop"][1]
    h += f["scope"][1]   # scope label
    h += f["ts"][1]      # timestamp
    if has_departures:
        h += f["note"][1]
    if is_multi:
        h += f["note"][1]
    h += f["sep"][1] + 4  # separator + padding
    return h


def _body_capacity(mode: str, has_property: bool, has_departures: bool) -> int:
    """Max number of body lines that fit on one label (assume is_multi=True for worst-case)."""
    header_h = _header_height(mode, has_property, has_departures, is_multi=True)
    available = LABEL_HEIGHT - header_h - BOTTOM_MARGIN
    # Use room line height as base unit (conservative)
    line_h = FONTS[mode]["room"][1]
    return max(1, available // line_h)


# ---------------------------------------------------------------------------
# ZPL block builder
# ---------------------------------------------------------------------------

def _build_zpl_block(
    body_lines: list[tuple[int, str]],   # (indent_level, text)
    scope_str: str,
    timestamp_str: str,
    has_departures: bool,
    mode: str,
    label_num: int,
    label_total: int,
    property_name: str,
) -> str:
    f = FONTS[mode]
    is_multi = label_total > 1
    lines_out: list[str] = [
        "^XA",
        f"^PW{LABEL_WIDTH}",
        f"^LL{LABEL_HEIGHT}",
        "^LH0,0",
        "^CI28",   # UTF-8
    ]

    y = TOP_MARGIN

    def field(font_cmd: str, x: int, ypos: int, text: str) -> str:
        return f"^FO{x},{ypos}{font_cmd}^FD{text}^FS"

    # Title
    lines_out.append(field(f["title"][0], LEFT_MARGIN, y, "Parking Audit"))
    y += f["title"][1]

    # Property name
    if property_name:
        lines_out.append(field(f["prop"][0], LEFT_MARGIN, y, _sanitize(property_name)))
        y += f["prop"][1]

    # Scope
    lines_out.append(field(f["scope"][0], LEFT_MARGIN, y, f"Scope: {_sanitize(scope_str)}"))
    y += f["scope"][1]

    # Timestamp
    lines_out.append(field(f["ts"][0], LEFT_MARGIN, y, f"Generated: {_sanitize(timestamp_str)}"))
    y += f["ts"][1]

    # Departures note
    if has_departures:
        lines_out.append(field(f["note"][0], LEFT_MARGIN, y, "Includes DUE OUT / STAYOVER"))
        y += f["note"][1]

    # Multi-label indicator
    if is_multi:
        lines_out.append(field(f["note"][0], LEFT_MARGIN, y, f"Label {label_num} of {label_total}"))
        y += f["note"][1]

    # Separator line
    y += 2
    lines_out.append(f"^FO{LEFT_MARGIN},{y}^GB{USABLE_WIDTH},2,2^FS")
    y += f["sep"][1] + 4

    # Body lines
    room_font = f["room"][0]
    room_lh = f["room"][1]
    veh_font = f["vehicle"][0]
    veh_lh = f["vehicle"][1]
    max_room = MAX_CHARS[mode]["room"]
    max_veh = MAX_CHARS[mode]["vehicle"]

    for indent, text in body_lines:
        if indent == 0:
            x = BODY_X
            font_cmd = room_font
            lh = room_lh
            max_c = max_room
        else:
            x = BODY_X + VEHICLE_INDENT
            font_cmd = veh_font
            lh = veh_lh
            max_c = max_veh - (VEHICLE_INDENT // max(1, CHAR_WIDTH[mode]["vehicle"]))
        safe = _sanitize(_truncate(text, max_c))
        lines_out.append(field(font_cmd, x, y, safe))
        y += lh

    lines_out.append("^XZ")
    return "\n".join(lines_out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_zpl(
    entries: list[RoomEntry],
    scope: str,
    generated_at: datetime,
    has_departures: bool,
    allow_multi_label: bool,
    property_name: str = "",
    tz=None,
) -> list[str]:
    """
    Returns list of ZPL strings (one per label).
    """
    from app.scope import scope_label as get_scope_label
    scope_str = get_scope_label(scope)

    if tz:
        ts_local = generated_at.astimezone(tz)
    else:
        ts_local = generated_at
    timestamp_str = ts_local.strftime("%Y-%m-%d %I:%M %p %Z").strip()

    # Build body lines
    body_lines = build_label_preview_lines(entries, has_departures)

    # Determine font mode and split
    cap_normal = _body_capacity("normal", bool(property_name), has_departures)
    cap_compact = _body_capacity("compact", bool(property_name), has_departures)
    n = len(body_lines)

    if n <= cap_normal:
        mode = "normal"
        chunks = [body_lines]
    elif n <= cap_compact:
        mode = "compact"
        chunks = [body_lines]
    elif allow_multi_label:
        mode = "compact"
        cap = _body_capacity("compact", bool(property_name), has_departures)
        chunks = [body_lines[i: i + cap] for i in range(0, n, cap)]
    else:
        # Force everything onto one label in compact mode (truncated)
        mode = "compact"
        cap = _body_capacity("compact", bool(property_name), has_departures)
        chunks = [body_lines[:cap]]

    total = len(chunks)
    zpl_blocks: list[str] = []
    for idx, chunk in enumerate(chunks):
        block = _build_zpl_block(
            body_lines=chunk,
            scope_str=scope_str,
            timestamp_str=timestamp_str,
            has_departures=has_departures,
            mode=mode,
            label_num=idx + 1,
            label_total=total,
            property_name=property_name,
        )
        zpl_blocks.append(block)

    return zpl_blocks


def zpl_to_file(zpl_blocks: list[str], scope: str) -> tuple[bytes, str]:
    """
    Returns (file_bytes, filename).
    If single label: returns .zpl bytes.
    If multiple labels: returns .zip containing label_N_of_M.zpl files.
    """
    scope_clean = scope.replace("/", "_").replace(" ", "_")
    if len(zpl_blocks) == 1:
        filename = f"parking_audit_{scope_clean}.zpl"
        return zpl_blocks[0].encode("ascii", errors="replace"), filename
    else:
        total = len(zpl_blocks)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, block in enumerate(zpl_blocks):
                name = f"label_{i+1}_of_{total}.zpl"
                zf.writestr(name, block)
        filename = f"parking_audit_{scope_clean}_labels.zip"
        return buf.getvalue(), filename

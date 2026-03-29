"""Scope filtering and room grouping logic."""
from __future__ import annotations

from typing import Optional
from app.parser import VehicleRecord, RoomEntry

# Rooms always included in 100/200 and 300/400 scopes
ALWAYS_INCLUDE = {501, 502}

SCOPE_LABELS = {
    "100_200": "100/200s",
    "300_400": "300/400s",
    "full": "Full List",
}


def scope_label(scope: str) -> str:
    return SCOPE_LABELS.get(scope, scope)


def _room_in_scope(room_number: int, scope: str) -> bool:
    if room_number in ALWAYS_INCLUDE and scope in ("100_200", "300_400"):
        return True
    if scope == "100_200":
        return 100 <= room_number <= 299
    if scope == "300_400":
        return 300 <= room_number <= 499
    return True  # full


def group_vehicles(records: list[VehicleRecord]) -> dict[int, list[VehicleRecord]]:
    """Group VehicleRecords by room_number, preserving order."""
    grouped: dict[int, list[VehicleRecord]] = {}
    for rec in records:
        grouped.setdefault(rec.room_number, []).append(rec)
    return grouped


def build_room_entries(
    records: list[VehicleRecord],
    scope: str,
    due_out_rooms: Optional[set[int]] = None,
) -> list[RoomEntry]:
    """
    Group records by room, filter by scope, apply departures status.
    Returns sorted list of RoomEntry.
    """
    grouped = group_vehicles(records)

    entries: list[RoomEntry] = []
    for room_number, vehicles in grouped.items():
        if not _room_in_scope(room_number, scope):
            continue
        status: Optional[str] = None
        if due_out_rooms is not None:
            status = "DUE_OUT" if room_number in due_out_rooms else "STAYOVER"
        entries.append(RoomEntry(
            room_number=room_number,
            vehicles=vehicles,
            status=status,
        ))

    entries.sort(key=lambda e: e.room_number)
    return entries


def build_label_preview_lines(
    entries: list[RoomEntry], has_departures: bool
) -> list[tuple[int, str]]:
    """
    Build flat list of (indent_level, text) representing what appears on labels.
    indent_level=0 for room lines, 1 for vehicle sub-lines.
    """
    lines: list[tuple[int, str]] = []
    for entry in entries:
        if has_departures:
            status_str = entry.status or "STAYOVER"
            lines.append((0, f"ROOM {entry.room_number} \u2014 {status_str}"))
            if not entry.has_vehicle_info:
                lines.append((1, "Not In VM System"))
            else:
                for v in entry.vehicles:
                    if not v.has_vehicle_info:
                        continue
                    parts = _vehicle_parts(v)
                    lines.append((1, " \u2014 ".join(parts) if parts else "Unknown"))
        else:
            if not entry.has_vehicle_info:
                lines.append((0, f"ROOM {entry.room_number} \u2014 Not In VM System"))
            elif len(entry.vehicles) == 1:
                v = entry.vehicles[0]
                parts = [f"ROOM {entry.room_number}"] + _vehicle_parts(v)
                lines.append((0, " \u2014 ".join(parts)))
            else:
                lines.append((0, f"ROOM {entry.room_number}"))
                for v in entry.vehicles:
                    if not v.has_vehicle_info:
                        continue
                    parts = _vehicle_parts(v)
                    lines.append((1, " \u2014 ".join(parts) if parts else "Unknown"))
    return lines


def _vehicle_parts(v: VehicleRecord) -> list[str]:
    """Build display parts for a vehicle: [state plate, make/model year]."""
    parts: list[str] = []
    id_part = " ".join(filter(None, [v.state, v.plate]))
    if id_part:
        parts.append(id_part)
    desc = v.make_model
    if desc and v.year:
        desc = f"{desc} {v.year}"
    elif v.year and not desc:
        desc = v.year
    if desc:
        parts.append(desc)
    return parts


def compute_counts(entries: list[RoomEntry]) -> dict:
    total = len(entries)
    with_vehicles = sum(1 for e in entries if e.has_vehicle_info)
    not_in_system = total - with_vehicles
    due_outs = sum(1 for e in entries if e.status == "DUE_OUT")
    stayovers = sum(1 for e in entries if e.status == "STAYOVER")
    return {
        "total_rooms": total,
        "rooms_with_vehicles": with_vehicles,
        "not_in_system": not_in_system,
        "due_outs": due_outs,
        "stayovers": stayovers,
    }

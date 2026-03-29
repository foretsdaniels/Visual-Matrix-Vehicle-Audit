"""Shared test fixtures for Parking Audit Builder."""
import io
import pytest
import openpyxl


def make_inhouse_xlsx(rows: list[dict], header_start_row: int = 1) -> bytes:
    """
    Build an in-memory .xlsx file with optional blank rows before the header.
    rows: list of dicts with keys: room, plate, state, make_model, year, comment
    header_start_row: 1-based row where headers begin (rows before it are blank)
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    # Pad with blank rows before header
    for _ in range(header_start_row - 1):
        ws.append([None] * 6)
    # Header row
    ws.append(["Room", "Car Make/Model", "Year", "State", "Plate", "Comment"])
    # Data rows
    for r in rows:
        ws.append([
            r.get("room"),
            r.get("make_model", ""),
            r.get("year", ""),
            r.get("state", ""),
            r.get("plate", ""),
            r.get("comment", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_departures_xlsx(rooms: list[int], include_date: bool = False, today_str: str = None) -> bytes:
    """Build a departures .xlsx with a list of room numbers."""
    from datetime import date
    wb = openpyxl.Workbook()
    ws = wb.active
    if include_date:
        ws.append(["Room", "Departure Date"])
        today = today_str or date.today().strftime("%Y-%m-%d")
        for rn in rooms:
            ws.append([rn, today])
    else:
        ws.append(["Room"])
        for rn in rooms:
            ws.append([rn])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

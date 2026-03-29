"""Excel parsing for VM In-House Guests export and Departures export."""
from __future__ import annotations

import io
import re
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VehicleRecord:
    room_number: int
    plate: str = ""
    state: str = ""
    make_model: str = ""
    year: str = ""
    comment: str = ""

    @property
    def has_vehicle_info(self) -> bool:
        return bool(self.plate or self.state or self.make_model)


@dataclass
class RoomEntry:
    room_number: int
    vehicles: list[VehicleRecord] = field(default_factory=list)
    status: Optional[str] = None  # 'DUE_OUT', 'STAYOVER', or None

    @property
    def has_vehicle_info(self) -> bool:
        return any(v.has_vehicle_info for v in self.vehicles)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _clean(val) -> str:
    """Return stripped string or '' for None/NaN."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "n/a", "-"):
        return ""
    return s


def normalize_room(val) -> Optional[int]:
    """Extract digits from val and return as int, or None if not parseable."""
    s = _clean(val)
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

REQUIRED_HEADER_TOKENS = {"room", "plate", "state"}


def _row_values(row) -> list[str]:
    """Return lowercased stripped string values from an openpyxl row."""
    return [_clean(cell.value).lower() for cell in row]


def _detect_header_row_openpyxl(ws) -> Optional[tuple[int, dict]]:
    """
    Return (row_index_1based, col_map) where col_map maps canonical names to
    column indices (0-based within the data row).
    Scans up to first 50 rows.
    """
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=50), start=1):
        vals = _row_values(row)
        if not any(vals):
            continue
        # Check required tokens appear somewhere in this row
        matched = {tok for tok in REQUIRED_HEADER_TOKENS if any(tok in v for v in vals)}
        if matched == REQUIRED_HEADER_TOKENS:
            col_map = _build_col_map(vals)
            return (row_idx, col_map)
    return None


def _build_col_map(header_vals: list[str]) -> dict[str, int]:
    """Map canonical column names to 0-based indices."""
    col_map: dict[str, int] = {}
    for i, v in enumerate(header_vals):
        if not v:
            continue
        if "room" in v and "room" not in col_map:
            col_map["room"] = i
        if "plate" in v and "plate" not in col_map:
            col_map["plate"] = i
        if "state" in v and "state" not in col_map:
            col_map["state"] = i
        if ("make" in v or "model" in v or "vehicle" in v) and "make_model" not in col_map:
            col_map["make_model"] = i
        if "year" in v and "year" not in col_map:
            col_map["year"] = i
        if "comment" in v and "comment" not in col_map:
            col_map["comment"] = i
    return col_map


# ---------------------------------------------------------------------------
# In-House Excel parsing
# ---------------------------------------------------------------------------

def _parse_rows_openpyxl(ws, header_row: int, col_map: dict) -> list[VehicleRecord]:
    records: list[VehicleRecord] = []
    blank_streak = 0
    for row in ws.iter_rows(min_row=header_row + 1):
        vals = [_clean(cell.value) for cell in row]
        # Detect blank row
        if not any(vals):
            blank_streak += 1
            if blank_streak >= 3:
                break
            continue
        blank_streak = 0

        def get(key: str) -> str:
            idx = col_map.get(key)
            if idx is None or idx >= len(vals):
                return ""
            return vals[idx]

        room = normalize_room(get("room"))
        if room is None:
            continue
        records.append(VehicleRecord(
            room_number=room,
            plate=get("plate"),
            state=get("state"),
            make_model=get("make_model"),
            year=get("year"),
            comment=get("comment"),
        ))
    return records


def _parse_inhouse_xlsx(file_bytes: bytes) -> list[VehicleRecord]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    ws = wb.active
    result = _detect_header_row_openpyxl(ws)
    if result is None:
        raise ValueError("Could not detect header row with required columns (Room, Plate, State).")
    header_row, col_map = result
    records = _parse_rows_openpyxl(ws, header_row, col_map)
    wb.close()
    return records


def _parse_inhouse_xls(file_bytes: bytes) -> list[VehicleRecord]:
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=file_bytes)
        ws = wb.sheet_by_index(0)
        # Find header row
        header_row_idx = None
        col_map: dict[str, int] = {}
        for row_i in range(min(50, ws.nrows)):
            vals = [_clean(ws.cell_value(row_i, c)).lower() for c in range(ws.ncols)]
            matched = {tok for tok in REQUIRED_HEADER_TOKENS if any(tok in v for v in vals)}
            if matched == REQUIRED_HEADER_TOKENS:
                col_map = _build_col_map(vals)
                header_row_idx = row_i
                break
        if header_row_idx is None:
            raise ValueError("Could not detect header row in .xls file.")
        records: list[VehicleRecord] = []
        blank_streak = 0
        for row_i in range(header_row_idx + 1, ws.nrows):
            vals = [_clean(ws.cell_value(row_i, c)) for c in range(ws.ncols)]
            if not any(vals):
                blank_streak += 1
                if blank_streak >= 3:
                    break
                continue
            blank_streak = 0

            def get(key: str, _vals=vals) -> str:
                idx = col_map.get(key)
                if idx is None or idx >= len(_vals):
                    return ""
                return _vals[idx]

            room = normalize_room(get("room"))
            if room is None:
                continue
            records.append(VehicleRecord(
                room_number=room,
                plate=get("plate"),
                state=get("state"),
                make_model=get("make_model"),
                year=get("year"),
                comment=get("comment"),
            ))
        return records
    except ImportError:
        # xlrd not available, try LibreOffice conversion
        return _convert_xls_to_xlsx_and_parse(file_bytes)


def _convert_xls_to_xlsx_and_parse(file_bytes: bytes) -> list[VehicleRecord]:
    """Convert .xls to .xlsx using headless LibreOffice, then parse."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xls_path = os.path.join(tmpdir, "input.xls")
        with open(xls_path, "wb") as f:
            f.write(file_bytes)
        result = subprocess.run(
            [
                "libreoffice", "--headless", "--convert-to", "xlsx",
                "--outdir", tmpdir, xls_path,
            ],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed: {result.stderr.decode()}"
            )
        xlsx_path = os.path.join(tmpdir, "input.xlsx")
        if not os.path.exists(xlsx_path):
            raise RuntimeError("LibreOffice did not produce output .xlsx file.")
        with open(xlsx_path, "rb") as f:
            return _parse_inhouse_xlsx(f.read())


def parse_inhouse_excel(file_bytes: bytes, filename: str) -> list[VehicleRecord]:
    """Parse VM In-House Excel file.  Returns list of VehicleRecord (one per row)."""
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".xls":
        return _parse_inhouse_xls(file_bytes)
    return _parse_inhouse_xlsx(file_bytes)


# ---------------------------------------------------------------------------
# Departures Excel parsing
# ---------------------------------------------------------------------------

def parse_departures_excel(file_bytes: bytes, filename: str, today: Optional[date] = None) -> set[int]:
    """Return set of room numbers that are due out today. Returns empty set on any parse error."""
    import openpyxl
    try:
        return _parse_departures_inner(file_bytes, today)
    except Exception:
        return set()


def _parse_departures_inner(file_bytes: bytes, today: Optional[date] = None) -> set[int]:
    import openpyxl
    if today is None:
        today = date.today()

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    ws = wb.active

    # Detect header row (look for "room")
    header_row_idx = None
    col_map: dict[str, int] = {}
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=50), start=1):
        vals = [_clean(cell.value).lower() for cell in row]
        if any("room" in v for v in vals):
            col_map = _build_col_map(vals)
            # Also look for date column
            for i, v in enumerate(vals):
                if any(tok in v for tok in ("depart", "date", "check", "out")) and "date_col" not in col_map:
                    col_map["date_col"] = i
            header_row_idx = row_idx
            break

    if header_row_idx is None or "room" not in col_map:
        # Fallback: scan whole sheet for room-like column
        wb.close()
        return set()

    due_out_rooms: set[int] = set()
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        vals = [_clean(cell.value) for cell in row]
        if not any(vals):
            continue
        room_val = vals[col_map["room"]] if col_map["room"] < len(vals) else ""
        room = normalize_room(room_val)
        if room is None:
            continue
        # Date filtering
        date_col = col_map.get("date_col")
        if date_col is not None and date_col < len(vals):
            raw_date = vals[date_col]
            parsed_date = _parse_date_value(raw_date)
            if parsed_date is not None and parsed_date != today:
                continue
        due_out_rooms.add(room)

    wb.close()
    return due_out_rooms


def _parse_date_value(val: str) -> Optional[date]:
    """Try to parse a date value from a cell."""
    if not val:
        return None
    # Try common formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except Exception:
            pass
    return None



"""Tests for app/parser.py — Excel parsing and normalization."""
import pytest
from tests.conftest import make_inhouse_xlsx, make_departures_xlsx
from app.parser import parse_inhouse_excel, parse_departures_excel, normalize_room


# ---------------------------------------------------------------------------
# normalize_room
# ---------------------------------------------------------------------------

class TestNormalizeRoom:
    def test_plain_integer(self):
        assert normalize_room("214") == 214

    def test_leading_zeros(self):
        assert normalize_room("0214") == 214

    def test_whitespace(self):
        assert normalize_room("  214  ") == 214

    def test_digits_only_extracts_from_string(self):
        assert normalize_room("Room 301") == 301

    def test_none_returns_none(self):
        assert normalize_room(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_room("") is None

    def test_non_numeric_returns_none(self):
        assert normalize_room("ABC") is None

    def test_integer_input(self):
        assert normalize_room(214) == 214


# ---------------------------------------------------------------------------
# parse_inhouse_excel
# ---------------------------------------------------------------------------

class TestParseInhouseExcel:
    def test_basic_parse(self):
        data = [
            {"room": "101", "plate": "ABC123", "state": "FL", "make_model": "Toyota Camry", "year": "2019"},
            {"room": "102", "plate": "XYZ789", "state": "GA", "make_model": "Ford F-150", "year": "2021"},
        ]
        xlsx = make_inhouse_xlsx(data)
        records = parse_inhouse_excel(xlsx, "test.xlsx")
        assert len(records) == 2
        assert records[0].room_number == 101
        assert records[0].plate == "ABC123"
        assert records[0].state == "FL"

    def test_header_not_on_row_1(self):
        """Header detection must work when table starts mid-sheet."""
        data = [
            {"room": "201", "plate": "LMN456", "state": "TX", "make_model": "Honda Accord"},
        ]
        xlsx = make_inhouse_xlsx(data, header_start_row=5)
        records = parse_inhouse_excel(xlsx, "test.xlsx")
        assert len(records) == 1
        assert records[0].room_number == 201

    def test_room_normalization_leading_zeros(self):
        data = [{"room": "0214", "plate": "AAA111", "state": "FL"}]
        xlsx = make_inhouse_xlsx(data)
        records = parse_inhouse_excel(xlsx, "test.xlsx")
        assert records[0].room_number == 214

    def test_room_normalization_with_spaces(self):
        data = [{"room": " 214 ", "plate": "AAA111", "state": "FL"}]
        xlsx = make_inhouse_xlsx(data)
        records = parse_inhouse_excel(xlsx, "test.xlsx")
        assert records[0].room_number == 214

    def test_missing_vehicle_info(self):
        """Room with blank plate/state/make_model has has_vehicle_info=False."""
        data = [
            {"room": "305", "plate": "", "state": "", "make_model": ""},
            {"room": "306", "plate": "DEF456", "state": "FL"},
        ]
        xlsx = make_inhouse_xlsx(data)
        records = parse_inhouse_excel(xlsx, "test.xlsx")
        assert records[0].room_number == 305
        assert records[0].has_vehicle_info is False
        assert records[1].has_vehicle_info is True

    def test_multiple_vehicles_same_room(self):
        """Multiple rows with same room number are all returned."""
        data = [
            {"room": "101", "plate": "ABC123", "state": "FL", "make_model": "Toyota Camry"},
            {"room": "101", "plate": "XYZ789", "state": "FL", "make_model": "Ford F-150"},
        ]
        xlsx = make_inhouse_xlsx(data)
        records = parse_inhouse_excel(xlsx, "test.xlsx")
        assert len(records) == 2
        assert all(r.room_number == 101 for r in records)

    def test_stops_at_blank_region(self):
        """Parsing stops after 3 consecutive blank rows."""
        import openpyxl, io
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Room", "Car Make/Model", "Year", "State", "Plate", "Comment"])
        ws.append([101, "Toyota Camry", "2019", "FL", "ABC123", ""])
        # 3 blank rows
        ws.append([None]*6)
        ws.append([None]*6)
        ws.append([None]*6)
        # Row after blank region — should NOT be included
        ws.append([102, "Ford F-150", "2020", "GA", "XYZ789", ""])
        buf = io.BytesIO(); wb.save(buf)
        records = parse_inhouse_excel(buf.getvalue(), "test.xlsx")
        assert len(records) == 1
        assert records[0].room_number == 101

    def test_invalid_file_raises(self):
        with pytest.raises(Exception):
            parse_inhouse_excel(b"not an excel file", "test.xlsx")


# ---------------------------------------------------------------------------
# parse_departures_excel
# ---------------------------------------------------------------------------

class TestParseDeparturesExcel:
    def test_basic_departures(self):
        xlsx = make_departures_xlsx([101, 205, 314])
        rooms = parse_departures_excel(xlsx, "departures.xlsx")
        assert 101 in rooms
        assert 205 in rooms
        assert 314 in rooms

    def test_departures_with_today_date(self):
        from datetime import date
        today = date.today()
        xlsx = make_departures_xlsx([101, 205], include_date=True, today_str=today.strftime("%Y-%m-%d"))
        rooms = parse_departures_excel(xlsx, "departures.xlsx", today=today)
        assert 101 in rooms
        assert 205 in rooms

    def test_departures_filters_wrong_date(self):
        """Rooms with a date that's not today should be excluded."""
        from datetime import date, timedelta
        today = date.today()
        tomorrow = today + timedelta(days=1)
        xlsx = make_departures_xlsx([101], include_date=True, today_str=tomorrow.strftime("%Y-%m-%d"))
        rooms = parse_departures_excel(xlsx, "departures.xlsx", today=today)
        assert 101 not in rooms

    def test_returns_empty_for_invalid_file(self):
        """Returns empty set (not exception) for unparseable departures."""
        rooms = parse_departures_excel(b"\x00\x01\x02", "bad.xlsx")
        assert isinstance(rooms, set)

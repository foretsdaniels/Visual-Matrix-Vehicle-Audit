"""Tests for departures tagging integration."""
import pytest
from tests.conftest import make_inhouse_xlsx, make_departures_xlsx
from app.parser import parse_inhouse_excel, parse_departures_excel
from app.scope import build_room_entries


class TestDeparturesIntegration:
    def test_due_out_stayover_assigned(self):
        inhouse = make_inhouse_xlsx([
            {"room": "101", "plate": "ABC123", "state": "FL", "make_model": "Camry"},
            {"room": "102", "plate": "XYZ789", "state": "GA", "make_model": "F-150"},
            {"room": "103", "plate": "DEF456", "state": "TX", "make_model": "Civic"},
        ])
        deps = make_departures_xlsx([101, 103])
        records = parse_inhouse_excel(inhouse, "inhouse.xlsx")
        due_out = parse_departures_excel(deps, "departures.xlsx")
        entries = build_room_entries(records, "full", due_out_rooms=due_out)
        by_room = {e.room_number: e for e in entries}
        assert by_room[101].status == "DUE_OUT"
        assert by_room[102].status == "STAYOVER"
        assert by_room[103].status == "DUE_OUT"

    def test_no_departures_no_status(self):
        inhouse = make_inhouse_xlsx([
            {"room": "101", "plate": "ABC123", "state": "FL"},
        ])
        records = parse_inhouse_excel(inhouse, "inhouse.xlsx")
        entries = build_room_entries(records, "full", due_out_rooms=None)
        assert entries[0].status is None

    def test_due_out_appears_in_preview_lines(self):
        from app.scope import build_label_preview_lines
        inhouse = make_inhouse_xlsx([
            {"room": "214", "plate": "FL1234", "state": "FL", "make_model": "Toyota Camry"},
        ])
        deps = make_departures_xlsx([214])
        records = parse_inhouse_excel(inhouse, "inhouse.xlsx")
        due_out = parse_departures_excel(deps, "departures.xlsx")
        entries = build_room_entries(records, "full", due_out_rooms=due_out)
        lines = build_label_preview_lines(entries, has_departures=True)
        # First line should have room and DUE_OUT
        text = lines[0][1]
        assert "214" in text
        assert "DUE_OUT" in text or "DUE OUT" in text

    def test_stayover_appears_in_preview_lines(self):
        from app.scope import build_label_preview_lines
        inhouse = make_inhouse_xlsx([
            {"room": "215", "plate": "GA5678", "state": "GA"},
        ])
        deps = make_departures_xlsx([100])  # different room
        records = parse_inhouse_excel(inhouse, "inhouse.xlsx")
        due_out = parse_departures_excel(deps, "departures.xlsx")
        entries = build_room_entries(records, "full", due_out_rooms=due_out)
        lines = build_label_preview_lines(entries, has_departures=True)
        text = lines[0][1]
        assert "STAYOVER" in text

    def test_no_due_out_stayover_when_no_departures_file(self):
        from app.scope import build_label_preview_lines
        inhouse = make_inhouse_xlsx([
            {"room": "214", "plate": "FL1234", "state": "FL"},
        ])
        records = parse_inhouse_excel(inhouse, "inhouse.xlsx")
        entries = build_room_entries(records, "full", due_out_rooms=None)
        lines = build_label_preview_lines(entries, has_departures=False)
        for _, text in lines:
            assert "DUE_OUT" not in text
            assert "STAYOVER" not in text
            assert "DUE OUT" not in text

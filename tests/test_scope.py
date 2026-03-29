"""Tests for app/scope.py — scope filtering and room grouping."""
import pytest
from app.parser import VehicleRecord
from app.scope import build_room_entries, compute_counts, build_label_preview_lines, scope_label


def _make_record(room: int, plate: str = "ABC123", state: str = "FL",
                 make_model: str = "Toyota Camry") -> VehicleRecord:
    return VehicleRecord(room_number=room, plate=plate, state=state, make_model=make_model)


def _make_empty_record(room: int) -> VehicleRecord:
    return VehicleRecord(room_number=room)


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------

class TestScopeFiltering:
    def _rooms_in_scope(self, room_nums: list[int], scope: str) -> set[int]:
        records = [_make_record(r) for r in room_nums]
        entries = build_room_entries(records, scope)
        return {e.room_number for e in entries}

    def test_100_200_includes_100_to_299(self):
        rooms = self._rooms_in_scope([99, 100, 199, 200, 299, 300], "100_200")
        assert 100 in rooms
        assert 199 in rooms
        assert 299 in rooms
        assert 99 not in rooms
        assert 300 not in rooms

    def test_100_200_always_includes_501_502(self):
        rooms = self._rooms_in_scope([101, 501, 502], "100_200")
        assert 501 in rooms
        assert 502 in rooms

    def test_100_200_501_502_even_if_only_rooms(self):
        """501 and 502 must be included in 100/200 scope regardless."""
        records = [_make_record(501), _make_record(502)]
        entries = build_room_entries(records, "100_200")
        nums = {e.room_number for e in entries}
        assert 501 in nums
        assert 502 in nums

    def test_300_400_includes_300_to_499(self):
        rooms = self._rooms_in_scope([299, 300, 399, 400, 499, 500], "300_400")
        assert 300 in rooms
        assert 499 in rooms
        assert 299 not in rooms
        assert 500 not in rooms

    def test_300_400_always_includes_501_502(self):
        rooms = self._rooms_in_scope([301, 501, 502], "300_400")
        assert 501 in rooms
        assert 502 in rooms

    def test_full_includes_all_rooms(self):
        room_nums = [50, 101, 250, 350, 450, 501, 502, 600]
        rooms = self._rooms_in_scope(room_nums, "full")
        assert rooms == set(room_nums)

    def test_results_sorted_ascending(self):
        records = [_make_record(r) for r in [250, 101, 199, 150]]
        entries = build_room_entries(records, "100_200")
        nums = [e.room_number for e in entries]
        assert nums == sorted(nums)

    def test_missing_vehicle_rooms_included(self):
        """Rooms with no vehicle info still appear in scope."""
        records = [_make_empty_record(150), _make_record(151)]
        entries = build_room_entries(records, "100_200")
        nums = {e.room_number for e in entries}
        assert 150 in nums


# ---------------------------------------------------------------------------
# Room grouping and multiple vehicles
# ---------------------------------------------------------------------------

class TestRoomGrouping:
    def test_multiple_vehicles_grouped(self):
        records = [
            _make_record(214, plate="ABC123"),
            _make_record(214, plate="XYZ789"),
        ]
        entries = build_room_entries(records, "100_200")
        assert len(entries) == 1
        entry = entries[0]
        assert len(entry.vehicles) == 2
        plates = {v.plate for v in entry.vehicles}
        assert "ABC123" in plates
        assert "XYZ789" in plates


# ---------------------------------------------------------------------------
# Departures tagging
# ---------------------------------------------------------------------------

class TestDeparturesTagging:
    def test_due_out_tagging(self):
        records = [_make_record(101), _make_record(102)]
        due_out = {101}
        entries = build_room_entries(records, "full", due_out_rooms=due_out)
        by_room = {e.room_number: e for e in entries}
        assert by_room[101].status == "DUE_OUT"
        assert by_room[102].status == "STAYOVER"

    def test_no_departures_no_status(self):
        records = [_make_record(101)]
        entries = build_room_entries(records, "full", due_out_rooms=None)
        assert entries[0].status is None

    def test_empty_due_out_set_all_stayover(self):
        records = [_make_record(101), _make_record(102)]
        entries = build_room_entries(records, "full", due_out_rooms=set())
        assert all(e.status == "STAYOVER" for e in entries)


# ---------------------------------------------------------------------------
# Preview lines
# ---------------------------------------------------------------------------

class TestPreviewLines:
    def test_no_departures_single_vehicle(self):
        from app.parser import RoomEntry
        entry = RoomEntry(
            room_number=214,
            vehicles=[VehicleRecord(214, plate="ABC123", state="FL", make_model="Toyota Camry")],
            status=None,
        )
        lines = build_label_preview_lines([entry], has_departures=False)
        assert len(lines) == 1
        indent, text = lines[0]
        assert indent == 0
        assert "214" in text
        assert "ABC123" in text
        assert "FL" in text

    def test_no_departures_missing_vehicle(self):
        from app.parser import RoomEntry
        entry = RoomEntry(room_number=216, vehicles=[VehicleRecord(216)], status=None)
        lines = build_label_preview_lines([entry], has_departures=False)
        assert len(lines) == 1
        assert "Not In VM System" in lines[0][1]

    def test_with_departures_due_out(self):
        from app.parser import RoomEntry
        entry = RoomEntry(
            room_number=214,
            vehicles=[VehicleRecord(214, plate="ABC123", state="FL", make_model="Toyota Camry")],
            status="DUE_OUT",
        )
        lines = build_label_preview_lines([entry], has_departures=True)
        # First line: room + DUE_OUT
        assert "DUE_OUT" in lines[0][1] or "DUE OUT" in lines[0][1]
        # Second line: vehicle info
        assert lines[1][0] == 1  # indented

    def test_with_departures_stayover_missing(self):
        from app.parser import RoomEntry
        entry = RoomEntry(room_number=216, vehicles=[VehicleRecord(216)], status="STAYOVER")
        lines = build_label_preview_lines([entry], has_departures=True)
        assert "STAYOVER" in lines[0][1]
        assert "Not In VM System" in lines[1][1]


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------

class TestComputeCounts:
    def test_counts(self):
        from app.parser import RoomEntry
        entries = [
            RoomEntry(101, [VehicleRecord(101, plate="P1", state="FL")], "DUE_OUT"),
            RoomEntry(102, [VehicleRecord(102)], "STAYOVER"),
            RoomEntry(103, [VehicleRecord(103, plate="P3", state="GA")], "STAYOVER"),
        ]
        c = compute_counts(entries)
        assert c["total_rooms"] == 3
        assert c["rooms_with_vehicles"] == 2
        assert c["not_in_system"] == 1
        assert c["due_outs"] == 1
        assert c["stayovers"] == 2


# ---------------------------------------------------------------------------
# Scope labels
# ---------------------------------------------------------------------------

class TestScopeLabel:
    def test_labels(self):
        assert scope_label("100_200") == "100/200s"
        assert scope_label("300_400") == "300/400s"
        assert scope_label("full") == "Full List"

import pytest

from contract import Event, ScheduleInput
from plugin import find_schedule_conflicts
from verifier import verify_output


@pytest.mark.parametrize(
    "start,end,room,speakers,count",
    [
        ("14:00:00", "15:00:00", "R", ["P"], 1),
        ("15:00:00", "16:00:00", "R", ["P"], 0),
        ("13:00:00", "14:00:00", "R", ["P"], 0),
        ("14:30:00", "14:45:00", "Other", ["P"], 1),
        ("14:30:00", "14:45:00", "R", [], 1),
        ("14:30:00", "14:45:00", "Other", [], 0),
        ("14:59:59", "15:00:01", "R", [], 1),
        ("13:00:00", "16:00:00", "R", ["P"], 1),
    ],
)
def test_interval_resource_boundaries(start, end, room, speakers, count, tmp_path):
    day = "2026-11-02T"
    value = ScheduleInput(
        [
            Event("B", "First", "R", ["P"], day + "14:00:00Z", day + "15:00:00Z"),
            Event("A", "Second", room, speakers, day + start + "Z", day + end + "Z"),
        ]
    )
    result = find_schedule_conflicts(value, tmp_path)
    assert len(result.conflicts) == count
    assert verify_output("find_schedule_conflicts", value, result, tmp_path)["valid"]
    if count:
        pair = result.conflicts[0]
        assert pair.event_ids == ["A", "B"]
        assert pair.overlap_start_utc == day + max(start, "14:00:00") + "Z"
        assert pair.overlap_end_utc == day + min(end, "15:00:00") + "Z"
        assert pair.room == ("R" if room == "R" else None)


def test_shared_speakers_sorted_and_both_reasons_returned_once(tmp_path):
    value = ScheduleInput(
        [
            Event(key, "Title", "R", speakers, "2026-11-02T14:00:00Z", "2026-11-02T15:00:00Z")
            for key, speakers in [("Z", ["P2", "P1", "P3"]), ("A", ["P3", "P1"])]
        ]
    )
    result = find_schedule_conflicts(value, tmp_path)
    assert len(result.conflicts) == 1
    assert result.conflicts[0].shared_speakers == ["P1", "P3"]
    assert result.conflicts[0].room == "R"


def test_cross_midnight_conflict_in_utc(tmp_path):
    value = ScheduleInput(
        [
            Event("A", "Title", "R", [], "2026-11-02T23:45:00-02:00", "2026-11-03T00:15:00-02:00"),
            Event("B", "Title", "R", [], "2026-11-03T07:30:00+05:30", "2026-11-03T08:00:00+05:30"),
        ]
    )
    pair = find_schedule_conflicts(value, tmp_path).conflicts[0]
    assert pair.overlap_start_utc == "2026-11-03T02:00:00Z"
    assert pair.overlap_end_utc == "2026-11-03T02:15:00Z"


def test_same_wall_times_can_be_disjoint_and_different_wall_times_can_overlap(tmp_path):
    value = ScheduleInput(
        [
            Event("A", "Title", "R", [], "2026-11-02T09:00:00-05:00", "2026-11-02T10:00:00-05:00"),
            Event("B", "Title", "R", [], "2026-11-02T09:00:00+05:00", "2026-11-02T10:00:00+05:00"),
            Event("C", "Title", "R", [], "2026-11-02T19:30:00+05:30", "2026-11-02T20:30:00+05:30"),
        ]
    )
    assert [c.event_ids for c in find_schedule_conflicts(value, tmp_path).conflicts] == [["A", "C"]]

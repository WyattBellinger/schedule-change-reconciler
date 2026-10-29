import copy
import random

import pytest
from conftest import fixture
from slimconfig import build_output, plain_output

from contract import ReconcileInput, ScheduleInput
from plugin import find_schedule_conflicts, replay_schedule
from verifier.oracle import replay


@pytest.mark.parametrize("name", ["example", "long-history"])
def test_matches_hand_specified_complete_schedule(name, tmp_path):
    given = build_output(fixture(f"{name}.json"), ReconcileInput)
    wanted = fixture(f"{name}-expected.json")
    assert plain_output(replay_schedule(given, tmp_path)) == wanted
    assert replay(given) == wanted


def test_input_is_not_mutated_and_runs_are_independent(arguments, tmp_path):
    given = build_output(arguments, ReconcileInput)
    original = copy.deepcopy(given)
    first = replay_schedule(given, tmp_path)
    assert given == original
    assert replay_schedule(given, tmp_path) == first
    assert not list(tmp_path.iterdir())


def test_empty_and_all_cancelled_schedules(arguments, tmp_path):
    assert plain_output(replay_schedule(ReconcileInput([], []), tmp_path)) == {
        "events": [],
        "cancelled_event_ids": [],
        "conflicts": [],
    }
    arguments["messages"] = [
        {"message_id": f"M{n}", "text": f"Cancel {event['event_id']}."}
        for n, event in enumerate(arguments["initial_events"])
    ]
    result = replay_schedule(build_output(arguments, ReconcileInput), tmp_path)
    assert result.events == result.conflicts == []
    assert result.cancelled_event_ids == ["A", "B", "C", "D", "E"]


def test_swap_is_simultaneous_and_only_changes_rooms(arguments, tmp_path):
    arguments["initial_events"] = arguments["initial_events"][:2]
    arguments["messages"] = [{"message_id": "M", "text": "Swap rooms of A and B."}]
    result = replay_schedule(build_output(arguments, ReconcileInput), tmp_path)
    assert [row.room for row in result.events] == ["Pine", "Oak"]
    assert [row.start_utc for row in result.events] == ["2026-11-02T14:00:00Z", "2026-11-02T14:30:00Z"]
    assert [row.speakers for row in result.events] == [["P1"], ["P2"]]
    assert not result.conflicts


def test_cancelled_state_keeps_all_later_field_changes(arguments, tmp_path):
    texts = [
        "Cancel A.",
        "Move A to room New.",
        "Swap rooms of A and B.",
        "Reschedule A to 2026-11-03T00:15:00+05:45 through 2026-11-03T00:45:00+05:45.",
        "Correction: Reinstate A.",
    ]
    arguments["messages"] = [{"message_id": f"M{i}", "text": text} for i, text in enumerate(texts)]
    result = replay_schedule(build_output(arguments, ReconcileInput), tmp_path)
    assert result.events[0].room == "Pine"
    assert result.events[1].room == "New"
    assert result.events[0].start_utc == "2026-11-02T18:30:00Z"
    assert not result.cancelled_event_ids


def test_no_messages_still_checks_the_initial_schedule(arguments, tmp_path):
    arguments["messages"] = []
    given = build_output(arguments, ReconcileInput)
    result = replay_schedule(given, tmp_path)
    helper = find_schedule_conflicts(ScheduleInput(given.initial_events), tmp_path)
    assert result.conflicts == helper.conflicts
    assert [pair.event_ids for pair in result.conflicts] == [["C", "E"]]


def test_seeded_histories_match_independent_oracle(arguments, tmp_path):
    rng = random.Random(480)
    for _ in range(30):
        cancelled = set()
        messages = []
        for index in range(60):
            key = rng.choice("ABCDE")
            operation = rng.randrange(4)
            if operation == 0:
                command = f"{'Reinstate' if key in cancelled else 'Cancel'} {key}."
                if key in cancelled:
                    cancelled.remove(key)
                else:
                    cancelled.add(key)
            elif operation == 1:
                command = f"Move {key} to room {rng.choice(['Oak', 'Pine', 'Elm'])}."
            elif operation == 2:
                other = rng.choice([k for k in "ABCDE" if k != key])
                command = f"Swap rooms of {key} and {other}."
            else:
                hour = rng.randrange(8, 20)
                zone = rng.choice(["Z", "+05:45", "-04:00", "+14:00"])
                command = f"Reschedule {key} to 2026-11-02T{hour:02}:00:00{zone} through 2026-11-02T{hour + 1:02}:00:00{zone}."
            messages.append({"message_id": f"M{index}", "text": ("Correction: " if index % 7 == 0 else "") + command})
        given = build_output({**arguments, "messages": messages}, ReconcileInput)
        assert plain_output(replay_schedule(given, tmp_path)) == replay(given)

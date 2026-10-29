"""Replay a defined announcement language and calculate final resource collisions."""

import re
from dataclasses import replace
from itertools import combinations
from pathlib import Path

from contract import (
    Conflict,
    ConflictsOutput,
    Event,
    FinalEvent,
    IntervalInput,
    ReconcileInput,
    ReconcileOutput,
    ScheduleInput,
)

from .times import normalize_interval, parse_time, utc_text

IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
COMMANDS = {
    "cancel": re.compile(rf"Cancel ({IDENTIFIER})\."),
    "reinstate": re.compile(rf"Reinstate ({IDENTIFIER})\."),
    "move": re.compile(rf"Move ({IDENTIFIER}) to room ({IDENTIFIER})\."),
    "swap": re.compile(rf"Swap rooms of ({IDENTIFIER}) and ({IDENTIFIER})\."),
    "reschedule": re.compile(rf"Reschedule ({IDENTIFIER}) to (\S+) through (\S+)\."),
}


def valid_id(value: str) -> bool:
    return re.fullmatch(IDENTIFIER, value) is not None


def validate_events(events: list[Event], workspace: Path) -> dict[str, Event]:
    table = {}
    for event in events:
        if not valid_id(event.event_id) or event.event_id in table:
            raise ValueError("event IDs must be valid and unique")
        if not event.title.strip() or not valid_id(event.room):
            raise ValueError("event titles must be nonblank and room IDs valid")
        if any(not valid_id(speaker) for speaker in event.speakers) or len(set(event.speakers)) != len(event.speakers):
            raise ValueError("speaker IDs must be valid and unique per event")
        normalize_interval(IntervalInput(event.start, event.end), workspace)
        table[event.event_id] = replace(event, speakers=list(event.speakers))
    return table


def final_events(events: list[Event], workspace: Path) -> list[FinalEvent]:
    table = validate_events(events, workspace)
    result = []
    for event in sorted(table.values(), key=lambda row: row.event_id):
        interval = normalize_interval(IntervalInput(event.start, event.end), workspace)
        result.append(
            FinalEvent(
                event.event_id, event.title, event.room, sorted(event.speakers), interval.start_utc, interval.end_utc
            )
        )
    return result


def collisions(events: list[FinalEvent]) -> list[Conflict]:
    result = []
    for left, right in combinations(events, 2):
        start = max(parse_time(left.start_utc), parse_time(right.start_utc))
        end = min(parse_time(left.end_utc), parse_time(right.end_utc))
        room = left.room if left.room == right.room else None
        speakers = sorted(set(left.speakers) & set(right.speakers))
        if start < end and (room is not None or speakers):
            result.append(Conflict([left.event_id, right.event_id], room, speakers, utc_text(start), utc_text(end)))
    return result


def find_schedule_conflicts(value: ScheduleInput, workspace: Path) -> ConflictsOutput:
    return ConflictsOutput(collisions(final_events(value.events, workspace)))


def replay_schedule(value: ReconcileInput, workspace: Path) -> ReconcileOutput:
    table = validate_events(value.initial_events, workspace)
    cancelled = set()
    seen = set()
    for message in value.messages:
        if not valid_id(message.message_id) or message.message_id in seen:
            raise ValueError("message IDs must be valid and unique")
        seen.add(message.message_id)
        text = message.text.removeprefix("Correction: ")
        parsed = [(kind, pattern.fullmatch(text)) for kind, pattern in COMMANDS.items()]
        matched = [(kind, match.groups()) for kind, match in parsed if match]
        if len(matched) != 1:
            raise ValueError(f"message {message.message_id}: unsupported announcement syntax")
        kind, parts = matched[0]
        event_id = parts[0]
        if event_id not in table:
            raise ValueError(f"message {message.message_id}: unknown event {event_id}")
        if kind == "cancel":
            if event_id in cancelled:
                raise ValueError("cannot cancel an already cancelled event")
            cancelled.add(event_id)
        elif kind == "reinstate":
            if event_id not in cancelled:
                raise ValueError("cannot reinstate an active event")
            cancelled.remove(event_id)
        elif kind == "move":
            table[event_id] = replace(table[event_id], room=parts[1])
        elif kind == "swap":
            other = parts[1]
            if other == event_id or other not in table:
                raise ValueError("room swaps require two distinct known events")
            first_room, second_room = table[event_id].room, table[other].room
            table[event_id] = replace(table[event_id], room=second_room)
            table[other] = replace(table[other], room=first_room)
        else:
            normalize_interval(IntervalInput(parts[1], parts[2]), workspace)
            table[event_id] = replace(table[event_id], start=parts[1], end=parts[2])
    active = final_events([event for key, event in table.items() if key not in cancelled], workspace)
    return ReconcileOutput(active, sorted(cancelled), collisions(active))

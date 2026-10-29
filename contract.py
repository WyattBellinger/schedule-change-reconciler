"""Typed task and tool declarations for the schedule replay benchmark."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    NORMALIZE_INTERVAL = "normalize_interval"
    FIND_SCHEDULE_CONFLICTS = "find_schedule_conflicts"
    REPLAY_SCHEDULE = "replay_schedule"


class Task(Enum):
    RECONCILE_SCHEDULE = "reconcile-schedule"
    REPLAY_SCHEDULE = "replay-schedule"


@dataclass
class Event(Output):
    event_id: str
    title: str
    room: str
    speakers: list[str]
    start: Annotated[str, "YYYY-MM-DDTHH:MM:SS followed by Z or an explicit numeric UTC offset"]
    end: str


@dataclass
class Announcement(Output):
    message_id: str
    text: Annotated[str, "One exact announcement sentence; list order is authoritative, including corrections"]


@dataclass
class ReconcileInput(Output):
    initial_events: list[Event]
    messages: list[Announcement]


@dataclass
class IntervalInput(Output):
    start: str
    end: str


@dataclass
class IntervalOutput(Output):
    start_utc: str
    end_utc: str
    duration_seconds: int


@dataclass
class ScheduleInput(Output):
    events: Annotated[list[Event], "The candidate active schedule; no cancelled events"]


@dataclass
class FinalEvent(Output):
    event_id: str
    title: str
    room: str
    speakers: Annotated[list[str], "Unique speaker IDs in lexicographic order"]
    start_utc: str
    end_utc: str


@dataclass
class Conflict(Output):
    event_ids: Annotated[list[str], "Exactly two different event IDs in lexicographic order"]
    room: Annotated[str | None, "The common room, or null when only speakers conflict"]
    shared_speakers: list[str]
    overlap_start_utc: str
    overlap_end_utc: str


@dataclass
class ConflictsOutput(Output):
    conflicts: Annotated[list[Conflict], "All conflict pairs, sorted by their pair of IDs"]


@dataclass
class ReconcileOutput(Output):
    events: Annotated[list[FinalEvent], "All active events, sorted by event_id, with canonical UTC times"]
    cancelled_event_ids: Annotated[list[str], "All currently cancelled IDs in lexicographic order"]
    conflicts: Annotated[list[Conflict], "Every remaining room or shared-speaker conflict, once per pair"]


TOOLS = {
    Tool.NORMALIZE_INTERVAL: (IntervalInput, IntervalOutput),
    Tool.FIND_SCHEDULE_CONFLICTS: (ScheduleInput, ConflictsOutput),
    Tool.REPLAY_SCHEDULE: (ReconcileInput, ReconcileOutput),
}
TASKS = {
    Task.RECONCILE_SCHEDULE: (ReconcileInput, ReconcileOutput),
    Task.REPLAY_SCHEDULE: (ReconcileInput, ReconcileOutput),
}

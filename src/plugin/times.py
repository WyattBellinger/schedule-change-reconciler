"""Strict explicit-offset timestamps; the runtime uses Python's Gregorian calendar."""

import re
from datetime import UTC, datetime
from pathlib import Path

from contract import IntervalInput, IntervalOutput

TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})")


def parse_time(value: str) -> datetime:
    if not TIMESTAMP.fullmatch(value):
        raise ValueError("timestamps require seconds and Z or an explicit numeric UTC offset")
    if value.endswith("-00:00"):
        raise ValueError("-00:00 denotes an unknown offset and is not accepted")
    if not value.endswith("Z"):
        hours, minutes = int(value[-5:-3]), int(value[-2:])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
            raise ValueError("UTC offsets must be between -14:00 and +14:00")
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except (ValueError, OverflowError) as error:
        raise ValueError("invalid calendar timestamp or UTC date outside years 0001..9999") from error


def utc_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_interval(value: IntervalInput, workspace: Path) -> IntervalOutput:
    start, end = parse_time(value.start), parse_time(value.end)
    if end <= start:
        raise ValueError("event end must be strictly after its start in UTC")
    return IntervalOutput(utc_text(start), utc_text(end), int((end - start).total_seconds()))

"""Independent oracle: integer Gregorian arithmetic, token parsing and a time sweep.

No runtime imports, clock, model, network, reference output or workspace evidence.
The original typed task arguments are the sole authority.
"""

import re

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
STAMP = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(Z|[+-][0-9]{2}:[0-9]{2})")


def leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def month_days(year):
    return [31, 29 if leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def year_days(year):
    previous = year - 1
    return 365 * previous + previous // 4 - previous // 100 + previous // 400


def seconds(text):
    match = STAMP.fullmatch(text)
    if match is None:
        raise ValueError("timestamp requires exact date, seconds and an explicit offset")
    year, month, day, hour, minute, second = [int(value) for value in match.groups()[:6]]
    zone = match.group(7)
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ValueError("invalid timestamp year or month")
    if not 1 <= day <= month_days(year)[month - 1] or hour > 23 or minute > 59 or second > 59:
        raise ValueError("invalid calendar date or clock time")
    offset = 0
    if zone != "Z":
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if zone == "-00:00" or hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
            raise ValueError("invalid or unknown UTC offset")
        offset = (hours * 60 + minutes) * 60 * (1 if zone[0] == "+" else -1)
    day_number = year_days(year) + sum(month_days(year)[: month - 1]) + day - 1
    result = day_number * 86400 + hour * 3600 + minute * 60 + second - offset
    if not 0 <= result < year_days(10000) * 86400:
        raise ValueError("UTC timestamp outside years 0001..9999")
    return result


def timestamp(value):
    days, clock = divmod(value, 86400)
    low, high = 1, 10000
    while low + 1 < high:
        middle = (low + high) // 2
        if year_days(middle) <= days:
            low = middle
        else:
            high = middle
    day = days - year_days(low)
    month = 1
    for count in month_days(low):
        if day < count:
            break
        day -= count
        month += 1
    hour, remainder = divmod(clock, 3600)
    minute, second = divmod(remainder, 60)
    return f"{low:04d}-{month:02d}-{day + 1:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


def interval(start, end):
    first, last = seconds(start), seconds(end)
    if last <= first:
        raise ValueError("end must follow start in UTC")
    return {"start_utc": timestamp(first), "end_utc": timestamp(last), "duration_seconds": last - first}


def identifier(value):
    if ID.fullmatch(value) is None:
        raise ValueError("invalid identifier")
    return value


def event_table(events):
    result = {}
    for event in events:
        key = identifier(event.event_id)
        if key in result or not event.title.strip():
            raise ValueError("duplicate event ID or blank title")
        identifier(event.room)
        for speaker in event.speakers:
            identifier(speaker)
        if len(set(event.speakers)) != len(event.speakers):
            raise ValueError("duplicate speaker")
        interval(event.start, event.end)
        result[key] = {
            "event_id": key,
            "title": event.title,
            "room": event.room,
            "speakers": sorted(event.speakers),
            "start": event.start,
            "end": event.end,
        }
    return result


def active_rows(table, cancelled):
    rows = []
    for key in sorted(table):
        if key in cancelled:
            continue
        event = table[key]
        times = interval(event["start"], event["end"])
        rows.append(
            {
                "event_id": key,
                "title": event["title"],
                "room": event["room"],
                "speakers": event["speakers"],
                "start_utc": times["start_utc"],
                "end_utc": times["end_utc"],
            }
        )
    return rows


def conflicts(rows):
    """Sweep by UTC start; ended events leave before coincident starts enter."""
    pending = []
    found = []
    for row in sorted(rows, key=lambda item: (item["start_utc"], item["event_id"])):
        pending = [other for other in pending if other["end_utc"] > row["start_utc"]]
        for other in pending:
            room = row["room"] if row["room"] == other["room"] else None
            speakers = sorted(set(row["speakers"]).intersection(other["speakers"]))
            if room is not None or speakers:
                found.append(
                    {
                        "event_ids": sorted([row["event_id"], other["event_id"]]),
                        "room": room,
                        "shared_speakers": speakers,
                        "overlap_start_utc": max(row["start_utc"], other["start_utc"]),
                        "overlap_end_utc": min(row["end_utc"], other["end_utc"]),
                    }
                )
        pending.append(row)
    return sorted(found, key=lambda item: item["event_ids"])


def replay(value):
    table = event_table(value.initial_events)
    cancelled = set()
    seen = set()
    for message in value.messages:
        key = identifier(message.message_id)
        if key in seen:
            raise ValueError("duplicate message ID")
        seen.add(key)
        text = message.text.removeprefix("Correction: ")
        if not text.endswith("."):
            raise ValueError("announcement must end with a period")
        parts = text[:-1].split(" ")
        if len(parts) == 6 and parts[:3] == ["Swap", "rooms", "of"] and parts[4] == "and":
            first, second = parts[3], parts[5]
            if first not in table or second not in table or first == second:
                raise ValueError("swap needs two distinct known events")
            rooms = [table[second]["room"], table[first]["room"]]
            table[first]["room"], table[second]["room"] = rooms
            continue
        if len(parts) < 2 or parts[1] not in table:
            raise ValueError("unknown event or invalid command")
        event = table[parts[1]]
        if len(parts) == 2 and parts[0] == "Cancel":
            if parts[1] in cancelled:
                raise ValueError("event already cancelled")
            cancelled.add(parts[1])
        elif len(parts) == 2 and parts[0] == "Reinstate":
            if parts[1] not in cancelled:
                raise ValueError("event is active")
            cancelled.remove(parts[1])
        elif len(parts) == 5 and parts[0] == "Move" and parts[2:4] == ["to", "room"]:
            event["room"] = identifier(parts[4])
        elif len(parts) == 6 and parts[0] == "Reschedule" and parts[2] == "to" and parts[4] == "through":
            interval(parts[3], parts[5])
            event["start"], event["end"] = parts[3], parts[5]
        else:
            raise ValueError("unsupported announcement syntax")
    rows = active_rows(table, cancelled)
    return {"events": rows, "cancelled_event_ids": sorted(cancelled), "conflicts": conflicts(rows)}

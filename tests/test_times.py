import pytest
from slimconfig import plain_output

from contract import IntervalInput
from plugin import normalize_interval
from verifier import verify_input, verify_output
from verifier.oracle import interval


@pytest.mark.parametrize(
    "start,end,utc_start,utc_end,duration",
    [
        (
            "2026-11-03T00:15:00+05:45",
            "2026-11-03T00:45:00+05:45",
            "2026-11-02T18:30:00Z",
            "2026-11-02T19:00:00Z",
            1800,
        ),
        (
            "2026-12-31T23:30:00-02:00",
            "2027-01-01T00:00:00-02:00",
            "2027-01-01T01:30:00Z",
            "2027-01-01T02:00:00Z",
            1800,
        ),
        ("2000-02-28T23:59:59Z", "2000-03-01T00:00:00Z", "2000-02-28T23:59:59Z", "2000-03-01T00:00:00Z", 86401),
        ("1900-02-28T23:59:59Z", "1900-03-01T00:00:00Z", "1900-02-28T23:59:59Z", "1900-03-01T00:00:00Z", 1),
        (
            "2026-11-01T01:30:00-04:00",
            "2026-11-01T01:30:00-05:00",
            "2026-11-01T05:30:00Z",
            "2026-11-01T06:30:00Z",
            3600,
        ),
        (
            "2026-11-02T23:00:00+14:00",
            "2026-11-02T01:00:00-14:00",
            "2026-11-02T09:00:00Z",
            "2026-11-02T15:00:00Z",
            21600,
        ),
        ("0001-01-01T00:00:00Z", "0001-01-01T00:00:01+00:00", "0001-01-01T00:00:00Z", "0001-01-01T00:00:01Z", 1),
        ("9999-12-31T23:59:58Z", "9999-12-31T23:59:59Z", "9999-12-31T23:59:58Z", "9999-12-31T23:59:59Z", 1),
    ],
)
def test_known_utc_intervals(start, end, utc_start, utc_end, duration, tmp_path):
    given = IntervalInput(start, end)
    wanted = {"start_utc": utc_start, "end_utc": utc_end, "duration_seconds": duration}
    result = normalize_interval(given, tmp_path)
    assert plain_output(result) == interval(start, end) == wanted
    assert verify_input("normalize_interval", given)["valid"]
    assert verify_output("normalize_interval", given, result, tmp_path)["valid"]


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-11-02T09:00:00", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00Z", "2026-11-02T10:00:00Z"),
        ("2026-11-02 09:00:00Z", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:00z", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:00.1Z", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:60Z", "2026-11-02T10:00:00Z"),
        ("2026-11-02T24:00:00Z", "2026-11-03T10:00:00Z"),
        ("1900-02-29T09:00:00Z", "1900-03-01T10:00:00Z"),
        ("2026-02-29T09:00:00Z", "2026-03-01T10:00:00Z"),
        ("2026-04-31T09:00:00Z", "2026-05-01T10:00:00Z"),
        ("0000-01-01T09:00:00Z", "2026-11-02T10:00:00Z"),
        ("2026-00-01T09:00:00Z", "2026-11-02T10:00:00Z"),
        ("2026-13-01T09:00:00Z", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:00-00:00", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:00+14:01", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:00-15:00", "2026-11-02T10:00:00Z"),
        ("2026-11-02T09:00:00+01:60", "2026-11-02T10:00:00Z"),
        ("0001-01-01T00:00:00+00:01", "0001-01-01T01:00:00Z"),
        ("9999-12-31T23:59:59-00:01", "9999-12-31T23:59:59Z"),
        ("2026-11-02T09:00:00Z", "2026-11-02T09:00:00Z"),
        ("2026-11-02T10:00:00Z", "2026-11-02T09:00:00Z"),
        ("2026-11-02T09:00:00-05:00", "2026-11-02T10:00:00+00:00"),
    ],
)
def test_invalid_intervals_fail_both_implementations(start, end, tmp_path):
    given = IntervalInput(start, end)
    with pytest.raises(ValueError):
        normalize_interval(given, tmp_path)
    with pytest.raises(ValueError):
        interval(start, end)
    assert not verify_input("normalize_interval", given)["valid"]


def test_all_numeric_offset_minutes_against_integer_oracle(tmp_path):
    for minutes in range(-840, 841):
        zone = f"{'+' if minutes >= 0 else '-'}{abs(minutes) // 60:02}:{abs(minutes) % 60:02}"
        start, end = f"2000-03-01T00:00:00{zone}", f"2000-03-01T01:00:00{zone}"
        assert plain_output(normalize_interval(IntervalInput(start, end), tmp_path)) == interval(start, end)


def test_gregorian_month_boundaries_across_four_centuries(tmp_path):
    for year in range(1800, 2201):
        for month in [1, 2, 3, 6, 12]:
            start = f"{year:04}-{month:02}-01T00:00:00+05:30"
            end = f"{year:04}-{month:02}-02T00:00:00-03:30"
            assert plain_output(normalize_interval(IntervalInput(start, end), tmp_path)) == interval(start, end)

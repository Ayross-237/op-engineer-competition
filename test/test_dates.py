"""Tests for src.shared.dates.next_week.

next_week reads `date.today()`, so every test mocks that to a known weekday
to keep results stable across calendar drift.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from src.shared.dates import next_week


def _today_is(d: date):
    """Patch date.today() inside src.shared.dates to return d. Use as a context
    manager. Only date.today is mocked; date constructor + timedelta pass through."""
    patcher = patch("src.shared.dates.date")
    mocked = patcher.start()
    mocked.today.return_value = d
    # Keep date(year, month, day) constructor calls inside the module working
    # if they ever get added later.
    mocked.side_effect = lambda *a, **kw: date(*a, **kw)
    return patcher


def test_returns_seven_dates():
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 5, 25)  # Monday
        result = next_week()
    assert len(result) == 7


def test_returns_strings():
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 5, 25)
        result = next_week()
    for r in result:
        assert isinstance(r, str)


def test_iso_format_yyyy_mm_dd():
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 5, 25)
        result = next_week()
    for r in result:
        # Should parse back as a date — confirms format.
        date.fromisoformat(r)


def test_first_day_is_monday():
    """The first date returned must always be a Monday."""
    # Test from each weekday to cover the wrap-around.
    base = date(2026, 5, 25)  # Monday
    for delta in range(7):
        d = base + timedelta(days=delta)
        with patch("src.shared.dates.date") as mocked:
            mocked.today.return_value = d
            result = next_week()
        first_day = date.fromisoformat(result[0])
        assert first_day.weekday() == 0, f"Called on weekday {d.weekday()}, expected Monday first, got {first_day} (weekday {first_day.weekday()})"


def test_last_day_is_sunday():
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 5, 25)
        result = next_week()
    last_day = date.fromisoformat(result[-1])
    assert last_day.weekday() == 6  # Sunday


def test_dates_are_consecutive():
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 5, 27)  # Wednesday
        result = next_week()
    parsed = [date.fromisoformat(r) for r in result]
    for i in range(1, len(parsed)):
        assert (parsed[i] - parsed[i - 1]).days == 1


def test_called_on_monday_returns_following_week_not_today():
    """The docstring says 'strictly after today' — Monday → next Monday, not today."""
    today = date(2026, 5, 25)  # Monday
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = today
        result = next_week()
    first_day = date.fromisoformat(result[0])
    assert first_day == today + timedelta(days=7)


def test_called_on_sunday_returns_next_day():
    """Sunday → the immediately following Monday."""
    today = date(2026, 5, 31)  # Sunday
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = today
        result = next_week()
    first_day = date.fromisoformat(result[0])
    assert first_day == today + timedelta(days=1)


def test_called_on_friday_returns_following_monday():
    today = date(2026, 5, 29)  # Friday
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = today
        result = next_week()
    first_day = date.fromisoformat(result[0])
    assert first_day == today + timedelta(days=3)  # Fri+3 = Mon


@pytest.mark.parametrize(
    "today,expected_first",
    [
        (date(2026, 5, 25), date(2026, 6, 1)),   # Monday -> next Monday
        (date(2026, 5, 26), date(2026, 6, 1)),   # Tuesday -> next Monday
        (date(2026, 5, 27), date(2026, 6, 1)),   # Wednesday -> next Monday
        (date(2026, 5, 28), date(2026, 6, 1)),   # Thursday -> next Monday
        (date(2026, 5, 29), date(2026, 6, 1)),   # Friday -> next Monday
        (date(2026, 5, 30), date(2026, 6, 1)),   # Saturday -> next Monday
        (date(2026, 5, 31), date(2026, 6, 1)),   # Sunday -> next Monday
    ],
)
def test_every_weekday_resolves_to_correct_next_monday(today, expected_first):
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = today
        result = next_week()
    assert date.fromisoformat(result[0]) == expected_first


def test_handles_month_boundary():
    """May 31 (Sunday) → June 1-7."""
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 5, 31)
        result = next_week()
    assert result[0] == "2026-06-01"
    assert result[-1] == "2026-06-07"


def test_handles_year_boundary():
    """Dec 28, 2026 is a Monday → Jan 4-10, 2027."""
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2026, 12, 28)
        result = next_week()
    assert result[0] == "2027-01-04"
    assert result[-1] == "2027-01-10"


def test_handles_leap_year_february():
    """Feb 24, 2028 is a Thursday → Feb 28 - Mar 5, 2028 (2028 is a leap year so Feb has 29)."""
    with patch("src.shared.dates.date") as mocked:
        mocked.today.return_value = date(2028, 2, 24)
        result = next_week()
    assert result[0] == "2028-02-28"
    assert "2028-02-29" in result  # leap day must be in the week
    assert result[-1] == "2028-03-05"

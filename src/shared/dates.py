from datetime import date, datetime, timedelta


def delivery_window(dinner_time: str, lead_min: int = 10, lead_max: int = 5) -> str:
    """Render the requested delivery window so the order arrives shortly before dinner.

    `dinner_time` is a 'HH:MM' or 'HH:MM:SS' string (as stored in programs.dinner_time).
    Returns 'H:MM AM/PM – H:MM AM/PM', from `lead_min` minutes before dinner up to
    `lead_max` minutes before (default: arrive 10–5 min early). Defaults assume
    lead_min >= lead_max so the window reads earliest-to-latest.
    """
    parsed = datetime.strptime(dinner_time[:5], "%H:%M")
    start = parsed - timedelta(minutes=lead_min)
    end = parsed - timedelta(minutes=lead_max)

    def fmt(t: datetime) -> str:
        # Strip the leading zero from the hour (e.g. '05:20 PM' -> '5:20 PM') without
        # relying on the platform-specific %-I / %#I strftime flag.
        return t.strftime("%I:%M %p").lstrip("0")

    return f"{fmt(start)} – {fmt(end)}"


def next_week(today=None) -> list[str]:
    """
    Returns the seven dates of the next calendar week, Monday through Sunday inclusive.
    "Next week" is the week starting on the first Monday strictly after today.
    """
    if today is None:
        today = date.today()
    days_until_next_monday = 7 - today.weekday()
    monday = today + timedelta(days=days_until_next_monday)
    return [str(monday + timedelta(days=i)) for i in range(7)]  

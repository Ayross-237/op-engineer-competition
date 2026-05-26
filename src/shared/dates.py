from datetime import date, timedelta


def next_week() -> list[str]:
    """
    Returns the seven dates of the next calendar week, Monday through Sunday inclusive.
    "Next week" is the week starting on the first Monday strictly after today.
    """
    today = date.today()
    days_until_next_monday = 7 - today.weekday()
    monday = today + timedelta(days=days_until_next_monday)
    return [str(monday + timedelta(days=i)) for i in range(7)]  

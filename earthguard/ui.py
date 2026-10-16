"""Text helpers: turn week numbers into words people understand."""

import calendar
from datetime import date, timedelta

MONTH_NAMES = list(calendar.month_abbr)[1:]


def week_label(week: int) -> str:
    """Week 31 -> 'early Aug' (week 1 = Jan 1-7)."""
    middle = date(2001, 1, 1) + timedelta(days=(week - 1) * 7 + 3)
    part = "early" if middle.day <= 10 else "mid" if middle.day <= 20 else "late"
    return f"{part} {MONTH_NAMES[middle.month - 1]}"


def season_months(period: tuple[int, int]) -> str:
    """(31, 43) -> 'Aug – Oct'."""
    first, last = (week_label(week).split()[1] for week in period)
    return first if first == last else f"{first} – {last}"


def current_week() -> int:
    return min((date.today().timetuple().tm_yday - 1) // 7 + 1, 52)


def current_month() -> int:
    return date.today().month

"""Burning calendar: patterns, "unusual" months/weeks and critical periods.

Named burn_calendar (not calendar) so it does not hide Python's built-in `calendar` module.

All functions take a "matrix": rows = years, columns = months (1..12) or weeks (1..52),
values = harmonized burning activity. Each definition fits in one sentence:

    typical         the median of the same month/week over all years
    x typical       value / typical
    unusual         top 10% of years for that month/week, at least 2x typical, and big enough
                    to see (at least 10% of the worst month/week ever recorded there)
    fire season     consecutive weeks around the peak where the typical week (smoothed over
                    5 weeks) is >= 50% of the peak week (the code calls it "critical period")
"""

import pandas as pd

from earthguard.config import (CRITICAL_SHARE_OF_PEAK, CRITICAL_SMOOTHING_WEEKS,
                               MIN_UNUSUAL_COUNT, UNUSUAL_MIN_SHARE, UNUSUAL_MIN_TIMES,
                               UNUSUAL_PERCENTILE, WEEKS_PER_YEAR)


def to_matrix(series: pd.Series, period: str) -> pd.DataFrame:
    """Harmonized series -> matrix. period is "month" (date index) or "week" ((year, week) index)."""
    if period == "month":
        frame = pd.DataFrame({"v": series.to_numpy(), "year": series.index.year,
                              "month": series.index.month})
        return frame.pivot(index="year", columns="month", values="v")
    return series.unstack("week")


def typical(matrix: pd.DataFrame) -> pd.Series:
    return matrix.median()


def times_typical(matrix: pd.DataFrame) -> pd.DataFrame:
    # Never divide by less than 1, so a month that is "usually 0" does not explode to infinity.
    return matrix / typical(matrix).clip(lower=1)


def unusual(matrix: pd.DataFrame) -> pd.DataFrame:
    """True where a cell is far above normal for that month/week (see config for the 3 rules)."""
    top_years = matrix > matrix.quantile(UNUSUAL_PERCENTILE)
    doubled = times_typical(matrix) >= UNUSUAL_MIN_TIMES
    big_enough = matrix >= max(MIN_UNUSUAL_COUNT, UNUSUAL_MIN_SHARE * matrix.max().max())
    return top_years & doubled & big_enough


def smoothed_typical(weekly_matrix: pd.DataFrame) -> pd.Series:
    """Typical week, averaged with its neighbours so one odd week does not decide the result.

    The window wraps around New Year: week 1's neighbours include weeks 51 and 52.
    """
    profile = typical(weekly_matrix).reindex(range(1, WEEKS_PER_YEAR + 1), fill_value=0)
    half = CRITICAL_SMOOTHING_WEEKS // 2
    padded = pd.concat([profile.iloc[-half:], profile, profile.iloc[:half]])
    smooth = padded.rolling(CRITICAL_SMOOTHING_WEEKS, center=True).mean()
    return pd.Series(smooth.iloc[half:-half].to_numpy(), index=profile.index)


def critical_period(weekly_matrix: pd.DataFrame) -> tuple[int, int] | None:
    """(first week, last week) of the typical critical period, or None if there is no fire.

    Start at the peak of the smoothed typical year and grow left and right while activity
    stays >= 50% of the peak. The calendar wraps around (week 52 is next to week 1), because
    in some places the fire season crosses New Year.
    """
    profile = smoothed_typical(weekly_matrix)
    peak_week = int(profile.idxmax())
    if profile[peak_week] <= 0:
        return None
    threshold = CRITICAL_SHARE_OF_PEAK * profile[peak_week]

    def step(week: int, direction: int) -> int:
        return (week - 1 + direction) % WEEKS_PER_YEAR + 1

    start = end = peak_week
    for _ in range(WEEKS_PER_YEAR - 1):
        if profile[step(start, -1)] >= threshold and step(start, -1) != end:
            start = step(start, -1)
        else:
            break
    for _ in range(WEEKS_PER_YEAR - 1):
        if profile[step(end, +1)] >= threshold and step(end, +1) != start:
            end = step(end, +1)
        else:
            break
    return start, end


def weeks_in(period: tuple[int, int]) -> list[int]:
    start, end = period
    if start <= end:
        return list(range(start, end + 1))
    return list(range(start, WEEKS_PER_YEAR + 1)) + list(range(1, end + 1))


def unusual_events(monthly_matrix: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """The most extreme unusual months, biggest first."""
    flags = unusual(monthly_matrix).stack()
    ratio = times_typical(monthly_matrix).stack()
    value = monthly_matrix.stack()
    events = pd.DataFrame({"value": value, "times_typical": ratio})[flags.reindex(value.index,
                                                                                  fill_value=False)]
    return events.sort_values("times_typical", ascending=False).head(limit)


def worst_year(monthly_matrix: pd.DataFrame) -> tuple[int, float]:
    """The year with the most burning, and how many times a normal year that was."""
    yearly = monthly_matrix.sum(axis=1)
    year = int(yearly.idxmax())
    return year, yearly[year] / max(yearly.median(), 1)


def weeks_until(week_now: int, target_week: int) -> int:
    """How many weeks from week_now until target_week (wrapping into next year)."""
    return (target_week - week_now) % WEEKS_PER_YEAR

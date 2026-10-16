import numpy as np
import pandas as pd

from earthguard.burn_calendar import (critical_period, times_typical, unusual, unusual_events,
                                      weeks_in, weeks_until, worst_year)

YEARS = range(2001, 2026)
WEEKS = range(1, 53)


def weekly(profile) -> pd.DataFrame:
    """Every year has the same weekly profile."""
    return pd.DataFrame([list(profile)] * len(YEARS), index=YEARS, columns=WEEKS, dtype=float)


def test_critical_period_around_a_summer_peak():
    profile = [0] * 52
    for week, value in {30: 40, 31: 60, 32: 100, 33: 80, 34: 50, 35: 30}.items():
        profile[week - 1] = value
    # 5-week averages: w29=20 w30=40 w31=56 w32=66 w33=64 w34=52 w35=32 -> peak 66, keep >= 33
    assert critical_period(weekly(profile)) == (30, 34)


def test_critical_period_can_cross_new_year():
    profile = [0] * 52
    for week in (51, 52, 1, 2):
        profile[week - 1] = 100
    # 5-week averages: w49=20 w50=40 w51=60 w52=80 w1=80 w2=60 w3=40 w4=20 -> keep >= 40
    period = critical_period(weekly(profile))
    assert period == (50, 3)
    assert weeks_in(period) == [50, 51, 52, 1, 2, 3]


def test_no_fire_means_no_critical_period():
    assert critical_period(weekly([0] * 52)) is None


def test_one_extreme_month_is_unusual():
    monthly = pd.DataFrame(100.0, index=YEARS, columns=range(1, 13))
    monthly.loc[2015, 9] = 500
    flags = unusual(monthly)
    assert flags.loc[2015, 9]
    assert flags.to_numpy().sum() == 1
    assert times_typical(monthly).loc[2015, 9] == 5
    events = unusual_events(monthly)
    assert list(events.index) == [(2015, 9)]


def test_top_year_but_less_than_double_is_not_unusual():
    monthly = pd.DataFrame(100.0, index=YEARS, columns=range(1, 13))
    monthly.loc[2015, 9] = 150      # the highest September, but only 1.5x typical
    assert not unusual(monthly).to_numpy().any()


def test_tiny_numbers_are_never_unusual():
    monthly = pd.DataFrame(1.0, index=YEARS, columns=range(1, 13))
    monthly.loc[2015, 9] = 3        # 3x typical, but only 3 cell-days
    assert not unusual(monthly).to_numpy().any()


def test_worst_year():
    monthly = pd.DataFrame(100.0, index=YEARS, columns=range(1, 13))
    monthly.loc[2015] = 300
    year, times = worst_year(monthly)
    assert year == 2015 and times == 3


def test_weeks_until_wraps_into_next_year():
    assert weeks_until(50, 3) == 5
    assert weeks_until(10, 31) == 21
    assert np.isclose(weeks_until(31, 31), 0)

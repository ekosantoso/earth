"""Tests with made-up data where we KNOW the right answer.

If VIIRS always sees exactly 4x what MODIS sees, harmonization must find a ratio of 4,
and the harmonized record must have no jump in 2012.
"""

import numpy as np
import pandas as pd
import pytest

from earthguard.config import MODIS, VIIRS
from earthguard.harmonize import (fit_ratios, harmonize, harmonize_weekly, monthly_table,
                                  validate, weekly_table)


def make_rows(viirs_factor: float = 4.0, modis_per_month: int = 100) -> pd.DataFrame:
    rows = []
    for year in range(2001, 2026):
        for month in range(1, 13):
            seasonal = modis_per_month * (3 if month in (8, 9, 10) else 1)
            rows.append((year, month, MODIS, seasonal))
            if year >= 2012:
                rows.append((year, month, VIIRS, seasonal * viirs_factor))
    return pd.DataFrame(rows, columns=["year", "month", "sensor", "cell_days"])


def test_monthly_table_marks_viirs_unknown_before_it_started():
    table = monthly_table(make_rows())
    assert np.isnan(table.loc["2011-12-01", VIIRS])
    assert np.isnan(table.loc["2012-01-01", VIIRS])   # VIIRS started on 20 Jan 2012
    assert table.loc["2012-02-01", VIIRS] == 400


def test_incomplete_january_2012_uses_modis():
    table = monthly_table(make_rows())
    harmonized = harmonize(table, fit_ratios(table)["ratio"])
    assert harmonized["2012-01-01"] == 100


def test_ratio_is_learned_exactly():
    ratios = fit_ratios(monthly_table(make_rows(viirs_factor=4.0)))
    assert np.allclose(ratios["ratio"], 4.0)
    assert (ratios["basis"] == "this month").all()


def test_harmonized_series_has_no_jump_in_2012():
    table = monthly_table(make_rows())
    harmonized = harmonize(table, fit_ratios(table)["ratio"])
    assert harmonized["2011-12-01"] == pytest.approx(harmonized["2012-12-01"])
    assert harmonized["2015-09-01"] == pytest.approx(300)


def test_sparse_months_fall_back_to_all_months_then_parent():
    rows = make_rows(modis_per_month=1)          # 14 overlap years x 1-3 = too few per month
    table = monthly_table(rows)
    own = fit_ratios(table)
    assert (own["basis"] == "all months").all()  # 14 years x 12 months x ... >= 50 in total

    empty = monthly_table(rows.iloc[0:0])
    parent = pd.Series(5.0, index=range(1, 13))
    borrowed = fit_ratios(empty, parent)
    assert (borrowed["basis"] == "parent region").all()
    assert np.allclose(borrowed["ratio"], 5.0)


def test_validation_is_perfect_on_perfect_data():
    result = validate(monthly_table(make_rows()))
    assert result["months"] == 14 * 12 - 1   # all overlap months except Jan 2012
    assert result["r2"] == pytest.approx(1.0)
    assert result["median_error"] == pytest.approx(0.0)


def test_weekly_harmonization_uses_monthly_ratios():
    rows = []
    for year in range(2001, 2026):
        for week in range(1, 53):
            rows.append((year, week, MODIS, 10))
            if year >= 2012:
                rows.append((year, week, VIIRS, 30))
    weekly = weekly_table(pd.DataFrame(rows, columns=["year", "week", "sensor", "cell_days"]))
    harmonized = harmonize_weekly(weekly, pd.Series(3.0, index=range(1, 13)))
    assert np.allclose(harmonized.to_numpy(), 10)

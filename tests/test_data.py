import pandas as pd
import pandera.pandas as pa
import pytest

from mobile_price.data import EXPORT, ROWS


@pytest.fixture
def sample():
    row = {
        "battery_power": 1043,
        "blue": 1,
        "clock_speed": 1.8,
        "dual_sim": 1,
        "fc": 14,
        "four_g": 0,
        "int_memory": 5,
        "m_dep": 0.1,
        "mobile_wt": 193,
        "n_cores": 3,
        "pc": 16,
        "px_height": 226,
        "px_width": 1412,
        "ram": 3476,
        "sc_h": 12,
        "sc_w": 7,
        "talk_time": 2,
        "three_g": 0,
        "touch_screen": 1,
        "wifi": 0,
    }
    return pd.DataFrame([{**row, "price_range": price} for price in range(4)])


def test_valid_rows(sample):
    result = ROWS.validate(sample, lazy=True)
    assert len(result) == 4


def test_invalid_value_is_rejected(sample):
    sample.loc[0, "ram"] = -1

    with pytest.raises(pa.errors.SchemaErrors) as error:
        ROWS.validate(sample, lazy=True)

    assert "ram" in error.value.failure_cases["column"].values


def test_small_export_is_rejected(sample):
    with pytest.raises(pa.errors.SchemaErrors) as error:
        EXPORT.validate(sample, lazy=True)

    assert "меньше 1000 строк" in error.value.failure_cases.to_string()

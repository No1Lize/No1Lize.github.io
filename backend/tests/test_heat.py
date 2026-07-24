import pytest
from tools.recalculate_heat import HeatInputs, heat_score


def test_heat_formula() -> None:
    score = heat_score(HeatInputs(100, 80, 60, 40, 20))
    assert score == 67.0


def test_heat_formula_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        heat_score(HeatInputs(101, 80, 60, 40, 20))

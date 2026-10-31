import math

from avaliar_skill_score import calcular_skill_score


def test_skill_score_uses_ratio_of_summed_absolute_errors():
    result = calcular_skill_score(
        [
            ("1h", 1, 0.5),
            ("1h", -2, -1),
        ]
    )

    horizon, n, mae_model, mae_persist, score, small = result[0]
    assert horizon == "1h"
    assert n == 2
    assert mae_model == 0.75
    assert mae_persist == 1.5
    assert score == 0.5
    assert small is True


def test_skill_score_is_negative_infinity_when_persistence_error_is_zero():
    result = calcular_skill_score([("3h", 0, 0.5)])

    assert math.isinf(result[0][4])
    assert result[0][4] < 0


def test_skill_score_clears_small_sample_warning_at_threshold():
    rows = [("1h", 1, 1)] * 30

    result = calcular_skill_score(rows)

    assert result[0][1] == 30
    assert result[0][5] is False

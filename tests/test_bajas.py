"""Tests del ajuste por bajas (Task 4.2)."""

import pandas as pd

from predictor.bajas import CAP_MIN, factor_bajas, share_disponible


def _minutos():
    return pd.DataFrame({
        "jugador": ["A", "B", "C"], "equipo": ["X"] * 3, "minutos": [900, 800, 700],
    })


def test_share_equipo_completo():
    valor = {"A": 50e6, "B": 30e6, "C": 20e6}
    conv = {"X": {"A", "B", "C"}}
    assert share_disponible("X", _minutos(), valor, conv) == 1.0


def test_share_baja_estrella():
    valor = {"A": 50e6, "B": 30e6, "C": 20e6}
    conv = {"X": {"B", "C"}}  # falta A (50% del valor)
    s = share_disponible("X", _minutos(), valor, conv)
    assert abs(s - 0.5) < 1e-9


def test_factor_solo_penaliza_y_capa():
    valor = {"A": 50e6, "B": 30e6, "C": 20e6}
    # equipo completo → factor 1.0
    assert factor_bajas("X", _minutos(), valor, {"X": {"A", "B", "C"}}) == 1.0
    # media plantilla fuera → factor capado a CAP_MIN (no baja más)
    f = factor_bajas("X", _minutos(), valor, {"X": {"C"}})
    assert f == CAP_MIN


def test_jugador_sin_valor_no_rompe():
    valor = {"A": 50e6}  # B y C sin valor → fuera del cálculo
    s = share_disponible("X", _minutos(), valor, {"X": {"A"}})
    assert s == 1.0

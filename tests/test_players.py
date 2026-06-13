"""Tests de los mercados de jugador (bloque 7 portado + minutos esperados, Task 6.1)."""

import numpy as np
import pandas as pd

from predictor.players import (
    P_MAX_JUGADOR, construir_pool_jugador, minutos_esperados_por_jugador,
    seleccion_de_jugador, simular_jugador,
)


class _KNNVacio:
    def pesos(self, equipo):
        return {}


def _tel():
    return pd.DataFrame({
        "partido_id": [f"p{i}" for i in range(7)],
        "jugador": ["Titular"] * 5 + ["Suplente"] * 2,
        "home_team": ["X", "X", "Y", "X", "Z", "X", "X"],
        "away_team": ["Y", "Z", "X", "W", "X", "Y", "Z"],
        "minutesPlayed": [90, 80, 75, 85, 88, 12, 10],
        "goals": [1, 0, 1, 0, 1, 1, 0],
        "goalAssist": [0, 1, 0, 0, 1, 0, 0],
        "totalShots": [3, 2, 4, 1, 2, 1, 1],
        "onTargetScoringAttempt": [1, 1, 2, 0, 1, 1, 1],
        "totalPass": [40, 35, 50, 20, 45, 5, 6],
        "totalTackle": [1, 0, 2, 1, 0, 0, 0],
        "fouls": [1, 0, 1, 2, 0, 0, 0],
        "wasFouled": [2, 1, 0, 1, 1, 0, 0],
        "saves": [0] * 7,
    })


def _stats_x_partidos(n=10):
    # n partidos de la selección X (para el denominador de minutos esperados).
    return pd.DataFrame({"equipo_nombre": ["X"] * n,
                         "partido_id": [f"p{i}" for i in range(n)]})


def test_seleccion_filtra_por_convocatoria():
    sel = seleccion_de_jugador(_tel(), ["X"], {"X": {"Titular"}})  # Suplente no convocado
    assert sel == {"Titular": "X"}


def test_minutos_esperados_distingue_titular_de_suplente():
    tel = _tel()
    sel = {"Titular": "X", "Suplente": "X"}
    me = minutos_esperados_por_jugador(tel, sel, _stats_x_partidos(10))
    # Titular: (90+80+75+85+88)/10 = 41.8 ; Suplente: (12+10)/10 = 2.2
    assert me["Titular"] > 30
    assert me["Suplente"] < 5


def test_suplente_prob_baja_no_inflada():
    """Un suplente (minutos esperados bajos) tiene P(anotar) baja aunque marcara
    en su único partido — no se infla a 80'."""
    tel = _tel()
    me = minutos_esperados_por_jugador(tel, {"Suplente": "X"}, _stats_x_partidos(10))
    pool = construir_pool_jugador("Suplente", "X", "Y", tel, _KNNVacio())
    sim = simular_jugador(pool, np.random.default_rng(0), me["Suplente"], n_sim=3000)
    assert sim is not None
    assert (sim["goals"] >= 1).mean() < 0.20  # baja: apenas juega


def test_titular_prob_realista_y_capada():
    tel = _tel()
    me = minutos_esperados_por_jugador(tel, {"Titular": "X"}, _stats_x_partidos(5))
    pool = construir_pool_jugador("Titular", "X", "Y", tel, _KNNVacio())
    sim = simular_jugador(pool, np.random.default_rng(0), me["Titular"], n_sim=3000)
    assert sim is not None
    assert 0.0 < (sim["goals"] >= 1).mean() <= P_MAX_JUGADOR

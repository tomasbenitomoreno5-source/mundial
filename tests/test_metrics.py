"""Tests de las métricas de evaluación (backtest)."""

import numpy as np

from predictor.metrics import brier_1x2, logloss_1x2


def test_brier_perfecto():
    # Predicción perfecta al resultado real → Brier 0.
    assert brier_1x2([(1.0, 0.0, 0.0)], ["1"]) == 0.0


def test_brier_uniforme():
    # (1/3,1/3,1/3) con resultado X: (1/3)²+(1/3-1)²+(1/3)² = 2·(1/3)²+(2/3)².
    b = brier_1x2([(1 / 3, 1 / 3, 1 / 3)], ["X"])
    assert abs(b - (2 * (1 / 3) ** 2 + (2 / 3) ** 2)) < 1e-9


def test_brier_promedia_sobre_partidos():
    b = brier_1x2([(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)], ["1", "2"])
    assert b == 0.0


def test_logloss_perfecto():
    assert logloss_1x2([(1.0, 0.0, 0.0)], ["1"]) < 1e-9


def test_logloss_clip_no_es_infinito():
    # Probabilidad 0 al resultado real no debe dar inf (se clipa).
    ll = logloss_1x2([(0.0, 0.5, 0.5)], ["1"])
    assert np.isfinite(ll)


def test_logloss_penaliza_confianza_equivocada():
    seguro_mal = logloss_1x2([(0.9, 0.05, 0.05)], ["2"])
    dudoso = logloss_1x2([(0.34, 0.33, 0.33)], ["2"])
    assert seguro_mal > dudoso

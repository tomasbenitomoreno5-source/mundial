"""Tests de estilo/KNN (bloque 4) y fuerza/ELO (bloque 4b).

Incluye regresión contra los artefactos deterministas del R: debug_knn.csv
(identidad de vecinos) y el sanity check de fuerza (top-tier arriba).
"""

import numpy as np
import pandas as pd
import pytest

from predictor import config
from predictor.strength import compute_strength
from predictor.style import compute_style_knn


@pytest.fixture(scope="module")
def knn(dataset):
    return compute_style_knn(dataset.stats)


@pytest.fixture(scope="module")
def fuerza(dataset):
    return compute_strength(dataset.stats, dataset.equipos_mundial)


def test_pesos_knn_suman_uno(knn):
    for eq, df in knn.vecinos.items():
        assert len(df) == 8
        assert abs(df["peso"].sum() - 1.0) < 1e-9, eq
        # Pesos decrecientes con la distancia (exp(-dist) normalizado)
        assert df["peso"].is_monotonic_decreasing


def test_equipo_no_es_su_propio_vecino(knn):
    for eq, df in knn.vecinos.items():
        assert eq not in set(df["vecino"]), eq


def test_regresion_vecinos_vs_R(knn):
    """La identidad de vecinos debe coincidir con debug_knn.csv del R."""
    ref = pd.read_csv(config.DATA_DIR / "debug_knn.csv", sep=";", decimal=",", encoding="utf-8-sig")
    ref_sets = ref.groupby("equipo")["vecino"].apply(set).to_dict()
    overlaps = []
    for eq, rset in ref_sets.items():
        pset = set(knn.vecinos[eq]["vecino"])
        overlaps.append(len(rset & pset))
    overlaps = np.array(overlaps)
    # Determinista: esperamos identidad casi perfecta (8/8).
    assert overlaps.mean() >= 7.5, f"overlap medio bajo: {overlaps.mean()}"
    assert overlaps.min() >= 6


def test_fuerza_top_son_grandes_selecciones(dataset, fuerza):
    top = sorted(
        ((e, fuerza[e]) for e in dataset.equipos_mundial), key=lambda x: -x[1]
    )[:6]
    top_names = {e for e, _ in top}
    # Las grandes deben estar arriba (sanity check del R)
    assert "Spain" in top_names
    assert "Argentina" in top_names
    assert "France" in top_names


def test_fuerza_cubre_todos_los_equipos(dataset, fuerza):
    for eq in dataset.equipos_mundial:
        assert eq in fuerza
        assert np.isfinite(fuerza[eq])

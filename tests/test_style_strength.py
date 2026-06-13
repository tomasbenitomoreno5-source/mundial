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


@pytest.fixture(scope="module")
def knn_legacy(dataset_legacy):
    """KNN sobre el dataset original, para comparar con debug_knn.csv del R.
    min_partidos=1 = sin filtro (el R no lo tenía)."""
    return compute_style_knn(dataset_legacy.stats, min_partidos=1)


def test_pesos_knn_suman_uno(knn):
    for eq, df in knn.vecinos.items():
        assert len(df) == 8
        assert abs(df["peso"].sum() - 1.0) < 1e-9, eq
        # Pesos decrecientes con la distancia (exp(-dist) normalizado)
        assert df["peso"].is_monotonic_decreasing


def test_equipo_no_es_su_propio_vecino(knn):
    for eq, df in knn.vecinos.items():
        assert eq not in set(df["vecino"]), eq


def test_regresion_vecinos_vs_R(knn_legacy):
    """La identidad de vecinos (sobre el dataset original) coincide con el R."""
    ref = pd.read_csv(config.DATA_DIR / "debug_knn.csv", sep=";", decimal=",", encoding="utf-8-sig")
    ref_sets = ref.groupby("equipo")["vecino"].apply(set).to_dict()
    overlaps = []
    for eq, rset in ref_sets.items():
        pset = set(knn_legacy.vecinos[eq]["vecino"])
        overlaps.append(len(rset & pset))
    overlaps = np.array(overlaps)
    # Determinista: esperamos identidad casi perfecta (8/8).
    assert overlaps.mean() >= 7.5, f"overlap medio bajo: {overlaps.mean()}"
    assert overlaps.min() >= 6


def test_knn_sin_vecinos_de_muestra_minima(dataset, knn):
    """Ningún vecino tiene menos de KNN_MIN_PARTIDOS partidos (3.3)."""
    from predictor import config

    n = dataset.stats.groupby("equipo_nombre").size()
    for eq, df in knn.vecinos.items():
        for v in df["vecino"]:
            assert n.get(v, 0) >= config.KNN_MIN_PARTIDOS, f"{eq}→{v} (n={n.get(v,0)})"


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


def test_no_mundialistas_usan_elo_mundo(dataset):
    """Con ELO_MUNDO (Task 2.4), un no-mundialista fuerte queda por encima de
    uno débil — antes ambos dependían solo de z_interna (circular)."""
    from predictor import config

    if "Italy" not in config.ELO_MUNDO or "Eswatini" not in config.ELO_MUNDO:
        import pytest

        pytest.skip("elo_mundo.csv no disponible")
    # fuerza sobre todos los equipos del dataset (no solo mundialistas)
    todos = sorted(set(dataset.stats["equipo_nombre"]))
    f = compute_strength(dataset.stats, todos)
    assert f["Italy"] > f["Eswatini"]

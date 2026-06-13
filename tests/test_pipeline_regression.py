"""Regresión del pipeline completo contra el golden output del R.

El motor es Monte Carlo y el RNG de Python != el de R, así que comparamos
probabilidades dentro de tolerancia (no al decimal). Con 20.000 simulaciones
la desviación esperada por muestreo es ~±0.02.
"""

import numpy as np
import pandas as pd
import pytest

from predictor import config
from predictor.markets import fit_distr, generar_lineas, prob_over
from predictor.pipeline import build_resumen, predict_all

TOL_MAE = 0.02
TOL_MAX = 0.05
KEY_COLS = ["p_1", "p_X", "p_2", "btts_si", "goles_over_2_5", "corners_over_9_5"]


GOLDEN_PY = config.DATA_DIR / "golden_py" / "predicciones_resumen_golden.csv"


@pytest.fixture(scope="module")
def largo(dataset):
    return predict_all(dataset=dataset)


@pytest.fixture(scope="module")
def resumen(largo):
    return build_resumen(largo)


@pytest.fixture(scope="module")
def resumen_legacy(dataset_legacy):
    """Resumen sobre el dataset original (sin saneamiento), para comparar con
    el golden del R."""
    return build_resumen(predict_all(dataset=dataset_legacy))


def test_cobertura_72_partidos(largo):
    assert largo["partido_id"].nunique() == 72


def test_probabilidades_en_rango(largo):
    assert largo["probabilidad"].between(0, 1).all()


def test_1x2_suma_uno(largo):
    # Cada periodo (FT, 1H) debe sumar 1 por separado.
    s = (largo[largo["mercado"] == "1X2"]
         .groupby(["partido_id", "periodo"])["probabilidad"].sum())
    assert ((s - 1).abs() < 0.01).all()


def test_btts_suma_uno(largo):
    s = (largo[largo["mercado"] == "btts"]
         .groupby(["partido_id", "periodo"])["probabilidad"].sum())
    assert ((s - 1).abs() < 0.01).all()


def test_mercados_mitad_presentes(largo):
    # Existen los tres periodos y over+under suman 1 en cada línea/periodo.
    assert {"FT", "1H", "2H"} <= set(largo["periodo"].unique())
    ou = largo[largo["evento_o_jugador"].isin(["over", "under"])]
    s = ou.groupby(
        ["partido_id", "mercado", "ambito", "linea_o_target", "periodo"]
    )["probabilidad"].sum()
    assert ((s - 1).abs() < 0.01).all()


# --- Fidelidad del port vs el golden del R (sobre el dataset ORIGINAL) ------
def test_regresion_vs_golden_R(resumen_legacy):
    """El port Python reproduce el R cuando se le da el MISMO dataset (legacy)."""
    R = pd.read_csv(config.DATA_DIR / "predicciones_resumen.csv", sep=";",
                    decimal=",", encoding="utf-8-sig")
    m = R.merge(resumen_legacy, on="partido_id", suffixes=("_R", "_P"))
    assert len(m) == 72
    for c in KEY_COLS:
        diff = (m[f"{c}_R"] - m[f"{c}_P"]).abs()
        assert diff.mean() < TOL_MAE, f"{c}: MAE {diff.mean():.4f} >= {TOL_MAE}"
        assert diff.max() < TOL_MAX, f"{c}: max {diff.max():.4f} >= {TOL_MAX}"


def test_correlacion_alta_vs_golden_R(resumen_legacy):
    R = pd.read_csv(config.DATA_DIR / "predicciones_resumen.csv", sep=";",
                    decimal=",", encoding="utf-8-sig")
    m = R.merge(resumen_legacy, on="partido_id", suffixes=("_R", "_P"))
    for c in ("p_1", "p_2"):
        assert m[f"{c}_R"].corr(m[f"{c}_P"]) > 0.98


# --- Regresión del motor sobre el dataset SANEADO (golden Python congelado) --
def test_regresion_vs_golden_py(resumen):
    """Detecta regresiones del motor sobre el dataset actual. Regenerar el
    golden (data/golden_py/) a propósito en cada cambio de modelo de Fase 2-3."""
    G = pd.read_csv(GOLDEN_PY, sep=";", decimal=",", encoding="utf-8-sig")
    m = G.merge(resumen, on="partido_id", suffixes=("_G", "_P"))
    assert len(m) == 72
    for c in KEY_COLS:
        if f"{c}_G" not in m.columns:
            continue
        diff = (m[f"{c}_G"] - m[f"{c}_P"]).abs()
        assert diff.mean() < TOL_MAE, f"{c}: MAE {diff.mean():.4f} >= {TOL_MAE}"


# --- Utilidades de mercados ---
def test_generar_lineas():
    lns = generar_lineas(2.5)
    assert all(abs(x - round(x) - 0.5) < 1e-9 or abs(x - int(x) - 0.5) < 1e-9
               for x in lns)
    assert all(x >= 0.5 for x in lns)


def test_fit_distr_nb_vs_pois():
    rng = np.random.default_rng(1)
    # Sobre-dispersión -> NB
    nb_sample = rng.negative_binomial(5, 0.3, 50000).astype(float)
    assert fit_distr(nb_sample)["tipo"] == "nb"
    # Poisson puro -> pois
    pois_sample = rng.poisson(3, 50000).astype(float)
    fit = fit_distr(pois_sample)
    assert fit["tipo"] in ("pois", "nb")  # var≈mean, puede caer en cualquiera
    # prob_over monótona decreciente en la línea
    f = fit_distr(rng.poisson(4, 50000).astype(float))
    assert prob_over(f, 1.5) > prob_over(f, 5.5)

"""Tests del pool (5.1), QoO (#2) y simulación MC + Dixon-Coles (5)."""

import numpy as np
import pytest

from predictor import config
from predictor.pool import ajustar_pool_por_calidad_rival, construir_pool
from predictor.simulate import (
    MatchSim,
    dixon_coles_matrix,
    elo_lambdas,
    sample_dc,
    simular_partido_bootstrap,
)
from predictor.strength import compute_strength
from predictor.style import compute_style_knn


@pytest.fixture(scope="module")
def modelo(dataset):
    knn = compute_style_knn(dataset.stats)
    fuerza = compute_strength(dataset.stats, dataset.equipos_mundial)
    return knn, fuerza


# --------------------- Dixon-Coles (determinista) --------------------------
def test_dc_matrix_normalizada():
    M = dixon_coles_matrix(1.4, 1.1)
    assert M.shape == (config.MAX_GOLES_DC + 1, config.MAX_GOLES_DC + 1)
    assert abs(M.sum() - 1.0) < 1e-12
    assert (M >= 0).all()


def test_dc_correccion_tau():
    """τ infla (0,0)/(1,1) y desinfla (0,1)/(1,0) respecto al producto Poisson."""
    from scipy.stats import poisson
    lam_a, lam_b, rho = 1.4, 1.1, config.RHO_DC
    M = dixon_coles_matrix(lam_a, lam_b, rho=rho)
    # Producto independiente (sin τ, sin renormalizar)
    base = np.outer(poisson.pmf(np.arange(7), lam_a), poisson.pmf(np.arange(7), lam_b))
    # rho<0 => (0,0) y (1,1) suben en proporción al producto
    assert M[0, 0] / base[0, 0] > M[0, 2] / base[0, 2]


def test_elo_lambdas():
    # Igualdad de ELO -> lambdas iguales que suman el total esperado
    la, lb = elo_lambdas(1800, 1800)
    assert abs(la - lb) < 1e-9
    assert abs((la + lb) - config.ELO_TOTAL_ESPERADO) < 1e-9
    # A más fuerte -> A marca más
    la2, lb2 = elo_lambdas(2100, 1500)
    assert la2 > lb2


def test_sample_dc_reproduce_marginales(modelo):
    rng = np.random.default_rng(0)
    M = dixon_coles_matrix(1.5, 1.0)
    gA, gB = sample_dc(M, 200_000, rng)
    # P(gA=0) empírico ~ suma de la fila 0 de M
    assert abs((gA == 0).mean() - M[0, :].sum()) < 0.01
    assert abs((gB == 0).mean() - M[:, 0].sum()) < 0.01


# --------------------- Pool ------------------------------------------------
def test_pool_pesos_suman_uno(dataset, modelo):
    knn, fuerza = modelo
    pool = construir_pool("Argentina", "Algeria", dataset.stats, knn, fuerza)
    assert pool is not None
    assert abs(pool["peso"].sum() - 1.0) < 1e-9
    assert (pool["peso"] > 0).all()


def test_pool_qoo_preserva_estructura(dataset, modelo):
    knn, fuerza = modelo
    pool = construir_pool("Argentina", "Algeria", dataset.stats, knn, fuerza)
    n0 = len(pool)
    ajustado = ajustar_pool_por_calidad_rival(pool, fuerza["Algeria"], fuerza)
    assert len(ajustado) == n0
    assert abs(ajustado["peso"].sum() - 1.0) < 1e-9
    # Las métricas QoO no pueden quedar negativas
    for m in config.METRICAS_QOO:
        if m in ajustado.columns:
            assert (ajustado[m] >= 0).all()


# --------------------- Simulación ------------------------------------------
def test_simular_partido(dataset, modelo):
    knn, fuerza = modelo
    rng = np.random.default_rng(config.SEED)
    global_means = {c: float(dataset.stats[c].mean()) for c in config.COLS_RARAS_SHRINK
                    if c in dataset.stats.columns}
    cols_shrink = [c for c in config.COLS_RARAS_SHRINK if c in dataset.metricas_equipo]
    pool_A = construir_pool("Argentina", "Algeria", dataset.stats, knn, fuerza)
    pool_B = construir_pool("Algeria", "Argentina", dataset.stats, knn, fuerza)
    sims = simular_partido_bootstrap(
        pool_A, pool_B, dataset.metricas_equipo, cols_shrink, global_means,
        "Argentina", "Algeria", rng,
    )
    assert isinstance(sims, MatchSim)
    assert sims.A.shape == (config.N_SIM, len(dataset.metricas_equipo))
    assert sims.B.shape == (config.N_SIM, len(dataset.metricas_equipo))
    # Argentina (más fuerte) debe marcar más en promedio
    assert sims.col(sims.A, "goles").mean() > sims.col(sims.B, "goles").mean()
    assert sims.lam_a_blend > sims.lam_b_blend

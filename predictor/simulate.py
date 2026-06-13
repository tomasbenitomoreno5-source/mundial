"""Simulación Monte Carlo: bootstrap multivariado + Dixon-Coles (bloque 5).

Notas de fidelidad respecto al R:
- El RNG de numpy != el de R, así que las probabilidades coinciden dentro de
  tolerancia (no al decimal). Las partes deterministas (matriz DC, lambdas ELO)
  sí son exactas.
- ``sample_dc`` respeta el orden column-major de R para que ``gA`` varíe primero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import config
from .strength import get_elo


# --------------------- Lambdas ELO para goles ------------------------------
def elo_lambdas(elo_a: float, elo_b: float,
                total_esperado: float = config.ELO_TOTAL_ESPERADO) -> tuple[float, float]:
    """λ_A, λ_B a partir de la diferencia ELO (Maher/De Boer, venue neutral)."""
    elo_diff = elo_a - elo_b
    goal_diff = elo_diff / 100 * config.ELO_GOLES_POR_100PTS
    half = total_esperado / 2
    lam_a = max(0.25, half + goal_diff / 2)
    lam_b = max(0.25, half - goal_diff / 2)
    return lam_a, lam_b


# --------------------- Dixon-Coles -----------------------------------------
def dixon_coles_matrix(lam_a: float, lam_b: float,
                       rho: float = config.RHO_DC,
                       max_g: int = config.MAX_GOLES_DC) -> np.ndarray:
    """Matriz (max_g+1)² de P(gA=i, gB=j) con la corrección τ de Dixon-Coles."""
    lam_a = max(lam_a, 1e-6)
    lam_b = max(lam_b, 1e-6)
    ii = np.arange(max_g + 1)
    pa = poisson.pmf(ii, lam_a)
    pb = poisson.pmf(ii, lam_b)
    M = np.outer(pa, pb)  # M[i, j] = P(gA=i, gB=j)
    M[0, 0] *= (1 - lam_a * lam_b * rho)
    M[0, 1] *= (1 + lam_a * rho)
    M[1, 0] *= (1 + lam_b * rho)
    M[1, 1] *= (1 - rho)
    return M / M.sum()


def sample_dc(M: np.ndarray, n_sim: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Muestrea n_sim pares (gA, gB) proporcional a las celdas de M."""
    k = M.shape[0]
    flat = M.ravel(order="F")  # column-major como R: gA varía primero
    idx = rng.choice(len(flat), size=n_sim, replace=True, p=flat)
    gA = (idx % k).astype(int)
    gB = (idx // k).astype(int)
    return gA, gB


# --------------------- Tasas con shrinkage (eventos raros) -----------------
def tasa_shrunk(pool: pd.DataFrame, col: str, global_means: dict[str, float],
                masa_prior: float = 0.5) -> float:
    """Tasa ponderada del pool encogida hacia la media global del dataset."""
    v = pd.to_numeric(pool[col], errors="coerce").to_numpy(dtype=float)
    w = pool["peso"].to_numpy(dtype=float)
    ok = ~np.isnan(v)
    v, w = v[ok], w[ok]
    if len(v) == 0:
        return global_means[col]
    pool_mean = np.sum(v * w) / np.sum(w)
    prior_mean = global_means[col]
    # Masa del prior proporcional a la (falta de) evidencia: pools con pocas
    # filas efectivas (n_eff = 1/Σŵ²) se encogen más hacia la media global.
    # Con n_eff≈80 (pool típico) masa≈0.25 (≈ comportamiento previo); con
    # n_eff≈10 sube a 2.0 (encoge fuerte). Reemplaza la masa fija de 0.5.
    w_norm = w / w.sum()
    n_eff = 1.0 / np.sum(w_norm ** 2)
    masa = float(np.clip(masa_prior * 40.0 / n_eff, 0.1, 2.0))
    return (pool_mean * 1 + prior_mean * masa) / (1 + masa)


# --------------------- Bootstrap del partido -------------------------------
@dataclass
class MatchSim:
    A: np.ndarray              # (n_sim, n_metricas)
    B: np.ndarray
    metricas: list[str]
    lam_a_blend: float
    lam_b_blend: float

    def col(self, side: np.ndarray, metrica: str) -> np.ndarray:
        return side[:, self.metricas.index(metrica)]


def simular_partido_bootstrap(
    pool_A: pd.DataFrame | None,
    pool_B: pd.DataFrame | None,
    metricas: list[str],
    cols_shrink,
    global_means: dict[str, float],
    eA: str,
    eB: str,
    rng: np.random.Generator,
    n_sim: int = config.N_SIM,
    w_fifa: float = config.W_FIFA,
    total_esperado: float = config.ELO_TOTAL_ESPERADO,
    factor_a: float = 1.0,
    factor_b: float = 1.0,
    sharp_k: float = config.LAMBDA_SHARP_K,
) -> MatchSim | None:
    if pool_A is None or pool_B is None or len(pool_A) == 0 or len(pool_B) == 0:
        return None

    idx_A = rng.choice(len(pool_A), size=n_sim, replace=True,
                       p=pool_A["peso"].to_numpy())
    idx_B = rng.choice(len(pool_B), size=n_sim, replace=True,
                       p=pool_B["peso"].to_numpy())

    matA = pool_A[metricas].to_numpy(dtype=float)
    matB = pool_B[metricas].to_numpy(dtype=float)
    sim_A = matA[idx_A]
    sim_B = matB[idx_B]

    # Eventos raros: Poisson(tasa shrunk) en lugar del bootstrap
    for c in cols_shrink:
        if c not in metricas:
            continue
        j = metricas.index(c)
        rate_A = tasa_shrunk(pool_A, c, global_means)
        rate_B = tasa_shrunk(pool_B, c, global_means)
        sim_A[:, j] = rng.poisson(max(rate_A, 1e-6), n_sim)
        sim_B[:, j] = rng.poisson(max(rate_B, 1e-6), n_sim)

    # Blend Poisson-ELO solo para goles
    jg = metricas.index("goles")
    lam_a_pool = sim_A[:, jg].mean()
    lam_b_pool = sim_B[:, jg].mean()
    el_a, el_b = elo_lambdas(get_elo(eA), get_elo(eB), total_esperado=total_esperado)
    # factor_a/b: ajuste por bajas (Task 4.2); 1.0 = plantilla completa.
    lam_a_blend = ((1 - w_fifa) * lam_a_pool + w_fifa * el_a) * factor_a
    lam_b_blend = ((1 - w_fifa) * lam_b_pool + w_fifa * el_b) * factor_b
    # Sharpening: separa la diferencia por sharp_k manteniendo el total fijo
    # (corrige la timidez del 1X2 sin mover el O/U de goles). k=1.0 = sin efecto.
    if sharp_k != 1.0:
        half = (lam_a_blend + lam_b_blend) / 2.0
        lam_a_blend = max(0.05, half + sharp_k * (lam_a_blend - half))
        lam_b_blend = max(0.05, half + sharp_k * (lam_b_blend - half))
    sim_A[:, jg] = rng.poisson(max(lam_a_blend, 1e-6), n_sim)
    sim_B[:, jg] = rng.poisson(max(lam_b_blend, 1e-6), n_sim)

    return MatchSim(A=sim_A, B=sim_B, metricas=list(metricas),
                    lam_a_blend=lam_a_blend, lam_b_blend=lam_b_blend)

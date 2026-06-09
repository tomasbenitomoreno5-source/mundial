"""Mercados de equipo a partir de las simulaciones MC (bloque 6, Fase 1).

Fase 1 (núcleo, lo que necesita la web MVP): 1X2, doble oportunidad, BTTS y
Over/Under de todas las métricas de conteo (goles, córners, tiros, tarjetas…).
Los goles se re-derivan de la matriz Dixon-Coles para preservar la covarianza
gA↔gB; el resto usa suavizado Negative-Binomial (MoM) como en la mejora #7.

La cola larga (marcador exacto, hándicaps, HT/FT, mercados de jugador) queda
para la Fase 2.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import nbinom, poisson

from . import config
from .simulate import MatchSim, dixon_coles_matrix, sample_dc


def generar_lineas(mu: float) -> list[float]:
    """Líneas semienteras alrededor de la media (X+0.5)."""
    if mu is None or np.isnan(mu) or mu < 0:
        return []
    centro = np.floor(mu)
    lns = [centro + o + 0.5 for o in range(-3, 6)]
    lns = [round(x, 2) for x in lns if x >= 0.5]
    # unique preservando orden
    seen, out = set(), []
    for x in lns:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def fit_distr(sim_vec: np.ndarray) -> dict:
    """Ajuste por momentos: NB si hay sobre-dispersión, si no Poisson."""
    v = sim_vec[~np.isnan(sim_vec)]
    if len(v) == 0:
        return {"tipo": "empirico", "v": sim_vec}
    mu = float(v.mean())
    if mu <= 0:
        return {"tipo": "cero"}
    vv = float(v.var(ddof=1))
    if vv > mu * 1.02:
        size = mu ** 2 / (vv - mu)
        if np.isfinite(size) and 0 < size < 1e4:
            return {"tipo": "nb", "size": size, "mu": mu}
    return {"tipo": "pois", "mu": mu}


def prob_over(fit: dict, linea: float) -> float:
    """P(X > linea) desde el ajuste cacheado."""
    if fit["tipo"] == "cero":
        return 0.0
    L = np.floor(linea)
    if fit["tipo"] == "nb":
        r, mu = fit["size"], fit["mu"]
        p = r / (r + mu)
        return float(1 - nbinom.cdf(L, r, p))
    if fit["tipo"] == "pois":
        return float(1 - poisson.cdf(L, fit["mu"]))
    return float((fit["v"] > linea).mean())


def calcular_mercados(
    sims: MatchSim,
    pid: str,
    fecha: str,
    eA: str,
    eB: str,
    metricas_ou=config.METRICAS_OU,
    rng: np.random.Generator | None = None,
    n_sim: int = config.N_SIM,
) -> list[dict]:
    if sims is None:
        return []
    if rng is None:
        rng = np.random.default_rng(config.SEED)

    out: list[dict] = []

    def push(mercado, ambito, evento, linea, prob):
        out.append({
            "partido_id": pid, "fecha": fecha, "equipo_a": eA, "equipo_b": eB,
            "mercado": mercado, "ambito": ambito, "evento_o_jugador": evento,
            "linea_o_target": linea,
            "probabilidad": round(max(0.0, min(1.0, float(prob))), 4),
        })

    sA = sims.A.copy()
    sB = sims.B.copy()
    jg = sims.metricas.index("goles")

    # Re-derivar goles desde la matriz Dixon-Coles (mejora #1)
    lam_a = sims.lam_a_blend if np.isfinite(sims.lam_a_blend) else sA[:, jg].mean()
    lam_b = sims.lam_b_blend if np.isfinite(sims.lam_b_blend) else sB[:, jg].mean()
    M_dc = dixon_coles_matrix(lam_a, lam_b)
    gA, gB = sample_dc(M_dc, n_sim, rng)
    sA[:, jg] = gA
    sB[:, jg] = gB

    # --- 1X2 (desde los samples DC) ---
    p_a = float((gA > gB).mean())
    p_x = float((gA == gB).mean())
    p_b = float((gA < gB).mean())
    push("1X2", "-", "gana_A", "-", p_a)
    push("1X2", "-", "empate", "-", p_x)
    push("1X2", "-", "gana_B", "-", p_b)

    # --- Doble oportunidad ---
    push("doble_oportunidad", "-", "1X", "-", p_a + p_x)
    push("doble_oportunidad", "-", "X2", "-", p_x + p_b)
    push("doble_oportunidad", "-", "12", "-", p_a + p_b)

    # --- BTTS ---
    p_btts = float(((gA >= 1) & (gB >= 1)).mean())
    push("btts", "-", "si", "-", p_btts)
    push("btts", "-", "no", "-", 1 - p_btts)

    # --- Over/Under de métricas de conteo ---
    for m in metricas_ou:
        if m not in sims.metricas:
            continue
        j = sims.metricas.index(m)
        vA = sA[:, j]
        vB = sB[:, j]
        vT = vA + vB
        usar_nb = m != "goles"  # goles ya viene de DC: no se re-suaviza
        fitA = fit_distr(vA) if usar_nb else None
        fitB = fit_distr(vB) if usar_nb else None
        fitT = fit_distr(vT) if usar_nb else None
        for L in generar_lineas(vA.mean()):
            p = prob_over(fitA, L) if usar_nb else float((vA > L).mean())
            push(m, "A", "over", L, p)
            push(m, "A", "under", L, 1 - p)
        for L in generar_lineas(vB.mean()):
            p = prob_over(fitB, L) if usar_nb else float((vB > L).mean())
            push(m, "B", "over", L, p)
            push(m, "B", "under", L, 1 - p)
        for L in generar_lineas(vT.mean()):
            p = prob_over(fitT, L) if usar_nb else float((vT > L).mean())
            push(m, "TOTAL", "over", L, p)
            push(m, "TOTAL", "under", L, 1 - p)

    return out

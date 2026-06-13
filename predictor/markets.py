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
    """Líneas semienteras alrededor de la media (X+0.5). El rango (config) es
    amplio; las líneas triviales se descartan luego por probabilidad."""
    if mu is None or np.isnan(mu) or mu < 0:
        return []
    centro = np.floor(mu)
    lns = [centro + o + 0.5 for o in range(config.LINEA_OFFSET_MIN, config.LINEA_OFFSET_MAX)]
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
    shares: dict[str, float] | None = None,
) -> list[dict]:
    if sims is None:
        return []
    if rng is None:
        rng = np.random.default_rng(config.SEED)

    out: list[dict] = []

    def push(mercado, ambito, evento, linea, prob, periodo="FT"):
        out.append({
            "partido_id": pid, "fecha": fecha, "equipo_a": eA, "equipo_b": eB,
            "mercado": mercado, "ambito": ambito, "evento_o_jugador": evento,
            "linea_o_target": linea,
            "probabilidad": round(max(0.0, min(1.0, float(prob))), 4),
            "periodo": periodo,
        })

    triv = config.LINEA_PROB_TRIVIAL

    def push_ou(mercado, ambito, linea, p_over, periodo="FT"):
        """Push over+under solo si la línea no es trivial (corta colas inútiles)."""
        if triv <= p_over <= 1 - triv:
            push(mercado, ambito, "over", linea, p_over, periodo)
            push(mercado, ambito, "under", linea, 1 - p_over, periodo)

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
            push_ou(m, "A", L, p)
        for L in generar_lineas(vB.mean()):
            p = prob_over(fitB, L) if usar_nb else float((vB > L).mean())
            push_ou(m, "B", L, p)
        for L in generar_lineas(vT.mean()):
            p = prob_over(fitT, L) if usar_nb else float((vT > L).mean())
            push_ou(m, "TOTAL", L, p)

    # --- Mercados por mitad (1ª/2ª parte) -----------------------------------
    # Se reparte cada conteo simulado del partido completo en mitades por split
    # binomial con la cuota real de 1ª parte (data/reparto_mitades.csv). Así el
    # total 1ª+2ª es coherente con el mercado FT y no se toca el motor.
    if shares:
        def split(v, share):
            vi = np.rint(np.clip(v, 0, None)).astype(int)
            h1 = rng.binomial(vi, share)
            return h1, vi - h1

        # Goles por mitad (reparto de los goles DC) → O/U + 1X2/BTTS de 1ª parte.
        gshare = shares.get("goles", config.REPARTO_1H_DEFAULT["goles"])
        gA1, gA2 = split(gA, gshare)
        gB1, gB2 = split(gB, gshare)
        pa1 = float((gA1 > gB1).mean())
        px1 = float((gA1 == gB1).mean())
        pb1 = float((gA1 < gB1).mean())
        push("1X2", "-", "gana_A", "-", pa1, "1H")
        push("1X2", "-", "empate", "-", px1, "1H")
        push("1X2", "-", "gana_B", "-", pb1, "1H")
        pbtts1 = float(((gA1 >= 1) & (gB1 >= 1)).mean())
        push("btts", "-", "si", "-", pbtts1, "1H")
        push("btts", "-", "no", "-", 1 - pbtts1, "1H")

        for m in config.METRICAS_OU_MITAD:
            if m not in sims.metricas:
                continue
            j = sims.metricas.index(m)
            share = shares.get(m, config.REPARTO_1H_DEFAULT.get(m, 0.45))
            if m == "goles":
                a1, a2, b1, b2 = gA1, gA2, gB1, gB2
            else:
                a1, a2 = split(sA[:, j], share)
                b1, b2 = split(sB[:, j], share)
            for periodo, vA_h, vB_h in (("1H", a1, b1), ("2H", a2, b2)):
                vT_h = vA_h + vB_h
                for L in generar_lineas(vA_h.mean()):
                    push_ou(m, "A", L, float((vA_h > L).mean()), periodo)
                for L in generar_lineas(vB_h.mean()):
                    push_ou(m, "B", L, float((vB_h > L).mean()), periodo)
                for L in generar_lineas(vT_h.mean()):
                    push_ou(m, "TOTAL", L, float((vT_h > L).mean()), periodo)

    return out

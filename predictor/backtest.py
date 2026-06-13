"""Backtest temporal: replay de partidos históricos con datos SOLO-pasado.

Para cada mes desde --desde: reajusta KNN + fuerza usando únicamente partidos
con fecha anterior al mes, y predice los partidos jugados en ese mes. Compara el
motor completo contra un baseline Poisson off/def + Dixon-Coles. Si el motor no
bate al baseline, las capas extra (pool/KNN/QoO/ELO) no están aportando.

Métricas: Brier y log-loss 1X2, Brier de Over 2.5 y BTTS.

Uso:  python -m predictor.backtest --desde 2026-01-01
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import config
from .dataset import load_dataset
from .metrics import brier_1x2, logloss_1x2
from .pool import ajustar_pool_por_calidad_rival, construir_pool
from .simulate import dixon_coles_matrix, simular_partido_bootstrap
from .strength import compute_strength
from .style import compute_style_knn

MIN_PARTIDOS_PREVIOS = 5
N_SIM_BACKTEST = 4000


def _resultado(ga: int, gb: int) -> str:
    return "1" if ga > gb else ("2" if ga < gb else "X")


def _partidos_unicos(stats: pd.DataFrame) -> pd.DataFrame:
    """Una fila por partido_id (define A=equipo_nombre, B=oponente)."""
    return stats.sort_values(["partido_id", "equipo_nombre"]).drop_duplicates("partido_id")


def _baseline_dc(pasado: pd.DataFrame, eA: str, eB: str) -> tuple[float, float] | None:
    """λs de un Poisson off/def clásico: λ_A = off_A · def_B / media_global."""
    g = pasado.groupby("equipo_nombre").agg(off=("goles", "mean"), de=("goles_op", "mean"))
    mu = pasado["goles"].mean()
    if eA not in g.index or eB not in g.index or not mu > 0:
        return None
    lam_a = g.loc[eA, "off"] * g.loc[eB, "de"] / mu
    lam_b = g.loc[eB, "off"] * g.loc[eA, "de"] / mu
    return max(lam_a, 0.05), max(lam_b, 0.05)


def _probs_desde_matriz(M: np.ndarray) -> tuple[float, float, float, float, float]:
    """(p1, px, p2, p_over2.5, p_btts) desde la matriz Dixon-Coles."""
    i, j = np.indices(M.shape)
    p1 = float(M[i > j].sum())
    px = float(M[i == j].sum())
    p2 = float(M[i < j].sum())
    pov = float(M[(i + j) > 2.5].sum())
    pbt = float(M[(i >= 1) & (j >= 1)].sum())
    return p1, px, p2, pov, pbt


def backtest(desde: str, n_sim: int = N_SIM_BACKTEST, seed: int = config.SEED,
             half_life: float = config.RECENCIA_HALF_LIFE_DIAS,
             params: dict | None = None,
             metricas_out: list | None = None) -> pd.DataFrame:
    """params: dict opcional con w_fifa/rho/total_esperado/bandwidth para calibrar.

    metricas_out: si se pasa una lista, se rellena (en sitio) con un dict por
    (partido, métrica de conteo) con la distribución predicha del TOTAL del
    partido (media + cuantiles) y el total real, para medir calibración de los
    mercados O/U más allá del 1X2. Aditivo: no altera el DataFrame devuelto.
    """
    p = params or {}
    w_fifa = p.get("w_fifa", config.W_FIFA)
    rho = p.get("rho", config.RHO_DC)
    total_esperado = p.get("total_esperado", config.ELO_TOTAL_ESPERADO)
    bandwidth = p.get("bandwidth", config.POOL_BANDWIDTH)
    sharp_k = p.get("sharp_k", config.LAMBDA_SHARP_K)
    d = load_dataset()
    stats = d.stats.copy()
    stats = stats[stats["fecha"].notna()]
    stats["mes"] = stats["fecha"].astype(str).str[:7]

    partidos = _partidos_unicos(stats)
    meses = sorted(m for m in partidos["mes"].unique() if f"{m}-01" >= desde)

    rng = np.random.default_rng(seed)
    cols_shrink = [c for c in config.COLS_RARAS_SHRINK if c in d.metricas_equipo]
    filas: list[dict] = []

    # Totales reales por partido (suma de las filas de ambos equipos) para medir
    # la calibración de los mercados O/U de conteo.
    recolectar = (
        [m for m in config.METRICAS_OU if m in d.metricas_equipo]
        if metricas_out is not None else []
    )
    tot_real_pid = (
        stats.groupby("partido_id")[recolectar].sum(min_count=1).to_dict("index")
        if recolectar else {}
    )

    for mes in meses:
        pasado = stats[stats["mes"] < mes]
        if len(pasado) < 200:
            continue
        mes_df = partidos[partidos["mes"] == mes]
        n_prev = pasado.groupby("equipo_nombre").size()

        knn = compute_style_knn(pasado)
        fuerza = compute_strength(
            pasado, sorted(set(mes_df["equipo_nombre"]) | set(mes_df["oponente"]))
        )
        gmeans = {c: float(pasado[c].mean()) for c in cols_shrink if c in pasado.columns}

        for _, p in mes_df.iterrows():
            eA, eB = p["equipo_nombre"], p["oponente"]
            if n_prev.get(eA, 0) < MIN_PARTIDOS_PREVIOS or n_prev.get(eB, 0) < MIN_PARTIDOS_PREVIOS:
                continue
            ga, gb = int(p["goles"]), int(p["goles_op"])

            ref = f"{mes}-01"  # recencia respecto al inicio del mes (solo-pasado)
            pool_A = ajustar_pool_por_calidad_rival(
                construir_pool(eA, eB, pasado, knn, fuerza, bandwidth=bandwidth,
                               fecha_ref=ref, half_life=half_life),
                fuerza.get(eB, 0.0), fuerza)
            pool_B = ajustar_pool_por_calidad_rival(
                construir_pool(eB, eA, pasado, knn, fuerza, bandwidth=bandwidth,
                               fecha_ref=ref, half_life=half_life),
                fuerza.get(eA, 0.0), fuerza)
            sims = simular_partido_bootstrap(
                pool_A, pool_B, d.metricas_equipo, cols_shrink, gmeans, eA, eB, rng,
                n_sim=n_sim, w_fifa=w_fifa, total_esperado=total_esperado,
                sharp_k=sharp_k,
            )
            if sims is None or not (np.isfinite(sims.lam_a_blend) and np.isfinite(sims.lam_b_blend)):
                continue
            M = dixon_coles_matrix(sims.lam_a_blend, sims.lam_b_blend, rho=rho)
            p1, px, p2, pov, pbt = _probs_desde_matriz(M)

            fila = {
                "mes": mes, "partido_id": p["partido_id"], "eA": eA, "eB": eB,
                "ga": ga, "gb": gb, "res": _resultado(ga, gb),
                "p1": p1, "px": px, "p2": p2, "p_o25": pov, "p_btts": pbt,
            }
            bl = _baseline_dc(pasado, eA, eB)
            if bl:
                Mb = dixon_coles_matrix(*bl)
                b1, bx, b2, bov, bbt = _probs_desde_matriz(Mb)
                fila.update({"b1": b1, "bx": bx, "b2": b2, "b_o25": bov, "b_btts": bbt})
            filas.append(fila)

            # Calibración de mercados de conteo: total predicho vs total real.
            if metricas_out is not None:
                tot = tot_real_pid.get(p["partido_id"])
                if tot:
                    for met in recolectar:
                        if met not in sims.metricas:
                            continue
                        actual = tot.get(met)
                        if actual is None or not np.isfinite(actual):
                            continue
                        pred = sims.col(sims.A, met) + sims.col(sims.B, met)
                        qs = np.percentile(pred, [10, 25, 50, 75, 90])
                        # Líneas O/U centradas en la media predicha (4 medio-
                        # enteros) con su prob. de over y el over real → calibración.
                        base = np.floor(pred.mean())
                        lineas = []
                        for off in (-1.5, -0.5, 0.5, 1.5):
                            L = base + off
                            if L < 0:
                                continue
                            lineas.append((float(L), float((pred > L).mean()),
                                           1.0 if actual > L else 0.0))
                        metricas_out.append({
                            "partido_id": p["partido_id"], "metrica": met,
                            "pred_mean": float(pred.mean()),
                            "q10": float(qs[0]), "q25": float(qs[1]),
                            "q50": float(qs[2]), "q75": float(qs[3]),
                            "q90": float(qs[4]), "actual": float(actual),
                            "lineas": lineas,
                        })

    return pd.DataFrame(filas)


def resumen(df: pd.DataFrame) -> str:
    if len(df) == 0:
        return "backtest vacío (¿faltan fechas o pocos partidos elegibles?)"
    res = df["res"].tolist()
    modelo = list(zip(df["p1"], df["px"], df["p2"]))
    ov = (df["ga"] + df["gb"] > 2.5).astype(float)
    bt = ((df["ga"] >= 1) & (df["gb"] >= 1)).astype(float)
    lineas = [
        f"partidos evaluados: {len(df)}",
        f"modelo   : logloss={logloss_1x2(modelo, res):.4f}  brier={brier_1x2(modelo, res):.4f}",
        f"  O2.5 brier={((df['p_o25'] - ov) ** 2).mean():.4f}  BTTS brier={((df['p_btts'] - bt) ** 2).mean():.4f}",
    ]
    if "b1" in df.columns:
        con = df.dropna(subset=["b1"])
        bl = list(zip(con["b1"], con["bx"], con["b2"]))
        mod = list(zip(con["p1"], con["px"], con["p2"]))
        r = con["res"].tolist()
        lineas += [
            f"(comparativa sobre {len(con)} con baseline)",
            f"modelo   : logloss={logloss_1x2(mod, r):.4f}",
            f"baseline : logloss={logloss_1x2(bl, r):.4f}",
        ]
    return "\n".join(lineas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-01-01")
    ap.add_argument("--n-sim", type=int, default=N_SIM_BACKTEST)
    ap.add_argument("--out", default=str(config.DATA_DIR / "backtest_resultados.csv"))
    args = ap.parse_args()
    df = backtest(args.desde, n_sim=args.n_sim)
    df.to_csv(args.out, sep=";", index=False, encoding="utf-8-sig")
    print(resumen(df))


if __name__ == "__main__":
    main()

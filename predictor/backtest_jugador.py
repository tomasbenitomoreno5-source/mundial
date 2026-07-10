"""Backtest temporal del modelo de JUGADOR — mercado "marca gol" (anytime_scorer).

Análogo a backtest.py pero a nivel jugador: para cada mes, reconstruye el modelo
con datos SOLO-pasados (KNN de estilo + pool por jugador) y predice, para cada
jugador que jugó un partido de ese mes, P(marca >=1 gol). Compara con lo real
(telemetria_full.csv: goals>=1). Mide Brier, log-loss y calibración.

Sirve para (a) medir de una vez cómo de bueno es el modelo de jugador, y (b)
validar si mezclar el xG de jugador mejora la predicción (--w-xg), con fallback
a goles donde no hay xG.

Uso:  python -m predictor.backtest_jugador --desde 2025-01-01 --w-xg 0.0
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import config
from .dataset import load_dataset
from .players import (MERCADOS_JUGADOR, P_MAX_JUGADOR, _blend_xg_jugador,
                      _CAP_KEYS, _lineas_jugador, _XG_COL, cargar_telemetria,
                      construir_pool_jugador, minutos_esperados_por_jugador,
                      simular_jugador)
from .style import compute_style_knn

MIN_MINUTOS_ROL = 15.0   # minutos esperados mínimos para considerar que tiene rol
MIN_POOL_XG = 3          # filas con xG en el pool para activar el brazo xG


def _player_team_map(tel: pd.DataFrame) -> dict[str, str]:
    """jugador -> selección (moda de home/away en sus partidos)."""
    apil = pd.concat([
        tel[["jugador", "home_team"]].rename(columns={"home_team": "equipo"}),
        tel[["jugador", "away_team"]].rename(columns={"away_team": "equipo"}),
    ])
    apil = apil[apil["equipo"].notna() & (apil["equipo"] != "")]
    return apil.groupby("jugador")["equipo"].agg(lambda s: s.mode().iat[0]).to_dict()


def _p_scorer(sim: dict, pool: pd.DataFrame, minutos: float, w_xg: float) -> tuple[float, bool]:
    """P(marca >=1). Si w_xg>0 y el pool tiene xG, mezcla con un Poisson sobre el
    xG-por-minuto del jugador (fallback a goles si no hay xG). Devuelve (p, uso_xg)."""
    p_goals = float((sim["goals"] >= 1).mean())
    xg = pd.to_numeric(pool.get("expectedGoals"), errors="coerce").to_numpy(dtype=float)
    mn = pd.to_numeric(pool.get("minutesPlayed"), errors="coerce").to_numpy(dtype=float)
    pe = pool["peso"].to_numpy(dtype=float)
    ok = ~np.isnan(xg) & ~np.isnan(mn) & (mn > 0)
    elegible = ok.sum() >= MIN_POOL_XG and (pe[ok] * mn[ok]).sum() > 0
    if not elegible:
        return p_goals, False
    if w_xg <= 0:
        return p_goals, True  # elegible, pero sin mezcla (baseline comparable)
    rate_min = (pe[ok] * xg[ok]).sum() / (pe[ok] * mn[ok]).sum()
    lam_xg = max(0.0, rate_min * minutos)
    p_xg = 1.0 - np.exp(-lam_xg)
    return (1 - w_xg) * p_goals + w_xg * p_xg, True


def _num(x) -> float:
    try:
        return float(str(x).replace(",", "."))
    except (ValueError, TypeError):
        return float("nan")


def _eval_mercados_jugador(sim: dict, pool: pd.DataFrame, row, minutos: float,
                           w_xg: float, out: list[dict]) -> None:
    """Emite predicciones {mercado, p, y} de cada mercado de jugador para medir
    su calibración (mismo cálculo que producción). Excluye saves (portero) y
    tarjeta (heurística sin resultado limpio)."""
    triv = config.LINEA_PROB_TRIVIAL_JUGADOR
    for key, metric, tipo in MERCADOS_JUGADOR:
        if key == "saves" or metric == "__yellow_card__":
            continue
        if tipo == "binary":
            if metric == "__goal_or_assist__":
                g, a = _num(row.get("goals")), _num(row.get("goalAssist"))
                if np.isnan(g) and np.isnan(a):
                    continue
                p = float(((sim["goals"] >= 1) | (sim["goalAssist"] >= 1)).mean())
                y = 1.0 if ((g >= 1) or (a >= 1)) else 0.0
            elif metric in sim:
                real = _num(row.get(metric))
                if np.isnan(real):
                    continue
                p = float((sim[metric] >= 1).mean())
                if metric in _XG_COL and w_xg > 0:
                    p = _blend_xg_jugador(p, pool, _XG_COL[metric], minutos, w=w_xg)
                y = 1.0 if real >= 1 else 0.0
            else:
                continue
            if key in _CAP_KEYS:
                p = min(p, P_MAX_JUGADOR)
            out.append({"mercado": key, "p": min(max(p, 0.0), 1.0), "y": y})
        else:  # over/under
            if metric not in sim:
                continue
            real = _num(row.get(metric))
            if np.isnan(real):
                continue
            v = sim[metric]
            for L in _lineas_jugador(float(v.mean())):
                po = float((v > L).mean())
                if triv <= po <= 1 - triv:
                    out.append({"mercado": key, "p": po, "y": 1.0 if real > L else 0.0})


def backtest_jugador(desde: str, n_sim: int = 1500, w_xg: float = 0.0,
                     seed: int = config.SEED, preds_out: list | None = None) -> pd.DataFrame:
    d = load_dataset()
    stats = d.stats.copy()
    stats = stats[stats["fecha"].notna()]
    stats["mes"] = stats["fecha"].astype(str).str[:7]

    tel = cargar_telemetria()
    # fecha por partido (para split temporal) desde stats
    fpid = stats.drop_duplicates("partido_id").set_index("partido_id")["fecha"].astype(str).to_dict()
    tel = tel.copy()
    tel["fecha"] = tel["partido_id"].astype(str).map(fpid)
    tel = tel[tel["fecha"].notna()]
    tel["mes"] = tel["fecha"].str[:7]
    for c in ("goals", "minutesPlayed"):
        tel[c] = pd.to_numeric(tel[c], errors="coerce")

    rng = np.random.default_rng(seed)
    meses = sorted(m for m in tel["mes"].dropna().unique() if f"{m}-01" >= desde)
    filas: list[dict] = []

    for mes in meses:
        pasado_tel = tel[tel["mes"] < mes]
        pasado_stats = stats[stats["mes"] < mes]
        if len(pasado_stats) < 200 or len(pasado_tel) < 200:
            continue
        knn = compute_style_knn(pasado_stats)
        pteam = _player_team_map(pasado_tel)
        mes_tel = tel[(tel["mes"] == mes) & (tel["minutesPlayed"] > 0)]
        # minutos esperados (solo-pasado) de los jugadores que aparecen este mes
        sel = {j: pteam[j] for j in mes_tel["jugador"].unique() if j in pteam}
        minutos_esp = minutos_esperados_por_jugador(pasado_tel, sel, pasado_stats)
        ref = f"{mes}-01"

        for pid, grp in mes_tel.groupby("partido_id"):
            home = grp["home_team"].iloc[0]
            away = grp["away_team"].iloc[0]
            for _, r in grp.iterrows():
                j = r["jugador"]
                team = sel.get(j)
                if team not in (home, away):
                    continue
                rival = away if team == home else home
                mins = minutos_esp.get(j, 0.0)
                if mins < MIN_MINUTOS_ROL:
                    continue
                pool = construir_pool_jugador(j, team, rival, pasado_tel, knn, fecha_ref=ref)
                sim = simular_jugador(pool, rng, mins, n_sim=n_sim)
                if sim is None or "goals" not in sim:
                    continue
                p, uso_xg = _p_scorer(sim, pool, mins, w_xg)
                filas.append({"mes": mes, "partido_id": str(pid), "jugador": j,
                              "p": min(max(p, 0.0), 1.0),
                              "marco": 1 if (r["goals"] or 0) >= 1 else 0,
                              "uso_xg": uso_xg})
                if preds_out is not None:
                    _eval_mercados_jugador(sim, pool, r, mins, w_xg, preds_out)
    return pd.DataFrame(filas)


def _metricas(df: pd.DataFrame, etiq: str) -> str:
    if not len(df):
        return f"{etiq}: vacío"
    p = df["p"].to_numpy(); y = df["marco"].to_numpy()
    brier = float(((p - y) ** 2).mean())
    eps = 1e-12
    logloss = float(-(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)).mean())
    base = y.mean()  # tasa real de "marca gol"
    # calibración: bins de 0.1
    return (f"{etiq}: n={len(df)} | brier={brier:.4f} | logloss={logloss:.4f} | "
            f"tasa_real={base:.3f} | p_media={p.mean():.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2025-01-01")
    ap.add_argument("--n-sim", type=int, default=1500)
    ap.add_argument("--w-xg", type=float, default=0.0)
    args = ap.parse_args()
    df = backtest_jugador(args.desde, n_sim=args.n_sim, w_xg=args.w_xg)
    print(f"=== backtest jugador (anytime_scorer) desde {args.desde} | w_xg={args.w_xg} ===")
    print(_metricas(df, "TODOS    "))
    if args.w_xg > 0 and "uso_xg" in df.columns:
        print(_metricas(df[df["uso_xg"]], "con xG   "))
        print(_metricas(df[~df["uso_xg"]], "sin xG   "))


if __name__ == "__main__":
    main()

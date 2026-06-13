"""Construcción del pool bootstrap por equipo + ajuste por calidad del rival.

Port del bloque 5.1 (construir_pool) y de la mejora #2 (QoO) del R.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import config
from .style import StyleKNN


def _prox_fuerza(team_vec, opp_vec, fuerza_map, fuerza_diff_target, bandwidth):
    """Kernel gaussiano sobre la distancia del diferencial de fuerza al target."""
    f_t = np.array([fuerza_map.get(t, 0.0) for t in team_vec])
    f_o = np.array([fuerza_map.get(o, 0.0) for o in opp_vec])
    diff_pool = f_t - f_o
    return np.exp(-((fuerza_diff_target - diff_pool) ** 2) / (2 * bandwidth ** 2))


def _peso_torneo(torneos: pd.Series) -> np.ndarray:
    """Atenúa los amistosos (menos informativos) frente a partidos competitivos."""
    es_amistoso = torneos.fillna("").str.contains("Friendl", case=False).to_numpy()
    return np.where(es_amistoso, config.PESO_AMISTOSO, 1.0)


def _peso_recencia(fechas: pd.Series, fecha_ref, half_life: float) -> np.ndarray:
    """Peso 0.5^(Δdías/half_life) respecto a fecha_ref. Filas sin fecha → mediana."""
    f = pd.to_datetime(fechas, errors="coerce")
    delta = (pd.Timestamp(fecha_ref) - f).dt.days
    delta = delta.clip(lower=0).to_numpy(dtype=float)
    w = np.power(0.5, delta / half_life)
    if np.isnan(w).any():
        med = np.nanmedian(w)
        w = np.where(np.isnan(w), med if np.isfinite(med) else 1.0, w)
    return w


def construir_pool(
    propio: str,
    rival: str,
    stats: pd.DataFrame,
    knn: StyleKNN,
    fuerza_map: dict[str, float],
    bandwidth: float = config.POOL_BANDWIDTH,
    alpha: float = config.POOL_ALPHA,
    beta: float = config.POOL_BETA,
    gamma: float = config.POOL_GAMMA,
    masa_threshold: float = config.POOL_MASA_THRESHOLD,
    fecha_ref: str | None = None,
    half_life: float = config.RECENCIA_HALF_LIFE_DIAS,
) -> pd.DataFrame | None:
    """Devuelve un DataFrame de filas-partido reales con un peso de muestreo.

    Si ``fecha_ref`` se da y las filas tienen columna ``fecha``, el peso de cada
    fila se atenúa por recencia (0.5^(Δdías/half_life)) respecto a fecha_ref.
    """
    # Solo filas con stats reales: las imputadas (mediana) serían clones que
    # comprimen varianza y rompen correlaciones del bootstrap (ver dataset 2.5b).
    if "stats_completas" in stats.columns:
        stats = stats[stats["stats_completas"]]

    w_vec_rival = knn.pesos(rival)
    w_vec_propio = knn.pesos(propio)

    f_prop = fuerza_map.get(propio, 0.0)
    f_riv = fuerza_map.get(rival, 0.0)
    fuerza_diff_target = f_prop - f_riv

    usar_recencia = fecha_ref is not None and "fecha" in stats.columns
    usar_torneo = "torneo" in stats.columns

    def prox(team_vec, opp_vec):
        return _prox_fuerza(team_vec, opp_vec, fuerza_map, fuerza_diff_target, bandwidth)

    def rec(rows):
        """Factor combinado recencia × tipo-de-competición por fila."""
        f = np.ones(len(rows))
        if usar_recencia:
            f = f * _peso_recencia(rows["fecha"], fecha_ref, half_life)
        if usar_torneo:
            f = f * _peso_torneo(rows["torneo"])
        return f

    # --- Componente alpha: partidos del propio equipo ---
    rows_a = stats[stats["equipo_nombre"] == propio].copy()
    if len(rows_a):
        rows_a["peso_raw"] = prox(rows_a["equipo_nombre"], rows_a["oponente"]) * rec(rows_a)
        rows_a["componente"] = "alpha"

    # --- Componente beta: propio vs rivales estilo-rival ---
    rows_b = stats[
        (stats["equipo_nombre"] == propio)
        & (stats["oponente"].isin(w_vec_rival))
    ].copy()
    if len(rows_b):
        w_sim = rows_b["oponente"].map(w_vec_rival).to_numpy()
        w_prox = prox(rows_b["equipo_nombre"], rows_b["oponente"])
        rows_b["peso_raw"] = w_sim * w_prox * rec(rows_b)
        rows_b["componente"] = "beta"

    # --- Componente gamma: estilo-propio vs estilo-rival ---
    rows_g = stats[
        (stats["equipo_nombre"].isin(w_vec_propio))
        & (stats["oponente"].isin(w_vec_rival))
        & (stats["equipo_nombre"] != propio)
    ].copy()
    if len(rows_g):
        w_eq = rows_g["equipo_nombre"].map(w_vec_propio).to_numpy()
        w_op = rows_g["oponente"].map(w_vec_rival).to_numpy()
        w_prox = prox(rows_g["equipo_nombre"], rows_g["oponente"])
        rows_g["peso_raw"] = w_eq * w_op * w_prox * rec(rows_g)
        rows_g["componente"] = "gamma"

    masa_a = rows_a["peso_raw"].sum() if len(rows_a) else 0.0
    masa_b = rows_b["peso_raw"].sum() if len(rows_b) else 0.0
    masa_g = rows_g["peso_raw"].sum() if len(rows_g) else 0.0

    presente = np.array([masa_a > masa_threshold, masa_b > masa_threshold,
                         masa_g > masa_threshold])
    pesos_globales = np.array([alpha, beta, gamma]) * presente

    if pesos_globales.sum() == 0:
        # Ningún componente con afinidad: cae a alpha uniforme
        if len(rows_a):
            rows_a = rows_a.copy()
            rows_a["peso"] = 1.0 / len(rows_a)
            rows_a = rows_a.drop(columns=["peso_raw"])
            return rows_a
        return None
    pesos_globales = pesos_globales / pesos_globales.sum()
    pg = {"alpha": pesos_globales[0], "beta": pesos_globales[1], "gamma": pesos_globales[2]}

    def _asignar(rows, masa, comp):
        if not len(rows):
            return rows
        if presente[{"alpha": 0, "beta": 1, "gamma": 2}[comp]] and masa > 0:
            rows["peso"] = (rows["peso_raw"] / masa) * pg[comp]
        else:
            rows["peso"] = 0.0
        return rows.drop(columns=["peso_raw"])

    rows_a = _asignar(rows_a, masa_a, "alpha")
    rows_b = _asignar(rows_b, masa_b, "beta")
    rows_g = _asignar(rows_g, masa_g, "gamma")

    partes = [r for r in (rows_a, rows_b, rows_g) if len(r)]
    pool = pd.concat(partes, ignore_index=True)
    pool = pool[pool["peso"] > 0].copy()
    if len(pool) == 0:
        return None
    pool["peso"] = pool["peso"] / pool["peso"].sum()
    return pool


def ajustar_pool_por_calidad_rival(
    pool: pd.DataFrame | None,
    f_rival_target: float,
    fuerza_map: dict[str, float],
    metricas_ajustar=config.METRICAS_QOO,
    cap_pct: float = config.QOO_CAP_PCT,
) -> pd.DataFrame | None:
    """Residualiza cada métrica sensible al rival al nivel del rival target.

    Mejora #2 del R: corrige que el historial de un equipo sea contra rivales
    más fuertes/débiles que el rival de este partido. WLS + cap del shift.
    """
    if pool is None or len(pool) < 5:
        return pool
    pool = pool.copy()
    pool["f_oponente"] = pool["oponente"].map(lambda o: fuerza_map.get(o, 0.0))
    pool["f_oponente"] = pool["f_oponente"].fillna(0.0)

    rango_obs = (pool["f_oponente"].min(), pool["f_oponente"].max())
    f_eff = float(np.clip(f_rival_target, rango_obs[0], rango_obs[1]))

    pesos = pool["peso"].to_numpy()
    x = pool["f_oponente"].to_numpy()
    X = sm.add_constant(x, has_constant="add")

    for m in metricas_ajustar:
        if m not in pool.columns:
            continue
        v = pd.to_numeric(pool[m], errors="coerce").to_numpy(dtype=float)
        n_ok = np.sum(~np.isnan(v))
        if n_ok < 5:
            continue
        if np.nanvar(v) == 0:
            continue
        if np.mean(np.isnan(v) | (v == 0)) > 0.5:
            continue

        v_fit = np.where(np.isnan(v), 0.0, v)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                mod = sm.WLS(v_fit, X, weights=pesos).fit()
        except Exception:
            continue

        pred_target = float(mod.predict(np.array([[1.0, f_eff]]))[0])
        pred_fila = mod.predict(X)

        mu_v = np.average(v_fit, weights=pesos)
        mean_pred_fila = np.average(pred_fila, weights=pesos)
        shift_prop = pred_target - mean_pred_fila
        cap_abs = cap_pct * mu_v
        shift_eff = float(np.clip(shift_prop, -cap_abs, cap_abs))
        pred_target_eff = mean_pred_fila + shift_eff

        nuevo = np.maximum(0.0, v_fit - pred_fila + pred_target_eff)

        # Escalar la familia por el mismo factor por-fila para no romper las
        # jerarquías (a puerta/fuera/bloqueados/área ≤ totales). factor acotado.
        familia = config.FAMILIAS_QOO.get(m, ())
        if familia:
            # factor multiplicativo por fila SIN cap: preserva la identidad
            # exactamente (suma hijos = total). El shift de la madre ya está
            # capado al 35%, así que el factor no explota en la práctica.
            viejo = np.where(v_fit > 0, v_fit, np.nan)
            factor = np.where(np.isnan(viejo), 1.0, nuevo / viejo)
            for hijo in familia:
                if hijo in pool.columns:
                    h = pd.to_numeric(pool[hijo], errors="coerce").to_numpy(dtype=float)
                    pool[hijo] = np.maximum(0.0, np.where(np.isnan(h), h, h * factor))

        pool[m] = nuevo

    pool = pool.drop(columns=["f_oponente"])
    return pool

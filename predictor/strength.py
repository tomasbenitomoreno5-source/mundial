"""Fuerza por equipo: interna (goles ± con shrinkage) + ELO (port bloque 4b)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def compute_strength(stats: pd.DataFrame, equipos_mundial: list[str],
                     usar_elo_mundo: bool = True) -> dict[str, float]:
    """Devuelve un mapa equipo -> fuerza (z-score combinado)."""
    agg = stats.groupby("equipo_nombre", sort=False).agg(
        n_partidos=("goles", "size"),
        off_rate=("goles", "mean"),
        def_rate=("goles_op", "mean"),
    ).reset_index()

    agg["raw"] = agg["off_rate"] - agg["def_rate"]
    prior = agg["raw"].mean()
    # Shrinkage bayesiano simple hacia el prior (media global)
    agg["raw_shrunk"] = (agg["raw"] * agg["n_partidos"] + prior * 5) / (
        agg["n_partidos"] + 5
    )
    mu = agg["raw_shrunk"].mean()
    sd = agg["raw_shrunk"].std(ddof=1)
    agg["z_interna"] = (agg["raw_shrunk"] - mu) / sd

    # ELO estandarizado sobre los mundialistas con rating (mantiene la escala).
    elo = config.ELO_2026
    mundial_con_elo = [e for e in equipos_mundial if e in elo]
    elo_vals = np.array([elo[e] for e in mundial_con_elo], dtype=float)
    mu_elo = elo_vals.mean()
    sd_elo = elo_vals.std(ddof=1)

    # ELO de todo el mundo (Task 2.4) para dar coordenada no-circular a los
    # no-mundialistas; ELO_2026 (snapshot mayo) manda para los 48. En legacy
    # (usar_elo_mundo=False) solo ELO_2026, para reproducir el R.
    elo_all = dict(config.ELO_MUNDO) if usar_elo_mundo else {}
    elo_all.update(elo)

    def z_elo(equipo: str) -> float:
        if equipo in elo_all:
            return (elo_all[equipo] - mu_elo) / sd_elo
        return np.nan

    agg["z_elo"] = agg["equipo_nombre"].map(z_elo)
    # Fuerza final: 50/50 si hay ELO; solo z_interna si no.
    agg["fuerza"] = np.where(
        agg["z_elo"].isna(),
        agg["z_interna"],
        0.5 * agg["z_interna"] + 0.5 * agg["z_elo"],
    )

    return dict(zip(agg["equipo_nombre"], agg["fuerza"]))


def get_elo(equipo: str) -> float:
    """ELO de un equipo; fallback al ELO 'promedio mundial' por defecto."""
    return float(config.ELO_2026.get(equipo, config.ELO_DEFAULT))

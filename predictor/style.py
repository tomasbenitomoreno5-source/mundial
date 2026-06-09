"""Vector de estilo táctico + PCA + KNN (port del bloque 4 del R).

El vector usa RATIOS (no volúmenes) para que el KNN agrupe por estilo táctico
y no por nivel/cantidad de juego. Se reduce con PCA (>=90% varianza, mín. 5
componentes) y se calculan los K vecinos más parecidos por equipo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

from . import config


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """Columna como numérica (coerce). Las sumas/medias ignoran NaN (na.rm)."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def _ratio(num: pd.Series, den: pd.Series) -> float:
    """sum(num) / pmax(1, sum(den)) — réplica exacta del R."""
    return float(num.sum()) / max(1.0, float(den.sum()))


def build_style_features(stats: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo con las features de estilo (ratios)."""
    rows = []
    for equipo, g in stats.groupby("equipo_nombre", sort=False):
        total_shots = _num(g, "total_shots")
        passes = _num(g, "passes")
        duels = _num(g, "duels")
        fouls = _num(g, "fouls")
        rows.append({
            "equipo_nombre": equipo,
            "n_partidos": len(g),
            "shots_on_ratio": _ratio(_num(g, "shots_on_target"), total_shots),
            "shots_box_ratio": _ratio(_num(g, "shots_inside_box"), total_shots),
            "shots_blocked_r": _ratio(_num(g, "blocked_shots"), total_shots),
            "conv_ratio": _ratio(_num(g, "goles"), total_shots),
            "possession": float(_num(g, "ball_possession").mean()),
            "pass_acc_ratio": _ratio(_num(g, "accurate_passes"), passes),
            "long_balls_r": _ratio(_num(g, "long_balls"), passes),
            "crosses_r": _ratio(_num(g, "crosses"), passes),
            "through_r": _ratio(_num(g, "through_balls"), passes),
            "final_third_r": _ratio(_num(g, "final_third_entries"), passes),
            "aerial_won_rat": _ratio(_num(g, "aerial_duels"), duels),
            "ground_won_rat": _ratio(_num(g, "ground_duels"), duels),
            "tackles_won_r": _ratio(_num(g, "tackles_won"), _num(g, "total_tackles")),
            "fouls_per_duel": _ratio(fouls, duels),
            "yellows_per_foul": _ratio(_num(g, "yellow_cards"), fouls),
            "corners_per_shot": _ratio(_num(g, "corner_kicks"), total_shots),
            "bigchance_ratio": _ratio(_num(g, "big_chances"), total_shots),
        })
    return pd.DataFrame(rows)


@dataclass
class StyleKNN:
    """Resultado del KNN: vecinos ponderados por equipo."""

    # equipo -> DataFrame(vecino, dist, peso)
    vecinos: dict[str, pd.DataFrame]
    equipos: list[str]
    k_pca: int

    def pesos(self, equipo: str) -> dict[str, float]:
        df = self.vecinos.get(equipo)
        if df is None:
            return {}
        return dict(zip(df["vecino"], df["peso"]))


def _zscore(mat: np.ndarray) -> np.ndarray:
    """Equivalente a scale() de R: (x-mean)/sd con sd muestral (ddof=1)."""
    mu = mat.mean(axis=0)
    sd = mat.std(axis=0, ddof=1)
    sd[sd == 0] = 1.0  # evita división por cero
    z = (mat - mu) / sd
    z[np.isnan(z)] = 0.0
    return z


def compute_style_knn(stats: pd.DataFrame, k: int = config.K_KNN) -> StyleKNN:
    feats = build_style_features(stats)
    feature_cols = [c for c in feats.columns if c not in ("equipo_nombre", "n_partidos")]

    # Imputar NaN/inf de cada feature con su media global (como el R)
    X = feats[feature_cols].to_numpy(dtype=float).copy()
    col_mean = np.nanmean(np.where(np.isinf(X), np.nan, X), axis=0)
    inds = np.where(~np.isfinite(X))
    X[inds] = np.take(col_mean, inds[1])

    equipos = feats["equipo_nombre"].tolist()
    Xz = _zscore(X)

    # PCA: componentes que retienen >=90% varianza (mínimo 5). prcomp(center=F)
    # — Xz ya está centrado, así que sklearn (que centra) da el mismo resultado.
    pca = PCA()
    scores = pca.fit_transform(Xz)
    var_exp = np.cumsum(pca.explained_variance_ratio_)
    k_pca = max(5, int(np.argmax(var_exp >= 0.90)) + 1)
    scores = scores[:, :k_pca]

    # KNN euclídeo. n_neighbors = k+1 para incluir el propio punto y quitarlo.
    nn = NearestNeighbors(n_neighbors=k + 1, algorithm="brute", metric="euclidean")
    nn.fit(scores)
    dist, idx = nn.kneighbors(scores)

    vecinos: dict[str, pd.DataFrame] = {}
    for i, eq in enumerate(equipos):
        nb_idx = list(idx[i])
        nb_dist = list(dist[i])
        # Quitar self si aparece
        if i in nb_idx:
            pos = nb_idx.index(i)
            nb_idx.pop(pos)
            nb_dist.pop(pos)
        nb_idx = nb_idx[:k]
        nb_dist = nb_dist[:k]
        vecinos_eq = [equipos[j] for j in nb_idx]
        w = np.exp(-np.array(nb_dist))
        w = w / w.sum()
        vecinos[eq] = pd.DataFrame({
            "vecino": vecinos_eq,
            "dist": nb_dist,
            "peso": w,
        })

    return StyleKNN(vecinos=vecinos, equipos=equipos, k_pca=k_pca)

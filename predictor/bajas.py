"""Ajuste de fuerza por bajas (Task 4.2).

Mide qué fracción del valor de mercado del once habitual de cada selección
está disponible en la convocatoria actual:

    share = Σ valor(habituales ∩ convocados) / Σ valor(habituales)
    factor = clip(share^THETA, CAP_MIN, 1.0)   (solo penaliza, nunca premia)

"Habituales" = jugadores con ≥ MIN_MINUTOS en el ciclo (telemetria_full).
El factor multiplica λ de goles del equipo. Capado a CAP_MIN porque el mapeo
de nombres entre telemetría/bios/convocatorias es imperfecto: un mismatch no
debe hundir una predicción. Su valor real aparece DURANTE el Mundial (lesiones
y sanciones por acumulación de amarillas cambian la convocatoria).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

THETA = 0.5
CAP_MIN = 0.85
MIN_MINUTOS = 270  # ≈3 partidos completos en el ciclo


def share_disponible(equipo: str, minutos: pd.DataFrame, valor: dict[str, float],
                     convocatorias: dict[str, set]) -> float:
    """Fracción del valor del once habitual presente en la convocatoria."""
    habituales = minutos[(minutos["equipo"] == equipo) & (minutos["minutos"] >= MIN_MINUTOS)]["jugador"]
    vals = {j: valor.get(j, np.nan) for j in habituales}
    vals = {j: v for j, v in vals.items() if np.isfinite(v) and v > 0}
    total = sum(vals.values())
    if total <= 0:
        return 1.0
    conv = convocatorias.get(equipo, set())
    disponibles = sum(v for j, v in vals.items() if j in conv)
    return disponibles / total


def factor_bajas(equipo: str, minutos: pd.DataFrame, valor: dict[str, float],
                 convocatorias: dict[str, set]) -> float:
    s = share_disponible(equipo, minutos, valor, convocatorias)
    return float(np.clip(s ** THETA, CAP_MIN, 1.0))


def cargar_insumos():
    """Devuelve (minutos_df[jugador,equipo,minutos], valor{jugador:eur}, conv{eq:set})."""
    tel = pd.read_csv(
        config.DATA_DIR / "telemetria_full.csv", sep=";", encoding="utf-8-sig",
        usecols=["jugador", "home_team", "away_team", "minutesPlayed"], dtype=str,
    )
    tel["minutesPlayed"] = pd.to_numeric(tel["minutesPlayed"], errors="coerce").fillna(0.0)
    # Equipo del jugador: el que aparece en TODAS sus filas (moda de home∪away).
    apil = pd.concat([
        tel[["jugador", "home_team"]].rename(columns={"home_team": "equipo"}),
        tel[["jugador", "away_team"]].rename(columns={"away_team": "equipo"}),
    ])
    equipo_de = apil.groupby("jugador")["equipo"].agg(lambda s: s.mode().iat[0])
    minutos = tel.groupby("jugador", as_index=False)["minutesPlayed"].sum()
    minutos["equipo"] = minutos["jugador"].map(equipo_de)
    minutos = minutos.rename(columns={"minutesPlayed": "minutos"})

    bios = pd.read_csv(config.DATA_DIR / "bios.csv", sep=";", encoding="utf-8-sig")
    valor = dict(zip(bios["jugador"], pd.to_numeric(bios["valor_eur"], errors="coerce")))

    conv = pd.read_csv(config.DATA_DIR / "convocatorias.csv", sep=";", encoding="utf-8-sig")
    convocatorias = conv.groupby("equipo")["jugador"].agg(set).to_dict()
    return minutos, valor, convocatorias


def factores_por_equipo(equipos: list[str]) -> dict[str, float]:
    """factor de bajas por equipo (1.0 si faltan insumos). Persiste ajuste_bajas.csv."""
    try:
        minutos, valor, conv = cargar_insumos()
    except (FileNotFoundError, KeyError, ValueError):
        return {}
    filas, out = [], {}
    for eq in equipos:
        s = share_disponible(eq, minutos, valor, conv)
        f = float(np.clip(s ** THETA, CAP_MIN, 1.0))
        out[eq] = f
        hab = minutos[(minutos["equipo"] == eq) & (minutos["minutos"] >= MIN_MINUTOS)]
        filas.append({"equipo": eq, "share": round(s, 4), "factor": round(f, 4),
                      "n_habituales": len(hab)})
    pd.DataFrame(filas).to_csv(config.DATA_DIR / "ajuste_bajas.csv", sep=";",
                               index=False, encoding="utf-8-sig")
    return out

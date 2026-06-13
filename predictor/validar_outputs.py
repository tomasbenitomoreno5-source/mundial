"""Validación de coherencia de las predicciones (Task 0.6).

Se ejecuta tras cada run del pipeline (paso del cron). Detecta automáticamente
predicciones rotas — el tipo de cosa que llegó a la web sin avisar (SOT>TS,
sumas que no cuadran, rondas de torneo imposibles). Exit code 1 si hay
violaciones, para que el orquestador lo notifique.

    python -m predictor.validar_outputs
"""

from __future__ import annotations

import sys

import pandas as pd

from . import config

TOL = 0.015  # margen por ruido MC + redondeo a 4 decimales
# Subconjunto vs superconjunto: tolerancia mayor porque a líneas bajas (≥1) dos
# métricas con fits NB independientes pueden cruzarse ~2-3pp sin ser un bug real
# (el bug del QoO que cazamos antes daba violaciones mucho mayores y masivas).
TOL_SUB = 0.035

# (subconjunto, superconjunto): a la misma línea, P(sub>L) no puede superar a P(sup>L).
PARES_SUBCONJUNTO = [
    ("shots_on_target", "total_shots"),
    ("shots_off_target", "total_shots"),
    ("shots_inside_box", "total_shots"),
    ("shots_outside_box", "total_shots"),
    ("blocked_shots", "total_shots"),
    ("accurate_passes", "passes"),
]


def validar_largo(largo: pd.DataFrame) -> list[str]:
    errores: list[str] = []
    ou = largo[largo["evento_o_jugador"].isin(["over", "under"])].copy()
    ou["linea"] = pd.to_numeric(ou["linea_o_target"], errors="coerce")

    # 1. over + under = 1
    piv = ou.pivot_table(index=["partido_id", "mercado", "ambito", "linea", "periodo"],
                         columns="evento_o_jugador", values="probabilidad", aggfunc="first")
    if "over" in piv and "under" in piv:
        mal = piv[(piv["over"] + piv["under"] - 1).abs() > 0.01]
        errores += [f"over+under≠1: {i}" for i in mal.index[:15]]

    # 2. over(L) decreciente al subir la línea
    overs = ou[ou["evento_o_jugador"] == "over"]
    for key, g in overs.groupby(["partido_id", "mercado", "ambito", "periodo"]):
        g = g.sort_values("linea")
        if (g["probabilidad"].diff() > TOL).any():
            errores.append(f"over no monótono: {key}")

    # 3. subconjunto ≤ superconjunto a la misma línea (el bug SOT>TS)
    ov = overs.pivot_table(index=["partido_id", "ambito", "linea", "periodo"],
                           columns="mercado", values="probabilidad", aggfunc="first")
    for sub, sup in PARES_SUBCONJUNTO:
        if sub in ov.columns and sup in ov.columns:
            both = ov[[sub, sup]].dropna()
            mal = both[both[sub] > both[sup] + TOL_SUB]
            errores += [f"P({sub}>L)>P({sup}>L): {i}" for i in mal.index[:15]]

    # 4. 1X2 suma 1
    x12 = largo[largo["mercado"] == "1X2"].pivot_table(
        index=["partido_id", "periodo"], columns="evento_o_jugador",
        values="probabilidad", aggfunc="first")
    mal = x12[(x12.sum(axis=1) - 1).abs() > 0.01]
    errores += [f"1X2 no suma 1: {i}" for i in mal.index[:15]]

    # 5. 1H ≤ FT (mismo over, misma línea)
    ov_p = overs.pivot_table(index=["partido_id", "mercado", "ambito", "linea"],
                             columns="periodo", values="probabilidad", aggfunc="first")
    if "1H" in ov_p.columns and "FT" in ov_p.columns:
        both = ov_p[["1H", "FT"]].dropna()
        mal = both[both["1H"] > both["FT"] + TOL]
        errores += [f"over 1H>FT: {i}" for i in mal.index[:15]]
    return errores


def validar_torneo(torneo: pd.DataFrame) -> list[str]:
    errores: list[str] = []
    rondas = [c for c in ("p_grupo", "p_r16", "p_qf", "p_sf", "p_final", "p_campeon")
              if c in torneo.columns]
    for _, r in torneo.iterrows():
        vals = [r[c] for c in rondas]
        if any(b > a + 1e-6 for a, b in zip(vals, vals[1:])):
            errores.append(f"rondas no monótonas: {r['equipo']}")
    if "p_campeon" in torneo.columns:
        s = torneo["p_campeon"].sum()
        if abs(s - 1.0) > 0.02:
            errores.append(f"suma p_campeon={s:.3f}≠1")
    return errores


def main() -> None:
    largo = pd.read_csv(config.DATA_DIR / "predicciones_largo_py.csv",
                        sep=";", decimal=",", encoding="utf-8-sig")
    errores = validar_largo(largo)
    tpath = config.DATA_DIR / "probabilidades_torneo.csv"
    if tpath.exists():
        errores += validar_torneo(pd.read_csv(tpath, sep=";"))
    if errores:
        print(f"{len(errores)} violaciones de coherencia:")
        for e in errores[:40]:
            print("  -", e)
        sys.exit(1)
    print("Outputs coherentes ✔")


if __name__ == "__main__":
    main()

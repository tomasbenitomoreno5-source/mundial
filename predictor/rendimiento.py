"""Rendimiento del modelo por mercado — calibración + Brier sobre el backtest.

Filosofía: TODO mercado se reduce a predicciones binarias (p_modelo, resultado
∈ {0,1}). Así se puntúa cualquier mercado con la misma vara:

- **Brier**: error cuadrático medio (0 perfecto). Métrica propia: premia
  acertar Y estar bien calibrado, a diferencia del "% de acierto".
- **Calibración (reliability)**: cuando el modelo dice X%, ¿pasa el X%? Se mide
  por tramos; el ECE (error de calibración esperado) lo resume en un número.
- **Cobertura** (solo conteos): ¿el intervalo central contiene el valor real
  tan a menudo como debería? Detecta infra/sobre-dispersión.

Fuente = backtest (track record, 429 partidos, todos los mercados, datos reales
de córners/tarjetas/etc.). En vivo durante el Mundial solo se puede medir la
familia de goles (las stats de conteo del Mundial están bloqueadas por
Cloudflare); esa parte la añade la web con los partidos ya jugados.

Salida: `data/rendimiento_mercados.csv` (lo carga el seed → pestaña de
rendimiento de la web).

Uso:  python -m predictor.rendimiento [--desde 2023-06-01]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
import pandas as pd

from . import config
from .backtest import backtest

# Bins de calibración (reliability).
BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]

# Etiquetas legibles por mercado (las que no estén usan su propia key).
ETIQUETAS = {
    "1X2": "Resultado (1X2)", "doble_oportunidad": "Doble oportunidad",
    "btts": "Ambos marcan", "goles": "Goles O/U",
    "corner_kicks": "Córners O/U", "yellow_cards": "Tarjetas O/U",
    "fouls": "Faltas O/U", "total_shots": "Tiros O/U",
    "shots_on_target": "Tiros a puerta O/U", "offsides": "Fueras de juego O/U",
    "tackles": "Entradas O/U", "goalkeeper_saves": "Paradas O/U",
}


def resolver_backtest(desde: str, n_sim: int) -> tuple[list[dict], list[dict]]:
    """Corre el backtest y devuelve (predicciones binarias, datos de conteo)."""
    met: list[dict] = []
    df = backtest(desde, n_sim=n_sim, metricas_out=met)
    preds: list[dict] = []

    for _, r in df.iterrows():
        res = r["res"]
        # 1X2 (one-vs-rest por resultado)
        for ev, p in (("1", r["p1"]), ("X", r["px"]), ("2", r["p2"])):
            preds.append({"mercado": "1X2", "p": float(p),
                          "y": 1.0 if res == ev else 0.0})
        # Doble oportunidad
        for combo, p in ((("1", "X"), r["p1"] + r["px"]),
                         (("1", "2"), r["p1"] + r["p2"]),
                         (("X", "2"), r["px"] + r["p2"])):
            preds.append({"mercado": "doble_oportunidad", "p": float(p),
                          "y": 1.0 if res in combo else 0.0})
        # BTTS
        bt = 1.0 if (r["ga"] >= 1 and r["gb"] >= 1) else 0.0
        preds.append({"mercado": "btts", "p": float(r["p_btts"]), "y": bt})

    # Goles + métricas de conteo: O/U por línea (de los sims del backtest)
    for m in met:
        for (_linea, p_over, y) in m["lineas"]:
            preds.append({"mercado": m["metrica"], "p": p_over, "y": y})

    return preds, met


def evaluar(preds: list[dict]) -> dict[str, dict]:
    """Por mercado: n, Brier, acierto, ECE y tabla de calibración."""
    por_mkt: dict[str, list] = defaultdict(list)
    for p in preds:
        por_mkt[p["mercado"]].append((p["p"], p["y"]))

    out: dict[str, dict] = {}
    for mkt, rows in por_mkt.items():
        ps = np.array([a for a, _ in rows])
        ys = np.array([b for _, b in rows])
        n = len(ps)
        brier = float(((ps - ys) ** 2).mean())
        hit = float(((ps >= 0.5) == (ys >= 0.5)).mean())
        bins, ece = [], 0.0
        for lo, hi in BINS:
            sel = (ps >= lo) & (ps < hi)
            c = int(sel.sum())
            if c == 0:
                continue
            pm, rm = float(ps[sel].mean()), float(ys[sel].mean())
            bins.append({"lo": lo, "hi": hi, "pred": pm, "real": rm, "n": c})
            ece += c / n * abs(pm - rm)
        out[mkt] = {"n": n, "brier": brier, "hit": hit, "ece": ece, "bins": bins}
    return out


def cobertura(met: list[dict]) -> dict[str, dict]:
    """Cobertura de intervalos central-50%/80% por métrica de conteo (dispersión)."""
    df = pd.DataFrame(met)
    out: dict[str, dict] = {}
    for metrica in df["metrica"].unique() if len(df) else []:
        sub = df[df["metrica"] == metrica]
        cob50 = ((sub["actual"] >= sub["q25"]) & (sub["actual"] <= sub["q75"])).mean()
        cob80 = ((sub["actual"] >= sub["q10"]) & (sub["actual"] <= sub["q90"])).mean()
        out[metrica] = {
            "pred_mean": float(sub["pred_mean"].mean()),
            "real_mean": float(sub["actual"].mean()),
            "cob50": float(cob50), "cob80": float(cob80),
        }
    return out


# Orden de presentación: familia de goles primero, luego conteos.
ORDEN = ["1X2", "doble_oportunidad", "btts", "goles", "corner_kicks",
         "yellow_cards", "fouls", "total_shots", "shots_on_target",
         "shots_off_target", "shots_inside_box", "shots_outside_box",
         "blocked_shots", "offsides", "tackles", "goalkeeper_saves",
         "free_kicks", "throw-ins", "goal_kicks", "passes", "accurate_passes"]


def reporte(ev: dict, cob: dict) -> str:
    lineas = ["{:<22} {:>6} {:>8} {:>8} {:>8} {:>8}".format(
        "mercado", "n", "brier", "acierto", "ECE", "cob80%"), "-" * 64]
    claves = [k for k in ORDEN if k in ev] + [k for k in ev if k not in ORDEN]
    for mkt in claves:
        e = ev[mkt]
        c80 = cob.get(mkt, {}).get("cob80")
        c80s = f"{c80 * 100:.0f}%" if c80 is not None else "—"
        marca = "  <- ECE alto" if e["ece"] > 0.05 else ""
        lineas.append("{:<22} {:>6} {:>8.3f} {:>7.0f}% {:>8.3f} {:>8}{}".format(
            ETIQUETAS.get(mkt, mkt)[:22], e["n"], e["brier"], e["hit"] * 100,
            e["ece"], c80s, marca))
    lineas.append("")
    lineas.append("Brier: menor mejor (0=perfecto). ECE: error de calibración "
                  "(menor mejor; >0.05 = mal calibrado). cob80%≈80% ideal.")
    return "\n".join(lineas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2023-06-01")
    ap.add_argument("--n-sim", type=int, default=4000)
    ap.add_argument("--out", default=str(config.DATA_DIR / "rendimiento_mercados.csv"))
    args = ap.parse_args()

    preds, met = resolver_backtest(args.desde, args.n_sim)
    ev = evaluar(preds)
    cob = cobertura(met)
    print(f"(backtest track record · {len(ev)} mercados · "
          f"{len(preds)} predicciones binarias)\n")
    print(reporte(ev, cob))

    # CSV para la web (una fila por mercado; bins y cobertura como JSON).
    filas = []
    for mkt, e in ev.items():
        filas.append({
            "mercado": mkt, "etiqueta": ETIQUETAS.get(mkt, mkt),
            "fuente": "backtest", "n": e["n"],
            "brier": round(e["brier"], 4), "acierto": round(e["hit"], 4),
            "ece": round(e["ece"], 4),
            "cob80": round(cob.get(mkt, {}).get("cob80", 0), 4) if mkt in cob else "",
            "bins_json": json.dumps(e["bins"]),
        })
    pd.DataFrame(filas).to_csv(args.out, sep=";", index=False, encoding="utf-8-sig")
    print(f"\nEscrito {args.out} ({len(filas)} mercados)")


if __name__ == "__main__":
    main()

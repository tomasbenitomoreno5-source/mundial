"""Rendimiento de mercados de JUGADOR — calibración sobre el backtest de jugador.

Mismo enfoque y vara que rendimiento.py (Brier + ECE por mercado, reduciendo todo
a predicciones binarias), pero para los mercados de jugador (marca gol, asistencia,
tiros, pases, entradas, ...). Usa el modelo de producción (incluido el xG/xA de
jugador, W_XG_JUGADOR). Excluye paradas (portero) y tarjeta (heurística).

Salida: data/rendimiento_jugador_mercados.csv → la carga el seed → sección de
rendimiento de jugador de la web.

Uso:  python -m predictor.rendimiento_jugador [--desde 2024-06-01]
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from . import config
from .backtest_jugador import backtest_jugador
from .rendimiento import evaluar

ETIQUETAS = {
    "anytime_scorer": "Marca gol", "assist": "Da asistencia",
    "goal_or_assist": "Gol o asistencia", "big_chance_created": "Crea ocasión clara",
    "shots": "Tiros O/U",
    "shots_on_target": "Tiros a puerta O/U", "shots_off_target": "Tiros fuera O/U",
    "shots_blocked": "Tiros bloqueados O/U", "big_chances_missed": "Ocasiones falladas O/U",
    "passes": "Pases O/U", "accurate_passes": "Pases precisos O/U",
    "key_passes": "Pases clave O/U", "crosses": "Centros O/U",
    "accurate_crosses": "Centros precisos O/U", "long_balls": "Balones largos O/U",
    "dribbles": "Regates O/U", "dribbles_att": "Regates intentados O/U",
    "touches": "Toques O/U", "tackles": "Entradas O/U", "won_tackles": "Entradas ganadas O/U",
    "interceptions": "Intercepciones O/U", "clearances": "Despejes O/U",
    "recoveries": "Recuperaciones O/U", "duels_won": "Duelos ganados O/U",
    "aerials_won": "Duelos aéreos O/U", "blocks": "Bloqueos O/U",
    "fouls": "Faltas cometidas O/U", "fouled": "Faltas recibidas O/U",
    "offsides": "Fueras de juego O/U", "possession_lost": "Pérdidas O/U",
    "dispossessed": "Robos sufridos O/U",
}
# Orden de presentación: gol/asistencia primero, luego el resto.
ORDEN = ["anytime_scorer", "assist", "goal_or_assist", "big_chance_created",
         "shots", "shots_on_target", "key_passes", "passes",
         "accurate_passes", "dribbles", "tackles", "interceptions", "duels_won",
         "aerials_won", "touches", "recoveries", "clearances", "fouls", "fouled"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2024-06-01")
    ap.add_argument("--n-sim", type=int, default=1500)
    ap.add_argument("--w-xg", type=float, default=config.W_XG_JUGADOR)
    ap.add_argument("--out", default=str(config.DATA_DIR / "rendimiento_jugador_mercados.csv"))
    args = ap.parse_args()

    preds: list[dict] = []
    backtest_jugador(args.desde, n_sim=args.n_sim, w_xg=args.w_xg, preds_out=preds)
    ev = evaluar(preds)
    print(f"(backtest jugador · {len(ev)} mercados · {len(preds)} predicciones binarias)\n")
    claves = [k for k in ORDEN if k in ev] + [k for k in ev if k not in ORDEN]
    print("{:<26} {:>6} {:>8} {:>8} {:>8}".format("mercado", "n", "brier", "acierto", "ECE"))
    print("-" * 60)
    for mkt in claves:
        e = ev[mkt]
        marca = "  <- ECE alto" if e["ece"] > 0.05 else ""
        print("{:<26} {:>6} {:>8.3f} {:>7.0f}% {:>8.3f}{}".format(
            ETIQUETAS.get(mkt, mkt)[:26], e["n"], e["brier"], e["hit"] * 100, e["ece"], marca))

    filas = [{
        "mercado": mkt, "etiqueta": ETIQUETAS.get(mkt, mkt), "fuente": "backtest",
        "n": e["n"], "brier": round(e["brier"], 4), "acierto": round(e["hit"], 4),
        "ece": round(e["ece"], 4), "cob80": "", "bins_json": json.dumps(e["bins"]),
    } for mkt, e in ev.items()]
    pd.DataFrame(filas).to_csv(args.out, sep=";", index=False, encoding="utf-8-sig")
    print(f"\nEscrito {args.out} ({len(filas)} mercados)")


if __name__ == "__main__":
    main()

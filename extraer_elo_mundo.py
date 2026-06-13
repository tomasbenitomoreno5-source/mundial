"""Vuelca el ELO mundial COMPLETO a data/elo_mundo.csv (equipo;elo).

Fuente: eloratings.net (TSVs planos que consume su propio frontend; accesibles
sin bloqueo). World.tsv = ranking actual (col[2]=código país, col[3]=rating);
en.teams.tsv = código → nombre.

Motivo: hoy solo los 48 mundialistas tienen ELO (config.ELO_2026). Los ~140
equipos restantes del dataset usan solo fuerza interna (circular). Con ELO
universal, la coordenada de fuerza del rival deja de depender del propio
rendimiento ofensivo → arregla el QoO (limitación documentada en el R).

Uso:  python extraer_elo_mundo.py
"""

from __future__ import annotations

import csv
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# eloratings (nombre) → canon del dataset (inglés de SofaScore).
ALIAS = {
    "Ivory Coast": "Côte d'Ivoire", "Cape Verde": "Cabo Verde",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina", "Turkey": "Türkiye",
    "United States": "USA", "Curacao": "Curaçao", "Kyrgyzstan": "Kyrgyzstan",
    "Cabo Verde": "Cabo Verde", "DR Congo": "DR Congo", "Korea DPR": "North Korea",
    "Korea Republic": "South Korea", "South Korea": "South Korea",
    "China PR": "China", "Czech Republic": "Czechia",
}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    nombres: dict[str, str] = {}
    for line in _get("https://www.eloratings.net/en.teams.tsv").splitlines():
        cols = line.split("\t")
        if len(cols) >= 2:
            nombres[cols[0]] = cols[1]

    filas = []
    for line in _get("https://www.eloratings.net/World.tsv").splitlines():
        cols = line.split("\t")
        if len(cols) >= 4 and cols[2] in nombres:
            try:
                elo = int(cols[3])
            except ValueError:
                continue
            nombre = nombres[cols[2]]
            filas.append({"equipo": ALIAS.get(nombre, nombre), "elo": elo})

    out = DATA / "elo_mundo.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["equipo", "elo"], delimiter=";")
        w.writeheader()
        w.writerows(filas)
    print(f"OK: {len(filas)} equipos -> {out.name}")

    # --- Reporte de cobertura: ¿qué equipos del dataset quedan sin ELO? ---
    elo_map = {r["equipo"]: r["elo"] for r in filas}
    stats = DATA / "stats_final.csv"
    if stats.exists():
        import pandas as pd
        eqs = set(pd.read_csv(stats, sep=";", encoding="utf-8-sig",
                              usecols=["equipo_nombre"])["equipo_nombre"].dropna())
        sin = sorted(e for e in eqs if e not in elo_map)
        print(f"equipos del dataset SIN ELO_MUNDO: {len(sin)}/{len(eqs)}")
        print("  ejemplos:", sin[:25])

    # Validación vs ELO_2026 (los 48 deben coincidir dentro de ~deriva).
    from predictor import config
    difs = {e: (config.ELO_2026[e], elo_map[e])
            for e in config.ELO_2026 if e in elo_map
            and abs(config.ELO_2026[e] - elo_map[e]) > 40}
    print(f"mundialistas con |Δ| > 40 vs snapshot mayo: {len(difs)} {difs or ''}")
    falta48 = [e for e in config.ELO_2026 if e not in elo_map]
    print(f"mundialistas SIN match en elo_mundo: {falta48 or 'ninguno'}")


if __name__ == "__main__":
    main()

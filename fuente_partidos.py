"""Emparejado partido-del-proyecto ↔ evento de ESPN (capa de identidad de partidos).

El pipeline keya por `partido_id` propio (de `partidos_a_predecir.csv`), no por el
id de la fuente. Este helper cruza cada partido del proyecto con su evento de ESPN
por el par de equipos canónico (no orientado: equipo_a no es necesariamente local).

Lo usan los extractores de 2026 (resultados, stats, ...) para escribir con el
`partido_id` correcto y orientar marcador/stats a equipo_a/equipo_b.
"""

from __future__ import annotations

import csv
from pathlib import Path

from predictor.sources import espn, identity

DATA = Path(__file__).resolve().parent / "data"
PARTIDOS = DATA / "partidos_a_predecir.csv"


def partidos_proyecto() -> list[dict]:
    """(partido_id, equipo_a, equipo_b) del calendario del proyecto."""
    with open(PARTIDOS, encoding="utf-8-sig") as f:
        return [
            {"partido_id": r["partido_id"],
             "equipo_a": r["equipo_a"].strip(),
             "equipo_b": r["equipo_b"].strip()}
            for r in csv.DictReader(f, delimiter=";")
        ]


def _indice_espn(dates: str) -> dict[frozenset, dict]:
    """{frozenset(par canónico): evento ESPN} para partidos con ambos equipos reales."""
    idx = {}
    for e in espn.scoreboard(dates=dates):
        ca, cb = identity.canonical(e["home"]), identity.canonical(e["away"])
        if ca and cb:
            idx[frozenset((ca, cb))] = e
    return idx


def emparejar(dates: str) -> list[dict]:
    """Cada partido del proyecto con su evento ESPN (o event=None si no se halló).

    Devuelve dicts con: partido_id, equipo_a, equipo_b, event_id, finalizado,
    score_a, score_b (orientados a equipo_a/equipo_b).
    """
    idx = _indice_espn(dates)
    out = []
    for p in partidos_proyecto():
        ca, cb = identity.canonical(p["equipo_a"]), identity.canonical(p["equipo_b"])
        ev = idx.get(frozenset((ca, cb))) if ca and cb else None
        fila = {**p, "event_id": None, "finalizado": False, "iniciado": False,
                "score_a": None, "score_b": None}
        if ev:
            # Orientar el marcador de home/away (ESPN) a equipo_a/equipo_b (proyecto).
            a_es_home = identity.canonical(ev["home"]) == ca
            fila.update({
                "event_id": ev["id"],
                "finalizado": ev["finalizado"],
                "iniciado": ev["iniciado"],
                "score_a": ev["home_score"] if a_es_home else ev["away_score"],
                "score_b": ev["away_score"] if a_es_home else ev["home_score"],
            })
        out.append(fila)
    return out

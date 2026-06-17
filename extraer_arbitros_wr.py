"""Fichas de árbitros del Mundial 2026: carrera desde worldreferee + pool existente.

Reemplaza el perfil de SofaScore (bloqueado). Para cada árbitro del plantel
(arbitros_mundial.csv): busca su carrera en worldreferee (partidos, amarillas,
rojas, 2ª amarillas) y la combina con las columnas *_pool del arbitro_pool.jsonl
ya existente (histórico, sin tocar) y el sofa_id de arbitro_ids.csv (continuidad
con designaciones y la web).

⚠️ ESCALA: las tasas de worldreferee son más bajas que las de SofaScore (distinta
cobertura). El modelo usa la tasa como multiplicador relativo, así que la media de
referencia debe recalcularse desde ESTA fuente (decisión de calibración a revisar).

Mismo esquema que arbitros.csv. De momento escribe a data/arbitros_wr.csv (scratch).
exit 0/3/1.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

from predictor.sources import base, worldreferee

DATA = Path(__file__).resolve().parent / "data"
ROSTER = DATA / "arbitros_mundial.csv"
IDS = DATA / "arbitro_ids.csv"
POOL = DATA / "arbitro_pool.jsonl"
OUT = DATA / "arbitros_wr.csv"
OUT_FIELDS = [
    "sofa_id", "nombre", "pais", "cc", "confederacion",
    "partidos_carrera", "amarillas", "rojas", "dobles_amarillas",
    "partidos_pool", "amarillas_pool", "amarillas_pool_local",
    "amarillas_pool_visita", "rojas_pool", "faltas_pool", "goles_pool",
    "penaltis_pool", "amarillas_pool_1h", "amarillas_pool_2h",
]

log = logging.getLogger("extraer_arbitros_wr")


def _ids_por_nombre() -> dict[str, dict]:
    if not IDS.exists():
        return {}
    with open(IDS, encoding="utf-8-sig") as f:
        return {r["nombre"]: r for r in csv.DictReader(f, delimiter=";")}


def _pool_por_id() -> dict[str, dict]:
    """Agrega arbitro_pool.jsonl por referee_id (mismo cálculo que el viejo)."""
    agg = defaultdict(lambda: {"games": 0, "yellow": 0, "yellow_home": 0,
                               "yellow_away": 0, "red": 0, "fouls": 0.0, "fouls_n": 0,
                               "goals": 0.0, "goals_n": 0, "pen": 0,
                               "yellow_1h": 0, "yellow_2h": 0})
    if not POOL.exists():
        return {}
    with open(POOL, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rid = r.get("referee_id")
            if not rid:
                continue
            a = agg[str(rid)]
            a["games"] += 1
            for k_src, k_dst in [("yellow", "yellow"), ("yellow_home", "yellow_home"),
                                 ("yellow_away", "yellow_away"), ("red", "red"),
                                 ("penalties", "pen"), ("yellow_1h", "yellow_1h"),
                                 ("yellow_2h", "yellow_2h")]:
                a[k_dst] += r.get(k_src, 0) or 0
            if r.get("fouls") is not None:
                a["fouls"] += r["fouls"]; a["fouls_n"] += 1
            gh, ga = r.get("goals_home"), r.get("goals_away")
            if gh is not None and ga is not None:
                a["goals"] += gh + ga; a["goals_n"] += 1
    return agg


def _int(x):
    return int(x) if x is not None else ""


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        with open(ROSTER, encoding="utf-8-sig") as f:
            roster = list(csv.DictReader(f, delimiter=";"))
        ids = _ids_por_nombre()
        pool = _pool_por_id()

        rows, encontrados = [], 0
        for ref in roster:
            nombre, pais = ref["nombre"], ref["pais"]
            idc = ids.get(nombre, {})
            sid = idc.get("sofa_id", "")
            try:
                c = worldreferee.career(nombre, pais)
            except base.FetchError as e:
                log.warning("worldreferee falló para %s: %s", nombre, e)
                c = None
            if c and c.get("matches"):
                encontrados += 1
            pa = pool.get(str(sid)) if sid else None
            rows.append({
                "sofa_id": sid,
                "nombre": nombre,
                "pais": idc.get("pais", pais),
                "cc": idc.get("cc", ""),
                "confederacion": ref.get("confederacion", ""),
                "partidos_carrera": _int(c["matches"]) if c else "",
                "amarillas": _int(c["yellow"]) if c else "",
                "rojas": _int(c["red"]) if c else "",
                "dobles_amarillas": _int(c["second_yellow"]) if c else "",
                "partidos_pool": pa["games"] if pa else "",
                "amarillas_pool": pa["yellow"] if pa else "",
                "amarillas_pool_local": pa["yellow_home"] if pa else "",
                "amarillas_pool_visita": pa["yellow_away"] if pa else "",
                "rojas_pool": pa["red"] if pa else "",
                "faltas_pool": round(pa["fouls"] / pa["fouls_n"], 2) if pa and pa["fouls_n"] else "",
                "goles_pool": round(pa["goals"] / pa["goals_n"], 2) if pa and pa["goals_n"] else "",
                "penaltis_pool": pa["pen"] if pa else "",
                "amarillas_pool_1h": pa["yellow_1h"] if pa else "",
                "amarillas_pool_2h": pa["yellow_2h"] if pa else "",
            })

        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OUT_FIELDS, delimiter=";")
            w.writeheader()
            w.writerows(rows)
        log.info("OK: %d árbitros, %d con carrera en worldreferee -> %s",
                 len(rows), encontrados, OUT.name)
        if not encontrados:
            sys.exit(3)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo árbitros")
        sys.exit(1)


if __name__ == "__main__":
    main()

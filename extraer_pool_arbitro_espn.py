"""Pool de árbitro por partido del Mundial 2026 desde eventos de ESPN.

Reconstruye, por partido FINALIZADO, lo que el backfill viejo sacaba de los
`incidents` de SofaScore: tarjetas por bando (casa/fuera) y por mitad (1ª/2ª),
rojas, penaltis, faltas y marcador. Lo añade a data/arbitro_pool.jsonl (dedup por
partido_id). Después, `extraer_arbitros.py --merge` lo fusiona en arbitros.csv
(columnas *_pool) SIN tocar la carrera (que se conserva del estado pre-bloqueo).

exit 0/3/1.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from extraer_designaciones_wiki import load_ids, resolve_name
from predictor.sources import base, espn, identity

DATA = Path(__file__).resolve().parent / "data"
POOL = DATA / "arbitro_pool.jsonl"
DATES = "20260611-20260719"

log = logging.getLogger("extraer_pool_arbitro_espn")


def _registro(event_id: str, s: dict, ids: dict) -> dict:
    h = espn.header(s)
    ts = espn.team_stats(s)
    ref = espn.referee(s)
    r = resolve_name(ref, ids) if ref else None
    yh = ya = y1 = y2 = red = pen = 0
    for e in espn.events(s):
        t = e["tipo"] or ""
        if t == "Yellow Card":
            if e["equipo"] == h["home"]:
                yh += 1
            elif e["equipo"] == h["away"]:
                ya += 1
            if e["mitad"] == 1:
                y1 += 1
            elif e["mitad"] == 2:
                y2 += 1
        if t == "Red Card" or "Red) Card" in t:
            red += 1
        if "Penalty" in t:
            pen += 1
    fouls = (ts["home"].get("fouls") or 0) + (ts["away"].get("fouls") or 0)
    return {
        "partido_id": str(event_id),
        "referee_id": int(r["sofa_id"]) if r and r.get("sofa_id") else None,
        "referee_name": r["nombre"] if r else ref,
        "home": identity.canonical(h["home"]) or h["home"],
        "away": identity.canonical(h["away"]) or h["away"],
        "yellow": yh + ya, "yellow_home": yh, "yellow_away": ya,
        "yellow_1h": y1, "yellow_2h": y2, "red": red, "penalties": pen,
        "goals_home": h["home_score"], "goals_away": h["away_score"],
        "fouls": fouls or None,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        ids = load_ids()
        eventos = [e for e in espn.scoreboard(dates=DATES) if e["finalizado"]]
        if not eventos:
            log.warning("ESPN: 0 partidos finalizados")
            sys.exit(3)

        nuevos = {}
        for ev in eventos:
            rec = _registro(ev["id"], espn.summary(ev["id"], cache=True), ids)
            nuevos[str(ev["id"])] = rec

        # Append con dedup: conserva el pool histórico, reemplaza los del Mundial.
        existentes = []
        if POOL.exists():
            for line in POOL.read_text(encoding="utf-8").splitlines():
                if line.strip() and str(json.loads(line)["partido_id"]) not in nuevos:
                    existentes.append(line)
        with open(POOL, "w", encoding="utf-8") as f:
            for line in existentes:
                f.write(line + "\n")
            for rec in nuevos.values():
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        sin_ref = sum(1 for r in nuevos.values() if not r["referee_id"])
        log.info("%d partidos al pool de árbitro (+%d históricos), %d sin id de árbitro",
                 len(nuevos), len(existentes), sin_ref)
    except base.FetchError as e:
        log.error("ESPN no disponible: %s", e)
        sys.exit(3)
    except Exception:  # noqa: BLE001
        log.exception("fallo reconstruyendo pool de árbitro")
        sys.exit(1)


if __name__ == "__main__":
    main()

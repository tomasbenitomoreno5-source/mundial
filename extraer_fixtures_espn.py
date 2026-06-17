"""Cruces de eliminatoria del Mundial 2026 desde ESPN -> partidos_a_predecir.csv.

Cuando una eliminatoria queda decidida (ambos equipos reales, no "Group A Winner"),
la añade a partidos_a_predecir (fase=eliminatoria) y a calendario.csv. El resto del
pipeline (predecir, resultados, designaciones) la coge por par de equipos canónico.

Idempotente: dedup por PAR canónico — un cruce de eliminatoria es siempre entre
equipos de grupos distintos, así que su par nunca coincide con un partido de grupos
(única excepción: una final entre dos equipos del mismo grupo, rarísima; si pasara
se añadiría a mano). Mientras la fase de grupos no acabe, los cruces tienen equipos
sin decidir -> no añade nada.

El HORARIO del cron lo cubre calendario_completo.csv (fechas de los 104 ya fijadas).
exit 0/3/1.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import sys
import unicodedata
from pathlib import Path

from predictor.sources import base, espn, identity

DATA = Path(__file__).resolve().parent / "data"
PRED = DATA / "partidos_a_predecir.csv"
CAL = DATA / "calendario.csv"
DATES = "20260611-20260719"
PRED_FIELDS = ["partido_id", "fecha", "equipo_a", "equipo_b", "fase"]
CAL_FIELDS = ["partido_id", "sofa_event_id", "kickoff", "sofa", "referee_id", "referee_name"]

log = logging.getLogger("extraer_fixtures_espn")


def _code3(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    letras = [c for c in s.upper() if c.isalpha()]
    return "".join(letras[:3]) or "XXX"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        pred = list(csv.DictReader(open(PRED, encoding="utf-8-sig"), delimiter=";"))
        # pares ya presentes (grupos + eliminatorias añadidas antes) y partido_ids en uso
        existentes = set()
        pids = set()
        for r in pred:
            pids.add(r["partido_id"])
            a, b = identity.canonical(r["equipo_a"]), identity.canonical(r["equipo_b"])
            if a and b:
                existentes.add(frozenset((a, b)))

        nuevos_pred, nuevos_cal = [], []
        for e in espn.scoreboard(dates=DATES):
            ca, cb = identity.canonical(e["home"]), identity.canonical(e["away"])
            if not ca or not cb:
                continue  # cruce aún sin decidir (placeholder tipo "Group A Winner")
            if frozenset((ca, cb)) in existentes:
                continue  # ya está (partido de grupos o añadido antes)
            iso = e.get("date") or ""
            t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None
            fecha = t.strftime("%Y-%m-%d") if t else ""
            base_id = f"{_code3(ca)}_{_code3(cb)}"
            pid = base_id if base_id not in pids else f"{base_id}_{e['id']}"
            pids.add(pid)
            existentes.add(frozenset((ca, cb)))
            nuevos_pred.append({"partido_id": pid, "fecha": fecha,
                                "equipo_a": ca, "equipo_b": cb, "fase": "eliminatoria"})
            nuevos_cal.append({"partido_id": pid, "sofa_event_id": e["id"],
                               "kickoff": int(t.timestamp()) if t else "",
                               "sofa": f"{ca} vs {cb}", "referee_id": "", "referee_name": ""})

        if nuevos_pred:
            with open(PRED, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=PRED_FIELDS, delimiter=";").writerows(nuevos_pred)
            with open(CAL, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=CAL_FIELDS, delimiter=";",
                               extrasaction="ignore").writerows(nuevos_cal)
        log.info("%d cruces de eliminatoria nuevos añadidos", len(nuevos_pred))
        for r in nuevos_pred:
            log.info("  + %s: %s vs %s (%s)", r["partido_id"], r["equipo_a"],
                     r["equipo_b"], r["fecha"])
    except base.FetchError as e:
        log.error("ESPN no disponible: %s", e)
        sys.exit(3)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo fixtures")
        sys.exit(1)


if __name__ == "__main__":
    main()

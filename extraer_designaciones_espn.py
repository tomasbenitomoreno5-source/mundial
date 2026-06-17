"""Designaciones de árbitro: ESPN (jugados, ground-truth) + Wikipedia (futuros).

Reemplaza la vía SofaScore. Para cada partido del calendario:
  - si ya está iniciado/jugado -> árbitro real de ESPN (gameInfo.officials).
  - si es futuro -> designación de Wikipedia (tabla de oficiales) por par canónico.
El nombre se normaliza al plantel (arbitro_ids) para fijar referee_name + referee_id.

Mismo esquema de calendario.csv. De momento escribe a data/calendario_espn.csv
(scratch). exit 0/3/1.
"""

from __future__ import annotations

import csv
import logging
import re
import sys
from pathlib import Path

import fuente_partidos
from extraer_designaciones_wiki import CAL_FIELDS, load_ids, resolve_name
from predictor.sources import espn, identity, wikipedia_refs

DATA = Path(__file__).resolve().parent / "data"
CAL = DATA / "calendario.csv"
OUT = CAL  # cutover: rellena el árbitro y reescribe el real
DATES = "20260611-20260719"

log = logging.getLogger("extraer_designaciones_espn")


def _par_canonico(sofa: str) -> frozenset | None:
    m = re.split(r"\s+vs\.?\s+", sofa or "", maxsplit=1)
    if len(m) != 2:
        return None
    a, b = identity.canonical(m[0]), identity.canonical(m[1])
    return frozenset((a, b)) if a and b else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        emp = {p["partido_id"]: p for p in fuente_partidos.emparejar(DATES)}
        wiki = wikipedia_refs.assignments()
        ids = load_ids()

        rows = list(csv.DictReader(open(CAL, encoding="utf-8-sig"), delimiter=";"))
        de_espn = de_wiki = sin_id = 0
        for r in rows:
            pid = r["partido_id"]
            p = emp.get(pid)
            nombre = fuente = None
            # 1) ESPN para partidos ya iniciados (árbitro real).
            if p and p.get("iniciado") and p.get("event_id"):
                ref = espn.referee(espn.summary(p["event_id"], cache=True))
                if ref:
                    nombre, fuente = ref, "espn"
            # 2) Wikipedia para el resto (futuros / no asignados en ESPN).
            if not nombre:
                par = _par_canonico(r.get("sofa", ""))
                w = wiki.get(par) if par else None
                if w:
                    nombre, fuente = w, "wiki"
            if not nombre:
                continue
            res = resolve_name(nombre, ids)
            r["referee_name"] = res["nombre"] if res else nombre
            r["referee_id"] = res["sofa_id"] if res else ""
            if not res:
                sin_id += 1
            de_espn += fuente == "espn"
            de_wiki += fuente == "wiki"

        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAL_FIELDS, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in CAL_FIELDS})

        con = sum(1 for r in rows if r.get("referee_name"))
        log.info("designaciones: %d/%d con árbitro, sin id en plantel %d -> %s",
                 con, len(rows), sin_id, OUT.name)
        # Degradado si este run no resolvió NINGUNA designación (fuentes caídas),
        # aunque el calendario de entrada ya trajera árbitros.
        if de_espn + de_wiki == 0:
            log.warning("0 designaciones resueltas (fuentes caídas?)")
            sys.exit(3)
        # Línea final concisa = detalle del mensaje.
        log.info("%d/%d con árbitro (espn %d, wiki %d)", con, len(rows), de_espn, de_wiki)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo designaciones")
        sys.exit(1)


if __name__ == "__main__":
    main()

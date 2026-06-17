"""Designaciones de árbitro desde Wikipedia (API) -> calendario.csv.

Reemplaza la vía SofaScore. Cruza la tabla de oficiales del Mundial 2026 con el
calendario por par de equipos canónico y rellena referee_name (+ referee_id, vía
arbitro_ids.csv). Mismo esquema de calendario.csv. Sin Playwright.

Casa el nombre de Wikipedia con el plantel (p.ej. "Amin Omar" -> "Amin Mohamed
Omar") con la misma heurística que el extractor viejo.

De momento escribe a data/calendario_wiki.csv (scratch). exit 0/3/1.
"""

from __future__ import annotations

import csv
import logging
import re
import sys
import unicodedata
from pathlib import Path

from predictor.sources import identity, wikipedia_refs

DATA = Path(__file__).resolve().parent / "data"
CAL = DATA / "calendario.csv"
IDS = DATA / "arbitro_ids.csv"
OUT = DATA / "calendario_wiki.csv"
CAL_FIELDS = ["partido_id", "sofa_event_id", "kickoff", "sofa", "referee_id", "referee_name"]

log = logging.getLogger("extraer_designaciones_wiki")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def load_ids() -> dict[str, dict]:
    out = {}
    if IDS.exists():
        with open(IDS, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r.get("sofa_id"):
                    out[norm(r["nombre"])] = r
    return out


def resolve_name(name: str, ids: dict[str, dict]) -> dict | None:
    """Empareja un nombre de árbitro (de Wikipedia) con el plantel (arbitro_ids).

    Exacto; si no, un conjunto de tokens (≥3 letras) es subconjunto del otro
    (p.ej. "Amin Omar" ⊆ "Amin Mohamed Omar"). NO casa por un token suelto
    compartido (evita "Amin Omar" -> "Omar Al Ali").
    """
    n = norm(name)
    if n in ids:
        return ids[n]
    toks = {t for t in n.split(" ") if len(t) >= 3}
    if not toks:
        return None
    for k, v in ids.items():
        ktoks = {t for t in k.split(" ") if len(t) >= 3}
        if ktoks and (toks <= ktoks or ktoks <= toks):
            return v
    return None


def _par_canonico(sofa: str) -> frozenset | None:
    m = re.split(r"\s+vs\.?\s+", sofa or "", maxsplit=1)
    if len(m) != 2:
        return None
    a, b = identity.canonical(m[0]), identity.canonical(m[1])
    return frozenset((a, b)) if a and b else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        asg = wikipedia_refs.assignments()
        if not asg:
            log.warning("Wikipedia: 0 designaciones parseadas")
            sys.exit(3)
        ids = load_ids()

        rows = list(csv.DictReader(open(CAL, encoding="utf-8-sig"), delimiter=";"))
        nuevos = sin_id = 0
        for r in rows:
            par = _par_canonico(r.get("sofa", ""))
            arb = asg.get(par) if par else None
            if not arb:
                continue
            ref = resolve_name(arb, ids)
            r["referee_name"] = ref["nombre"] if ref else arb
            r["referee_id"] = ref["sofa_id"] if ref else ""
            if not ref:
                sin_id += 1
            nuevos += 1

        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAL_FIELDS, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in CAL_FIELDS})

        con = sum(1 for r in rows if r.get("referee_name"))
        log.info("OK: %d/%d con árbitro (%d de wiki, %d sin id en plantel) -> %s",
                 con, len(rows), nuevos, sin_id, OUT.name)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo designaciones de Wikipedia")
        sys.exit(1)


if __name__ == "__main__":
    main()

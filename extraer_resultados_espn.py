"""Marcadores del Mundial 2026 desde ESPN -> data/resultados.csv.

Reemplaza la vía SofaScore (bloqueada). Cruza cada partido del proyecto con su
evento de ESPN (vía fuente_partidos) y escribe el marcador orientado a
equipo_a/equipo_b. Mismo esquema que el extractor viejo:
    partido_id;score_a;score_b;finished
Idempotente: reescribe el CSV con todos los partidos ya iniciados.

De momento escribe a data/resultados_espn.csv (scratch) para validar; el cutover
(escribir resultados.csv) es un cambio de una línea.

Códigos de salida: 0 = ok · 3 = degradado (0 finalizados / 0 emparejados) · 1 = fallo.
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import fuente_partidos

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "resultados.csv"  # cutover: reescribe el real (idempotente)
DATES = "20260611-20260719"

log = logging.getLogger("extraer_resultados_espn")


def _finalizados_previos() -> int:
    """Nº de partidos finalizados en la salida anterior (para detectar novedad)."""
    if not OUT.exists():
        return 0
    with open(OUT, encoding="utf-8") as f:
        return sum(1 for r in csv.DictReader(f, delimiter=";") if r.get("finished") == "1")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        partidos = fuente_partidos.emparejar(DATES)
        emparejados = [p for p in partidos if p["event_id"]]
        # Solo partidos ya iniciados (en juego o terminados); no los programados.
        con_marcador = [p for p in emparejados if p["iniciado"] and p["score_a"] is not None]
        fin_previos = _finalizados_previos()

        filas = [{
            "partido_id": p["partido_id"],
            "score_a": p["score_a"],
            "score_b": p["score_b"],
            "finished": 1 if p["finalizado"] else 0,
        } for p in con_marcador]

        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["partido_id", "score_a", "score_b", "finished"],
                               delimiter=";")
            w.writeheader()
            w.writerows(filas)

        fin = sum(1 for p in con_marcador if p["finalizado"])
        nuevos = max(0, fin - fin_previos)
        log.info("%d finalizados (+%d nuevos), %d con marcador", fin, nuevos, len(filas))
        if not emparejados or not filas:
            sys.exit(3)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo resultados ESPN")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Fecha/torneo de los partidos del Mundial 2026 desde ESPN -> partido_fechas.csv.

El modelo usa la fecha para la recencia y el backtest temporal. Para los partidos
nuevos del Mundial (keyados por event-id de ESPN, igual que stats_final) añade su
fecha/timestamp. MERGE seguro a nivel de texto: conserva el histórico byte a byte,
dedup por partido_id, añade los nuevos.

Esquema: partido_id;fecha;timestamp;torneo;categoria
exit 0/3/1.
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

from predictor.sources import base, espn

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "partido_fechas.csv"
DATES = "20260611-20260719"
HEADER = "partido_id;fecha;timestamp;torneo;categoria"

log = logging.getLogger("extraer_fechas_espn")


def _filas_nuevas() -> dict[str, str]:
    """{partido_id: linea_csv} de los partidos del Mundial con fecha en ESPN."""
    out = {}
    for e in espn.scoreboard(dates=DATES):
        iso = e.get("date")
        if not iso:
            continue
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        pid = str(e["id"])
        out[pid] = f"{pid};{t.strftime('%Y-%m-%d')};{int(t.timestamp())};FIFA World Cup;International"
    return out


def _merge(nuevas: dict[str, str]) -> tuple[int, int]:
    """Mete las filas nuevas en partido_fechas.csv conservando el histórico."""
    lineas = OUT.read_text(encoding="utf-8-sig").splitlines() if OUT.exists() else [HEADER]
    header, datos = lineas[0], lineas[1:]
    conservadas = [l for l in datos if l.strip() and l.split(";", 1)[0] not in nuevas]
    OUT.write_text("\n".join([header] + conservadas + list(nuevas.values())) + "\n",
                   encoding="utf-8-sig")
    return len(nuevas), len(conservadas)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        nuevas = _filas_nuevas()
        if not nuevas:
            log.warning("ESPN: 0 fechas de partidos del Mundial")
            sys.exit(3)
        n_new, n_hist = _merge(nuevas)
        log.info("%d fechas del Mundial (+%d históricas conservadas)", n_new, n_hist)
    except base.FetchError as e:
        log.error("ESPN no disponible: %s", e)
        sys.exit(3)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo fechas")
        sys.exit(1)


if __name__ == "__main__":
    main()

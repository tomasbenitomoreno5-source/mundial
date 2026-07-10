"""Backfill del xG/xA de jugador histórico en telemetria_full.csv desde FotMob.

La telemetría histórica se scrapeó de SofaScore, que NO traía xG/xA de jugador
(solo el 4% de filas lo tiene, las nuevas del Mundial vía FotMob). FotMob SÍ tiene
xG/xA de la mayoría de esos partidos pasados; este script los rellena:

  1. Para cada partido sin xG (con par de equipos + fecha), lo mapea a su id de
     FotMob por nombre normalizado + fecha (±1 día por zona horaria).
  2. Baja el detalle y, por jugador (match por nombre normalizado), rellena
     expectedGoals / expectedAssists SOLO en las celdas hoy vacías.
  3. Conserva el resto byte a byte (csv module, mismas columnas/orden).

Hace backup en data/telemetria_full.bak.csv. Idempotente: re-ejecutarlo solo
rellena lo que siga vacío. NO va en el cron (es un backfill puntual); el cron
sigue con extraer_plantillas_espn.py para los partidos nuevos.

Uso:  python backfill_xg_jugador.py
"""

from __future__ import annotations

import csv
import logging
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from predictor.sources import base, fotmob, identity

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "telemetria_full.csv"
BAK = DATA / "telemetria_full.bak.csv"
FECHAS = DATA / "partido_fechas.csv"
HDRS = {"Accept": "application/json"}
PAUSA = 0.3  # cortés con FotMob

log = logging.getLogger("backfill_xg_jugador")


def _par(a: str, b: str) -> frozenset:
    return frozenset((identity.norm(a or ""), identity.norm(b or "")))


def _matches_by_date(yyyymmdd: str) -> list[dict]:
    d = base.get_json(f"https://www.fotmob.com/api/data/matches?date={yyyymmdd}", headers=HDRS)
    out = []
    for lg in d.get("leagues", []):
        for m in lg.get("matches", []):
            out.append({"id": m.get("id"),
                        "home": (m.get("home") or {}).get("name"),
                        "away": (m.get("away") or {}).get("name")})
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rows = list(csv.DictReader(open(OUT, encoding="utf-8-sig"), delimiter=";"))
    cols = list(rows[0].keys())
    if "expectedGoals" not in cols:
        log.error("telemetria_full.csv no tiene columna expectedGoals"); sys.exit(1)
    tiene_xa = "expectedAssists" in cols

    fechas = {r["partido_id"]: r["fecha"]
              for r in csv.DictReader(open(FECHAS, encoding="utf-8-sig"), delimiter=";")}

    # Partidos a rellenar: alguna fila sin expectedGoals, con equipos y fecha.
    por_partido: dict[str, list[dict]] = {}
    for r in rows:
        por_partido.setdefault(r["partido_id"], []).append(r)
    pendientes = []
    for pid, frs in por_partido.items():
        falta = any(not (f.get("expectedGoals") or "").strip() for f in frs)
        home = next((f.get("home_team") for f in frs if f.get("home_team")), None)
        away = next((f.get("away_team") for f in frs if f.get("away_team")), None)
        fecha = fechas.get(pid)
        if falta and home and away and fecha:
            pendientes.append((pid, home, away, fecha[:10], frs))
    log.info("partidos a rellenar: %d", len(pendientes))

    cache_fecha: dict[str, list] = {}
    mapeados = filas_xg = filas_xa = sin_match = err = 0
    t0 = time.time()
    for i, (pid, home, away, fecha, frs) in enumerate(pendientes, 1):
        objetivo = _par(home, away)
        try:
            base_d = datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            sin_match += 1; continue
        fm = None
        for off in (0, -1, 1):
            ymd = (base_d + timedelta(days=off)).strftime("%Y%m%d")
            try:
                if ymd not in cache_fecha:
                    cache_fecha[ymd] = _matches_by_date(ymd); time.sleep(PAUSA)
            except base.FetchError as e:
                err += 1; log.warning("fecha %s: %s", ymd, e); continue
            fm = next((m for m in cache_fecha[ymd] if m["id"] and
                       _par(m["home"], m["away"]) == objetivo), None)
            if fm:
                break
        if not fm:
            sin_match += 1; continue
        mapeados += 1
        try:
            det = fotmob.match_details(fm["id"], cache=True); time.sleep(PAUSA)
            jugs = {identity.norm(j.get("name")): j for j in fotmob.parse_player_stats(det)}
        except base.FetchError as e:
            err += 1; log.warning("detalle %s: %s", fm["id"], e); continue
        for f in frs:
            j = jugs.get(identity.norm(f.get("jugador")))
            if not j:
                continue
            if not (f.get("expectedGoals") or "").strip() and j.get("expected_goals") is not None:
                f["expectedGoals"] = j["expected_goals"]; filas_xg += 1
            if tiene_xa and not (f.get("expectedAssists") or "").strip() \
                    and j.get("expected_assists") is not None:
                f["expectedAssists"] = j["expected_assists"]; filas_xa += 1
        if i % 100 == 0:
            log.info("  %d/%d procesados (%.0fs)", i, len(pendientes), time.time() - t0)

    # Backup + escritura (mismas columnas/orden; csv module conserva strings).
    if filas_xg or filas_xa:
        shutil.copy2(OUT, BAK)
        with open(OUT, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, delimiter=";")
            w.writeheader(); w.writerows(rows)

    dt = time.time() - t0
    log.info("=== backfill xG/xA jugador (%.0fs) ===", dt)
    log.info("  partidos mapeados a FotMob : %d/%d", mapeados, len(pendientes))
    log.info("  sin match                  : %d", sin_match)
    log.info("  errores FotMob             : %d", err)
    log.info("  filas con xG rellenado     : %d", filas_xg)
    log.info("  filas con xA rellenado     : %d", filas_xa)
    log.info("  backup en                  : %s", BAK if (filas_xg or filas_xa) else "(no escrito)")


if __name__ == "__main__":
    main()

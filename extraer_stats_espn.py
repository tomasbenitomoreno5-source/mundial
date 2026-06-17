"""Stats de equipo del Mundial 2026 desde ESPN (+ xG de xgscore) -> esquema de
stats_final.csv.

Sustituye a la vía SofaScore para las stats de equipo. Produce filas con EXACTAMENTE
las mismas columnas que data/stats_final.csv (sep ';', decimales con coma, NA para
lo que la fuente no da), una por equipo y partido FINALIZADO.

De momento escribe a un fichero scratch (data/stats_espn_nuevos.csv) para VALIDAR
el flujo antes de tocar el pool histórico. El cutover (append a stats_final) es un
paso posterior, una vez cerrada la capa de identidad de nombres de equipo.

Códigos de salida: 0 = ok · 3 = degradado (sin partidos / fuente vacía) · 1 = fallo.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from predictor.sources import base, espn, fotmob, identity

DATA = Path(__file__).resolve().parent / "data"
STATS = DATA / "stats_final.csv"
OUT = STATS  # cutover: append a stats_final.csv (merge seguro; ver _escribir)
# Ventana del torneo (Mundial 2026). El cron puede acotarla a los últimos días;
# para backfill se barre todo el rango (la caché evita re-bajar lo ya cogido).
DATES = "20260611-20260719"

log = logging.getLogger("extraer_stats_espn")


def _columnas() -> list[str]:
    """Orden exacto de columnas de stats_final.csv (esquema a respetar)."""
    return list(pd.read_csv(STATS, sep=";", encoding="utf-8-sig", nrows=0).columns)


STRING_COLS = {"partido_completo", "equipo_nombre", "tipo_equipo"}


def _fila(cols: list[str], stats: dict, partido_id, partido_completo,
          equipo, tipo, xg) -> dict:
    """Construye una fila en el esquema, None para lo no disponible."""
    fila = {c: None for c in cols}
    fila["partido_id"] = partido_id
    fila["partido_completo"] = partido_completo
    fila["equipo_nombre"] = equipo
    fila["tipo_equipo"] = tipo
    for metrica, valor in stats.items():
        if metrica in fila and valor is not None:
            fila[metrica] = valor
    if xg is not None:
        fila["expected_goals"] = xg
    return fila


def _field(col: str, val) -> str:
    """Formatea un campo como el histórico: NA sin comillas, decimales con coma,
    enteros sin decimal, solo las columnas de texto entrecomilladas."""
    if val is None or val == "":
        return "NA"
    if col in STRING_COLS:
        return f'"{val}"'
    if isinstance(val, float):
        return f"{val:.2f}".replace(".", ",") if not val.is_integer() else str(int(val))
    return str(val)


def _xg_fotmob(ch: str, ca: str, fm_idx: dict) -> tuple:
    """xG (home, away) de FotMob para el par canónico (ch=home, ca=away)."""
    mid = fm_idx.get(frozenset((ch, ca)))
    if not mid:
        return None, None
    try:
        txg = fotmob.team_xg(fotmob.match_details(mid, cache=True))
    except base.FetchError:
        return None, None
    if not txg:
        return None, None
    # Orientar el xG de FotMob (su home/away) a nuestro ch/ca.
    if identity.canonical(txg["home_team"]) == ch:
        return txg["home_xg"], txg["away_xg"]
    return txg["away_xg"], txg["home_xg"]


def _escribir(cols: list[str], filas: list[dict]) -> None:
    """MERGE seguro en stats_final.csv: conserva el histórico byte a byte, dedup
    por partido_id (re-runs) y añade las filas nuevas en formato byte-compatible."""
    nuevos_pid = {str(f["partido_id"]) for f in filas}
    if OUT.exists():
        existentes = OUT.read_text(encoding="utf-8").splitlines()
        header = existentes[0]
        conservadas = [l for l in existentes[1:]
                       if l.strip() and l.split(";", 1)[0] not in nuevos_pid]
    else:
        header = ";".join(f'"{c}"' for c in cols)
        conservadas = []
    nuevas = [";".join(_field(c, fila.get(c)) for c in cols) for fila in filas]
    OUT.write_text("\n".join([header] + conservadas + nuevas) + "\n", encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        cols = _columnas()
        eventos = [e for e in espn.scoreboard(dates=DATES) if e["finalizado"]]
        if not eventos:
            log.warning("ESPN: 0 partidos finalizados en el scoreboard")
            sys.exit(3)

        # Índice matchId de FotMob por par canónico (fuente de xG fiable, JSON).
        fuente_xg_ok = True
        try:
            fm_idx = {}
            for m in fotmob.league_matches(77):
                a, b = identity.canonical(m["home"]), identity.canonical(m["away"])
                if a and b and m.get("id"):
                    fm_idx[frozenset((a, b))] = m["id"]
            if not fm_idx:
                fuente_xg_ok = False
        except base.FetchError as e:
            log.warning("FotMob liga 77 no disponible (%s); xG quedará NA", e)
            fm_idx = {}
            fuente_xg_ok = False

        filas = []
        sin_xg = sin_canon = 0
        for ev in eventos:
            s = espn.summary(ev["id"], cache=True)
            h = espn.header(s)
            ts = espn.team_stats(s)
            # Posesión: el histórico la guarda como ENTERO y `_to_numeric` del
            # pipeline no parsea decimales con coma → redondear (si no, queda NaN).
            for lado in ("home", "away"):
                bp = ts[lado].get("ball_possession")
                if bp is not None:
                    ts[lado]["ball_possession"] = round(bp)
            ch, ca = identity.canonical(h["home"]), identity.canonical(h["away"])
            if not ch or not ca:
                log.warning("equipo sin canónico: %r / %r (partido %s)",
                            h["home"], h["away"], ev["id"])
                sin_canon += 1
                continue
            comp = f"{ch} vs {ca}"
            xg_h, xg_a = _xg_fotmob(ch, ca, fm_idx)
            if xg_h is None:
                sin_xg += 1
            filas.append(_fila(cols, ts["home"], ev["id"], comp, ch, "home", xg_h))
            filas.append(_fila(cols, ts["away"], ev["id"], comp, ca, "away", xg_a))

        _escribir(cols, filas)
        n_match = len(filas) // 2
        # Detalle completo al log.
        log.info("stats: %d partidos, %d filas, sin xG %d, sin canónico %d -> %s",
                 n_match, len(filas), sin_xg, sin_canon, OUT.name)
        # Equipo sin mapear = CRÍTICO (pérdida real de dato del modelo).
        if sin_canon:
            log.error("%d equipos sin canónico (pérdida de dato)", sin_canon)
            sys.exit(3)
        # Fuente de xG CAÍDA = degradado (⚠️): aunque el modelo no use xG aún,
        # conviene enterarse de que xgscore dejó de responder/parsear.
        if not fuente_xg_ok:
            log.warning("FotMob (fuente de xG) caída: sin xG este run")
            sys.exit(3)
        # Línea final concisa = detalle del mensaje (xG es best-effort).
        log.info("%d partidos · xG en %d/%d", n_match, n_match - sin_xg, n_match)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo stats ESPN")
        sys.exit(1)


if __name__ == "__main__":
    main()

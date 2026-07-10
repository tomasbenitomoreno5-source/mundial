"""Telemetría de jugador del Mundial 2026 desde FotMob -> telemetria_full.csv.

Por cada partido finalizado de la liga 77 (Mundial) baja matchDetails de FotMob y
escribe una fila por jugador con su telemetría (rating, pases, duelos, tackles,
toques, recuperaciones, xG de jugador, ...). MERGE seguro: conserva el histórico
byte a byte, dedup por partido_id, añade los nuevos.

⚠️ FRÁGIL: FotMob puede amurallar su API (ver fotmob.py). Si cae, este paso sale
degradado (exit 3) pero no rompe el resto. El modelo de jugador está parqueado, así
que esto deja el dato listo (incluido el xG de jugador) para cuando se reactive.

Esquema = el de telemetria_full.csv (sep ';', decimal '.'). exit 0/3/1.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from predictor.sources import base, fotmob, identity

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "telemetria_full.csv"
META = ("partido_id", "partido_completo", "jugador", "home_team", "away_team")

# columna de telemetria_full  <-  campo de fotmob.parse_player_stats
_MAP = {
    "rating": "rating", "minutesPlayed": "minutesPlayed", "goals": "goals",
    "goalAssist": "goalAssist", "totalShots": "totalShots",
    "onTargetScoringAttempt": "onTargetScoringAttempt", "totalPass": "totalPass",
    "accuratePass": "accuratePass", "totalLongBalls": "totalLongBalls",
    "aerialWon": "aerialWon", "aerialLost": "aerialLost", "duelWon": "duelWon",
    "duelLost": "duelLost", "ballRecovery": "ballRecovery", "wasFouled": "wasFouled",
    "touches": "touches", "totalClearance": "totalClearance", "totalTackle": "totalTackle",
    "fouls": "fouls", "possessionLostCtrl": "possessionLostCtrl",
    "interceptionWon": "interceptions", "wonContest": "dribbles",
    "expectedGoals": "expected_goals", "expectedAssists": "expected_assists",
}

log = logging.getLogger("extraer_plantillas_espn")


def _cols() -> list[str]:
    return OUT.read_text(encoding="utf-8-sig").splitlines()[0].split(";")


def _fila(cols: list[str], pid, comp, home, away, p: dict) -> str:
    d = dict.fromkeys(cols, "")
    d["partido_id"], d["partido_completo"], d["jugador"] = pid, comp, p.get("name", "")
    d["home_team"], d["away_team"] = home, away
    for tel_col, fm_key in _MAP.items():
        if tel_col in d and p.get(fm_key) is not None:
            d[tel_col] = p[fm_key]
    return ";".join(str(d[c]) for c in cols)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        cols = _cols()
        partidos = [m for m in fotmob.league_matches(77) if m["finalizado"] and m.get("id")]
        if not partidos:
            log.warning("FotMob liga 77: 0 partidos finalizados")
            sys.exit(3)

        nuevas, pids, sin_jug = [], set(), 0
        for m in partidos:
            ch, ca = identity.canonical(m["home"]), identity.canonical(m["away"])
            if not ch or not ca:
                continue
            try:
                det = fotmob.match_details(m["id"], cache=True)
            except base.FetchError:
                continue
            jug = fotmob.parse_player_stats(det)
            if not jug:
                sin_jug += 1
                continue
            pid = str(m["id"])
            pids.add(pid)
            comp = f"{ch} vs {ca}"
            for p in jug:
                nuevas.append(_fila(cols, pid, comp, ch, ca, p))

        if not nuevas:
            log.warning("0 jugadores extraídos (¿FotMob amurallado?)")
            sys.exit(3)

        # MERGE: conserva histórico, dedup por partido_id, añade nuevos.
        existentes = OUT.read_text(encoding="utf-8").splitlines()
        header = existentes[0]
        conservadas = [l for l in existentes[1:]
                       if l.strip() and l.split(";", 1)[0] not in pids]
        OUT.write_text("\n".join([header] + conservadas + nuevas) + "\n", encoding="utf-8")
        log.info("%d partidos, %d filas jugador (+%d históricas), %d sin telemetría",
                 len(pids), len(nuevas), len(conservadas), sin_jug)
    except base.FetchError as e:
        log.error("FotMob no disponible: %s", e)
        sys.exit(3)
    except Exception:  # noqa: BLE001
        log.exception("fallo extrayendo telemetría de jugador")
        sys.exit(1)


if __name__ == "__main__":
    main()

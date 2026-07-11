"""Cliente FotMob — telemetría RICA de jugador del Mundial 2026.

Usa el endpoint interno que hoy NO exige token:
    https://www.fotmob.com/api/data/matchDetails?matchId={id}

⚠️ FRÁGIL: FotMob ya amuralló el endpoint hermano `/api/matchDetails` con el
header firmado `x-fm-req`; pueden hacer lo mismo a `/api/data/...`. Por eso este
cliente queda ACOTADO a la telemetría de jugador (modelo parqueado): si cae, el
backbone (ESPN) sigue. Fallback documentado: generar `x-fm-req` local
(ver `@max-xoo/fotmob`) + IP residencial. Liga del Mundial en FotMob = id 77.

Los nombres de salida por jugador son los de SofaScore (rating, totalPass,
accuratePass, duelWon, ...) para encajar en el esquema de telemetría existente.
"""

from __future__ import annotations

from typing import Any

from . import base

API = "https://www.fotmob.com/api/data"
_HEADERS = {"Accept": "application/json"}

# key de FotMob -> (campo SofaScore destino, ¿usar 'total' en vez de 'value'?)
_MAP = {
    "rating_title": ("rating", False),
    "minutes_played": ("minutesPlayed", False),
    "goals": ("goals", False),
    "assists": ("goalAssist", False),
    "total_shots": ("totalShots", False),
    "ShotsOnTarget": ("onTargetScoringAttempt", False),
    "accurate_passes": ("accuratePass", False),     # total -> totalPass (aparte)
    "long_balls_accurate": ("totalLongBalls", True),  # intentados = total
    "duel_won": ("duelWon", False),
    "duel_lost": ("duelLost", False),
    "recoveries": ("ballRecovery", False),
    "was_fouled": ("wasFouled", False),
    "touches": ("touches", False),
    "clearances": ("totalClearance", False),
    "matchstats.headers.tackles": ("totalTackle", False),
    "fouls": ("fouls", False),
    "dispossessed": ("possessionLostCtrl", False),
    "interceptions": ("interceptions", False),
    "expected_goals": ("expected_goals", False),
    "expected_assists": ("expected_assists", False),
    "dribbles_succeeded": ("dribbles", False),
}


def _details_terminado(d: dict) -> bool:
    return bool(d.get("general", {}).get("finished"))


def match_details(match_id: int | str, *, cache: bool = False) -> dict:
    """JSON crudo de un partido. La caché solo persiste partidos TERMINADOS
    (uno en vivo dejaría xG/telemetría congelados a mitad de partido)."""
    return base.get_json(f"{API}/matchDetails?matchId={match_id}",
                         headers=_HEADERS, cache=cache,
                         cacheable=_details_terminado)


def league_matches(league_id: int = 77) -> list[dict]:
    """Partidos de la liga (id 77 = Mundial): para mapear partido -> matchId."""
    data = base.get_json(f"{API}/leagues?id={league_id}", headers=_HEADERS)
    out = []
    for m in data.get("fixtures", {}).get("allMatches", []) or []:
        out.append({
            "id": m.get("id"),
            "home": m.get("home", {}).get("name"),
            "away": m.get("away", {}).get("name"),
            "utc": m.get("status", {}).get("utcTime"),
            "finalizado": bool(m.get("status", {}).get("finished")),
        })
    return out


def _flatten(stats_groups: list) -> dict[str, dict]:
    """Aplana los grupos de stats a {key: stat_obj} (value/total)."""
    flat = {}
    for g in stats_groups or []:
        for _label, obj in g.get("stats", {}).items():
            k = obj.get("key")
            if k and k not in flat:
                flat[k] = obj.get("stat", {})
    return flat


def parse_player_stats(details: dict) -> list[dict]:
    """Telemetría por jugador (campos SofaScore). Una fila por jugador."""
    out = []
    for _pid, pl in (details.get("content", {}).get("playerStats", {}) or {}).items():
        if not isinstance(pl, dict):
            continue
        flat = _flatten(pl.get("stats"))
        fila: dict[str, Any] = {
            "player_id": pl.get("id"),
            "opta_id": pl.get("optaId"),
            "name": pl.get("name"),
            "team_id": pl.get("teamId"),
            "team": pl.get("teamName"),
            "position": pl.get("usualPosition"),
            "shirt": pl.get("shirtNumber"),
            "is_gk": pl.get("isGoalkeeper"),
        }
        for fm_key, (campo, usar_total) in _MAP.items():
            st = flat.get(fm_key)
            if not st:
                continue
            fila[campo] = st.get("total") if usar_total else st.get("value")
        # totalPass = total del par accurate_passes
        ap = flat.get("accurate_passes")
        if ap:
            fila["totalPass"] = ap.get("total")
        # aéreos: SofaScore separa ganados/perdidos; FotMob da won (value/total)
        aw = flat.get("aerials_won")
        if aw and aw.get("total") is not None:
            fila["aerialWon"] = aw.get("value")
            fila["aerialLost"] = max(0, (aw.get("total") or 0) - (aw.get("value") or 0))
        out.append(fila)
    return out


def team_xg(details: dict) -> dict | None:
    """xG de equipo del partido: {home_team, away_team, home_xg, away_xg}.

    Más fiable que xgscore (JSON limpio). Busca el stat `expected_goals` (lista
    [valor_home, valor_away]) en content.stats.
    """
    found = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("key") == "expected_goals" and isinstance(n.get("stats"), list) \
                    and len(n["stats"]) == 2 and not found:
                found.extend(n["stats"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(details.get("content", {}).get("stats", {}))
    if len(found) != 2:
        return None
    g = general(details)
    try:
        return {"home_team": g["home"], "away_team": g["away"],
                "home_xg": float(found[0]), "away_xg": float(found[1])}
    except (TypeError, ValueError):
        return None


def general(details: dict) -> dict:
    """Equipos y estado del partido."""
    g = details.get("general", {})
    return {
        "home": g.get("homeTeam", {}).get("name"),
        "away": g.get("awayTeam", {}).get("name"),
        "home_id": g.get("homeTeam", {}).get("id"),
        "away_id": g.get("awayTeam", {}).get("id"),
        "finalizado": bool(g.get("finished")),
    }

"""Cliente ESPN (hidden API) — backbone estable del pipeline del Mundial 2026.

Endpoint público, sin key ni token, sin bloqueo:
    https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/...

Aporta: calendario, resultados, stats de equipo, eventos (goles/tarjetas con
minuto+mitad → reparto 1ª/2ª parte), alineaciones y árbitro.
NO aporta: xG de equipo (su `expectedGoals` es de portería, no el xG de ataque
→ ese dato viene de xgscore), ni big_chances/duelos/regates a nivel equipo.

Los nombres de campo de salida son los de `config.METRICAS_EQUIPO` para que los
extractores escriban directamente en el mismo esquema CSV que SofaScore.
"""

from __future__ import annotations

import re
from typing import Any

from . import base

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"

# ESPN (boxscore.teams[].statistics 'name') -> métrica del proyecto.
_MAP_EQUIPO = {
    "foulsCommitted": "fouls",
    "yellowCards": "yellow_cards",
    "redCards": "red_cards",
    "offsides": "offsides",
    "wonCorners": "corner_kicks",
    "saves": "goalkeeper_saves",
    "possessionPct": "ball_possession",
    "totalShots": "total_shots",
    "shotsOnTarget": "shots_on_target",
    "blockedShots": "blocked_shots",
    "accuratePasses": "accurate_passes",
    "totalPasses": "passes",
    "totalCrosses": "crosses",
    "totalLongBalls": "long_balls",
    "effectiveTackles": "tackles",
    "totalTackles": "total_tackles",
    "interceptions": "interceptions",
    "totalClearance": "clearances",
}


def _num(s: Any) -> float | int | None:
    if s is None:
        return None
    try:
        # ESPN usa formato US: '%' y coma de millares ('1,234'). Quitar ambos.
        f = float(str(s).replace("%", "").replace(",", ""))
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def scoreboard(dates: str | None = None) -> list[dict]:
    """Lista de eventos del Mundial. `dates`='YYYYMMDD' o 'YYYYMMDD-YYYYMMDD'."""
    url = f"{BASE}/scoreboard" + (f"?dates={dates}" if dates else "")
    data = base.get_json(url)
    out = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        st = e["status"]["type"]
        cs = {c["homeAway"]: c for c in comp["competitors"]}
        out.append({
            "id": e["id"],
            "name": e.get("name"),
            "date": e.get("date"),
            "estado": st.get("name"),
            "state": st.get("state"),  # "pre" | "in" | "post"
            "finalizado": bool(st.get("completed")),
            "iniciado": st.get("state") in ("in", "post"),
            "home": cs.get("home", {}).get("team", {}).get("displayName"),
            "away": cs.get("away", {}).get("team", {}).get("displayName"),
            "home_score": _num(cs.get("home", {}).get("score")),
            "away_score": _num(cs.get("away", {}).get("score")),
        })
    return out


def summary(event_id: int | str, *, cache: bool = False) -> dict:
    """JSON crudo del resumen de un partido. cache=True solo si ya terminó."""
    return base.get_json(f"{BASE}/summary?event={event_id}", cache=cache)


def header(summary_obj: dict) -> dict:
    """Marcador, fecha, estado y equipos (con id ESPN)."""
    comp = summary_obj["header"]["competitions"][0]
    cs = {c["homeAway"]: c for c in comp["competitors"]}
    return {
        "fecha": comp.get("date"),
        "estado": comp["status"]["type"]["name"],
        "finalizado": bool(comp["status"]["type"].get("completed")),
        "home_id": cs.get("home", {}).get("team", {}).get("id"),
        "away_id": cs.get("away", {}).get("team", {}).get("id"),
        "home": cs.get("home", {}).get("team", {}).get("displayName"),
        "away": cs.get("away", {}).get("team", {}).get("displayName"),
        "home_score": _num(cs.get("home", {}).get("score")),
        "away_score": _num(cs.get("away", {}).get("score")),
    }


def team_stats(summary_obj: dict) -> dict:
    """Stats de equipo por bando: {'home': {metrica: valor}, 'away': {...}}.

    Nombres de métrica = config.METRICAS_EQUIPO. Faltan (vacías) las que ESPN no
    da; `goles` sale del marcador; `shots_off_target` se deriva.
    """
    h = header(summary_obj)
    id2lado = {h["home_id"]: "home", h["away_id"]: "away"}
    res = {"home": {}, "away": {}}
    for t in summary_obj.get("boxscore", {}).get("teams", []):
        lado = id2lado.get(t.get("team", {}).get("id"))
        if not lado:
            continue
        d = res[lado]
        for st in t.get("statistics", []):
            metrica = _MAP_EQUIPO.get(st.get("name"))
            if metrica:
                d[metrica] = _num(st.get("displayValue"))
        # off target = totales - a puerta - bloqueados (si los 3 están)
        ts, sot, bl = d.get("total_shots"), d.get("shots_on_target"), d.get("blocked_shots")
        if None not in (ts, sot, bl):
            d["shots_off_target"] = max(0, ts - sot - bl)
    res["home"]["goles"] = h["home_score"]
    res["away"]["goles"] = h["away_score"]
    return res


def events(summary_obj: dict) -> list[dict]:
    """Eventos clave (goles/tarjetas...) con minuto, mitad y equipo.

    Permite reconstruir reparto 1ª/2ª parte y el pool del árbitro (tarjetas por
    bando y por mitad), igual que SofaScore hacía con `incidents`.
    """
    out = []
    for ke in summary_obj.get("keyEvents", []):
        clock = ke.get("clock", {}).get("displayValue") or ""
        m = re.search(r"(\d+)", clock)
        out.append({
            "tipo": ke.get("type", {}).get("text"),
            "minuto": int(m.group(1)) if m else None,
            "mitad": ke.get("period", {}).get("number"),
            "equipo": (ke.get("team") or {}).get("displayName"),
            "jugadores": [a.get("displayName") for a in ke.get("athletesInvolved", [])],
        })
    return out


def referee(summary_obj: dict) -> str | None:
    """Nombre del árbitro principal."""
    for o in summary_obj.get("gameInfo", {}).get("officials", []):
        if o.get("position", {}).get("displayName") == "Referee":
            return o.get("displayName")
    return None

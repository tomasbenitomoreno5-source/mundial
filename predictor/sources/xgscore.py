"""Cliente xgscore.io — xG de equipo por partido del Mundial 2026.

ESPN no expone xG de equipo (su `expectedGoals` es de portería) y API-Football
Free no da 2026. xgscore publica el xG por partido en el HTML (estado SSR), gratis
y sin bloqueo. Lo usamos como FUENTE de xG; FotMob sirve de cross-check.

Devuelve, por partido: equipos, goles y xG de cada lado. El cruce con el partido
de ESPN/FotMob se hace por nombres de equipo (capa de identidad, Fase 2).
"""

from __future__ import annotations

import re
import time

from . import base

URL = "https://xgscore.io/xg-statistics/world-cup/2026"

# match object: ...goals{h,a}, xG{h,a}, teams{h:{...name},a:{...name}}
_RE = re.compile(
    r'"goals":\{"h":(\d+),"a":(\d+)\},'
    r'"xG":\{"h":([\d.]+),"a":([\d.]+)\},'
    r'"teams":\{"h":\{[^{}]*?"name":"([^"]+)"[^{}]*?\},'
    r'"a":\{[^{}]*?"name":"([^"]+)"'
)


def _parse(html: str) -> list[dict]:
    vistos = set()
    out = []
    for gh, ga, xh, xa, home, away in _RE.findall(html):
        clave = (home, away)
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append({
            "home": home, "away": away,
            "goals_home": int(gh), "goals_away": int(ga),
            "xg_home": float(xh), "xg_away": float(xa),
        })
    return out


def world_cup_xg(reintentos: int = 3) -> list[dict]:
    """xG por partido del Mundial 2026. Dedup por (home, away).

    xgscore es intermitente: a veces sirve una página "cáscara" sin la isla de
    datos. Como la página completa está casi siempre disponible, se reintenta si
    el parseo sale vacío. Devuelve [] solo si tras los reintentos sigue sin datos
    (→ el extractor lo marca ⚠️ fuente caída).
    """
    for intento in range(1, reintentos + 1):
        out = _parse(base.get_text(URL))
        if out:
            return out
        if intento < reintentos:
            time.sleep(2)
    return []

"""Designaciones de árbitro del Mundial 2026 desde la API de Wikipedia.

Fuente estructurada y gratuita (MediaWiki `action=parse`), más robusta que
scrapear el HTML. Parsea la tabla de "2026 FIFA World Cup officials": cada fila
de árbitro lista los partidos asignados como wikilinks `...#Home vs Away|...`.

`assignments()` devuelve {frozenset((canónico_home, canónico_away)): árbitro}.
El cruce con el calendario se hace por par de equipos canónico (no orientado).
"""

from __future__ import annotations

import re

from . import base, identity

API = ("https://en.wikipedia.org/w/api.php?action=parse"
       "&page=2026_FIFA_World_Cup_officials&prop=wikitext&format=json")

# Partido dentro de la celda "Matches assigned": ...#Home vs Away|...
_RE_MATCH = re.compile(r"#([^#\]|]+?)\s+vs\s+([^#\]|]+?)\|")
# Enlaces que NO son personas (confederación, federación, grupo...).
_NO_PERSONA = re.compile(r"Football|Confederation|Association|Federation|Group|2026 FIFA|UEFA|CONMEBOL|CONCACAF",
                         re.IGNORECASE)
# Nombre del árbitro: primer [[Persona]] sin pipe ni paréntesis de país.
_RE_LINK = re.compile(r"\[\[([^\]|#]+?)\]\]")


def _wikitext() -> str:
    data = base.get_json(API)
    return data["parse"]["wikitext"]["*"]


def _arbitro_de_fila(fila: str) -> str | None:
    for nombre in _RE_LINK.findall(fila):
        if not _NO_PERSONA.search(nombre):
            return nombre.strip()
    return None


def assignments() -> dict[frozenset, str]:
    """{frozenset(par canónico): árbitro PRINCIPAL} de la tabla de oficiales.

    Solo la sección de árbitros principales (no la de VAR) y solo la columna
    "Matches assigned" (penúltima celda; la última es "Fourth official"), para no
    confundir al árbitro con el 4º árbitro o el VAR del mismo partido.
    """
    wt = _wikitext()
    # Cortar antes de la sección de VAR (esos también listan partidos).
    seccion = wt.split("Video assistant referees")[0]
    out: dict[frozenset, str] = {}
    for fila in seccion.split("\n|-"):
        celdas = fila.split("\n|")
        if len(celdas) < 2:
            continue
        # "Matches assigned" = penúltima celda; "Fourth official" = última.
        matches = _RE_MATCH.findall(celdas[-2])
        if not matches:
            continue
        arbitro = _arbitro_de_fila(fila)
        if not arbitro:
            continue
        for home, away in matches:
            ch, ca = identity.canonical(home), identity.canonical(away)
            if ch and ca:
                out[frozenset((ch, ca))] = arbitro
    return out

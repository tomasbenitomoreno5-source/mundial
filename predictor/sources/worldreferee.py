"""Cliente worldreferee.com — stats de CARRERA del árbitro (gratis, sin Cloudflare).

Reemplaza el perfil de SofaScore (referee/{id}). Vía:
  1. API de búsqueda: /home/searchReferees?q=Nombre -> [{name, country, url}].
     (Imprescindible: da la URL canónica con guion BAJO; la de guiones devuelve
     una plantilla vacía con datos placeholder.)
  2. Perfil HTML en esa URL: stats de carrera (partidos, amarillas, rojas, 2ª
     amarillas, penaltis) como `>VALOR</span> <span class="wr-ref-stat-label">LABEL</span>`.

NOTA: los totales NO coinciden con SofaScore (cobertura distinta); lo que importa
al modelo es la TASA (amarillas/partido), que sí es comparable.
"""

from __future__ import annotations

import re
import urllib.parse

from . import base, identity

SEARCH = "https://worldreferee.com/home/searchReferees?q={}"


def _stat(html: str, label: str) -> float | None:
    m = re.search(r'>([0-9.]+)</span>\s*<span class="wr-ref-stat-label">' + re.escape(label),
                  html)
    return float(m.group(1)) if m else None


def search(name: str) -> list[dict]:
    return base.get_json(SEARCH.format(urllib.parse.quote(name)))


def best_match(name: str, pais: str | None = None) -> dict | None:
    """Mejor candidato: nombre normalizado exacto y, si se da, mismo país.

    Prueba el nombre completo y, si no hay resultados, un "Nombre Apellido"
    abreviado (p.ej. "César Arturo Ramos" -> "César Ramos").
    """
    toks = name.split()
    corto = f"{toks[0]} {toks[-1]}" if len(toks) > 2 else name
    res = []
    for q in dict.fromkeys([name, corto]):  # dedupe, en orden
        res = search(q)
        if res:
            break
    if not res:
        return None
    nn = identity.norm(name)
    # nombre exacto; si no, contención de tokens (≥3 letras) en cualquier sentido
    toks_n = {t for t in nn_tokens(name) if len(t) >= 3}
    exact = [r for r in res if identity.norm(r.get("name", "")) == nn]
    if not exact:
        exact = [r for r in res
                 if toks_n and (toks_n <= nn_tokens(r.get("name", ""))
                                or nn_tokens(r.get("name", "")) <= toks_n)]
    cand = exact or res
    if pais:
        pn = identity.norm(pais)
        cand = [r for r in cand if identity.norm(r.get("country", "")) == pn] or cand
    return cand[0]


def nn_tokens(name: str) -> set[str]:
    """Tokens normalizados (sin acentos) de un nombre."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return {t for t in s.lower().split() if t}


def career(name: str, pais: str | None = None) -> dict | None:
    """Stats de carrera del árbitro, o None si no se encuentra."""
    m = best_match(name, pais)
    if not m or not m.get("url"):
        return None
    html = base.get_text(m["url"])
    return {
        "url": m["url"],
        "matched_name": m.get("name"),
        "country": m.get("country"),
        "matches": _stat(html, "Matches"),
        "yellow": _stat(html, "Yellow Cards"),
        "red": _stat(html, "Red Cards"),
        "second_yellow": _stat(html, "2nd Yellow"),
        "penalties": _stat(html, "Penalties"),
    }

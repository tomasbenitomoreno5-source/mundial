"""Capa de identidad: nombres de equipo de cada fuente -> nombre CANÓNICO.

El canónico es el de `data/grupos_oficiales.csv` (48 selecciones), que es el que
usa el lado de predicción (fixtures, grupos). ESPN/xgscore/FotMob usan grafías
distintas para unos pocos países; aquí se reconcilian.

`canonical(name)` devuelve el nombre canónico o None si no se reconoce (p.ej.
placeholders de eliminatoria tipo "Group A Winner", "1A", "Winner QF 1"). Los
extractores solo procesan partidos finalizados (equipos reales), así que un None
ahí = mismatch real a corregir -> el extractor sale degradado (exit 3), nunca
inventa ni cruza mal en silencio.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from pathlib import Path

import pandas as pd

GRUPOS = Path(__file__).resolve().parents[2] / "data" / "grupos_oficiales.csv"

# alias (nombre normalizado de fuente) -> nombre canónico exacto
_ALIAS = {
    "capeverde": "Cabo Verde",
    "congodr": "DR Congo",
    "drcongo": "DR Congo",
    "ivorycoast": "Côte d'Ivoire",
    "unitedstates": "USA",
    "bosniaandherzegovina": "Bosnia & Herzegovina",
    "bosniaandherz": "Bosnia & Herzegovina",
    "czech": "Czechia",
    "czechrepublic": "Czechia",
    "saudia": "Saudi Arabia",
    "turkey": "Türkiye",
    "korearepublic": "South Korea",
    "iriran": "Iran",
    "iranislamicrepublic": "Iran",
}


def norm(s: str) -> str:
    """Quita acentos, pasa a minúsculas y deja solo alfanuméricos."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


@functools.lru_cache(maxsize=1)
def _canon_index() -> dict[str, str]:
    df = pd.read_csv(GRUPOS, sep=";", encoding="utf-8-sig")
    return {norm(n): n for n in df["equipo"].dropna().unique()}


def canonical(name: str | None) -> str | None:
    """Nombre canónico para `name`, o None si no se reconoce."""
    if not name:
        return None
    n = norm(name)
    idx = _canon_index()
    if n in idx:
        return idx[n]
    return _ALIAS.get(n)

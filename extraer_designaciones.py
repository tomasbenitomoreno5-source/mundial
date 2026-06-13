"""Designaciones de árbitro por partido del Mundial 2026.

El árbitro de cada partido se guarda en data/calendario.csv (columnas
referee_id;referee_name). La fuente es intercambiable; por prioridad:

  1. data/designaciones.csv  — override manual (event_id;referee_name). Sirve
     para cargar a mano lo que veas en cualquier sitio, y para SIMULAR una
     asignación en local.
  2. --wiki   — Wikipedia "2026 FIFA World Cup officials": árbitro por partido,
     cruzado por equipos. Se actualiza durante el torneo.
  3. --sofa   — SofaScore event/{id}.referee (respaldo gratis; hoy suele venir
     vacío hasta que lo ingieren).

Resuelve el nombre del árbitro a su sofa_id usando data/arbitro_ids.csv (lo
genera extraer_arbitros.py), para que la web pueda enlazar a la ficha.

Uso:
    python extraer_designaciones.py                 # manual + sofa (cron)
    python extraer_designaciones.py --wiki --sofa   # + Wikipedia (cron completo)
    python extraer_designaciones.py --wiki          # solo Wikipedia + manual
"""

import asyncio
import csv
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CAL = DATA / "calendario.csv"
IDS = DATA / "arbitro_ids.csv"
MANUAL = DATA / "designaciones.csv"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
API = "https://api.sofascore.com/api/v1"
WIKI = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_officials"

CAL_FIELDS = ["partido_id", "sofa_event_id", "kickoff", "sofa", "referee_id", "referee_name"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def load_ids() -> dict[str, dict]:
    """norm(nombre) -> {sofa_id, nombre}. También indexa por apellido suelto."""
    out = {}
    if not IDS.exists():
        return out
    with open(IDS, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r.get("sofa_id"):
                out[norm(r["nombre"])] = r
    return out


def resolve_name(name: str, ids: dict[str, dict]) -> dict | None:
    """Empareja un nombre de árbitro (de Wikipedia/manual) con el plantel."""
    n = norm(name)
    if n in ids:
        return ids[n]
    # contains en ambos sentidos (p.ej. "Hernández" vs "Alejandro Hernández Hernández")
    for k, v in ids.items():
        if n and (n in k or k in n):
            return v
    # por cualquier token distintivo compartido (≥4 letras), p.ej. el nombre web
    # "Facundo Raul Tello Figueroa" casa con "Facundo Tello" por "facundo"/"tello".
    toks = {t for t in n.split(" ") if len(t) >= 4}
    for k, v in ids.items():
        if toks & set(k.split(" ")):
            return v
    return None


def read_cal() -> list[dict]:
    with open(CAL, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    for r in rows:  # asegura las columnas nuevas
        r.setdefault("referee_id", "")
        r.setdefault("referee_name", "")
    return rows


def write_cal(rows: list[dict]):
    with open(CAL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAL_FIELDS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CAL_FIELDS})


def teams_of(row: dict) -> tuple[str, str]:
    """Equipos del partido a partir de la columna 'sofa' ('Home vs Away')."""
    s = row.get("sofa", "")
    m = re.split(r"\s+vs\.?\s+", s, maxsplit=1, flags=re.I)
    return (norm(m[0]), norm(m[1])) if len(m) == 2 else ("", "")


def apply_assignment(rows, ids, by_event=None, by_teams=None, label=""):
    """Rellena referee_* en las filas que aún no lo tengan. Devuelve nº aplicados."""
    n = 0
    for r in rows:
        if r.get("referee_id"):
            continue
        name = None
        if by_event:
            name = by_event.get(str(r.get("sofa_event_id")))
        if not name and by_teams:
            h, a = teams_of(r)
            name = by_teams.get((h, a)) or by_teams.get((a, h))
        if not name:
            continue
        ref = resolve_name(name, ids)
        # Si resuelve, usar el nombre CANÓNICO del plantel (evita nombres
        # truncados/largos del scrape, p.ej. "Slavko Vin" → "Slavko Vinčić").
        r["referee_name"] = ref["nombre"] if ref else name
        r["referee_id"] = ref["sofa_id"] if ref else ""
        if not ref:
            print(f"  ! '{name}' sin id en el plantel ({r.get('sofa')})")
        n += 1
    if label:
        print(f"  {label}: {n} asignaciones")
    return n


# --------------------------------------------------------------------------- #
# Fuentes
# --------------------------------------------------------------------------- #
def load_manual() -> dict[str, str]:
    if not MANUAL.exists():
        return {}
    with open(MANUAL, encoding="utf-8-sig") as f:
        return {
            str(r["sofa_event_id"]): r["referee_name"]
            for r in csv.DictReader(f, delimiter=";")
            if r.get("sofa_event_id") and r.get("referee_name")
        }


async def fetch_sofa_referees(get, rows) -> dict[str, str]:
    """event/{id}.referee para los partidos que aún no tienen árbitro."""
    out = {}
    pend = [r for r in rows if not r.get("referee_id") and r.get("sofa_event_id")]
    for r in pend:
        eid = r["sofa_event_id"]
        d = await get(f"{API}/event/{eid}")
        ref = (d or {}).get("event", {}).get("referee")
        if ref and ref.get("name"):
            out[str(eid)] = ref["name"]
            print(f"  · sofa {eid}: {ref['name']}")
        time.sleep(1.0)
    return out


async def fetch_wiki_referees(pg) -> dict[tuple[str, str], str]:
    """Extrae 'Home v Away ... Referee: Nombre' de la página de oficiales.

    Best-effort: la tabla/markup de Wikipedia cambia; se basa en el texto
    'Referee: <nombre>' que sigue a cada cruce. Devuelve {(home,away): nombre}.
    """
    d = await get_html(pg, WIKI)
    out = {}
    if not d:
        return out
    # Bloques tipo:  "Team A v Team B ... Referee: Name (Country)"
    pat = re.compile(
        r"([A-Z][A-Za-z .'\-]+?)\s+v\.?\s+([A-Z][A-Za-z .'\-]+?)[\s\S]{0,400}?Referee:\s*([A-Z][A-Za-z .'\-]+)",
    )
    for m in pat.finditer(d):
        home, away, ref = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        out[(norm(home), norm(away))] = ref
    print(f"  wiki: {len(out)} cruces con árbitro")
    return out


async def fetch_www_referees(pg, rows) -> dict[str, str]:
    """Árbitro desde la PÁGINA del partido en www.sofascore.com/event/{id}.

    El API (api.sofascore.com) suele estar rate-limitado (403), pero la web sí
    carga y muestra "Referee: Nombre" para los partidos ya designados/jugados.
    """
    out = {}
    pend = [r for r in rows if not r.get("referee_id") and r.get("sofa_event_id")]
    for r in pend:
        eid = str(r["sofa_event_id"])
        try:
            resp = await pg.goto(
                f"https://www.sofascore.com/event/{eid}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            if not resp or resp.status != 200:
                continue
            # Esperar a que hidrate el bloque de info (donde aparece "Referee").
            try:
                await pg.wait_for_function(
                    "() => /Referee/i.test(document.body.innerText)", timeout=8000
                )
            except Exception:
                pass
            txt = await pg.evaluate("() => document.body.innerText")
            m = re.search(r"Referee[:\s]*([A-Z][A-Za-zÀ-ÿ .'\-]+)", txt)
            if m:
                out[eid] = m.group(1).strip()
                print(f"  · www {eid}: {out[eid]}")
        except Exception:
            pass
        await asyncio.sleep(0.8)
    return out


async def make_get(pg):
    async def get(u):
        for _ in range(2):
            try:
                r = await pg.goto(u, wait_until="domcontentloaded", timeout=30000)
                if r and r.status == 200:
                    return json.loads(
                        await pg.evaluate(
                            "()=>document.querySelector('pre')?.innerText ?? document.body.innerText"
                        )
                    )
                return None
            except Exception:
                await asyncio.sleep(2)
        return None

    return get


async def get_html(pg, url):
    """Página HTML (Wikipedia): innerText plano (no JSON)."""
    try:
        r = await pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        if r and r.status == 200:
            return await pg.evaluate("()=>document.body.innerText")
    except Exception:
        return None
    return None


# --------------------------------------------------------------------------- #
async def main():
    use_wiki = "--wiki" in sys.argv
    use_sofa = "--sofa" in sys.argv  # API directo (suele estar 403)
    # Por defecto: web del partido (www), que sí está accesible.
    use_www = "--www" in sys.argv or (not use_wiki and not use_sofa)
    rows = read_cal()
    ids = load_ids()

    # 1) Override manual (siempre, máxima prioridad).
    manual = load_manual()
    if manual:
        apply_assignment(rows, ids, by_event=manual, label="manual")

    if use_wiki or use_sofa or use_www:
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True)
            pg = await (await b.new_context(user_agent=UA)).new_page()
            get = await make_get(pg)
            wiki = await fetch_wiki_referees(pg) if use_wiki else None
            if wiki:
                apply_assignment(rows, ids, by_teams=wiki, label="wiki")
            www = await fetch_www_referees(pg, rows) if use_www else None
            if www:
                apply_assignment(rows, ids, by_event=www, label="www")
            sofa = await fetch_sofa_referees(get, rows) if use_sofa else None
            if sofa:
                apply_assignment(rows, ids, by_event=sofa, label="sofa")
            await b.close()

    write_cal(rows)
    con = sum(1 for r in rows if r.get("referee_id") or r.get("referee_name"))
    print(f"OK: {con}/{len(rows)} partidos con árbitro -> calendario.csv")


if __name__ == "__main__":
    asyncio.run(main())

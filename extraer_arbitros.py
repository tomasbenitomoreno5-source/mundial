"""Fichas de los árbitros del Mundial 2026.

Plantel base: data/arbitros_mundial.csv (lista oficial FIFA, curada a mano).

Modo normal (barato, va en el cron):
  - Resuelve el id de SofaScore de cada árbitro (search/all), cacheado en
    data/arbitro_ids.csv.
  - Baja perfil de carrera (referee/{id}) y últimos partidos (events/last).
  - Si existe data/arbitro_pool.jsonl (del backfill), añade stats reales de
    nuestro pool (faltas/partido, sesgo local/visitante, amarillas/partido).
  - Salidas: data/arbitros.csv + data/arbitro_ultimos.jsonl.

Modo backfill (pesado, MANUAL una sola vez):  python extraer_arbitros.py --backfill
  - Por cada partido del pool (tarjetas.jsonl) baja event/{id} (árbitro +
    marcador) e incidents/{id} (tarjetas por local/visita) y suma fouls de
    telemetria_full.csv. Escribe data/arbitro_pool.jsonl (resumable).

Uso:
    python extraer_arbitros.py              # perfil + últimos partidos
    python extraer_arbitros.py --backfill   # cruce con el pool histórico (1 vez)
"""

import asyncio
import csv
import json
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ROSTER = DATA / "arbitros_mundial.csv"
IDS = DATA / "arbitro_ids.csv"
POOL = DATA / "arbitro_pool.jsonl"
OUT_CSV = DATA / "arbitros.csv"
OUT_ULT = DATA / "arbitro_ultimos.jsonl"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
API = "https://api.sofascore.com/api/v1"

OUT_FIELDS = [
    "sofa_id", "nombre", "pais", "cc", "confederacion",
    "partidos_carrera", "amarillas", "rojas", "dobles_amarillas",
    "partidos_pool", "amarillas_pool", "amarillas_pool_local",
    "amarillas_pool_visita", "rojas_pool", "faltas_pool", "goles_pool",
    "penaltis_pool", "amarillas_pool_1h", "amarillas_pool_2h",
]
EQUIPOS_CSV = DATA / "arbitro_equipos.csv"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


# --------------------------------------------------------------------------- #
# HTTP helper (mismo patrón que el resto de scrapers)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Plantel + resolución de id
# --------------------------------------------------------------------------- #
def load_roster() -> list[dict]:
    with open(ROSTER, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def load_id_cache() -> dict[str, dict]:
    if not IDS.exists():
        return {}
    with open(IDS, encoding="utf-8-sig") as f:
        return {r["nombre"]: r for r in csv.DictReader(f, delimiter=";")}


def save_id_cache(cache: dict[str, dict]):
    with open(IDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["nombre", "sofa_id", "pais", "cc"], delimiter=";")
        w.writeheader()
        for r in cache.values():
            w.writerow(r)


async def resolve_ids(get, roster: list[dict]) -> dict[str, dict]:
    cache = load_id_cache()
    for ref in roster:
        nombre = ref["nombre"]
        if nombre in cache and cache[nombre].get("sofa_id"):
            continue
        # Consultas de respaldo: nombre tal cual, sin guiones, y nombre+apellido.
        sin_guion = nombre.replace("-", " ")
        toks = sin_guion.split()
        corto = f"{toks[0]} {toks[-1]}" if len(toks) > 2 else sin_guion
        refs = []
        for q in dict.fromkeys([nombre, sin_guion, corto]):  # dedupe, en orden
            d = await get(f"{API}/search/all?q={q.replace(' ', '%20')}")
            refs = [
                r["entity"]
                for r in (d or {}).get("results", [])
                if r.get("type") == "referee"
            ]
            if refs:
                break
            time.sleep(0.6)
        pick = None
        if refs:
            # 1) nombre exacto (sin acentos) y país que coincide; 2) nombre; 3) el primero.
            target_c = norm(ref["pais"])
            by_name = [r for r in refs if norm(r.get("name", "")) == norm(nombre)]
            by_both = [r for r in by_name if norm((r.get("country") or {}).get("name", "")) == target_c]
            by_country = [r for r in refs if norm((r.get("country") or {}).get("name", "")) == target_c]
            pick = (by_both or by_name or by_country or refs)[0]
        if not pick:
            print(f"  ! sin id para: {nombre}")
            cache[nombre] = {"nombre": nombre, "sofa_id": "", "pais": ref["pais"], "cc": ""}
        else:
            c = pick.get("country") or {}
            cache[nombre] = {
                "nombre": nombre,
                "sofa_id": str(pick.get("id")),
                "pais": c.get("name") or ref["pais"],
                "cc": (c.get("alpha2") or "").lower(),
            }
            print(f"  · {nombre} -> {pick.get('id')} ({cache[nombre]['cc']})")
        save_id_cache(cache)
        time.sleep(1.2)
    return cache


# --------------------------------------------------------------------------- #
# Perfil + últimos partidos
# --------------------------------------------------------------------------- #
async def fetch_profile(get, sofa_id: str) -> dict | None:
    d = await get(f"{API}/referee/{sofa_id}")
    return (d or {}).get("referee")


async def fetch_last(get, sofa_id: str) -> list[dict]:
    d = await get(f"{API}/referee/{sofa_id}/events/last/0")
    out = []
    for e in (d or {}).get("events", []):
        out.append(
            {
                "event_id": e.get("id"),
                "ts": e.get("startTimestamp"),
                "torneo": (e.get("tournament") or {}).get("name"),
                "home": (e.get("homeTeam") or {}).get("name"),
                "away": (e.get("awayTeam") or {}).get("name"),
                "score_home": (e.get("homeScore") or {}).get("current"),
                "score_away": (e.get("awayScore") or {}).get("current"),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Agregación del pool (si hay backfill)
# --------------------------------------------------------------------------- #
def load_pool_agg(path: Path = POOL) -> tuple[dict, dict]:
    """Devuelve (por_arbitro, por_evento) a partir de un arbitro_pool.jsonl."""
    by_ref = defaultdict(lambda: {
        "games": 0, "yellow": 0, "yellow_home": 0, "yellow_away": 0,
        "red": 0, "fouls": 0.0, "fouls_n": 0, "goals": 0.0, "goals_n": 0,
        "pen": 0, "yellow_1h": 0, "yellow_2h": 0,
    })
    by_event = {}
    if not path.exists():
        return {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rid = r.get("referee_id")
            if not rid:
                continue
            a = by_ref[rid]
            a["games"] += 1
            a["yellow"] += r.get("yellow", 0)
            a["yellow_home"] += r.get("yellow_home", 0)
            a["yellow_away"] += r.get("yellow_away", 0)
            a["red"] += r.get("red", 0)
            a["pen"] += r.get("penalties", 0)
            a["yellow_1h"] += r.get("yellow_1h", 0)
            a["yellow_2h"] += r.get("yellow_2h", 0)
            if r.get("fouls") is not None:
                a["fouls"] += r["fouls"]; a["fouls_n"] += 1
            gh, ga = r.get("goals_home"), r.get("goals_away")
            if gh is not None and ga is not None:
                a["goals"] += gh + ga; a["goals_n"] += 1
            by_event[str(r["partido_id"])] = r.get("yellow")
    return by_ref, by_event


def pool_equipos() -> dict:
    """Por (referee_id, equipo): partidos arbitrados y amarillas totales del
    partido. Para el 'historial vs selecciones del Mundial'."""
    agg = defaultdict(lambda: {"games": 0, "yellow": 0})
    if not POOL.exists():
        return {}
    with open(POOL, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rid = r.get("referee_id")
            if not rid:
                continue
            y = r.get("yellow", 0)
            for team in (r.get("home"), r.get("away")):
                if team:
                    k = (rid, team)
                    agg[k]["games"] += 1
                    agg[k]["yellow"] += y
    return agg


# --------------------------------------------------------------------------- #
# Modo normal
# --------------------------------------------------------------------------- #
async def run_normal():
    roster = load_roster()
    pool_ref, pool_ev = load_pool_agg()

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await (await b.new_context(user_agent=UA)).new_page()
        get = await make_get(pg)

        cache = await resolve_ids(get, roster)

        rows, ult = [], []
        roster_by_name = {r["nombre"]: r for r in roster}
        for nombre, c in cache.items():
            sid = c.get("sofa_id")
            if not sid:
                continue
            prof = await fetch_profile(get, sid)
            time.sleep(1.2)
            last = await fetch_last(get, sid)
            time.sleep(1.2)
            if not prof:
                print(f"  ! sin perfil: {nombre}")
                continue
            rid = int(sid)
            pa = pool_ref.get(rid)
            row = {
                "sofa_id": sid,
                "nombre": nombre,
                "pais": c.get("pais", ""),
                "cc": c.get("cc", ""),
                "confederacion": roster_by_name.get(nombre, {}).get("confederacion", ""),
                "partidos_carrera": prof.get("games", 0),
                "amarillas": prof.get("yellowCards", 0),
                "rojas": prof.get("redCards", 0),
                "dobles_amarillas": prof.get("yellowRedCards", 0),
                "partidos_pool": pa["games"] if pa else "",
                "amarillas_pool": pa["yellow"] if pa else "",
                "amarillas_pool_local": pa["yellow_home"] if pa else "",
                "amarillas_pool_visita": pa["yellow_away"] if pa else "",
                "rojas_pool": pa["red"] if pa else "",
                "faltas_pool": round(pa["fouls"] / pa["fouls_n"], 2) if pa and pa["fouls_n"] else "",
                "goles_pool": round(pa["goals"] / pa["goals_n"], 2) if pa and pa["goals_n"] else "",
                "penaltis_pool": pa["pen"] if pa else "",
                "amarillas_pool_1h": pa["yellow_1h"] if pa else "",
                "amarillas_pool_2h": pa["yellow_2h"] if pa else "",
            }
            rows.append(row)
            # anota amarillas reales en los últimos partidos que estén en el pool
            for m in last:
                m["amarillas"] = pool_ev.get(str(m.get("event_id")))
            ult.append({"sofa_id": int(sid), "partidos": last})
            print(f"  ficha {nombre}: {row['partidos_carrera']}p, {row['amarillas']}am")
        await b.close()

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    with open(OUT_ULT, "w", encoding="utf-8") as f:
        for r in ult:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Historial vs equipos (para "vs selecciones del Mundial"); el seed filtra
    # a las 48 mundialistas. Solo árbitros del plantel resuelto.
    ids_plantel = {int(c["sofa_id"]) for c in cache.values() if c.get("sofa_id")}
    equipos = pool_equipos()
    with open(EQUIPOS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["sofa_id", "equipo", "partidos", "amarillas"])
        for (rid, team), v in sorted(equipos.items()):
            if rid in ids_plantel:
                w.writerow([rid, team, v["games"], v["yellow"]])
    print(f"OK: {len(rows)} árbitros -> arbitros.csv (+ equipos)")


# --------------------------------------------------------------------------- #
# Modo backfill (pool histórico)
# --------------------------------------------------------------------------- #
def pool_partidos() -> list[str]:
    seen, pids = set(), []
    with open(DATA / "tarjetas.jsonl", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            pid = str(json.loads(line)["partido_id"])
            if pid not in seen:
                seen.add(pid); pids.append(pid)
    return pids


def fouls_por_partido() -> dict[str, float]:
    """Suma fouls de telemetria_full.csv por partido_id."""
    out = defaultdict(float)
    path = DATA / "telemetria_full.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            v = r.get("fouls")
            if v:
                try:
                    out[r["partido_id"]] += float(v)
                except ValueError:
                    pass
    return out


def backfill_hechos() -> set[str]:
    if not POOL.exists():
        return set()
    return {str(json.loads(l)["partido_id"]) for l in open(POOL, encoding="utf-8") if l.strip()}


WWW_EVENT = "https://www.sofascore.com/event"


async def fetch_event_www(pg, pid: str):
    """(event, incidents) del JSON embebido (__NEXT_DATA__) de la web del
    partido. Esquiva el 403 del API: www.sofascore.com sí carga y trae los
    mismos datos (referee, marcador por mitad, incidents con minuto/equipo)."""
    try:
        r = await pg.goto(f"{WWW_EVENT}/{pid}", wait_until="domcontentloaded", timeout=30000)
        if not r or r.status != 200:
            return None, None
        nd = await pg.evaluate("()=>document.getElementById('__NEXT_DATA__')?.textContent")
        if not nd:
            return None, None
        pp = json.loads(nd).get("props", {}).get("pageProps", {})
        return pp.get("event"), pp.get("incidents") or []
    except Exception:
        return None, None


async def run_backfill():
    fouls = fouls_por_partido()
    hechos = backfill_hechos()
    pend = [p for p in pool_partidos() if p not in hechos]
    if "--limit" in sys.argv:
        pend = pend[: int(sys.argv[sys.argv.index("--limit") + 1])]
    print(f"backfill (web): {len(pend)} partidos por procesar")

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await (await b.new_context(user_agent=UA)).new_page()
        out = open(POOL, "a", encoding="utf-8")

        fallos = 0
        for i, pid in enumerate(pend, 1):
            event, incidents = await fetch_event_www(pg, pid)
            # Si falla la carga, NO escribir el registro: así no se marca como
            # "hecho" y un reintento posterior lo recupera.
            if not event:
                fallos += 1
                if fallos >= 20:
                    print(f"  ! {fallos} fallos seguidos, abortando; reintenta más tarde.")
                    break
                await asyncio.sleep(2)
                continue
            fallos = 0
            ref = event.get("referee")
            yh = ya = red = pen = y1h = y2h = 0
            for x in incidents:
                it, ic = x.get("incidentType"), x.get("incidentClass")
                if it == "card" and ic in ("yellow", "yellowRed"):
                    if x.get("isHome"):
                        yh += 1
                    else:
                        ya += 1
                    if (x.get("time") or 0) <= 45:
                        y1h += 1
                    else:
                        y2h += 1
                if it == "card" and ic in ("red", "yellowRed"):
                    red += 1
                # Penaltis pitados: marcados (goal/penalty) + fallados (missedPenalty).
                if (it == "goal" and ic == "penalty") or it == "missedPenalty":
                    pen += 1
            rec = {
                "partido_id": pid,
                "referee_id": (ref or {}).get("id"),
                "referee_name": (ref or {}).get("name"),
                "home": (event.get("homeTeam") or {}).get("name"),
                "away": (event.get("awayTeam") or {}).get("name"),
                "yellow": yh + ya,
                "yellow_home": yh,
                "yellow_away": ya,
                "yellow_1h": y1h,
                "yellow_2h": y2h,
                "red": red,
                "penalties": pen,
                "goals_home": (event.get("homeScore") or {}).get("current"),
                "goals_away": (event.get("awayScore") or {}).get("current"),
                "fouls": fouls.get(pid),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0 or i == len(pend):
                print(f"  [{i}/{len(pend)}]")
            time.sleep(0.5)
        out.close()
        await b.close()
    print(f"OK backfill -> {POOL.name}. Vuelve a correr 'extraer_arbitros.py' para fusionar.")


def run_merge():
    """Fusiona los datos del pool (arbitro_pool.jsonl) en arbitros.csv SIN tocar
    la API: actualiza las columnas *_pool y escribe arbitro_equipos.csv. Pensado
    para correr tras un --backfill (aunque sea parcial)."""
    if not OUT_CSV.exists():
        print("no hay arbitros.csv; corre el modo normal primero")
        return
    pool_ref, _ = load_pool_agg()
    rows = list(csv.DictReader(open(OUT_CSV, encoding="utf-8-sig"), delimiter=";"))
    n = 0
    for row in rows:
        sid = row.get("sofa_id")
        pa = pool_ref.get(int(sid)) if sid else None
        if not pa:
            continue
        n += 1
        row["partidos_pool"] = pa["games"]
        row["amarillas_pool"] = pa["yellow"]
        row["amarillas_pool_local"] = pa["yellow_home"]
        row["amarillas_pool_visita"] = pa["yellow_away"]
        row["rojas_pool"] = pa["red"]
        row["faltas_pool"] = round(pa["fouls"] / pa["fouls_n"], 2) if pa["fouls_n"] else ""
        row["goles_pool"] = round(pa["goals"] / pa["goals_n"], 2) if pa["goals_n"] else ""
        row["penaltis_pool"] = pa["pen"]
        row["amarillas_pool_1h"] = pa["yellow_1h"]
        row["amarillas_pool_2h"] = pa["yellow_2h"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    ids_plantel = {int(r["sofa_id"]) for r in rows if r.get("sofa_id")}
    equipos = pool_equipos()
    with open(EQUIPOS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["sofa_id", "equipo", "partidos", "amarillas"])
        for (rid, team), v in sorted(equipos.items()):
            if rid in ids_plantel:
                w.writerow([rid, team, v["games"], v["yellow"]])
    print(f"merge OK: {n} árbitros con datos del pool -> arbitros.csv (+ equipos)")


def main():
    if "--backfill" in sys.argv:
        asyncio.run(run_backfill())
    elif "--merge" in sys.argv:
        run_merge()
    else:
        asyncio.run(run_normal())


if __name__ == "__main__":
    main()

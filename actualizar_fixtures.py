"""Detecta partidos NUEVOS del Mundial (eliminatorias, cuando ya se conocen los
cruces) desde el calendario de SofaScore y los añade a:
  - data/partidos_a_predecir.csv  (con fase=eliminatoria)  → el modelo los predice
  - data/calendario.csv           (event_id + kickoff)      → para resultado/post-partido

Idempotente: solo añade eventos cuyo id no esté ya en calendario.csv. Mientras
los grupos no acaben, las eliminatorias tienen equipos "TBD" → no casan con las
48 → no se añade nada.
"""

import asyncio
import csv
import datetime as dt
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UT, SEASON = 16, 58210  # World Cup 2026 en SofaScore


def norm(s: str) -> str:
    return (s or "").lower().replace("&", "and").replace("-", " ").replace(".", "").strip()


def code3(name: str) -> str:
    letras = [c for c in name.upper() if c.isalpha()]
    return "".join(letras[:3]) or "XXX"


async def main():
    pred_rows = list(
        csv.DictReader(open(DATA / "partidos_a_predecir.csv", encoding="utf-8-sig"), delimiter=";")
    )
    cal_rows = list(
        csv.DictReader(open(DATA / "calendario.csv", encoding="utf-8-sig"), delimiter=";")
    )
    nuestras = {norm(r["equipo_a"]) for r in pred_rows} | {
        norm(r["equipo_b"]) for r in pred_rows
    }
    nombre_real = {}  # norm -> nombre tal cual lo tenemos
    for r in pred_rows:
        nombre_real[norm(r["equipo_a"])] = r["equipo_a"]
        nombre_real[norm(r["equipo_b"])] = r["equipo_b"]
    pids = {r["partido_id"] for r in pred_rows}
    event_ids = {r["sofa_event_id"] for r in cal_rows if r.get("sofa_event_id")}

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await (
            await b.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        ).new_page()

        async def get(u):
            r = await pg.goto(u, wait_until="domcontentloaded")
            if r and r.status == 200:
                return json.loads(
                    await pg.evaluate("()=>document.querySelector('pre')?.innerText ?? document.body.innerText")
                )
            return None

        eventos = []
        for fase in ("next", "last"):
            for page in range(0, 6):
                d = await get(
                    f"https://api.sofascore.com/api/v1/unique-tournament/{UT}/season/{SEASON}/events/{fase}/{page}"
                )
                evs = (d or {}).get("events", [])
                if not evs:
                    break
                eventos += evs
        await b.close()

    nuevos_pred, nuevos_cal = [], []
    for ev in eventos:
        eid = str(ev.get("id"))
        if eid in event_ids:
            continue  # ya lo tenemos (grupos o añadido antes)
        h = ev.get("homeTeam", {}).get("name")
        a = ev.get("awayTeam", {}).get("name")
        if norm(h) not in nuestras or norm(a) not in nuestras:
            continue  # equipos aún sin decidir (TBD) o no mundialistas
        ka = nombre_real[norm(h)]
        kb = nombre_real[norm(a)]
        base = f"{code3(ka)}_{code3(kb)}"
        pid = base if base not in pids else f"{base}_{eid}"
        pids.add(pid)
        event_ids.add(eid)
        ts = ev.get("startTimestamp")
        fecha = dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
        nuevos_pred.append(
            {"partido_id": pid, "fecha": fecha, "equipo_a": ka, "equipo_b": kb, "fase": "eliminatoria"}
        )
        nuevos_cal.append(
            {"partido_id": pid, "sofa_event_id": eid, "kickoff": ts or "", "sofa": f"{h} vs {a}"}
        )

    if nuevos_pred:
        with open(DATA / "partidos_a_predecir.csv", "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["partido_id", "fecha", "equipo_a", "equipo_b", "fase"], delimiter=";").writerows(nuevos_pred)
        with open(DATA / "calendario.csv", "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["partido_id", "sofa_event_id", "kickoff", "sofa"], delimiter=";").writerows(nuevos_cal)
    print(f"Fixtures nuevos añadidos: {len(nuevos_pred)}")
    for r in nuevos_pred:
        print(f"  + {r['partido_id']}: {r['equipo_a']} vs {r['equipo_b']} ({r['fecha']})")


if __name__ == "__main__":
    asyncio.run(main())

"""Scrape de convocatorias (plantilla actual) por selección desde SofaScore.

Para cada team_id de extraer.equipos_maestros baja:
  - team/{id}/players  -> jugadores de la plantilla
  - team/{id}          -> nombre de la selección (inglés, casa con stats/telemetría)

Salida: convocatorias.csv  (equipo;jugador)  + convocatorias.jsonl (resumable).
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

from extraer import equipos_maestros

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT_JSONL = DATA / "convocatorias.jsonl"
OUT_CSV = DATA / "convocatorias.csv"
DELAY = 1.5


def ids_hechos() -> set[int]:
    if not OUT_JSONL.exists():
        return set()
    done = set()
    with open(OUT_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                done.add(json.loads(line)["team_id"])
            except Exception:
                pass
    return done


async def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    ids = sorted({m["id"] for m in equipos_maestros.values() if m.get("id")})
    hechos = ids_hechos()
    pend = [i for i in ids if i not in hechos]
    if limite:
        pend = pend[:limite]
    print(f"IDs únicos: {len(ids)} | hechos: {len(hechos)} | a procesar: {len(pend)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await (
            await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        ).new_page()

        async def get(url):
            try:
                r = await page.goto(url, wait_until="domcontentloaded")
                if r and r.status == 200:
                    t = await page.evaluate(
                        "()=>document.querySelector('pre')?.innerText ?? document.body.innerText"
                    )
                    return json.loads(t)
            except Exception:
                return None
            return None

        out = open(OUT_JSONL, "a", encoding="utf-8")
        for i, tid in enumerate(pend, 1):
            info = await get(f"https://api.sofascore.com/api/v1/team/{tid}")
            time.sleep(DELAY)
            squad = await get(f"https://api.sofascore.com/api/v1/team/{tid}/players")
            time.sleep(DELAY)
            equipo = (info or {}).get("team", {}).get("name") or (info or {}).get("name")
            jugadores = [
                x.get("player", {}).get("name")
                for x in (squad or {}).get("players", [])
                if x.get("player", {}).get("name")
            ]
            out.write(
                json.dumps(
                    {"team_id": tid, "equipo": equipo, "jugadores": jugadores},
                    ensure_ascii=False,
                )
                + "\n"
            )
            out.flush()
            if i % 20 == 0 or i == len(pend):
                print(f"  [{i}/{len(pend)}] id={tid} {equipo}: {len(jugadores)} jug")
        out.close()
        await browser.close()

    # Consolidar a CSV largo (equipo;jugador)
    filas = []
    with open(OUT_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if not d.get("equipo"):
                continue
            for j in d["jugadores"]:
                filas.append({"equipo": d["equipo"], "jugador": j})
    df = pd.DataFrame(filas).drop_duplicates()
    df.to_csv(OUT_CSV, index=False, sep=";")
    print(f"OK: {len(df)} (equipo,jugador), {df['equipo'].nunique()} selecciones -> {OUT_CSV.name}")


if __name__ == "__main__":
    asyncio.run(main())

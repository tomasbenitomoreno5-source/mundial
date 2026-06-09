"""Scrape de bio + id de cada jugador de las 48 selecciones (team/{id}/players):
id de SofaScore (para la foto), posición, edad, altura, pie y valor de mercado.

Salida: data/bios.csv  (jugador;sofa_id;posicion;edad;altura;pie;valor_eur)
"""

import asyncio
import csv
import datetime as dt
import json
from pathlib import Path

from playwright.async_api import async_playwright

from extraer import equipos_maestros

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
# IDs correctos de las 6 selecciones cuyo id en equipos_maestros estaba mal.
EXTRA_IDS = [4475, 4695, 4688, 4729, 55827, 4768]
AHORA = dt.datetime.now()


def edad(ts) -> int | None:
    if not ts:
        return None
    nac = dt.datetime.fromtimestamp(ts)
    return int((AHORA - nac).days // 365.25)


async def main():
    ids = sorted({m["id"] for m in equipos_maestros.values() if m.get("id")} | set(EXTRA_IDS))
    filas = {}  # jugador -> fila (dedupe por nombre)

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await (
            await b.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        ).new_page()

        async def get(u):
            try:
                r = await pg.goto(u, wait_until="domcontentloaded")
                if r and r.status == 200:
                    return json.loads(await pg.evaluate("()=>document.querySelector('pre')?.innerText ?? document.body.innerText"))
            except Exception:
                return None
            return None

        for i, tid in enumerate(ids, 1):
            d = await get(f"https://api.sofascore.com/api/v1/team/{tid}/players")
            for entry in (d or {}).get("players", []):
                pl = entry.get("player", {})
                name = pl.get("name")
                if not name:
                    continue
                val = (pl.get("proposedMarketValueRaw") or {}).get("value")
                filas[name] = {
                    "jugador": name,
                    "sofa_id": pl.get("id") or "",
                    "posicion": pl.get("position") or "",
                    "edad": edad(pl.get("dateOfBirthTimestamp")) or "",
                    "altura": pl.get("height") or "",
                    "pie": pl.get("preferredFoot") or "",
                    "valor_eur": val or "",
                }
            await asyncio.sleep(1.2)
            if i % 25 == 0 or i == len(ids):
                print(f"  [{i}/{len(ids)}] {len(filas)} jugadores")
        await b.close()

    with open(DATA / "bios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["jugador", "sofa_id", "posicion", "edad", "altura", "pie", "valor_eur"],
            delimiter=";",
        )
        w.writeheader()
        w.writerows(filas.values())
    print(f"OK: {len(filas)} jugadores -> bios.csv")


if __name__ == "__main__":
    asyncio.run(main())

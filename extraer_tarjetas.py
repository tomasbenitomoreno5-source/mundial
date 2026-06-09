"""Scrape de amonestaciones: para los partidos que tenemos en telemetria_full,
baja event/{id}/incidents y cuenta en cuántos partidos cada jugador vio amarilla.

Salida: data/tarjetas.csv  (jugador;partidos_amonestado)
Resumable vía data/tarjetas.jsonl (un registro por partido).
"""

import asyncio
import csv
import json
import time
from collections import Counter
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JSONL = DATA / "tarjetas.jsonl"


def partidos() -> list[str]:
    pids = []
    seen = set()
    with open(DATA / "telemetria_full.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            pid = r["partido_id"]
            if pid not in seen:
                seen.add(pid)
                pids.append(pid)
    return pids


def hechos() -> set[str]:
    if not JSONL.exists():
        return set()
    return {json.loads(l)["partido_id"] for l in open(JSONL, encoding="utf-8") if l.strip()}


async def main():
    pend = [p for p in partidos() if p not in hechos()]
    print(f"partidos: total {len(partidos())} | a procesar {len(pend)}")

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await (
            await b.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        ).new_page()
        out = open(JSONL, "a", encoding="utf-8")

        async def get(u):
            for _ in range(2):
                try:
                    r = await pg.goto(u, wait_until="domcontentloaded", timeout=30000)
                    if r and r.status == 200:
                        return json.loads(await pg.evaluate("()=>document.querySelector('pre')?.innerText ?? document.body.innerText"))
                    return None
                except Exception:
                    await asyncio.sleep(2)
            return None

        for i, pid in enumerate(pend, 1):
            d = await get(f"https://api.sofascore.com/api/v1/event/{pid}/incidents")
            booked = sorted(
                {
                    (inc.get("player") or {}).get("name")
                    for inc in (d or {}).get("incidents", [])
                    if inc.get("incidentType") == "card"
                    and inc.get("incidentClass") in ("yellow", "yellowRed")
                    and (inc.get("player") or {}).get("name")
                }
            )
            out.write(json.dumps({"partido_id": pid, "booked": booked}, ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0 or i == len(pend):
                print(f"  [{i}/{len(pend)}]")
            time.sleep(1.4)
        out.close()
        await b.close()

    # Agregar: nº de partidos en que cada jugador vio amarilla.
    cnt = Counter()
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            for name in json.loads(line).get("booked", []):
                cnt[name] += 1
    with open(DATA / "tarjetas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["jugador", "partidos_amonestado"])
        for name, c in sorted(cnt.items()):
            w.writerow([name, c])
    print(f"OK: {len(cnt)} jugadores con amarillas -> tarjetas.csv")


if __name__ == "__main__":
    asyncio.run(main())

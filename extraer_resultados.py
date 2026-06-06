"""Baja el marcador real de los partidos del Mundial ya jugados.

Lee data/calendario.csv (partido_id, sofa_event_id, kickoff) y, para los
partidos cuyo kickoff ya pasó, consulta event/{id} en SofaScore. Orienta el
marcador a NUESTRO equipo_a/equipo_b (el calendario se mapeó por pareja, así que
equipo_a no es necesariamente el local).

Salida: data/resultados.csv  (partido_id;score_a;score_b;finished)
Idempotente: reescribe el CSV completo en cada ejecución.
"""

import asyncio
import csv
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def norm(s: str) -> str:
    return (s or "").lower().replace("&", "and").replace("-", " ").replace(".", "").strip()


def cargar() -> list[dict]:
    cal = {}
    with open(DATA / "calendario.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cal[r["partido_id"]] = {
                "event_id": r["sofa_event_id"],
                "kickoff": int(r["kickoff"]) if r["kickoff"] else 0,
            }
    out = []
    with open(DATA / "partidos_a_predecir.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            c = cal.get(r["partido_id"])
            if c:
                out.append(
                    {
                        "partido_id": r["partido_id"],
                        "equipo_a": r["equipo_a"].strip(),
                        "equipo_b": r["equipo_b"].strip(),
                        **c,
                    }
                )
    return out


async def main():
    partidos = cargar()
    ahora = time.time()
    # Solo los que ya han empezado (con margen de 0): evita 72 llamadas inútiles.
    jugados = [p for p in partidos if p["kickoff"] and p["kickoff"] <= ahora]
    print(f"Partidos en calendario: {len(partidos)} | ya iniciados: {len(jugados)}")

    filas = []
    if jugados:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (
                await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
                )
            ).new_page()

            async def get(url):
                try:
                    r = await page.goto(url, wait_until="domcontentloaded")
                    if r and r.status == 200:
                        return json.loads(
                            await page.evaluate(
                                "()=>document.querySelector('pre')?.innerText ?? document.body.innerText"
                            )
                        )
                except Exception:
                    return None
                return None

            for pmatch in jugados:
                data = await get(
                    f"https://api.sofascore.com/api/v1/event/{pmatch['event_id']}"
                )
                ev = (data or {}).get("event", {})
                status = ev.get("status", {}).get("type")  # "finished" | "inprogress" | ...
                home = ev.get("homeTeam", {}).get("name")
                hs = ev.get("homeScore", {}).get("current")
                aws = ev.get("awayScore", {}).get("current")
                # Orientar a nuestro equipo_a/equipo_b
                if norm(home) == norm(pmatch["equipo_a"]):
                    sa, sb = hs, aws
                else:
                    sa, sb = aws, hs
                filas.append(
                    {
                        "partido_id": pmatch["partido_id"],
                        "score_a": "" if sa is None else sa,
                        "score_b": "" if sb is None else sb,
                        "finished": 1 if status == "finished" else 0,
                    }
                )
                time.sleep(1.5)
            await browser.close()

    with open(DATA / "resultados.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["partido_id", "score_a", "score_b", "finished"], delimiter=";"
        )
        w.writeheader()
        w.writerows(filas)
    fin = sum(1 for r in filas if r["finished"] == 1)
    print(f"OK: {len(filas)} con datos, {fin} finalizados -> resultados.csv")


if __name__ == "__main__":
    asyncio.run(main())

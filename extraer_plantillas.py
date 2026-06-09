"""Re-scrape de plantillas COMPLETAS (no solo las estrellas).

Reutiliza los `partido_id` que ya tenemos en stats_final.csv (cubren las 48
selecciones) y re-baja `event/{id}/lineups` capturando TODOS los jugadores con
estadísticas, no la lista blanca `jugadores_objetivo` del extraer.py original.

El equipo de cada jugador se deduce de stats_final (sabemos las dos selecciones
de cada partido y qué lado es local/visitante).

Salida: telemetria_full.csv (mismo formato que telemetria_final.csv).
Incremental y resumable vía telemetria_full.jsonl (si se corta, se reanuda
saltando los partidos ya hechos).

Uso:
    .venv/bin/python extraer_plantillas.py            # todos los partidos
    .venv/bin/python extraer_plantillas.py 5          # solo 5 (prueba)
"""

import asyncio
import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STATS = DATA / "stats_final.csv"
OUT_JSONL = DATA / "telemetria_full.jsonl"
OUT_CSV = DATA / "telemetria_full.csv"
DELAY = 1.8  # segundos entre partidos


def cargar_partidos() -> dict[str, dict]:
    """partido_id -> {home, away, completo} desde stats_final.csv."""
    pids: dict[str, dict] = {}
    with open(STATS, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            pid = row["partido_id"]
            d = pids.setdefault(pid, {})
            d[row["tipo_equipo"]] = row["equipo_nombre"]
    out = {}
    for pid, d in pids.items():
        if "home" in d and "away" in d:
            out[pid] = {
                "home": d["home"],
                "away": d["away"],
                "completo": f"{d['home']} vs {d['away']}",
            }
    return out


def pids_hechos() -> set[str]:
    if not OUT_JSONL.exists():
        return set()
    done = set()
    with open(OUT_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                done.add(json.loads(line)["partido_id"])
            except Exception:
                pass
    return done


async def fetch_json(page, url):
    try:
        resp = await page.goto(url, wait_until="domcontentloaded")
        if resp and resp.status == 200:
            txt = await page.evaluate(
                "() => document.querySelector('pre')?.innerText ?? document.body.innerText"
            )
            return json.loads(txt)
    except Exception:
        return None
    return None


async def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    partidos = cargar_partidos()
    hechos = pids_hechos()
    pendientes = [p for p in partidos if p not in hechos]
    if limite:
        pendientes = pendientes[:limite]
    print(f"Partidos totales: {len(partidos)} | hechos: {len(hechos)} | a procesar: {len(pendientes)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        )
        page = await context.new_page()

        out = open(OUT_JSONL, "a", encoding="utf-8")
        n_jug = 0
        for i, pid in enumerate(pendientes, 1):
            meta = partidos[pid]
            data = await fetch_json(page, f"https://api.sofascore.com/api/v1/event/{pid}/lineups")
            filas = 0
            if data:
                for side in ("home", "away"):
                    for entry in data.get(side, {}).get("players", []):
                        stats = entry.get("statistics") or {}
                        if not stats:
                            continue
                        row = dict(stats)
                        row.update({
                            "partido_id": pid,
                            "partido_completo": meta["completo"],
                            "jugador": entry.get("player", {}).get("name", ""),
                            "home_team": meta["home"],
                            "away_team": meta["away"],
                        })
                        out.write(json.dumps(row, ensure_ascii=False) + "\n")
                        filas += 1
                        n_jug += 1
            out.flush()
            if i % 25 == 0 or i == len(pendientes):
                print(f"  [{i}/{len(pendientes)}] {pid} ({meta['completo']}): {filas} jug · total {n_jug}")
            time.sleep(DELAY)

        out.close()
        await browser.close()

    # Consolidar JSONL -> CSV
    rows = []
    with open(OUT_JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    df = pd.DataFrame(rows)
    # columnas de identidad primero
    front = ["partido_id", "partido_completo", "jugador", "home_team", "away_team"]
    cols = front + [c for c in df.columns if c not in front]
    df = df[cols]
    df.to_csv(OUT_CSV, index=False, sep=";")
    print(f"OK: {len(df)} filas, {df['jugador'].nunique()} jugadores, "
          f"{df['partido_id'].nunique()} partidos -> {OUT_CSV.name}")


if __name__ == "__main__":
    asyncio.run(main())

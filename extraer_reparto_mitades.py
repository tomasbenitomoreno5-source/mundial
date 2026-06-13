"""Reparto 1ª/2ª parte de cada métrica de conteo, del pool histórico.

Para cada partido del pool baja event/{id}/statistics (periodos 1ST/2ND) y suma
por métrica (home+away). Agrega global -> cuota de 1ª parte por métrica, que el
motor usa para repartir las simulaciones de partido completo en mitades.

Salidas:
  - data/reparto_mitades.jsonl  (un registro por partido; resumable)
  - data/reparto_mitades.csv    (metrica;share_1h agregado)

Uso:
    python extraer_reparto_mitades.py            # todo el pool (resumable)
    python extraer_reparto_mitades.py --limit 250  # solo N nuevos (muestra)
"""

import asyncio
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JSONL = DATA / "reparto_mitades.jsonl"
OUT = DATA / "reparto_mitades.csv"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
API = "https://api.sofascore.com/api/v1"

# Nombre SofaScore -> métrica canónica (las de conteo viables por mitad).
ITEMS = {
    "Total shots": "total_shots",
    "Shots on target": "shots_on_target",
    "Corner kicks": "corner_kicks",
    "Fouls": "fouls",
    "Yellow cards": "yellow_cards",
    "Offsides": "offsides",
}


def pool_partidos() -> list[str]:
    seen, pids = set(), []
    src = DATA / "tarjetas.jsonl"
    if not src.exists():
        return []
    with open(src, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pid = str(json.loads(line)["partido_id"])
                if pid not in seen:
                    seen.add(pid); pids.append(pid)
    return pids


def hechos() -> set[str]:
    if not JSONL.exists():
        return set()
    return {str(json.loads(l)["partido_id"]) for l in open(JSONL, encoding="utf-8") if l.strip()}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


async def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    pend = [p for p in pool_partidos() if p not in hechos()]
    if limit:
        pend = pend[:limit]
    print(f"reparto: {len(pend)} partidos por procesar")

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await (await b.new_context(user_agent=UA)).new_page()
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
            d = await get(f"{API}/event/{pid}/statistics")
            ev = await get(f"{API}/event/{pid}")
            rec = {"partido_id": pid, "h1": {}, "h2": {}}
            for period in (d or {}).get("statistics", []):
                per = period.get("period")
                if per not in ("1ST", "2ND"):
                    continue
                key = "h1" if per == "1ST" else "h2"
                for g in period.get("groups", []):
                    for it in g.get("statisticsItems", []):
                        canon = ITEMS.get(it.get("name"))
                        if canon is None:
                            continue
                        h, a = num(it.get("home")), num(it.get("away"))
                        if h is not None and a is not None:
                            rec[key][canon] = rec[key].get(canon, 0.0) + h + a
            # Goles por mitad del marcador por periodo.
            evd = (ev or {}).get("event", {})
            hs, as_ = evd.get("homeScore", {}), evd.get("awayScore", {})
            if hs.get("period1") is not None and as_.get("period1") is not None:
                rec["h1"]["goles"] = hs["period1"] + as_["period1"]
            if hs.get("period2") is not None and as_.get("period2") is not None:
                rec["h2"]["goles"] = hs["period2"] + as_["period2"]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0 or i == len(pend):
                print(f"  [{i}/{len(pend)}]")
            time.sleep(1.2)
        out.close()
        await b.close()

    agregar()


def agregar():
    """Agrega reparto_mitades.jsonl -> share_1h por métrica."""
    s1, s2 = defaultdict(float), defaultdict(float)
    n = 0
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line); n += 1
            for m, v in r.get("h1", {}).items():
                s1[m] += v
            for m, v in r.get("h2", {}).items():
                s2[m] += v
    metricas = sorted(set(s1) | set(s2))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["metrica", "share_1h", "n_partidos"])
        for m in metricas:
            tot = s1[m] + s2[m]
            share = round(s1[m] / tot, 4) if tot > 0 else 0.5
            w.writerow([m, share, n])
    print(f"OK: reparto de {len(metricas)} métricas ({n} partidos) -> {OUT.name}")


if __name__ == "__main__":
    asyncio.run(main())

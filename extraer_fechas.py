"""Backfill de fecha/torneo por partido_id (event id de SofaScore).

stats_final.csv no tiene fecha → la recencia (mejora #8) y el backtest temporal
están bloqueados. El partido_id ES el event id de SofaScore, así que se
backfillea sin re-scrapear los partidos: por cada id, fecha + torneo + categoría.

Usa el cliente único (predictor.sofascore) con fallback API→HTML, así que
funciona aunque la API esté tras Cloudflare. Resumable vía data/partido_fechas.jsonl.

Uso:  python extraer_fechas.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd

from predictor.sofascore import SofaScoreClient

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STATS = DATA / "stats_final.csv"
OUT_JSONL = DATA / "partido_fechas.jsonl"
OUT_CSV = DATA / "partido_fechas.csv"


def _ids_objetivo() -> list[int]:
    s = pd.read_csv(STATS, sep=";", encoding="utf-8-sig", usecols=["partido_id"])
    return sorted(int(x) for x in s["partido_id"].unique())


def _ya_hechos() -> set[int]:
    if not OUT_JSONL.exists():
        return set()
    hechos = set()
    with OUT_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                hechos.add(int(json.loads(line)["partido_id"]))
    return hechos


def _consolidar_csv() -> int:
    rows = [json.loads(l) for l in OUT_JSONL.open(encoding="utf-8") if l.strip()]
    df = pd.DataFrame(rows).drop_duplicates("partido_id")
    df["fecha"] = pd.to_datetime(df["timestamp"], unit="s").dt.date.astype(str)
    df = df[["partido_id", "fecha", "timestamp", "torneo", "categoria"]]
    df.to_csv(OUT_CSV, sep=";", index=False, encoding="utf-8-sig")
    return len(df)


async def main() -> None:
    ids = _ids_objetivo()
    hechos = _ya_hechos()
    pendientes = [i for i in ids if i not in hechos]
    print(f"ids totales: {len(ids)} | ya hechos: {len(hechos)} | pendientes: {len(pendientes)}",
          flush=True)
    if not pendientes:
        n = _consolidar_csv()
        print(f"Nada pendiente. CSV consolidado: {n} filas -> {OUT_CSV.name}", flush=True)
        return

    async with SofaScoreClient(rate_limit_s=0.3) as cli:
        with OUT_JSONL.open("a", encoding="utf-8") as f:
            for n, eid in enumerate(pendientes, 1):
                ev = await cli.fetch_event(eid)
                if ev and ev.get("startTimestamp"):
                    t = ev.get("tournament", {}) or {}
                    row = {
                        "partido_id": eid,
                        "timestamp": ev["startTimestamp"],
                        "torneo": t.get("name", ""),
                        "categoria": (t.get("category", {}) or {}).get("name", ""),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                if n % 50 == 0:
                    print(f"  {n}/{len(pendientes)}  via={cli.via}", flush=True)
        print(f"via final: {cli.via}", flush=True)

    n = _consolidar_csv()
    print(f"OK: {n} filas -> {OUT_CSV.name}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

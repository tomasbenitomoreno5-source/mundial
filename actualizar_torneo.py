"""Loop en vivo del Mundial: incorpora resultados jugados, actualiza el ELO y
re-predice los partidos restantes.

El marcador SÍ es accesible vía HTML (lo baja extraer_resultados.py al
SofaScoreClient), así que el ELO puede actualizarse en vivo aunque la API de
stats esté bloqueada por Cloudflare. (Incorporar STATS del Mundial al histórico
sigue bloqueado; ver Task 2.2/5.1.)

Pasos:
  1. Lee data/resultados.csv (partidos del Mundial; score_a; score_b; finished).
  2. Para los terminados aún no aplicados: actualiza data/elo_2026.csv
     (K=60 con multiplicador de margen de eloratings). Idempotente vía
     data/elo_aplicados.txt.
  3. Re-ejecuta el pipeline y la simulación del torneo con el ELO nuevo.

Uso (tras cada jornada o en cron diario):  python actualizar_torneo.py
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
K_MUNDIAL = 60
APLICADOS = DATA / "elo_aplicados.txt"


def _margen(diff_goles: int) -> float:
    """Multiplicador de margen de victoria (fórmula de eloratings.net)."""
    d = abs(diff_goles)
    if d <= 1:
        return 1.0
    if d == 2:
        return 1.5
    return (11 + d) / 8.0


def elo_update(elo_a: float, elo_b: float, ga: int, gb: int,
               k: float = K_MUNDIAL) -> tuple[float, float]:
    """Cambio de ELO (delta_a, delta_b) tras un partido. delta_b = -delta_a."""
    we = 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))
    w = 1.0 if ga > gb else (0.5 if ga == gb else 0.0)
    delta = k * _margen(ga - gb) * (w - we)
    return delta, -delta


def _leer_aplicados() -> set[str]:
    if not APLICADOS.exists():
        return set()
    return {l.strip() for l in APLICADOS.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> None:
    aplicados = _leer_aplicados()
    nuevos = []
    rpath = DATA / "resultados.csv"
    if rpath.exists():
        with rpath.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                fin = str(r.get("finished", "")).strip().lower()
                if fin in ("1", "true") and r["partido_id"] not in aplicados:
                    nuevos.append(r)
    if not nuevos:
        print("Sin resultados nuevos que aplicar.")
        return

    # Equipos por partido (de partidos_a_predecir) y ELO actual (elo_2026.csv).
    cruces = {}
    with (DATA / "partidos_a_predecir.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cruces[r["partido_id"]] = (r["equipo_a"].strip(), r["equipo_b"].strip())
    elo = {}
    with (DATA / "elo_2026.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            elo[r["equipo"].strip()] = float(r["elo"])

    for r in nuevos:
        pid = r["partido_id"]
        if pid not in cruces:
            print(f"  [WARN] {pid} no está en partidos_a_predecir; se ignora")
            continue
        a, b = cruces[pid]
        if a not in elo or b not in elo:
            print(f"  [WARN] {pid}: {a}/{b} sin ELO; se ignora")
            continue
        ga, gb = int(r["score_a"]), int(r["score_b"])
        da, db = elo_update(elo[a], elo[b], ga, gb)
        elo[a] += da
        elo[b] += db
        aplicados.add(pid)
        print(f"  {pid}: {a} {ga}-{gb} {b}  (ELO {a} {da:+.1f}, {b} {db:+.1f})")

    # Persistir ELO actualizado y registro de aplicados.
    with (DATA / "elo_2026.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["equipo", "elo"], delimiter=";")
        w.writeheader()
        for e, v in sorted(elo.items(), key=lambda kv: -kv[1]):
            w.writerow({"equipo": e, "elo": round(v)})
    APLICADOS.write_text("\n".join(sorted(aplicados)) + "\n", encoding="utf-8")

    # --solo-elo: el cron (actualizar.sh) re-predice después; evita duplicarlo.
    if "--solo-elo" in sys.argv:
        print(f"ELO actualizado ({len(nuevos)} resultados). Re-predicción la hace el cron.")
        return

    # Re-predecir con el ELO nuevo.
    subprocess.run([sys.executable, "-m", "predictor.cli"], check=True)
    subprocess.run([sys.executable, "-m", "predictor.tournament"], check=True)
    print("Re-predicción OK. Recargar la web: cd web && npm run db:seed")


if __name__ == "__main__":
    main()

"""Genera las lineas de crontab (Linux) para el auto-update del Mundial:

  - Cada 6h: red de seguridad.
  - Por cada partido (data/calendario.csv): a kickoff +1h y +2.5h.

Todas llaman al wrapper de Docker (deploy/actualizar_docker.sh).
EJECUTAR EN EL SERVIDOR (usa su zona horaria local para las horas).

    python3 deploy/generar_crontab.py            # imprime las lineas (revisar)
    python3 deploy/generar_crontab.py | crontab - # instalarlas (reemplaza el crontab)

Compatible con Python 3.8 (sin anotaciones de tipos modernas).
"""

import csv
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = "flock -w 900 /tmp/mundial_cron.lock %s" % (
    ROOT / "deploy" / "actualizar_docker.sh")
LOG = "/tmp/mundial_update.log"
# Relativo al inicio de cada partido: 2.5h y 1h ANTES (fijar árbitro + re-predecir
# con lo más fresco) y 1h y 2.5h DESPUÉS (recoger marcador/stats/telemetría/árbitro).
OFFSETS_MIN = [-150, -60, 60, 150]


def main():
    out = []
    out.append("# Mundial 2026 - auto-update (generado por generar_crontab.py)")
    out.append("# Red de seguridad cada 6h")
    out.append("0 */6 * * * %s >> %s 2>&1" % (WRAPPER, LOG))
    out.append("# Relativo al partido: kickoff -2.5h, -1h, +1h, +2.5h")

    triggers = []
    # calendario_completo.csv = los 104 partidos (grupos + eliminatorias).
    # Si no existe, cae a calendario.csv (solo los 72 de grupos).
    cal = ROOT / "data" / "calendario_completo.csv"
    if not cal.exists():
        cal = ROOT / "data" / "calendario.csv"
    with open(cal, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if not r.get("kickoff"):
                continue
            ko = int(r["kickoff"])
            for off in OFFSETS_MIN:
                t = dt.datetime.fromtimestamp(ko + off * 60)
                line = "%d %d %d %d * %s >> %s 2>&1" % (
                    t.minute, t.hour, t.day, t.month, WRAPPER, LOG,
                )
                triggers.append((t, line))

    triggers.sort(key=lambda x: x[0])
    for _, line in triggers:
        out.append(line)
    print("\n".join(out))


if __name__ == "__main__":
    main()

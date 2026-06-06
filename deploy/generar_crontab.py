"""Genera las líneas de crontab (Linux) para correr actualizar.sh ~2.5h después
de cada partido del Mundial, con las horas reales de data/calendario.csv.

EJECUTAR EN EL SERVIDOR (usa su zona horaria local para los timestamps).

    .venv/bin/python deploy/generar_crontab.py            # imprime las líneas
    .venv/bin/python deploy/generar_crontab.py | crontab -  # instalarlas

Alternativa simple (sin esto): una sola línea cada 2h ->
    0 */2 * * * /ruta/mundial/actualizar.sh >> /tmp/mundial_update.log 2>&1
"""

import csv
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFSET_MIN = 150
SCRIPT = ROOT / "actualizar.sh"
LOG = "/tmp/mundial_update.log"


def main():
    lineas = []
    with open(ROOT / "data" / "calendario.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if not r.get("kickoff"):
                continue
            t = dt.datetime.fromtimestamp(int(r["kickoff"]) + OFFSET_MIN * 60)
            lineas.append(
                (t, f"{t.minute} {t.hour} {t.day} {t.month} * {SCRIPT} >> {LOG} 2>&1")
            )
    lineas.sort(key=lambda x: x[0])
    print("# Auto-update post-partido del Mundial (kickoff + 2.5h)")
    for _, l in lineas:
        print(l)


if __name__ == "__main__":
    main()

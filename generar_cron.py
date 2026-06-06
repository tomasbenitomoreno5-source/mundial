"""Genera un LaunchAgent (launchd) que ejecuta actualizar.sh ~2.5h después del
inicio de cada partido del Mundial, usando las horas reales de data/calendario.csv.

Un solo plist con un StartCalendarInterval por partido (72). En macOS es la forma
nativa de "cron exacto".

Uso:
    .venv/bin/python generar_cron.py            # genera el plist
    launchctl load ~/Library/LaunchAgents/com.mundial.actualizar.plist
Para quitarlo:
    launchctl unload ~/Library/LaunchAgents/com.mundial.actualizar.plist
"""

import csv
import datetime as dt
import plistlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABEL = "com.mundial.actualizar"
OFFSET_MIN = 150  # 2.5h tras el inicio (partido + descanso + margen)


def main():
    triggers = []
    with open(ROOT / "data" / "calendario.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if not r.get("kickoff"):
                continue
            t = dt.datetime.fromtimestamp(int(r["kickoff"]) + OFFSET_MIN * 60)
            triggers.append(
                {"Month": t.month, "Day": t.day, "Hour": t.hour, "Minute": t.minute}
            )

    # PATH para que launchd encuentre npm/node (no hereda el shell).
    npm = shutil.which("npm")
    node_dir = str(Path(npm).parent) if npm else "/usr/local/bin"
    path = f"{node_dir}:/usr/local/bin:/usr/bin:/bin"

    plist = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(ROOT / "actualizar.sh")],
        "StartCalendarInterval": triggers,
        "EnvironmentVariables": {"PATH": path},
        "StandardOutPath": "/tmp/mundial_update.log",
        "StandardErrorPath": "/tmp/mundial_update.log",
        "RunAtLoad": False,
    }

    dest = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        plistlib.dump(plist, f)
    print(f"OK: {len(triggers)} disparadores post-partido -> {dest}")
    print("Cárgalo con:  launchctl load", dest)


if __name__ == "__main__":
    main()

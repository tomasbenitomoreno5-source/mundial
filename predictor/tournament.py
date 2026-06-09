"""Monte Carlo del torneo: probabilidad de cada selección de pasar de grupo,
llegar a cada ronda y ser campeona.

- **Fase de grupos**: se simula con las probabilidades 1X2 del propio modelo
  (predicciones_resumen_py.csv). Puntos 3/1/0; clasifican los 2 primeros de cada
  grupo + los 8 mejores terceros.
- **Eliminatorias**: como los cruces no están predeterminados, se modela un
  cuadro aleatorio entre los 32 clasificados y cada eliminatoria se resuelve por
  ELO (probabilidad logística estándar). Es una simplificación consciente: la
  fase de grupos usa el modelo; el cuadro asume emparejamiento aleatorio.

Salida: data/probabilidades_torneo.csv
  equipo;p_grupo;p_r16;p_qf;p_sf;p_final;p_campeon
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict

from . import config

N_SIM = 20000
SEED = config.SEED


def _load_matches() -> list[dict]:
    # Solo partidos de fase de grupos (la simulación del torneo parte de ahí).
    grupos = set()
    pred_path = config.DATA_DIR / "partidos_a_predecir.csv"
    if pred_path.exists():
        with open(pred_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r.get("fase", "grupos") == "grupos":
                    grupos.add(r["partido_id"])

    path = config.DATA_DIR / "predicciones_resumen_py.csv"
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if grupos and r["partido_id"] not in grupos:
                continue
            out.append(
                {
                    "a": r["equipo_a"].strip(),
                    "b": r["equipo_b"].strip(),
                    "p1": float(r["p_1"].replace(",", ".")),
                    "px": float(r["p_X"].replace(",", ".")),
                    "p2": float(r["p_2"].replace(",", ".")),
                }
            )
    return out


def _load_elo() -> dict[str, int]:
    path = config.DATA_DIR / "elo_2026.csv"
    elo = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            elo[r["equipo"].strip()] = int(r["elo"])
    return elo


def _derive_groups(matches: list[dict]) -> dict[str, list[str]]:
    """Componentes conexas del grafo 'A juega contra B' = grupos."""
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for m in matches:
        union(m["a"], m["b"])
    groups: dict[str, list[str]] = defaultdict(list)
    for t in {t for m in matches for t in (m["a"], m["b"])}:
        groups[find(t)].append(t)
    return dict(groups)


def _elo_pwin(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def simulate(n_sim: int = N_SIM, seed: int = SEED) -> dict[str, dict[str, int]]:
    matches = _load_matches()
    elo = _load_elo()
    groups = _derive_groups(matches)
    teams = sorted({t for m in matches for t in (m["a"], m["b"])})
    elo_of = {t: elo.get(t, config.ELO_DEFAULT) for t in teams}

    # Partidos por grupo (los que tenemos = round robin de cada grupo).
    group_of = {t: g for g, ts in groups.items() for t in ts}
    group_matches: dict[str, list[dict]] = defaultdict(list)
    for m in matches:
        group_matches[group_of[m["a"]]].append(m)

    rng = random.Random(seed)
    tally = {
        t: {
            "grupo": 0, "r16": 0, "qf": 0, "sf": 0, "final": 0, "campeon": 0,
            "first": 0, "second": 0, "ptsSum": 0.0,
        }
        for t in teams
    }

    for _ in range(n_sim):
        # --- Fase de grupos ---
        pts: dict[str, float] = defaultdict(float)
        for g, ms in group_matches.items():
            for m in ms:
                u = rng.random()
                if u < m["p1"]:
                    pts[m["a"]] += 3
                elif u < m["p1"] + m["px"]:
                    pts[m["a"]] += 1
                    pts[m["b"]] += 1
                else:
                    pts[m["b"]] += 3

        for t in teams:
            tally[t]["ptsSum"] += pts[t]

        clasificados: list[str] = []
        terceros: list[tuple[float, float, str]] = []
        for g, ts in groups.items():
            ordenado = sorted(ts, key=lambda t: (pts[t], rng.random()), reverse=True)
            tally[ordenado[0]]["first"] += 1
            tally[ordenado[1]]["second"] += 1
            clasificados.extend(ordenado[:2])
            t3 = ordenado[2]
            terceros.append((pts[t3], rng.random(), t3))
        # 8 mejores terceros
        terceros.sort(reverse=True)
        clasificados.extend(t for _, _, t in terceros[:8])

        for t in clasificados:
            tally[t]["grupo"] += 1

        # --- Eliminatorias: cuadro aleatorio resuelto por ELO ---
        rng.shuffle(clasificados)
        ronda_keys = ["r16", "qf", "sf", "final", "campeon"]
        vivos = clasificados
        for ronda in ronda_keys:
            ganadores = []
            for i in range(0, len(vivos), 2):
                a, b = vivos[i], vivos[i + 1]
                pa = _elo_pwin(elo_of[a], elo_of[b])
                ganador = a if rng.random() < pa else b
                ganadores.append(ganador)
                tally[ganador][ronda] += 1
            vivos = ganadores

    return tally


def main() -> None:
    tally = simulate()
    n = N_SIM
    rows = []
    for t, c in tally.items():
        rows.append(
            {
                "equipo": t,
                "p_grupo": round(c["grupo"] / n, 4),
                "p_r16": round(c["r16"] / n, 4),
                "p_qf": round(c["qf"] / n, 4),
                "p_sf": round(c["sf"] / n, 4),
                "p_final": round(c["final"] / n, 4),
                "p_campeon": round(c["campeon"] / n, 4),
                "p_1grupo": round(c["first"] / n, 4),
                "p_2grupo": round(c["second"] / n, 4),
                "pts_grupo": round(c["ptsSum"] / n, 2),
            }
        )
    rows.sort(key=lambda r: r["p_campeon"], reverse=True)
    out = config.DATA_DIR / "probabilidades_torneo.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "equipo",
                "p_grupo",
                "p_r16",
                "p_qf",
                "p_sf",
                "p_final",
                "p_campeon",
                "p_1grupo",
                "p_2grupo",
                "pts_grupo",
            ],
            delimiter=";",
        )
        w.writeheader()
        w.writerows(rows)
    top = ", ".join(f"{r['equipo']} {r['p_campeon']:.0%}" for r in rows[:5])
    print(f"Torneo OK: {len(rows)} selecciones -> {out.name}. Favoritas: {top}")


if __name__ == "__main__":
    main()

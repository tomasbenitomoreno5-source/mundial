"""Monte Carlo del torneo con el CUADRO REAL del Mundial 2026 (Task 3.5).

Antes: cuadro aleatorio + desempates a moneda + eliminatorias por ELO logístico.
Ahora:
- **Grupos oficiales** (data/grupos_oficiales.csv, verificado contra los cruces).
- **Fase de grupos** simulada muestreando el marcador exacto (data/marcadores_py.csv),
  con desempates reales: puntos → diferencia de goles → goles a favor.
- **Cuadro real de FIFA**: 1º/2º a slots fijos; 8 mejores terceros asignados por
  la tabla oficial de 495 combinaciones (data/cuadro_terceros.csv, Annex C).
- **Eliminatorias resueltas con el modelo de goles** (matriz Dixon-Coles desde
  lambdas ELO); empate a 90' → penaltis (moneda).

Salida: data/probabilidades_torneo.csv
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict

from . import config
from .simulate import dixon_coles_matrix, elo_lambdas
from .strength import get_elo

N_SIM = 20000
SEED = config.SEED

# --- Cuadro fijo del Mundial 2026 (extraído del bracket oficial) -----------
# R32: cada match -> (lado_a, lado_b). Referencias de grupo:
#   ("1", L) ganador grupo L · ("2", L) segundo grupo L · ("3", slot) tercero
#   asignado al slot de la tabla oficial (columnas 1A..1L de cuadro_terceros).
R32 = {
    73: (("2", "A"), ("2", "B")), 74: (("1", "E"), ("3", "1E")),
    75: (("1", "F"), ("2", "C")), 76: (("1", "C"), ("2", "F")),
    77: (("1", "I"), ("3", "1I")), 78: (("2", "E"), ("2", "I")),
    79: (("1", "A"), ("3", "1A")), 80: (("1", "L"), ("3", "1L")),
    81: (("1", "D"), ("3", "1D")), 82: (("1", "G"), ("3", "1G")),
    83: (("2", "K"), ("2", "L")), 84: (("1", "H"), ("2", "J")),
    85: (("1", "B"), ("3", "1B")), 86: (("1", "J"), ("2", "H")),
    87: (("1", "K"), ("3", "1K")), 88: (("2", "D"), ("2", "G")),
}
# Rondas siguientes: match -> (match_a, match_b). 103 (3er puesto) se omite.
LATER = {
    89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
    101: (97, 98), 102: (99, 100), 104: (101, 102),
}
# Ronda a la que llega el GANADOR de cada match (para el tally).
GANAR_DA = (
    {m: "r16" for m in R32}
    | {m: "qf" for m in (89, 90, 91, 92, 93, 94, 95, 96)}
    | {m: "sf" for m in (97, 98, 99, 100)}
    | {m: "final" for m in (101, 102)}
    | {104: "campeon"}
)


def _load_grupos() -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    with open(config.DATA_DIR / "grupos_oficiales.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            out[r["grupo"].strip()].append(r["equipo"].strip())
    return dict(out)


def _load_terceros() -> dict[str, dict[str, str]]:
    """combo (8 letras ordenadas) -> {slot '1A'..'1L': letra del grupo del tercero}."""
    slots = ["1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"]
    out = {}
    with open(config.DATA_DIR / "cuadro_terceros.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            out[r["combo"]] = {s: r[s] for s in slots}
    return out


def _load_marcadores() -> dict[str, list[tuple[int, int, float]]]:
    out: dict[str, list[tuple[int, int, float]]] = defaultdict(list)
    with open(config.DATA_DIR / "marcadores_py.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            out[r["partido_id"]].append(
                (int(r["a"]), int(r["b"]), float(r["prob"].replace(",", ".")))
            )
    return out


def _load_partidos_grupo() -> dict[str, list[dict]]:
    """grupo-letra -> lista de partidos (partido_id, a, b) de fase de grupos."""
    eq2grupo = {e: g for g, es in _load_grupos().items() for e in es}
    out: dict[str, list[dict]] = defaultdict(list)
    with open(config.DATA_DIR / "partidos_a_predecir.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r.get("fase", "grupos") != "grupos":
                continue
            a, b = r["equipo_a"].strip(), r["equipo_b"].strip()
            g = eq2grupo.get(a)
            if g and eq2grupo.get(b) == g:
                out[g].append({"id": r["partido_id"], "a": a, "b": b})
    return out


def _muestrear(dist: list[tuple[int, int, float]], rng: random.Random) -> tuple[int, int]:
    """Muestrea un marcador (ga, gb) de la distribución (normalizada)."""
    total = sum(p for _, _, p in dist)
    u = rng.random() * total
    acc = 0.0
    for ga, gb, p in dist:
        acc += p
        if u <= acc:
            return ga, gb
    return dist[-1][0], dist[-1][1]


def _ganador_ko(a: str, b: str, rng: random.Random) -> str:
    """Resuelve una eliminatoria con el modelo de goles (DC desde ELO)."""
    la, lb = elo_lambdas(get_elo(a), get_elo(b))
    M = dixon_coles_matrix(la, lb)
    u = rng.random()
    acc = 0.0
    k = M.shape[0]
    for i in range(k):
        for j in range(k):
            acc += M[i, j]
            if u <= acc:
                if i > j:
                    return a
                if j > i:
                    return b
                return a if rng.random() < 0.5 else b  # penaltis
    return a if rng.random() < 0.5 else b


def simulate(n_sim: int = N_SIM, seed: int = SEED) -> dict[str, dict]:
    grupos = _load_grupos()
    terceros_tab = _load_terceros()
    marcadores = _load_marcadores()
    partidos_grupo = _load_partidos_grupo()
    teams = [t for ts in grupos.values() for t in ts]

    rng = random.Random(seed)
    claves = ["grupo", "r16", "qf", "sf", "final", "campeon", "first", "second", "ptsSum"]
    tally = {t: {k: 0.0 for k in claves} for t in teams}

    for _ in range(n_sim):
        pts = defaultdict(float)
        gf = defaultdict(int)
        gd = defaultdict(int)
        for g, ms in partidos_grupo.items():
            for m in ms:
                dist = marcadores.get(m["id"])
                if not dist:
                    continue
                ga, gb = _muestrear(dist, rng)
                gf[m["a"]] += ga; gf[m["b"]] += gb
                gd[m["a"]] += ga - gb; gd[m["b"]] += gb - ga
                if ga > gb:
                    pts[m["a"]] += 3
                elif gb > ga:
                    pts[m["b"]] += 3
                else:
                    pts[m["a"]] += 1; pts[m["b"]] += 1

        for t in teams:
            tally[t]["ptsSum"] += pts[t]

        # Clasificación de cada grupo (pts, dif goles, goles a favor, azar)
        pos1, pos2, pos3 = {}, {}, {}
        terceros = []  # (pts, gd, gf, rand, equipo, grupo)
        for g, ts in grupos.items():
            orden = sorted(ts, key=lambda t: (pts[t], gd[t], gf[t], rng.random()), reverse=True)
            pos1[g], pos2[g], pos3[g] = orden[0], orden[1], orden[2]
            tally[orden[0]]["first"] += 1
            tally[orden[1]]["second"] += 1
            terceros.append((pts[orden[2]], gd[orden[2]], gf[orden[2]], rng.random(), orden[2], g))

        # 8 mejores terceros → combo → asignación oficial de slots
        terceros.sort(reverse=True)
        mejores = terceros[:8]
        grupos_3 = sorted(t[5] for t in mejores)
        combo = "".join(grupos_3)
        asign = terceros_tab.get(combo)  # {slot '1A': letra grupo tercero}
        pos3_por_grupo = {t[5]: t[4] for t in mejores}

        clasificados = list(pos1.values()) + list(pos2.values()) + [t[4] for t in mejores]
        for t in clasificados:
            tally[t]["grupo"] += 1

        # --- Resolver el cuadro ---
        winners: dict[int, str] = {}

        def equipo_de(ref):
            tipo, val = ref
            if tipo == "1":
                return pos1[val]
            if tipo == "2":
                return pos2[val]
            if tipo == "3":  # val = slot '1A'..'1L'; asign da la letra del grupo
                if not asign:
                    return None
                return pos3_por_grupo.get(asign[val])
            if tipo == "W":
                return winners.get(val)
            return None

        for m in range(73, 89):
            a = equipo_de(R32[m][0]); b = equipo_de(R32[m][1])
            if a is None or b is None:
                continue
            w = _ganador_ko(a, b, rng)
            winners[m] = w
            tally[w][GANAR_DA[m]] += 1

        for m in (89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 104):
            ma, mb = LATER[m]
            a = winners.get(ma); b = winners.get(mb)
            if a is None or b is None:
                continue
            w = _ganador_ko(a, b, rng)
            winners[m] = w
            tally[w][GANAR_DA[m]] += 1

    return tally


def main() -> None:
    tally = simulate()
    n = N_SIM
    rows = []
    for t, c in tally.items():
        rows.append({
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
        })
    rows.sort(key=lambda r: r["p_campeon"], reverse=True)
    out = config.DATA_DIR / "probabilidades_torneo.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["equipo", "p_grupo", "p_r16", "p_qf", "p_sf", "p_final",
                        "p_campeon", "p_1grupo", "p_2grupo", "pts_grupo"],
            delimiter=";",
        )
        w.writeheader()
        w.writerows(rows)
    top = ", ".join(f"{r['equipo']} {r['p_campeon']:.0%}" for r in rows[:5])
    print(f"Torneo OK: {len(rows)} selecciones -> {out.name}. Favoritas: {top}")


if __name__ == "__main__":
    main()

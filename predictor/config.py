"""Configuración y constantes del motor.

En el script R original todo esto vivía hardcodeado a lo largo de las 1.800
líneas. Aquí se centraliza para que cambiar un parámetro o un rating ELO no
implique tocar la lógica.
"""

from __future__ import annotations

from pathlib import Path

# --- Rutas -----------------------------------------------------------------
# Los datos (raw scrape + inputs/outputs del modelo) viven en data/. El seed de
# la web los carga desde ahí; la DB (Prisma/SQLite) es la fuente canónica.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
STATS_CSV = DATA_DIR / "stats_final.csv"
TELEMETRIA_CSV = DATA_DIR / "telemetria_final.csv"
PARTIDOS_CSV = DATA_DIR / "partidos_a_predecir.csv"
REPARTO_MITADES_CSV = DATA_DIR / "reparto_mitades.csv"  # cuota 1ª parte por métrica
EQUIPOS_EXCLUIDOS_CSV = DATA_DIR / "equipos_excluidos.csv"  # clubes/no-selecciones a purgar
ARBITROS_CSV = DATA_DIR / "arbitros.csv"      # tasas por árbitro (carrera + pool)
CALENDARIO_CSV = DATA_DIR / "calendario.csv"  # árbitro designado por partido

# --- Efecto árbitro (Task 4.1 + 6.2): escala amarillas y faltas del partido --
ARBITRO_MIN_CARRERA = 30   # mínimo de partidos de carrera para fiarse de la tasa
ARBITRO_MIN_POOL = 5       # mínimo de partidos de pool para faltas
ARBITRO_CAP_AMARILLAS = (0.80, 1.20)  # un árbitro mueve ±20% las amarillas
ARBITRO_CAP_FALTAS = (0.88, 1.12)     # las faltas dependen menos del árbitro
PARTIDO_FECHAS_CSV = DATA_DIR / "partido_fechas.csv"  # fecha/torneo por partido_id (backfill)

# --- Semilla reproducible (Monte Carlo) ------------------------------------
SEED = 20260611

# --- Parámetros globales ---------------------------------------------------
K_KNN = 8          # vecinos por equipo
KNN_MIN_PARTIDOS = 5  # mínimo de partidos para poder SER vecino (no para ser predicho)
N_SIM = 20_000     # simulaciones Monte Carlo por partido
MIN_TITULAR = 80   # minutos asumidos para titulares
SHRINK_PRIOR = 0.05
SHRINK_N = 3

# --- Recencia (mejora #8, desbloqueada por partido_fechas.csv) -------------
# Peso 0.5^(Δdías/half_life): un partido de hace `half_life` días pesa la mitad.
# 730d elegido por backtest (2026-06-13): half_life corto empeora (descarta
# demasiado para selecciones, que juegan ~10 partidos/año); 730d da el mejor
# log-loss 1X2 (0.9368 vs 0.9418 sin recencia). Re-calibrable en Task 3.1.
RECENCIA_HALF_LIFE_DIAS = 730

# Peso de los amistosos en el pool (menos informativos: rotaciones, ritmo bajo).
# Calibrable por backtest.
PESO_AMISTOSO = 0.6

# --- Pesos del pool (construir_pool) ---------------------------------------
POOL_ALPHA = 0.30   # filas del propio equipo
POOL_BETA = 0.25    # propio vs rivales estilo-rival
POOL_GAMMA = 0.45   # equipos estilo-propio vs estilo-rival
POOL_BANDWIDTH = 0.6
POOL_MASA_THRESHOLD = 0.05

# --- Blend goles ELO/pool --------------------------------------------------
W_FIFA = 0.70       # 0.70 ELO + 0.30 pool (solo goles). Calibrado por backtest
                    # (Task 3.1): el ELO predice goles mejor que el pool; óptimo
                    # interior en 0.70 (0.40→0.926, 0.70→0.909, 1.0→0.917).
ELO_TOTAL_ESPERADO = 2.65  # calibrado por backtest (2026-06-14): 2.65 mejora el
# log-loss 1X2 (0.9265→0.9255) y elimina el sesgo de O/U goles (+2pp→0pp) sin
# empeorar el Brier. Barrido 2.55/2.65/2.75/2.85.
ELO_GOLES_POR_100PTS = 0.3  # 100 pts ELO ≈ 0.3 goles en venue neutral
ELO_DEFAULT = 1400  # ELO efectivo para equipos sin rating

# --- Dixon-Coles -----------------------------------------------------------
RHO_DC = -0.08
MAX_GOLES_DC = 6

# --- Sharpening de lambdas (corrige la infra-dispersión del 1X2) -----------
# El modelo era "tímido": comprimía el 1X2 hacia 33/33/33 (backtest 2026-06-14:
# cuando decía 50-70% para un lado, la realidad pasaba +10/13pp más). Se separa
# la diferencia (λ_fuerte − λ_débil) por este factor manteniendo el total
# (λ_a+λ_b) fijo, así afila 1X2/marcadores/BTTS sin tocar el O/U de goles.
# k=1.0 → sin efecto (comportamiento previo / legacy). Calibrado por backtest
# (2026-06-14): k=1.10 da el mejor log-loss 1X2 (0.9288→0.9265) y cierra el gap
# de calibración del favorito (+3pp→0) sin tocar O/U goles ni BTTS. La timidez
# real (vs resultados) era leve (+3pp), no los 14pp del mercado.
LAMBDA_SHARP_K = 1.10

# --- Quality-of-opposition (QoO) -------------------------------------------
QOO_CAP_PCT = 0.35
METRICAS_QOO = ("goles", "total_shots", "corner_kicks")  # xG fuera: 52% NA imputado
# Métricas que se mueven SOLIDARIAMENTE con su métrica madre en el QoO: al
# reescalar `total_shots` se escala su familia por el mismo factor por fila, así
# se preserva la identidad (a puerta + fuera + bloqueados = totales; dentro +
# fuera del área = totales). Sin esto, el QoO rompía la jerarquía (Task 3.4).
FAMILIAS_QOO = {
    "total_shots": ("shots_on_target", "shots_off_target", "shots_inside_box",
                    "shots_outside_box", "blocked_shots"),
}

# --- ELO 2026 (eloratings.net snapshot 14 mayo 2026), 48 mundialistas ------
# Fuente ÚNICA: data/elo_2026.csv (antes había un dict hardcoded duplicado que
# podía divergir del CSV que usa tournament.py). El loop en vivo (Task 4.3)
# actualiza ese CSV con cada resultado, así que cargarlo aquí mantiene una sola
# verdad. Nombres mapeados al canon del dataset (inglés de SofaScore).
ELO_2026_CSV = DATA_DIR / "elo_2026.csv"


def _load_elo_2026() -> dict[str, int]:
    import csv

    with open(ELO_2026_CSV, encoding="utf-8-sig") as f:
        return {r["equipo"].strip(): int(r["elo"])
                for r in csv.DictReader(f, delimiter=";")}


ELO_2026: dict[str, int] = _load_elo_2026()

# ELO de TODAS las selecciones (eloratings.net completo, Task 2.4). Da una
# coordenada de fuerza no-circular a los ~140 no-mundialistas del dataset, que
# antes solo tenían z_interna. ELO_2026 (snapshot mayo) manda para los 48.
ELO_MUNDO_CSV = DATA_DIR / "elo_mundo.csv"


def _load_elo_mundo() -> dict[str, int]:
    import csv

    if not ELO_MUNDO_CSV.exists():
        return {}
    with open(ELO_MUNDO_CSV, encoding="utf-8-sig") as f:
        return {r["equipo"].strip(): int(r["elo"])
                for r in csv.DictReader(f, delimiter=";")}


ELO_MUNDO: dict[str, int] = _load_elo_mundo()

# --- Métricas de equipo a modelar (orden canónico del R) -------------------
METRICAS_EQUIPO = (
    "goles", "expected_goals", "total_shots", "shots_on_target",
    "shots_off_target", "shots_inside_box", "shots_outside_box",
    "blocked_shots",
    "corner_kicks", "free_kicks", "throw-ins", "goal_kicks",
    "yellow_cards", "red_cards", "fouls", "offsides",
    "tackles", "total_tackles", "interceptions", "passes",
    "accurate_passes", "ball_possession", "big_chances",
    "goalkeeper_saves", "aerial_duels", "ground_duels", "dribbles",
    "duels", "dispossessed", "recoveries", "clearances", "long_balls",
    "crosses",
)

# Columnas de eventos raros: NA -> 0 (NA = "no ocurrió")
COLS_RARAS_STATS = (
    "red_cards", "penalty_saves", "goals_prevented",
    "errors_lead_to_a_goal", "errors_lead_to_a_shot",
    "big_chances_scored", "big_chances_missed", "through_balls",
    "punches", "big_saves", "high_claims", "hit_woodwork", "big_chances",
)

# Eventos raros con shrinkage hacia la media global (Poisson en la sim)
COLS_RARAS_SHRINK = (
    "red_cards", "big_chances_missed", "penalty_saves",
    "errors_lead_to_a_goal", "errors_lead_to_a_shot", "hit_woodwork",
    "goals_prevented",
)

# --- Líneas Over/Under (Task 6.4) ------------------------------------------
# Rango de offsets semienteros alrededor de floor(media). Más amplio que el
# original (-3..5) para ofrecer más líneas; las triviales se cortan por prob.
LINEA_OFFSET_MIN = -6
LINEA_OFFSET_MAX = 9
# No se guardan líneas cuya prob over caiga fuera de [trivial, 1-trivial]:
# nadie apuesta un over al 99%. Adapta el rango efectivo a cada mercado.
LINEA_PROB_TRIVIAL = 0.03
# Para mercados de JUGADOR el corte es más laxo: los jugadores de poco minutaje
# producen poco, así que con 0.03 solo sobrevivía la línea 0.5. Con 0.015 salen
# 1-2 líneas más (la cola larga) sin llenar de ruido al 0%.
LINEA_PROB_TRIVIAL_JUGADOR = 0.015

# Métricas ofrecidas como Over/Under (líneas X+0.5)
METRICAS_OU = (
    "goles", "corner_kicks", "yellow_cards", "fouls",
    "total_shots", "shots_on_target", "shots_off_target",
    "shots_inside_box", "shots_outside_box", "blocked_shots",
    "offsides", "tackles", "goalkeeper_saves",
    "free_kicks", "throw-ins", "goal_kicks",
    "passes", "accurate_passes",
)

# --- Mercados por mitad (1ª/2ª parte) --------------------------------------
# Métricas viables por mitad (se reparte la simulación de partido completo según
# la cuota real de 1ª parte; ver extraer_reparto_mitades.py).
METRICAS_OU_MITAD = (
    "goles", "total_shots", "shots_on_target",
    "corner_kicks", "yellow_cards", "fouls",
)
# Cuota de 1ª parte por defecto (fallback si falta reparto_mitades.csv). Valores
# de prior futbolístico: en 2ª parte se marca/dispara/amonesta algo más.
REPARTO_1H_DEFAULT: dict[str, float] = {
    "goles": 0.45, "total_shots": 0.47, "shots_on_target": 0.47,
    "corner_kicks": 0.48, "yellow_cards": 0.40, "fouls": 0.49,
}

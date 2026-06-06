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

# --- Semilla reproducible (Monte Carlo) ------------------------------------
SEED = 20260611

# --- Parámetros globales ---------------------------------------------------
K_KNN = 8          # vecinos por equipo
N_SIM = 20_000     # simulaciones Monte Carlo por partido
MIN_TITULAR = 80   # minutos asumidos para titulares
SHRINK_PRIOR = 0.05
SHRINK_N = 3

# --- Pesos del pool (construir_pool) ---------------------------------------
POOL_ALPHA = 0.30   # filas del propio equipo
POOL_BETA = 0.25    # propio vs rivales estilo-rival
POOL_GAMMA = 0.45   # equipos estilo-propio vs estilo-rival
POOL_BANDWIDTH = 0.6
POOL_MASA_THRESHOLD = 0.05

# --- Blend goles ELO/pool --------------------------------------------------
W_FIFA = 0.40       # 0.40 ELO + 0.60 pool (solo goles)
ELO_TOTAL_ESPERADO = 2.55
ELO_GOLES_POR_100PTS = 0.3  # 100 pts ELO ≈ 0.3 goles en venue neutral
ELO_DEFAULT = 1400  # ELO efectivo para equipos sin rating

# --- Dixon-Coles -----------------------------------------------------------
RHO_DC = -0.08
MAX_GOLES_DC = 6

# --- Quality-of-opposition (QoO) -------------------------------------------
QOO_CAP_PCT = 0.35
METRICAS_QOO = ("goles", "total_shots", "corner_kicks", "expected_goals")

# --- ELO 2026 (eloratings.net snapshot 14 mayo 2026), 48 mundialistas ------
# Nombres mapeados al canon del dataset (inglés de SofaScore).
ELO_2026: dict[str, int] = {
    "Spain": 2165, "Argentina": 2113, "France": 2081, "England": 2020,
    "Brazil": 1984, "Portugal": 1984, "Colombia": 1975, "Netherlands": 1961,
    "Ecuador": 1933, "Croatia": 1930, "Germany": 1923, "Norway": 1912,
    "Japan": 1904, "Türkiye": 1902, "Uruguay": 1892, "Switzerland": 1889,
    "Senegal": 1878, "Belgium": 1866, "Mexico": 1858, "Paraguay": 1833,
    "Austria": 1827, "Morocco": 1821, "Canada": 1784, "Australia": 1783,
    "Scotland": 1767, "Iran": 1760, "South Korea": 1752, "Algeria": 1743,
    "Panama": 1737, "Uzbekistan": 1727, "Czechia": 1726, "USA": 1721,
    "Sweden": 1719, "Jordan": 1690, "Egypt": 1689,
    "Côte d'Ivoire": 1676, "DR Congo": 1655, "Tunisia": 1636,
    "Iraq": 1607, "Bosnia & Herzegovina": 1594, "New Zealand": 1585,
    "Saudi Arabia": 1568, "Cabo Verde": 1549, "Haiti": 1532,
    "South Africa": 1524, "Ghana": 1505, "Curaçao": 1436, "Qatar": 1425,
}

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

# Métricas ofrecidas como Over/Under (líneas X+0.5)
METRICAS_OU = (
    "goles", "corner_kicks", "yellow_cards", "fouls",
    "total_shots", "shots_on_target", "shots_off_target",
    "shots_inside_box", "shots_outside_box", "blocked_shots",
    "offsides", "tackles", "goalkeeper_saves",
    "free_kicks", "throw-ins", "goal_kicks",
    "passes", "accurate_passes",
)

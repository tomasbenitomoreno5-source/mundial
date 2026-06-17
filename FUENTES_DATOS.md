# Procedencia de los datos (tras la migración SofaScore → fuentes múltiples)

Registro de DE DÓNDE sale cada dato. Estado: migración en curso (extractores nuevos
escriben a ficheros *scratch* hasta el cutover). Detalle del plan en `MIGRACION_FUENTES.md`.

## Resumen por fuente

| Fuente | Acceso | Qué aporta | Cliente |
|---|---|---|---|
| **ESPN** (`site.api.espn.com/.../fifa.world/`) | API oculta, sin key, sin bloqueo | fixtures, resultados, stats de equipo (goles, tiros, córners, faltas, tarjetas, posesión, pases, tackles, intercepciones, despejes, balones largos, centros, paradas, offsides), eventos (minuto+mitad), alineaciones, árbitro del partido | `predictor/sources/espn.py` |
| **FotMob** (`/api/data/matchDetails`) | sin token (hoy) | **xG de equipo por partido** (JSON fiable; sustituye a xgscore) | `predictor/sources/fotmob.py` |
| **FotMob** (`/api/data/matchDetails`) | sin token (hoy); frágil | telemetría rica de jugador (rating, pases, duelos, tackles, aéreos, recuperaciones, toques, xG jugador) | `predictor/sources/fotmob.py` |
| **Wikipedia** (API MediaWiki) | API pública | designaciones de árbitro (partidos futuros) | `predictor/sources/wikipedia_refs.py` |
| **worldreferee.com** | scraping | stats de carrera del árbitro (partidos, amarillas, rojas, 2ª amarillas) | `predictor/sources/worldreferee.py` |
| **Transfermarkt** *(pendiente)* | self-host / dump | valor de mercado + pie del jugador | `predictor/sources/transfermarkt.py` |
| **The Odds API** | API con key (ya existía) | cuotas 1X2 + O/U goles | `predictor/odds_theoddsapi.py` |
| **eloratings.net** | (ya existía) | ELO de selecciones | `extraer_elo_*` |
| `predictor/sofascore.py` | **LEGACY** (bloqueado) | — (archivado; conserva caché histórica) | — |

## Por fichero de salida

| Fichero | Columna(s) | Fuente | Extractor (scratch → real en cutover) |
|---|---|---|---|
| `stats_final.csv` | goles, total_shots, shots_on/off_target, blocked_shots, corner_kicks, fouls, yellow/red_cards, offsides, passes, accurate_passes, ball_possession, tackles, total_tackles, interceptions, clearances, long_balls, crosses, goalkeeper_saves | **ESPN** | `extraer_stats_espn.py` (→ `stats_espn_nuevos.csv`) |
| `stats_final.csv` | **expected_goals** | **FotMob** team xG (best-effort; xgscore descartado por intermitente) | `extraer_stats_espn.py` |
| `stats_final.csv` | free_kicks, throw-ins, goal_kicks, big_chances*, duelos, regates, dispossessed, recoveries, through_balls, etc. | — (VACÍO; ESPN no los da; el modelo no los usa) | — |
| `resultados.csv` | partido_id, score_a, score_b, finished | **ESPN** | `extraer_resultados_espn.py` (→ `resultados_espn.csv`) |
| `calendario.csv` | referee_name, referee_id | **ESPN** (jugados, ground-truth) + **Wikipedia** (futuros) | `extraer_designaciones_espn.py` (→ `calendario_espn.csv`) |
| `arbitros.csv` | partidos_carrera, amarillas, rojas, dobles_amarillas | **worldreferee** | `extraer_arbitros_wr.py` (→ `arbitros_wr.csv`) |
| `arbitros.csv` | *_pool (casa/fuera, 1ª/2ª, faltas, penaltis) | **histórico** + reconstrucción 2026 de eventos ESPN | `extraer_pool_arbitro_espn.py` + `extraer_arbitros.py --merge` |
| `telemetria_full.csv` | rating, pases, duelos, tackles… (jugador) | **FotMob** (incl. xG de jugador) | `extraer_plantillas_espn.py` ✅ |
| `bios.csv` | valor de mercado, pie | **Transfermarkt** *(pendiente)* | `extraer_bios` (pendiente) |
| `partido_fechas.csv` | fecha, torneo | **ESPN** *(extractor pendiente)* | `extraer_fechas` (pendiente) |
| `cuotas_mercado.csv` | cuotas | **The Odds API** | `odds_theoddsapi.py` (ya existía) |
| `elo_2026.csv`, `elo_mundo.csv` | ELO | **eloratings.net** | `extraer_elo_*` (ya existía) |

## Notas
- **El modelo NO usa `expected_goals` hoy** (calcula fuerza con goles+ELO; O/U con
  goles/córners/tarjetas/faltas/tiros). El xG se recoge para una mejora futura (ver
  `MIGRACION_FUENTES.md`).
- **Fiabilidad de los avisos** (cron → Telegram): cada extractor emite `exit 0/3/1`
  (ok/degradado/fallo). xgscore caído → ⚠️; equipo sin mapear → ⚠️; gap menor de xG → solo log.

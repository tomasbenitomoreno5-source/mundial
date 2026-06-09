# `data/` — raw cache de datos

Esta carpeta es la **caché cruda** que sirve de puente entre el mundo Python
(scrapers + motor) y el mundo Node/Prisma (web). **No es la fuente canónica de
consulta**: lo canónico vive en SQLite (`web/prisma/dev.db`) tras el seed; aquí
solo están los CSV/JSONL intermedios.

Se mantiene como caché a propósito: el scraping es lento y con rate-limit, así
que separar "raspar" de "cargar a la DB" permite re-seedear en segundos sin
volver a raspar.

## Qué hay

**Inputs del modelo** (los lee `predictor/` vía `config.DATA_DIR`):
- `stats_final.csv` — stats de equipo por partido (histórico).
- `telemetria_final.csv` — telemetría de las 58 estrellas (legacy; ver `telemetria_full.csv`).
- `partidos_a_predecir.csv` — los 72 cruces del Mundial.

**Golden del R** (regresión en `tests/`):
- `predicciones_resumen.csv`, `predicciones_largo.csv`, `debug_knn.csv`, `debug_perfiles.csv`.

**Outputs del motor** (los escribe `predictor.pipeline.write_outputs`):
- `predicciones_resumen_py.csv`, `predicciones_largo_py.csv`.

**Raw scrape (jugadores)**:
- `telemetria_full.csv` (+ `.jsonl` resumable) — plantillas completas (`extraer_plantillas.py`).
- `convocatorias.csv` (+ `.jsonl`) — convocatoria actual por selección (`extraer_convocatorias.py`).
- `elo_2026.csv` — ELO volcado de `predictor/config.py`.

## El loader único: `web/prisma/seed.ts`

**Todo lo que llega a la DB pasa por el seed**, que lee de esta carpeta
(`ROOT = ../data`) y escribe en SQLite vía Prisma. Prisma es el único dueño del
schema (migraciones). Ningún otro proceso escribe en la DB.

```
scrapers (.py) ─┐
motor (.py) ────┼─► data/*.csv ─► web/prisma/seed.ts ─► SQLite (canónico) ─► web
                ┘
```

Regenerar la DB: `cd web && npm run db:seed`.

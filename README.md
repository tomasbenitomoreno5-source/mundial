# Predictor Mundial 2026

Plataforma de predicciones probabilísticas para los 72 partidos del Mundial
2026. Port a Python del motor estadístico original en R + base de datos + web.

## Arquitectura

```
scrapers (.py, Playwright) ─┐
  · extraer.py / extraer_plantillas.py / extraer_convocatorias.py
motor de predicción (predictor/, port del R) ─┤
                                              ▼
                                  data/  (raw cache: CSV/JSONL)
                                              │
                          loader único: web/prisma/seed.ts
                                              │
                                SQLite (Prisma) — fuente canónica
                                              │
                                       web Next.js (web/)
```

Todos los datos viven en `data/` (raw cache, ver `data/README.md`); lo que se
**consulta** vive en SQLite tras el seed, que es el **único** proceso que
escribe en la DB. La web muestra: predicciones de los 72 partidos con sus
mercados de equipo y de jugador, y una sección de selecciones (estilo, perfiles,
historial y plantilla/convocatoria).

El motor R original (`predictor_mundial_2026.R`) se conserva como referencia
("golden output"): la suite de tests verifica que el port Python reproduce sus
resultados dentro de tolerancia Monte Carlo.

## Motor de predicción (Python)

Paquete `predictor/`, un módulo por responsabilidad:

| Módulo | Qué hace |
|---|---|
| `config.py` | Constantes y parámetros (ELO, pesos, semilla) — antes hardcodeados en el R |
| `dataset.py` | Carga + limpieza de CSVs (bloques 1-2 del R) |
| `style.py` | Vector de estilo + PCA + KNN (bloque 4) |
| `strength.py` | Fuerza interna + ELO (bloque 4b) |
| `pool.py` | Pool α/β/γ + ajuste por calidad del rival (bloque 5.1, mejora #2) |
| `simulate.py` | Bootstrap MC + Dixon-Coles + lambdas ELO (bloque 5) |
| `markets.py` | Mercados núcleo: 1X2, doble oportunidad, BTTS, Over/Under |
| `pipeline.py` | Orquesta los 72 partidos y arma las salidas |
| `cli.py` | Entrypoint |

### Ejecutar

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m predictor.cli        # genera predicciones_*_py.csv
.venv/bin/python -m pytest               # 28 tests (incl. regresión vs R)
```

Fidelidad verificada contra el golden del R: KNN idéntico (8/8 vecinos),
MAE ≈ 0.004 en 1X2/BTTS/goles/córners, correlación ≈ 1.0.

## Web (Next.js + Prisma + SQLite)

```bash
cd web
npm install
npx prisma migrate dev      # crea + migra SQLite
npm run db:seed             # carga predicciones_*_py.csv en la DB
npm run dev                 # http://localhost:3000
```

Páginas: lista de partidos agrupados por fecha (con 1X2/BTTS/goles) y detalle
por partido con todos los mercados núcleo.

## Estado y fases

- **Fase 1 (hecha):** motor Python con mercados núcleo + DB + web MVP.
- **Fase 2 (pendiente):** cola larga de mercados (marcador exacto, hándicaps,
  HT/FT, mercados de jugador), apartado "Resultados/acierto del modelo" (cuando
  se jueguen los partidos), página de metodología.

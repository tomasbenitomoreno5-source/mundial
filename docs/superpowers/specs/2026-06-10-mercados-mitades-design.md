# Diseño A: Mercados de 1ª / 2ª parte

Fecha: 2026-06-10
Estado: aprobado (pendiente de revisión del spec)

## Objetivo

Añadir mercados por mitad (1ª parte / 2ª parte) a los mercados de equipo que ya
existen, para las métricas viables: goles, tiros, tiros a puerta, córners,
tarjetas (amarillas) y faltas — por equipo (A/B) y total. Además, **1X2 de 1ª
parte** y **BTTS de 1ª parte**. Solo visualización/predicción; no cambia la
metodología de los mercados a partido completo (FT), que se conservan idénticos.

## Hechos verificados (API SofaScore)

- `event/{id}/statistics` devuelve `statistics` con tres periodos: `ALL`,
  `1ST`, `2ND`. Cada periodo trae los valores por equipo de: Total shots, Shots
  on target, Shots off target, Corner kicks, Fouls, Yellow cards, Offsides,
  Goalkeeper saves, Passes, etc. (≈39 ítems en 1ST).
- Goles por mitad: del marcador por periodo del evento (`homeScore.period1/2`,
  `awayScore.period1/2`) o de los minutos de gol en `event/{id}/incidents`.
- El motor (`predictor/`) ya simula estas métricas a partido completo por
  bootstrap del pool histórico de cada equipo (`simulate.simular_partido_bootstrap`)
  y deriva Over/Under en `markets.calcular_mercados`.

## Arquitectura

```
extraer_stats_mitades.py  →  data/stats_mitades.csv  (pool por equipo y periodo)
                                      │
            dataset.py (carga pools por periodo: 1H / 2H)
                                      │
   simulate.py / markets.py  (bootstrap + O/U por periodo; 1X2/BTTS 1ª parte)
                                      │
        predicciones_largo_py.csv  (+ columna `periodo`: FT | 1H | 2H)
                                      │
            web/prisma/seed.ts  →  Market.periodo (+ migración)
                                      │
            web: selector de periodo en la página de partido
```

## Componentes

### 1. Scraper — `extraer_stats_mitades.py` (nuevo, resumable)

Mismo patrón que el resto (Playwright, user-agent, `get()` con reintentos).
Por cada `partido_id` del pool (los de `telemetria_full.csv` / el stats pool):

- `event/{id}/statistics` → para `1ST` y `2ND`, extraer por equipo los ítems
  mapeados a las métricas canónicas de `config.METRICAS_EQUIPO` (las que existen
  por mitad). Mapeo de nombres SofaScore → canon (reutilizar el de `extraer.py`).
- Goles por mitad: del marcador por periodo del evento (`event/{id}`).
- Salida `data/stats_mitades.csv`: una fila por (partido, equipo, periodo) con
  las mismas columnas-métrica que el pool a partido completo + columna `periodo`
  (`1H` | `2H`). Resumable vía `data/stats_mitades.jsonl`.

Coste: ~1111 partidos × 1 llamada `statistics`. Resumable; se añade a
`actualizar.sh` como paso opcional (los pools por mitad cambian poco).

### 2. Carga de datos — `dataset.py`

Cargar `stats_mitades.csv` y exponer, además del pool a partido completo, dos
pools por equipo: `pool_1h` y `pool_2h` (mismo esquema de columnas). Limpieza /
relleno de NA idéntico al pool FT (eventos raros → 0, shrinkage donde aplica).

### 3. Motor — `simulate.py` / `markets.py`

- `simular_partido_bootstrap` se invoca por periodo con el pool correspondiente,
  produciendo `MatchSim` para 1H y 2H. Para **goles por mitad** se usa el blend
  ELO escalado por el reparto histórico de goles por mitad (≈45% 1H / 55% 2H,
  parametrizado en `config`), manteniendo Dixon-Coles dentro de cada mitad.
- `calcular_mercados` recibe un `periodo` y emite las filas con ese valor:
  - O/U de las métricas viables (goles, total_shots, shots_on_target,
    corner_kicks, yellow_cards, fouls) en A/B/TOTAL.
  - Para 1H además: `1X2_1h` (gana_A/empate/gana_B) y `btts_1h` (si/no), desde
    los goles simulados de la 1ª mitad.
- `pipeline.py` orquesta: para cada partido genera FT (como hoy) + 1H + 2H.

Nueva constante en `config`: `METRICAS_OU_MITAD` (subconjunto viable) y
`REPARTO_GOLES_1H` (proporción de goles en 1ª parte).

### 4. Salida + datos canónicos

- `predicciones_largo_py.csv`: nueva columna `periodo` (`FT` por defecto en lo
  existente; `1H`/`2H` en lo nuevo).
- Prisma `Market`: añadir `periodo String @default("FT")` + migración (vía
  `prisma db push`, aditivo, sin reset).
- `seed.ts`: leer la columna `periodo` al cargar `Market`.

### 5. Web

- Página de partido (`/predicciones/[id]`): **selector de periodo** (Total / 1ª
  parte / 2ª parte) que filtra las secciones de mercados por `periodo`.
- 1X2 y BTTS: cuando el periodo es "1ª parte", mostrar `1X2_1h` / `btts_1h`.
- Reutiliza `MatchMarkets` y `lib/markets-ui`; las queries de mercados filtran
  por `periodo`.

## Testing

- Regresión: los mercados `FT` no cambian respecto al golden actual (la suite
  vs R sigue verde).
- Coherencia: para cada métrica, media(1H) + media(2H) ≈ media(FT) dentro de
  tolerancia; probabilidades en [0,1]; líneas bien formadas.
- Test de mapeo de ítems SofaScore → métricas canónicas por periodo.

## Fuera de alcance

- Mercados HT/FT combinados (resultado al descanso + final).
- Mercados de jugador por mitad.
- Hándicaps por mitad.

## Decisiones

- Periodo como columna nueva en `Market` (no codificado en el nombre del mercado).
- Goles por mitad con reparto histórico parametrizado, no por minuto exacto.
- Migración con `db push` (aditiva, sin reset), como el resto del proyecto.
- Spec sin commitear (lo commitea el usuario).

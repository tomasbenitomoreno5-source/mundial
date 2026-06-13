# Diseño: Sección de árbitros del Mundial 2026

Fecha: 2026-06-09
Estado: aprobado (pendiente de revisión del spec)

## Objetivo

Añadir árbitros al Predictor Mundial 2026 como **contenido informativo** (no
afecta al modelo de predicción por ahora):

1. **Fichas de árbitro** análogas a las de jugador: foto, perfil, estilo,
   "cómo son sus partidos" y últimos partidos.
2. **Árbitro de cada partido** del Mundial: se muestra cuando FIFA/SofaScore lo
   designe; mientras tanto, "Por designar".
3. **Fotos** en las fichas de jugador (ya existen) y de árbitro (nuevo).

El plantel base son los **árbitros principales del Mundial 2026** (lista oficial
FIFA), no cualquier árbitro del histórico. Los asistentes y VAR se excluyen: las
fichas son de disciplina (tarjetas/faltas) y los asistentes no tienen esas stats.

## Hechos verificados (API SofaScore, 2026-06-09)

- Partidos del Mundial 2026: **sin árbitro asignado** (`event/{id}.referee = NONE`
  en 6/6 muestreados; FIFA designa por partido 1-2 días antes).
- `event/{id}`: cuando hay árbitro, trae `referee {id, name, slug, country,
  yellowCards, redCards, yellowRedCards, games}` (totales de **carrera**).
- `referee/{id}`: mismos totales de carrera. No hay `statistics/seasons` (404).
- `referee/{id}/events/last/{page}`: 30 partidos/página con `tournament`,
  `homeTeam`, `awayTeam`, `homeScore`, `awayScore`, `startTimestamp` (sin
  conteo de tarjetas).
- `search/all?q=<nombre>`: devuelve entidades `referee` con `id`, `name`,
  `country` → permite resolver nombre del plantel → `sofaId` (desambiguar por país).
- Imagen: `img.sofascore.com/api/v1/referee/{sofaId}/image` → 200 webp. Mismo
  patrón que jugadores (`.../player/{sofaId}/image`), ya usado en la ficha de jugador.
- Pool histórico: `data/tarjetas.jsonl` (~1111 eventos de clasificación/amistosos)
  tiene amarillas por jugador; `data/telemetria_full.csv` tiene `fouls` por
  jugador y partido. Cruzando con el árbitro de cada evento se obtienen
  faltas/partido y tarjetas/partido reales.

## Arquitectura de datos

```
data/arbitros_mundial.csv  (curado, plantel FIFA)  ─┐
                                                    ├─ extraer_arbitros.py
SofaScore: search + referee/{id} + events/last  ───┘   (resuelve id, perfil,
                                                        últimos partidos, foto)
data/tarjetas.jsonl + telemetria_full.csv  ──────────  backfill pool (1 vez)
                                                        (amarillas/faltas reales)
                              │
                              ▼
        data/arbitros.csv + data/arbitro_ultimos.jsonl
                              │
                   web/prisma/seed.ts  →  SQLite (Referee, RefereeMatch)
                              │
                       web Next.js (/arbitros, ficha, página de partido)
```

## Componentes

### 1. Fuente del plantel — `data/arbitros_mundial.csv`

Fichero **curado a mano una vez** desde la lista oficial de árbitros del Mundial
2026 de FIFA. Columnas:

```
nombre;pais;confederacion
```

Solo árbitros **principales** (centro). No se scrapea en cada cron: la lista no
cambia durante el torneo.

### 2. Scraper — `extraer_arbitros.py` (nuevo, resumable)

Sigue el patrón "un scraper por responsabilidad" (Playwright, `headless`, mismo
user-agent y `get()` con reintentos que el resto). Pasos:

1. **Resolución de id**: por cada árbitro del plantel → `search/all?q=nombre` →
   `sofaId` (elige el `referee` cuyo `country` coincide; si hay ambigüedad,
   registra warning y deja el primero). Cachea en `data/arbitro_ids.csv`
   (`nombre;sofa_id;pais`) para no re-buscar en cada corrida.
2. **Perfil de carrera**: `referee/{sofaId}` → `games`, `yellowCards`,
   `redCards`, `yellowRedCards`.
3. **Últimos partidos**: `referee/{sofaId}/events/last/0` → hasta 30 partidos
   (rival home/away, marcador, torneo, timestamp).
4. **Salidas**:
   - `data/arbitros.csv`, una fila por árbitro:
     `sofa_id;nombre;pais;cc;confederacion;partidos_carrera;amarillas;rojas;`
     `dobles_amarillas;partidos_pool;amarillas_pool;amarillas_pool_local;`
     `amarillas_pool_visita;rojas_pool;faltas_pool;goles_pool`
     (los campos `*_pool` los rellena el backfill; sin backfill quedan vacíos).
   - `data/arbitro_ultimos.jsonl`, un registro por árbitro:
     `{sofa_id, partidos: [{ts, torneo, home, away, score_home, score_away,
     amarillas|null}]}` (amarillas no-null solo si el partido está en el pool).

Coste recurrente: ~100 árbitros × 2 llamadas ≈ 200. Cabe en el cron de 6h.

### 3. Backfill del pool (manual, una vez) — `extraer_arbitros.py --backfill`

Mapea los ~1111 eventos del pool a su árbitro y calcula disciplina real por
partido. Resumable vía `data/arbitro_pool.jsonl`:

1. Por cada `partido_id` del pool: `event/{id}` (→ árbitro, equipos local/visita)
   e `incidents/{id}` (→ amarillas/rojas separadas por `isHome`).
2. Faltas/partido: sumar `fouls` de `telemetria_full.csv` por `partido_id`.
3. Agregar por árbitro y volcar a las columnas `*_pool` de `data/arbitros.csv` y
   las `amarillas` de `data/arbitro_ultimos.jsonl`.

Es un dato estático: se corre una vez. Las fichas funcionan sin él (usan totales
de carrera); el backfill añade faltas/partido reales y sesgo local/visitante.

### 4. Árbitro por partido del Mundial — `actualizar_fixtures.py` (extender)

Hoy solo *añade* partidos nuevos. Se le añade: por cada partido del Mundial cuyo
árbitro aún no se conoce, 1 llamada `event/{id}`; si trae `referee`, escribe
`referee_id` y `referee_name` en `data/calendario.csv` (columnas nuevas, vacías
por defecto). Idempotente: una vez relleno, no se vuelve a consultar. ≤104
llamadas, decrecientes según se van designando. Va en el cron de 6h existente.

### 5. Modelos Prisma (`web/prisma/schema.prisma`)

```prisma
model Referee {
  id              Int     @id @default(autoincrement())
  sofaId          Int     @unique
  name            String
  country         String?
  countryCode     String? // alpha2, para la bandera
  confederation   String?
  // carrera (de referee/{id})
  games           Int
  yellow          Int
  red             Int
  yellowRed       Int     // dobles amarillas
  // pool histórico (del backfill; 0/null si no se hizo)
  poolGames       Int     @default(0)
  poolYellow      Int     @default(0)
  poolYellowHome  Int     @default(0)
  poolYellowAway  Int     @default(0)
  poolRed         Int     @default(0)
  poolFouls       Float?  // faltas/partido medias en el pool
  poolGoals       Float?  // goles/partido medios en el pool
  matches         RefereeMatch[]
}

model RefereeMatch {
  id            Int     @id @default(autoincrement())
  refereeSofaId Int
  ts            Int?
  tournament    String?
  home          String
  away          String
  scoreHome     Int?
  scoreAway     Int?
  yellow        Int?    // real si el partido está en el pool; null si no
  referee       Referee @relation(fields: [refereeSofaId], references: [sofaId])
  @@index([refereeSofaId])
}
```

En `Match` se añade:

```prisma
  refereeSofaId Int?
  refereeName   String?
```

Las métricas derivadas (amarillas/partido, rojas/partido, % roja, severidad y
percentil vs media del plantel, sesgo local/visitante, %local/empate/visita,
%BTTS, %Over2.5) se calculan **en query**, no se almacenan.

### 6. Seed (`web/prisma/seed.ts`)

Tres bloques nuevos siguiendo el patrón existente (`deleteMany` + `createMany`
en lotes de 2000):

- `Referee` desde `data/arbitros.csv`.
- `RefereeMatch` desde `data/arbitro_ultimos.jsonl`.
- `Match.refereeSofaId` / `refereeName` desde `data/calendario.csv` (se enlazan
  por `sofa_event_id` ↔ `Match.sofaEventId`).

### 7. Web (Next.js)

- **`/arbitros`** — índice del plantel: tarjeta/fila por árbitro con foto, bandera,
  partidos, amarillas/partido y etiqueta de severidad. Ordenable por severidad.
- **`/arbitros/[sofaId]`** — ficha (espejo de `jugadores/[name]`):
  - Cabecera: **foto** (`img.sofascore.com/.../referee/{sofaId}/image`), nombre,
    bandera, confederación, chips (partidos carrera / partidos pool).
  - **Barra de severidad** (`SeverityBar`, componente nuevo): amarillas/partido
    vs media del plantel, con percentil y etiqueta `permisivo ↔ estricto`.
  - **Chips de estilo**: rojas/partido, % partidos con roja, doble-amarilla,
    sesgo tarjetas local/visitante (del pool).
  - **Bloque "Cómo son sus partidos"**: goles/partido, faltas/partido,
    amarillas/partido, rojas/partido, % victoria local / empate / visitante,
    % BTTS, % Over 2.5. Con indicación del tamaño de muestra (pool vs últimos 30).
  - **Tabla "Últimos partidos"**: rival, marcador, torneo, amarillas (si es del pool).
- **Página de partido** (`/predicciones/[id]`): fila "Árbitro" → enlace a la ficha
  por `refereeSofaId`, o "Por designar" si es null.
- **Navegación**: enlace "Árbitros".
- **Fotos de jugador**: ya implementadas (`bio.sofaId` → `<img>`). Cobertura
  completa (4862/4862 bios con `sofa_id`). No requiere cambios; se verifica.

### 8. Cron (sin crons nuevos)

Todo se engancha al cron existente (6h red de seguridad + post-partido
kickoff+1h/+2.5h → `actualizar.sh`):

```
resultados → actualizar_fixtures.py (+ árbitro por partido)
           → re-predecir
           → extraer_arbitros.py (refresco plantel, ~200 llamadas)
           → db:seed
```

La web (ISR, revalida 1800s) recoge los cambios en ≤30 min. Cuando SofaScore
publique el árbitro de un partido, el siguiente cron lo capta y la web cambia
"Por designar" → enlace a la ficha automáticamente.

El **backfill del pool** NO va en el cron: es un `extraer_arbitros.py --backfill`
manual, una sola vez.

## Origen de cada métrica (honestidad de datos)

| Métrica | Fuente | Muestra |
|---|---|---|
| Amarillas/partido, rojas/partido, %roja, doble-amarilla | `referee/{id}` | carrera completa |
| Goles/partido, %local/empate/visita, %BTTS, %Over2.5 | `events/last/0` | últimos ≤30 |
| Faltas/partido, sesgo tarjetas local/visita, amarillas/partido (pool) | backfill pool | partidos del pool que arbitró |

La UI indica de qué muestra sale cada bloque para no mezclar carrera con pool.

## Testing

- **Python**: test de agregación de `extraer_arbitros.py` (eventos + tarjetas +
  telemetría fixture → `arbitros.csv` con amarillas/partido, faltas/partido y
  sesgo local/visita correctos). Test de resolución de id por país.
- **Seed/web**: regresión ligera (los modelos se cargan, las páginas renderizan
  con datos mínimos).

## Fuera de alcance (posible fase 2)

- Que el árbitro afecte al modelo de predicción (ajuste de mercados de
  tarjetas/faltas). De momento solo visualización.
- Asistentes y VAR.
- Refresco del backfill del pool en cada cron (es estático).

## Decisiones tomadas

- Ruta de ficha por `sofaId` (estable) en vez de por nombre.
- Plantel = solo árbitros principales (lista oficial FIFA), curado en CSV.
- Backfill del pool: **sí**, una vez (faltas/partido y sesgo reales).
- Cero crons nuevos; todo en el cron de 6h existente + backfill manual único.
- Spec sin commitear (preferencia del usuario: commitea él).

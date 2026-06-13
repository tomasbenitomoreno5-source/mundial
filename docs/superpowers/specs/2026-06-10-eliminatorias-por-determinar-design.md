# Diseño B: Eliminatorias "Por determinar"

Fecha: 2026-06-10
Estado: aprobado (pendiente de revisión del spec)

## Objetivo

Mostrar los partidos de la fase de eliminatorias en la web **antes** de que se
conozcan los cruces, como tarjetas placeholder con "Por determinar" en vez de
equipos. Cuando el cron detecta los equipos, el cruce pasa a ser un partido real
con sus predicciones (incluido el mercado de tarjetas) y el placeholder
desaparece. Es display + un dato derivado del calendario; **no** toca las FK de
`Match` ni el motor.

## Contexto verificado

- `data/calendario_completo.csv` tiene los 104 partidos (72 grupos + 32
  eliminatoria) con columnas `sofa_event_id;kickoff;ronda;descr`.
- `actualizar_fixtures.py` ya promueve un cruce de eliminatoria a `Match` real
  (con equipos + predicciones) en cuanto los equipos casan con las 48
  selecciones; mientras son "TBD", no añade nada.
- `Match.teamAName/teamBName` son FK no-nulas a `Team.name`. Por eso los
  placeholders NO se modelan como `Match` (evita romper FK y queries).

## Arquitectura

```
data/calendario_completo.csv  ──┐
                                ├─ seed.ts: KnockoutFixture (solo cruces no promovidos)
Match (sofaEventId promovidos) ─┘
                                │
        web: tarjetas "Por determinar" en la lista de predicciones
```

## Componentes

### 1. Modelo Prisma — `KnockoutFixture` (nuevo)

```prisma
model KnockoutFixture {
  id          Int     @id @default(autoincrement())
  sofaEventId Int     @unique
  kickoff     Int?
  ronda       String?  // etiqueta de ronda (octavos, cuartos, …)
  label       String?  // descr del calendario si la hay
}
```

Migración aditiva con `prisma db push` (sin reset).

### 2. Seed — `seed.ts`

- Leer `calendario_completo.csv`.
- Determinar qué `sofa_event_id` ya son `Match` reales (promovidos): los que
  están en `calendario.csv` / en `resumen`.
- Sembrar en `KnockoutFixture` **solo** los cruces de eliminatoria cuyo
  `sofa_event_id` aún no es un `Match` real. `deleteMany` + `createMany`
  idempotente.
- Derivar la etiqueta de ronda a partir de `ronda`/`descr` (mapa simple:
  octavos / cuartos / semifinal / 3er puesto / final, según el nº de partidos
  por ronda u orden cronológico).

### 3. Query — `lib/queries.ts`

`getKnockoutPlaceholders()` → `KnockoutFixture` ordenados por `kickoff`.

### 4. Web

- Lista de predicciones (`/predicciones`): tras los partidos reales, una sección
  o tarjetas placeholder por cada `KnockoutFixture`:
  - "Por determinar  vs  Por determinar", etiqueta de ronda + fecha (de
    `kickoff`).
  - Aspecto atenuado (sin probabilidades), no enlazable a detalle (o detalle con
    mensaje "Los mercados se publican cuando se conozcan los equipos").
- Reutiliza el estilo de `MatchCard` con una variante placeholder.

### 5. Cron (sin cambios de lógica)

`actualizar_fixtures.py` promueve cruces → `db:seed` recalcula `KnockoutFixture`
(excluye los ya promovidos) → la web (ISR) deja de mostrar ese placeholder y
muestra el partido real con su mercado de tarjetas. Todo automático.

## Testing

- Seed: dado un `calendario_completo.csv` y un conjunto de `Match` promovidos,
  `KnockoutFixture` contiene exactamente los cruces de eliminatoria no
  promovidos.
- Web: la página renderiza placeholders sin equipos ni probabilidades.

## Fuera de alcance

- Predecir tarjetas sin equipos (se descartó: "solo placeholder").
- Cuadro/bracket interactivo (posible fase 2).

## Decisiones

- Placeholders en modelo aparte (`KnockoutFixture`), no como `Match` con teams
  nulos → cero riesgo en FK/queries existentes.
- La etiqueta de los placeholders es "Por determinar"; el mercado de tarjetas se
  rellena solo cuando el cron promueve el cruce.
- Migración `db push` aditiva; spec sin commitear.

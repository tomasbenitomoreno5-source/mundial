# Diseño: exponer mercados de equipo en la web (detalle de partido)

Fecha: 2026-06-05
Estado: aprobado (pendiente de plan de implementación)

## Contexto

El motor de predicción (`predictor/`) ya calcula y persiste en SQLite (tabla
`Market`) **todos** los mercados de equipo: `1X2`, `doble_oportunidad`, `btts` y
Over/Under de ~18 métricas de conteo, cada O/U en tres ámbitos (`A`, `B`,
`TOTAL`).

La página de detalle de partido (`web/app/predicciones/[id]/page.tsx`) hoy solo
muestra:

- Cabecera 1X2.
- "Mercados principales": doble oportunidad + BTTS.
- "Over / Under (totales del partido)": **8** métricas (`OU_LABELS`), todas solo
  en ámbito `TOTAL`.

Quedan ocultos en la DB ~10 mercados O/U y, en todos, los ámbitos por equipo
(`A`/`B`).

## Objetivo

Exponer en la página de detalle de partido **todos** los mercados O/U de equipo
que ya están en la DB, organizados en secciones, con un **selector por mercado**
para alternar entre `TOTAL`, equipo `A` y equipo `B`.

Alcance: **solo frontend**. No se toca el modelo (`predictor/`), ni el
`schema.prisma`, ni el seed. Los mercados de jugador quedan fuera de este lote
(iteración posterior).

## Enfoque elegido

Toggle **por mercado**, con los tres sets de líneas pre-renderizados en el
servidor (Enfoque A de la fase de brainstorming). La página sigue siendo
`force-static`; la única interactividad nueva es el estado local del toggle en
un componente cliente. Descartados: un toggle global de página (menos flexible)
y ámbito por query-param (recarga/navegación, server-only).

## Arquitectura de componentes

- **`OU_LABELS`** se amplía de 8 a ~18 métricas y se reemplaza por una config
  **`SECTIONS`**: un array ordenado de `{ titulo, mercados: { mercado, label }[] }`
  que define agrupado y orden.
- **Nuevo componente cliente `MarketOU`** (`'use client'`), en
  `web/components/MarketOU.tsx`:
  - Props: `{ titulo, total: OULine[], teamA: OULine[], teamB: OULine[], flagA?, flagB? }`.
  - Mantiene estado local del ámbito seleccionado (`"TOTAL" | "A" | "B"`, default `"TOTAL"`).
  - Renderiza la misma tabla compacta que `OverUnderTable` (línea / over / under).
  - El control segmentado (`TOTAL · 🇦 · 🇧`) solo se muestra para los ámbitos que
    tengan datos; si solo hay `TOTAL`, no hay control.
- **`OverUnderTable`** se conserva como tabla presentacional reutilizable; el
  render de filas puede extraerse para compartirlo con `MarketOU` (o `MarketOU`
  lo reutiliza directamente).
- **`[id]/page.tsx`** sigue siendo server component / `force-static`. La query
  `getMatch` (con `include: { markets: true }`) ya trae todo; **no cambia**.

## Data-flow

1. `getMatch(id)` devuelve el partido con todos sus `markets`.
2. Helper nuevo `ouLinesByScope(markets, mercado)` → `{ total, teamA, teamB }`,
   cada uno un `OULine[]` (`{ linea, over }`) filtrando `evento === "over"`,
   repartiendo por `ambito` y ordenando por línea ascendente.
3. La página recorre `SECTIONS`; por cada métrica renderiza un `<MarketOU>` con
   sus tres sets de líneas y las banderas de A/B (`flag(teamAName)`,
   `flag(teamBName)`).

## Secciones (cubren los 18 O/U + goles)

| Sección | Mercados (clave DB) |
|---|---|
| Goles | `goles` |
| Tiros | `total_shots`, `shots_on_target`, `shots_off_target`, `shots_inside_box`, `shots_outside_box`, `blocked_shots` |
| Córners y balón parado | `corner_kicks`, `free_kicks`, `goal_kicks`, `throw-ins` |
| Disciplina | `yellow_cards`, `fouls`, `offsides` |
| Posesión y defensa | `passes`, `accurate_passes`, `tackles` |
| Portería | `goalkeeper_saves` |

Etiquetas en español (propuestas): Goles / Tiros totales / Tiros a puerta /
Tiros fuera / Tiros dentro del área / Tiros desde fuera del área / Tiros
bloqueados / Córners / Tiros libres / Saques de puerta / Saques de banda /
Tarjetas amarillas / Faltas / Fueras de juego / Pases / Pases precisos /
Entradas / Paradas del portero.

La cabecera 1X2 y "Mercados principales" (doble oportunidad + BTTS) se mantienen
intactas por encima de las secciones.

## Casos límite

- **Ámbito sin líneas** → su botón no aparece; si solo hay `TOTAL`, sin control.
- **Métrica en `SECTIONS` ausente en la DB del partido** → la tabla no se pinta
  (como hoy con `lineas.length === 0`).
- **Default del toggle** → `TOTAL`, para que la vista inicial sea idéntica a la
  actual.
- **Banderas** → `flag(teamName)`; fallback a "A"/"B" si falta.

## Verificación

- Cambio solo frontend: no hay tests Python que tocar.
- Manual (`npm run dev`): un partido muestra las 6 secciones; el toggle cambia
  los números entre TOTAL/A/B; los `TOTAL` coinciden con lo mostrado antes.
- `npm run build` sigue pasando (página `force-static` + interactividad de
  cliente compatible).

## Notas de implementación

- `web/AGENTS.md` advierte que esta versión de Next.js tiene *breaking changes*
  respecto a lo conocido: **leer `node_modules/next/dist/docs/` antes de escribir
  código**, especialmente para el componente `'use client'`.
- Reutilizar `pct` de `lib/format` y `flag` de `lib/flags`.

## Fuera de alcance

- Mercados de jugador (modelo, schema, seed, web) → iteración posterior.
- Cambios en la página de lista (`predicciones/page.tsx`) y en los campos
  denormalizados del `Match`.

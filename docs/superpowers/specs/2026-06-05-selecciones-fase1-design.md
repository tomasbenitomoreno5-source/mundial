# Diseño: Selecciones — Fase 1 (quick wins + transparencia)

Fecha: 2026-06-05
Estado: aprobado (pendiente de plan de implementación)

## Contexto

La sección Selecciones (MVP) ya existe: listado `/selecciones` (buscador +
orden Alfabético/Por grupo) y ficha `/selecciones/[team]` con cabecera + chips
Resumen (partidos del Mundial, estilo/similares, perfiles de métricas) y
Historial (tabla raw). Datos en SQL: `Team` (con `groupLabel`), `TeamSimilar`,
`TeamMetricProfile`, `TeamMatchStat`, `Match`/`Market`.

Esta es la Fase 1 de las mejoras de producto. Sin re-scrape, sin cambios de
schema/seed (los datos ya están cargados).

## Objetivo

Pulir la sección Selecciones con cinco mejoras de bajo coste + transparencia.

## Alcance (5 piezas)

### 1. Selecciones similares clicables
En `TeamProfile`, los chips de "estilo similar" pasan de `<span>` a `<Link>`
hacia `/selecciones/${encodeURIComponent(vecino)}`. Mantienen bandera + nombre.

### 2. Tooltip "cómo se calcula" (texto corto)
Nuevo componente reutilizable `InfoTip` (`web/components/InfoTip.tsx`): icono ℹ️
con texto breve mostrado al hover y al focus (accesible por teclado;
`aria-label`/`role`). Sin enlace. Placements en `TeamProfile`:
- Junto al título "Sus partidos del Mundial":
  *"Probabilidad del modelo: 20.000 simulaciones Monte Carlo por partido + ELO/Dixon-Coles."*
- Junto a "Estilo de juego — selecciones similares":
  *"Selecciones con el perfil de métricas más parecido (vecinos KNN)."*
- Junto a "Perfiles de métricas (por partido)":
  *"Media de sus partidos. El puesto (#) es entre las 48 selecciones mundialistas."*

### 3. Ranking por métrica
En la tabla de perfiles, columna nueva "#" = puesto de la selección entre las 48
por la **media** de esa métrica.
- Cálculo server-side: ranking descendente por `media` (1 = media más alta).
  Empates comparten posición (rank competición: misma media → mismo #).
- Presentación **neutral** (`#3 / 48`), sin colorear bueno/malo (en métricas como
  faltas o fueras de juego, "más" no es mejor).
- Métricas rankeadas: **todas** las presentes en `TeamMetricProfile` de la
  selección (las mismas que ya se muestran en la tabla).

### 4. Badge + filtro de grupo en el listado
- `TeamCard`: badge "Grupo X" (mismo estilo que el de `MatchCard`:
  `rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600`).
  Requiere pasar `groupLabel` a `TeamCard` (ahora solo recibe `name`).
- `SeleccionesBrowser`: filtro de grupo nuevo (`Dropdown`: "Todos los grupos" +
  A…L), que se combina con el buscador y con el selector de orden existente.

### 5. Tabla de historial: orden + búsqueda
En la pestaña Historial de `TeamProfile` (estado cliente):
- **Búsqueda por rival**: input que filtra filas por `partidoCompleto`
  (normalizado sin acentos, como el buscador de la lista).
- **Orden por columna**: clic en una cabecera ordena por esa columna
  (asc↔desc); indicador visual de la columna/dirección activa. Ordena tanto la
  columna "Partido" (alfabético por `partidoCompleto`) como las métricas
  (numérico; nulls al final).
- Sin descarga.

## Arquitectura

- Sin cambios de `schema.prisma` ni `seed.ts`.
- **`web/lib/queries.ts`**: `getTeamDetail` calcula además el ranking por métrica.
  Para ello carga los perfiles de **todas** las selecciones una vez y, por cada
  métrica de la selección consultada, calcula su puesto. Devuelve un mapa
  `rankByMetric: Record<string, number>` (y el total, 48, para "#/48").
- **`web/components/InfoTip.tsx`** (nuevo): tooltip accesible. Puede ser cliente
  (`'use client'`) si usa estado para el toggle en táctil; en desktop basta CSS
  `group-hover`. Decisión: implementación CSS-first (hover + focus-within) sin
  estado, para que funcione dentro de Server Components; si hiciera falta táctil,
  se reevalúa.
- **`web/components/TeamCard.tsx`**: acepta `groupLabel?: string | null` y pinta
  el badge.
- **`web/components/SeleccionesBrowser.tsx`**: añade estado `grupo` + `Dropdown`;
  filtra por grupo. `TeamLike` ya incluye `groupLabel`.
- **`web/components/TeamProfile.tsx`**: similares como `Link`; columna "#" en
  perfiles (recibe `rankByMetric`); `InfoTip` en los títulos; historial con
  estado de búsqueda + orden.
- **`web/app/selecciones/[team]/page.tsx`**: pasa `rankByMetric` a `TeamProfile`.

## Casos límite

- **Métrica sin ranking** (no presente para otras selecciones) → muestra "–" en
  la columna "#".
- **Empates de media** → mismo puesto (no se desempata arbitrariamente).
- **Historial vacío / sin coincidencias de búsqueda** → mensaje "Sin
  resultados.".
- **Grupo null** en el filtro → la opción "Todos" no filtra; selecciones sin
  grupo (no debería haber, las 48 lo tienen) no se pierden bajo "Todos".

## Verificación

- Sin runner de tests JS: `npm run lint` + `npm run build`.
- Visual (`npm run dev`):
  - Listado: badge de grupo en las tarjetas; el filtro de grupo acota; combina
    con buscador y orden.
  - Ficha: similares llevan a su ficha; columna "#" en perfiles; ℹ️ muestra el
    texto al pasar/enfocar; en Historial, buscar por rival filtra y clicar una
    cabecera ordena.

## Notas de implementación

- `web/AGENTS.md`: Next.js 16 con breaking changes; leer
  `web/node_modules/next/dist/docs/` antes de tocar cliente.
- Reutilizar: `Dropdown`/`Option`, `flag`, `teamES`, `pct`, `norm` (patrón de
  `SeleccionesBrowser`/`PrediccionesBrowser`), el estilo de badge de `MatchCard`.
- No commitear (el usuario commitea él).

## Fuera de alcance (otras fases)

- Fase 2: radar de estilo, comparador, métricas vs media, sparklines.
- Fase 3: probabilidades de torneo (Monte Carlo del cuadro).
- Fase 4: plantilla/jugadores, forma, h2h, escudos (re-scrape).
- Mercados/apuestas en la sección Selecciones (el usuario los excluyó aquí).
- Descarga del historial.

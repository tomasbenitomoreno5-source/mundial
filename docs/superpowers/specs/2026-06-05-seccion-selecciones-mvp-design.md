# Diseño: sección "Selecciones" (MVP, sin re-scrape)

Fecha: 2026-06-05
Estado: aprobado (pendiente de plan de implementación)

## Contexto

La web (`web/`, Next.js 16 + Prisma/SQLite) muestra hoy los 72 partidos del
Mundial y sus mercados. No hay vista centrada en la selección. El motor genera
más datos que la DB no contiene: `stats_final.csv` (input crudo: historial
equipo-partido), `debug_knn.csv` (vecinos de estilo) y `debug_perfiles.csv`
(perfiles de métricas por equipo). El seed actual solo carga
`predicciones_resumen_py.csv` y `predicciones_largo_py.csv`.

Esta es la primera sub-pieza ("A") de una sección "Selecciones" mayor; cubre lo
que se puede construir **sin re-scrapear**. La sub-pieza "B" (plantillas, stats
por jugador, resultados/agregados de temporada — requiere re-scrape) y los
mercados de jugador se diseñan aparte después.

Dirección del proyecto: ir migrando todos los datos a SQL (no solo lo nuevo).

## Objetivo

Añadir una sección "Selecciones": un listado de las 48 mundialistas y una ficha
por selección con los datos que el modelo ya tiene. **Sin re-scrape.**

## Decisiones de producto

- **Nav**: nueva entrada "Selecciones" (top-level, junto a Predicciones/
  Metodología).
- **Listado** `/selecciones`: tickets (bandera, nombre, ELO + ranking).
  Buscador por nombre + selector de orden (Alfabético [default] · Grupo · ELO).
- **Ficha** `/selecciones/[team]`:
  - Cabecera (siempre visible): bandera, nombre, ELO + puesto en el ranking.
  - Navegación por chips (mismo patrón que el detalle de partido):
    - **Resumen** (default): Partidos del Mundial + Estilo/similares + Perfiles
      de métricas.
    - **Historial** (datos raw): tabla partido-a-partido.
- **Alcance**: solo las 48 selecciones de la tabla `Team` (no las ~150
  históricas de `stats_final`).

## Enfoque elegido

Cargar los CSV en tablas Prisma nuevas vía `seed.ts`; las páginas consultan
Prisma como el resto de la app (Enfoque A del brainstorming). Descartados: leer
CSV en build time o pre-generar JSON (rompen el patrón Prisma y mezclan formas
de acceso a datos).

## Capa de datos (schema + seed)

Tablas nuevas en `web/prisma/schema.prisma`:

- **`TeamSimilar`** (de `debug_knn.csv`: `equipo;rank;vecino;distancia;peso`):
  `{ id, team, rank Int, vecino, distancia Float, peso Float }`, índice por
  `team`.
- **`TeamMetricProfile`** (de `debug_perfiles.csv`:
  `equipo;metrica;n;media;mediana;moda;sd;min;max`):
  `{ id, team, metrica, n Int, media Float, mediana Float, moda Float?, sd Float?, min Float?, max Float? }`,
  índice por `team`.
- **`TeamMatchStat`** (de `stats_final.csv`, una fila por partido histórico de un
  equipo): clave `{ id, team, partidoId }` + columnas de métricas. Dado el número
  de métricas (~18) y para no acoplar el schema a nombres exactos, las métricas
  se guardan como **JSON** en un campo `metrics String` (objeto serializado
  `{ metrica: valor }`), más columnas fijas útiles (`team`, `partidoId`,
  `oponente?`, `goles?`, `golesOp?`). Índice por `team`.

`web/prisma/seed.ts`: 3 pasos de carga nuevos, reutilizando el `parseCsv`/`num`
existentes (separador `;`, decimal `,`, BOM). Cada paso hace `deleteMany()` +
`createMany()` por lotes (como el de `Market`). El seed **registra por consola
los nombres de equipo que no casan** con `Team.name` (riesgo de encoding/idioma).

Nota: `Team.name` es el nombre canónico (inglés de SofaScore); los tres CSV usan
ese mismo nombre en su columna `equipo`/`equipo_nombre`. La clave de unión es el
nombre. La traducción a español es solo de presentación (`teamES`).

## Páginas y componentes

- **`web/app/selecciones/page.tsx`** (server, `force-static`): carga las 48
  selecciones (con ELO) y las pasa a `SeleccionesBrowser`.
- **`web/components/SeleccionesBrowser.tsx`** (`'use client'`): toolbar sticky
  con buscador + `Dropdown` de orden; grid de `TeamCard`. Reutiliza `Dropdown`,
  `flag`, `teamES`, el patrón de `PrediccionesBrowser`.
- **`web/components/TeamCard.tsx`**: ticket con bandera, nombre, ELO + ranking.
- **`web/app/selecciones/[team]/page.tsx`** (server, `force-static`,
  `generateStaticParams` desde `Team.name`): carga cabecera (ELO+rank), partidos
  del Mundial de esa selección, similares, perfiles e historial; los pasa a un
  cliente.
- **`web/components/TeamProfile.tsx`** (`'use client'`): cabecera + chips
  (Resumen / Historial) + render por pestaña. Reutiliza el patrón de chips de
  `MatchMarkets`.
- **`web/lib/queries.ts`**: añadir `getTeams()` (con ELO), `getTeamDetail(name)`
  (selección + similares + perfiles + historial + sus partidos), `getTeamNames()`.

Bloques de la ficha:
- *Cabecera*: bandera, nombre (`teamES`), ELO, puesto (ranking calculado
  ordenando las 48 por ELO desc).
- *Partidos del Mundial*: los `Match` donde la selección es A o B, con su 1X2,
  enlazando a `/predicciones/[id]`.
- *Estilo/similares*: top vecinos por `peso` de `TeamSimilar` → "Juega parecido
  a 🇫🇷 Francia, …".
- *Perfiles de métricas*: tabla compacta métrica → media/mediana de
  `TeamMetricProfile`. Etiquetas reutilizando las de `markets-ui` donde existan.
- *Historial raw*: tabla de `TeamMatchStat` (un row por partido; columnas =
  métricas del JSON). Render completo (prerenderizado estático); sin paginación
  en el MVP.

## Casos límite

- **Selección sin similares/perfiles/historial** → el bloque muestra "Sin datos"
  en vez de romper.
- **Nombre del CSV que no casa con `Team.name`** → el seed lo registra; esa
  selección simplemente no tendrá ese bloque.
- **Orden por grupo** cuando `groupLabel` es null → agrupar bajo "Sin grupo" al
  final.

## Verificación

- Solo frontend + seed; sin runner de tests JS: `npm run lint` + `npm run build`
  (debe generar estáticas las 48 fichas) + `npm run db:seed` sin errores.
- Visual (`npm run dev`): `/selecciones` lista 48 tickets, el orden cambia con el
  selector, el buscador filtra; una ficha muestra cabecera+ELO, sus partidos,
  similares y perfiles en "Resumen", y la tabla en "Historial".

## Notas de implementación

- `web/AGENTS.md`: Next.js 16 con breaking changes; leer
  `web/node_modules/next/dist/docs/` antes de tocar cliente/rutas dinámicas.
- Reutilizar: `Dropdown`, `flag`, `teamES`, `pct`, patrón sticky de
  `PrediccionesBrowser`, patrón de chips de `MatchMarkets`, `parseCsv`/`num` de
  `seed.ts`.
- Tras cambiar el schema: `npx prisma migrate dev` (o `db push`) + re-seed.
- **Ruta de la ficha**: los nombres tienen espacios/acentos/apóstrofos
  (p.ej. "Côte d'Ivoire"). Usar `encodeURIComponent(name)` para construir el
  enlace y decodificar el `params.team` en la página; `generateStaticParams`
  devuelve los nombres tal cual (Next los codifica). Verificar en build que las
  rutas con caracteres especiales se generan bien.
- No commitear (el usuario commitea él).

## Fuera de alcance (sub-pieza B / futuro)

- Plantillas y estadísticas por jugador (requiere re-scrape de escuadras).
- Resultados históricos y agregados de temporada de la selección (re-scrape).
- Mercados de jugador.
- Descarga CSV de los datos raw (se eligió solo tabla en página).
- Paginación/orden de la tabla de historial.

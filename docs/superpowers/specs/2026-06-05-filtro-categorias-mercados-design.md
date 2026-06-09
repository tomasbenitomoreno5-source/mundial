# Diseño: filtro de categorías de mercado en el detalle de partido

Fecha: 2026-06-05
Estado: aprobado (pendiente de plan de implementación)

## Contexto

La página de detalle de partido (`web/app/predicciones/[id]/page.tsx`) muestra,
de arriba abajo: la cabecera del partido (1X2 + barra de %), la sección
"Mercados principales" (Doble oportunidad + BTTS) y 6 secciones Over/Under
(Goles, Tiros, Córners y balón parado, Disciplina, Posesión y defensa,
Portería) renderizadas con el componente cliente `MarketOU`.

Con ~18 mercados O/U repartidos en 6 secciones apiladas en vertical, la página
queda muy larga. Se quiere acotar con un filtro de categorías.

## Objetivo

Añadir, justo debajo del cuadro del partido, una **barra de chips clicables**
(sticky) que filtra qué categoría de mercados se muestra. Solo una categoría
visible a la vez, salvo el chip "Todos" que muestra todo.

Alcance: **solo frontend**. No se toca el modelo (`predictor/`), ni
`schema.prisma`, ni el seed.

## Decisiones de producto

- **Chips** (orden): Principales · Goles · Tiros · Córners y balón parado ·
  Disciplina · Posesión y defensa · Portería · Todos.
- **Default**: "Principales" (la vista inicial es Doble oportunidad + BTTS;
  corta, sin scroll largo).
- **"Principales"** es una categoría más (DO + BTTS).
- **"Todos"** muestra Principales + las 6 secciones O/U de golpe.
- **Cabecera del partido** (1X2 + barra de %) **siempre visible** por encima de
  los chips; no la afecta el filtro.
- **Barra sticky** al hacer scroll, con el mismo estilo que la toolbar de la
  página de lista.
- **Sin sincronización con la URL** (a diferencia de la lista): YAGNI para el
  detalle.

## Enfoque elegido

Componente cliente `MatchMarkets` que envuelve la barra de chips y el contenido
(Enfoque A del brainstorming). El server component calcula todos los datos
serializables y los pasa como props; el cliente mantiene el estado del chip
activo. Descartados: query-param server-side (choca con `force-static` +
recargas) y toggle de visibilidad por CSS sobre hermanos server-rendered (más
frágil).

## Arquitectura de componentes

- **`web/lib/markets-ui.ts`** (modificar): añadir a cada entrada de `SECTIONS`
  un campo `key` (categoría) y exportar `CATEGORIAS`, lista ordenada de
  `{ key, label }`:
  - `principales` → Principales
  - `goles`, `tiros`, `corners`, `disciplina`, `posesion`, `porteria` → 1:1 con
    las 6 secciones O/U existentes
  - `todos` → Todos
- **`web/components/MiniMarket.tsx`** (crear): extraer la función `MiniMarket`
  que hoy está inline en `page.tsx` (Doble oportunidad / BTTS) a un componente
  reutilizable, para poder renderizarla dentro del cliente bajo "Principales".
  Firma: `MiniMarket({ titulo, filas }: { titulo: string; filas: [string, number | null][] })`.
- **`web/components/MatchMarkets.tsx`** (crear, `'use client'`): recibe
  `{ principales, secciones, flagA, flagB }`; estado `categoria` (default
  `"principales"`); pinta la barra de chips sticky + el contenido de la
  categoría activa. Reutiliza `MiniMarket` y `MarketOU`.
- **`web/app/predicciones/[id]/page.tsx`** (modificar): sigue server/estático.
  Calcula `principales` y `secciones` y los pasa a `<MatchMarkets>`. La cabecera
  1X2 se queda en la página. La función `evento()` se conserva (la usa para
  calcular `principales`); `ouLinesByScope` se conserva.

## Tipos / contrato de datos

```ts
// markets-ui.ts
type MarketSection = {
  key: string;     // categoría: "goles" | "tiros" | ...
  titulo: string;
  mercados: { mercado: string; label: string }[];
};
type Categoria = { key: string; label: string };

// MatchMarkets props
type Principales = {
  doble: { "1X": number | null; X2: number | null; "12": number | null };
  btts: { si: number | null; no: number | null };
};
type SeccionData = {
  key: string;
  titulo: string;
  mercados: {
    mercado: string;
    label: string;
    total: OULine[];
    teamA: OULine[];
    teamB: OULine[];
  }[];
};
```

`MatchMarkets` recibe `principales: Principales`, `secciones: SeccionData[]`,
`flagA?: string`, `flagB?: string`.

## Data-flow

1. `page.tsx` (server) calcula:
   - `principales`: con el helper `evento()` actual (DO 1X/X2/12, BTTS si/no).
   - `secciones`: por cada entrada de `SECTIONS`, mapea sus mercados a
     `{ mercado, label, ...ouLinesByScope(markets, mercado) }`.
2. Pasa `{ principales, secciones, flagA: flag(teamAName), flagB: flag(teamBName) }`
   a `<MatchMarkets>`.
3. `MatchMarkets` (cliente), según `categoria`:
   - `"principales"` → dos `<MiniMarket>` (Doble oportunidad + BTTS).
   - `"todos"` → Principales + las 6 secciones.
   - cualquier otra → solo la sección cuyo `key` coincide, con sus `<MarketOU>`.

## Comportamiento de los chips

- Barra horizontal de botones; el activo resaltado (estilo segmentado, como el
  toggle de `MarketOU` / la toolbar de la lista).
- `aria-pressed` en cada chip para el estado activo.
- Sticky: `sticky top-[57px] z-10 … backdrop-blur` (mismo offset que la toolbar
  de la lista, que se ancla bajo el nav).
- En móvil, la barra hace scroll horizontal si no cabe (`overflow-x-auto`).

## Casos límite

- **Sección sin datos**: su chip se muestra igualmente (simplicidad/estabilidad).
  Si una métrica concreta no tiene líneas, su `MarketOU` ya devuelve `null`.
- **Default**: `"principales"`.

## Verificación

- Solo frontend, sin runner de tests JS: `npm run lint` + `npm run build`.
- Visual (`npm run dev`): al abrir un partido se ve "Principales" por defecto;
  clicar un chip cambia la categoría sin recargar; "Todos" muestra todo; la
  cabecera 1X2 sigue visible; la barra queda fija al hacer scroll; en móvil la
  barra hace scroll horizontal.

## Notas de implementación

- `web/AGENTS.md`: Next.js 16 con *breaking changes*; leer
  `web/node_modules/next/dist/docs/` antes de tocar el cliente.
- Reutilizar `pct` (`lib/format`), `flag` (`lib/flags`), `MarketOU` y el patrón
  sticky de `PrediccionesBrowser.tsx`.
- No commitear (el usuario commitea él).

## Fuera de alcance

- Sincronización con la URL del chip activo.
- Mercados de jugador.
- Cambios en el modelo, schema o seed.

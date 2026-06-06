# Mercados de equipo en la web — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar en la página de detalle de partido todos los mercados O/U de equipo que ya están en la DB, agrupados en 6 secciones, con un selector TOTAL/A/B por mercado.

**Architecture:** Solo frontend. La query `getMatch` ya trae todos los `markets`. Se añade una config de secciones (`lib/markets-ui.ts`), un helper que reparte las líneas por ámbito en `page.tsx`, y un componente cliente `MarketOU` con toggle local. La página sigue siendo `force-static`.

**Tech Stack:** Next.js 16.2.7 (App Router, RSC), React, Tailwind, Prisma/SQLite (sin cambios de datos).

> ⚠️ `web/AGENTS.md`: esta versión de Next.js tiene *breaking changes* respecto a versiones conocidas. **Antes de escribir el componente `'use client'`, leer la guía relevante en `web/node_modules/next/dist/docs/`** (Server vs Client Components, `"use client"`).

> Nota de verificación: el proyecto `web/` no tiene runner de tests JS (los tests viven en `predictor/` con pytest y no se tocan). La verificación de cada tarea es `npm run lint` + `npm run build` + comprobación visual. No se introduce un framework de tests JS (fuera de alcance).

Todos los comandos `npm` se ejecutan desde `web/` (`cd web`).

---

### Task 1: Config de secciones y etiquetas

**Files:**
- Create: `web/lib/markets-ui.ts`

- [ ] **Step 1: Crear el módulo de config**

```ts
// web/lib/markets-ui.ts
// Agrupado y etiquetas (es-ES) de los mercados O/U de equipo para la vista de
// detalle de partido. Las claves `mercado` coinciden con la columna `mercado`
// de la tabla Market en la DB.

export type MarketSection = {
  titulo: string;
  mercados: { mercado: string; label: string }[];
};

export const SECTIONS: MarketSection[] = [
  {
    titulo: "Goles",
    mercados: [{ mercado: "goles", label: "Goles" }],
  },
  {
    titulo: "Tiros",
    mercados: [
      { mercado: "total_shots", label: "Tiros totales" },
      { mercado: "shots_on_target", label: "Tiros a puerta" },
      { mercado: "shots_off_target", label: "Tiros fuera" },
      { mercado: "shots_inside_box", label: "Tiros dentro del área" },
      { mercado: "shots_outside_box", label: "Tiros desde fuera del área" },
      { mercado: "blocked_shots", label: "Tiros bloqueados" },
    ],
  },
  {
    titulo: "Córners y balón parado",
    mercados: [
      { mercado: "corner_kicks", label: "Córners" },
      { mercado: "free_kicks", label: "Tiros libres" },
      { mercado: "goal_kicks", label: "Saques de puerta" },
      { mercado: "throw-ins", label: "Saques de banda" },
    ],
  },
  {
    titulo: "Disciplina",
    mercados: [
      { mercado: "yellow_cards", label: "Tarjetas amarillas" },
      { mercado: "fouls", label: "Faltas" },
      { mercado: "offsides", label: "Fueras de juego" },
    ],
  },
  {
    titulo: "Posesión y defensa",
    mercados: [
      { mercado: "passes", label: "Pases" },
      { mercado: "accurate_passes", label: "Pases precisos" },
      { mercado: "tackles", label: "Entradas" },
    ],
  },
  {
    titulo: "Portería",
    mercados: [{ mercado: "goalkeeper_saves", label: "Paradas del portero" }],
  },
];
```

- [ ] **Step 2: Verificar lint y tipos**

Run: `cd web && npm run lint`
Expected: sin errores en `lib/markets-ui.ts`.

- [ ] **Step 3: Commit**

```bash
git add web/lib/markets-ui.ts
git commit -m "feat(web): config de secciones de mercados de equipo"
```

---

### Task 2: Componente cliente `MarketOU` con selector TOTAL/A/B

**Files:**
- Create: `web/components/MarketOU.tsx`

Reutiliza el tipo `OULine` ya exportado por `components/OverUnderTable.tsx`
(`export type OULine = { linea: string; over: number }`) y `pct` de `lib/format`.

- [ ] **Step 1: Leer la guía de Next.js sobre Client Components**

Localizar y leer la guía relevante:
Run: `ls web/node_modules/next/dist/docs/ 2>/dev/null && grep -rl "use client" web/node_modules/next/dist/docs/ 2>/dev/null | head`
Confirmar la convención de `"use client"` y el uso de `useState` antes de escribir.

- [ ] **Step 2: Crear el componente**

```tsx
// web/components/MarketOU.tsx
"use client";

import { useState } from "react";

import { pct } from "@/lib/format";
import type { OULine } from "./OverUnderTable";

type Scope = "TOTAL" | "A" | "B";

/**
 * Tabla O/U con selector de ámbito. Recibe los tres sets de líneas
 * pre-renderizados; el toggle solo cambia cuál se pinta. Si un ámbito no
 * tiene líneas, su botón no se ofrece. Si solo hay un ámbito, no hay control.
 */
export function MarketOU({
  titulo,
  total,
  teamA,
  teamB,
  flagA,
  flagB,
}: {
  titulo: string;
  total: OULine[];
  teamA: OULine[];
  teamB: OULine[];
  flagA?: string;
  flagB?: string;
}) {
  const opciones: { scope: Scope; label: string; lineas: OULine[] }[] = [
    { scope: "TOTAL", label: "Total", lineas: total },
    { scope: "A", label: flagA ?? "A", lineas: teamA },
    { scope: "B", label: flagB ?? "B", lineas: teamB },
  ].filter((o) => o.lineas.length > 0);

  const [scope, setScope] = useState<Scope>("TOTAL");

  if (opciones.length === 0) return null;

  const activa = opciones.find((o) => o.scope === scope) ?? opciones[0];
  const lineas = activa.lineas;

  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-900">{titulo}</h4>
        {opciones.length > 1 && (
          <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs">
            {opciones.map((o) => (
              <button
                key={o.scope}
                type="button"
                onClick={() => setScope(o.scope)}
                className={`rounded-md px-2 py-0.5 font-medium transition ${
                  o.scope === activa.scope
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
            <th className="font-medium">Línea</th>
            <th className="text-right font-medium">Over</th>
            <th className="text-right font-medium">Under</th>
          </tr>
        </thead>
        <tbody>
          {lineas.map((l) => (
            <tr key={l.linea} className="border-t border-slate-100">
              <td className="py-1.5 tabular-nums text-slate-600">{l.linea}</td>
              <td className="py-1.5 text-right font-medium tabular-nums text-indigo-600">
                {pct(l.over)}
              </td>
              <td className="py-1.5 text-right tabular-nums text-slate-400">
                {pct(1 - l.over)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Nota: la clase activa se compara contra `activa.scope` (no contra `scope`) para
que, si el ámbito por defecto `TOTAL` no tuviera líneas, el botón resaltado
coincida con la tabla mostrada (fallback a `opciones[0]`).

- [ ] **Step 3: Verificar lint y tipos**

Run: `cd web && npm run lint`
Expected: sin errores en `components/MarketOU.tsx`.

- [ ] **Step 4: Commit**

```bash
git add web/components/MarketOU.tsx
git commit -m "feat(web): componente MarketOU con selector TOTAL/A/B"
```

---

### Task 3: Cablear secciones en la página de detalle

**Files:**
- Modify: `web/app/predicciones/[id]/page.tsx`

Cambios: (a) sustituir el import de `OverUnderTable` por `MarketOU` y `SECTIONS`,
manteniendo el tipo `OULine`; (b) borrar `OU_LABELS` y la función `ouLines`;
(c) añadir el helper `ouLinesByScope`; (d) reemplazar la `<section>` de Over/Under
por el bucle de secciones. La cabecera 1X2 y "Mercados principales" no se tocan.

- [ ] **Step 1: Actualizar imports**

Reemplazar (líneas 4 y 9 actuales):

```tsx
import { OULine, OverUnderTable } from "@/components/OverUnderTable";
```

por:

```tsx
import { MarketOU } from "@/components/MarketOU";
import type { OULine } from "@/components/OverUnderTable";
import { SECTIONS } from "@/lib/markets-ui";
```

(El resto de imports —`ProbBar`, `flag`, `formatFecha`, `pct`, `teamES`,
`getMatch`, `getMatchIds`, `MarketRow`— se mantienen.)

- [ ] **Step 2: Borrar `OU_LABELS` y `ouLines`, añadir `ouLinesByScope`**

Eliminar el bloque `const OU_LABELS = { ... };` (líneas 31-40 actuales) y la
función `function ouLines(...) { ... }` (líneas 42-49 actuales).

Añadir, junto a la función `evento` que se conserva, este helper:

```tsx
function ouLinesByScope(markets: MarketRow[], mercado: string) {
  const byScope = (ambito: string): OULine[] =>
    markets
      .filter(
        (m) =>
          m.mercado === mercado &&
          m.ambito === ambito &&
          m.evento === "over",
      )
      .map((m) => ({ linea: m.linea, over: m.probabilidad }))
      .sort((a, b) => parseFloat(a.linea) - parseFloat(b.linea));
  return {
    total: byScope("TOTAL"),
    teamA: byScope("A"),
    teamB: byScope("B"),
  };
}
```

- [ ] **Step 3: Reemplazar la sección Over/Under**

Sustituir la `<section>` actual de "Over / Under (totales del partido)"
(líneas 136-150 actuales, el bloque que mapea `Object.entries(OU_LABELS)`) por:

```tsx
      {/* Mercados por categoría */}
      {SECTIONS.map((section) => (
        <section key={section.titulo} className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            {section.titulo}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {section.mercados.map(({ mercado, label }) => {
              const { total, teamA, teamB } = ouLinesByScope(markets, mercado);
              return (
                <MarketOU
                  key={mercado}
                  titulo={label}
                  total={total}
                  teamA={teamA}
                  teamB={teamB}
                  flagA={flag(match.teamAName)}
                  flagB={flag(match.teamBName)}
                />
              );
            })}
          </div>
        </section>
      ))}
```

- [ ] **Step 4: Verificar lint y build**

Run: `cd web && npm run lint && npm run build`
Expected: lint sin errores; build completa el render estático de todos los
partidos sin fallos de tipos.

- [ ] **Step 5: Commit**

```bash
git add web/app/predicciones/\[id\]/page.tsx
git commit -m "feat(web): secciones de mercados de equipo con selector de ámbito"
```

---

### Task 4: Verificación visual

**Files:** (ninguno — verificación manual)

- [ ] **Step 1: Arrancar el dev server**

Run: `cd web && npm run dev`
Abrir `http://localhost:3000/predicciones` y entrar en un partido.

- [ ] **Step 2: Comprobar las 6 secciones**

Verificar que aparecen, en orden: Goles, Tiros, Córners y balón parado,
Disciplina, Posesión y defensa, Portería — con sus tablas O/U.

- [ ] **Step 3: Comprobar el selector**

En un mercado con datos por equipo (p.ej. Córners), pulsar `Total` / bandera A /
bandera B y confirmar que los números cambian. Confirmar que el valor inicial es
`Total` y que coincide con lo que mostraba la web antes del cambio.

- [ ] **Step 4: Comprobar build de producción**

Run: `cd web && npm run build`
Expected: build OK (sanity final).

---

## Self-Review

- **Cobertura del spec:** secciones (Task 1) ✓, componente con toggle y casos
  límite de ámbito vacío/único (Task 2) ✓, helper `ouLinesByScope` + cableado +
  borrado de `OU_LABELS`/`ouLines` (Task 3) ✓, verificación manual + build
  (Task 4) ✓. Fuera de alcance (jugador, lista, denormalizados) no genera tareas.
- **Placeholders:** ninguno; todo el código va literal.
- **Consistencia de tipos:** `OULine = { linea: string; over: number }` reusado
  desde `OverUnderTable` en `ouLinesByScope` y `MarketOU`; `MarketRow` desde
  `lib/queries`; props de `MarketOU` (`total/teamA/teamB/flagA/flagB`) coinciden
  con lo que pasa la página; `flag(team: string)` y `pct` con sus firmas reales.

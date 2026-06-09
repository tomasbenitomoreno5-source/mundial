"use client";

import { useState } from "react";

import { MarketOU } from "@/components/MarketOU";
import { MiniMarket } from "@/components/MiniMarket";
import type { OULine } from "@/components/OverUnderTable";
import {
  PlayerMarketCard,
  type PlayerMarketGroup,
} from "@/components/PlayerMarketCard";
import { CATEGORIAS } from "@/lib/markets-ui";

export type Principales = {
  doble: { "1X": number | null; X2: number | null; "12": number | null };
  btts: { si: number | null; no: number | null };
};

export type SeccionData = {
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

/**
 * Mercados del partido con barra de chips de categoría (sticky). Por defecto
 * muestra "Principales"; cada chip muestra su sección; "Todos" muestra todo.
 */
export function MatchMarkets({
  principales,
  secciones,
  jugadores,
  flagA,
  flagB,
}: {
  principales: Principales;
  secciones: SeccionData[];
  jugadores: PlayerMarketGroup[];
  flagA?: string;
  flagB?: string;
}) {
  const [categoria, setCategoria] = useState("principales");

  const cats = CATEGORIAS.filter(
    (c) => c.key !== "jugadores" || jugadores.length > 0,
  );
  const verPrincipales = categoria === "principales" || categoria === "todos";
  const verJugadores =
    (categoria === "jugadores" || categoria === "todos") &&
    jugadores.length > 0;
  const seccionesVisibles =
    categoria === "todos"
      ? secciones
      : secciones.filter((s) => s.key === categoria);

  return (
    <div className="mt-8">
      {/* Barra de chips de categoría (sticky bajo el nav) */}
      <div className="sticky top-[57px] z-10 -mx-4 mb-6 border-b border-slate-200 bg-[var(--background)]/95 px-4 py-3 backdrop-blur">
        <div className="flex gap-2 overflow-x-auto">
          {cats.map((c) => (
            <button
              key={c.key}
              type="button"
              aria-pressed={c.key === categoria}
              onClick={() => setCategoria(c.key)}
              className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition ${
                c.key === categoria
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Mercados principales */}
      {verPrincipales && (
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Mercados principales
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <MiniMarket
              titulo="Doble oportunidad"
              filas={[
                ["1X", principales.doble["1X"]],
                ["X2", principales.doble.X2],
                ["12", principales.doble["12"]],
              ]}
            />
            <MiniMarket
              titulo="Ambos marcan (BTTS)"
              filas={[
                ["Sí", principales.btts.si],
                ["No", principales.btts.no],
              ]}
            />
          </div>
        </section>
      )}

      {/* Secciones O/U */}
      {seccionesVisibles.map((section) => (
        <section key={section.key} className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            {section.titulo}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {section.mercados.map((m) => (
              <MarketOU
                key={m.mercado}
                titulo={m.label}
                total={m.total}
                teamA={m.teamA}
                teamB={m.teamB}
                flagA={flagA}
                flagB={flagB}
              />
            ))}
          </div>
        </section>
      ))}

      {/* Mercados de jugador */}
      {verJugadores && (
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Jugadores
          </h2>
          <div className="space-y-2">
            {jugadores.map((j) => (
              <PlayerMarketCard key={j.player} j={j} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

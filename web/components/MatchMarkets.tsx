"use client";

import { useState } from "react";

import { ApuestasFiltradas } from "@/components/ApuestasFiltradas";
import { MarketOU } from "@/components/MarketOU";
import { MiniMarket } from "@/components/MiniMarket";
import type { OULine } from "@/components/OverUnderTable";
import {
  PlayerMarketCard,
  type PlayerMarketGroup,
} from "@/components/PlayerMarketCard";
import type { Apuesta } from "@/lib/best-bets";
import { flag } from "@/lib/flags";
import { CATEGORIAS } from "@/lib/markets-ui";
import { teamES } from "@/lib/teams";

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
  seccionesPorPeriodo,
  resultado1h,
  hayMitades = false,
  jugadores,
  sinDatos = [],
  apuestas = [],
  flagA,
  flagB,
}: {
  principales: Principales;
  secciones: SeccionData[];
  seccionesPorPeriodo?: Record<string, SeccionData[]>;
  resultado1h?: {
    p1: number | null;
    pX: number | null;
    p2: number | null;
    bttsSi: number | null;
    bttsNo: number | null;
  };
  hayMitades?: boolean;
  jugadores: PlayerMarketGroup[];
  sinDatos?: { player: string; team: string }[];
  apuestas?: Apuesta[];
  flagA?: string;
  flagB?: string;
}) {
  const [modo, setModo] = useState<"mercados" | "apuestas">("mercados");
  const [categoria, setCategoria] = useState("principales");
  const [equipoJug, setEquipoJug] = useState<string | null>(null); // filtro de equipo
  const [periodo, setPeriodo] = useState<"FT" | "1H" | "2H">("FT");
  const [minPct, setMinPct] = useState(75);
  const [maxPct, setMaxPct] = useState(95);
  const esFT = periodo === "FT";
  const verApuestas = modo === "apuestas";

  const cats = CATEGORIAS.filter(
    (c) => c.key !== "jugadores" || jugadores.length > 0,
  );
  // Secciones del periodo activo; en 1ª/2ª solo las métricas con datos.
  const seccionesPeriodo = seccionesPorPeriodo?.[periodo] ?? secciones;
  const conDatos = (s: SeccionData) =>
    s.mercados.some((m) => m.total.length || m.teamA.length || m.teamB.length);
  const baseSecciones = esFT
    ? seccionesPeriodo
    : seccionesPeriodo
        .map((s) => ({
          ...s,
          mercados: s.mercados.filter(
            (m) => m.total.length || m.teamA.length || m.teamB.length,
          ),
        }))
        .filter(conDatos);

  const verPrincipales =
    !verApuestas && esFT && (categoria === "principales" || categoria === "todos");
  const verResultado1h =
    !verApuestas &&
    periodo === "1H" &&
    (categoria === "principales" || categoria === "todos") &&
    !!resultado1h;
  const verJugadores =
    !verApuestas &&
    esFT &&
    (categoria === "jugadores" || categoria === "todos") &&
    jugadores.length > 0;
  const seccionesVisibles = verApuestas
    ? [] // en modo Apuestas no se muestran las tablas de mercados
    : categoria === "todos"
      ? baseSecciones
      : baseSecciones.filter((s) => s.key === categoria);

  const PERIODOS: { key: "FT" | "1H" | "2H"; label: string }[] = [
    { key: "FT", label: "Todo el partido" },
    { key: "1H", label: "1ª parte" },
    { key: "2H", label: "2ª parte" },
  ];

  return (
    <div className="mt-8">
      {/* Barra sticky: selector de periodo (1ª/2ª) + chips de categoría */}
      <div className="sticky top-[57px] z-10 -mx-4 mb-6 border-b border-slate-200 bg-[var(--background)]/95 px-4 py-3 backdrop-blur">
        {/* Modo: Mercados / Apuestas */}
        <div className="mb-2.5 inline-flex rounded-full bg-slate-100 p-1">
          {([["mercados", "Mercados"], ["apuestas", "Apuestas"]] as const).map(
            ([k, l]) => (
              <button
                key={k}
                type="button"
                aria-pressed={modo === k}
                onClick={() => setModo(k)}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                  modo === k
                    ? "bg-white text-indigo-600 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {l}
              </button>
            ),
          )}
        </div>
        {/* Periodo (aplica a Mercados y Apuestas) */}
        {hayMitades && (
          <div className="mb-2.5 flex">
            <div className="inline-flex rounded-full bg-slate-100 p-1">
              {PERIODOS.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  aria-pressed={p.key === periodo}
                  onClick={() => setPeriodo(p.key)}
                  className={`rounded-full px-3 py-1.5 text-sm font-semibold transition ${
                    p.key === periodo
                      ? "bg-white text-indigo-600 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}
        {/* Rango de % (solo en la pestaña Apuestas), junto al selector de periodo */}
        {verApuestas && (
          <div className="mb-2.5 flex items-center gap-2 text-sm text-slate-500">
            <span className="font-medium">Apuestas entre</span>
            <input
              type="number"
              min={60}
              max={99}
              value={minPct}
              onChange={(e) =>
                setMinPct(Math.min(maxPct, Math.max(60, Number(e.target.value) || 60)))
              }
              className="w-16 rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm font-bold tabular-nums outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            />
            <span>y</span>
            <input
              type="number"
              min={60}
              max={99}
              value={maxPct}
              onChange={(e) =>
                setMaxPct(Math.min(99, Math.max(minPct, Number(e.target.value) || 99)))
              }
              className="w-16 rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm font-bold tabular-nums outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            />
            <span className="font-medium">%</span>
          </div>
        )}
        {!verApuestas && (
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
        )}
      </div>

      {/* Apuestas filtradas por % (respeta el periodo activo) */}
      {verApuestas && (
        <ApuestasFiltradas
          apuestas={apuestas}
          periodo={periodo}
          min={minPct}
          max={maxPct}
        />
      )}

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

      {/* Resultado de 1ª parte (1X2 + BTTS al descanso) */}
      {verResultado1h && resultado1h && (
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Resultado al descanso
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <MiniMarket
              titulo="1X2 1ª parte"
              filas={[
                ["1", resultado1h.p1],
                ["X", resultado1h.pX],
                ["2", resultado1h.p2],
              ]}
            />
            <MiniMarket
              titulo="Ambos marcan 1ª parte"
              filas={[
                ["Sí", resultado1h.bttsSi],
                ["No", resultado1h.bttsNo],
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
      {verJugadores &&
        (() => {
          const equipos = [
            ...new Set([
              ...jugadores.map((j) => j.team),
              ...sinDatos.map((s) => s.team),
            ]),
          ];
          const jugVisibles = equipoJug
            ? jugadores.filter((j) => j.team === equipoJug)
            : jugadores;
          const sdVisibles = equipoJug
            ? sinDatos.filter((s) => s.team === equipoJug)
            : sinDatos;
          return (
            <section className="mb-8">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Jugadores
                </h2>
                {equipos.length > 1 && (
                  <div className="inline-flex rounded-full bg-slate-100 p-0.5 text-xs">
                    <button
                      type="button"
                      aria-pressed={equipoJug === null}
                      onClick={() => setEquipoJug(null)}
                      className={`rounded-full px-3 py-1 font-medium transition ${
                        equipoJug === null
                          ? "bg-white text-indigo-600 shadow-sm"
                          : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      Todos
                    </button>
                    {equipos.map((eq) => (
                      <button
                        key={eq}
                        type="button"
                        aria-pressed={equipoJug === eq}
                        onClick={() => setEquipoJug(eq)}
                        className={`rounded-full px-3 py-1 font-medium transition ${
                          equipoJug === eq
                            ? "bg-white text-indigo-600 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                        }`}
                      >
                        {flag(eq)} {teamES(eq)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="space-y-2">
                {jugVisibles.map((j) => (
                  <PlayerMarketCard key={j.player} j={j} />
                ))}
              </div>
              {sdVisibles.length > 0 && (
                <div className="mt-3 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/60">
                  <p className="mb-2 text-xs font-medium text-slate-400">
                    Sin datos suficientes para predecir ({sdVisibles.length})
                  </p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {sdVisibles.map((s) => (
                      <span key={s.player} className="text-sm text-slate-400">
                        {s.player}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </section>
          );
        })()}
    </div>
  );
}

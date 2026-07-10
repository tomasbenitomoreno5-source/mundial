"use client";

import Link from "next/link";
import { useState } from "react";

import { outcome, pred1x2 } from "@/lib/accuracy";
import { flag } from "@/lib/flags";
import { teamES } from "@/lib/teams";

// Partidos jugados (subconjunto de Match) que usa la lista.
interface Partido {
  id: string;
  p1: number | null;
  pX: number | null;
  p2: number | null;
  scoreA: number | null;
  scoreB: number | null;
  teamAName: string;
  teamBName: string;
}

const INICIAL = 6; // cuántos se ven de entrada
const INCREMENTO = 6; // cuántos añade cada clic en "mostrar más"

export function PartidoAPartidoLista({ settled }: { settled: Partido[] }) {
  // `settled` llega ya ordenado descendente (más reciente primero).
  const [mostrar, setMostrar] = useState(INICIAL);
  const visibles = settled.slice(0, mostrar);
  const restantes = settled.length - visibles.length;

  return (
    <div className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
      <div className="divide-y divide-slate-100">
        {visibles.map((m) => {
          const real = outcome(m.scoreA ?? 0, m.scoreB ?? 0);
          const pick = pred1x2(m.p1, m.pX, m.p2);
          const ok = pick === real;
          const prob = pick === "A" ? m.p1 : pick === "B" ? m.p2 : m.pX;
          const pickTxt =
            pick === "A"
              ? `gana ${teamES(m.teamAName)}`
              : pick === "B"
                ? `gana ${teamES(m.teamBName)}`
                : "empate";
          return (
            <Link
              key={m.id}
              href={`/predicciones/${m.id}`}
              className="group flex items-center gap-3 px-4 py-3 transition hover:bg-slate-50"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-slate-900">
                  {flag(m.teamAName)} {teamES(m.teamAName)} –{" "}
                  {teamES(m.teamBName)} {flag(m.teamBName)}
                </div>
                <div className="text-xs text-slate-400">
                  El modelo dijo: {pickTxt}
                  {prob != null && ` · ${Math.round(prob * 100)}%`}
                </div>
              </div>
              <span className="shrink-0 text-lg font-bold tabular-nums text-slate-900">
                {m.scoreA}–{m.scoreB}
              </span>
              <span
                className={`w-20 shrink-0 text-right text-sm font-medium ${
                  ok ? "text-emerald-600" : "text-rose-500"
                }`}
              >
                {ok ? "✓ acertó" : "✗ falló"}
              </span>
              <span className="shrink-0 text-slate-300 transition group-hover:text-slate-500">
                ›
              </span>
            </Link>
          );
        })}
      </div>
      {restantes > 0 && (
        <button
          type="button"
          onClick={() => setMostrar((n) => n + INCREMENTO)}
          className="block w-full border-t border-slate-100 py-3 text-center text-sm font-medium text-indigo-600 transition hover:bg-slate-50"
        >
          Mostrar {Math.min(restantes, INCREMENTO)} más
          {restantes > INCREMENTO ? ` · ${restantes} restantes` : ""}
        </button>
      )}
    </div>
  );
}

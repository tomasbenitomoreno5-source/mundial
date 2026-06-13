"use client";

import { useMemo } from "react";

import type { Apuesta } from "@/lib/best-bets";
import { pct } from "@/lib/format";

/**
 * Lista las apuestas del partido dentro de la banda [min, máx] y del periodo
 * activo. Los controles (rango de % y periodo) viven en la barra sticky de
 * MatchMarkets; aquí solo se filtra y se pinta.
 */
export function ApuestasFiltradas({
  apuestas,
  periodo,
  min,
  max,
}: {
  apuestas: Apuesta[];
  periodo: string;
  min: number;
  max: number;
}) {
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);

  const filtradas = useMemo(() => {
    const best = new Map<string, Apuesta>();
    for (const a of apuestas) {
      if (a.periodo !== periodo) continue;
      const p = Math.round(a.prob * 100); // redondeado, igual que la etiqueta
      if (p < lo || p > hi) continue;
      const cur = best.get(a.key);
      if (!cur || a.prob < cur.prob) best.set(a.key, a); // la línea más ajustada
    }
    return [...best.values()].sort((x, y) => y.prob - x.prob);
  }, [apuestas, periodo, lo, hi]);

  return (
    <section className="mb-8">
      <div className="mb-3 text-xs text-slate-500">
        {filtradas.length} {filtradas.length === 1 ? "apuesta" : "apuestas"}{" "}
        entre el {lo}% y el {hi}%
      </div>
      {filtradas.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-slate-300 py-8 text-center text-sm text-slate-400">
          Ninguna selección en esa banda para este periodo.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {filtradas.map((a, i) => (
            <span
              key={i}
              className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm ring-1 ring-slate-200"
            >
              {a.label}
              <span className="font-bold text-indigo-600">{pct(a.prob)}</span>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

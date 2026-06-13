"use client";

import { useState } from "react";

import { CalibrationBars } from "@/components/CalibrationBars";
import type { MarketPerf } from "@/lib/rendimiento";

// Nota de fiabilidad 0-100 a partir del error de calibración (ECE).
// ECE 0 → 100, 0.03 → 80, 0.06 → 60, 0.15 → 0. Comparable entre mercados.
function nota(ece: number): number {
  return Math.round(Math.max(0, Math.min(1, 1 - ece / 0.15)) * 100);
}

function colorBarra(n: number): string {
  if (n >= 80) return "bg-emerald-500";
  if (n >= 60) return "bg-amber-500";
  return "bg-rose-400";
}

const pct = (x: number) => `${Math.round(x * 100)}%`;

export function RendimientoMercadosLista({ rows }: { rows: MarketPerf[] }) {
  const orden = [...rows].sort((a, b) => nota(a.ece) - nota(b.ece)).reverse();
  // El mejor mercado abierto de entrada, para que se vea el gráfico al llegar.
  const [abierto, setAbierto] = useState<string | null>(orden[0]?.mercado ?? null);

  return (
    <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
      {orden.map((r) => {
        const n = nota(r.ece);
        const barra = colorBarra(n);
        const abierta = abierto === r.mercado;
        return (
          <div key={r.mercado}>
            <button
              type="button"
              onClick={() => setAbierto(abierta ? null : r.mercado)}
              className={`flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50 ${
                abierta ? "bg-slate-50" : ""
              }`}
            >
              <span className="flex-1 font-medium text-slate-900">
                {r.etiqueta}
              </span>
              {/* barra de fiabilidad */}
              <div className="h-2.5 w-24 shrink-0 overflow-hidden rounded-full bg-slate-100 sm:w-32">
                <div
                  className={`h-full rounded-full ${barra}`}
                  style={{ width: `${n}%` }}
                />
              </div>
              <span className="w-14 shrink-0 text-right text-sm font-bold tabular-nums text-slate-700">
                {n}
                <span className="text-xs font-normal text-slate-400">/100</span>
              </span>
              <span className="w-3 shrink-0 text-slate-400">
                {abierta ? "▾" : "▸"}
              </span>
            </button>
            {abierta && (
              <div className="bg-slate-50/60 px-4 py-4 sm:px-10">
                <div className="mx-auto max-w-md">
                  <CalibrationBars bins={r.bins} etiqueta={r.etiqueta} />
                  <div className="mt-3 flex justify-center gap-6 text-xs text-slate-400">
                    <span>Acierto <b className="text-slate-600">{pct(r.acierto)}</b></span>
                    <span>Brier <b className="text-slate-600">{r.brier.toFixed(3)}</b></span>
                    <span>{r.n.toLocaleString("es")} casos</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

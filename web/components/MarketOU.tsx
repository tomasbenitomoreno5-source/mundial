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
  const ambitos: { scope: Scope; label: string; lineas: OULine[] }[] = [
    { scope: "TOTAL", label: "Total", lineas: total },
    { scope: "A", label: flagA ?? "A", lineas: teamA },
    { scope: "B", label: flagB ?? "B", lineas: teamB },
  ];
  const opciones = ambitos.filter((o) => o.lineas.length > 0);

  const [scope, setScope] = useState<Scope>("TOTAL");
  const [verTodas, setVerTodas] = useState(false);

  if (opciones.length === 0) return null;

  const activa = opciones.find((o) => o.scope === scope) ?? opciones[0];
  // Ordenar por línea y localizar la "principal" (over más cercano a 50%).
  const ordenadas = [...activa.lineas].sort(
    (a, b) => parseFloat(a.linea) - parseFloat(b.linea),
  );
  let idxEq = 0;
  let mejor = Infinity;
  ordenadas.forEach((l, i) => {
    const d = Math.abs(l.over - 0.5);
    if (d < mejor) {
      mejor = d;
      idxEq = i;
    }
  });
  // Por defecto: 5 líneas centradas en la principal. "Ver todas" las despliega.
  const N = 5;
  let ini = Math.max(0, idxEq - Math.floor(N / 2));
  const fin = Math.min(ordenadas.length, ini + N);
  ini = Math.max(0, fin - N);
  const visibles = verTodas ? ordenadas : ordenadas.slice(ini, fin);
  const hayMas = !verTodas && visibles.length < ordenadas.length;

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
                aria-pressed={o.scope === activa.scope}
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
          {visibles.map((l) => {
            return (
              <tr key={l.linea} className="border-t border-slate-100">
                <td className="py-1.5 tabular-nums text-slate-600">
                  {l.linea}
                </td>
                <td className="py-1.5 text-right font-medium tabular-nums text-indigo-600">
                  {pct(l.over)}
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-400">
                  {pct(1 - l.over)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {(hayMas || verTodas) && ordenadas.length > N && (
        <button
          type="button"
          onClick={() => setVerTodas((v) => !v)}
          className="mt-2 w-full rounded-lg py-1.5 text-xs font-medium text-indigo-600 transition hover:bg-indigo-50"
        >
          {verTodas
            ? "Ver menos"
            : `Ver todas las líneas (${ordenadas.length})`}
        </button>
      )}
    </div>
  );
}

import { pct } from "@/lib/format";

export type OULine = { linea: string; over: number };

/** Tabla compacta de Over/Under (totales) para una métrica. */
export function OverUnderTable({
  titulo,
  lineas,
}: {
  titulo: string;
  lineas: OULine[];
}) {
  if (lineas.length === 0) return null;
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <h4 className="mb-3 text-sm font-semibold text-slate-900">{titulo}</h4>
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

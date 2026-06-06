import { pct } from "@/lib/format";

/** Tarjeta compacta clave→probabilidad (Doble oportunidad, BTTS, …). */
export function MiniMarket({
  titulo,
  filas,
}: {
  titulo: string;
  filas: [string, number | null][];
}) {
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <h4 className="mb-3 text-sm font-semibold">{titulo}</h4>
      <ul className="space-y-2 text-sm">
        {filas.map(([k, v]) => (
          <li key={k} className="flex items-center justify-between">
            <span className="text-slate-500">{k}</span>
            <span className="font-semibold tabular-nums">{pct(v)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

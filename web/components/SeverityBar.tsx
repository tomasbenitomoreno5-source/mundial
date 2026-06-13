/**
 * Barra de severidad de un árbitro: posición de su valor (p.ej. amarillas por
 * partido) dentro del rango del plantel, con la media marcada.
 */
export function SeverityBar({
  value,
  avg,
  max,
  unit = "",
}: {
  value: number;
  avg: number;
  max: number;
  unit?: string;
}) {
  const clamp = (x: number) => Math.max(0, Math.min(100, x));
  const pos = clamp(max > 0 ? (value / max) * 100 : 0);
  const avgPos = clamp(max > 0 ? (avg / max) * 100 : 0);
  const strict = value >= avg;

  return (
    <div className="w-full">
      <div className="relative h-3 w-full rounded-full bg-gradient-to-r from-emerald-200 via-amber-200 to-rose-300">
        {/* media del plantel */}
        <div
          className="absolute top-[-3px] h-[18px] w-0.5 bg-slate-500/70"
          style={{ left: `${avgPos}%` }}
          title={`Media plantel: ${avg.toFixed(2)}${unit}`}
        />
        {/* valor del árbitro */}
        <div
          className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-slate-900 shadow"
          style={{ left: `${pos}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] font-medium text-slate-400">
        <span>Permisivo</span>
        <span className={strict ? "text-rose-600" : "text-emerald-600"}>
          {value.toFixed(2)}
          {unit} · {strict ? "por encima" : "por debajo"} de la media (
          {avg.toFixed(2)}
          {unit})
        </span>
        <span>Estricto</span>
      </div>
    </div>
  );
}

import { pct } from "@/lib/format";

/** Barra apilada 1X2: victoria A / empate / victoria B. */
export function ProbBar({
  p1,
  pX,
  p2,
}: {
  p1: number | null;
  pX: number | null;
  p2: number | null;
}) {
  const a = p1 ?? 0;
  const x = pX ?? 0;
  const b = p2 ?? 0;
  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
      <div className="bg-indigo-600" style={{ width: `${a * 100}%` }} />
      <div className="bg-slate-300" style={{ width: `${x * 100}%` }} />
      <div className="bg-rose-500" style={{ width: `${b * 100}%` }} />
    </div>
  );
}

/** Leyenda 1X2 con porcentajes (tres columnas). */
export function ProbLegend({
  teamA,
  teamB,
  p1,
  pX,
  p2,
}: {
  teamA: string;
  teamB: string;
  p1: number | null;
  pX: number | null;
  p2: number | null;
}) {
  return (
    <div className="flex items-center justify-between text-xs text-slate-500">
      <span className="flex items-center gap-1.5">
        <i className="h-2 w-2 rounded-full bg-indigo-600" /> {pct(p1)}
      </span>
      <span className="flex items-center gap-1.5">
        <i className="h-2 w-2 rounded-full bg-slate-300" /> Empate {pct(pX)}
      </span>
      <span className="flex items-center gap-1.5">
        {pct(p2)} <i className="h-2 w-2 rounded-full bg-rose-500" />
      </span>
    </div>
  );
}

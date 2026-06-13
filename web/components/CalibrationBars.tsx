import type { Bin } from "@/lib/rendimiento";

/**
 * Calibración clara. Agrupamos los partidos por la probabilidad que les dio el
 * modelo; en cada grupo comparamos lo que estimó (su probabilidad media) con lo
 * que ocurrió de verdad (en cuántos pasó). Mostramos el recuento "X de N" para
 * que se vea de dónde sale el %. Componente puro.
 */
export function CalibrationBars({
  bins,
  etiqueta,
}: {
  bins: Bin[];
  etiqueta?: string;
}) {
  const utiles = bins.filter((b) => b.n > 0);
  if (utiles.length === 0) return null;
  return (
    <div>
      <p className="mb-4 text-xs leading-relaxed text-slate-500">
        Tomamos los partidos del histórico y los agrupamos por la probabilidad
        que les dio el modelo{etiqueta ? ` en "${etiqueta}"` : ""}. En cada grupo
        comparamos lo que{" "}
        <span className="font-medium text-indigo-600">estimó</span> (su
        probabilidad media) con lo que{" "}
        <span className="font-medium text-emerald-600">ocurrió</span> de verdad.
      </p>
      <div className="space-y-4">
        {utiles.map((b, i) => {
          const ocurrencias = Math.round(b.real * b.n);
          const ok = Math.abs(b.pred - b.real) <= 0.05;
          return (
            <div key={i}>
              <div className="mb-1.5 text-[11px] font-medium text-slate-500">
                Cuando el modelo daba {Math.round(b.lo * 100)}–
                {Math.round(Math.min(b.hi, 1) * 100)}%{" "}
                <span className="text-slate-400">
                  · {b.n} {b.n === 1 ? "partido" : "partidos"}
                </span>
              </div>
              <Barra
                etiqueta="Estimó"
                valor={b.pred}
                color="bg-indigo-500"
                detalle={`${Math.round(b.pred * 100)}% de media`}
              />
              <Barra
                etiqueta="Ocurrió"
                valor={b.real}
                color={ok ? "bg-emerald-500" : "bg-rose-400"}
                detalle={`${Math.round(b.real * 100)}% (${ocurrencias}/${b.n})`}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Barra({
  etiqueta,
  valor,
  color,
  detalle,
}: {
  etiqueta: string;
  valor: number;
  color: string;
  detalle: string;
}) {
  return (
    <div className="mt-1 flex items-center gap-2">
      <span className="w-14 shrink-0 text-right text-[10px] uppercase tracking-wide text-slate-400">
        {etiqueta}
      </span>
      <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.max(2, valor * 100)}%` }}
        />
      </div>
      <span className="w-28 shrink-0 text-right text-[11px] font-medium tabular-nums text-slate-500">
        {detalle}
      </span>
    </div>
  );
}

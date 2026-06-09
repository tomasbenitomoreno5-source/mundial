import Link from "next/link";

import { brier1x2, outcome, pred1x2, type Outcome } from "@/lib/accuracy";
import { flag } from "@/lib/flags";
import { pct } from "@/lib/format";
import { getSettledMatches } from "@/lib/queries";
import { teamES } from "@/lib/teams";

export const revalidate = 60; // ISR: se refresca a medida que se juegan partidos

export const metadata = { title: "Rendimiento del modelo · Mundial.Predict" };

const ETIQUETA: Record<Outcome, string> = { A: "1", X: "X", B: "2" };

export default async function RendimientoPage() {
  const settled = await getSettledMatches();
  const n = settled.length;

  let h1x2 = 0;
  let brierSum = 0;
  let nB = 0;
  let hB = 0;
  let nO = 0;
  let hO = 0;
  for (const m of settled) {
    const a = m.scoreA ?? 0;
    const b = m.scoreB ?? 0;
    const real = outcome(a, b);
    if (pred1x2(m.p1, m.pX, m.p2) === real) h1x2++;
    brierSum += brier1x2(m.p1 ?? 0, m.pX ?? 0, m.p2 ?? 0, real);
    if (m.bttsSi != null) {
      nB++;
      if (m.bttsSi >= 0.5 === (a > 0 && b > 0)) hB++;
    }
    if (m.golesOver25 != null) {
      nO++;
      if (m.golesOver25 >= 0.5 === a + b > 2.5) hO++;
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-2xl font-black tracking-tight">
        Rendimiento del modelo
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        Predicho vs realidad, a medida que se juegan los partidos.
      </p>

      {n === 0 ? (
        <div className="mt-8 rounded-3xl border border-dashed border-slate-300 py-16 text-center text-slate-500">
          Aún no se ha jugado ningún partido del Mundial.
          <br />
          Esta sección se llenará automáticamente cuando arranque el torneo.
        </div>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Partidos" value={String(n)} />
            <Metric label="Acierto 1X2" value={pct(h1x2 / n)} big />
            <Metric label="Acierto BTTS" value={nB ? pct(hB / nB) : "–"} />
            <Metric label="Acierto Over 2.5" value={nO ? pct(hO / nO) : "–"} />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Brier score 1X2: <b>{(brierSum / n).toFixed(3)}</b> (0 = perfecto;
            menor es mejor — un modelo sin información daría ~0.67).
          </p>

          <h2 className="mb-3 mt-8 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Partido a partido
          </h2>
          <div className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
                  <th className="px-4 py-2 font-medium">Partido</th>
                  <th className="px-3 py-2 text-center font-medium">Real</th>
                  <th className="px-3 py-2 text-center font-medium">Predicho</th>
                  <th className="px-3 py-2 text-center font-medium">1X2</th>
                </tr>
              </thead>
              <tbody>
                {settled.map((m) => {
                  const a = m.scoreA ?? 0;
                  const b = m.scoreB ?? 0;
                  const real = outcome(a, b);
                  const pred = pred1x2(m.p1, m.pX, m.p2);
                  const ok = pred === real;
                  return (
                    <tr key={m.id} className="border-t border-slate-100">
                      <td className="px-4 py-2">
                        <Link
                          href={`/predicciones/${m.id}`}
                          className="flex items-center gap-1.5 hover:underline"
                        >
                          {flag(m.teamAName)} {teamES(m.teamAName)} –{" "}
                          {teamES(m.teamBName)} {flag(m.teamBName)}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-center font-semibold tabular-nums">
                        {a}–{b}
                      </td>
                      <td className="px-3 py-2 text-center tabular-nums text-slate-500">
                        {ETIQUETA[pred]}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span
                          className={
                            ok ? "text-emerald-600" : "text-rose-500"
                          }
                        >
                          {ok ? "✓" : "✗"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  big,
}: {
  label: string;
  value: string;
  big?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <div
        className={`tabular-nums ${big ? "text-2xl font-black text-indigo-600" : "text-xl font-bold text-slate-900"}`}
      >
        {value}
      </div>
      <div className="mt-1 text-[11px] uppercase tracking-wide text-slate-400">
        {label}
      </div>
    </div>
  );
}

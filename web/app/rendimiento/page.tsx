import Link from "next/link";

import { Donut } from "@/components/Donut";
import { RendimientoMercadosLista } from "@/components/RendimientoMercadosLista";
import { outcome, pred1x2 } from "@/lib/accuracy";
import { flag } from "@/lib/flags";
import { getMarketPerformance, getSettledMatches } from "@/lib/queries";
import { teamES } from "@/lib/teams";

export const revalidate = 60; // ISR: se refresca con el re-seed del cron

export const metadata = { title: "Rendimiento del modelo · Mundial.Predict" };

const pct = (x: number) => `${Math.round(x * 100)}%`;
const notaDe = (ece: number) =>
  Math.round(Math.max(0, Math.min(1, 1 - ece / 0.15)) * 100);

export default async function RendimientoPage() {
  const [rows, settled] = await Promise.all([
    getMarketPerformance(),
    getSettledMatches(),
  ]);
  const x2 = rows.find((r) => r.mercado === "1X2");

  let aciertoVivo: number | null = null;
  if (settled.length) {
    const ok = settled.filter(
      (m) => pred1x2(m.p1, m.pX, m.p2) === outcome(m.scoreA ?? 0, m.scoreB ?? 0),
    ).length;
    aciertoVivo = ok / settled.length;
  }

  const notas = rows.map((r) => notaDe(r.ece));
  const notaMedia = notas.length
    ? Math.round(notas.reduce((a, b) => a + b, 0) / notas.length)
    : 0;
  const rangos = {
    alto: notas.filter((n) => n >= 80).length,
    medio: notas.filter((n) => n >= 60 && n < 80).length,
    bajo: notas.filter((n) => n < 60).length,
  };
  const total = rows.length || 1;
  const acierto1x2 = x2?.acierto ?? 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-black tracking-tight">Rendimiento del modelo</h1>
      <p className="mt-1 text-sm text-slate-500">
        Aquí puedes ver, con datos reales, lo bien que acierta el modelo — en el
        resultado de los partidos y en cada uno de sus mercados.
      </p>

      {/* === PRINCIPAL: mercado 1X2 === */}
      <section className="mt-6 rounded-3xl bg-white p-6 ring-1 ring-slate-200">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Resultado del partido (1X2) · el mercado principal
        </h2>
        <div className="mt-4 flex flex-col items-center gap-6 sm:flex-row sm:gap-8">
          <Donut value={acierto1x2} label={pct(acierto1x2)} sub="acierto" />
          <div className="flex-1 text-center sm:text-left">
            <p className="text-lg font-semibold text-slate-800">
              El modelo acierta quién gana en{" "}
              <span className="text-indigo-600">
                {Math.round(acierto1x2 * 10)} de cada 10
              </span>{" "}
              partidos.
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Medido sobre cientos de partidos históricos. Durante el Mundial,
              esta cifra se actualiza con cada partido jugado
              {aciertoVivo != null && (
                <>
                  {" "}
                  (ahora mismo, <b>{pct(aciertoVivo)}</b> en {settled.length})
                </>
              )}
              .
            </p>
          </div>
        </div>
      </section>

      {/* === Explicador === */}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Explica
          titulo="¿Qué es el acierto?"
          texto="De cada 10 partidos, en cuántos el modelo señala al ganador correcto (o el empate)."
        />
        <Explica
          titulo="¿Y la fiabilidad?"
          texto="Si el modelo dice “60% de probabilidad”, ¿pasa de verdad ~60% de las veces? Cuanto más cuadra, más fiable."
        />
        <Explica
          titulo="¿Para qué sirve?"
          texto="Para saber de qué mercados fiarte más. No todos se predicen igual de bien."
        />
      </div>

      {/* === Resultados partido a partido === */}
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Partido a partido
        </h2>
        {settled.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 py-12 text-center text-sm text-slate-500">
            Aún no se ha jugado ningún partido del Mundial.
            <br />
            Aquí verás cada partido: lo que predijo el modelo vs el resultado real.
          </div>
        ) : (
          <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
            {settled.map((m) => {
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
        )}
      </section>

      {/* === Fiabilidad por mercado === */}
      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Fiabilidad por mercado
        </h2>
        <div className="mb-3 mt-1 flex items-center gap-4">
          <div>
            <div className="text-3xl font-black tabular-nums text-slate-900">
              {notaMedia}
              <span className="text-base font-semibold text-slate-400">/100</span>
            </div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              nota media
            </div>
          </div>
          <p className="flex-1 text-sm text-slate-500">
            Cada uno de los <b>{rows.length} mercados</b> tiene una nota de 0 a
            100 según lo bien calibrado que está (cuánto se ajustan sus
            probabilidades a lo que pasa de verdad). Clica un mercado para ver su
            detalle.
          </p>
        </div>

        <div className="mb-1.5 flex h-3 overflow-hidden rounded-full">
          <div className="bg-emerald-500" style={{ width: `${(rangos.alto / total) * 100}%` }} />
          <div className="bg-amber-500" style={{ width: `${(rangos.medio / total) * 100}%` }} />
          <div className="bg-rose-400" style={{ width: `${(rangos.bajo / total) * 100}%` }} />
        </div>
        <div className="mb-4 flex gap-4 text-[11px] text-slate-400">
          <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />80-100 · {rangos.alto}</span>
          <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-500" />60-79 · {rangos.medio}</span>
          <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-rose-400" />0-59 · {rangos.bajo}</span>
        </div>

        <RendimientoMercadosLista rows={rows} />
        <p className="mt-3 text-xs text-slate-400">
          Basado en ~400 partidos reales de selecciones (2023-2026). Durante el
          Mundial se van sumando los resultados de cada partido.
        </p>
      </section>
    </div>
  );
}

function Explica({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/60">
      <h3 className="text-sm font-semibold text-slate-800">{titulo}</h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{texto}</p>
    </div>
  );
}

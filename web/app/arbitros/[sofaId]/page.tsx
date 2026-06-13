import Link from "next/link";
import { notFound } from "next/navigation";

import { SeverityBar } from "@/components/SeverityBar";
import { flag, flagCC } from "@/lib/flags";
import { formatFecha } from "@/lib/format";
import { teamES } from "@/lib/teams";
import {
  getRefereeDetail,
  getRefereeSofaIds,
  getReferees,
  type RefereeMatchRow,
} from "@/lib/queries";

export const revalidate = 60; // ISR: refleja el re-seed sin rebuild

export async function generateStaticParams() {
  const ids = await getRefereeSofaIds();
  return ids.map((sofaId) => ({ sofaId: String(sofaId) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ sofaId: string }>;
}) {
  const { sofaId } = await params;
  const detail = await getRefereeDetail(parseInt(sofaId, 10));
  if (!detail) return {};
  return { title: `${detail.ref.name} · Árbitro · Mundial.Predict` };
}

const pct = (x: number) => `${Math.round(x * 100)}%`;
const safe = (n: number, d: number) => (d > 0 ? n / d : 0);

export default async function RefereePage({
  params,
}: {
  params: Promise<{ sofaId: string }>;
}) {
  const { sofaId } = await params;
  const detail = await getRefereeDetail(parseInt(sofaId, 10));
  if (!detail) notFound();
  const { ref, matches, teamHistory } = detail;

  // Contexto del plantel para la barra de severidad + ranking.
  const all = await getReferees();
  const ypgOf = (r: { yellow: number; games: number }) => safe(r.yellow, r.games);
  const conP = all.filter((r) => r.games > 0);
  const avgYpg = conP.reduce((s, r) => s + ypgOf(r), 0) / (conP.length || 1);
  const maxYpg = Math.max(...conP.map(ypgOf), 0.01);

  const ypg = ypgOf(ref);
  const rpg = safe(ref.red, ref.games);
  const yrpg = safe(ref.yellowRed, ref.games);

  // Ranking de severidad dentro del plantel (1 = más estricto).
  const ordenSev = [...conP].sort((a, b) => ypgOf(b) - ypgOf(a));
  const rank = ordenSev.findIndex((r) => r.sofaId === ref.sofaId) + 1;
  const nPlantel = ordenSev.length;
  const percentil =
    rank > 0 && nPlantel > 1
      ? Math.round(((nPlantel - rank) / (nPlantel - 1)) * 100)
      : null;

  // Sesgo local/visita (de nuestro pool).
  const poolCards = ref.poolYellowHome + ref.poolYellowAway;
  const homeBias = poolCards > 0 ? ref.poolYellowHome / poolCards : null;
  // Penaltis/partido y reparto de tarjetas por mitad (de nuestro pool).
  const penPP = ref.poolGames > 0 ? safe(ref.poolPenalties, ref.poolGames) : null;
  const poolHalf = ref.poolYellow1h + ref.poolYellow2h;
  const share1h = poolHalf > 0 ? ref.poolYellow1h / poolHalf : null;

  // "Cómo son sus partidos": métricas de resultado de los últimos partidos.
  const conMarcador = matches.filter(
    (m) => m.scoreHome != null && m.scoreAway != null,
  );
  const nR = conMarcador.length;
  const sum = (f: (m: RefereeMatchRow) => number) =>
    conMarcador.reduce((s, m) => s + f(m), 0);
  const golesPP = nR ? safe(sum((m) => m.scoreHome! + m.scoreAway!), nR) : null;
  const pLocal = nR ? safe(sum((m) => (m.scoreHome! > m.scoreAway! ? 1 : 0)), nR) : null;
  const pEmpate = nR ? safe(sum((m) => (m.scoreHome! === m.scoreAway! ? 1 : 0)), nR) : null;
  const pVisita = nR ? safe(sum((m) => (m.scoreHome! < m.scoreAway! ? 1 : 0)), nR) : null;
  const pBtts = nR ? safe(sum((m) => (m.scoreHome! > 0 && m.scoreAway! > 0 ? 1 : 0)), nR) : null;
  const pOver = nR ? safe(sum((m) => (m.scoreHome! + m.scoreAway! >= 3 ? 1 : 0)), nR) : null;

  const chips: string[] = [`${ref.games} partidos (carrera)`];
  if (ref.poolGames > 0) chips.push(`${ref.poolGames} en nuestro pool`);
  if (ref.confederation) chips.push(ref.confederation);
  if (rank > 0) chips.push(`#${rank} de ${nPlantel} en severidad`);

  // Tarjetas reales/partido en el pool (si hubo backfill).
  const poolYpg = ref.poolGames > 0 ? safe(ref.poolYellow, ref.poolGames) : null;

  const partidoStats: [string, string, string][] = [];
  if (golesPP != null) partidoStats.push(["Goles/partido", golesPP.toFixed(2), "últimos"]);
  if (ref.poolFouls != null) partidoStats.push(["Faltas/partido", ref.poolFouls.toFixed(1), "pool"]);
  partidoStats.push(["Amarillas/partido", (poolYpg ?? ypg).toFixed(2), poolYpg != null ? "pool" : "carrera"]);
  partidoStats.push(["Rojas/partido", rpg.toFixed(2), "carrera"]);
  if (pLocal != null) partidoStats.push(["Victoria local", pct(pLocal), "últimos"]);
  if (pEmpate != null) partidoStats.push(["Empate", pct(pEmpate), "últimos"]);
  if (pVisita != null) partidoStats.push(["Victoria visitante", pct(pVisita), "últimos"]);
  if (pBtts != null) partidoStats.push(["Ambos marcan", pct(pBtts), "últimos"]);
  if (pOver != null) partidoStats.push(["Más de 2.5 goles", pct(pOver), "últimos"]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Link
        href="/arbitros"
        className="text-sm font-semibold text-indigo-600 hover:underline"
      >
        ← Árbitros
      </Link>

      {/* Cabecera */}
      <div className="mt-4 flex items-center gap-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200 sm:p-8">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`https://img.sofascore.com/api/v1/referee/${ref.sofaId}/image`}
          alt={ref.name}
          width={72}
          height={72}
          className="h-18 w-18 shrink-0 rounded-full bg-slate-100 object-cover ring-1 ring-slate-200"
          style={{ height: 72, width: 72 }}
        />
        <div className="min-w-0">
          <h1 className="text-2xl font-black tracking-tight">
            {flagCC(ref.countryCode)} {ref.name}
          </h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={c}
                className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600"
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Severidad */}
      <section className="mt-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
          Severidad
        </h2>
        <SeverityBar value={ypg} avg={avgYpg} max={maxYpg} unit=" am" />
        {percentil != null && (
          <p className="mt-2 text-xs text-slate-400">
            Más estricto que el {percentil}% del plantel.
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-1.5">
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
            {rpg.toFixed(2)} rojas/partido
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
            {yrpg.toFixed(2)} dobles amarillas/partido
          </span>
          {penPP != null && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              {penPP.toFixed(2)} penaltis/partido
            </span>
          )}
          {share1h != null && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              Tarjetas: {pct(share1h)} en 1ª / {pct(1 - share1h)} en 2ª
            </span>
          )}
          {homeBias != null && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              Sesgo tarjetas: {pct(homeBias)} local / {pct(1 - homeBias)} visita
            </span>
          )}
        </div>
      </section>

      {/* Cómo son sus partidos */}
      <section className="mt-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200">
        <h2 className="mb-1 text-sm font-bold uppercase tracking-wide text-slate-500">
          Cómo son sus partidos
        </h2>
        <p className="mb-4 text-xs text-slate-400">
          «últimos» = sus últimos {nR} partidos · «pool» = partidos de
          clasificación/amistosos que arbitró · «carrera» = total de su carrera.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {partidoStats.map(([label, val, src]) => (
            <div key={label} className="rounded-2xl bg-slate-50 p-3">
              <div className="text-lg font-black tabular-nums">{val}</div>
              <div className="text-xs text-slate-500">{label}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                {src}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Historial vs selecciones del Mundial */}
      {teamHistory.length > 0 && (
        <section className="mt-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200">
          <h2 className="mb-1 text-sm font-bold uppercase tracking-wide text-slate-500">
            Historial vs mundialistas
          </h2>
          <p className="mb-3 text-xs text-slate-400">
            Selecciones del Mundial 2026 que ha dirigido (de nuestro pool), con
            las amarillas medias de esos partidos.
          </p>
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {teamHistory.map((t) => (
              <li
                key={t.team}
                className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2">
                  <span className="text-lg leading-none">{flag(t.team)}</span>
                  {teamES(t.team)}
                </span>
                <span className="text-xs text-slate-500">
                  {t.games} {t.games === 1 ? "partido" : "partidos"} ·{" "}
                  <span className="font-semibold text-slate-700">
                    {safe(t.yellow, t.games).toFixed(1)} am
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Últimos partidos */}
      {matches.length > 0 && (
        <section className="mt-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            Últimos partidos
          </h2>
          <ul className="divide-y divide-slate-100">
            {matches.slice(0, 20).map((m) => (
              <li key={m.id} className="flex items-center gap-2 py-2 text-sm">
                <span className="w-24 shrink-0 text-xs text-slate-400">
                  {m.ts ? formatFecha(new Date(m.ts * 1000).toISOString().slice(0, 10)) : ""}
                </span>
                <span className="min-w-0 flex-1 truncate">
                  {m.home} <span className="text-slate-400">vs</span> {m.away}
                </span>
                {m.scoreHome != null && m.scoreAway != null && (
                  <span className="shrink-0 font-bold tabular-nums">
                    {m.scoreHome}–{m.scoreAway}
                  </span>
                )}
                {m.yellow != null && (
                  <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                    {m.yellow} am
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

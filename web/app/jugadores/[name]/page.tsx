import Link from "next/link";
import { notFound } from "next/navigation";

import {
  PlayerMarketCard,
  type PlayerMarketGroup,
} from "@/components/PlayerMarketCard";
import { StyleRadar } from "@/components/StyleRadar";
import { flag } from "@/lib/flags";
import { formatFecha } from "@/lib/format";
import { fmtMetric } from "@/lib/metric-labels";
import { PLAYER_MARKETS } from "@/lib/player-markets";
import {
  getPlayerDetail,
  getPlayerNames,
  type PlayerMarketRow,
} from "@/lib/queries";
import { teamES } from "@/lib/teams";

export const revalidate = 1800;

export async function generateStaticParams() {
  const names = await getPlayerNames();
  return names.map((name) => ({ name }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  return { title: `${decodeURIComponent(name)} · Mundial.Predict` };
}

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name: raw } = await params;
  const name = decodeURIComponent(raw);
  const detail = await getPlayerDetail(name);
  if (!detail) notFound();
  const { agg, markets, matches } = detail;

  const radar = [
    { label: "Goleador", value: agg.radarGol },
    { label: "Tirador", value: agg.radarTiro },
    { label: "Creador", value: agg.radarCrea },
    { label: "Pasador", value: agg.radarPase },
    { label: "Regateador", value: agg.radarRegate },
    { label: "Defensa", value: agg.radarDef },
  ];

  // Mercados por partido del jugador.
  const ou = (rows: PlayerMarketRow[], m: string) =>
    rows
      .filter((r) => r.mercado === m && r.evento === "over")
      .map((r) => ({ linea: r.linea, over: r.probabilidad }))
      .sort((a, b) => parseFloat(a.linea) - parseFloat(b.linea));
  const si = (rows: PlayerMarketRow[], m: string) =>
    rows.find((r) => r.mercado === m && r.evento === "si")?.probabilidad ?? null;
  const porPartido = matches.map((mt) => {
    const rows = markets.filter((r) => r.matchId === mt.id);
    const grupo: PlayerMarketGroup = {
      player: agg.player,
      team: agg.team,
      binarios: {},
      ou: {},
    };
    for (const d of PLAYER_MARKETS) {
      if (d.tipo === "binary") grupo.binarios[d.key] = si(rows, d.key);
      else grupo.ou[d.key] = ou(rows, d.key);
    }
    const rival = mt.teamAName === agg.team ? mt.teamBName : mt.teamAName;
    return { mt, grupo, rival };
  });

  const stats: [string, string][] = [
    ["Tiros/p", fmtMetric(agg.tiros)],
    ["A puerta/p", fmtMetric(agg.sot)],
    ["xG/p", fmtMetric(agg.xg)],
    ["xA/p", fmtMetric(agg.xa)],
    ["Pases clave/p", fmtMetric(agg.pasesClave)],
    ["Pases/p", fmtMetric(agg.pases)],
    ["Regates/p", fmtMetric(agg.regates)],
    ["Entradas/p", fmtMetric(agg.entradas)],
    ["Intercep./p", fmtMetric(agg.intercep)],
    ["Duelos g./p", fmtMetric(agg.duelos)],
    ["Recuper./p", fmtMetric(agg.recuperaciones)],
    ["Min/p", fmtMetric(agg.minutos)],
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link
        href={`/selecciones/${encodeURIComponent(agg.team)}`}
        className="text-sm text-slate-500 hover:text-slate-900"
      >
        ← {flag(agg.team)} {teamES(agg.team)}
      </Link>

      {/* Cabecera */}
      <div className="mt-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200 sm:p-8">
        <h1 className="text-2xl font-black tracking-tight">{agg.player}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {flag(agg.team)} {teamES(agg.team)} · {agg.partidos} partidos ·{" "}
          {agg.goles} goles · {agg.asistencias} asistencias
          {agg.rating != null && ` · rating ${fmtMetric(agg.rating)}`}
        </p>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Radar */}
        <section className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Perfil
          </h2>
          <p className="mb-2 text-xs text-slate-400">
            Percentil entre todos los jugadores (100 = el que más).
          </p>
          <StyleRadar data={radar} />
        </section>

        {/* Medias por partido */}
        <section className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Medias por partido
          </h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            {stats.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <span className="text-slate-500">{k}</span>
                <span className="tabular-nums text-slate-700">{v}</span>
              </div>
            ))}
          </dl>
        </section>
      </div>

      {/* Mercados por partido */}
      {porPartido.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Sus mercados en el Mundial
          </h2>
          <div className="space-y-2">
            {porPartido.map(({ mt, grupo, rival }) => (
              <PlayerMarketCard
                key={mt.id}
                j={grupo}
                headerLabel={`${flag(rival)} vs ${teamES(rival)} · ${formatFecha(mt.date)}`}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

import Link from "next/link";

import { TeamProfile } from "@/components/TeamProfile";
import { flag } from "@/lib/flags";
import { teamES } from "@/lib/teams";
import {
  getLinkableTeamNames,
  getTeamDetail,
  getTeamPlayers,
} from "@/lib/queries";

export const revalidate = 60; // ISR: refleja el re-seed sin rebuild

export async function generateStaticParams() {
  const names = await getLinkableTeamNames();
  return names.map((name) => ({ team: name }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;
  return { title: `${teamES(decodeURIComponent(team))} · Mundial.Predict` };
}

export default async function TeamPage({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;
  const name = decodeURIComponent(team);
  const [detail, players] = await Promise.all([
    getTeamDetail(name),
    getTeamPlayers(name),
  ]);

  // Selecciones enlazadas como "similares" que no están entre las 48 del
  // Mundial: no tienen ficha; mostramos un aviso en vez de un 404.
  if (!detail) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <Link
          href="/selecciones"
          className="text-sm text-slate-500 hover:text-slate-900"
        >
          ← Todas las selecciones
        </Link>
        <div className="mt-8 flex flex-col items-center rounded-3xl bg-white p-10 text-center ring-1 ring-slate-200">
          <span className="text-5xl leading-none">{flag(name)}</span>
          <h1 className="mt-3 text-xl font-bold tracking-tight">
            {teamES(name)}
          </h1>
          <p className="mt-2 max-w-sm text-sm text-slate-500">
            No hay datos de esta selección. No está entre las 48 clasificadas
            para el Mundial 2026.
          </p>
        </div>
      </div>
    );
  }

  const historial = detail.historial.map((h) => ({
    partidoCompleto: h.partidoCompleto,
    rival: h.rival,
    tipoEquipo: h.tipoEquipo,
    golesFavor: h.golesFavor,
    golesContra: h.golesContra,
    metrics: JSON.parse(h.metrics) as Record<string, number | null>,
  }));

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link
        href="/selecciones"
        className="text-sm text-slate-500 hover:text-slate-900"
      >
        ← Todas las selecciones
      </Link>
      <div className="mt-4">
        <TeamProfile
          name={name}
          similares={detail.similares.map((s) => ({
            rank: s.rank,
            vecino: s.vecino,
            peso: s.peso,
          }))}
          perfiles={detail.perfiles.map((p) => ({
            metrica: p.metrica,
            media: p.media,
            mediana: p.mediana,
          }))}
          matches={detail.matches.map((m) => ({
            id: m.id,
            date: m.date,
            teamAName: m.teamAName,
            teamBName: m.teamBName,
            p1: m.p1,
            pX: m.pX,
            p2: m.p2,
          }))}
          historial={historial}
          players={players}
          rankByMetric={detail.rankByMetric}
          totalTeams={detail.totalTeams}
          radar={detail.radar}
          odds={detail.odds}
        />
      </div>
    </div>
  );
}

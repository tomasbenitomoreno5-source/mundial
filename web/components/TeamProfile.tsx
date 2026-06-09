"use client";

import Link from "next/link";
import { useState } from "react";

import {
  HistorialSelecciones,
  type HistorialItem,
} from "@/components/HistorialSelecciones";
import { InfoTip } from "@/components/InfoTip";
import { StyleRadar, type RadarAxis } from "@/components/StyleRadar";
import { flag } from "@/lib/flags";
import { formatFecha, pct } from "@/lib/format";
import { fmtMetric, METRIC_DESC, metricLabel } from "@/lib/metric-labels";
import type { TeamPlayer } from "@/lib/queries";
import { teamES } from "@/lib/teams";

export type SimilarLike = { rank: number; vecino: string; peso: number };
export type PerfilLike = {
  metrica: string;
  media: number | null;
  mediana: number | null;
};
export type MatchLike = {
  id: string;
  date: string;
  teamAName: string;
  teamBName: string;
  p1: number | null;
  pX: number | null;
  p2: number | null;
};

const TABS = [
  { key: "resumen", label: "Resumen" },
  { key: "jugadores", label: "Jugadores" },
  { key: "historial", label: "Historial" },
] as const;

function ratingClase(r: number): string {
  if (r >= 7.2) return "bg-emerald-50 text-emerald-700";
  if (r >= 6.8) return "bg-amber-50 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function Stat({
  label,
  value,
  big,
}: {
  label: string;
  value: string;
  big?: boolean;
}) {
  return (
    <div>
      <div
        className={`tabular-nums ${big ? "text-lg font-bold text-slate-900" : "font-medium"}`}
      >
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wide text-slate-400">
        {label}
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-slate-500">{label}</span>
      <span className="tabular-nums text-slate-700">{value}</span>
    </div>
  );
}

export function TeamProfile({
  name,
  similares,
  perfiles,
  matches,
  historial,
  players,
  rankByMetric,
  totalTeams,
  radar,
  odds,
}: {
  name: string;
  similares: SimilarLike[];
  perfiles: PerfilLike[];
  matches: MatchLike[];
  historial: HistorialItem[];
  players: TeamPlayer[];
  rankByMetric: Record<string, number>;
  totalTeams: number;
  radar: RadarAxis[];
  odds: {
    pGrupo: number;
    pR16: number;
    pQf: number;
    pSf: number;
    pFinal: number;
    pCampeon: number;
  } | null;
}) {
  const [tab, setTab] = useState<"resumen" | "historial" | "jugadores">(
    "resumen",
  );

  return (
    <div>
      {/* Cabecera */}
      <div className="rounded-3xl bg-white p-6 ring-1 ring-slate-200 sm:p-8">
        <div className="flex items-center gap-4">
          <span className="text-5xl leading-none">{flag(name)}</span>
          <h1 className="text-2xl font-black tracking-tight">{teamES(name)}</h1>
        </div>
      </div>

      {/* Chips */}
      <div className="sticky top-[57px] z-10 -mx-4 my-6 border-b border-slate-200 bg-[var(--background)]/95 px-4 py-3 backdrop-blur">
        <div className="flex gap-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              aria-pressed={t.key === tab}
              onClick={() => setTab(t.key)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                t.key === tab
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "resumen" ? (
        <div className="space-y-8">
          {/* Camino al título */}
          {odds && (
            <section>
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Camino al título
              </h2>
              <p className="mb-3 text-xs text-slate-400">
                Probabilidad de llegar a cada ronda (Monte Carlo del torneo).
              </p>
              <div className="grid grid-cols-3 gap-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200 sm:grid-cols-6">
                <Stat label="Pasa grupo" value={pct(odds.pGrupo)} />
                <Stat label="Octavos" value={pct(odds.pR16)} />
                <Stat label="Cuartos" value={pct(odds.pQf)} />
                <Stat label="Semis" value={pct(odds.pSf)} />
                <Stat label="Final" value={pct(odds.pFinal)} />
                <Stat label="Campeón" value={pct(odds.pCampeon)} big />
              </div>
            </section>
          )}

          {/* Partidos del Mundial */}
          <section>
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Sus partidos del Mundial
            </h2>
            <p className="mb-3 text-xs text-slate-400">
              Probabilidad del modelo: 20.000 simulaciones Monte Carlo por
              partido + ELO/Dixon-Coles.
            </p>
            {matches.length === 0 ? (
              <p className="text-sm text-slate-500">Sin datos.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {matches.map((m) => {
                  const esA = m.teamAName === name;
                  const rival = esA ? m.teamBName : m.teamAName;
                  const pGana = esA ? m.p1 : m.p2;
                  const pPierde = esA ? m.p2 : m.p1;
                  return (
                    <Link
                      key={m.id}
                      href={`/predicciones/${m.id}`}
                      className="flex items-center justify-between rounded-2xl bg-white p-4 ring-1 ring-slate-200 transition hover:shadow-md"
                    >
                      <span className="flex items-center gap-2">
                        <span className="text-xl leading-none">
                          {flag(rival)}
                        </span>
                        <span className="text-sm">
                          <span className="block font-medium text-slate-900">
                            {teamES(rival)}
                          </span>
                          <span className="text-xs text-slate-400">
                            {formatFecha(m.date)}
                          </span>
                        </span>
                      </span>
                      <span className="text-right text-xs tabular-nums text-slate-500">
                        <span className="font-semibold text-indigo-600">
                          {pct(pGana)}
                        </span>{" "}
                        / {pct(m.pX)} / {pct(pPierde)}
                      </span>
                    </Link>
                  );
                })}
              </div>
            )}
          </section>

          {/* Perfil de estilo (radar) */}
          <section>
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Perfil de estilo
            </h2>
            <p className="mb-3 text-xs text-slate-400">
              Percentil de la selección entre las 48 mundialistas en cada eje
              (100 = la que más).
            </p>
            <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
              <StyleRadar data={radar} />
            </div>
          </section>

          {/* Estilo / similares */}
          <section>
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Selecciones similares
            </h2>
            <p className="mb-3 text-xs text-slate-400">
              Selecciones con el perfil de métricas más parecido (vecinos KNN).
            </p>
            {similares.length === 0 ? (
              <p className="text-sm text-slate-500">Sin datos.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {similares.map((s) => (
                  <Link
                    key={s.rank}
                    href={`/selecciones/${encodeURIComponent(s.vecino)}`}
                    className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm ring-1 ring-slate-200 transition hover:ring-indigo-300"
                  >
                    <span className="leading-none">{flag(s.vecino)}</span>
                    <span className="text-slate-700">{teamES(s.vecino)}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          {/* Perfiles de métricas */}
          <section>
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Perfiles de métricas (por partido)
            </h2>
            <p className="mb-3 text-xs text-slate-400">
              Media de sus partidos. El puesto (Ranking Mundial) es entre las 48
              selecciones mundialistas.
            </p>
            {perfiles.length === 0 ? (
              <p className="text-sm text-slate-500">Sin datos.</p>
            ) : (
              <div className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
                      <th className="px-4 py-2 font-medium">Métrica</th>
                      <th className="px-4 py-2 text-right font-medium">Media</th>
                      <th className="px-4 py-2 text-right font-medium">
                        Mediana
                      </th>
                      <th className="px-4 py-2 text-right font-medium">
                        Ranking Mundial
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {perfiles.map((p) => (
                      <tr key={p.metrica} className="border-t border-slate-100">
                        <td className="px-4 py-2 text-slate-600">
                          {metricLabel(p.metrica)}
                          {METRIC_DESC[p.metrica] && (
                            <span className="block text-xs font-normal text-slate-400">
                              {METRIC_DESC[p.metrica]}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {fmtMetric(p.media)}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-slate-500">
                          {fmtMetric(p.mediana)}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-slate-400">
                          {rankByMetric[p.metrica]
                            ? `${rankByMetric[p.metrica]} / ${totalTeams}`
                            : "–"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : tab === "jugadores" ? (
        <section>
          <h2 className="mb-3 flex items-center text-sm font-semibold uppercase tracking-wide text-slate-400">
            Jugadores
            <InfoTip text="Estrellas de la selección con datos. Medias por partido de su telemetría reciente." />
          </h2>
          {players.length === 0 ? (
            <p className="text-sm text-slate-500">
              Sin datos de jugadores para esta selección.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {players.map((p) => (
                <Link
                  key={p.player}
                  href={`/jugadores/${encodeURIComponent(p.player)}`}
                  className="block rounded-2xl bg-white p-4 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <span className="truncate font-semibold text-slate-900">
                      {p.player}
                    </span>
                    {p.rating != null && (
                      <span
                        className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-bold tabular-nums ${ratingClase(
                          p.rating,
                        )}`}
                      >
                        {fmtMetric(p.rating)}
                      </span>
                    )}
                  </div>
                  {/* Totales del periodo */}
                  <div className="mb-3 flex gap-4 text-sm">
                    <Stat label="PJ" value={String(p.partidos)} big />
                    <Stat label="Goles" value={String(p.goles)} big />
                    <Stat label="Asist." value={String(p.asistencias)} big />
                  </div>
                  {/* Medias por partido */}
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                    <StatRow label="Tiros/p" value={fmtMetric(p.tirosPorPartido)} />
                    <StatRow label="A puerta/p" value={fmtMetric(p.sotPorPartido)} />
                    <StatRow label="xG/p" value={fmtMetric(p.xgPorPartido)} />
                    <StatRow label="xA/p" value={fmtMetric(p.xaPorPartido)} />
                    <StatRow label="P. clave/p" value={fmtMetric(p.pasesClavePorPartido)} />
                    <StatRow label="Pases/p" value={fmtMetric(p.pasesPorPartido)} />
                    <StatRow label="Regates/p" value={fmtMetric(p.regatesPorPartido)} />
                    <StatRow label="Entradas/p" value={fmtMetric(p.entradasPorPartido)} />
                    <StatRow label="Intercep./p" value={fmtMetric(p.intercepcionesPorPartido)} />
                    <StatRow label="Duelos g./p" value={fmtMetric(p.duelosGanadosPorPartido)} />
                    <StatRow label="Recuper./p" value={fmtMetric(p.recuperacionesPorPartido)} />
                    <StatRow label="Min/p" value={fmtMetric(p.minutos)} />
                  </dl>
                </Link>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Historial partido a partido
          </h2>
          <HistorialSelecciones historial={historial} teamName={name} />
        </section>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Dropdown, type Option } from "@/components/Dropdown";
import { flagCC } from "@/lib/flags";

export type RefRow = {
  sofaId: number;
  name: string;
  country: string | null;
  countryCode: string | null;
  confederation: string | null;
  games: number;
  ypg: number;
  rank: number;
  sevLabel: string;
  sevCls: string;
};

export function ArbitrosBrowser({ referees }: { referees: RefRow[] }) {
  const [conf, setConf] = useState("all");
  const [orden, setOrden] = useState("sev_desc");

  const confs = useMemo(
    () =>
      [...new Set(referees.map((r) => r.confederation).filter(Boolean))].sort() as string[],
    [referees],
  );
  const confOpts: Option[] = [
    { value: "all", label: "Todas las confederaciones" },
    ...confs.map((c) => ({ value: c, label: c })),
  ];
  const ordenOpts: Option[] = [
    { value: "sev_desc", label: "Más estrictos primero" },
    { value: "sev_asc", label: "Más permisivos primero" },
    { value: "games_desc", label: "Más partidos" },
  ];

  const lista = useMemo(() => {
    let l = referees;
    if (conf !== "all") l = l.filter((r) => r.confederation === conf);
    const cmp: Record<string, (a: RefRow, b: RefRow) => number> = {
      sev_desc: (a, b) => b.ypg - a.ypg,
      sev_asc: (a, b) => a.ypg - b.ypg,
      games_desc: (a, b) => b.games - a.games,
    };
    return [...l].sort(cmp[orden]);
  }, [referees, conf, orden]);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Dropdown
          value={conf}
          options={confOpts}
          onChange={setConf}
          ariaLabel="Filtrar por confederación"
        />
        <Dropdown
          value={orden}
          options={ordenOpts}
          onChange={setOrden}
          ariaLabel="Ordenar"
        />
        <span className="ml-auto text-xs text-slate-500">
          {lista.length} {lista.length === 1 ? "árbitro" : "árbitros"}
        </span>
      </div>

      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {lista.map((r) => (
          <li key={r.sofaId}>
            <Link
              href={`/arbitros/${r.sofaId}`}
              className="flex items-center gap-3 rounded-2xl bg-white p-3 ring-1 ring-slate-200 transition hover:ring-indigo-300"
            >
              <span className="w-6 shrink-0 text-center text-sm font-bold text-slate-300">
                {r.rank}
              </span>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`https://img.sofascore.com/api/v1/referee/${r.sofaId}/image`}
                alt={r.name}
                width={44}
                height={44}
                className="h-11 w-11 shrink-0 rounded-full bg-slate-100 object-cover ring-1 ring-slate-200"
                style={{ height: 44, width: 44 }}
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-bold">
                  {flagCC(r.countryCode)} {r.name}
                </div>
                <div className="text-xs text-slate-500">
                  {r.country} · {r.games} partidos
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-sm font-black tabular-nums">
                  {r.ypg.toFixed(2)}
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${r.sevCls}`}
                >
                  {r.sevLabel}
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

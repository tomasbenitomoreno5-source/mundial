"use client";

import { useState } from "react";

import { OverUnderTable, type OULine } from "@/components/OverUnderTable";
import { flag } from "@/lib/flags";
import { pct } from "@/lib/format";
import {
  PLAYER_MARKET_CATS,
  PLAYER_MARKETS_BINARY,
  PLAYER_MARKETS_OU,
} from "@/lib/player-markets";

export type PlayerMarketGroup = {
  player: string;
  team: string;
  binarios: Record<string, number | null>;
  ou: Record<string, OULine[]>;
};

/**
 * Tarjeta de mercados de un jugador: colapsada muestra nombre + "marca gol";
 * al expandir, los mercados sí/no (pills) + chips de categoría que filtran los
 * Over/Under (tiros, pases, defensa, …).
 */
export function PlayerMarketCard({
  j,
  headerLabel,
}: {
  j: PlayerMarketGroup;
  headerLabel?: string;
}) {
  const [open, setOpen] = useState(false);

  const cats: string[] = PLAYER_MARKET_CATS.filter((c) =>
    PLAYER_MARKETS_OU.some(
      (d) => d.cat === c && (j.ou[d.key]?.length ?? 0) > 0,
    ),
  );
  const [cat, setCat] = useState<string>(cats[0] ?? "");
  const binPills = PLAYER_MARKETS_BINARY.filter((d) => j.binarios[d.key] != null);
  const catActiva = cats.includes(cat) ? cat : (cats[0] ?? "");

  return (
    <div className="rounded-2xl bg-white ring-1 ring-slate-200">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 p-4 text-left"
      >
        <span className="flex items-center gap-1.5 font-semibold text-slate-900">
          {headerLabel ? (
            headerLabel
          ) : (
            <>
              {j.team && <span className="leading-none">{flag(j.team)}</span>}
              {j.player}
            </>
          )}
        </span>
        <span className="flex items-center gap-2">
          {j.binarios["anytime_scorer"] != null && (
            <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
              Gol {pct(j.binarios["anytime_scorer"])}
            </span>
          )}
          <span className="text-slate-400">{open ? "▾" : "▸"}</span>
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-3">
          {binPills.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {binPills.map((d) => (
                <span
                  key={d.key}
                  className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
                >
                  {d.label}{" "}
                  <span className="font-bold">{pct(j.binarios[d.key])}</span>
                </span>
              ))}
            </div>
          )}

          {cats.length > 0 && (
            <>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {cats.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={c === catActiva}
                    onClick={() => setCat(c)}
                    className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition ${
                      c === catActiva
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                {PLAYER_MARKETS_OU.filter((d) => d.cat === catActiva).map((d) => (
                  <OverUnderTable
                    key={d.key}
                    titulo={d.label}
                    lineas={j.ou[d.key] ?? []}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

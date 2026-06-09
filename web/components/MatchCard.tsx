import Link from "next/link";

import { ProbBar, ProbLegend } from "@/components/ProbBar";
import { flag } from "@/lib/flags";
import { formatFecha, pct } from "@/lib/format";
import { teamES } from "@/lib/teams";

export type MatchLike = {
  id: string;
  date: string;
  teamAName: string;
  teamBName: string;
  groupLabel: string | null;
  p1: number | null;
  pX: number | null;
  p2: number | null;
  bttsSi: number | null;
  golesOver25: number | null;
  cornersOver95: number | null;
};

/** Quién es el favorito (mayor de p1/pX/p2). */
function favorito(m: MatchLike): "A" | "X" | "B" {
  const a = m.p1 ?? 0;
  const x = m.pX ?? 0;
  const b = m.p2 ?? 0;
  if (a >= x && a >= b) return "A";
  if (b >= a && b >= x) return "B";
  return "X";
}

export function MatchCard({ m }: { m: MatchLike }) {
  const fav = favorito(m);
  return (
    <Link
      href={`/predicciones/${m.id}`}
      className="group block rounded-2xl bg-white p-5 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/70"
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs font-medium text-slate-400">
          {formatFecha(m.date)}
        </span>
        {m.groupLabel && (
          <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600">
            Grupo {m.groupLabel}
          </span>
        )}
      </div>

      <div className="mb-4 space-y-2">
        <TeamRow
          name={m.teamAName}
          prob={m.p1}
          highlight={fav === "A"}
          accent="indigo"
        />
        <TeamRow
          name={m.teamBName}
          prob={m.p2}
          highlight={fav === "B"}
          accent="rose"
        />
      </div>

      <ProbBar p1={m.p1} pX={m.pX} p2={m.p2} />
      <div className="mt-2">
        <ProbLegend
          teamA={m.teamAName}
          teamB={m.teamBName}
          p1={m.p1}
          pX={m.pX}
          p2={m.p2}
        />
      </div>
    </Link>
  );
}

function TeamRow({
  name,
  prob,
  highlight,
  accent,
}: {
  name: string;
  prob: number | null;
  highlight: boolean;
  accent: "indigo" | "rose";
}) {
  const accentText = accent === "indigo" ? "text-indigo-600" : "text-rose-600";
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2.5">
        <span className="text-xl leading-none">{flag(name)}</span>
        <span
          className={`text-sm ${
            highlight ? "font-semibold text-slate-900" : "text-slate-600"
          }`}
        >
          {teamES(name)}
        </span>
      </span>
      <span
        className={`text-sm tabular-nums ${
          highlight ? `font-bold ${accentText}` : "text-slate-400"
        }`}
      >
        {pct(prob)}
      </span>
    </div>
  );
}

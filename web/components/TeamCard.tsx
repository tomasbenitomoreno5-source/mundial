import Link from "next/link";

import { flag } from "@/lib/flags";
import { teamES } from "@/lib/teams";

/** Ticket de una selección para el listado. */
export function TeamCard({
  name,
  groupLabel,
}: {
  name: string;
  groupLabel: string | null;
}) {
  return (
    <Link
      href={`/selecciones/${encodeURIComponent(name)}`}
      className="group flex items-center gap-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/70"
    >
      <span className="text-3xl leading-none">{flag(name)}</span>
      <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">
        {teamES(name)}
      </span>
      {groupLabel && (
        <span className="shrink-0 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600">
          Grupo {groupLabel}
        </span>
      )}
    </Link>
  );
}

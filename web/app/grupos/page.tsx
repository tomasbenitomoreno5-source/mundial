import Link from "next/link";

import { flag } from "@/lib/flags";
import { pct } from "@/lib/format";
import { getGroupStandings } from "@/lib/queries";
import { teamES } from "@/lib/teams";

export const revalidate = 1800;

export const metadata = { title: "Grupos · Mundial.Predict" };

export default async function GruposPage() {
  const grupos = await getGroupStandings();

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-2xl font-black tracking-tight">Grupos</h1>
      <p className="mt-1 text-sm text-slate-500">
        Clasificación simulada de cada grupo (Monte Carlo del torneo). Pasan los
        2 primeros + los 8 mejores terceros.
      </p>
      <p className="mt-1 text-xs text-slate-400">
        <b>1º</b> / <b>2º</b> = probabilidad de acabar primero / segundo de
        grupo · <b>Pasa</b> = probabilidad de clasificar (incl. mejor tercero) ·{" "}
        <b>Pts</b> = puntos medios.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {grupos.map(([g, equipos]) => (
          <section
            key={g}
            className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200"
          >
            <h2 className="border-b border-slate-100 px-4 py-2 text-sm font-bold">
              Grupo {g}
            </h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-1.5 font-medium">Selección</th>
                  <th className="px-2 py-1.5 text-right font-medium">1º</th>
                  <th className="px-2 py-1.5 text-right font-medium">2º</th>
                  <th className="px-2 py-1.5 text-right font-medium">Pasa</th>
                  <th className="px-3 py-1.5 text-right font-medium">Pts</th>
                </tr>
              </thead>
              <tbody>
                {equipos.map((e) => (
                  <tr key={e.name} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <Link
                        href={`/selecciones/${encodeURIComponent(e.name)}`}
                        className="flex items-center gap-1.5 hover:underline"
                      >
                        <span className="leading-none">{flag(e.name)}</span>
                        <span className="truncate">{teamES(e.name)}</span>
                      </Link>
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums text-slate-500">
                      {pct(e.p1)}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums text-slate-500">
                      {pct(e.p2)}
                    </td>
                    <td className="px-2 py-2 text-right font-semibold tabular-nums text-indigo-600">
                      {pct(e.pAdv)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                      {e.pts.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  );
}

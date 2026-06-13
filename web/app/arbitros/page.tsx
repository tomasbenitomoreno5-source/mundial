import { ArbitrosBrowser, type RefRow } from "@/components/ArbitrosBrowser";
import { getReferees } from "@/lib/queries";

export const revalidate = 60; // ISR: refleja el re-seed sin rebuild

export const metadata = {
  title: "Árbitros · Mundial.Predict",
};

function severidad(ypg: number, avg: number): { label: string; cls: string } {
  const r = avg > 0 ? ypg / avg : 1;
  if (r >= 1.35) return { label: "Muy estricto", cls: "bg-rose-100 text-rose-700" };
  if (r >= 1.12) return { label: "Estricto", cls: "bg-amber-100 text-amber-700" };
  if (r <= 0.85) return { label: "Permisivo", cls: "bg-emerald-100 text-emerald-700" };
  return { label: "Medio", cls: "bg-slate-100 text-slate-600" };
}

export default async function ArbitrosPage() {
  const refs = await getReferees();
  const ypgOf = (r: { yellow: number; games: number }) =>
    r.games > 0 ? r.yellow / r.games : 0;

  const conPartidos = refs.filter((r) => r.games > 0);
  const avg =
    conPartidos.reduce((s, r) => s + ypgOf(r), 0) / (conPartidos.length || 1);

  // Ranking global por severidad (amarillas/partido de carrera).
  const ordenados = [...refs].sort((a, b) => ypgOf(b) - ypgOf(a));
  const rows: RefRow[] = ordenados.map((r, i) => {
    const ypg = ypgOf(r);
    const sev = severidad(ypg, avg);
    return {
      sofaId: r.sofaId,
      name: r.name,
      country: r.country,
      countryCode: r.countryCode,
      confederation: r.confederation,
      games: r.games,
      ypg,
      rank: i + 1,
      sevLabel: sev.label,
      sevCls: sev.cls,
    };
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="mb-1 text-2xl font-black tracking-tight">Árbitros</h1>
      <p className="mb-6 text-sm text-slate-500">
        Plantel de árbitros principales del Mundial 2026 ({refs.length}).
        Ordenados por severidad (amarillas por partido en su carrera). Media del
        plantel: {avg.toFixed(2)} am/partido.
      </p>

      {refs.length === 0 ? (
        <p className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-800 ring-1 ring-amber-200">
          Aún no hay datos de árbitros. Ejecuta{" "}
          <code className="font-mono">extraer_arbitros.py</code> y vuelve a
          sembrar la base de datos.
        </p>
      ) : (
        <ArbitrosBrowser referees={rows} />
      )}
    </div>
  );
}

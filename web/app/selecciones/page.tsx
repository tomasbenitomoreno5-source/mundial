import { SeleccionesBrowser } from "@/components/SeleccionesBrowser";
import { getTeams } from "@/lib/queries";

export const revalidate = 1800; // ISR: refleja el re-seed sin rebuild

export const metadata = {
  title: "Selecciones · Mundial.Predict",
};

export default async function SeleccionesPage() {
  const teams = await getTeams();
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-black tracking-tight">Selecciones</h1>
      <SeleccionesBrowser
        teams={teams.map((t) => ({
          name: t.name,
          groupLabel: t.groupLabel,
        }))}
      />
    </div>
  );
}

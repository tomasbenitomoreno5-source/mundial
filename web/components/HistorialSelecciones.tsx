"use client";

import { useState } from "react";

import { flag } from "@/lib/flags";
import { HIST_CATEGORIAS } from "@/lib/historial-ui";
import { fmtMetric, metricLabel } from "@/lib/metric-labels";
import { teamES } from "@/lib/teams";

export type HistorialItem = {
  partidoCompleto: string | null;
  rival: string | null;
  tipoEquipo: string | null;
  golesFavor: number | null;
  golesContra: number | null;
  metrics: Record<string, number | null>;
};

function norm(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

/** Línea de partido en orden local–visitante, con la selección en negrita. */
function MatchLine({ h, teamName }: { h: HistorialItem; teamName: string }) {
  const esLocal = h.tipoEquipo === "home";
  const home = esLocal ? teamName : h.rival;
  const away = esLocal ? h.rival : teamName;
  const gHome = esLocal ? h.golesFavor : h.golesContra;
  const gAway = esLocal ? h.golesContra : h.golesFavor;
  const resClass =
    h.golesFavor == null || h.golesContra == null
      ? "bg-slate-100 text-slate-500"
      : h.golesFavor > h.golesContra
        ? "bg-emerald-50 text-emerald-700"
        : h.golesFavor < h.golesContra
          ? "bg-rose-50 text-rose-700"
          : "bg-slate-100 text-slate-500";
  const side = (t: string | null, isName: boolean) => (
    <span
      className={`flex items-center gap-1.5 ${
        isName ? "font-semibold text-slate-900" : "text-slate-600"
      }`}
    >
      {t && <span className="text-base leading-none">{flag(t)}</span>}
      {t ? teamES(t) : "—"}
    </span>
  );
  return (
    <span className="flex items-center gap-2">
      {side(home, home === teamName)}
      <span
        className={`rounded px-1.5 py-0.5 text-xs font-semibold tabular-nums ${resClass}`}
      >
        {gHome ?? "–"}–{gAway ?? "–"}
      </span>
      {side(away, away === teamName)}
    </span>
  );
}

/** Rejilla de métricas (label → valor) para una lista de columnas. */
function MetricGrid({
  h,
  cols,
}: {
  h: HistorialItem;
  cols: string[];
}) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
      {cols.map((col) => (
        <span key={col} className="flex justify-between gap-2">
          <span className="text-slate-500">{metricLabel(col)}</span>
          <span className="tabular-nums">{fmtMetric(h.metrics[col])}</span>
        </span>
      ))}
    </div>
  );
}

/** Tarjeta de partido del feed: resultado, expandible a las métricas de la
 * categoría seleccionada. */
function MatchHistoryCard({
  h,
  teamName,
}: {
  h: HistorialItem;
  teamName: string;
}) {
  const [open, setOpen] = useState(false);
  const [cat, setCat] = useState("resumen");
  const cats =
    cat === "todas"
      ? HIST_CATEGORIAS.filter((c) => c.cols)
      : HIST_CATEGORIAS.filter((c) => c.key === cat && c.cols);

  return (
    <div className="rounded-2xl bg-white ring-1 ring-slate-200">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <MatchLine h={h} teamName={teamName} />
        <span className="shrink-0 text-slate-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-4 py-3">
          {/* Selector de categoría del propio partido */}
          <div className="mb-3 flex flex-wrap gap-1.5">
            {HIST_CATEGORIAS.map((c) => (
              <button
                key={c.key}
                type="button"
                aria-pressed={c.key === cat}
                onClick={() => setCat(c.key)}
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition ${
                  c.key === cat
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          {cats.map((c) => {
            const cols = c.cols!.filter((col) => h.metrics[col] != null);
            if (cols.length === 0) return null;
            return (
              <div key={c.key} className="mb-3 last:mb-0">
                {cat === "todas" && (
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    {c.label}
                  </p>
                )}
                <MetricGrid h={h} cols={cols} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Historial de una selección con dos vistas: feed de tarjetas o tabla. */
export function HistorialSelecciones({
  historial,
  teamName,
}: {
  historial: HistorialItem[];
  teamName: string;
}) {
  const [vista, setVista] = useState<"tarjetas" | "tabla">("tarjetas");
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState("resumen");

  if (historial.length === 0) {
    return <p className="text-sm text-slate-500">Sin datos.</p>;
  }

  const q = norm(query);
  const filtrado = historial.filter(
    (h) =>
      q === "" || norm(`${teamES(h.rival ?? "")} ${h.rival ?? ""}`).includes(q),
  );

  const allCols = Object.keys(historial[0].metrics);
  const catDef = HIST_CATEGORIAS.find((c) => c.key === cat) ?? HIST_CATEGORIAS[0];
  const cols =
    catDef.cols == null ? allCols : catDef.cols.filter((c) => allCols.includes(c));

  return (
    <div>
      {/* Vista + búsqueda */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs">
          {(["tarjetas", "tabla"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={v === vista}
              onClick={() => setVista(v)}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                v === vista
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {v === "tarjetas" ? "Partidos" : "Tabla"}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por rival…"
          className="w-full max-w-xs rounded-full border border-slate-200 bg-white px-4 py-2 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />
      </div>

      {/* Categorías de columnas (solo en vista Tabla; en Tarjetas el selector
          va dentro de cada partido desplegado) */}
      {vista === "tabla" && (
        <div className="mb-3 flex flex-wrap gap-2">
          {HIST_CATEGORIAS.map((c) => (
            <button
              key={c.key}
              type="button"
              aria-pressed={c.key === cat}
              onClick={() => setCat(c.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                c.key === cat
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      )}

      {filtrado.length === 0 ? (
        <p className="text-sm text-slate-500">Sin resultados.</p>
      ) : vista === "tarjetas" ? (
        <div className="space-y-2">
          {filtrado.map((h, i) => (
            <MatchHistoryCard key={i} h={h} teamName={teamName} />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl bg-white ring-1 ring-slate-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
                <th className="whitespace-nowrap px-3 py-2 font-medium">
                  Partido
                </th>
                {cols.map((c) => (
                  <th
                    key={c}
                    className="whitespace-nowrap px-3 py-2 text-right font-medium"
                  >
                    {metricLabel(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtrado.map((h, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="whitespace-nowrap px-3 py-2">
                    <MatchLine h={h} teamName={teamName} />
                  </td>
                  {cols.map((c) => (
                    <td
                      key={c}
                      className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-slate-500"
                    >
                      {fmtMetric(h.metrics[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

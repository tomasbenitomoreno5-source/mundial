import { flag } from "@/lib/flags";
import { pct } from "@/lib/format";
import { teamES } from "@/lib/teams";

export type ScoreCell = { a: number; b: number; prob: number };

/** Heatmap de marcador exacto (filas = goles A, columnas = goles B). */
export function ScoreHeatmap({
  probs,
  teamA,
  teamB,
}: {
  probs: ScoreCell[];
  teamA: string;
  teamB: string;
}) {
  const N = 6; // 0..5
  const grid: number[][] = Array.from({ length: N }, () => Array(N).fill(0));
  let max = 0;
  const best = { a: 0, b: 0, p: 0 };
  for (const { a, b, prob } of probs) {
    if (a < N && b < N) {
      grid[a][b] = prob;
      if (prob > max) max = prob;
      if (prob > best.p) {
        best.a = a;
        best.b = b;
        best.p = prob;
      }
    }
  }

  return (
    <div className="overflow-x-auto rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <table className="border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr>
            <th />
            <th
              colSpan={N}
              className="pb-1 text-center text-[11px] font-medium text-slate-400"
            >
              {flag(teamB)} {teamES(teamB)} →
            </th>
          </tr>
          <tr>
            <th />
            {Array.from({ length: N }, (_, b) => (
              <th key={b} className="text-center text-[11px] text-slate-400">
                {b}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grid.map((row, a) => (
            <tr key={a}>
              <th className="pr-1 text-right text-[11px] font-normal text-slate-400">
                {a === 0 && (
                  <span className="mr-1">
                    {flag(teamA)} {teamES(teamA)} ↓
                  </span>
                )}
                {a}
              </th>
              {row.map((p, b) => {
                const intensity = max > 0 ? p / max : 0;
                const isBest = a === best.a && b === best.b;
                return (
                  <td
                    key={b}
                    className={`h-9 w-9 rounded text-center text-[10px] tabular-nums ${
                      isBest ? "ring-2 ring-indigo-500" : ""
                    }`}
                    style={{
                      backgroundColor: `rgba(79,70,229,${(0.05 + intensity * 0.6).toFixed(3)})`,
                      color: intensity > 0.5 ? "#fff" : "#475569",
                    }}
                  >
                    {p >= 0.02 ? Math.round(p * 100) : ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-400">
        Marcador más probable:{" "}
        <b>
          {teamES(teamA)} {best.a}–{best.b} {teamES(teamB)}
        </b>{" "}
        ({pct(best.p)}).
      </p>
    </div>
  );
}

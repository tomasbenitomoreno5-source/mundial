/**
 * Anillo de progreso con etiqueta central. Visual y claro para una cifra
 * principal (p. ej. "% de acierto"). Componente puro.
 */
export function Donut({
  value,
  label,
  sub,
  size = 132,
  color = "#4f46e5",
}: {
  value: number; // 0-1
  label: string;
  sub?: string;
  size?: number;
  color?: string;
}) {
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = Math.max(0, Math.min(1, value)) * c;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#eef2ff"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-black tabular-nums text-slate-900">
          {label}
        </span>
        {sub && <span className="text-[11px] font-medium text-slate-400">{sub}</span>}
      </div>
    </div>
  );
}

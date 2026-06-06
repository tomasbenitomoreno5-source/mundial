export type RadarAxis = { label: string; value: number }; // value 0-100

/** Radar de estilo en SVG (sin dependencias). Cada eje es un percentil 0-100. */
export function StyleRadar({
  data,
  size = 240,
}: {
  data: RadarAxis[];
  size?: number;
}) {
  const n = data.length;
  if (n < 3) return null;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 34; // hueco para etiquetas
  const ang = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2; // arriba
  const pt = (i: number, frac: number): [number, number] => [
    cx + Math.cos(ang(i)) * r * frac,
    cy + Math.sin(ang(i)) * r * frac,
  ];
  const poly = (frac: number) =>
    data.map((_, i) => pt(i, frac).join(",")).join(" ");
  const dataPoly = data
    .map((d, i) => pt(i, Math.max(0.03, d.value / 100)).join(","))
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto h-auto w-full max-w-[280px]"
      role="img"
      aria-label="Radar de estilo"
    >
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon
          key={f}
          points={poly(f)}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={1}
        />
      ))}
      {data.map((_, i) => {
        const [x, y] = pt(i, 1);
        return (
          <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#e2e8f0" strokeWidth={1} />
        );
      })}
      <polygon
        points={dataPoly}
        fill="rgba(79,70,229,0.18)"
        stroke="#4f46e5"
        strokeWidth={2}
      />
      {data.map((d, i) => {
        const [x, y] = pt(i, 1.16);
        return (
          <text
            key={d.label}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-slate-500 text-[10px] font-medium"
          >
            {d.label}
          </text>
        );
      })}
    </svg>
  );
}

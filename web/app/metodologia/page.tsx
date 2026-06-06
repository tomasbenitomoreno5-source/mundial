export const metadata = {
  title: "Metodología · Mundial.Predict",
  description:
    "Cómo funciona el modelo: estilo (KNN), fuerza ELO, pool de partidos, Dixon-Coles y simulación Monte Carlo.",
};

export default function MetodologiaPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-black tracking-tight">Metodología</h1>
      <p className="mt-3 text-lg text-slate-600">
        El predictor no opina: estima probabilidades a partir de datos reales y
        simulación. Aquí tienes el modelo, sin tecnicismos innecesarios.
      </p>

      <div className="mt-10 space-y-10">
        <Block
          n="1"
          title="Datos partido a partido"
          body="Partimos de las estadísticas reales de cada selección en su ciclo actual (goles, tiros, córners, posesión, faltas, tarjetas…) y de la telemetría de los jugadores destacados. Cada partido es una fila con decenas de métricas."
        />
        <Block
          n="2"
          title="Estilo de juego (KNN)"
          body="Para cada selección calculamos un “vector de estilo” basado en proporciones (precisión de pase, tiros a puerta, balones largos, duelos…), no en volúmenes. Reducimos la redundancia con PCA y buscamos las 8 selecciones de estilo más parecido. Así podemos razonar sobre cruces incluso con poca historia directa."
        />
        <Block
          n="3"
          title="Fuerza (ELO)"
          body="Combinamos una fuerza interna (goles a favor menos en contra, suavizada) con el rating ELO de cada selección. El ELO ancla el nivel absoluto y evita que un equipo parezca mejor solo por haber jugado contra rivales débiles."
        />
        <Block
          n="4"
          title="Pool de partidos comparables"
          body="Para predecir A vs B montamos un conjunto de partidos reales: los de A, los de A contra rivales del estilo de B, y los de equipos como A contra equipos como B. Cada partido pesa según su parecido de estilo y de diferencia de nivel con el cruce objetivo."
        />
        <Block
          n="5"
          title="Simulación Monte Carlo + Dixon-Coles"
          body="Remuestreamos ese pool 20.000 veces para simular el partido conservando las correlaciones entre métricas. Los goles se ajustan con el modelo Dixon-Coles, que corrige la dependencia entre los goles de ambos equipos y reparte bien empates y marcadores bajos."
        />
      </div>

      <div className="mt-12 rounded-2xl bg-amber-50 p-6 ring-1 ring-amber-200">
        <h2 className="font-semibold text-amber-900">Una nota de honestidad</h2>
        <p className="mt-2 text-sm leading-relaxed text-amber-800/90">
          Ningún modelo predice el fútbol con certeza: lo que ves son
          probabilidades, no pronósticos cerrados. El contenido es informativo y
          no constituye consejo de apuestas.
        </p>
      </div>
    </div>
  );
}

function Block({
  n,
  title,
  body,
}: {
  n: string;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-5">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white">
        {n}
      </span>
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <p className="mt-1.5 leading-relaxed text-slate-600">{body}</p>
      </div>
    </div>
  );
}

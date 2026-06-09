import Link from "next/link";

/** Logo/marca: monograma con balón estilizado + wordmark. */
export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-lg text-lg font-black ${
          light ? "bg-white/15 text-white" : "bg-indigo-600 text-white"
        }`}
      >
        26
      </span>
      <span
        className={`hidden text-base font-bold tracking-tight sm:inline ${
          light ? "text-white" : "text-slate-900"
        }`}
      >
        Mundial<span className="text-amber-500">.</span>Predict
      </span>
    </Link>
  );
}

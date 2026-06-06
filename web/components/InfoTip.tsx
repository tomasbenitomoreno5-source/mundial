/**
 * Tooltip "cómo se calcula": un icono ℹ️ que muestra un texto breve al pasar el
 * ratón o al enfocar con teclado. CSS-first (group-hover / focus-within), sin
 * estado, así que funciona tanto en Server como en Client Components.
 */
export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative ml-1 inline-flex align-middle">
      <button
        type="button"
        aria-label={text}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold lowercase text-slate-500 transition hover:bg-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-300"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-6 z-20 w-56 -translate-x-1/2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-normal normal-case tracking-normal text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}

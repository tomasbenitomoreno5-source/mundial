import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Brand } from "@/components/Brand";
import { Nav } from "@/components/Nav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Mundial.Predict — Predicciones del Mundial 2026",
  description:
    "Probabilidades de los 72 partidos del Mundial 2026 estimadas con un modelo estadístico (KNN de estilo, ELO, Dixon-Coles y simulación Monte Carlo).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full`}
    >
      <body className="flex min-h-full flex-col bg-[var(--background)] text-slate-900">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Brand />
            <Nav />
          </div>
        </header>
        <div className="flex-1">{children}</div>
        <footer className="mt-16 border-t border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <p>
              <span className="font-semibold text-slate-700">
                Mundial.Predict
              </span>{" "}
              · modelo probabilístico de los 72 partidos.
            </p>
            <p className="text-xs">
              Estimaciones por Monte Carlo. Contenido informativo, no es consejo
              de apuestas.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

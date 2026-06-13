// Bandera (emoji) por selección. Nombres en inglés tal y como vienen del dataset.
const FLAGS: Record<string, string> = {
  Spain: "🇪🇸",
  Argentina: "🇦🇷",
  France: "🇫🇷",
  England: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  Brazil: "🇧🇷",
  Portugal: "🇵🇹",
  Colombia: "🇨🇴",
  Netherlands: "🇳🇱",
  Ecuador: "🇪🇨",
  Croatia: "🇭🇷",
  Germany: "🇩🇪",
  Norway: "🇳🇴",
  Japan: "🇯🇵",
  Türkiye: "🇹🇷",
  Uruguay: "🇺🇾",
  Switzerland: "🇨🇭",
  Senegal: "🇸🇳",
  Belgium: "🇧🇪",
  Mexico: "🇲🇽",
  Paraguay: "🇵🇾",
  Austria: "🇦🇹",
  Morocco: "🇲🇦",
  Canada: "🇨🇦",
  Australia: "🇦🇺",
  Scotland: "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  Iran: "🇮🇷",
  "South Korea": "🇰🇷",
  Algeria: "🇩🇿",
  Panama: "🇵🇦",
  Uzbekistan: "🇺🇿",
  Czechia: "🇨🇿",
  USA: "🇺🇸",
  Sweden: "🇸🇪",
  Jordan: "🇯🇴",
  Egypt: "🇪🇬",
  "Côte d'Ivoire": "🇨🇮",
  "DR Congo": "🇨🇩",
  Tunisia: "🇹🇳",
  Iraq: "🇮🇶",
  "Bosnia & Herzegovina": "🇧🇦",
  "New Zealand": "🇳🇿",
  "Saudi Arabia": "🇸🇦",
  "Cabo Verde": "🇨🇻",
  Haiti: "🇭🇹",
  "South Africa": "🇿🇦",
  Ghana: "🇬🇭",
  Curaçao: "🇨🇼",
  Qatar: "🇶🇦",
};

export function flag(team: string): string {
  return FLAGS[team] ?? "🏳️";
}

/** Bandera emoji a partir de un código de país ISO alpha2 (p.ej. "nl" → 🇳🇱). */
export function flagCC(cc: string | null | undefined): string {
  if (!cc || cc.length !== 2) return "🏳️";
  const base = 0x1f1e6;
  const up = cc.toUpperCase();
  return String.fromCodePoint(
    base + (up.charCodeAt(0) - 65),
    base + (up.charCodeAt(1) - 65),
  );
}

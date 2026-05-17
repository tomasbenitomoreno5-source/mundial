import asyncio
import pandas as pd
import time
from datetime import datetime
from playwright.async_api import async_playwright

# --- 1. DICCIONARIO MAESTRO CON IDs ACTUALIZADOS ---
equipos_maestros = {
"Islandia": {"id": 4708, "fecha": "2025-09-01"},
"Bolivia": {"id": 4746, "fecha": "2025-09-01"}, 
"Camerún": {"id": 4751, "fecha": "2025-09-01"}, 
"Zimbabue": {"id": 4719, "fecha": "2025-09-01"}, 
"Angola": {"id": 4692, "fecha": "2025-09-01"}, 
"Zambia": {"id": 4720, "fecha": "2025-09-01"}, 
"Ruanda": {"id": 8037, "fecha": "2025-09-01"}, 
"Nigeria": {"id": 4785, "fecha": "2025-09-01"}, 
"Lesoto": {"id": 8033, "fecha": "2025-09-01"}, 
"Irlanda": {"id": 4693, "fecha": "2025-09-01"}, 
"Dinamarca": {"id": 4476, "fecha": "2025-09-01"}, 
"Gibraltar": {"id": 129264, "fecha": "2025-09-01"}, 
"San Marino": {"id": 4833, "fecha": "2025-09-01"}, 
"Islas Feroe": {"id": 4760, "fecha": "2025-09-01"}, 
"Montenegro": {"id": 7139, "fecha": "2025-09-01"}, 
"Guatemala": {"id": 5163, "fecha": "2025-09-01"}, 
"Venezuela": {"id": 4722, "fecha": "2025-09-01"}, 
"Gales": {"id": 4702, "fecha": "2025-09-01"}, 
"Rumania": {"id": 4477, "fecha": "2025-09-01"}, 
"Italia": {"id": 4707, "fecha": "2025-09-01"}, 
"Malta": {"id": 4483, "fecha": "2025-09-01"}, 
"Chipre": {"id": 4482, "fecha": "2025-09-01"}, 
"Siria": {"id": 4731, "fecha": "2025-09-01"}, 
"Palestina": {"id": 4788, "fecha": "2025-09-01"}, 
"EAU": {"id": 4727, "fecha": "2025-09-01"}, 
"Omán": {"id": 4787, "fecha": "2025-09-01"}, 
"Rusia": {"id": 4694, "fecha": "2025-09-01"}, 
"Bahréin": {"id": 5161, "fecha": "2025-09-01"}, 
"Kosovo": {"id": 154426, "fecha": "2025-09-01"}, 
"Eslovenia": {"id": 4484, "fecha": "2025-09-01"},
"Chile": {"id": 4754, "fecha": "2025-09-01"}, 
"Tanzania": {"id": 4835, "fecha": "2025-09-01"}, 
"Malí": {"id": 4831, "fecha": "2025-09-01"},
"Comoras": {"id": 23494, "fecha": "2025-09-01"},
"Uganda": {"id": 4726, "fecha": "2025-09-01"}, 
"Mozambique": {"id": 4783, "fecha": "2025-09-01"},
"República del Congo": {"id": 8040, "fecha": "2025-09-01"},
"Níger": {"id": 8031, "fecha": "2025-09-01"},
"Nicaragua": {"id": 21817, "fecha": "2025-09-01"},
"Costa Rica": {"id": 4756, "fecha": "2025-09-01"},
"Honduras": {"id": 4827, "fecha": "2025-09-01"},
"Grecia": {"id": 4710, "fecha": "2025-09-01"}, 
"Bielorrusia": {"id": 4743, "fecha": "2025-09-01"}, 
"Perú": {"id": 4790, "fecha": "2025-09-01"}, 
"Bulgaria": {"id": 4716, "fecha": "2025-09-01"},
"Georgia": {"id": 4763, "fecha": "2025-09-01"}, 
"Eslovaquia": {"id": 4697, "fecha": "2025-09-01"}, 
"Luxemburgo": {"id": 4478, "fecha": "2025-09-01"},
"Irlanda del Norte": {"id": 4786, "fecha": "2025-09-01"},
"China": {"id": 4755, "fecha": "2025-09-01"}, 
"Jamaica": {"id": 4769, "fecha": "2025-09-01"}, 
"Trinidad y Tobago": {"id": 5162, "fecha": "2025-09-01"}, 
"Islas Bermudas": {"id": 4745, "fecha": "2025-09-01"},
"Burkina Faso": {"id": 4749, "fecha": "2025-09-01"},
"Gabón": {"id": 4761, "fecha": "2025-09-01"}, 
"Kenia": {"id": 4773, "fecha": "2025-09-01"}, 
"Seychelles": {"id": 8038, "fecha": "2025-09-01"},
"Burundi": {"id": 4750, "fecha": "2025-09-01"},
"Lituania": {"id": 4776, "fecha": "2025-09-01"}, 
"Polonia": {"id": 4703, "fecha": "2025-09-01"}, 
"Finlandia": {"id": 4712, "fecha": "2025-09-01"}, 
"Ucrania": {"id": 4701, "fecha": "2025-09-01"},
"Botsuana": {"id": 298497, "fecha": "2025-09-01"},
"Mauritania": {"id": 4779, "fecha": "2025-09-01"},
"Namibia": {"id": 4832, "fecha": "2025-09-01"},
"Santo Tomé y Príncipe": {"id": 33813, "fecha": "2025-09-01"}, 
"Liechtenstein": {"id": 4830, "fecha": "2025-09-01"}, 
"Kazajistán": {"id": 4772, "fecha": "2025-09-01"},
"Macedonia del Norte": {"id": 4777, "fecha": "2025-09-01"},
"Benín": {"id": 4744, "fecha": "2025-09-01"}, 
"Kuwait": {"id": 4781, "fecha": "2025-09-01"},
"Guinea-Bisáu": {"id": 23478, "fecha": "2025-09-01"},
"Yibuti": {"id": 8042, "fecha": "2025-09-01"}, 
"Tayikistán": {"id": 4789, "fecha": "2025-09-01"},
"India": {"id": 4796, "fecha": "2025-09-01"},
"Afganistán": {"id": 6368, "fecha": "2025-09-01"},
"Serbia": {"id": 6355, "fecha": "2025-09-01"},
"Libia": {"id": 4775, "fecha": "2025-09-01"},
"Esuatini": {"id": 4733, "fecha": "2025-09-01"},
"Mauricio": {"id": 4780, "fecha": "2025-09-01"},
"Indonesia": {"id": 4794, "fecha": "2025-09-01"},
"República Dominicana": {"id": 21813, "fecha": "2025-09-01"},
"Azerbaiyán": {"id": 4683, "fecha": "2025-09-01"}, 
"Gambia": {"id": 4762, "fecha": "2025-09-01"}, 
"Sudán": {"id": 4734, "fecha": "2025-09-01"}, 
"Sudán del Sur": {"id": 88508, "fecha": "2025-09-01"},
"Tailandia": {"id": 4730, "fecha": "2025-09-01"},
"Hong Kong": {"id": 4765, "fecha": "2025-09-01"}, 
"Estonia": {"id": 4759, "fecha": "2025-09-01"},
"Israel": {"id": 4480, "fecha": "2025-09-01"}, 
"Moldavia": {"id": 4782, "fecha": "2025-09-01"},
"Puerto Rico": {"id": 21818, "fecha": "2025-09-01"}, 
"Guinea Ecuatorial": {"id": 8032, "fecha": "2025-09-01"},
"Somalia": {"id": 23472, "fecha": "2025-09-01"}, 
"Guinea": {"id": 4826, "fecha": "2025-09-01"}, 
"Albania": {"id": 4690, "fecha": "2025-09-01"},
"Armenia": {"id": 4717, "fecha": "2025-09-01"},
"Hungría": {"id": 4718, "fecha": "2025-09-01"}, 
"Togo": {"id": 4836, "fecha": "2025-09-01"}, 
"Kirguistán": {"id": 7930, "fecha": "2025-09-01"},
"Turkmenistán": {"id": 4728, "fecha": "2025-09-01"}, 
"Letonia": {"id": 4706, "fecha": "2025-09-01"}, 
"Andorra": {"id": 4818, "fecha": "2025-09-01"}, 
"Chad": {"id": 8039, "fecha": "2025-09-01"}, 
"República Centroafricana": {"id": 23470, "fecha": "2025-09-01"}, 
"El Salvador": {"id": 4825, "fecha": "2025-09-01"}, 
"Surinam": {"id": 21822, "fecha": "2025-09-01"},
"Chile": {"id": 4754, "fecha": "2018-11-01"}, 
"Dinamarca": {"id": 4476, "fecha": "2019-05-01"},
"China": {"id": 4755, "fecha": "2024-01-01"}, 
"Emiratos Árabes Unidos": {"id": 4727, "fecha": "2025-05-01"}, 
"Bolivia": {"id": 4746, "fecha": "2025-05-01"}, 
"Polonia": {"id": 4703, "fecha": "2025-10-01"}, 
"Eswatini": {"id": 4733, "fecha": "2020-01-01"},
"Guatemala": {"id": 5163, "fecha": "2020-01-01"},
"Argentina": {"id": 4819, "fecha": "2018-11-01"},
"Brasil": {"id": 4748, "fecha": "2025-05-01"}, 
"Uruguay": {"id": 4725, "fecha": "2023-05-01"},
"Colombia": {"id": 4820, "fecha": "2022-07-01"},
"Ecuador": {"id": 4757, "fecha": "2024-08-01"}, 
"Paraguay": {"id": 4789, "fecha": "2024-08-01"},
"Francia": {"id": 4481, "fecha": "2012-07-01"},
"Inglaterra": {"id": 4713, "fecha": "2025-01-01"},
"España": {"id": 4698, "fecha": "2022-12-01"},
"Alemania": {"id": 4711, "fecha": "2023-09-01"},
"Portugal": {"id": 4704, "fecha": "2023-01-01"},
"Países Bajos": {"id": 4705, "fecha": "2023-01-01"},
"Bélgica": {"id": 4717, "fecha": "2025-01-01"}, 
"Croacia": {"id": 4715, "fecha": "2017-10-01"}, 
"Suiza": {"id": 4699, "fecha": "2021-08-01"},
"Austria": {"id": 4718, "fecha": "2022-05-01"},
"Escocia": {"id": 4712, "fecha": "2019-05-01"}, 
"Suecia": {"id": 4723, "fecha": "2025-10-01"},
"Noruega": {"id": 4722, "fecha": "2020-12-01"}, 
"Türkiye": {"id": 4700, "fecha": "2023-09-01"}, 
"Chequia": {"id": 4714, "fecha": "2025-12-01"}, 
"Bosnia y Herzegovina": {"id": 4479, "fecha": "2024-04-01"},
"Estados Unidos": {"id": 4724, "fecha": "2024-09-01"}, 
"México": {"id": 4781, "fecha": "2024-07-01"}, 
"Canadá": {"id": 4752, "fecha": "2024-01-01"}, 
"Panamá": {"id": 5164, "fecha": "2020-07-01"}, 
"Haití": {"id": 7229, "fecha": "2024-06-01"}, 
"Curaçao": {"id": 11520, "fecha": "2026-05-01"},
"Marruecos": {"id": 4778, "fecha": "2022-08-01"},
"Senegal": {"id": 4739, "fecha": "2024-12-01"},
"Egipto": {"id": 4758, "fecha": "2024-02-01"},
"Argelia": {"id": 4691, "fecha": "2024-02-01"},
"Costa de Marfil": {"id": 4774, "fecha": "2024-01-01"},
"Túnez": {"id": 4780, "fecha": "2025-02-01"},
"Sudáfrica": {"id": 4736, "fecha": "2021-05-01"},
"Ghana": {"id": 4764, "fecha": "2026-05-01"},
"RD Congo": {"id": 4823, "fecha": "2022-08-01"},
"Cabo Verde": {"id": 4753, "fecha": "2020-01-01"},
"Japón": {"id": 4770, "fecha": "2018-07-01"}, 
"RI Irán": {"id": 4766, "fecha": "2023-03-01"},
"Corea del Sur": {"id": 4735, "fecha": "2024-07-01"},
"Australia": {"id": 4741, "fecha": "2024-09-01"},
"Arabia Saudita": {"id": 4834, "fecha": "2026-04-01"},
"Qatar": {"id": 4792, "fecha": "2025-05-01"},
"Irak": {"id": 4767, "fecha": "2025-05-01"},
"Uzbekistán": {"id": 4723, "fecha": "2025-10-01"},
"Jordania": {"id": 4771, "fecha": "2024-08-01"},
"Nueva Zelanda": {"id": 4784, "fecha": "2022-11-01"}
}

jugadores_objetivo = ["Erling Haaland", "Harry Kane", "Kylian Mbappé", "Viktor Gyökeres", "Cristiano Ronaldo", "Lionel Messi", "James Rodríguez", "Raphinha", "Enner Valencia", "Miguel Terceros", "Mohamed Amoura", "Mohamed Salah", "Dailon Livramento", "Cédric Bakambu", "Sadio Mané", "Almoez Ali", "Akram Afif", "Son Heung-min", "Mehdi Taremi", "Aymen Hussein", "Ali Olwan", "Duckens Nazon", "Óscar Santis", "Chris Wood", "Florian Wirtz", "Darwin Núñez", "Vinicius Júnior", "Youssef En-Nesyri", "Jordan Ayew", "Ayase Ueda", "Eldor Shomurodov", "Zeki Amdouni", "Lamine Yamal", "Robert Andrich", "Joshua Kimmich", "Declan Rice", "Sander Berge", "Rodrigo De Paul", "Manuel Ugarte", "Federico Valverde", "Bruno Guimarães", "Sofyan Amrabat", "Achraf Hakimi", "Mohammed Kudus", "Thomas Partey", "Wataru Endo", "Rebin Sulaka", "Otabek Shukurov", "Granit Xhaka", "Aurélien Tchouaméni", "Rodri", "João Palhinha", "Ørjan Nyland", "Emiliano Martínez", "Alisson", "Jalal Hassan", "Utkir Yusupov", "Gregor Kobel", "Mike Maignan", "Diogo Costa"]

# --- 2. PIPELINE DE EXTRACCIÓN ---

async def fetch_json(page, url):
    try:
        response = await page.goto(url, wait_until="networkidle")
        if response.status == 200:
            return await response.json()
        return None
    except Exception:
        return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        telemetria_total = []
        stats_globales_total = []

        for equipo, meta in equipos_maestros.items():
            if meta["id"] is None: continue
            
            print(f"Buscando histórico de: {equipo}...")
            # FASE 1: Filtro Histórico
            url_events = f"https://api.sofascore.com/api/v1/team/{meta['id']}/events/last/0"
            data_events = await fetch_json(page, url_events)
            
            if not data_events or "events" not in data_events: continue
            
            fecha_manager = datetime.strptime(meta["fecha"], "%Y-%m-%d").timestamp()
            partidos_ids = [ev["id"] for ev in data_events["events"] if ev["startTimestamp"] >= fecha_manager]

            for id_partido in partidos_ids:
                time.sleep(3) # Delay prudencial
                
                # FASE 2: Telemetría de Jugadores
                url_lineups = f"https://api.sofascore.com/api/v1/event/{id_partido}/lineups"
                data_lineups = await fetch_json(page, url_lineups)
                
                if data_lineups:
                    for side in ["home", "away"]:
                        for p_entry in data_lineups.get(side, {}).get("players", []):
                            if p_entry["player"]["name"] in jugadores_objetivo:
                                p_stats = p_entry.get("statistics", {})
                                p_stats.update({
                                    "jugador": p_entry["player"]["name"],
                                    "partido_id": id_partido,
                                    "equipo": equipo
                                })
                                telemetria_total.append(p_stats)

                # FASE 3: Estadísticas Globales
                url_stats = f"https://api.sofascore.com/api/v1/event/{id_partido}/statistics"
                data_stats = await fetch_json(page, url_stats)
                
                if data_stats and "statistics" in data_stats:
                    for period in data_stats["statistics"]:
                        if period["period"] == "ALL":
                            for group in period["groups"]:
                                for item in group["statisticsItems"]:
                                    stats_globales_total.append({
                                        "partido_id": id_partido,
                                        "metrica": item["name"],
                                        "home_val": item["home"],
                                        "away_val": item["away"]
                                    })

        # --- 3. CONSOLIDACIÓN Y EXPORTACIÓN ---
        
        df_telemetria = pd.DataFrame(telemetria_total)
        df_global = pd.DataFrame(stats_globales_total)

        df_telemetria.to_csv("telemetria_pro_2026.csv", index=False)
        df_global.to_csv("stats_globales_2026.csv", index=False)
        
        print("Pipeline finalizado. Archivos generados.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
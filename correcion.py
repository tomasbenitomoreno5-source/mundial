import asyncio
import pandas as pd
from playwright.async_api import async_playwright

async def get_match_info(page, partido_id):
    url = f"https://api.sofascore.com/api/v1/event/{partido_id}"
    try:
        response = await page.goto(url)
        if response.status == 200:
            data = await response.json()
            event = data.get("event", {})
            return {
                "partido_id": partido_id,
                "home_team": event.get("homeTeam", {}).get("name"),
                "away_team": event.get("awayTeam", {}).get("name")
            }
    except Exception:
        pass
    return {"partido_id": partido_id, "home_team": "Unknown", "away_team": "Unknown"}

async def main():
    # 1. Cargar IDs únicos de tus archivos actuales
    df_stats = pd.read_csv("stats_globales_2026.csv")
    ids_unicos = df_stats["partido_id"].unique()
    
    print(f"Total de partidos a mapear: {len(ids_unicos)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        resultados = []
        for i, pid in enumerate(ids_unicos):
            print(f"[{i+1}/{len(ids_unicos)}] Mapeando ID: {pid}")
            info = await get_match_info(page, pid)
            resultados.append(info)
            # Un delay mínimo solo para no saturar, pero mucho más rápido que antes
            await asyncio.sleep(0.5) 
        
        df_map = pd.DataFrame(resultados)
        df_map.to_csv("mapeo_equipos.csv", index=False)
        print("Mapeo finalizado. Archivo 'mapeo_equipos.csv' creado.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
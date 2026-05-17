import asyncio
import pandas as pd
from playwright.async_api import async_playwright

async def obtener_info_partido(page, partido_id):
    url = f"https://api.sofascore.com/api/v1/event/{partido_id}"
    try:
        await page.goto(url, wait_until="domcontentloaded")
        data = await page.evaluate("() => JSON.parse(document.querySelector('pre').innerText)")
        
        event = data.get("event", {})
        
        return {
            "partido_id": partido_id,
            "home_team": event.get("homeTeam", {}).get("name", "Unknown"),
            "away_team": event.get("awayTeam", {}).get("name", "Unknown"),
            # Añadimos los goles del partido
            "home_score": event.get("homeScore", {}).get("current", 0),
            "away_score": event.get("awayScore", {}).get("current", 0)
        }
    except Exception:
        return {
            "partido_id": partido_id, "home_team": "Error", "away_team": "Error",
            "home_score": 0, "away_score": 0
        }

async def main():
    # Leemos tu archivo actual para sacar los IDs de los partidos
    df_existente = pd.read_csv("mapeo_equipos.csv")
    ids_a_buscar = df_existente["partido_id"].unique()

    print(f"Buscando nombres y GOLES de {len(ids_a_buscar)} partidos...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        resultados = []
        for pid in ids_a_buscar:
            info = await obtener_info_partido(page, pid)
            resultados.append(info)
            await asyncio.sleep(0.3) # Delay de seguridad
            
        df_mapeo = pd.DataFrame(resultados)
        df_mapeo.to_csv("mapeo_con_goles.csv", index=False)
        print("¡Listo! Archivo 'mapeo_con_goles.csv' generado.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
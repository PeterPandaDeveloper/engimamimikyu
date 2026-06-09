import aiohttp
import random

async def obtener_datos_completos_pokemon(id_pokemon):
    url_base = f"https://pokeapi.co/api/v2/pokemon/{id_pokemon}"
    url_species = f"https://pokeapi.co/api/v2/pokemon-species/{id_pokemon}"
    
    async with aiohttp.ClientSession() as session:
        # Petición 1: Datos de combate y tipos
        async with session.get(url_base) as resp1:
            data = await resp1.json()
            nombre = data['name'].capitalize()
            sprite = data['sprites']['front_default']
            tipos = [t['type']['name'].capitalize() for t in data['types']]
            habilidades = [h['ability']['name'].capitalize() for h in data['abilities']]
            
            # Calcular estadística mayor y menor
            stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
            stat_mayor = max(stats, key=stats.get)
            stat_menor = min(stats, key=stats.get)

        # Petición 2: Datos de especie (Hábitat, Huevos, Evolución)
        async with session.get(url_species) as resp2:
            species_data = await resp2.json()
            habitat = species_data['habitat']['name'].capitalize() if species_data['habitat'] else "Desconocido"
            grupos_huevo = [g['name'].capitalize() for g in species_data['egg_groups']]
            es_bebe = species_data['is_baby']
            es_legendario = species_data['is_legendary'] or species_data['is_mythical']
            gen = species_data['generation']['name'].upper()

        return {
            "nombre": nombre, "sprite": sprite, "tipos": tipos, "habilidades": habilidades,
            "stat_mayor": stat_mayor, "stat_menor": stat_menor, "habitat": habitat,
            "grupos_huevo": grupos_huevo, "es_legendario": es_legendario, "gen": gen
        }
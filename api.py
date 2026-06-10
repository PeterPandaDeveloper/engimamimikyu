import aiohttp
import random

# Sesión compartida a nivel de módulo — se inicializa una vez y se reutiliza
_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session

async def cerrar_session():
    global _session
    if _session and not _session.closed:
        await _session.close()

async def obtener_datos_completos_pokemon(id_pokemon: int, intentos: int = 3) -> dict | None:
    """
    Obtiene datos de un Pokémon desde PokéAPI.
    Reintenta hasta `intentos` veces con IDs aleatorios si falla.
    Devuelve None si agota todos los intentos.
    """
    session = await get_session()

    for intento in range(intentos):
        try:
            url_base    = f"https://pokeapi.co/api/v2/pokemon/{id_pokemon}"
            url_species = f"https://pokeapi.co/api/v2/pokemon-species/{id_pokemon}"

            async with session.get(url_base, timeout=aiohttp.ClientTimeout(total=10)) as resp1:
                if resp1.status != 200:
                    raise ValueError(f"pokemon/{id_pokemon} devolvió HTTP {resp1.status}")
                data = await resp1.json()

            async with session.get(url_species, timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                if resp2.status != 200:
                    raise ValueError(f"pokemon-species/{id_pokemon} devolvió HTTP {resp2.status}")
                species_data = await resp2.json()

            nombre     = data['name'].capitalize()
            sprite     = data['sprites']['front_default']
            tipos      = [t['type']['name'].capitalize() for t in data['types']]
            habilidades = [h['ability']['name'].capitalize() for h in data['abilities']]

            stats      = {s['stat']['name']: s['base_stat'] for s in data['stats']}
            stat_mayor = max(stats, key=stats.get)
            stat_menor = min(stats, key=stats.get)

            habitat      = species_data['habitat']['name'].capitalize() if species_data['habitat'] else "Desconocido"
            grupos_huevo = [g['name'].capitalize() for g in species_data['egg_groups']]
            es_legendario = species_data['is_legendary'] or species_data['is_mythical']
            gen          = species_data['generation']['name'].upper()

            return {
                "nombre": nombre, "sprite": sprite, "tipos": tipos, "habilidades": habilidades,
                "stat_mayor": stat_mayor, "stat_menor": stat_menor, "habitat": habitat,
                "grupos_huevo": grupos_huevo, "es_legendario": es_legendario, "gen": gen
            }

        except Exception as e:
            print(f"⚠️ [API] Intento {intento + 1}/{intentos} fallido para ID {id_pokemon}: {e}")
            # Fallback: elegir otro ID aleatorio para el siguiente intento
            id_pokemon = random.randint(1, 1025)

    print("❌ [API] Se agotaron los intentos. No se pudo obtener un Pokémon.")
    return None

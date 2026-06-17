"""
api.py — Wrapper de PokéAPI con sesión compartida, reintentos y soporte
de idioma (EN/ES) para especie, entrada de Pokédex y habitat.
"""
import aiohttp
import random

# Sesión compartida — se inicializa una vez y se reutiliza
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


def _get_localizado(lista: list[dict], campo: str, lang: str, fallback_lang: str = "en") -> str:
    """
    Extrae un texto localizado de una lista de entradas con formato
    [{"language": {"name": "en"}, campo: "..."}].
    Intenta `lang` primero y cae a `fallback_lang` si no existe.
    """
    preferido = ""
    fallback  = ""
    for entry in lista:
        entry_lang = entry.get("language", {}).get("name", "")
        valor      = entry.get(campo, "").replace("\n", " ").replace("\x0c", " ").strip()
        if entry_lang == lang and not preferido:
            preferido = valor
        if entry_lang == fallback_lang and not fallback:
            fallback = valor
    return preferido or fallback


async def obtener_datos_completos_pokemon(
    id_pokemon: int,
    intentos: int = 3,
    lang: str = "en",
) -> dict | None:
    """
    Obtiene datos de un Pokémon desde PokéAPI.
    - lang: idioma preferido para especie, Pokédex entry y habitat ("en" | "es")
    - Reintenta hasta `intentos` veces con IDs aleatorios si falla.
    - Devuelve None si agota todos los intentos.
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

            # ── Datos básicos (siempre en inglés desde la API) ────────────────
            nombre      = data["name"].capitalize()
            sprite      = data["sprites"]["front_default"]
            tipos       = [t["type"]["name"].capitalize() for t in data["types"]]
            habilidades = [h["ability"]["name"].replace("-", " ").capitalize() for h in data["abilities"]]

            stats      = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
            stat_mayor = max(stats, key=stats.get)
            stat_menor = min(stats, key=stats.get)

            gen = species_data["generation"]["name"].upper()
            es_legendario = species_data["is_legendary"] or species_data["is_mythical"]

            # ── Habitat localizado ────────────────────────────────────────────
            habitat_raw = species_data.get("habitat")
            if habitat_raw:
                habitat_name = habitat_raw.get("name", "")
                # La PokéAPI no ofrece nombres de habitat en español directamente,
                # así que usamos una tabla de traducción propia.
                _HABITAT_ES = {
                    "cave": "Cueva", "forest": "Bosque", "grassland": "Praderas",
                    "mountain": "Montaña", "rare": "Raro", "rough-terrain": "Terreno Escarpado",
                    "sea": "Mar", "urban": "Urbano", "waters-edge": "Orilla del Agua",
                }
                if lang == "es":
                    habitat = _HABITAT_ES.get(habitat_name, habitat_name.replace("-", " ").capitalize())
                else:
                    habitat = habitat_name.replace("-", " ").capitalize()
            else:
                habitat = "Unknown" if lang == "en" else "Desconocido"

            # ── Grupos huevo (sin localización oficial en la API) ─────────────
            grupos_huevo = [g["name"].replace("-", " ").capitalize()
                            for g in species_data.get("egg_groups", [])]

            # ── Especie localizada (ej. "Mouse Pokémon" / "Pokémon Ratón") ────
            especie = _get_localizado(
                species_data.get("genera", []), "genus", lang=lang, fallback_lang="en"
            )

            # ── Entrada de Pokédex localizada ─────────────────────────────────
            pokedex_entry = _get_localizado(
                species_data.get("flavor_text_entries", []),
                "flavor_text", lang=lang, fallback_lang="en"
            )

            return {
                "nombre": nombre, "sprite": sprite, "tipos": tipos,
                "habilidades": habilidades, "stat_mayor": stat_mayor,
                "stat_menor": stat_menor, "stats": stats,
                "habitat": habitat, "grupos_huevo": grupos_huevo,
                "es_legendario": es_legendario, "gen": gen,
                "especie": especie, "pokedex_entry": pokedex_entry,
            }

        except Exception as e:
            print(f"⚠️ [API] Intento {intento + 1}/{intentos} fallido para ID {id_pokemon}: {e}")
            id_pokemon = random.randint(1, 1025)

    print("❌ [API] Se agotaron los intentos. No se pudo obtener un Pokémon.")
    return None
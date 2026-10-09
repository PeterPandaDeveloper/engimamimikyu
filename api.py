"""
api.py — Wrapper de PokéAPI con sesión compartida, reintentos, caché en memoria/disco
y soporte de idioma (EN/ES) para especie, entrada de Pokédex y habitat.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import threading
import aiohttp

# Sesión compartida — se inicializa una vez y se reutiliza
_session: aiohttp.ClientSession | None = None

# Caché en memoria: { (id_pokemon, lang): datos_dict }
_CACHE_POKEMON: dict[tuple[int, str], dict] = {}
_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pokemon_cache.json")
_CACHE_LOCK = threading.Lock()


def _cargar_cache_disco():
    global _CACHE_POKEMON
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                # Formato de clave: "id:lang" -> (int(id), lang)
                partes = k.split(":")
                if len(partes) == 2:
                    _CACHE_POKEMON[(int(partes[0]), partes[1])] = v
        except Exception as e:
            print(f"[Caché] Error al cargar caché de disco: {e}")


def _guardar_en_cache_disco(id_pokemon: int, lang: str, datos: dict):
    with _CACHE_LOCK:
        try:
            cache_dir = os.path.dirname(_CACHE_FILE)
            os.makedirs(cache_dir, exist_ok=True)
            raw = {}
            if os.path.exists(_CACHE_FILE):
                try:
                    with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                except Exception:
                    raw = {}
            raw[f"{id_pokemon}:{lang}"] = datos
            tmp_file = f"{_CACHE_FILE}.tmp.{os.getpid()}"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)
            os.replace(tmp_file, _CACHE_FILE)
        except Exception as e:
            print(f"[Caché] Error al guardar en caché: {e}")


# Inicializar caché en arranque
_cargar_cache_disco()


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def cerrar_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        await asyncio.sleep(0.25)
        _session = None


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
    Obtiene datos de un Pokémon desde la caché local o PokéAPI.
    - Si ya está en caché: respuesta instantánea (0 ms).
    - Si se descarga: realiza llamadas paralelas a base y species con timeout ajustado.
    - Guarda en caché en memoria y disco automáticamente.
    """
    cache_key = (id_pokemon, lang)
    if cache_key in _CACHE_POKEMON:
        return _CACHE_POKEMON[cache_key]

    session = await get_session()

    for intento in range(intentos):
        try:
            url_base    = f"https://pokeapi.co/api/v2/pokemon/{id_pokemon}"
            url_species = f"https://pokeapi.co/api/v2/pokemon-species/{id_pokemon}"

            # Peticiones paralelas ultrarrápidas
            async def _fetch(url: str) -> dict:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
                    if resp.status != 200:
                        raise ValueError(f"{url} HTTP {resp.status}")
                    return await resp.json()

            data, species_data = await asyncio.gather(_fetch(url_base), _fetch(url_species))

            # ── Datos básicos (siempre en inglés desde la API) ────────────────
            nombre = data["name"].capitalize()
            sprites_data = data.get("sprites", {})
            sprite = (
                sprites_data.get("front_default")
                or sprites_data.get("other", {}).get("official-artwork", {}).get("front_default")
                or sprites_data.get("other", {}).get("home", {}).get("front_default")
                or None
            )
            tipos = [t["type"]["name"].capitalize() for t in data.get("types", [])]
            habilidades = [h["ability"]["name"].replace("-", " ").capitalize() for h in data.get("abilities", [])]

            stats      = {s["stat"]["name"]: s["base_stat"] for s in data.get("stats", [])}
            stat_mayor = max(stats, key=stats.get) if stats else "None"
            stat_menor = min(stats, key=stats.get) if stats else "None"

            gen = species_data["generation"]["name"].upper()
            es_legendario = species_data.get("is_legendary", False) or species_data.get("is_mythical", False)

            # ── Habitat localizado ────────────────────────────────────────────
            habitat_raw = species_data.get("habitat")
            if habitat_raw:
                habitat_name = habitat_raw.get("name", "")
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

            # ── Grupos huevo ──────────────────────────────────────────────────
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

            res = {
                "id": id_pokemon,
                "nombre": nombre, "sprite": sprite, "tipos": tipos,
                "habilidades": habilidades, "stat_mayor": stat_mayor,
                "stat_menor": stat_menor, "stats": stats,
                "habitat": habitat, "grupos_huevo": grupos_huevo,
                "es_legendario": es_legendario, "gen": gen,
                "especie": especie, "pokedex_entry": pokedex_entry,
            }

            # Guardar en memoria y disco
            _CACHE_POKEMON[cache_key] = res
            asyncio.create_task(asyncio.to_thread(_guardar_en_cache_disco, id_pokemon, lang, res))

            return res

        except Exception as e:
            print(f"[API] Intento {intento + 1}/{intentos} fallido para ID {id_pokemon}: {e}")
            id_pokemon = random.randint(1, 151)  # Fallback a Kanto más confiable y rápido

    print("[API] Se agotaron los intentos. No se pudo obtener un Pokemon.")
    return None
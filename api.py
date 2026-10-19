"""
api.py — Wrapper de PokéAPI con sesión compartida, reintentos, caché en memoria/disco,
soporte de idioma (EN/ES) para especie, entrada de Pokédex, hábitat, color
y soporte completo para Mega Evoluciones, Regionales, Gigantamax y Formas Gimmick (IDs 10001+).
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

_COLORES_ES = {
    "black": "Negro",
    "blue": "Azul",
    "brown": "Marrón",
    "gray": "Gris",
    "green": "Verde",
    "pink": "Rosa",
    "purple": "Morado",
    "red": "Rojo",
    "white": "Blanco",
    "yellow": "Amarillo",
}

_HABITAT_ES = {
    "cave": "Cueva",
    "forest": "Bosque",
    "grassland": "Praderas",
    "mountain": "Montaña",
    "rare": "Raro",
    "rough-terrain": "Terreno Escarpado",
    "sea": "Mar",
    "urban": "Urbano",
    "waters-edge": "Orilla del Agua",
}

_GEN_DISPLAY = {
    "generation-i":    ("Kanto (Gen 1)",   "Kanto (Gen 1)"),
    "generation-ii":   ("Johto (Gen 2)",   "Johto (Gen 2)"),
    "generation-iii":  ("Hoenn (Gen 3)",   "Hoenn (Gen 3)"),
    "generation-iv":   ("Sinnoh (Gen 4)",  "Sinnoh (Gen 4)"),
    "generation-v":    ("Teselia (Gen 5)", "Unova (Gen 5)"),
    "generation-vi":   ("Kalos (Gen 6)",   "Kalos (Gen 6)"),
    "generation-vii":  ("Alola (Gen 7)",   "Alola (Gen 7)"),
    "generation-viii": ("Galar (Gen 8)",   "Galar (Gen 8)"),
    "generation-ix":   ("Paldea (Gen 9)",  "Paldea (Gen 9)"),
}


def _formatear_nombre_pokemon(raw_name: str, lang: str = "en") -> str:
    """
    Convierte slugs de PokéAPI (ej. 'charizard-mega-x', 'ninetales-alola', 'gengar-gmax')
    en nombres legibles e intuitivos según el idioma del servidor.
    """
    low = raw_name.lower()
    partes = low.split("-")
    base = partes[0].capitalize()

    if len(partes) == 1:
        return base

    # Mega Evoluciones y Primigenios
    if "mega" in partes:
        sufijo = " X" if partes[-1] == "x" else (" Y" if partes[-1] == "y" else "")
        return f"Mega {base}{sufijo}"
    if "primal" in partes:
        return f"{base} Primigenio" if lang == "es" else f"Primal {base}"

    # Gigantamax / Eternamax
    if "gmax" in partes:
        return f"{base} Gigantamax" if lang == "es" else f"Gigantamax {base}"
    if "eternamax" in partes:
        return f"Eternamax {base}"

    # Formas Regionales
    regionales = {
        "alola":  ("de Alola",  "Alolan"),
        "galar":  ("de Galar",  "Galarian"),
        "hisui":  ("de Hisui",  "Hisuian"),
        "paldea": ("de Paldea", "Paldean"),
    }
    for reg_key, (es_txt, en_txt) in regionales.items():
        if reg_key in partes:
            extra = [p.capitalize() for p in partes[1:] if p != reg_key]
            extra_str = f" ({' '.join(extra)})" if extra else ""
            if lang == "es":
                return f"{base} {es_txt}{extra_str}"
            return f"{en_txt} {base}{extra_str}"

    # Excepciones con guion en su nombre oficial
    nombres_con_guion = {
        "ho-oh", "porygon-z", "jangmo-o", "hakamo-o", "kommo-o",
        "ting-lu", "chien-pao", "wo-chien", "chi-yu", "type-null",
    }
    if low in nombres_con_guion:
        return "-".join(p.capitalize() for p in partes)

    # Otras formas Gimmick (Rotom, Deoxys, Urshifu, Ogerpon, etc.)
    forma_txt = " ".join(p.capitalize() for p in partes[1:])
    return f"{base} ({forma_txt})"


def _cargar_cache_disco():
    global _CACHE_POKEMON
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
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
    Obtiene datos de un Pokémon (1..1025 o formas Gimmick/Mega 10001+) desde caché o PokéAPI.
    Incluye el color localizado para enriquecer la pista de letra inicial.
    """
    session = await get_session()
    current_id = id_pokemon

    for intento in range(intentos):
        cache_key = (current_id, lang)
        if cache_key in _CACHE_POKEMON:
            cached = _CACHE_POKEMON[cache_key]
            # Si viene de una caché vieja que aún no tenía 'color', le asignamos un fallback seguro
            if "color" not in cached:
                cached["color"] = "Desconocido" if lang == "es" else "Unknown"
            return cached

        try:
            async def _fetch(url: str) -> dict:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=4.0)) as resp:
                    if resp.status != 200:
                        raise ValueError(f"{url} HTTP {resp.status}")
                    return await resp.json()

            url_base = f"https://pokeapi.co/api/v2/pokemon/{current_id}"

            if current_id <= 1025:
                # Pokémon estándar: petición paralela directa
                url_species = f"https://pokeapi.co/api/v2/pokemon-species/{current_id}"
                data, species_data = await asyncio.gather(_fetch(url_base), _fetch(url_species))
            else:
                # Forma Gimmick / Mega / Regional / Gmax (ID >= 10001):
                # Primero obtenemos /pokemon/{id} y extraemos la URL real de su especie base
                data = await _fetch(url_base)
                species_url = data.get("species", {}).get("url")
                if not species_url:
                    raise ValueError(f"Sin species URL para forma {current_id}")
                species_data = await _fetch(species_url)

            raw_name = data["name"]
            base_species_name = species_data.get("name", raw_name).capitalize()
            nombre = _formatear_nombre_pokemon(raw_name, lang=lang)

            sprites_data = data.get("sprites", {})
            sprite = (
                sprites_data.get("other", {}).get("official-artwork", {}).get("front_default")
                or sprites_data.get("other", {}).get("home", {}).get("front_default")
                or sprites_data.get("front_default")
                or None
            )
            tipos = [t["type"]["name"].capitalize() for t in data.get("types", [])]
            habilidades = [h["ability"]["name"].replace("-", " ").capitalize() for h in data.get("abilities", [])]

            stats      = {s["stat"]["name"]: s["base_stat"] for s in data.get("stats", [])}
            stat_mayor = max(stats, key=stats.get) if stats else "None"
            stat_menor = min(stats, key=stats.get) if stats else "None"

            gen_raw = species_data.get("generation", {}).get("name", "").lower()
            if gen_raw in _GEN_DISPLAY:
                gen = _GEN_DISPLAY[gen_raw][0] if lang == "es" else _GEN_DISPLAY[gen_raw][1]
            else:
                gen = gen_raw.upper() or "?"

            es_legendario = species_data.get("is_legendary", False) or species_data.get("is_mythical", False)

            # ── Color localizado (Feedback de Candela) ────────────────────────
            color_raw = (species_data.get("color") or {}).get("name", "").lower()
            if color_raw:
                if lang == "es":
                    color = _COLORES_ES.get(color_raw, color_raw.capitalize())
                else:
                    color = color_raw.capitalize()
            else:
                color = "Desconocido" if lang == "es" else "Unknown"

            # ── Hábitat localizado ────────────────────────────────────────────
            habitat_raw = species_data.get("habitat")
            if habitat_raw:
                habitat_name = habitat_raw.get("name", "")
                if lang == "es":
                    habitat = _HABITAT_ES.get(habitat_name, habitat_name.replace("-", " ").capitalize())
                else:
                    habitat = habitat_name.replace("-", " ").capitalize()
            else:
                habitat = "Unknown" if lang == "en" else "Desconocido"

            grupos_huevo = [g["name"].replace("-", " ").capitalize()
                            for g in species_data.get("egg_groups", [])]

            especie = _get_localizado(
                species_data.get("genera", []), "genus", lang=lang, fallback_lang="en"
            )
            pokedex_entry = _get_localizado(
                species_data.get("flavor_text_entries", []),
                "flavor_text", lang=lang, fallback_lang="en"
            )

            res = {
                "id": current_id,
                "nombre": nombre,
                "nombre_base": base_species_name,
                "sprite": sprite,
                "tipos": tipos,
                "habilidades": habilidades,
                "stat_mayor": stat_mayor,
                "stat_menor": stat_menor,
                "stats": stats,
                "color": color,
                "habitat": habitat,
                "grupos_huevo": grupos_huevo,
                "es_legendario": es_legendario,
                "gen": gen,
                "especie": especie,
                "pokedex_entry": pokedex_entry,
            }

            _CACHE_POKEMON[cache_key] = res
            asyncio.create_task(asyncio.to_thread(_guardar_en_cache_disco, current_id, lang, res))
            return res

        except Exception as e:
            print(f"[API] Intento {intento + 1}/{intentos} fallido para ID {current_id}: {e}")
            current_id = random.randint(1, 151)

    print("[API] Se agotaron los intentos. No se pudo obtener un Pokemon.")
    return None
"""
pistas.py — Generación y formateo de pistas para impostores y detectives en PokeImpostor.
Incluye el bonus de característica visual (Color) en pistas de Letra Inicial y Región.
"""
from __future__ import annotations

import random
import re
from enum import Enum

from i18n import t, get_lang
from tipos_pokemon import debilidades_x4, debilidades_x2


class Ventaja(str, Enum):
    ALEATORIO       = "aleatorio"
    LETRA           = "letra"
    TIPO            = "tipo"
    RANGO_REGION    = "rango_region"
    HABILIDAD       = "habilidad"
    PALABRA_AMBIGUA = "palabra_ambigua"  # Pista de una sola palabra ambigua y temática
    PERFIL          = "perfil"          # especie + hábitat + grupo huevo (3 datos)
    DEBILIDADES     = "debilidades"     # x4 si existe, sino x2, sino "sin debilidades"
    POKEDEX         = "pokedex"         # primeras palabras de la entrada Pokédex


# 1. Vocabulario temático curado para Pokémon icónicos
VOCABULARIO_TEMATICO: dict[str, tuple[str, str]] = {
    "pikachu": ("Chispa", "Spark"),
    "raichu": ("Relámpago", "Lightning"),
    "charizard": ("Alas", "Wings"),
    "charmander": ("Rescoldo", "Ember"),
    "blastoise": ("Coraza", "Shell"),
    "squirtle": ("Caparazón", "Carapace"),
    "venusaur": ("Florecer", "Bloom"),
    "bulbasaur": ("Semilla", "Seed"),
    "gengar": ("Sombra", "Shadow"),
    "haunter": ("Espectro", "Specter"),
    "gastly": ("Gas", "Vapor"),
    "snorlax": ("Letargo", "Slumber"),
    "eevee": ("Adaptación", "Adaptable"),
    "lucario": ("Aura", "Aura"),
    "mewtwo": ("Genético", "Genetic"),
    "mew": ("Misterio", "Mystery"),
    "mimikyu": ("Disfraz", "Disguise"),
    "zoroark": ("Ilusión", "Illusion"),
    "talonflame": ("Rapaz", "Falcon"),
    "greninja": ("Sigilo", "Stealth"),
    "garchomp": ("Tiburón", "Shark"),
    "dragonite": ("Mensajero", "Messenger"),
    "gyarados": ("Furia", "Rage"),
    "magikarp": ("Salto", "Splash"),
    "ditto": ("Transformación", "Morph"),
    "lapras": ("Navegante", "Voyager"),
    "articuno": ("Escarcha", "Frost"),
    "zapdos": ("Tormenta", "Storm"),
    "moltres": ("Llama", "Blaze"),
    "tyranitar": ("Armadura", "Armor"),
    "lugia": ("Mareas", "Tides"),
    "ho-oh": ("Arcoíris", "Rainbow"),
    "gardevoir": ("Lealtad", "Loyalty"),
    "rayquaza": ("Estratosfera", "Sky"),
    "dialga": ("Tiempo", "Time"),
    "palkia": ("Espacio", "Space"),
    "giratina": ("Distorsión", "Distortion"),
    "darkrai": ("Pesadilla", "Nightmare"),
    "arceus": ("Creación", "Creation"),
    "meowscarada": ("Truco", "Illusionist"),
    "skeledirge": ("Canto", "Melody"),
    "quaquaval": ("Danza", "Dancer"),
    "tinkaton": ("Forja", "Forge"),
    "ceruledge": ("Filo", "Blade"),
    "armarouge": ("Cañón", "Cannon"),
    "dragapult": ("Proyectil", "Missile"),
    "corviknight": ("Blindaje", "Steely"),
    "toxtricity": ("Punk", "Voltage"),
    "decidueye": ("Tirador", "Archer"),
    "incineroar": ("Luchador", "Brawler"),
    "primarina": ("Sirena", "Siren"),
}

# 2. Extracción dinámica por hábitat (soporte para inglés y español)
HABITATS_AMBIGUOS: dict[str, tuple[str, str]] = {
    "cave": ("Caverna", "Cavern"),
    "cueva": ("Caverna", "Cavern"),
    "forest": ("Silvestre", "Woodland"),
    "bosque": ("Silvestre", "Woodland"),
    "grassland": ("Pradera", "Meadow"),
    "praderas": ("Pradera", "Meadow"),
    "pradera": ("Pradera", "Meadow"),
    "mountain": ("Cumbre", "Summit"),
    "montaña": ("Cumbre", "Summit"),
    "montana": ("Cumbre", "Summit"),
    "rare": ("Insólito", "Uncommon"),
    "raro": ("Insólito", "Uncommon"),
    "rough-terrain": ("Rocoso", "Craggy"),
    "terreno escarpado": ("Rocoso", "Craggy"),
    "sea": ("Abisal", "Marine"),
    "mar": ("Abisal", "Marine"),
    "urban": ("Metrópolis", "Urban"),
    "urbano": ("Metrópolis", "Urban"),
    "waters-edge": ("Ribera", "Shore"),
    "orilla del agua": ("Ribera", "Shore"),
}

# 3. Fallback temático por Tipo elemental
TIPOS_AMBIGUOS: dict[str, tuple[str, str]] = {
    "fire": ("Calor", "Warmth"),
    "water": ("Fluido", "Flow"),
    "grass": ("Clorofila", "Flora"),
    "electric": ("Voltio", "Energy"),
    "ice": ("Gélido", "Glacial"),
    "fighting": ("Marcial", "Martial"),
    "poison": ("Tóxico", "Venom"),
    "ground": ("Terrestre", "Earthy"),
    "flying": ("Aéreo", "Aerial"),
    "psychic": ("Mental", "Mind"),
    "bug": ("Exoesqueleto", "Insect"),
    "rock": ("Mineral", "Mineral"),
    "ghost": ("Incorpóreo", "Ethereal"),
    "dragon": ("Ancestral", "Ancient"),
    "steel": ("Metálico", "Alloy"),
    "dark": ("Penumbra", "Gloom"),
    "fairy": ("Encanto", "Fae"),
    "normal": ("Común", "Plain"),
}


def pista_palabra_ambigua(dp: dict, gid: int) -> str:
    lang = get_lang(gid)
    # Usar nombre_base si es una forma Mega/Gimmick para encontrar su palabra temática
    nombre_base = (dp.get("nombre_base") or dp.get("nombre") or "").lower()
    especie = dp.get("especie", "")
    habitat = dp.get("habitat", "")
    tipos = dp.get("tipos", [])

    if nombre_base in VOCABULARIO_TEMATICO:
        pal_es, pal_en = VOCABULARIO_TEMATICO[nombre_base]
        palabra = pal_es if lang == "es" else pal_en
        return t("hint_text_word", gid, word=palabra)

    if especie:
        limpia = especie.replace("Pokémon", "").replace("Pokemon", "").strip()
        partes = limpia.split()
        if partes:
            palabra = partes[-1].capitalize() if lang == "es" else partes[0].capitalize()
            if len(palabra) >= 3 and palabra.lower() != nombre_base:
                return t("hint_text_word", gid, word=palabra)

    hab_key = str(habitat).lower()
    if hab_key in HABITATS_AMBIGUOS:
        p_es, p_en = HABITATS_AMBIGUOS[hab_key]
        palabra = p_es if lang == "es" else p_en
        return t("hint_text_word", gid, word=palabra)

    for t_elem in tipos:
        t_low = t_elem.lower()
        if t_low in TIPOS_AMBIGUOS:
            p_es, p_en = TIPOS_AMBIGUOS[t_low]
            palabra = p_es if lang == "es" else p_en
            return t("hint_text_word", gid, word=palabra)

    return t("hint_text_word", gid, word="Enigma")


def pista_perfil(dp: dict, gid: int) -> str:
    especie = dp.get("especie") or t("hint_unknown_value", gid)
    habitat = dp.get("habitat") or t("hint_unknown_value", gid)
    huevo   = ", ".join(dp.get("grupos_huevo", [])) or t("hint_unknown_value", gid)
    return t("hint_text_profile", gid, species=especie, habitat=habitat, egg=huevo)


def pista_debilidades(dp: dict, gid: int) -> str:
    tipos = dp.get("tipos", [])
    x4 = debilidades_x4(tipos)
    if x4:
        return t("hint_text_weakness_x4", gid, types=", ".join(x4))

    x2 = debilidades_x2(tipos)
    if x2:
        return t("hint_text_weakness_x2", gid, types=", ".join(x2[:2]))

    return t("hint_text_weakness_none", gid)


def pista_pokedex(dp: dict, gid: int) -> str:
    entry = dp.get("pokedex_entry", "")
    if not entry:
        return t("hint_text_pokedex_unavailable", gid)

    nombre_base = dp.get("nombre_base") or dp.get("nombre", "")
    palabras = entry.split()
    limite = " ".join(palabras[:18])
    if len(palabras) > 18:
        limite += "..."

    terminos = {
        "fuego", "fire", "agua", "water", "planta", "grass", "electrico", "eléctrico", "electric",
        "hielo", "ice", "lucha", "fighting", "veneno", "poison", "tierra", "ground",
        "volador", "flying", "psiquico", "psíquico", "psychic", "bicho", "bug", "roca", "rock",
        "fantasma", "ghost", "dragon", "dragón", "steel", "acero", "siniestro", "dark", "hada", "fairy",
        "normal", "cola", "tail", "alas", "wings", "cuerno", "cuernos", "horn", "horns",
        "caparazon", "caparazón", "shell", "pico", "beak", "garras", "claws",
        "tentaculos", "tentáculos", "tentacles", "antenas", "colmillos", "fangs",
    }
    if nombre_base:
        nom_lower = nombre_base.lower()
        terminos.add(nom_lower)
        if len(nom_lower) >= 5 and nom_lower[:4] not in {"para", "como", "este", "esta", "todo", "toda", "gran", "star", "sand", "slow"}:
            terminos.add(nom_lower[:4])

    for termino in sorted(terminos, key=len, reverse=True):
        patron = re.compile(rf"\b{re.escape(termino)}\w*\b", re.IGNORECASE)
        limite = patron.sub("[???]", limite)

    return t("hint_text_pokedex", gid, excerpt=limite)


def pista_letra_con_color(dp: dict, gid: int) -> str:
    """
    Feedback de Candela: En lugar de dar solo la letra inicial (que deja vendido
    al impostor si le toca hablar de primero), entrega la Letra Inicial de la
    especie + el Color principal del Pokémon.
    """
    nombre_especie = dp.get("nombre_base") or dp.get("nombre") or "?"
    inicial = nombre_especie[0].upper()
    color = dp.get("color") or t("hint_unknown_value", gid)
    return t("hint_text_letter_color", gid, v=inicial, color=color)


def pista_region_con_color(dp: dict, gid: int) -> str:
    """
    Entrega la Región/Generación de origen acompañada de su color principal
    para dar una característica tangible de la que hablar en el turno 1.
    """
    gen = dp.get("gen", "?")
    color = dp.get("color") or t("hint_unknown_value", gid)
    return t("hint_text_region_color", gid, v=gen, color=color)


def generar_pista(dp: dict, ventaja: Ventaja, gid: int, excluir: set[str] | None = None) -> str:
    """
    Genera una pista aleatoria o según config.
    Si excluir está definido, no repite pistas ya asignadas a otros impostores.
    """
    habilidades = dp.get("habilidades") or []
    hab_valor = random.choice(habilidades) if habilidades else t("hint_unknown_value", gid)

    opciones: dict[Ventaja, str] = {
        Ventaja.LETRA:           pista_letra_con_color(dp, gid),
        Ventaja.TIPO:            t("hint_text_type",    gid, v=", ".join(dp.get("tipos", ["?"]))),
        Ventaja.RANGO_REGION:    pista_region_con_color(dp, gid),
        Ventaja.HABILIDAD:       t("hint_text_ability", gid, v=hab_valor),
        Ventaja.PALABRA_AMBIGUA: pista_palabra_ambigua(dp, gid),
        Ventaja.PERFIL:          pista_perfil(dp, gid),
        Ventaja.DEBILIDADES:     pista_debilidades(dp, gid),
        Ventaja.POKEDEX:         pista_pokedex(dp, gid),
    }

    if ventaja != Ventaja.ALEATORIO:
        return opciones.get(ventaja, opciones[Ventaja.TIPO])

    if excluir:
        disponibles = [v for k, v in opciones.items() if v not in excluir]
        if disponibles:
            return random.choice(disponibles)
    return random.choice(list(opciones.values()))

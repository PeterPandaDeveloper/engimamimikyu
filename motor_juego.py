"""
motor_juego.py — Núcleo lógico de PokeImpostor
"""
from __future__ import annotations

import asyncio
import random
import re
import discord
from dataclasses import dataclass, field
from enum import Enum

from api import obtener_datos_completos_pokemon
from tipos_pokemon import debilidades_x4, debilidades_x2
from i18n import t, get_lang


# ═══════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class ModoJuego(str, Enum):
    CLASICO   = "clasico"
    EXTENDIDO = "extendido"
    CAOS      = "caos"


class CaosVariante(str, Enum):
    """
    Sub-modificadores EXCLUSIVOS del modo CAOS (radio buttons: solo uno activo).
    Nunca se revelan en el embed público — solo el admin los ve al configurar.
    """
    NORMAL          = "normal"            # Caos estándar (impostores 0..N sobre un Pokémon)
    OBJETIVO_HUMANO = "objetivo_humano"   # un jugador real es el "secreto" en vez de un Pokémon
    DANZA_CAOS      = "danza_caos"        # cada jugador recibe un Pokémon distinto (sin impostores)


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


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConfigPartida:
    regiones:      list[str]    = field(default_factory=lambda: ["todas"])
    modo_juego:    ModoJuego    = ModoJuego.CLASICO
    ventaja:       Ventaja      = Ventaja.ALEATORIO
    max_rondas:    int          = 3  # Límite de rondas del juego (1 a 9)
    caos_variante: CaosVariante = CaosVariante.NORMAL


# ═══════════════════════════════════════════════════════════════════════════════
#  RANGOS POR GENERACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

RANGOS_GEN: dict[str, range] = {
    "gen1": range(1,   152),
    "gen2": range(152, 252),
    "gen3": range(252, 387),
    "gen4": range(387, 494),
    "gen5": range(494, 650),
    "gen6": range(650, 722),
    "gen7": range(722, 810),
    "gen8": range(810, 906),
    "gen9": range(906, 1026),
}


# ═══════════════════════════════════════════════════════════════════════════════
#  CLASE PARTIDA
# ═══════════════════════════════════════════════════════════════════════════════

class Partida:
    def __init__(self, canal: discord.TextChannel, partidas_activas: dict):
        self.canal  = canal
        self.config = ConfigPartida()

        self.jugadores:  list[discord.Member] = []
        self.impostores: list[discord.Member] = []

        self.jugadores_iniciales:  list[discord.Member] = []
        self.impostores_iniciales: list[discord.Member] = []

        self.ronda:               int         = 1
        self.datos_pokemon:       dict | None = None
        self.caos_sin_impostores: bool        = False

        # Anti-estancamiento: si pasan demasiadas rondas sin ninguna
        # expulsión (ej. todos votando nulo), se revela una pista pública
        # para presionar al grupo a decidirse.
        self.rondas_sin_expulsion: int  = 0
        self.pista_publica_revelada: bool = False

        # fix: cada impostor tiene su propia pista
        # { jugador.id: texto_de_pista }
        self.pistas_impostores: dict[int, str] = {}
        # para /impver y compatibilidad — pista del primer impostor o única
        self.pista_generada: str = ""

        # variante Objetivo Humano: quién es el "objetivo" (jugador que los demás describen)
        self.objetivo_humano: discord.Member | None = None

        # variante Danza Caos: cada tripulante tiene su propio Pokémon
        # { jugador.id: dict_pokemon }
        self.pokemons_ebrios: dict[int, dict] = {}

        # Variante efectiva de esta ronda (puede diferir de config.caos_variante
        # porque se sortea aleatoriamente en cada arrancar_ronda)
        self._variante_ronda: CaosVariante = CaosVariante.NORMAL

        self._pokemon_usados:   set[int] = set()
        self._partidas_activas: dict     = partidas_activas
        self.terminada:         bool     = False

        # Lock de concurrencia: protege operaciones que mutan el estado de la
        # partida desde callbacks de UI (votar, forzar cierre, iniciar ronda,
        # revancha...). Sin esto, dos interacciones casi simultáneas podrían
        # ejecutar la misma transición dos veces (doble expulsión, doble
        # avance de ronda, etc.).
        self.lock: asyncio.Lock = asyncio.Lock()
        # Flag auxiliar: True mientras arrancar_ronda() está en ejecución,
        # para detectar intentos concurrentes de iniciar/revancha.
        self._ronda_arrancando: bool = False

    @property
    def partidas_activas(self) -> dict:
        return self._partidas_activas

    @property
    def rondas_restantes(self) -> int:
        """Contador decremental: rondas que le quedan al grupo antes de que ganen los impostores."""
        return max(0, self.config.max_rondas - self.ronda + 1)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _t(self, key: str, **kwargs) -> str:
        return t(key, self.canal.guild.id, **kwargs)

    def limpiar_memoria(self) -> None:
        self._partidas_activas.pop(self.canal.id, None)

    # ── pista pública anti-estancamiento (visible para TODOS) ────────────────
    def generar_pista_publica(self) -> str | None:
        """
        Genera un dato público sobre el Pokémon secreto, distinto de las
        pistas ya entregadas a los impostores, para presionar al grupo
        cuando llevan demasiadas rondas sin expulsar a nadie.
        Devuelve None si no aplica (variantes sin Pokémon secreto tradicional).
        """
        if self.datos_pokemon is None:
            return None
        gid = self.canal.guild.id
        dp  = self.datos_pokemon
        # Reutilizamos el generador de pistas, excluyendo las ya repartidas
        # a los impostores para no dar información redundante.
        excluir = set(self.pistas_impostores.values())
        return self._generar_pista_para(dp, excluir=excluir)

    # ── selección de ID sin repetición ───────────────────────────────────────
    def _elegir_id_pokemon(self) -> int:
        ids_validos: list[int] = []
        if "todas" in self.config.regiones:
            ids_validos = list(range(1, 1026))
        else:
            for gen in self.config.regiones:
                if gen in RANGOS_GEN:
                    ids_validos.extend(RANGOS_GEN[gen])
        if not ids_validos:
            ids_validos = list(range(1, 152))

        disponibles = [i for i in ids_validos if i not in self._pokemon_usados]
        if not disponibles:
            self._pokemon_usados.clear()
            disponibles = ids_validos

        elegido = random.choice(disponibles)
        self._pokemon_usados.add(elegido)
        return elegido

    # ── generación de UNA pista para UN impostor (siempre distinta) ──────────
    def _generar_pista_para(self, dp: dict, excluir: set[str] | None = None) -> str:
        """
        Genera una pista aleatoria o según config.
        Si excluir está definido, no repite pistas ya asignadas a otros impostores.
        """
        gid = self.canal.guild.id
        nombre = dp.get("nombre") or "?"
        habilidades = dp.get("habilidades") or []
        hab_valor = random.choice(habilidades) if habilidades else t("hint_unknown_value", gid)

        opciones: dict[Ventaja, str] = {
            Ventaja.LETRA:        t("hint_text_letter", gid, v=nombre[0]),
            Ventaja.TIPO:         t("hint_text_type",   gid, v=", ".join(dp.get("tipos", ["?"]))),
            Ventaja.RANGO_REGION: t("hint_text_region", gid, v=dp.get("gen", "?")),
            Ventaja.HABILIDAD:    t("hint_text_ability", gid, v=hab_valor),
            Ventaja.PALABRA_AMBIGUA: self._pista_palabra_ambigua(dp, gid),
            Ventaja.PERFIL:          self._pista_perfil(dp, gid),
            Ventaja.DEBILIDADES:     self._pista_debilidades(dp, gid),
            Ventaja.POKEDEX:         self._pista_pokedex(dp, gid),
        }

        if self.config.ventaja != Ventaja.ALEATORIO:
            return opciones.get(self.config.ventaja, opciones[Ventaja.TIPO])

        # aleatorio: evitar repetir si hay varias pistas disponibles
        if excluir:
            disponibles = [v for k, v in opciones.items() if v not in excluir]
            if disponibles:
                return random.choice(disponibles)
        return random.choice(list(opciones.values()))

    # ── Pista: una sola palabra ambigua y temática (Sin estadísticas RPG) ────
    @staticmethod
    def _pista_palabra_ambigua(dp: dict, gid: int) -> str:
        """
        Pista de una sola palabra ambigua para el impostor.
        Entrega un término conceptual, rasgo, temática o comportamiento del Pokémon
        sin revelar su nombre directamente ni usar estadísticas numéricas.
        """
        lang = get_lang(gid)
        nombre = dp.get("nombre", "").lower()
        especie = dp.get("especie", "")
        habitat = dp.get("habitat", "")
        tipos = dp.get("tipos", [])

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

        if nombre in VOCABULARIO_TEMATICO:
            pal_es, pal_en = VOCABULARIO_TEMATICO[nombre]
            palabra = pal_es if lang == "es" else pal_en
            return t("hint_text_word", gid, word=palabra)

        # 2. Extracción dinámica desde 'especie' (género taxonómico)
        if especie:
            limpia = especie.replace("Pokémon", "").replace("Pokemon", "").strip()
            partes = limpia.split()
            if partes:
                palabra = partes[-1].capitalize() if lang == "es" else partes[0].capitalize()
                if len(palabra) >= 3 and palabra.lower() != nombre:
                    return t("hint_text_word", gid, word=palabra)

        # 3. Extracción dinámica por hábitat
        HABITATS_AMBIGUOS: dict[str, tuple[str, str]] = {
            "cave": ("Caverna", "Cavern"),
            "forest": ("Silvestre", "Woodland"),
            "grassland": ("Pradera", "Meadow"),
            "mountain": ("Cumbre", "Summit"),
            "rare": ("Insólito", "Uncommon"),
            "rough-terrain": ("Rocoso", "Craggy"),
            "sea": ("Abisal", "Marine"),
            "urban": ("Metrópolis", "Urban"),
            "waters-edge": ("Ribera", "Shore"),
        }
        hab_key = str(habitat).lower()
        if hab_key in HABITATS_AMBIGUOS:
            p_es, p_en = HABITATS_AMBIGUOS[hab_key]
            palabra = p_es if lang == "es" else p_en
            return t("hint_text_word", gid, word=palabra)

        # 4. Fallback temático por Tipo elemental
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
        for t_elem in tipos:
            t_low = t_elem.lower()
            if t_low in TIPOS_AMBIGUOS:
                p_es, p_en = TIPOS_AMBIGUOS[t_low]
                palabra = p_es if lang == "es" else p_en
                return t("hint_text_word", gid, word=palabra)

        palabra = "Enigma" if lang == "es" else "Enigma"
        return t("hint_text_word", gid, word=palabra)

    # ── Pista: perfil (especie + hábitat + grupo huevo) ───────────────────────
    @staticmethod
    def _pista_perfil(dp: dict, gid: int) -> str:
        especie = dp.get("especie") or t("hint_unknown_value", gid)
        habitat = dp.get("habitat") or t("hint_unknown_value", gid)
        huevo   = ", ".join(dp.get("grupos_huevo", [])) or t("hint_unknown_value", gid)
        return t("hint_text_profile", gid, species=especie, habitat=habitat, egg=huevo)

    # ── Pista: debilidades (x4 > x2 > ninguna) ────────────────────────────────
    @staticmethod
    def _pista_debilidades(dp: dict, gid: int) -> str:
        tipos = dp.get("tipos", [])
        x4 = debilidades_x4(tipos)
        if x4:
            return t("hint_text_weakness_x4", gid, types=", ".join(x4))

        x2 = debilidades_x2(tipos)
        if x2:
            # Mostrar como máximo 2 para no ser demasiado revelador
            return t("hint_text_weakness_x2", gid, types=", ".join(x2[:2]))

        return t("hint_text_weakness_none", gid)

    # ── Pista: entrada de Pokédex censurada (Cloze Test) ──────────────────────
    @staticmethod
    def _pista_pokedex(dp: dict, gid: int) -> str:
        entry = dp.get("pokedex_entry", "")
        if not entry:
            return t("hint_text_pokedex_unavailable", gid)

        nombre = dp.get("nombre", "")
        palabras = entry.split()
        limite = " ".join(palabras[:18])
        if len(palabras) > 18:
            limite += "..."

        # Términos que regalarían la identidad o tipo elemental
        terminos = {
            "fuego", "fire", "agua", "water", "planta", "grass", "electrico", "eléctrico", "electric",
            "hielo", "ice", "lucha", "fighting", "veneno", "poison", "tierra", "ground",
            "volador", "flying", "psiquico", "psíquico", "psychic", "bicho", "bug", "roca", "rock",
            "fantasma", "ghost", "dragon", "dragón", "steel", "acero", "siniestro", "dark", "hada", "fairy",
            "normal", "cola", "tail", "alas", "wings", "cuerno", "cuernos", "horn", "horns",
            "caparazon", "caparazón", "shell", "pico", "beak", "garras", "claws",
            "tentaculos", "tentáculos", "tentacles", "antenas", "colmillos", "fangs",
        }
        if nombre:
            nom_lower = nombre.lower()
            terminos.add(nom_lower)
            if len(nom_lower) >= 4:
                terminos.add(nom_lower[:4])

        for termino in sorted(terminos, key=len, reverse=True):
            patron = re.compile(rf"\b{re.escape(termino)}\w*\b", re.IGNORECASE)
            limite = patron.sub("[???]", limite)

        return t("hint_text_pokedex", gid, excerpt=limite)


    # ── sorteo de variante Caos por ronda ─────────────────────────────────
    def _sortear_variante_caos(self) -> CaosVariante:
        """
        Caos Total: Al elegir Modo Caos, el juego es una ruleta rusa impredecible.
        Sortea aleatoriamente entre Caos Normal (con 0 o N impostores), Objetivo Humano o Danza Caos.
        """
        opciones = [CaosVariante.NORMAL, CaosVariante.OBJETIVO_HUMANO, CaosVariante.DANZA_CAOS]
        pesos    = [0.45,                0.30,                         0.25]
        return random.choices(opciones, weights=pesos, k=1)[0]

    # ── cantidad de impostores ─────────────────────────────────────────────
    def _calcular_impostores(self, total: int) -> int:
        modo = self.config.modo_juego
        if modo == ModoJuego.CLASICO:   return 1
        if modo == ModoJuego.EXTENDIDO: return min(max(1, total // 3), total - 1)
        if modo == ModoJuego.CAOS:
            # Usar la variante efectiva de esta ronda (sorteada, no la config)
            if self._variante_ronda == CaosVariante.OBJETIVO_HUMANO:
                return 1
            return self._roll_caos_impostores(total)
        return 1

    @staticmethod
    def _roll_caos_impostores(total: int) -> int:
        """
        Tira el dado del Caos: cuántos impostores habrá.

        Reglas de diseño para que el Caos se sienta "dominado" y no un
        sorteo sin sentido:
        - Nunca TODOS son impostores (eso mata la partida en la ronda 1
          sin debate posible).
        - 0 impostores sigue siendo posible (es la sorpresa icónica del
          Caos: "esta ronda no hay traidores"), pero es poco frecuente.
        - El resto de la probabilidad se concentra en valores "jugables":
          de 1 hasta la mitad de los jugadores (redondeando hacia abajo,
          mínimo 1), que es donde el debate y la votación tienen sentido.
        """
        maximo_jugable = max(1, total // 2)  # ej. 6 jugadores → hasta 3 impostores
        # Pesos: 0 impostores tiene peso fijo bajo; el resto se reparte
        # uniformemente entre 1..maximo_jugable. Para grupos pequeños
        # (pocas opciones jugables), el peso de 0 se reduce más para que
        # no domine la distribución.
        opciones = [0] + list(range(1, maximo_jugable + 1))
        peso_cero = 1 if maximo_jugable >= 2 else 0.5
        pesos     = [peso_cero] + [3] * maximo_jugable
        elegido   = random.choices(opciones, weights=pesos, k=1)[0]
        # Salvaguarda final: jamás todos los jugadores (se necesita al
        # menos 1 tripulante para que haya partida).
        return min(elegido, total - 1)

    # ── DM impostor clásico/extendido/caos ───────────────────────────────────
    def _build_dm_impostor(self, jugador: discord.Member) -> discord.Embed:
        gid       = self.canal.guild.id
        pista     = self.pistas_impostores.get(jugador.id, self.pista_generada)
        total_imp = len(self.impostores)
        complices = [j for j in self.impostores if j != jugador]
        modo      = self.config.modo_juego

        embed = discord.Embed(
            title=t("dm_impostor_title", gid),
            description=t("dm_impostor_desc", gid, hint=pista),
            color=discord.Color.from_rgb(180, 30, 30),
        )
        if modo == ModoJuego.EXTENDIDO and total_imp > 1:
            nombres = ", ".join(f"**{c.display_name}**" for c in complices)
            embed.add_field(
                name=t("dm_impostor_accomplices_title_hidden", gid),
                value=t("dm_impostor_accomplices_value", gid, names=nombres),
                inline=False,
            )
        embed.set_footer(text=t("dm_impostor_footer", gid))
        return embed

    # ── DM tripulante ────────────────────────────────────────────────────────
    def _build_dm_tripulante(self, dp: dict) -> discord.Embed:
        gid = self.canal.guild.id
        embed = discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_crew_desc", gid, name=dp.get("nombre", "?"), types=" / ".join(dp.get("tipos", ["?"]))),
            color=discord.Color.from_rgb(30, 160, 80),
        )
        if dp.get("sprite"):
            embed.set_image(url=dp["sprite"])
        embed.set_footer(text=t("dm_crew_footer", gid))
        return embed

    # ── DM variante Objetivo Humano ──────────────────────────────────────────
    def _build_dm_caos_jugador_impostor(self, pista: str = "") -> discord.Embed:
        gid = self.canal.guild.id
        embed = discord.Embed(
            title=t("dm_impostor_title", gid),
            description=t("dm_impostor_desc", gid, hint=pista),
            color=discord.Color.from_rgb(180, 30, 30),
        )
        embed.set_footer(text=t("dm_impostor_footer", gid))
        return embed

    def _build_dm_caos_jugador_detective(self, objetivo: discord.Member, pista: str = "") -> discord.Embed:
        return self._build_dm_caos_jugador_impostor(pista)

    def _build_dm_caos_jugador_tripulante(self, objetivo: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        # Aparte de la imagen, entregamos nombre en servidor y username @ por si la imagen falla al cargar
        tag_usuario = f"**{objetivo.display_name}** (`@{objetivo.name}`)"
        embed = discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_caos_jugador_crew_desc", gid, target=tag_usuario),
            color=discord.Color.from_rgb(30, 160, 80),
        )
        if getattr(objetivo, "display_avatar", None) and objetivo.display_avatar.url:
            embed.set_image(url=objetivo.display_avatar.url)
            embed.set_thumbnail(url=objetivo.display_avatar.url)
        embed.set_footer(text=t("dm_crew_footer", gid))
        return embed

    def _build_dm_caos_jugador_objetivo(self) -> discord.Embed:
        return self._build_dm_caos_jugador_impostor()

    # ── DM variante Danza Caos — NO revela sub-modo NI nombre del Pokémon ──
    def _build_dm_amigos_ebrios(self, jugador: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        dp  = self.pokemons_ebrios.get(jugador.id)
        if not dp:
            return discord.Embed(title="Error", description="No se asignó Pokémon.")
        # Título y color IGUALES al tripulante normal → no delata el sub-modo.
        # NO se revela el nombre — solo el tipo y el sprite para que el jugador
        # sepa qué describir sin que sea trivialmente obvio para los demás.
        tipos_str = " / ".join(dp.get("tipos", ["?"]))
        embed = discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_ebrios_desc", gid, types=tipos_str),
            color=discord.Color.from_rgb(30, 160, 80),
        )
        if dp.get("sprite"):
            embed.set_image(url=dp["sprite"])
        embed.set_footer(text=t("dm_ebrios_footer", gid))
        return embed

    # ─────────────────────────────────────────────────────────────────────────
    #  ARRANCAR RONDA — punto de entrada principal
    # ─────────────────────────────────────────────────────────────────────────
    async def arrancar_ronda(self) -> bool:
        self.ronda = 1
        self.terminada = False
        self.impostores.clear()
        self.jugadores_iniciales.clear()
        self.impostores_iniciales.clear()
        self.pistas_impostores.clear()
        self.pista_generada   = ""
        self.caos_sin_impostores = False
        self.objetivo_humano  = None
        self.pokemons_ebrios.clear()
        self._variante_ronda = CaosVariante.NORMAL
        self.rondas_sin_expulsion   = 0
        self.pista_publica_revelada = False

        modo = self.config.modo_juego

        # Caos: elegir variante aleatoriamente entre las permitidas ─────────
        # Los radio buttons de configuración indican qué variantes PUEDEN salir
        # (NORMAL siempre disponible). En cada ronda se sortea cuál aparece.
        if modo == ModoJuego.CAOS:
            variante_elegida = self._sortear_variante_caos()
            self._variante_ronda = variante_elegida   # usada por _calcular_impostores
            if variante_elegida == CaosVariante.DANZA_CAOS:
                return await self._arrancar_amigos_ebrios()
            if variante_elegida == CaosVariante.OBJETIVO_HUMANO:
                return await self._arrancar_caos_jugador()
            # Si NORMAL, continúa con el flujo estándar de Caos

        # ── Modos normales (Clásico / Extendido / Caos) ───────────────────────
        id_elegido         = self._elegir_id_pokemon()
        lang               = get_lang(self.canal.guild.id)
        self.datos_pokemon = await obtener_datos_completos_pokemon(id_elegido, lang=lang)
        if self.datos_pokemon is None:
            await self.canal.send(self._t("api_error"))
            return False

        total    = len(self.jugadores)
        cant_imp = self._calcular_impostores(total)

        if cant_imp == 0:
            self.caos_sin_impostores = True
            self.impostores          = []
        else:
            self.impostores = random.sample(self.jugadores, cant_imp)

        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        # fix: pista DISTINTA para cada impostor
        pistas_usadas: set[str] = set()
        for imp in self.impostores:
            pista = self._generar_pista_para(self.datos_pokemon, excluir=pistas_usadas)
            self.pistas_impostores[imp.id] = pista
            pistas_usadas.add(pista)

        # pista_generada = primera pista (para compatibilidad con /impver en modo 1 impostor)
        if self.pistas_impostores:
            self.pista_generada = next(iter(self.pistas_impostores.values()))

        # enviar DMs en paralelo con asyncio.gather
        dm_fallidos: list[discord.Member] = []

        async def _enviar_dm(j: discord.Member):
            try:
                if j in self.impostores:
                    await j.send(embed=self._build_dm_impostor(j))
                else:
                    await j.send(embed=self._build_dm_tripulante(self.datos_pokemon))
            except Exception as e:
                print(f"[DM] Falló con {j.display_name}: {e}")
                dm_fallidos.append(j)

        await asyncio.gather(*(_enviar_dm(j) for j in self.jugadores))

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True

    # ── Subrutina: Amigos Ebrios ──────────────────────────────────────────────
    async def _arrancar_amigos_ebrios(self) -> bool:
        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = []
        self.impostores          = []
        self.caos_sin_impostores = True

        # asignar Pokémon y enviar DMs en paralelo
        dm_fallidos: list[discord.Member] = []
        lang = get_lang(self.canal.guild.id)

        async def _preparar_ebrio(jugador: discord.Member, idx: int):
            id_pk = self._elegir_id_pokemon()
            dp = await obtener_datos_completos_pokemon(id_pk, lang=lang)
            if dp is None:
                return False
            self.pokemons_ebrios[jugador.id] = dp
            if idx == 0:
                self.datos_pokemon = dp  # para la pantalla final
            try:
                await jugador.send(embed=self._build_dm_amigos_ebrios(jugador))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)
            return True

        resultados = await asyncio.gather(*(_preparar_ebrio(j, i) for i, j in enumerate(self.jugadores)))
        if not all(resultados):
            await self.canal.send(self._t("api_error"))
            return False

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True

    # ── Subrutina: Caos Jugador ────────────────────────────────────────────────
    async def _arrancar_caos_jugador(self) -> bool:
        # 1. Selección completamente aleatoria e independiente del objetivo y del/los impostor(es)
        self.objetivo_humano = random.choice(self.jugadores)

        num_imp = max(1, min(len(self.jugadores) - 1, self._calcular_impostores(len(self.jugadores))))
        self.impostores = random.sample(self.jugadores, k=num_imp)
        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        gid = self.canal.guild.id
        # Extraer letra inicial y letra final de forma segura
        nombre_limpio = [c.upper() for c in self.objetivo_humano.display_name if c.isalnum()]
        if nombre_limpio:
            primera_letra = nombre_limpio[0]
            ultima_letra = nombre_limpio[-1]
        else:
            primera_letra = self.objetivo_humano.display_name[0].upper()
            ultima_letra = self.objetivo_humano.display_name[-1].upper()

        # Generar pista ambigua (empieza con / termina con) para camuflar al impostor
        for imp in self.impostores:
            if random.choice([True, False]):
                pista = t("hint_text_letter", gid, v=primera_letra)
            else:
                pista = t("hint_text_ends_letter", gid, v=ultima_letra)
            self.pistas_impostores[imp.id] = pista

        dm_fallidos: list[discord.Member] = []

        async def _enviar_dm_humano(jugador: discord.Member):
            try:
                if jugador in self.impostores:
                    # El impostor recibe el DM ESTÁNDAR de impostor con su pista ambigua.
                    # NO sabe que es modo objetivo humano ni se spoilea.
                    pista = self.pistas_impostores.get(jugador.id, "")
                    await jugador.send(embed=self._build_dm_caos_jugador_impostor(pista))
                else:
                    # Los tripulantes reciben el nombre de usuario del servidor y la imagen
                    await jugador.send(embed=self._build_dm_caos_jugador_tripulante(self.objetivo_humano))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        await asyncio.gather(*(_enviar_dm_humano(j) for j in self.jugadores))

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True
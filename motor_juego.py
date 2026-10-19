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
from pistas import (
    Ventaja,
    generar_pista,
    pista_palabra_ambigua,
    pista_perfil,
    pista_debilidades,
    pista_pokedex,
    VOCABULARIO_TEMATICO,
    HABITATS_AMBIGUOS,
    TIPOS_AMBIGUOS,
)


class _DummyAvatar:
    def __init__(self, url: str):
        self.url = url


class DummyMember:
    """
    Jugador fantasma para pruebas en solitario (Modo Debugger en Discord real).
    Redirige sus DMs al anfitrión humano para que pueda inspeccionar todos los roles.
    """
    es_dummy: bool = True

    def __init__(self, user_id: int, display_name: str, host_member: discord.Member):
        self.id = user_id
        self.name = display_name.lower().replace(" ", "_")
        self.display_name = f"🤖 {display_name}"
        self.global_name = display_name
        self.mention = f"**@{display_name}**"
        self.bot = False
        self.host_member = host_member
        # Avatar oficial temático para que se vea genial en Objetivo Humano y expulsiones
        self.display_avatar = _DummyAvatar(
            f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{user_id % 151 + 1}.png"
        )
        self.roles = []
        self.color = discord.Color.blue()

    def __eq__(self, other):
        if hasattr(other, "id"):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)

    async def send(self, content: str | None = None, *, embed: discord.Embed | None = None, **kwargs):
        # Redirige el DM del bot fantasma al DM del anfitrión que está probando
        try:
            header = f"🧪 **[DEBUG — Rol enviado a {self.display_name}]:**"
            await self.host_member.send(content=header, embed=embed)
        except Exception as e:
            print(f"[Debug DM] No se pudo redirigir DM de {self.display_name}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class ModoJuego(str, Enum):
    CLASICO   = "clasico"
    EXTENDIDO = "extendido"
    CAOS      = "caos"


class CaosVariante(str, Enum):
    """
    Sub-modificadores del modo CAOS.
    En cada ronda de Modo Caos se sortea aleatoriamente una de estas posibilidades:
      - CERO_IMPOSTORES: 0% impostores, todos comparten el mismo Pokémon (paranoia pura).
      - UN_IMPOSTOR: 1 solo impostor clásico.
      - CINCUENTA_PORCIENTO: 50% de la sala impostor.
      - SETENTA_Y_CINCO: 75% de la sala impostor.
      - TODOS_IMPOSTORES: 100% de impostores (todos impostores).
      - AMIGOS_BORRACHOS: 0 impostores, cada jugador recibe un Pokémon diferente.
      - OBJETIVO_HUMANO: un jugador de la sala es el secreto (foto y nombre).
    """
    CERO_IMPOSTORES      = "cero_impostores"
    UN_IMPOSTOR          = "un_impostor"
    CINCUENTA_PORCIENTO  = "cincuenta_pct"
    SETENTA_Y_CINCO      = "setenta_y_cinco_pct"
    TODOS_IMPOSTORES     = "todos_impostores"
    AMIGOS_BORRACHOS     = "amigos_borrachos"
    OBJETIVO_HUMANO      = "objetivo_humano"

    # Aliases retrocompatibles
    NORMAL               = "normal"
    DANZA_CAOS           = "amigos_borrachos"




# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConfigPartida:
    regiones:      list[str]    = field(default_factory=lambda: ["todas"])
    modo_juego:    ModoJuego    = ModoJuego.CLASICO
    ventaja:       Ventaja      = Ventaja.ALEATORIO
    max_rondas:        int          = 3  # Límite de rondas del juego (1 a 9)
    caos_variante:     CaosVariante = CaosVariante.NORMAL
    conocer_complices: bool         = True  # Modo extendido: permitir que los impostores sepan quién es impostor


# ═══════════════════════════════════════════════════════════════════════════════
#  RANGOS POR GENERACIÓN Y FORMAS ESPECIALES (MEGAS / GIMMICKS)
# ═══════════════════════════════════════════════════════════════════════════════

# IDs verificados en PokéAPI v2 (/pokemon/{id})
IDS_MEGAS_PRIMAL: list[int] = (
    list(range(10033, 10080))  # Mega Venusaur..Mega Diancie + Kyogre/Groudon Primigenios
    + [10087, 10088, 10089, 10090]  # Mega Slowbro, Steelix, Pidgeot, Glalie
)

IDS_REGIONALES: list[int] = (
    list(range(10091, 10116))  # Formas de Alola (Rattata..Marowak)
    + list(range(10161, 10181))  # Formas de Galar (Meowth..Stunfisk)
    + list(range(10229, 10245))  # Formas de Hisui (Growlithe..Avalugg)
    + [10250, 10251, 10252, 10253]  # Formas de Paldea (Tauros, Wooper)
)

IDS_GMAX: list[int] = list(range(10195, 10228))  # Formas Gigantamax

IDS_GIMMICKS: list[int] = (
    list(range(10001, 10025))  # Deoxys, Wormadam, Giratina-O, Shaymin-S, Rotom, Castform, Meloetta, Landorus-T, Kyurem-B/W
    + [10026, 10086, 10116, 10118, 10119, 10152, 10155, 10156, 10157]  # Aegislash, Hoopa-U, Greninja-Ash, Zygarde, Lycanroc, Necrozma
    + [10185, 10186, 10188, 10189, 10191, 10193, 10194]  # Eiscue, Morpeko, Zacian-C, Zamazenta-C, Urshifu, Calyrex
    + [10245, 10246, 10247, 10248, 10256, 10272, 10273, 10274, 10275]  # Dialga/Palkia Origen, Enamorus-T, Palafin-H, Ursaluna-BM, Ogerpon
)

IDS_TODAS_FORMAS_ESPECIALES: list[int] = (
    IDS_MEGAS_PRIMAL + IDS_REGIONALES + IDS_GMAX + IDS_GIMMICKS
)

RANGOS_GEN: dict[str, range | list[int]] = {
    "gen1":     range(1,   152),
    "gen2":     range(152, 252),
    "gen3":     range(252, 387),
    "gen4":     range(387, 494),
    "gen5":     range(494, 650),
    "gen6":     range(650, 722),
    "gen7":     range(722, 810),
    "gen8":     range(810, 906),
    "gen9":     range(906, 1026),
    "megas":    IDS_MEGAS_PRIMAL,
    "regional": IDS_REGIONALES,
    "gmax":     IDS_GMAX,
    "gimmicks": IDS_GIMMICKS,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  CLASE PARTIDA
# ═══════════════════════════════════════════════════════════════════════════════

class Partida:
    def __init__(self, canal: discord.TextChannel, partidas_activas: dict):
        self.canal  = canal
        self.config = ConfigPartida()
        self.mensaje_lobby: discord.Message | None = None

        self.jugadores:  list[discord.Member] = []
        self.impostores: list[discord.Member] = []

        self.jugadores_iniciales:  list[discord.Member] = []
        self.impostores_iniciales: list[discord.Member] = []

        self.ronda:               int         = 1
        self.datos_pokemon:       dict | None = None
        self.caos_sin_impostores:   bool        = False
        self.caos_todos_impostores: bool        = False

        # Anti-estancamiento: si pasan demasiadas rondas sin ninguna
        # expulsión (ej. todos votando nulo), se revela una pista pública
        # para presionar al grupo a decidirse.
        self.rondas_sin_expulsion: int  = 0
        self.pista_publica_revelada: bool = False
        self.empates_consecutivos: int = 0

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
            ids_validos = list(range(1, 1026)) + IDS_TODAS_FORMAS_ESPECIALES
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
        Genera una pista aleatoria o según config delegando a pistas.generar_pista.
        Si excluir está definido, no repite pistas ya asignadas a otros impostores.
        """
        gid = self.canal.guild.id
        return generar_pista(dp, self.config.ventaja, gid, excluir=excluir)

    # Métodos estáticos delegados para retrocompatibilidad
    _pista_palabra_ambigua = staticmethod(pista_palabra_ambigua)
    _pista_perfil          = staticmethod(pista_perfil)
    _pista_debilidades     = staticmethod(pista_debilidades)
    _pista_pokedex         = staticmethod(pista_pokedex)


    # ── sorteo de variante Caos por ronda ─────────────────────────────────
    def _sortear_variante_caos(self) -> CaosVariante:
        """
        Caos Total: Al elegir Modo Caos, la ronda es una ruleta rusa impredecible.
        Sortea equitativamente entre las 7 variantes oficiales:
          1. 0% impostores (todos comparten el mismo Pokémon)
          2. 1 solo impostor
          3. 50% de la sala impostor
          4. 75% de la sala impostor
          5. 100% de impostores (todos impostores)
          6. Amigos borrachos / Danza Caos (0 impostores, cada jugador un Pokémon)
          7. Objetivo humano (un jugador actual al azar es el objetivo con foto y nombre)
        """
        opciones = [
            CaosVariante.CERO_IMPOSTORES,
            CaosVariante.UN_IMPOSTOR,
            CaosVariante.CINCUENTA_PORCIENTO,
            CaosVariante.SETENTA_Y_CINCO,
            CaosVariante.TODOS_IMPOSTORES,
            CaosVariante.AMIGOS_BORRACHOS,
            CaosVariante.OBJETIVO_HUMANO,
        ]
        return random.choice(opciones)

    # ── cantidad de impostores ─────────────────────────────────────────────
    def _calcular_impostores(self, total: int) -> int:
        modo = self.config.modo_juego
        if modo == ModoJuego.CLASICO:
            return 1
        if modo == ModoJuego.EXTENDIDO:
            return min(max(1, total // 3), total - 1)
        if modo == ModoJuego.CAOS:
            var = self._variante_ronda
            if var == CaosVariante.CERO_IMPOSTORES or var == CaosVariante.AMIGOS_BORRACHOS:
                return 0
            if var == CaosVariante.UN_IMPOSTOR or var == CaosVariante.OBJETIVO_HUMANO:
                return 1
            if var == CaosVariante.CINCUENTA_PORCIENTO:
                return max(1, min(total - 1, int(round(total * 0.50))))
            if var == CaosVariante.SETENTA_Y_CINCO:
                return max(1, min(total - 1, int(round(total * 0.75))))
            if var == CaosVariante.TODOS_IMPOSTORES:
                return total
            return 1
        return 1

    @staticmethod
    def _roll_caos_impostores(total: int) -> int:
        if total <= 1:
            return 0
        return random.randint(0, total - 1)

    # ── DM impostor clásico/extendido/caos ───────────────────────────────────
    def _build_dm_impostor(self, jugador: discord.Member) -> discord.Embed:
        gid       = self.canal.guild.id
        pista     = self.pistas_impostores.get(jugador.id, self.pista_generada)
        total_imp = len(self.impostores)
        complices = [j for j in self.impostores if j.id != jugador.id]
        modo      = self.config.modo_juego

        embed = discord.Embed(
            title=t("dm_impostor_title", gid),
            description=t("dm_impostor_desc", gid, hint=pista),
            color=discord.Color.from_rgb(180, 30, 30),
        )
        if (
            modo == ModoJuego.EXTENDIDO
            and total_imp > 1
            and getattr(self.config, "conocer_complices", True)
        ):
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

    # ── DM variante Danza Caos — 100% idéntico a tripulante normal ───────────
    def _build_dm_amigos_ebrios(self, jugador: discord.Member) -> discord.Embed:
        dp = self.pokemons_ebrios.get(jugador.id)
        if not dp:
            return discord.Embed(title="Error", description="No se asignó Pokémon.")
        return self._build_dm_tripulante(dp)

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
        self.caos_todos_impostores = False
        self.objetivo_humano  = None
        self.pokemons_ebrios.clear()
        self._variante_ronda = CaosVariante.NORMAL
        self.rondas_sin_expulsion   = 0
        self.pista_publica_revelada = False
        self.empates_consecutivos   = 0

        modo = self.config.modo_juego

        # Caos: elegir variante aleatoriamente entre las 7 permitidas ─────────
        if modo == ModoJuego.CAOS:
            if self.config.caos_variante not in (CaosVariante.NORMAL, "normal"):
                variante_elegida = self.config.caos_variante
                self.config.caos_variante = CaosVariante.NORMAL  # Resetear tras consumir
            else:
                variante_elegida = self._sortear_variante_caos()
            self._variante_ronda = variante_elegida   # usada por _calcular_impostores
            if variante_elegida in (CaosVariante.AMIGOS_BORRACHOS, CaosVariante.DANZA_CAOS):
                return await self._arrancar_amigos_ebrios()
            if variante_elegida == CaosVariante.OBJETIVO_HUMANO:
                return await self._arrancar_caos_jugador()
            # Las demás variantes (CERO_IMPOSTORES, UN_IMPOSTOR, CINCUENTA_PORCIENTO,
            # SETENTA_Y_CINCO, TODOS_IMPOSTORES) continúan con el flujo estándar

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
        elif cant_imp >= total:
            self.caos_todos_impostores = True
            self.impostores          = self.jugadores.copy()
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
        impostores_ids = {imp.id for imp in self.impostores}

        async def _enviar_dm(j: discord.Member):
            try:
                if j.id in impostores_ids:
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

    # ── Subrutina: Caos Jugador (Objetivo Humano) ──────────────────────────────
    async def _arrancar_caos_jugador(self) -> bool:
        # 1. El objetivo humano puede ser cualquier jugador elegido al azar
        self.objetivo_humano = random.choice(self.jugadores)

        # 2. El o los impostores se eligen de entre los demás jugadores (NUNCA el objetivo humano)
        candidatos_impostor = [j for j in self.jugadores if j.id != self.objetivo_humano.id]
        calc_imp = self._calcular_impostores(len(self.jugadores))
        num_imp = max(1, min(len(candidatos_impostor), calc_imp))
        self.impostores = random.sample(candidatos_impostor, k=num_imp)
        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        gid = self.canal.guild.id
        # Extraer letra inicial y letra final de forma segura (solo letras A-Z, sin números ni emojis)
        base_name = getattr(self.objetivo_humano, "global_name", None) or self.objetivo_humano.display_name
        nombre_limpio = [c.upper() for c in base_name if c.isalpha() and c.isascii()]
        if nombre_limpio:
            primera_letra = nombre_limpio[0]
            ultima_letra = nombre_limpio[-1]
        else:
            primera_letra = "A"
            ultima_letra = "Z"

        # Generar pista ambigua (empieza con / termina con) para camuflar al impostor
        for imp in self.impostores:
            if random.choice([True, False]):
                pista = t("hint_text_letter", gid, v=primera_letra)
            else:
                pista = t("hint_text_ends_letter", gid, v=ultima_letra)
            self.pistas_impostores[imp.id] = pista

        if self.impostores:
            self.pista_generada = self.pistas_impostores.get(self.impostores[0].id, "")

        dm_fallidos: list[discord.Member] = []
        impostores_ids = {imp.id for imp in self.impostores}

        async def _enviar_dm_humano(jugador: discord.Member):
            try:
                if jugador.id in impostores_ids:
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
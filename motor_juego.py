"""
motor_juego.py — Núcleo lógico de PokeImpostor
"""
from __future__ import annotations

import random
import discord
from dataclasses import dataclass, field
from enum import Enum

from api import obtener_datos_completos_pokemon
from i18n import t


# ═══════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class ModoJuego(str, Enum):
    CLASICO      = "clasico"
    EXTENDIDO    = "extendido"
    CAOS         = "caos"
    CAOS_JUGADOR = "caos_jugador"  # un jugador ES el objetivo en lugar de un Pokémon


class Ventaja(str, Enum):
    ALEATORIO    = "aleatorio"
    LETRA        = "letra"
    STAT_ALTA    = "stat_alta"
    STAT_BAJA    = "stat_baja"
    HUEVO        = "huevo"
    TIPO         = "tipo"
    HABITAT      = "habitat"
    RANGO_REGION = "rango_region"
    HABILIDAD    = "habilidad"


class DuracionDebate(int, Enum):
    SIN_LIMITE = 0
    DOS_MIN    = 120
    CINCO_MIN  = 300
    DIEZ_MIN   = 600


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConfigPartida:
    regiones:        list[str]      = field(default_factory=lambda: ["todas"])
    modo_juego:      ModoJuego      = ModoJuego.CLASICO
    ventaja:         Ventaja        = Ventaja.ALEATORIO
    duracion_debate: DuracionDebate = DuracionDebate.SIN_LIMITE
    # Modificador exclusivo del modo CAOS: cada jugador recibe su propio Pokémon
    caos_ebrios:     bool           = False


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

        # fix: cada impostor tiene su propia pista
        # { jugador.id: texto_de_pista }
        self.pistas_impostores: dict[int, str] = {}
        # para /impver y compatibilidad — pista del primer impostor o única
        self.pista_generada: str = ""

        # modo CAOS_JUGADOR: quién es el "objetivo" (jugador que los demás describen)
        self.objetivo_humano: discord.Member | None = None

        # modo Ebrios (CAOS + caos_ebrios=True): cada tripulante tiene su propio Pokémon
        # { jugador.id: dict_pokemon }
        self.pokemons_ebrios: dict[int, dict] = {}

        self._pokemon_usados:   set[int] = set()
        self._partidas_activas: dict     = partidas_activas

    # ── helpers ───────────────────────────────────────────────────────────────
    def _t(self, key: str, **kwargs) -> str:
        return t(key, self.canal.guild.id, **kwargs)

    def limpiar_memoria(self) -> None:
        self._partidas_activas.pop(self.canal.id, None)

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
        opciones: dict[Ventaja, str] = {
            Ventaja.LETRA:        t("hint_text_letter",    gid, v=dp["nombre"][0]),
            Ventaja.STAT_ALTA:    t("hint_text_stat_high", gid, v=dp["stat_mayor"]),
            Ventaja.STAT_BAJA:    t("hint_text_stat_low",  gid, v=dp["stat_menor"]),
            Ventaja.HUEVO:        t("hint_text_egg",       gid, v=", ".join(dp["grupos_huevo"])),
            Ventaja.TIPO:         t("hint_text_type",      gid, v=", ".join(dp["tipos"])),
            Ventaja.HABITAT:      t("hint_text_habitat",   gid, v=dp["habitat"]),
            Ventaja.RANGO_REGION: t("hint_text_region",    gid, v=dp["gen"]),
            Ventaja.HABILIDAD:    t("hint_text_ability",   gid, v=random.choice(dp["habilidades"])),
        }

        if self.config.ventaja != Ventaja.ALEATORIO:
            return opciones.get(self.config.ventaja, opciones[Ventaja.TIPO])

        # aleatorio: evitar repetir si hay varias pistas disponibles
        if excluir:
            disponibles = [v for k, v in opciones.items() if v not in excluir]
            if disponibles:
                return random.choice(disponibles)
        return random.choice(list(opciones.values()))

    # ── cantidad de impostores ─────────────────────────────────────────────
    def _calcular_impostores(self, total: int) -> int:
        modo = self.config.modo_juego
        if modo == ModoJuego.CLASICO:        return 1
        if modo == ModoJuego.EXTENDIDO:      return min(max(1, total // 3), total - 1)
        if modo == ModoJuego.CAOS:           return random.randint(0, total)
        if modo == ModoJuego.CAOS_JUGADOR:   return 1
        return 1

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
                name=t("dm_impostor_accomplices_title", gid, count=total_imp),
                value=t("dm_impostor_accomplices_value", gid, names=nombres),
                inline=False,
            )
        elif modo == ModoJuego.CAOS:
            embed.add_field(
                name=t("dm_impostor_caos_title", gid),
                value=t("dm_impostor_caos_value", gid, count=total_imp),
                inline=False,
            )
        embed.set_footer(text=t("dm_impostor_footer", gid))
        return embed

    # ── DM tripulante ────────────────────────────────────────────────────────
    def _build_dm_tripulante(self, dp: dict) -> discord.Embed:
        gid = self.canal.guild.id
        embed = discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_crew_desc", gid, name=dp["nombre"], types=" / ".join(dp["tipos"])),
            color=discord.Color.from_rgb(30, 160, 80),
        )
        embed.set_image(url=dp["sprite"])
        embed.set_footer(text=t("dm_crew_footer", gid))
        return embed

    # ── DM modo CAOS_JUGADOR ──────────────────────────────────────────────────
    def _build_dm_caos_jugador_detective(self, objetivo: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        pista = self.pistas_impostores.get(
            list(self.pistas_impostores.keys())[0] if self.pistas_impostores else 0, ""
        )
        return discord.Embed(
            title=t("dm_caos_jugador_detective_title", gid),
            description=t("dm_caos_jugador_detective_desc", gid, hint=pista),
            color=discord.Color.from_rgb(180, 30, 30),
        ).set_footer(text=t("dm_impostor_footer", gid))

    def _build_dm_caos_jugador_tripulante(self, objetivo: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        return discord.Embed(
            title=t("dm_caos_jugador_crew_title", gid),
            description=t("dm_caos_jugador_crew_desc", gid, target=f"**{objetivo.display_name}**"),
            color=discord.Color.from_rgb(30, 160, 80),
        ).set_image(url=objetivo.display_avatar.url)

    # ── DM modo Ebrios (CAOS + caos_ebrios) ──────────────────────────────────
    def _build_dm_amigos_ebrios(self, jugador: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        dp  = self.pokemons_ebrios.get(jugador.id)
        if not dp:
            return discord.Embed(title="Error", description="No se asignó Pokémon.")
        return discord.Embed(
            title=t("dm_ebrios_title", gid),
            description=t("dm_ebrios_desc", gid, name=dp["nombre"], types=" / ".join(dp["tipos"])),
            color=discord.Color.from_rgb(120, 80, 200),
        ).set_image(url=dp["sprite"]).set_footer(text=t("dm_ebrios_footer", gid))

    # ─────────────────────────────────────────────────────────────────────────
    #  ARRANCAR RONDA — punto de entrada principal
    # ─────────────────────────────────────────────────────────────────────────
    async def arrancar_ronda(self) -> bool:
        self.impostores.clear()
        self.jugadores_iniciales.clear()
        self.impostores_iniciales.clear()
        self.pistas_impostores.clear()
        self.pista_generada   = ""
        self.caos_sin_impostores = False
        self.objetivo_humano  = None
        self.pokemons_ebrios.clear()

        modo = self.config.modo_juego

        # ── Modo CAOS con modificador Ebrios — todos reciben pokémon distintos ─
        if modo == ModoJuego.CAOS and self.config.caos_ebrios:
            return await self._arrancar_amigos_ebrios()

        # ── Modo CAOS_JUGADOR — un jugador es el objetivo ─────────────────────
        if modo == ModoJuego.CAOS_JUGADOR:
            return await self._arrancar_caos_jugador()

        # ── Modos normales (Clásico / Extendido / Caos) ───────────────────────
        id_elegido         = self._elegir_id_pokemon()
        self.datos_pokemon = await obtener_datos_completos_pokemon(id_elegido)
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

        # enviar DMs
        dm_fallidos: list[discord.Member] = []
        for jugador in self.jugadores:
            try:
                if jugador in self.impostores:
                    await jugador.send(embed=self._build_dm_impostor(jugador))
                else:
                    await jugador.send(embed=self._build_dm_tripulante(self.datos_pokemon))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True

    # ── Subrutina: Amigos Ebrios ──────────────────────────────────────────────
    async def _arrancar_amigos_ebrios(self) -> bool:
        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = []

        # asignar un Pokémon distinto a cada jugador
        dm_fallidos: list[discord.Member] = []
        for jugador in self.jugadores:
            id_pk  = self._elegir_id_pokemon()
            dp     = await obtener_datos_completos_pokemon(id_pk)
            if dp is None:
                await self.canal.send(self._t("api_error"))
                return False
            self.pokemons_ebrios[jugador.id] = dp
            if jugador == self.jugadores[0]:
                self.datos_pokemon = dp  # para la pantalla final

            try:
                await jugador.send(embed=self._build_dm_amigos_ebrios(jugador))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True

    # ── Subrutina: Caos Jugador ────────────────────────────────────────────────
    async def _arrancar_caos_jugador(self) -> bool:
        # elegir un jugador al azar como "objetivo" (el que los demás describen)
        self.objetivo_humano = random.choice(self.jugadores)
        # el "detective" (impostor) es quien intenta adivinar
        resto = [j for j in self.jugadores if j != self.objetivo_humano]
        detective = random.choice(resto)
        self.impostores = [detective]

        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        # la "pista" del detective: un dato del perfil del objetivo
        # usamos una pista generada aleatoriamente sobre el jugador objetivo
        gid = self.canal.guild.id
        pistas_sobre_objetivo = [
            t("caos_jugador_hint_avatar",  gid, target=self.objetivo_humano.display_name),
            t("caos_jugador_hint_name",    gid, target=self.objetivo_humano.display_name[0]),
            t("caos_jugador_hint_join",    gid, target=self.objetivo_humano.display_name),
        ]
        pista_detective = random.choice(pistas_sobre_objetivo)
        self.pistas_impostores[detective.id] = pista_detective
        self.pista_generada = pista_detective

        dm_fallidos: list[discord.Member] = []
        for jugador in self.jugadores:
            try:
                if jugador == detective:
                    await jugador.send(embed=self._build_dm_caos_jugador_detective(self.objetivo_humano))
                else:
                    await jugador.send(embed=self._build_dm_caos_jugador_tripulante(self.objetivo_humano))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True
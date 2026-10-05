"""
vistas/config.py — Panel de configuración (solo admin, ephemeral).

Permite elegir modo de juego, tipo de pista, regiones de Pokémon y,
si el modo es CAOS, la variante exclusiva (radio buttons).
"""
from __future__ import annotations

import discord
from motor_juego import Partida, ModoJuego, CaosVariante, Ventaja
from i18n import t

from .common import (
    TIMEOUT_LOBBY,
    gid,
    build_embed_config,
    build_embed_ronda,
    NOMBRE_ROL_HOST,
    es_anfitrion_o_admin,
)


class PanelConfiguracion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        g = gid(partida)
        # Evita doble-click en "Iniciar Ronda" desde este mismo panel
        self._iniciado = False

        self._add_select_modo(g)
        self._add_select_pista(g)
        self._add_select_region(g)
        self._add_select_rondas(g)
        self._add_btn_iniciar(g)

    # ── Select: modo de juego ────────────────────────────────────────────────
    def _add_select_modo(self, g: int):
        sel = discord.ui.Select(
            placeholder=t("sel_gamemode", g),
            options=[
                discord.SelectOption(label=t("mode_classic",  g), value=ModoJuego.CLASICO,   description=t("mode_classic_desc",  g)),
                discord.SelectOption(label=t("mode_extended", g), value=ModoJuego.EXTENDIDO, description=t("mode_extended_desc", g)),
                discord.SelectOption(label=t("mode_caos",     g), value=ModoJuego.CAOS,      description=t("mode_caos_desc",     g)),
            ], row=0,
        )
        sel.callback = self._set_modo
        self.add_item(sel)

    # ── Select: tipo de pista para el impostor ──────────────────────────────
    def _add_select_pista(self, g: int):
        sel = discord.ui.Select(
            placeholder=t("sel_hint", g),
            options=[
                discord.SelectOption(label=t("hint_random",      g), value=Ventaja.ALEATORIO,    description=t("hint_random_desc", g)),
                discord.SelectOption(label=t("hint_letter",      g), value=Ventaja.LETRA),
                discord.SelectOption(label=t("hint_type",        g), value=Ventaja.TIPO),
                discord.SelectOption(label=t("hint_region",      g), value=Ventaja.RANGO_REGION),
                discord.SelectOption(label=t("hint_ability",     g), value=Ventaja.HABILIDAD),
                discord.SelectOption(label=t("hint_stats",       g), value=Ventaja.ESTADISTICAS, description=t("hint_stats_desc", g)),
                discord.SelectOption(label=t("hint_profile",     g), value=Ventaja.PERFIL,        description=t("hint_profile_desc", g)),
                discord.SelectOption(label=t("hint_weakness",    g), value=Ventaja.DEBILIDADES,   description=t("hint_weakness_desc", g)),
                discord.SelectOption(label=t("hint_pokedex",     g), value=Ventaja.POKEDEX,       description=t("hint_pokedex_desc", g)),
            ], row=1,
        )
        sel.callback = self._set_pista
        self.add_item(sel)

    # ── Select: regiones de Pokémon ──────────────────────────────────────────
    def _add_select_region(self, g: int):
        sel = discord.ui.Select(
            placeholder=t("sel_regions", g), min_values=1, max_values=10,
            options=[
                discord.SelectOption(label=t("region_all",  g), value="todas"),
                discord.SelectOption(label=t("region_gen1", g), value="gen1"),
                discord.SelectOption(label=t("region_gen2", g), value="gen2"),
                discord.SelectOption(label=t("region_gen3", g), value="gen3"),
                discord.SelectOption(label=t("region_gen4", g), value="gen4"),
                discord.SelectOption(label=t("region_gen5", g), value="gen5"),
                discord.SelectOption(label=t("region_gen6", g), value="gen6"),
                discord.SelectOption(label=t("region_gen7", g), value="gen7"),
                discord.SelectOption(label=t("region_gen8", g), value="gen8"),
                discord.SelectOption(label=t("region_gen9", g), value="gen9"),
            ], row=2,
        )
        sel.callback = self._set_region
        self.add_item(sel)

    # ── Select: límite de rondas (Combo Box 1 a 9) ───────────────────────────
    def _add_select_rondas(self, g: int):
        options = [
            discord.SelectOption(
                label=t("config_rounds_option", g, n=i),
                value=str(i),
                default=(i == self.partida.config.max_rondas),
                description=t("config_rounds_desc", g, n=i),
            )
            for i in range(1, 10)
        ]
        sel = discord.ui.Select(
            placeholder=t("sel_rounds", g),
            options=options,
            row=3,
        )
        sel.callback = self._set_rondas
        self.add_item(sel)

    def _add_btn_iniciar(self, g: int):
        btn = discord.ui.Button(label=t("btn_start_round", g), style=discord.ButtonStyle.primary, row=4)
        btn.callback = self._iniciar
        self.add_item(btn)

    async def _set_rondas(self, inter: discord.Interaction):
        self.partida.config.max_rondas = int(inter.data["values"][0])
        await inter.response.edit_message(embed=build_embed_config(self.partida), view=self)

    # ── Callbacks de los selects ─────────────────────────────────────────────
    async def _set_modo(self, inter: discord.Interaction):
        nuevo_modo = ModoJuego(inter.data["values"][0])
        self.partida.config.modo_juego = nuevo_modo
        await inter.response.edit_message(embed=build_embed_config(self.partida), view=self)

    async def _set_pista(self, inter: discord.Interaction):
        self.partida.config.ventaja = Ventaja(inter.data["values"][0])
        await inter.response.edit_message(embed=build_embed_config(self.partida))

    async def _set_region(self, inter: discord.Interaction):
        self.partida.config.regiones = inter.data["values"]
        await inter.response.edit_message(embed=build_embed_config(self.partida))

    # ── Iniciar ronda ─────────────────────────────────────────────────────────
    async def _iniciar(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=NOMBRE_ROL_HOST), ephemeral=True
            )

        # Lock: dos admins podrían tener cada uno su propio panel ephemeral
        # de configuración abierto y pulsar "Iniciar Ronda" casi a la vez.
        # Sin esto, ambos podrían pasar la validación y disparar
        # arrancar_ronda() dos veces (doble set de DMs, doble Pokémon, etc.)
        async with self.partida.lock:
            if getattr(self.partida, "_ronda_arrancando", False) or self._iniciado:
                return await inter.response.send_message(t("round_already_started", g), ephemeral=True)

            # SIEMPRE restaurar desde jugadores_iniciales si existen —
            # después de una ronda, jugadores puede estar vacío (todos
            # expulsados) o reducido (algunos expulsados), pero queremos
            # empezar la nueva ronda con todos los que participaron antes.
            if self.partida.jugadores_iniciales:
                self.partida.jugadores = self.partida.jugadores_iniciales.copy()

            if len(self.partida.jugadores) < 3:
                return await inter.response.send_message(t("min_players", g), ephemeral=True)

            self._iniciado = True
            self.partida._ronda_arrancando = True

            await inter.response.edit_message(content=t("config_saved", g), view=None, embed=None)

            try:
                exito = await self.partida.arrancar_ronda()
            finally:
                self.partida._ronda_arrancando = False

            if not exito:
                await inter.channel.send(t("api_error", g))
                return

        if self.partida.caos_sin_impostores:
            await inter.channel.send(embed=discord.Embed(
                title=t("caos_zero_title", g),
                description=t("caos_zero_desc", g),
                color=discord.Color.from_rgb(100, 0, 200),
            ))

        # Import diferido para evitar ciclo de imports
        from .debate import PanelDebate
        view_deb = PanelDebate(self.partida)
        msg = await inter.channel.send(embed=build_embed_ronda(self.partida), view=view_deb)
        view_deb.message = msg
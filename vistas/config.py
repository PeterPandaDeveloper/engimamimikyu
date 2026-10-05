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
        self._sel_modo = discord.ui.Select(
            placeholder=t("sel_gamemode", g),
            options=[
                discord.SelectOption(label=t("mode_classic",  g), value=ModoJuego.CLASICO,   description=t("mode_classic_desc",  g), default=(self.partida.config.modo_juego == ModoJuego.CLASICO)),
                discord.SelectOption(label=t("mode_extended", g), value=ModoJuego.EXTENDIDO, description=t("mode_extended_desc", g), default=(self.partida.config.modo_juego == ModoJuego.EXTENDIDO)),
                discord.SelectOption(label=t("mode_caos",     g), value=ModoJuego.CAOS,      description=t("mode_caos_desc",     g), default=(self.partida.config.modo_juego == ModoJuego.CAOS)),
            ], row=0,
        )
        self._sel_modo.callback = self._set_modo
        self.add_item(self._sel_modo)

    # ── Select: tipo de pista para el impostor ──────────────────────────────
    def _add_select_pista(self, g: int):
        pista_specs = [
            (Ventaja.ALEATORIO,    "hint_random",      "hint_random_desc"),
            (Ventaja.LETRA,        "hint_letter",      None),
            (Ventaja.TIPO,         "hint_type",        None),
            (Ventaja.RANGO_REGION, "hint_region",      None),
            (Ventaja.HABILIDAD,    "hint_ability",     None),
            (Ventaja.ESTADISTICAS, "hint_stats",       "hint_stats_desc"),
            (Ventaja.PERFIL,       "hint_profile",     "hint_profile_desc"),
            (Ventaja.DEBILIDADES,  "hint_weakness",    "hint_weakness_desc"),
            (Ventaja.POKEDEX,      "hint_pokedex",     "hint_pokedex_desc"),
        ]
        options = [
            discord.SelectOption(
                label=t(label_key, g),
                value=v,
                description=t(desc_key, g) if desc_key else None,
                default=(self.partida.config.ventaja == v),
            )
            for v, label_key, desc_key in pista_specs
        ]
        self._sel_pista = discord.ui.Select(
            placeholder=t("sel_hint", g),
            options=options,
            row=1,
        )
        self._sel_pista.callback = self._set_pista
        self.add_item(self._sel_pista)

    # ── Select: regiones de Pokémon ──────────────────────────────────────────
    def _add_select_region(self, g: int):
        region_specs = [
            ("todas", "region_all"),
            ("gen1",  "region_gen1"),
            ("gen2",  "region_gen2"),
            ("gen3",  "region_gen3"),
            ("gen4",  "region_gen4"),
            ("gen5",  "region_gen5"),
            ("gen6",  "region_gen6"),
            ("gen7",  "region_gen7"),
            ("gen8",  "region_gen8"),
            ("gen9",  "region_gen9"),
        ]
        options = [
            discord.SelectOption(
                label=t(label_key, g),
                value=val,
                default=(val in self.partida.config.regiones),
            )
            for val, label_key in region_specs
        ]
        self._sel_region = discord.ui.Select(
            placeholder=t("sel_regions", g), min_values=1, max_values=10,
            options=options, row=2,
        )
        self._sel_region.callback = self._set_region
        self.add_item(self._sel_region)

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
        self._sel_rondas = discord.ui.Select(
            placeholder=t("sel_rounds", g),
            options=options,
            row=3,
        )
        self._sel_rondas.callback = self._set_rondas
        self.add_item(self._sel_rondas)

    def _add_btn_iniciar(self, g: int):
        btn = discord.ui.Button(label=t("btn_start_round", g), style=discord.ButtonStyle.primary, row=4)
        btn.callback = self._iniciar
        self.add_item(btn)

    async def _set_rondas(self, inter: discord.Interaction):
        self.partida.config.max_rondas = int(inter.data["values"][0])
        for opt in self._sel_rondas.options:
            opt.default = (opt.value == str(self.partida.config.max_rondas))
        await inter.response.edit_message(embed=build_embed_config(self.partida), view=self)

    # ── Callbacks de los selects ─────────────────────────────────────────────
    async def _set_modo(self, inter: discord.Interaction):
        nuevo_modo = ModoJuego(inter.data["values"][0])
        self.partida.config.modo_juego = nuevo_modo
        for opt in self._sel_modo.options:
            opt.default = (opt.value == nuevo_modo.value)
        await inter.response.edit_message(embed=build_embed_config(self.partida), view=self)

    async def _set_pista(self, inter: discord.Interaction):
        nueva_ventaja = Ventaja(inter.data["values"][0])
        self.partida.config.ventaja = nueva_ventaja
        for opt in self._sel_pista.options:
            opt.default = (opt.value == nueva_ventaja.value)
        await inter.response.edit_message(embed=build_embed_config(self.partida), view=self)

    async def _set_region(self, inter: discord.Interaction):
        self.partida.config.regiones = inter.data["values"]
        for opt in self._sel_region.options:
            opt.default = (opt.value in self.partida.config.regiones)
        await inter.response.edit_message(embed=build_embed_config(self.partida), view=self)

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
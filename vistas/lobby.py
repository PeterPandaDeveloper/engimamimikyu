"""
vistas/lobby.py — Panel de inscripción (sala de espera).

Permite a los jugadores unirse/salir del lobby, y al admin abrir la
configuración o cancelar la partida antes de empezar.
"""
from __future__ import annotations

import discord
from motor_juego import Partida
from i18n import t

from .common import TIMEOUT_LOBBY, gid, build_embed_lobby, build_embed_config


class PanelInscripcion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        g = gid(partida)
        self._mk_btn(t("btn_join",   g), discord.ButtonStyle.success,   self._unirse,   0)
        self._mk_btn(t("btn_leave",  g), discord.ButtonStyle.secondary, self._salir,    0)
        self._mk_btn(t("btn_config", g), discord.ButtonStyle.primary,   self._config,   1)
        self._mk_btn(t("btn_cancel", g), discord.ButtonStyle.danger,    self._cancelar, 1)

    def _mk_btn(self, label, style, cb, row):
        b = discord.ui.Button(label=label, style=style, row=row)
        b.callback = cb
        self.add_item(b)

    async def on_timeout(self):
        self.partida.limpiar_memoria()

    async def _unirse(self, inter: discord.Interaction):
        g = inter.guild_id
        if inter.user in self.partida.jugadores:
            return await inter.response.send_message(t("lobby_already_in", g), ephemeral=True)
        self.partida.jugadores.append(inter.user)
        await inter.response.edit_message(embed=build_embed_lobby(self.partida))

    async def _salir(self, inter: discord.Interaction):
        g = inter.guild_id
        if inter.user not in self.partida.jugadores:
            return await inter.response.send_message(t("lobby_not_in", g), ephemeral=True)
        self.partida.jugadores.remove(inter.user)
        await inter.response.edit_message(embed=build_embed_lobby(self.partida))

    async def _config(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", g), ephemeral=True)
        # Import diferido para evitar import circular (config -> debate -> votacion -> final -> postronda -> config)
        from .config import PanelConfiguracion
        await inter.response.send_message(
            embed=build_embed_config(self.partida),
            view=PanelConfiguracion(self.partida),
            ephemeral=True,
        )

    async def _cancelar(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", g), ephemeral=True)
        self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(content=t("lobby_cancelled", g), embed=None, view=None)
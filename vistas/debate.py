"""
vistas/debate.py — Panel de debate.

Muestra el botón para que el admin abra la votación cuando el grupo
esté listo. No tiene límite de tiempo: el debate dura lo que el grupo
decida.
"""
from __future__ import annotations

import discord
from motor_juego import Partida
from i18n import t

from .common import TIMEOUT_DEBATE, gid


class PanelDebate(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_DEBATE)
        self.partida = partida
        g = gid(partida)

        btn_vote = discord.ui.Button(label=t("btn_open_vote", g), style=discord.ButtonStyle.danger, row=0)
        btn_vote.callback = self._abrir_votacion
        self.add_item(btn_vote)

    async def _abrir_votacion(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", g), ephemeral=True)

        self.stop()
        await inter.response.edit_message(view=None)

        # Import diferido para evitar ciclo de imports
        from .votacion import PanelVotacion
        await inter.channel.send(
            embed=discord.Embed(
                title=t("vote_title_open", g),
                description=t("vote_desc", g, current=0, total=len(self.partida.jugadores)),
                color=discord.Color.red(),
            ),
            view=PanelVotacion(self.partida),
        )
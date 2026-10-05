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

from .common import TIMEOUT_DEBATE, gid, NOMBRE_ROL_HOST, es_anfitrion_o_admin


class PanelDebate(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_DEBATE)
        self.partida = partida
        self._abierta = False
        g = gid(partida)

        btn_vote = discord.ui.Button(label=t("btn_open_vote", g), style=discord.ButtonStyle.danger, row=0)
        btn_vote.callback = self._abrir_votacion
        self.add_item(btn_vote)

    async def on_timeout(self):
        self.partida.limpiar_memoria()
        for child in self.children:
            child.disabled = True
        self.stop()
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def _abrir_votacion(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=NOMBRE_ROL_HOST), ephemeral=True
            )

        async with self.partida.lock:
            if self._abierta:
                return await inter.response.send_message(t("vote_already_closed", g), ephemeral=True)
            self._abierta = True

        self.stop()
        try:
            await inter.response.edit_message(view=None)
        except Exception:
            pass

        # Import diferido para evitar ciclo de imports
        from .votacion import PanelVotacion
        view_vot = PanelVotacion(self.partida)
        msg = await inter.channel.send(
            embed=discord.Embed(
                title=t("vote_title_open", g),
                description=t("vote_desc", g, current=0, total=len(self.partida.jugadores)),
                color=discord.Color.red(),
            ),
            view=view_vot,
        )
        view_vot.message = msg
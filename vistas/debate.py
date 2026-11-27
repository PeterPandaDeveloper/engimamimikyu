"""
vistas/debate.py — Panel de debate.

Muestra el botón para que el admin abra la votación cuando el grupo
esté listo. No tiene límite de tiempo: el debate dura lo que el grupo
decida.
"""
from __future__ import annotations

import discord
from motor_juego import Partida, ModoJuego, CaosVariante
from i18n import t

from .common import TIMEOUT_DEBATE, gid, NOMBRE_ROL_HOST, es_anfitrion_o_admin, obtener_nombre_rol_host


class PanelDebate(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_DEBATE)
        self.partida = partida
        self._abierta = False
        g = gid(partida)

        btn_vote = discord.ui.Button(label=t("btn_open_vote", g), style=discord.ButtonStyle.danger, row=0)
        btn_role = discord.ui.Button(label=t("btn_view_role", g), style=discord.ButtonStyle.secondary, row=0)
        btn_abort = discord.ui.Button(label=t("btn_abort_game", g), style=discord.ButtonStyle.secondary, row=1)
        btn_vote.callback = self._abrir_votacion
        btn_role.callback = self._ver_rol
        btn_abort.callback = self._cancelar_partida
        self.add_item(btn_vote)
        self.add_item(btn_role)
        self.add_item(btn_abort)

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

    async def _ver_rol(self, inter: discord.Interaction):
        from comandos_comunes import reenviar_rol_secreto
        g = inter.guild_id or 0
        _, msg_key = await reenviar_rol_secreto(self.partida, inter.user, g)
        await inter.response.send_message(t(msg_key, g), ephemeral=True)

    async def _cancelar_partida(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=obtener_nombre_rol_host(inter.guild)), ephemeral=True
            )
        async with self.partida.lock:
            if self._abierta:
                return await inter.response.send_message(t("vote_already_closed", g), ephemeral=True)
            self._abierta = True
            self.partida.terminada = True
            self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(content=t("match_aborted", g), embed=None, view=None)

    async def _abrir_votacion(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=obtener_nombre_rol_host(inter.guild)), ephemeral=True
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
            embed=view_vot.build_embed_votacion(),
            view=view_vot,
        )
        view_vot.message = msg
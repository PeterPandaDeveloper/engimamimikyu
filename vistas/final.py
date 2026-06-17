"""
vistas/final.py — Pantalla final de la partida y panel post-ronda
(revancha, cambiar configuración, terminar sesión).
"""
from __future__ import annotations

import discord
from motor_juego import Partida, ModoJuego, CaosVariante
from i18n import t

from .common import TIMEOUT_LOBBY, gid


async def mostrar_pantalla_final(partida: Partida, canal: discord.TextChannel, victoria_impostores: bool):
    g        = gid(partida)
    modo     = partida.config.modo_juego
    # Usar la variante efectiva de la ronda que acaba de terminar
    # (_variante_ronda), NO config.caos_variante (que puede haber cambiado
    # si el admin re-configuró entre rondas)
    variante = partida._variante_ronda
    es_danza_caos      = (modo == ModoJuego.CAOS and variante == CaosVariante.DANZA_CAOS)
    es_objetivo_humano = (modo == ModoJuego.CAOS and variante == CaosVariante.OBJETIVO_HUMANO)

    color_final  = discord.Color.from_rgb(50, 0, 0) if victoria_impostores else discord.Color.from_rgb(255, 203, 5)
    titulo_final = t("final_title_impostors_win", g) if victoria_impostores else t("final_title", g)
    embed = discord.Embed(title=titulo_final, color=color_final)

    if es_danza_caos:
        lines = []
        for j in partida.jugadores_iniciales:
            dp = partida.pokemons_ebrios.get(j.id)
            if dp:
                lines.append(f"• **{j.display_name}** → {dp['nombre']} ({' / '.join(dp['tipos'])})")
        embed.add_field(name=t("final_ebrios_field", g), value="\n".join(lines) or "—", inline=False)

    elif es_objetivo_humano:
        objetivo = partida.objetivo_humano
        if objetivo:
            embed.add_field(name=t("final_caos_jugador_field", g), value=f"👤 **{objetivo.display_name}**", inline=False)
            embed.set_image(url=objetivo.display_avatar.url)

    elif victoria_impostores:
        # Los impostores ganaron, pero igual revelamos el Pokémon —
        # es más satisfactorio para todos saber qué era.
        dp = partida.datos_pokemon
        if dp:
            embed.set_image(url=dp["sprite"])
            embed.add_field(
                name=t("final_pokemon_field", g),
                value=f"**{dp['nombre']}**\n{' / '.join(dp['tipos'])} · {dp['gen']}",
                inline=False,
            )

    else:
        dp = partida.datos_pokemon
        if dp:
            embed.set_image(url=dp["sprite"])
            embed.add_field(
                name=t("final_pokemon_field", g),
                value=f"**{dp['nombre']}**\n{' / '.join(dp['tipos'])} · {dp['gen']}",
                inline=False,
            )

    # ── Listas de impostores/tripulantes, distinguiendo descubiertos vs no ──
    descubiertos = [j for j in partida.impostores_iniciales if j not in partida.impostores]
    ocultos      = [j for j in partida.impostores_iniciales if j in partida.impostores]

    if victoria_impostores and ocultos:
        lineas_imp = []
        for j in descubiertos:
            lineas_imp.append(t("final_impostor_caught", g, name=j.display_name))
        for j in ocultos:
            lineas_imp.append(t("final_impostor_escaped", g, name=j.display_name))
        lista_imp = "\n".join(lineas_imp)
    else:
        lista_imp = "\n".join(f"🔪 {j.display_name}" for j in partida.impostores_iniciales)

    lista_trip = "\n".join(
        f"✅ {j.display_name}"
        for j in partida.jugadores_iniciales
        if j not in partida.impostores_iniciales
    )
    embed.add_field(name=t("final_impostors_field", g), value=lista_imp  or t("final_none_caos", g), inline=True)
    embed.add_field(name=t("final_crew_field",      g), value=lista_trip or "—",                     inline=True)
    embed.set_footer(text=t("final_footer", g, n=partida.ronda))
    await canal.send(embed=embed, view=PanelPostRonda(partida))


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL POST-RONDA
# ═══════════════════════════════════════════════════════════════════════════════

class PanelPostRonda(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        g = gid(partida)

        b1 = discord.ui.Button(label=t("btn_rematch",       g), style=discord.ButtonStyle.success, row=0)
        b2 = discord.ui.Button(label=t("btn_change_config", g), style=discord.ButtonStyle.primary,  row=0)
        b3 = discord.ui.Button(label=t("btn_end_session",   g), style=discord.ButtonStyle.danger,   row=0)
        b1.callback = self._revancha
        b2.callback = self._config
        b3.callback = self._cerrar
        self.add_item(b1); self.add_item(b2); self.add_item(b3)

    async def _revancha(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", g), ephemeral=True)

        async with self.partida.lock:
            if self.partida._ronda_arrancando:
                return await inter.response.send_message(t("round_already_started", g), ephemeral=True)

            await inter.response.edit_message(view=None)

            # restaurar todos los jugadores iniciales para la revancha
            self.partida.jugadores = self.partida.jugadores_iniciales.copy()
            self.partida.ronda    += 1

            self.partida._ronda_arrancando = True
            try:
                exito = await self.partida.arrancar_ronda()
            finally:
                self.partida._ronda_arrancando = False

            if not exito:
                return

        if self.partida.caos_sin_impostores:
            await inter.channel.send(embed=discord.Embed(
                title=t("caos_zero_title", g),
                description=t("caos_zero_desc", g),
                color=discord.Color.from_rgb(100, 0, 200),
            ))

        from .debate import PanelDebate
        from .common import build_embed_ronda
        await inter.channel.send(
            embed=build_embed_ronda(self.partida),
            view=PanelDebate(self.partida),
        )

    async def _config(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", g), ephemeral=True)

        # Restaurar jugadores desde jugadores_iniciales antes de abrir config
        # para que el botón "Iniciar Ronda" encuentre a los jugadores disponibles
        if self.partida.jugadores_iniciales:
            self.partida.jugadores = self.partida.jugadores_iniciales.copy()

        from .config import PanelConfiguracion
        from .common import build_embed_config
        await inter.response.send_message(
            embed=build_embed_config(self.partida),
            view=PanelConfiguracion(self.partida),
            ephemeral=True,
        )

    async def _cerrar(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", g), ephemeral=True)

        self.partida.jugadores = []
        self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(view=None)
        await inter.channel.send(embed=discord.Embed(
            title=t("session_closed_title", g),
            description=t("session_closed_desc", g),
            color=discord.Color.from_rgb(60, 60, 60),
        ))
"""
vistas/final.py — Pantalla final de la partida y panel post-ronda
(revancha, cambiar configuración, terminar sesión).
"""
from __future__ import annotations

import asyncio
import discord
from motor_juego import Partida, ModoJuego, CaosVariante
from i18n import t
from db import guardar_partida_async, consumir_partida_premium_async, verificar_estado_premium_async

from .common import TIMEOUT_LOBBY, gid, NOMBRE_ROL_HOST, es_anfitrion_o_admin, obtener_nombre_rol_host


async def mostrar_pantalla_final(partida: Partida, canal: discord.TextChannel, victoria_impostores: bool):
    partida.terminada = True
    g        = gid(partida)
    modo     = partida.config.modo_juego
    # Usar la variante efectiva de la ronda que acaba de terminar
    # (_variante_ronda), NO config.caos_variante (que puede haber cambiado
    # si el admin re-configuró entre rondas)
    variante = partida._variante_ronda
    es_danza_caos       = (modo == ModoJuego.CAOS and (variante in (CaosVariante.AMIGOS_BORRACHOS, CaosVariante.DANZA_CAOS) or bool(partida.pokemons_ebrios)))
    es_objetivo_humano  = (modo == ModoJuego.CAOS and (variante == CaosVariante.OBJETIVO_HUMANO or partida.objetivo_humano is not None))
    es_todos_impostores = (modo == ModoJuego.CAOS and (variante == CaosVariante.TODOS_IMPOSTORES or getattr(partida, "caos_todos_impostores", False)))
    es_cero_impostores  = (modo == ModoJuego.CAOS and (variante == CaosVariante.CERO_IMPOSTORES or getattr(partida, "caos_sin_impostores", False)) and not es_danza_caos and not es_todos_impostores)

    if es_todos_impostores:
        color_final  = discord.Color.magenta()
        titulo_final = t("final_title_todos_impostores", g)
        embed = discord.Embed(
            title=titulo_final,
            description=t("final_desc_todos_impostores", g),
            color=color_final,
        )
        dp = partida.datos_pokemon
        if dp:
            if dp.get("sprite"):
                embed.set_image(url=dp["sprite"])
            embed.add_field(
                name=t("final_pokemon_field", g),
                value=f"**{dp['nombre']}**\n{' / '.join(dp['tipos'])} · {dp['gen']}",
                inline=False,
            )
        lines = []
        for j in partida.jugadores_iniciales:
            p = partida.pistas_impostores.get(j.id, "—")
            lines.append(f"• **{j.display_name}** → 💡 *\"{p}\"*")
        embed.add_field(name=t("final_todos_impostores_field", g), value="\n".join(lines) or "—", inline=False)

    elif es_cero_impostores:
        color_final  = discord.Color.gold()
        titulo_final = t("final_title_cero_impostores", g)
        embed = discord.Embed(
            title=titulo_final,
            description=t("final_desc_cero_impostores", g),
            color=color_final,
        )
        dp = partida.datos_pokemon
        if dp:
            if dp.get("sprite"):
                embed.set_image(url=dp["sprite"])
            embed.add_field(
                name=t("final_pokemon_field", g),
                value=f"**{dp['nombre']}**\n{' / '.join(dp['tipos'])} · {dp['gen']}",
                inline=False,
            )
        lista_trip = "\n".join(f"✅ {j.display_name}" for j in partida.jugadores_iniciales)
        embed.add_field(name=t("final_impostors_field", g), value=t("final_none_caos", g), inline=True)
        embed.add_field(name=t("final_crew_field",      g), value=lista_trip or "—",                     inline=True)

    elif es_danza_caos:
        color_final  = discord.Color.from_rgb(255, 203, 5)
        titulo_final = t("final_title", g)
        embed = discord.Embed(title=titulo_final, color=color_final)
        lines = []
        for j in partida.jugadores_iniciales:
            dp = partida.pokemons_ebrios.get(j.id)
            if dp:
                lines.append(f"• **{j.display_name}** → {dp['nombre']} ({' / '.join(dp['tipos'])})")
        embed.add_field(name=t("final_ebrios_field", g), value="\n".join(lines) or "—", inline=False)
        lista_trip = "\n".join(f"✅ {j.display_name}" for j in partida.jugadores_iniciales)
        embed.add_field(name=t("final_impostors_field", g), value=t("final_none_caos", g), inline=True)
        embed.add_field(name=t("final_crew_field",      g), value=lista_trip or "—",                     inline=True)

    elif es_objetivo_humano:
        color_final  = discord.Color.from_rgb(50, 0, 0) if victoria_impostores else discord.Color.from_rgb(255, 203, 5)
        titulo_final = t("final_title_impostors_win", g) if victoria_impostores else t("final_title", g)
        embed = discord.Embed(title=titulo_final, color=color_final)
        objetivo = partida.objetivo_humano
        if objetivo:
            embed.add_field(name=t("final_caos_jugador_field", g), value=f"👤 **{objetivo.display_name}** (`@{objetivo.name}`)", inline=False)
            if getattr(objetivo, "display_avatar", None) and objetivo.display_avatar.url:
                embed.set_image(url=objetivo.display_avatar.url)
                embed.set_thumbnail(url=objetivo.display_avatar.url)
        impostores_iniciales_ids = {imp.id for imp in partida.impostores_iniciales}
        lista_imp = "\n".join(f"🔪 {j.display_name}" for j in partida.impostores_iniciales)
        lista_trip = "\n".join(f"✅ {j.display_name}" for j in partida.jugadores_iniciales if j.id not in impostores_iniciales_ids)
        embed.add_field(name=t("final_impostors_field", g), value=lista_imp or t("final_none_caos", g), inline=True)
        embed.add_field(name=t("final_crew_field",      g), value=lista_trip or "—", inline=True)

    else:
        # Clásico, Extendido, y Caos estándar (1 impostor, 50%, 75%)
        color_final  = discord.Color.from_rgb(50, 0, 0) if victoria_impostores else discord.Color.from_rgb(255, 203, 5)
        titulo_final = t("final_title_impostors_win", g) if victoria_impostores else t("final_title", g)
        embed = discord.Embed(title=titulo_final, color=color_final)
        dp = partida.datos_pokemon
        if dp:
            if dp.get("sprite"):
                embed.set_image(url=dp["sprite"])
            embed.add_field(
                name=t("final_pokemon_field", g),
                value=f"**{dp['nombre']}**\n{' / '.join(dp['tipos'])} · {dp['gen']}",
                inline=False,
            )
        impostores_actuales_ids = {imp.id for imp in partida.impostores}
        descubiertos = [j for j in partida.impostores_iniciales if j.id not in impostores_actuales_ids]
        ocultos      = [j for j in partida.impostores_iniciales if j.id in impostores_actuales_ids]

        if victoria_impostores and ocultos:
            lineas_imp = []
            for j in descubiertos:
                lineas_imp.append(t("final_impostor_caught", g, name=j.display_name))
            for j in ocultos:
                lineas_imp.append(t("final_impostor_escaped", g, name=j.display_name))
            lista_imp = "\n".join(lineas_imp)
        else:
            lista_imp = "\n".join(f"🔪 {j.display_name}" for j in partida.impostores_iniciales)

        impostores_iniciales_ids = {imp.id for imp in partida.impostores_iniciales}
        lista_trip = "\n".join(
            f"✅ {j.display_name}"
            for j in partida.jugadores_iniciales
            if j.id not in impostores_iniciales_ids
        )
        embed.add_field(name=t("final_impostors_field", g), value=lista_imp  or t("final_none_caos", g), inline=True)
        embed.add_field(name=t("final_crew_field",      g), value=lista_trip or "—",                     inline=True)
    # ── MODO TORNEO: Acumular puntos de la sesión ────────────────────────────
    ranking_t = []
    es_torneo_activo = getattr(partida, "es_torneo", False)
    if es_torneo_activo:
        partida.torneo_partida_num += 1
        impostores_ini_ids = {imp.id for imp in partida.impostores_iniciales}
        vivos_ids = {j.id for j in partida.jugadores}

        for j in partida.jugadores_iniciales:
            reg = partida.torneo_puntos.setdefault(
                j.id, {"nombre": j.display_name, "puntos": 0, "victorias": 0, "robos": 0}
            )
            es_imp = j.id in impostores_ini_ids
            if partida.caos_sin_impostores or getattr(partida, "caos_todos_impostores", False):
                gano_j = (j.id in vivos_ids)
                pts = 2 if gano_j else 0
            elif es_imp and victoria_impostores:
                gano_j = True
                pts = 2 if getattr(partida, "robo_ultima_oportunidad", False) else 3
                if getattr(partida, "robo_ultima_oportunidad", False):
                    reg["robos"] += 1
            elif not es_imp and not victoria_impostores:
                gano_j = True
                pts = 2
            else:
                gano_j = False
                pts = 0

            reg["puntos"] += pts
            if gano_j:
                reg["victorias"] += 1

        ranking_t = sorted(partida.torneo_puntos.values(), key=lambda x: (-x["puntos"], -x["victorias"]))
        medallas_t = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
        lineas_t = [
            f"{medallas_t[i] if i < len(medallas_t) else '▫️'} **{r['nombre']}** — **{r['puntos']} pts** ({r['victorias']}V)"
            for i, r in enumerate(ranking_t[:8])
        ]
        lbl_torneo_field = (
            f"🏆 Torneo en Curso — Partida {partida.torneo_partida_num} / {partida.torneo_max_partidas}"
            if get_lang(g) == "es" else
            f"🏆 Ongoing Tournament — Match {partida.torneo_partida_num} / {partida.torneo_max_partidas}"
        )
        embed.add_field(
            name=lbl_torneo_field,
            value="\n".join(lineas_t) or "—",
            inline=False,
        )

    embed.set_footer(text=t("final_footer", g, n=partida.ronda))
    post_view = PanelPostRonda(partida)
    msg = await canal.send(embed=embed, view=post_view)
    post_view.message = msg
    partida.mensaje_post_ronda = msg

    if es_torneo_activo and partida.torneo_partida_num >= partida.torneo_max_partidas:
        partida.es_torneo = False
        es_es = (get_lang(g) == "es")
        podio_lines = []
        iconos = ["🥇 **CAMPEÓN:**", "🥈 **2.º Lugar:**", "🥉 **3.er Lugar:**"] if es_es else ["🥇 **CHAMPION:**", "🥈 **2nd Place:**", "🥉 **3rd Place:**"]
        pts_label = "puntos" if es_es else "points"
        vics_label = "victorias" if es_es else "wins"
        for idx_p, r_p in enumerate(ranking_t[:3]):
            icono = iconos[idx_p]
            podio_lines.append(f"{icono} **{r_p['nombre']}** con **{r_p['puntos']} {pts_label}** ({r_p['victorias']} {vics_label})")
        titulo_p = f"👑 ¡TORNEO FINALIZADO ({partida.torneo_max_partidas} PARTIDAS)! 👑" if es_es else f"👑 TOURNAMENT CONCLUDED ({partida.torneo_max_partidas} MATCHES)! 👑"
        desc_p = (
            "¡La sesión de torneo ha concluido! Aquí está el podio oficial de entrenadores:\n\n" + "\n".join(podio_lines)
            if es_es else
            "The tournament session has concluded! Here is the official trainers' podium:\n\n" + "\n".join(podio_lines)
        )
        emb_podio = discord.Embed(
            title=titulo_p,
            description=desc_p,
            color=discord.Color.gold(),
        )
        emb_podio.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await canal.send(embed=emb_podio)

    # ── Guardar datos de la partida en DuckDB (asíncrono en segundo plano) ──
    # Si la partida contenía bots fantasma (DummyMember de depuración), no ensuciamos
    # la base de datos de producción ni consumimos cargas VIP del servidor.
    hay_dummies = any(getattr(j, "es_dummy", False) for j in partida.jugadores_iniciales)
    if not hay_dummies:
        try:
            jugadores_data = []
            impostores_iniciales_ids = {imp.id for imp in partida.impostores_iniciales}
            jugadores_actuales_ids = {j.id for j in partida.jugadores}
            for j in partida.jugadores_iniciales:
                es_imp = j.id in impostores_iniciales_ids
                es_obj = bool(partida.objetivo_humano and (partida.objetivo_humano.id == j.id))
                if es_imp:
                    rol = "impostor"
                elif es_obj:
                    rol = "objetivo"
                else:
                    rol = "tripulante"

                expulsado = (j.id not in jugadores_actuales_ids)
                if partida.caos_sin_impostores:
                    # En Caos sin impostores (0 Impostores / Amigos Borrachos), ganan los tripulantes que sobrevivieron a la paranoia
                    gano = not expulsado
                elif getattr(partida, "caos_todos_impostores", False):
                    # En Caos 100% impostores, los que sobrevivieron a la paranoia ganan y el expulsado pierde
                    gano = not expulsado
                else:
                    gano = (es_imp and victoria_impostores) or (not es_imp and not victoria_impostores)

                jugadores_data.append({
                    "user_id": j.id,
                    "user_name": j.display_name,
                    "rol": rol,
                    "gano": gano,
                    "expulsado": expulsado,
                })

            modo_val = modo.value if hasattr(modo, "value") else str(modo)
            var_val = variante.value if (variante and hasattr(variante, "value")) else (str(variante) if variante else None)
            pk_id = partida.datos_pokemon.get("id") if partida.datos_pokemon else None
            pk_nom = partida.datos_pokemon.get("nombre") if partida.datos_pokemon else None
            pk_tipos = " / ".join(partida.datos_pokemon.get("tipos", [])) if partida.datos_pokemon else None

            asyncio.create_task(
                guardar_partida_async(
                    guild_id=g,
                    canal_id=canal.id,
                    modo=modo_val,
                    variante=var_val,
                    rondas=partida.ronda,
                    pokemon_id=pk_id,
                    pokemon_nombre=pk_nom,
                    pokemon_tipos=pk_tipos,
                    victoria_impostores=victoria_impostores,
                    caos_sin_impostores=partida.caos_sin_impostores,
                    jugadores_data=jugadores_data,
                )
            )

            # Descontar una carga si el servidor funciona por partidas de Top.gg
            if canal.guild:
                asyncio.create_task(consumir_partida_premium_async(canal.guild.id))
        except Exception as e:
            print(f"⚠️ [DuckDB] No se pudo encolar el guardado de la partida: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL POST-RONDA
# ═══════════════════════════════════════════════════════════════════════════════

class PanelPostRonda(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        g = gid(partida)

        lbl_rematch = t("btn_rematch", g)
        if getattr(partida, "es_torneo", False):
            siguiente_num = partida.torneo_partida_num + 1
            if siguiente_num <= partida.torneo_max_partidas:
                lbl_rematch = f"⏭️ Siguiente Partida ({siguiente_num}/{partida.torneo_max_partidas})" if get_lang(g) == "es" else f"⏭️ Next Match ({siguiente_num}/{partida.torneo_max_partidas})"

        b1 = discord.ui.Button(label=lbl_rematch,            style=discord.ButtonStyle.success, row=0)
        b2 = discord.ui.Button(label=t("btn_change_config", g), style=discord.ButtonStyle.primary,  row=0)
        b3 = discord.ui.Button(label=t("btn_end_session",   g), style=discord.ButtonStyle.danger,   row=0)
        b1.callback = self._revancha
        b2.callback = self._config
        b3.callback = self._cerrar
        self.add_item(b1); self.add_item(b2); self.add_item(b3)

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

    async def _revancha(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=obtener_nombre_rol_host(inter.guild)), ephemeral=True
            )

        async with self.partida.lock:
            if self.partida._ronda_arrancando:
                return await inter.response.send_message(t("round_already_started", g), ephemeral=True)

            if len(self.partida.jugadores_iniciales) < 3:
                return await inter.response.send_message(t("min_players", g), ephemeral=True)

            # restaurar todos los jugadores iniciales para la revancha
            self.partida.jugadores = self.partida.jugadores_iniciales.copy()
            self.partida.ronda = 1
            self.partida.terminada = False

            # Verificar si el servidor aún tiene estado premium para modos especiales
            if self.partida.config.modo_juego != ModoJuego.CLASICO and g:
                estado = await verificar_estado_premium_async(g)
                if not estado["es_premium"]:
                    self.partida.config.modo_juego = ModoJuego.CLASICO

            self.partida._ronda_arrancando = True
            self.partida.mensaje_post_ronda = None
            await inter.response.edit_message(view=None)
            try:
                exito = await self.partida.arrancar_ronda()
            finally:
                self.partida._ronda_arrancando = False

            if not exito:
                await inter.channel.send(t("api_error", g))
                return

        from .debate import PanelDebate
        from .common import build_embed_ronda
        view_deb = PanelDebate(self.partida)
        msg = await inter.channel.send(
            embed=build_embed_ronda(self.partida),
            view=view_deb,
        )
        view_deb.message = msg

    async def _config(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=obtener_nombre_rol_host(inter.guild)), ephemeral=True
            )

        # Restaurar jugadores desde jugadores_iniciales antes de abrir config
        # para que el botón "Iniciar Ronda" encuentre a los jugadores disponibles
        if self.partida.jugadores_iniciales:
            self.partida.jugadores = self.partida.jugadores_iniciales.copy()

        from .config import PanelConfiguracion, PanelConfiguracionTorneo
        from .common import build_embed_config
        vista_cfg = PanelConfiguracionTorneo(self.partida) if getattr(self.partida, "es_torneo", False) else PanelConfiguracion(self.partida)
        await inter.response.send_message(
            embed=build_embed_config(self.partida),
            view=vista_cfg,
            ephemeral=True,
        )

    async def _cerrar(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=obtener_nombre_rol_host(inter.guild)), ephemeral=True
            )

        self.partida.jugadores = []
        self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(view=None)
        await inter.channel.send(embed=discord.Embed(
            title=t("session_closed_title", g),
            description=t("session_closed_desc", g),
            color=discord.Color.from_rgb(60, 60, 60),
        ))
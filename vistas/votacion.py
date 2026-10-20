"""
vistas/votacion.py — Panel de votación y resolución de resultados.

Reglas consolidadas (0 Spoilers):
- Todos los modos usan exactamente 1 voto por jugador (max_values=1).
- Los empates anulan la votación y avanzan la ronda sumando `empates_consecutivos`.
- Solo si se superan 3 empates seguidos (> 3, es decir, al 4.º empate consecutivo)
  en Extendido o Caos se activa la expulsión masiva.
- En Modo Caos NO hay instant-win por paridad ni fin prematuro en 100% impostores:
  la partida dura hasta expulsar a todos los impostores reales o agotar rondas/jugadores.
"""
from __future__ import annotations

import asyncio
import discord
from motor_juego import Partida, ModoJuego
from i18n import t, get_lang

from .common import (
    TIMEOUT_VOTACION,
    gid,
    VOTO_NULO_ID,
    es_anfitrion_o_admin,
    obtener_nombre_rol_host,
)
from .debate import PanelDebate


class PanelVotacion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_VOTACION)
        self.partida         = partida
        self.votos_emitidos: set[int]            = set()
        self.votos_urna:     dict[str, set[int]] = {}
        self._resultados_en_proceso: bool = False
        g = gid(partida)

        # Límite de Discord: máximo 25 opciones por Select (hasta 24 jugadores + 1 Voto Nulo)
        opciones = [
            discord.SelectOption(label=j.display_name, value=str(j.id))
            for j in partida.jugadores[:24]
        ]

        opciones.append(discord.SelectOption(
            label=t("vote_null_label", g),
            value=VOTO_NULO_ID,
            description=t("vote_null_desc", g),
            emoji="⚪",
        ))

        # Siempre 1 voto por jugador en todos los modos (0 Spoilers y balance)
        sel = discord.ui.Select(
            placeholder=t("vote_placeholder", g),
            min_values=1,
            max_values=1,
            options=opciones,
            row=0,
        )
        sel.callback = self._registrar_voto
        self.add_item(sel)
        self.sel_votos = sel

        btn_forzar = discord.ui.Button(label=t("btn_force_close", g), style=discord.ButtonStyle.secondary, row=1)
        btn_forzar.callback = self._forzar_cierre
        self.add_item(btn_forzar)

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

    # ─────────────────────────────────────────────────────────────────────────
    #  REGISTRO DE VOTOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _registrar_voto(self, inter: discord.Interaction):
        g = inter.guild_id

        async with self.partida.lock:
            if not any(j.id == inter.user.id for j in self.partida.jugadores):
                return await inter.response.send_message(t("vote_only_players", g), ephemeral=True)
            if inter.user.id in self.votos_emitidos:
                return await inter.response.send_message(t("vote_already_voted", g), ephemeral=True)

            self.votos_emitidos.add(inter.user.id)

            valores = inter.data.get("values", self.sel_votos.values if hasattr(self, "sel_votos") else [])
            if VOTO_NULO_ID not in valores:
                for acusado_id in valores:
                    self.votos_urna.setdefault(acusado_id, set()).add(inter.user.id)

            # ── AUTO-VOTO DE BOTS FANTASMA (MODO DEBUG) ──
            for j in self.partida.jugadores:
                if getattr(j, "es_dummy", False) and j.id not in self.votos_emitidos:
                    self.votos_emitidos.add(j.id)
                    if VOTO_NULO_ID not in valores:
                        for acusado_id in valores:
                            self.votos_urna.setdefault(acusado_id, set()).add(j.id)

            total  = len(self.partida.jugadores)
            actual = len(self.votos_emitidos)
            cerrar_ahora = (actual == total and not self._resultados_en_proceso)
            if cerrar_ahora:
                self._resultados_en_proceso = True

        await inter.response.send_message(t("vote_registered", g), ephemeral=True)
        await inter.message.edit(embed=discord.Embed(
            title=t("vote_title_open", g),
            description=t("vote_desc", g, current=actual, total=total),
            color=discord.Color.red(),
        ))

        if cerrar_ahora:
            await self._mostrar_resultados(inter.channel, inter.message)

    async def _forzar_cierre(self, inter: discord.Interaction):
        g = inter.guild_id
        if not es_anfitrion_o_admin(inter.user, inter.guild):
            return await inter.response.send_message(
                t("only_host_or_admin", g, role=obtener_nombre_rol_host(inter.guild)), ephemeral=True
            )

        async with self.partida.lock:
            if self._resultados_en_proceso:
                return await inter.response.send_message(t("vote_already_closed", g), ephemeral=True)
            self._resultados_en_proceso = True
            actual = len(self.votos_emitidos)
            total  = len(self.partida.jugadores)

        await inter.response.send_message(t("vote_force_closed", g, current=actual, total=total))
        await self._mostrar_resultados(inter.channel, inter.message)

    # ─────────────────────────────────────────────────────────────────────────
    #  RESOLUCIÓN DE RESULTADOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _mostrar_resultados(self, canal: discord.TextChannel, mensaje: discord.Message):
        g = gid(self.partida)
        self.clear_items()
        self.stop()
        try:
            await mensaje.edit(view=None)
        except Exception:
            pass

        conteo = {uid: len(v) for uid, v in self.votos_urna.items()}

        desglose_lines: list[str] = []
        if conteo:
            for uid_str, votos in sorted(conteo.items(), key=lambda x: -x[1]):
                miembro = discord.utils.get(self.partida.jugadores_iniciales, id=int(uid_str))
                nombre  = miembro.display_name if miembro else f"ID:{uid_str}"
                barra   = "█" * votos
                desglose_lines.append(f"`{barra:<10}` " + t("results_vote_field", g, votes=votos, name=nombre))

        await canal.send(embed=discord.Embed(
            title=t("results_tally_title", g),
            description="\n".join(desglose_lines) or t("results_no_votes", g),
            color=discord.Color.orange(),
        ))

        if not conteo:
            await canal.send(t("results_nobody_voted", g))
            self.partida.rondas_sin_expulsion += 1
            return await self._siguiente_ronda(canal)

        max_votos  = max(conteo.values())
        candidatos = [k for k, v in conteo.items() if v == max_votos]

        if len(candidatos) > 1:
            return await self._resolver_empate(canal, candidatos)

        return await self._resolver_expulsion_unica(canal, candidatos[0])

    # ── Empate (Anula votación; solo expulsa masivamente si supera 3 empates seguidos) ──
    async def _resolver_empate(self, canal: discord.TextChannel, candidatos: list[str]):
        g    = gid(self.partida)
        modo = self.partida.config.modo_juego

        self.partida.empates_consecutivos = getattr(self.partida, "empates_consecutivos", 0) + 1
        empates = self.partida.empates_consecutivos

        if modo in (ModoJuego.CAOS, ModoJuego.EXTENDIDO) and empates > 3:
            return await self._resolver_empate_multiple(canal, candidatos)

        desc_empate = t("results_tie_desc", g)
        if modo in (ModoJuego.CAOS, ModoJuego.EXTENDIDO):
            if get_lang(g) == "es":
                desc_empate += f"\n\n⚠️ **Empates consecutivos: {empates}/3** *(Al superar 3 empates seguidos habrá expulsión masiva)*."
            else:
                desc_empate += f"\n\n⚠️ **Consecutive ties: {empates}/3** *(Exceeding 3 consecutive ties triggers mass ejection)*."

        await canal.send(embed=discord.Embed(
            title=t("results_tie_title", g),
            description=desc_empate,
            color=discord.Color.greyple(),
        ))
        self.partida.rondas_sin_expulsion += 1
        return await self._siguiente_ronda(canal)

    async def _resolver_empate_multiple(self, canal: discord.TextChannel, candidatos: list[str]):
        g    = gid(self.partida)
        modo = self.partida.config.modo_juego

        expulsados_empate: list[discord.Member] = []
        for uid_str in candidatos:
            m = discord.utils.get(self.partida.jugadores, id=int(uid_str))
            if m:
                expulsados_empate.append(m)

        nombres_exp = ", ".join(f"**{m.display_name}**" for m in expulsados_empate)
        await canal.send(embed=discord.Embed(
            title=t("results_tie_multi_title", g),
            description=t("results_tie_multi_desc", g, names=nombres_exp),
            color=discord.Color.dark_orange(),
        ))

        for exp in expulsados_empate:
            self.partida.impostores = [j for j in self.partida.impostores if j.id != exp.id]
            self.partida.jugadores = [j for j in self.partida.jugadores if j.id != exp.id]

        self.partida.rondas_sin_expulsion = 0
        self.partida.empates_consecutivos = 0

        if (
            not self.partida.caos_sin_impostores
            and not getattr(self.partida, "caos_todos_impostores", False)
            and len(self.partida.impostores) == 0
        ):
            # En Modo Clásico y Extendido, el último impostor atrapado tiene su Última Oportunidad
            impostores_caidos = [m for m in expulsados_empate if any(imp.id == m.id for imp in self.partida.impostores_iniciales)]
            ultimo_imp = impostores_caidos[-1] if impostores_caidos else (expulsados_empate[0] if expulsados_empate else None)
            if modo in (ModoJuego.CLASICO, ModoJuego.EXTENDIDO) and self.partida.datos_pokemon and ultimo_imp:
                es_es = (get_lang(g) == "es")
                view_uo = PanelUltimaOportunidad(self.partida, ultimo_imp)
                emb_uo = discord.Embed(
                    title="🎯 ¡ÚLTIMA OPORTUNIDAD DEL IMPOSTOR!" if es_es else "🎯 IMPOSTOR'S LAST STAND!",
                    description=(
                        f"¡Han atrapado a **{ultimo_imp.display_name}** en la expulsión múltiple! Pero antes de cantar victoria...\n\n"
                        f"🕵️ **{ultimo_imp.display_name}** tiene **1 oportunidad** de escribir el nombre del Pokémon secreto. "
                        f"Si lo adivina, **¡robará la partida!**"
                        if es_es else
                        f"**{ultimo_imp.display_name}** was caught in the mass ejection! But before celebrating...\n\n"
                        f"🕵️ **{ultimo_imp.display_name}** has **1 chance** to guess the secret Pokémon's name. "
                        f"If they guess right, **they steal the match!**"
                    ),
                    color=discord.Color.from_rgb(255, 140, 0),
                )
                msg_uo = await canal.send(embed=emb_uo, view=view_uo)
                view_uo.message = msg_uo
                return

            return await self._pantalla_final(canal, victoria_impostores=False)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)

        # En Modo CAOS no hay instant-win por paridad; solo termina si quedan 0 tripulantes vivos
        if modo == ModoJuego.CAOS:
            if (
                not self.partida.caos_sin_impostores
                and not getattr(self.partida, "caos_todos_impostores", False)
                and len(self.partida.impostores) > 0
                and tripulantes_vivos == 0
            ):
                await canal.send(embed=discord.Embed(
                    title=t("results_impostors_win_title", g),
                    description=t("results_impostors_win_desc", g),
                    color=discord.Color.from_rgb(50, 0, 0),
                ))
                return await self._pantalla_final(canal, victoria_impostores=True)
            return await self._siguiente_ronda(canal)

        # En Modo EXTENDIDO: victoria por paridad (impostores >= tripulantes)
        if len(self.partida.impostores) > 0 and len(self.partida.impostores) >= tripulantes_vivos:
            await canal.send(embed=discord.Embed(
                title=t("results_impostors_win_title", g),
                description=t("results_impostors_win_desc", g),
                color=discord.Color.from_rgb(50, 0, 0),
            ))
            return await self._pantalla_final(canal, victoria_impostores=True)

        return await self._siguiente_ronda(canal)

    # ── Expulsión de un único jugador ────────────────────────────────────────
    async def _resolver_expulsion_unica(self, canal: discord.TextChannel, candidato_id: str):
        g    = gid(self.partida)
        modo = self.partida.config.modo_juego

        expulsado = discord.utils.get(self.partida.jugadores, id=int(candidato_id))
        if expulsado is None:
            await canal.send(t("results_left_server", g))
            return await self._siguiente_ronda(canal)

        self.partida.rondas_sin_expulsion = 0
        self.partida.empates_consecutivos = 0

        es_impostor = any(imp.id == expulsado.id for imp in self.partida.impostores)
        embed_rev   = discord.Embed(color=discord.Color.dark_red())
        if getattr(expulsado, "display_avatar", None) and getattr(expulsado.display_avatar, "url", None):
            embed_rev.set_thumbnail(url=expulsado.display_avatar.url)

        if es_impostor:
            self.partida.impostores = [j for j in self.partida.impostores if j.id != expulsado.id]
            self.partida.jugadores = [j for j in self.partida.jugadores if j.id != expulsado.id]

            if not getattr(self.partida, "caos_todos_impostores", False) and len(self.partida.impostores) == 0:
                embed_rev.title       = t("results_impostor_found_title", g)
                embed_rev.description = t("results_impostor_found_desc",  g, name=expulsado.display_name)
                embed_rev.color       = discord.Color.green()
                await canal.send(embed=embed_rev)

                # 🎯 En Modo Clásico y Extendido, el último impostor atrapado tiene su Última Oportunidad (Spyfall)
                if modo in (ModoJuego.CLASICO, ModoJuego.EXTENDIDO) and self.partida.datos_pokemon:
                    es_es = (get_lang(g) == "es")
                    view_uo = PanelUltimaOportunidad(self.partida, expulsado)
                    emb_uo = discord.Embed(
                        title="🎯 ¡ÚLTIMA OPORTUNIDAD DEL IMPOSTOR!" if es_es else "🎯 IMPOSTOR'S LAST STAND!",
                        description=(
                            f"¡Han atrapado a **{expulsado.display_name}**! Pero antes de cantar victoria...\n\n"
                            f"🕵️ **{expulsado.display_name}** tiene **1 oportunidad** de escribir el nombre del Pokémon secreto. "
                            f"Si lo adivina, **¡robará la partida!**"
                            if es_es else
                            f"**{expulsado.display_name}** was caught! But before celebrating...\n\n"
                            f"🕵️ **{expulsado.display_name}** has **1 chance** to guess the secret Pokémon's name. "
                            f"If they guess right, **they steal the match!**"
                        ),
                        color=discord.Color.from_rgb(255, 140, 0),
                    )
                    msg_uo = await canal.send(embed=emb_uo, view=view_uo)
                    view_uo.message = msg_uo
                    return

                return await self._pantalla_final(canal, victoria_impostores=False)

            embed_rev.title       = t("results_impostor_more_title", g)
            embed_rev.description = t("results_impostor_more_desc",  g, name=expulsado.display_name)
        else:
            self.partida.jugadores = [j for j in self.partida.jugadores if j.id != expulsado.id]
            embed_rev.title       = t("results_innocent_title", g)
            embed_rev.description = t("results_innocent_desc",  g, name=expulsado.display_name)

        await canal.send(embed=embed_rev)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)

        # En Modo CAOS: sin instant-win por paridad. Solo termina si ya no quedan tripulantes vivos.
        if modo == ModoJuego.CAOS:
            if (
                not self.partida.caos_sin_impostores
                and not getattr(self.partida, "caos_todos_impostores", False)
                and len(self.partida.impostores) > 0
                and tripulantes_vivos == 0
            ):
                return await self._resolver_victoria_impostores(canal, tripulantes_vivos)
            return await self._siguiente_ronda(canal)

        # En Modo CLÁSICO y EXTENDIDO: paridad (impostores >= tripulantes) da victoria a impostores
        if len(self.partida.impostores) > 0 and len(self.partida.impostores) >= tripulantes_vivos:
            return await self._resolver_victoria_impostores(canal, tripulantes_vivos)

        await self._siguiente_ronda(canal)

    # ── Victoria de impostores (con caso especial 1 vs 1) ────────────────────
    async def _resolver_victoria_impostores(self, canal: discord.TextChannel, tripulantes_vivos: int):
        g = gid(self.partida)

        if len(self.partida.impostores) == 1 and tripulantes_vivos == 1:
            impostor_final = self.partida.impostores[0]
            tripulante_final = next(
                (j for j in self.partida.jugadores if j.id != impostor_final.id),
                None,
            )
            embed_faceoff = discord.Embed(
                title=t("results_faceoff_title", g),
                description=t("results_faceoff_desc", g,
                              impostor=f"**{impostor_final.display_name}**",
                              crewmate=f"**{tripulante_final.display_name}**" if tripulante_final else "???"),
                color=discord.Color.from_rgb(120, 0, 0),
            )
            if getattr(impostor_final, "display_avatar", None) and getattr(impostor_final.display_avatar, "url", None):
                embed_faceoff.set_thumbnail(url=impostor_final.display_avatar.url)
            await canal.send(embed=embed_faceoff)
        else:
            await canal.send(embed=discord.Embed(
                title=t("results_impostors_win_title", g),
                description=t("results_impostors_win_desc", g),
                color=discord.Color.from_rgb(50, 0, 0),
            ))

        return await self._pantalla_final(canal, victoria_impostores=True)

    # ─────────────────────────────────────────────────────────────────────────
    #  TRANSICIONES
    # ─────────────────────────────────────────────────────────────────────────
    async def _siguiente_ronda(self, canal: discord.TextChannel):
        g = gid(self.partida)

        if len(self.partida.jugadores) < 3:
            if getattr(self.partida, "caos_todos_impostores", False):
                await canal.send(embed=discord.Embed(
                    title=t("results_caos_todos_impostores_title", g),
                    description=t("final_desc_todos_impostores", g),
                    color=discord.Color.magenta(),
                ))
                return await self._pantalla_final(canal, victoria_impostores=True)

            quedan_impostores = len(self.partida.impostores) > 0
            return await self._pantalla_final(canal, victoria_impostores=quedan_impostores)

        if self.partida.ronda >= self.partida.config.max_rondas:
            if getattr(self.partida, "caos_todos_impostores", False):
                await canal.send(embed=discord.Embed(
                    title=t("results_caos_todos_impostores_title", g),
                    description=t("final_desc_todos_impostores", g),
                    color=discord.Color.magenta(),
                ))
                return await self._pantalla_final(canal, victoria_impostores=True)

            if self.partida.caos_sin_impostores:
                await canal.send(embed=discord.Embed(
                    title=t("final_title_cero_impostores", g),
                    description=t("final_desc_cero_impostores", g),
                    color=discord.Color.gold(),
                ))
                return await self._pantalla_final(canal, victoria_impostores=False)

            quedan_impostores = len(self.partida.impostores) > 0
            await canal.send(embed=discord.Embed(
                title=t("game_over_timeout_title", g),
                description=t("game_over_timeout_desc", g),
                color=discord.Color.from_rgb(180, 20, 20),
            ))
            return await self._pantalla_final(canal, victoria_impostores=quedan_impostores)

        self.partida.ronda += 1
        restantes = self.partida.rondas_restantes
        view_deb = PanelDebate(self.partida)
        embed_sig = discord.Embed(
            title=t("round_next_title", g, n=self.partida.ronda),
            description=t("round_next_desc", g),
            color=discord.Color.gold(),
        )
        embed_sig.add_field(name=t("round_remaining_field", g), value=f"⏳ **{restantes}**", inline=True)
        msg = await canal.send(
            embed=embed_sig,
            view=view_deb,
        )
        view_deb.message = msg

        if (
            self.partida.rondas_sin_expulsion >= 3
            and not self.partida.pista_publica_revelada
        ):
            pista_publica = self.partida.generar_pista_publica()
            if pista_publica:
                self.partida.pista_publica_revelada = True
                await canal.send(embed=discord.Embed(
                    title=t("public_hint_title", g),
                    description=t("public_hint_desc", g, hint=pista_publica),
                    color=discord.Color.from_rgb(255, 150, 0),
                ))

    async def _pantalla_final(self, canal: discord.TextChannel, victoria_impostores: bool):
        from .final import mostrar_pantalla_final
        await mostrar_pantalla_final(self.partida, canal, victoria_impostores)


# ═══════════════════════════════════════════════════════════════════════════════
#  🎯 MECÁNICA SPYFALL: ÚLTIMA OPORTUNIDAD DEL IMPOSTOR (CON PAUSA DRAMÁTICA)
# ═══════════════════════════════════════════════════════════════════════════════

class _SelectAutocompletadoPokemon(discord.ui.View):
    """Menú efímero sin spoilers (solo nombres) para confirmar el Pokémon tras escribir un fragmento."""
    def __init__(self, padre_view: PanelUltimaOportunidad, coincidencias: list[str], autor: discord.Member):
        super().__init__(timeout=35)
        self.padre_view = padre_view
        self.coincidencias = coincidencias
        self.autor = autor

        opciones = [discord.SelectOption(label=nom, value=nom, emoji="🔮") for nom in coincidencias[:25]]
        g = gid(padre_view.partida)
        es_es = (get_lang(g) == "es")
        sel = discord.ui.Select(
            placeholder="🔍 Selecciona el Pokémon exacto de la lista..." if es_es else "🔍 Pick the exact Pokémon from the list...",
            options=opciones,
            min_values=1,
            max_values=1,
        )
        sel.callback = self._confirmar_seleccion
        self.add_item(sel)

    async def _confirmar_seleccion(self, inter: discord.Interaction):
        g = gid(self.padre_view.partida)
        es_es = (get_lang(g) == "es")
        elegido = inter.data["values"][0]
        msg_conf = f"🎯 Has elegido **{elegido}**. ¡Lanzando veredicto en el canal!" if es_es else f"🎯 You chose **{elegido}**. Revealing verdict in channel!"
        await inter.response.edit_message(content=msg_conf, view=None)
        await self.padre_view.ejecutar_revelacion_dramatica(inter.channel, self.autor, elegido)

    async def on_timeout(self):
        if not self.padre_view._resuelto and self.coincidencias:
            await self.padre_view.ejecutar_revelacion_dramatica(
                self.padre_view.partida.canal, self.autor, self.coincidencias[0]
            )


class PanelUltimaOportunidad(discord.ui.View):
    """
    Cuando el último impostor es descubierto en Modo Clásico o Extendido,
    tiene una única oportunidad de adivinar el nombre del Pokémon secreto para
    robar la victoria.
    """
    def __init__(self, partida: Partida, impostor_atrapado: discord.Member):
        super().__init__(timeout=90)
        self.partida = partida
        self.impostor_atrapado = impostor_atrapado
        self._resuelto = False
        g = gid(partida)
        es_es = (get_lang(g) == "es")

        lbl_guess = "🎯 Adivinar Pokémon (Última Oportunidad)" if es_es else "🎯 Guess Pokémon (Last Stand)"
        lbl_pass  = "🏳️ Rendirse" if es_es else "🏳️ Give Up"

        btn_guess = discord.ui.Button(label=lbl_guess, style=discord.ButtonStyle.danger, row=0)
        btn_pass  = discord.ui.Button(label=lbl_pass,  style=discord.ButtonStyle.secondary, row=0)
        btn_guess.callback = self._abrir_buscador
        btn_pass.callback  = self._rendirse
        self.add_item(btn_guess)
        self.add_item(btn_pass)

    def _puede_accionar(self, user: discord.Member, guild: discord.Guild | None) -> bool:
        if user.id == self.impostor_atrapado.id:
            return True
        if getattr(self.impostor_atrapado, "es_dummy", False) and es_anfitrion_o_admin(user, guild):
            return True
        return False

    async def on_timeout(self):
        if self._resuelto:
            return
        self._resuelto = True
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass
        from .final import mostrar_pantalla_final
        await mostrar_pantalla_final(self.partida, self.partida.canal, victoria_impostores=False)

    async def _rendirse(self, inter: discord.Interaction):
        g = inter.guild_id
        if not self._puede_accionar(inter.user, inter.guild):
            msg = "⛔ Solo el impostor atrapado puede usar su Última Oportunidad." if get_lang(g) == "es" else "⛔ Only the caught impostor can use Last Stand."
            return await inter.response.send_message(msg, ephemeral=True)

        async with self.partida.lock:
            if self._resuelto:
                return
            self._resuelto = True

        self.stop()
        try:
            await inter.message.edit(view=None)
        except Exception:
            pass

        es_es = (get_lang(g) == "es")
        txt = f"🏳️ **{self.impostor_atrapado.display_name}** no supo qué Pokémon era y aceptó su derrota." if es_es else f"🏳️ **{self.impostor_atrapado.display_name}** gave up and accepted defeat."
        await inter.response.send_message(txt)
        from .final import mostrar_pantalla_final
        await mostrar_pantalla_final(self.partida, inter.channel, victoria_impostores=False)

    async def _abrir_buscador(self, inter: discord.Interaction):
        g = inter.guild_id
        if not self._puede_accionar(inter.user, inter.guild):
            msg = "⛔ Solo el impostor atrapado puede usar su Última Oportunidad." if get_lang(g) == "es" else "⛔ Only the caught impostor can use Last Stand."
            return await inter.response.send_message(msg, ephemeral=True)

        if self._resuelto:
            return await inter.response.send_message("⏳ Ya se emitió un intento.", ephemeral=True)

        padre = self
        es_es = (get_lang(g) == "es")

        class ModalBuscarPoke(discord.ui.Modal, title="🎯 Última Oportunidad" if es_es else "🎯 Last Stand"):
            texto = discord.ui.TextInput(
                label="Escribe el nombre (o primeras letras)" if es_es else "Type Pokémon name (or first letters)",
                placeholder="Ej: gar, pangoro, charizard..." if es_es else "E.g.: gar, pangoro, charizard...",
                min_length=2,
                max_length=30,
                required=True,
            )

            async def on_submit(self, modal_inter: discord.Interaction):
                from api import buscar_coincidencias_pokemon
                escrito = self.texto.value.strip()
                coincidencias = await buscar_coincidencias_pokemon(escrito, limite=25)

                dp = padre.partida.datos_pokemon or {}
                nombre_real = (dp.get("nombre") or "").lower()
                nombre_base = (dp.get("nombre_base") or "").lower()

                if escrito.lower() in (nombre_real, nombre_base) or len(coincidencias) == 1:
                    elegido = coincidencias[0] if len(coincidencias) == 1 else escrito.capitalize()
                    msg_apuesta = f"🎯 Apostando todo a **{elegido}**..." if es_es else f"🎯 Putting it all on **{elegido}**..."
                    await modal_inter.response.send_message(msg_apuesta, ephemeral=True)
                    await padre.ejecutar_revelacion_dramatica(modal_inter.channel, padre.impostor_atrapado, elegido)
                    return

                if not coincidencias:
                    msg_apuesta = f"🎯 Apostando todo a **{escrito.capitalize()}**..." if es_es else f"🎯 Putting it all on **{escrito.capitalize()}**..."
                    await modal_inter.response.send_message(msg_apuesta, ephemeral=True)
                    await padre.ejecutar_revelacion_dramatica(modal_inter.channel, padre.impostor_atrapado, escrito.capitalize())
                    return

                vista_auto = _SelectAutocompletadoPokemon(padre, coincidencias, padre.impostor_atrapado)
                msg_auto = (
                    f"🔎 Encontré **{len(coincidencias)}** Pokémon que coinciden con `\"{escrito}\"`. "
                    f"Elige el nombre exacto en la lista de abajo:"
                    if es_es else
                    f"🔎 Found **{len(coincidencias)}** Pokémon matching `\"{escrito}\"`. Pick the exact name below:"
                )
                await modal_inter.response.send_message(msg_auto, view=vista_auto, ephemeral=True)

        await inter.response.send_modal(ModalBuscarPoke())

    async def ejecutar_revelacion_dramatica(self, canal: discord.TextChannel, autor: discord.Member, intento_nombre: str):
        async with self.partida.lock:
            if self._resuelto:
                return
            self._resuelto = True

        self.stop()
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

        g = gid(self.partida)
        es_es = (get_lang(g) == "es")
        dp = self.partida.datos_pokemon or {}
        real_full = (dp.get("nombre") or "").strip().lower()
        real_base = (dp.get("nombre_base") or real_full).strip().lower()
        intento_low = intento_nombre.strip().lower()

        # Acierto si coincide con el nombre completo o especie base
        acerto = (
            intento_low == real_full
            or intento_low == real_base
            or (len(intento_low) >= 4 and intento_low == real_full.split(" ")[0].lower())
        )

        titulo_suspenso = "🎭 ¡ÚLTIMA OPORTUNIDAD EN JUEGO!" if es_es else "🎭 LAST STAND IN PLAY!"
        base_desc = (
            f"🔪 **{autor.display_name}** se niega a caer sin pelear y asegura que el Pokémon secreto es...\n\n"
            f"👉 **« {intento_nombre.upper()} »**\n\n"
            if es_es else
            f"🔪 **{autor.display_name}** refuses to go down without a fight and claims the secret Pokémon is...\n\n"
            f"👉 **« {intento_nombre.upper()} »**\n\n"
        )

        emb_suspenso = discord.Embed(
            title=titulo_suspenso,
            description=base_desc + "⏳ **.**",
            color=discord.Color.from_rgb(255, 140, 0),
        )
        msg_drama = await canal.send(embed=emb_suspenso)

        for puntos in ("⏳ **. .**", "⏳ **. . .**"):
            await asyncio.sleep(1.1)
            try:
                emb_suspenso.description = base_desc + puntos
                await msg_drama.edit(embed=emb_suspenso)
            except Exception:
                pass

        await asyncio.sleep(1.2)

        if acerto:
            self.partida.robo_ultima_oportunidad = True
            emb_res = discord.Embed(
                title="💀 ¡ACERTÓ! ¡ROBO MAESTRO DEL IMPOSTOR!" if es_es else "💀 CORRECT! MASTERMIND IMPOSTOR STEAL!",
                description=(
                    f"😱 **¡INCREÍBLE!** ¡El Pokémon secreto sí era **{dp.get('nombre')}**!\n\n"
                    f"Aunque descubrieron a **{autor.display_name}**, dedujo el Pokémon exacto a partir de las pistas del grupo y **roba la victoria para los Impostores**."
                    if es_es else
                    f"😱 **UNBELIEVABLE!** The secret Pokémon was indeed **{dp.get('nombre')}**!\n\n"
                    f"Even though **{autor.display_name}** was caught, they deduced the exact Pokémon from your clues and **stole the win for the Impostors**!"
                ),
                color=discord.Color.from_rgb(180, 0, 40),
            )
            victoria_imp = True
        else:
            emb_res = discord.Embed(
                title="🎉 ¡SE EQUIVOCÓ! ¡VICTORIA DE LOS TRIPULANTES!" if es_es else "🎉 WRONG GUESS! CREWMATES WIN!",
                description=(
                    f"❌ **{autor.display_name}** apostó por **{intento_nombre}**, ¡pero estaba completamente equivocado!\n\n"
                    f"¡Los tripulantes protegen el secreto y aseguran la victoria definitiva!"
                    if es_es else
                    f"❌ **{autor.display_name}** guessed **{intento_nombre}**, but was dead wrong!\n\n"
                    f"The crewmates protected the secret and secured the victory!"
                ),
                color=discord.Color.green(),
            )
            victoria_imp = False

        try:
            await msg_drama.edit(embed=emb_res)
        except Exception:
            await canal.send(embed=emb_res)

        from .final import mostrar_pantalla_final
        await mostrar_pantalla_final(self.partida, canal, victoria_impostores=victoria_imp)
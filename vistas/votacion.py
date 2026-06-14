"""
vistas/votacion.py — Panel de votación y resolución de resultados.

Esta es la parte más grande del juego: gestiona la votación normal
(Clásico/Extendido/Caos), la votación especial de la variante
Objetivo Humano (solo vota el detective), el desglose de votos,
los empates (simples y múltiples), el enfrentamiento final 1v1,
y la transición a la siguiente ronda o a la pantalla final.
"""
from __future__ import annotations

import discord
from motor_juego import Partida, ModoJuego, CaosVariante
from i18n import t

from .common import TIMEOUT_VOTACION, gid, VOTO_NULO_ID
from .debate import PanelDebate


class PanelVotacion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_VOTACION)
        self.partida         = partida
        self.votos_emitidos: set[int]            = set()
        self.votos_urna:     dict[str, set[int]] = {}
        g     = gid(partida)
        modo  = partida.config.modo_juego
        total = len(partida.jugadores)

        # ── Variante OBJETIVO_HUMANO de CAOS: solo el detective vota ──────────
        if modo == ModoJuego.CAOS and partida.config.caos_variante == CaosVariante.OBJETIVO_HUMANO:
            self._init_votacion_objetivo_humano(g)
            return  # no construir el select normal

        # ── Modos normales (Clásico / Extendido / Caos estándar) ──────────────
        es_clasico = (modo == ModoJuego.CLASICO)
        max_v      = 1 if es_clasico else total

        opciones = [discord.SelectOption(label=j.display_name, value=str(j.id)) for j in partida.jugadores]

        # Voto nulo disponible en TODOS los modos
        opciones.append(discord.SelectOption(
            label=t("vote_null_label", g),
            value=VOTO_NULO_ID,
            description=t("vote_null_desc", g),
            emoji="⚪",
        ))

        sel = discord.ui.Select(
            placeholder=t("vote_placeholder", g),
            min_values=1,
            max_values=max_v,
            options=opciones,
            row=0,
        )
        sel.callback = self._registrar_voto
        self.add_item(sel)
        self.sel_votos = sel

        btn_forzar = discord.ui.Button(label=t("btn_force_close", g), style=discord.ButtonStyle.secondary, row=1)
        btn_forzar.callback = self._forzar_cierre
        self.add_item(btn_forzar)

    # ─────────────────────────────────────────────────────────────────────────
    #  VOTACIÓN ESPECIAL — Objetivo Humano (solo el detective vota)
    # ─────────────────────────────────────────────────────────────────────────
    def _init_votacion_objetivo_humano(self, g: int):
        # Solo el detective (impostor) puede votar, eligiendo quién cree que
        # es el objetivo. Los tripulantes no votan — la ronda termina cuando
        # el detective adivina o pasa.
        opciones_cj = [
            discord.SelectOption(label=j.display_name, value=str(j.id))
            for j in self.partida.jugadores
            if j not in self.partida.impostores  # el detective no puede votarse a sí mismo
        ]
        opciones_cj.append(discord.SelectOption(
            label=t("vote_null_label", g),
            value=VOTO_NULO_ID,
            description=t("caos_jugador_pass_desc", g),
            emoji="⚪",
        ))
        sel_cj = discord.ui.Select(
            placeholder=t("caos_jugador_vote_placeholder", g),
            min_values=1, max_values=1,
            options=opciones_cj,
            row=0,
        )
        sel_cj.callback = self._voto_caos_jugador
        self.add_item(sel_cj)
        self.sel_votos = sel_cj

        btn_forzar = discord.ui.Button(label=t("btn_force_close", g), style=discord.ButtonStyle.secondary, row=1)
        btn_forzar.callback = self._forzar_cierre_cj
        self.add_item(btn_forzar)

    async def _voto_caos_jugador(self, inter: discord.Interaction):
        g = inter.guild_id
        if inter.user not in self.partida.impostores:
            return await inter.response.send_message(t("caos_jugador_only_detective", g), ephemeral=True)
        if inter.user.id in self.votos_emitidos:
            return await inter.response.send_message(t("vote_already_voted", g), ephemeral=True)

        self.votos_emitidos.add(inter.user.id)
        valor = self.sel_votos.values[0]

        self.clear_items()
        self.stop()
        try:
            await inter.message.edit(view=None)
        except Exception:
            pass

        objetivo = self.partida.objetivo_humano
        acerto   = False  # por defecto: si pasa (voto nulo), el detective NO acierta

        if valor == VOTO_NULO_ID:
            await inter.response.send_message(embed=discord.Embed(
                title=t("caos_jugador_pass_title", g),
                description=t("caos_jugador_pass_desc_result", g, target=f"**{objetivo.display_name}**"),
                color=discord.Color.green(),
            ))
        else:
            adivinado = discord.utils.get(self.partida.jugadores, id=int(valor))
            acerto    = (adivinado == objetivo)
            if acerto:
                await inter.response.send_message(embed=discord.Embed(
                    title=t("caos_jugador_correct_title", g),
                    description=t("caos_jugador_correct_desc", g,
                                  detective=f"**{inter.user.display_name}**",
                                  target=f"**{objetivo.display_name}**"),
                    color=discord.Color.from_rgb(180, 30, 30),
                ).set_thumbnail(url=objetivo.display_avatar.url))
            else:
                nombre_adivinado = adivinado.display_name if adivinado else "???"
                await inter.response.send_message(embed=discord.Embed(
                    title=t("caos_jugador_wrong_title", g),
                    description=t("caos_jugador_wrong_desc", g,
                                  guessed=f"**{nombre_adivinado}**",
                                  target=f"**{objetivo.display_name}**"),
                    color=discord.Color.green(),
                ).set_thumbnail(url=objetivo.display_avatar.url))

        return await self._pantalla_final(inter.channel, victoria_impostores=acerto)

    async def _forzar_cierre_cj(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("vote_only_admin_force", g), ephemeral=True)
        await inter.response.send_message(t("caos_jugador_admin_skip", g))
        self.clear_items()
        self.stop()
        try:
            await inter.message.edit(view=None)
        except Exception:
            pass
        await self._pantalla_final(inter.channel, victoria_impostores=False)

    # ─────────────────────────────────────────────────────────────────────────
    #  VOTACIÓN NORMAL — Clásico / Extendido / Caos estándar
    # ─────────────────────────────────────────────────────────────────────────
    async def _registrar_voto(self, inter: discord.Interaction):
        g = inter.guild_id
        if inter.user not in self.partida.jugadores:
            return await inter.response.send_message(t("vote_only_players", g), ephemeral=True)
        if inter.user.id in self.votos_emitidos:
            return await inter.response.send_message(t("vote_already_voted", g), ephemeral=True)

        self.votos_emitidos.add(inter.user.id)

        valores = self.sel_votos.values
        # voto nulo: registrar pero no añadir a ningún acusado
        if VOTO_NULO_ID not in valores:
            for acusado_id in valores:
                self.votos_urna.setdefault(acusado_id, set()).add(inter.user.id)

        total  = len(self.partida.jugadores)
        actual = len(self.votos_emitidos)

        await inter.response.send_message(t("vote_registered", g), ephemeral=True)
        await inter.message.edit(embed=discord.Embed(
            title=t("vote_title_open", g),
            description=t("vote_desc", g, current=actual, total=total),
            color=discord.Color.red(),
        ))

        if actual == total:
            await self._mostrar_resultados(inter.channel, inter.message)

    async def _forzar_cierre(self, inter: discord.Interaction):
        g = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("vote_only_admin_force", g), ephemeral=True)
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

        # ── Desglose visual de votos ─────────────────────────────────────────
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

    # ── Empate (1 o más candidatos con el máximo de votos) ──────────────────
    async def _resolver_empate(self, canal: discord.TextChannel, candidatos: list[str]):
        g    = gid(self.partida)
        modo = self.partida.config.modo_juego

        # En CAOS y EXTENDIDO: empate con votos > 0 → todos los empatados salen
        if modo in (ModoJuego.CAOS, ModoJuego.EXTENDIDO):
            return await self._resolver_empate_multiple(canal, candidatos)

        # CLASICO (y Objetivo Humano nunca llega aquí, tiene su propia ruta):
        # empate = nadie sale
        await canal.send(embed=discord.Embed(
            title=t("results_tie_title", g),
            description=t("results_tie_desc", g),
            color=discord.Color.greyple(),
        ))
        self.partida.rondas_sin_expulsion += 1
        return await self._siguiente_ronda(canal)

    async def _resolver_empate_multiple(self, canal: discord.TextChannel, candidatos: list[str]):
        g = gid(self.partida)

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
            if exp in self.partida.impostores:
                self.partida.impostores.remove(exp)
            if exp in self.partida.jugadores:
                self.partida.jugadores.remove(exp)

        self.partida.rondas_sin_expulsion = 0  # hubo expulsión: resetear estancamiento

        # comprobar victoria tras el empate masivo
        if len(self.partida.impostores) == 0:
            return await self._pantalla_final(canal, victoria_impostores=False)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        if len(self.partida.impostores) >= tripulantes_vivos:
            await canal.send(embed=discord.Embed(
                title=t("results_impostors_win_title", g),
                description=t("results_impostors_win_desc", g),
                color=discord.Color.from_rgb(50, 0, 0),
            ))
            return await self._pantalla_final(canal, victoria_impostores=True)

        return await self._siguiente_ronda(canal)

    # ── Expulsión de un único jugador ────────────────────────────────────────
    async def _resolver_expulsion_unica(self, canal: discord.TextChannel, candidato_id: str):
        g = gid(self.partida)

        expulsado = discord.utils.get(self.partida.jugadores, id=int(candidato_id))
        if expulsado is None:
            await canal.send(t("results_left_server", g))
            return await self._siguiente_ronda(canal)

        self.partida.rondas_sin_expulsion = 0  # hubo expulsión: resetear estancamiento

        es_impostor = expulsado in self.partida.impostores
        embed_rev   = discord.Embed(color=discord.Color.dark_red())
        embed_rev.set_thumbnail(url=expulsado.display_avatar.url)

        if es_impostor:
            self.partida.impostores.remove(expulsado)
            self.partida.jugadores.remove(expulsado)

            if len(self.partida.impostores) == 0:
                embed_rev.title       = t("results_impostor_found_title", g)
                embed_rev.description = t("results_impostor_found_desc",  g, name=expulsado.display_name)
                embed_rev.color       = discord.Color.green()
                await canal.send(embed=embed_rev)
                return await self._pantalla_final(canal, victoria_impostores=False)

            embed_rev.title       = t("results_impostor_more_title", g)
            embed_rev.description = t("results_impostor_more_desc",  g,
                                      name=expulsado.display_name,
                                      remaining=len(self.partida.impostores))
        else:
            self.partida.jugadores.remove(expulsado)
            embed_rev.title       = t("results_innocent_title", g)
            embed_rev.description = t("results_innocent_desc",  g, name=expulsado.display_name)

        await canal.send(embed=embed_rev)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        if len(self.partida.impostores) >= tripulantes_vivos:
            return await self._resolver_victoria_impostores(canal, tripulantes_vivos)

        # La pregunta "¿hay más impostores?" solo aplica al Caos NORMAL
        # (las variantes Objetivo Humano / Danza Caos no llegan a esta rama)
        if self.partida.config.modo_juego == ModoJuego.CAOS and es_impostor:
            await self._pregunta_caos(canal)
        else:
            await self._siguiente_ronda(canal)

    # ── Victoria de impostores (con caso especial 1 vs 1) ────────────────────
    async def _resolver_victoria_impostores(self, canal: discord.TextChannel, tripulantes_vivos: int):
        g = gid(self.partida)

        # Caso especial: enfrentamiento final 1 contra 1 — el momento más
        # tenso posible. Revelamos cara a cara quién era el traidor antes
        # de la pantalla final.
        if len(self.partida.impostores) == 1 and tripulantes_vivos == 1:
            impostor_final = self.partida.impostores[0]
            tripulante_final = next(
                (j for j in self.partida.jugadores if j not in self.partida.impostores),
                None,
            )
            embed_faceoff = discord.Embed(
                title=t("results_faceoff_title", g),
                description=t("results_faceoff_desc", g,
                              impostor=f"**{impostor_final.display_name}**",
                              crewmate=f"**{tripulante_final.display_name}**" if tripulante_final else "???"),
                color=discord.Color.from_rgb(120, 0, 0),
            )
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

        # Si tras las expulsiones de esta ronda ya no hay suficientes jugadores
        # para seguir jugando, terminamos. Los impostores que sigan vivos
        # se consideran "escaparon" (ganan); si no quedan, ganan tripulantes.
        if len(self.partida.jugadores) < 3:
            quedan_impostores = len(self.partida.impostores) > 0
            return await self._pantalla_final(canal, victoria_impostores=quedan_impostores)

        self.partida.ronda += 1
        await canal.send(
            embed=discord.Embed(
                title=t("round_next_title", g, n=self.partida.ronda),
                description=t("round_next_desc", g),
                color=discord.Color.gold(),
            ),
            view=PanelDebate(self.partida),
        )

        # ── Anti-estancamiento: revelar pista pública tras 3 rondas sin expulsión ──
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

    async def _pregunta_caos(self, canal: discord.TextChannel):
        g      = gid(self.partida)
        _sig   = self._siguiente_ronda
        _final = self._pantalla_final

        class VotoCaos(discord.ui.View):
            def __init__(self, p: Partida):
                super().__init__(timeout=TIMEOUT_VOTACION)
                self.p = p

            @discord.ui.button(style=discord.ButtonStyle.danger)
            async def b_si(self, i: discord.Interaction, b: discord.ui.Button):
                self.stop()
                await i.response.edit_message(view=None)
                await _sig(i.channel)

            @discord.ui.button(style=discord.ButtonStyle.success)
            async def b_no(self, i: discord.Interaction, b: discord.ui.Button):
                self.stop()
                await i.response.edit_message(view=None)
                # Si el grupo dice "ya no hay más" pero en realidad SIGUEN
                # quedando impostores ocultos, esos impostores ganan (escaparon).
                quedan_impostores = len(self.p.impostores) > 0
                await _final(i.channel, victoria_impostores=quedan_impostores)

        view = VotoCaos(self.partida)
        view.b_si.label = t("btn_caos_yes", g)
        view.b_no.label = t("btn_caos_no",  g)
        await canal.send(embed=discord.Embed(
            title=t("caos_question_title", g),
            description=t("caos_question_desc", g),
            color=discord.Color.from_rgb(100, 0, 200),
        ), view=view)

    # ── Delegación a la pantalla final (módulo aparte) ───────────────────────
    async def _pantalla_final(self, canal: discord.TextChannel, victoria_impostores: bool):
        from .final import mostrar_pantalla_final
        await mostrar_pantalla_final(self.partida, canal, victoria_impostores)
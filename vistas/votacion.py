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

from .common import (
    TIMEOUT_VOTACION,
    gid,
    VOTO_NULO_ID,
    NOMBRE_ROL_HOST,
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
        # Evita que dos interacciones casi simultáneas (ej. el último voto
        # y un "forzar cierre" del admin al mismo tiempo) disparen
        # _mostrar_resultados dos veces.
        self._resultados_en_proceso: bool = False
        g     = gid(partida)
        modo  = partida.config.modo_juego
        total = len(partida.jugadores)

        # ── Modos (Clásico / Extendido / Caos con todas sus variantes) ──────────────
        # Solo Modo Extendido permite voto múltiple; Clásico y Caos (camuflado como Clásico) usan 1 voto
        permite_multivoto = (modo == ModoJuego.EXTENDIDO)

        # Límite de Discord: máximo 25 opciones por Select (hasta 24 jugadores + 1 Voto Nulo)
        opciones = [discord.SelectOption(label=j.display_name, value=str(j.id)) for j in partida.jugadores[:24]]

        # Voto nulo disponible en TODOS los modos
        opciones.append(discord.SelectOption(
            label=t("vote_null_label", g),
            value=VOTO_NULO_ID,
            description=t("vote_null_desc", g),
            emoji="⚪",
        ))

        max_v = min(total, len(opciones)) if permite_multivoto else 1

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

    async def on_timeout(self):
        self.partida.limpiar_memoria()
        self.clear_items()
        self.stop()

    # ─────────────────────────────────────────────────────────────────────────
    #  VOTACIÓN NORMAL — Clásico / Extendido / Caos estándar
    # ─────────────────────────────────────────────────────────────────────────
    async def _registrar_voto(self, inter: discord.Interaction):
        g = inter.guild_id

        # Sección crítica: chequear y registrar el voto bajo lock para
        # evitar que dos votos casi simultáneos (ej. el penúltimo y el
        # último) decidan ambos que "ya votaron todos".
        async with self.partida.lock:
            if not any(j.id == inter.user.id for j in self.partida.jugadores):
                return await inter.response.send_message(t("vote_only_players", g), ephemeral=True)
            if inter.user.id in self.votos_emitidos:
                return await inter.response.send_message(t("vote_already_voted", g), ephemeral=True)

            self.votos_emitidos.add(inter.user.id)

            valores = inter.data.get("values", self.sel_votos.values if hasattr(self, "sel_votos") else [])
            # voto nulo: registrar pero no añadir a ningún acusado
            if VOTO_NULO_ID not in valores:
                for acusado_id in valores:
                    self.votos_urna.setdefault(acusado_id, set()).add(inter.user.id)

            # ── AUTO-VOTO DE BOTS FANTASMA (MODO DEBUG) ──
            for j in self.partida.jugadores:
                if getattr(j, "es_dummy", False) and j.id not in self.votos_emitidos:
                    self.votos_emitidos.add(j.id)
                    # Los dummies votan al mismo que tú o a un sospechoso al azar si tú votaste nulo
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
                # Ya se están mostrando los resultados (ej. justo se completó
                # la votación en paralelo) — no hacer nada más.
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
            self.partida.impostores = [j for j in self.partida.impostores if j.id != exp.id]
            self.partida.jugadores = [j for j in self.partida.jugadores if j.id != exp.id]

        self.partida.rondas_sin_expulsion = 0  # hubo expulsión: resetear estancamiento

        # comprobar victoria tras el empate masivo
        if getattr(self.partida, "caos_todos_impostores", False):
            return await self._pantalla_final(canal, victoria_impostores=True)

        if not self.partida.caos_sin_impostores and len(self.partida.impostores) == 0:
            return await self._pantalla_final(canal, victoria_impostores=False)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        es_caos_mayoria = (
            self.partida.config.modo_juego == ModoJuego.CAOS
            and getattr(self.partida, "_variante_ronda", None) in (
                CaosVariante.CINCUENTA_PORCIENTO,
                CaosVariante.SETENTA_Y_CINCO,
            )
        )
        umbral_victoria = (tripulantes_vivos == 0) if es_caos_mayoria else (len(self.partida.impostores) >= tripulantes_vivos)
        if len(self.partida.impostores) > 0 and umbral_victoria:
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

        es_impostor = any(imp.id == expulsado.id for imp in self.partida.impostores)
        embed_rev   = discord.Embed(color=discord.Color.dark_red())
        if getattr(expulsado, "display_avatar", None) and getattr(expulsado.display_avatar, "url", None):
            embed_rev.set_thumbnail(url=expulsado.display_avatar.url)

        if es_impostor:
            if getattr(self.partida, "caos_todos_impostores", False):
                self.partida.impostores = [j for j in self.partida.impostores if j.id != expulsado.id]
                self.partida.jugadores = [j for j in self.partida.jugadores if j.id != expulsado.id]
                embed_rev.title       = t("results_caos_todos_impostores_title", g)
                embed_rev.description = t("results_caos_todos_impostores_desc",  g, name=expulsado.display_name)
                embed_rev.color       = discord.Color.magenta()
                await canal.send(embed=embed_rev)
                return await self._pantalla_final(canal, victoria_impostores=True)

            self.partida.impostores = [j for j in self.partida.impostores if j.id != expulsado.id]
            self.partida.jugadores = [j for j in self.partida.jugadores if j.id != expulsado.id]

            if len(self.partida.impostores) == 0:
                embed_rev.title       = t("results_impostor_found_title", g)
                embed_rev.description = t("results_impostor_found_desc",  g, name=expulsado.display_name)
                embed_rev.color       = discord.Color.green()
                await canal.send(embed=embed_rev)
                return await self._pantalla_final(canal, victoria_impostores=False)

            embed_rev.title       = t("results_impostor_more_title", g)
            embed_rev.description = t("results_impostor_more_desc",  g,
                                      name=expulsado.display_name)
        else:
            self.partida.jugadores = [j for j in self.partida.jugadores if j.id != expulsado.id]
            embed_rev.title       = t("results_innocent_title", g)
            embed_rev.description = t("results_innocent_desc",  g, name=expulsado.display_name)

        await canal.send(embed=embed_rev)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        es_caos_mayoria = (
            self.partida.config.modo_juego == ModoJuego.CAOS
            and getattr(self.partida, "_variante_ronda", None) in (
                CaosVariante.CINCUENTA_PORCIENTO,
                CaosVariante.SETENTA_Y_CINCO,
            )
        )
        umbral_victoria = (tripulantes_vivos == 0) if es_caos_mayoria else (len(self.partida.impostores) >= tripulantes_vivos)
        if len(self.partida.impostores) > 0 and umbral_victoria:
            return await self._resolver_victoria_impostores(canal, tripulantes_vivos)

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

        # Si tras las expulsiones de esta ronda ya no hay suficientes jugadores
        # para seguir jugando, terminamos. Los impostores que sigan vivos
        # se consideran "escaparon" (ganan); si no quedan, ganan tripulantes.
        if len(self.partida.jugadores) < 3:
            quedan_impostores = len(self.partida.impostores) > 0
            return await self._pantalla_final(canal, victoria_impostores=quedan_impostores)

        # Condición de fin por límite de rondas configurado (1 a 9)
        if self.partida.ronda >= self.partida.config.max_rondas:
            if self.partida.caos_sin_impostores:
                # En 0 impostores o Amigos Borrachos no hay traidores que hayan escapado
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

    # ── Delegación a la pantalla final (módulo aparte) ───────────────────────
    async def _pantalla_final(self, canal: discord.TextChannel, victoria_impostores: bool):
        from .final import mostrar_pantalla_final
        await mostrar_pantalla_final(self.partida, canal, victoria_impostores)
"""
vistas.py — UI completa de PokeImpostor con todos los fixes aplicados
"""
from __future__ import annotations

import asyncio
import discord
from motor_juego import Partida, ModoJuego, Ventaja, DuracionDebate
from i18n import t

TIMEOUT_LOBBY    = 3600
TIMEOUT_VOTACION = 1800
TIMEOUT_DEBATE   = 7200


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS GLOBALES
# ═══════════════════════════════════════════════════════════════════════════════

def _gid(partida: Partida) -> int:
    return partida.canal.guild.id


def _build_embed_lobby(partida: Partida) -> discord.Embed:
    gid = _gid(partida)
    lista = (
        "\n".join(f"• {j.display_name}" for j in partida.jugadores)
        if partida.jugadores else t("lobby_nobody", gid)
    )
    embed = discord.Embed(
        title=t("lobby_title", gid),
        description=t("lobby_desc", gid),
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.add_field(
        name=t("lobby_players_field", gid, count=len(partida.jugadores)),
        value=lista, inline=False,
    )
    embed.set_footer(text=t("lobby_footer", gid))
    return embed


def _build_embed_config(partida: Partida) -> discord.Embed:
    gid = _gid(partida)
    cfg = partida.config
    modo_display = {
        ModoJuego.CLASICO:      t("mode_classic_display",      gid),
        ModoJuego.EXTENDIDO:    t("mode_extended_display",     gid),
        ModoJuego.CAOS:         t("mode_caos_display",         gid),
        ModoJuego.CAOS_JUGADOR: t("mode_caos_jugador_display", gid),
    }
    timer_display = {
        DuracionDebate.SIN_LIMITE: t("timer_none",  gid),
        DuracionDebate.DOS_MIN:    t("timer_2min",  gid),
        DuracionDebate.CINCO_MIN:  t("timer_5min",  gid),
        DuracionDebate.DIEZ_MIN:   t("timer_10min", gid),
    }
    regiones_str = ", ".join(cfg.regiones) if cfg.regiones != ["todas"] else t("region_all", gid)
    embed = discord.Embed(title=t("config_title", gid), color=discord.Color.blurple())
    embed.add_field(name=t("config_mode_label",    gid), value=modo_display.get(cfg.modo_juego, cfg.modo_juego.value), inline=True)
    embed.add_field(name=t("config_hint_label",    gid), value=cfg.ventaja.value,                                      inline=True)
    embed.add_field(name=t("config_regions_label", gid), value=regiones_str,                                           inline=True)
    embed.add_field(name=t("config_timer_label",   gid), value=timer_display.get(cfg.duracion_debate, "—"),            inline=True)
    # Mostrar toggle ebrios solo si el modo es CAOS
    if cfg.modo_juego == ModoJuego.CAOS:
        estado_ebrios = t("caos_ebrios_on", gid) if cfg.caos_ebrios else t("caos_ebrios_off", gid)
        embed.add_field(name=t("caos_ebrios_label", gid), value=estado_ebrios, inline=True)
    return embed


def _build_embed_ronda(partida: Partida) -> discord.Embed:
    gid = _gid(partida)
    modo_display = {
        ModoJuego.CLASICO:      t("mode_classic",      gid),
        ModoJuego.EXTENDIDO:    t("mode_extended",     gid),
        ModoJuego.CAOS:         t("mode_caos",         gid),
        ModoJuego.CAOS_JUGADOR: t("mode_caos_jugador", gid),
    }
    # Si modo CAOS con ebrios activado, mostrar subtítulo especial
    if partida.config.modo_juego == ModoJuego.CAOS and partida.config.caos_ebrios:
        modo_val = t("mode_amigos_ebrios", gid)
    else:
        modo_val = modo_display.get(partida.config.modo_juego, "?")

    embed = discord.Embed(
        title=t("round_title", gid, n=partida.ronda),
        description=t("round_desc", gid),
        color=discord.Color.gold(),
    )
    embed.add_field(name=t("round_mode_field",    gid), value=modo_val,                         inline=True)
    embed.add_field(name=t("round_players_field", gid), value=str(len(partida.jugadores)),      inline=True)
    if partida.config.duracion_debate != DuracionDebate.SIN_LIMITE:
        embed.add_field(
            name=t("round_timer_field", gid),
            value=t("round_timer_value", gid, n=partida.config.duracion_debate.value // 60),
            inline=True,
        )
    return embed


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL DE INSCRIPCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class PanelInscripcion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        gid = _gid(partida)
        self._mk_btn(t("btn_join",   gid), discord.ButtonStyle.success,   self._unirse,   0)
        self._mk_btn(t("btn_leave",  gid), discord.ButtonStyle.secondary,  self._salir,    0)
        self._mk_btn(t("btn_config", gid), discord.ButtonStyle.primary,   self._config,   1)
        self._mk_btn(t("btn_cancel", gid), discord.ButtonStyle.danger,    self._cancelar, 1)

    def _mk_btn(self, label, style, cb, row):
        b = discord.ui.Button(label=label, style=style, row=row)
        b.callback = cb
        self.add_item(b)

    async def on_timeout(self):
        self.partida.limpiar_memoria()

    async def _unirse(self, inter: discord.Interaction):
        gid = inter.guild_id
        if inter.user in self.partida.jugadores:
            return await inter.response.send_message(t("lobby_already_in", gid), ephemeral=True)
        self.partida.jugadores.append(inter.user)
        await inter.response.edit_message(embed=_build_embed_lobby(self.partida))

    async def _salir(self, inter: discord.Interaction):
        gid = inter.guild_id
        if inter.user not in self.partida.jugadores:
            return await inter.response.send_message(t("lobby_not_in", gid), ephemeral=True)
        self.partida.jugadores.remove(inter.user)
        await inter.response.edit_message(embed=_build_embed_lobby(self.partida))

    async def _config(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)
        await inter.response.send_message(
            embed=_build_embed_config(self.partida),
            view=PanelConfiguracion(self.partida),
            ephemeral=True,
        )

    async def _cancelar(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)
        self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(content=t("lobby_cancelled", gid), embed=None, view=None)


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL DE CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class PanelConfiguracion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        gid = _gid(partida)

        sel_modo = discord.ui.Select(
            placeholder=t("sel_gamemode", gid),
            options=[
                discord.SelectOption(label=t("mode_classic",      gid), value=ModoJuego.CLASICO,      description=t("mode_classic_desc",      gid)),
                discord.SelectOption(label=t("mode_extended",     gid), value=ModoJuego.EXTENDIDO,    description=t("mode_extended_desc",     gid)),
                discord.SelectOption(label=t("mode_caos",         gid), value=ModoJuego.CAOS,         description=t("mode_caos_desc",         gid)),
                discord.SelectOption(label=t("mode_caos_jugador", gid), value=ModoJuego.CAOS_JUGADOR, description=t("mode_caos_jugador_desc", gid)),
            ], row=0,
        )
        sel_modo.callback = self._set_modo
        self.add_item(sel_modo)

        sel_pista = discord.ui.Select(
            placeholder=t("sel_hint", gid),
            options=[
                discord.SelectOption(label=t("hint_random",    gid), value=Ventaja.ALEATORIO,    description=t("hint_random_desc", gid)),
                discord.SelectOption(label=t("hint_letter",    gid), value=Ventaja.LETRA),
                discord.SelectOption(label=t("hint_stat_high", gid), value=Ventaja.STAT_ALTA),
                discord.SelectOption(label=t("hint_stat_low",  gid), value=Ventaja.STAT_BAJA),
                discord.SelectOption(label=t("hint_egg",       gid), value=Ventaja.HUEVO),
                discord.SelectOption(label=t("hint_type",      gid), value=Ventaja.TIPO),
                discord.SelectOption(label=t("hint_habitat",   gid), value=Ventaja.HABITAT),
                discord.SelectOption(label=t("hint_region",    gid), value=Ventaja.RANGO_REGION),
                discord.SelectOption(label=t("hint_ability",   gid), value=Ventaja.HABILIDAD),
            ], row=1,
        )
        sel_pista.callback = self._set_pista
        self.add_item(sel_pista)

        sel_region = discord.ui.Select(
            placeholder=t("sel_regions", gid), min_values=1, max_values=10,
            options=[
                discord.SelectOption(label=t("region_all",  gid), value="todas"),
                discord.SelectOption(label=t("region_gen1", gid), value="gen1"),
                discord.SelectOption(label=t("region_gen2", gid), value="gen2"),
                discord.SelectOption(label=t("region_gen3", gid), value="gen3"),
                discord.SelectOption(label=t("region_gen4", gid), value="gen4"),
                discord.SelectOption(label=t("region_gen5", gid), value="gen5"),
                discord.SelectOption(label=t("region_gen6", gid), value="gen6"),
                discord.SelectOption(label=t("region_gen7", gid), value="gen7"),
                discord.SelectOption(label=t("region_gen8", gid), value="gen8"),
                discord.SelectOption(label=t("region_gen9", gid), value="gen9"),
            ], row=2,
        )
        sel_region.callback = self._set_region
        self.add_item(sel_region)

        sel_timer = discord.ui.Select(
            placeholder=t("sel_timer", gid),
            options=[
                discord.SelectOption(label=t("timer_none",  gid), value=str(DuracionDebate.SIN_LIMITE)),
                discord.SelectOption(label=t("timer_2min",  gid), value=str(DuracionDebate.DOS_MIN)),
                discord.SelectOption(label=t("timer_5min",  gid), value=str(DuracionDebate.CINCO_MIN)),
                discord.SelectOption(label=t("timer_10min", gid), value=str(DuracionDebate.DIEZ_MIN)),
            ], row=3,
        )
        sel_timer.callback = self._set_timer
        self.add_item(sel_timer)

        # Toggle: Modo Ebrios — solo visible cuando se selecciona CAOS.
        # Como Discord no permite ocultar items dinámicamente, usamos un botón
        # con estilo que cambia según el estado (gris=off, verde=on).
        # El botón aparece siempre pero solo tiene efecto en modo CAOS.
        self._btn_ebrios = discord.ui.Button(
            label=self._label_ebrios(partida, gid),
            style=discord.ButtonStyle.success if partida.config.caos_ebrios else discord.ButtonStyle.secondary,
            row=4,
        )
        self._btn_ebrios.callback = self._toggle_ebrios
        self.add_item(self._btn_ebrios)

        btn_start = discord.ui.Button(label=t("btn_start_round", gid), style=discord.ButtonStyle.primary, row=4)
        btn_start.callback = self._iniciar
        self.add_item(btn_start)

    @staticmethod
    def _label_ebrios(partida: Partida, gid: int) -> str:
        if partida.config.caos_ebrios:
            return t("caos_ebrios_btn_on", gid)
        return t("caos_ebrios_btn_off", gid)

    async def _set_modo(self, inter: discord.Interaction):
        nuevo_modo = ModoJuego(inter.data["values"][0])
        # Si se sale del modo CAOS, apagar el modificador ebrios
        if nuevo_modo != ModoJuego.CAOS:
            self.partida.config.caos_ebrios = False
        self.partida.config.modo_juego = nuevo_modo
        # Actualizar también el estilo del botón ebrios
        self._btn_ebrios.style = discord.ButtonStyle.secondary
        self._btn_ebrios.label = self._label_ebrios(self.partida, inter.guild_id)
        await inter.response.edit_message(embed=_build_embed_config(self.partida), view=self)

    async def _set_pista(self, inter: discord.Interaction):
        self.partida.config.ventaja = Ventaja(inter.data["values"][0])
        await inter.response.edit_message(embed=_build_embed_config(self.partida))

    async def _set_region(self, inter: discord.Interaction):
        self.partida.config.regiones = inter.data["values"]
        await inter.response.edit_message(embed=_build_embed_config(self.partida))

    async def _set_timer(self, inter: discord.Interaction):
        self.partida.config.duracion_debate = DuracionDebate(int(inter.data["values"][0]))
        await inter.response.edit_message(embed=_build_embed_config(self.partida))

    async def _toggle_ebrios(self, inter: discord.Interaction):
        gid = inter.guild_id
        if self.partida.config.modo_juego != ModoJuego.CAOS:
            return await inter.response.send_message(t("caos_ebrios_only_caos", gid), ephemeral=True)
        self.partida.config.caos_ebrios = not self.partida.config.caos_ebrios
        self._btn_ebrios.label = self._label_ebrios(self.partida, gid)
        self._btn_ebrios.style = (
            discord.ButtonStyle.success if self.partida.config.caos_ebrios
            else discord.ButtonStyle.secondary
        )
        await inter.response.edit_message(embed=_build_embed_config(self.partida), view=self)

    async def _iniciar(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)

        # FIX CRÍTICO: restaurar lista de jugadores desde jugadores_iniciales si
        # venimos de una partida terminada (configurar después de una ronda).
        # jugadores puede estar vacío o reducido por expulsiones.
        if not self.partida.jugadores and self.partida.jugadores_iniciales:
            self.partida.jugadores = self.partida.jugadores_iniciales.copy()

        if len(self.partida.jugadores) < 3:
            return await inter.response.send_message(t("min_players", gid), ephemeral=True)

        await inter.response.edit_message(content=t("config_saved", gid), view=None, embed=None)

        exito = await self.partida.arrancar_ronda()
        if not exito:
            return

        if self.partida.caos_sin_impostores:
            await inter.channel.send(embed=discord.Embed(
                title=t("caos_zero_title", gid),
                description=t("caos_zero_desc", gid),
                color=discord.Color.from_rgb(100, 0, 200),
            ))

        await inter.channel.send(embed=_build_embed_ronda(self.partida), view=PanelDebate(self.partida))


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL DE DEBATE  — fix del timer: asyncio.ensure_future en lugar de get_event_loop
# ═══════════════════════════════════════════════════════════════════════════════

class PanelDebate(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_DEBATE)
        self.partida      = partida
        self._timer_task: asyncio.Task | None = None
        gid = _gid(partida)

        btn_vote = discord.ui.Button(label=t("btn_open_vote", gid), style=discord.ButtonStyle.danger, row=0)
        btn_vote.callback = self._abrir_votacion
        self.add_item(btn_vote)

        # FIX TIMER: usar ensure_future (compatible Python 3.10+)
        if partida.config.duracion_debate != DuracionDebate.SIN_LIMITE:
            self._timer_task = asyncio.ensure_future(
                self._countdown(partida.config.duracion_debate.value)
            )

    async def _countdown(self, segundos: int):
        await asyncio.sleep(segundos)
        if not self.is_finished():
            self.stop()
            gid = _gid(self.partida)
            try:
                await self.partida.canal.send(
                    embed=discord.Embed(
                        title=t("timer_expired_title", gid),
                        description=t("timer_expired_desc", gid),
                        color=discord.Color.orange(),
                    ),
                    view=PanelVotacion(self.partida),
                )
            except Exception as e:
                print(f"[Timer] {e}")

    def stop(self):
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        super().stop()

    async def _abrir_votacion(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)
        self.stop()
        await inter.response.edit_message(view=None)
        await inter.channel.send(
            embed=discord.Embed(
                title=t("vote_title_open", gid),
                description=t("vote_desc", gid, current=0, total=len(self.partida.jugadores)),
                color=discord.Color.red(),
            ),
            view=PanelVotacion(self.partida),
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL DE VOTACIÓN
#  - fix voto doble en clásico: max_values=1
#  - fix voto nulo: opción "Abstain/Voto nulo" solo en clásico
#  - fix empate en Caos: NO expulsar nadie, solo continuar
# ═══════════════════════════════════════════════════════════════════════════════

VOTO_NULO_ID = "voto_nulo"

class PanelVotacion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_VOTACION)
        self.partida         = partida
        self.votos_emitidos: set[int]            = set()
        self.votos_urna:     dict[str, set[int]] = {}
        gid   = _gid(partida)
        modo  = partida.config.modo_juego
        total = len(partida.jugadores)

        # ── Modo CAOS_JUGADOR: solo el detective vota, elige quién cree que es el objetivo ──
        if modo == ModoJuego.CAOS_JUGADOR:
            # Solo el detective (impostor) puede votar, y elige quién cree que es el objetivo
            # Los tripulantes no votan — la ronda termina cuando el detective adivina o pasa
            opciones_cj = [
                discord.SelectOption(label=j.display_name, value=str(j.id))
                for j in partida.jugadores
                if j not in partida.impostores  # el detective no puede votarse a sí mismo
            ]
            opciones_cj.append(discord.SelectOption(
                label=t("vote_null_label", gid),
                value=VOTO_NULO_ID,
                description=t("caos_jugador_pass_desc", gid),
                emoji="⚪",
            ))
            sel_cj = discord.ui.Select(
                placeholder=t("caos_jugador_vote_placeholder", gid),
                min_values=1, max_values=1,
                options=opciones_cj,
                row=0,
            )
            sel_cj.callback = self._voto_caos_jugador
            self.add_item(sel_cj)
            self.sel_votos = sel_cj
            # El botón de forzar cierre sigue disponible para el admin
            btn_forzar = discord.ui.Button(label=t("btn_force_close", gid), style=discord.ButtonStyle.secondary, row=1)
            btn_forzar.callback = self._forzar_cierre_cj
            self.add_item(btn_forzar)
            return  # no construir el select normal

        # ── Modos normales ────────────────────────────────────────────────────
        es_clasico = (modo == ModoJuego.CLASICO)
        max_v      = 1 if es_clasico else total

        opciones = [discord.SelectOption(label=j.display_name, value=str(j.id)) for j in partida.jugadores]

        # Voto nulo disponible en TODOS los modos
        opciones.append(discord.SelectOption(
            label=t("vote_null_label", gid),
            value=VOTO_NULO_ID,
            description=t("vote_null_desc", gid),
            emoji="⚪",
        ))

        sel = discord.ui.Select(
            placeholder=t("vote_placeholder", gid),
            min_values=1,
            max_values=max_v,
            options=opciones,
            row=0,
        )
        sel.callback = self._registrar_voto
        self.add_item(sel)
        self.sel_votos = sel

        btn_forzar = discord.ui.Button(label=t("btn_force_close", gid), style=discord.ButtonStyle.secondary, row=1)
        btn_forzar.callback = self._forzar_cierre
        self.add_item(btn_forzar)

    async def _registrar_voto(self, inter: discord.Interaction):
        gid = inter.guild_id
        if inter.user not in self.partida.jugadores:
            return await inter.response.send_message(t("vote_only_players", gid), ephemeral=True)
        if inter.user.id in self.votos_emitidos:
            return await inter.response.send_message(t("vote_already_voted", gid), ephemeral=True)

        self.votos_emitidos.add(inter.user.id)

        valores = self.sel_votos.values
        # voto nulo: registrar pero no añadir a ningún acusado
        if VOTO_NULO_ID not in valores:
            for acusado_id in valores:
                self.votos_urna.setdefault(acusado_id, set()).add(inter.user.id)

        total  = len(self.partida.jugadores)
        actual = len(self.votos_emitidos)

        await inter.response.send_message(t("vote_registered", gid), ephemeral=True)
        await inter.message.edit(embed=discord.Embed(
            title=t("vote_title_open", gid),
            description=t("vote_desc", gid, current=actual, total=total),
            color=discord.Color.red(),
        ))

        if actual == total:
            await self._mostrar_resultados(inter.channel, inter.message)

    async def _forzar_cierre(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("vote_only_admin_force", gid), ephemeral=True)
        actual = len(self.votos_emitidos)
        total  = len(self.partida.jugadores)
        await inter.response.send_message(t("vote_force_closed", gid, current=actual, total=total))
        await self._mostrar_resultados(inter.channel, inter.message)

    # ── Votación especial CAOS_JUGADOR ────────────────────────────────────────
    async def _voto_caos_jugador(self, inter: discord.Interaction):
        gid = inter.guild_id
        # Solo el detective puede votar
        if inter.user not in self.partida.impostores:
            return await inter.response.send_message(
                t("caos_jugador_only_detective", gid), ephemeral=True
            )
        if inter.user.id in self.votos_emitidos:
            return await inter.response.send_message(t("vote_already_voted", gid), ephemeral=True)

        self.votos_emitidos.add(inter.user.id)
        valor = self.sel_votos.values[0]

        self.clear_items()
        self.stop()
        try:
            await inter.message.edit(view=None)
        except Exception:
            pass

        gid = inter.guild_id
        objetivo = self.partida.objetivo_humano

        if valor == VOTO_NULO_ID:
            # Detective pasa — los tripulantes ganan
            await inter.response.send_message(
                embed=discord.Embed(
                    title=t("caos_jugador_pass_title", gid),
                    description=t("caos_jugador_pass_desc_result", gid,
                                  target=f"**{objetivo.display_name}**"),
                    color=discord.Color.green(),
                )
            )
        else:
            adivinado = discord.utils.get(self.partida.jugadores, id=int(valor))
            acerto    = (adivinado == objetivo)
            if acerto:
                await inter.response.send_message(
                    embed=discord.Embed(
                        title=t("caos_jugador_correct_title", gid),
                        description=t("caos_jugador_correct_desc", gid,
                                      detective=f"**{inter.user.display_name}**",
                                      target=f"**{objetivo.display_name}**"),
                        color=discord.Color.from_rgb(180, 30, 30),
                    ).set_thumbnail(url=objetivo.display_avatar.url)
                )
            else:
                nombre_adivinado = adivinado.display_name if adivinado else "???"
                await inter.response.send_message(
                    embed=discord.Embed(
                        title=t("caos_jugador_wrong_title", gid),
                        description=t("caos_jugador_wrong_desc", gid,
                                      guessed=f"**{nombre_adivinado}**",
                                      target=f"**{objetivo.display_name}**"),
                        color=discord.Color.green(),
                    ).set_thumbnail(url=objetivo.display_avatar.url)
                )

        return await self._pantalla_final(inter.channel)

    async def _forzar_cierre_cj(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("vote_only_admin_force", gid), ephemeral=True)
        await inter.response.send_message(t("caos_jugador_admin_skip", gid))
        self.clear_items()
        self.stop()
        try:
            await inter.message.edit(view=None)
        except Exception:
            pass
        await self._pantalla_final(inter.channel)

    async def _mostrar_resultados(self, canal: discord.TextChannel, mensaje: discord.Message):
        gid = _gid(self.partida)
        self.clear_items()
        self.stop()
        try:
            await mensaje.edit(view=None)
        except Exception:
            pass

        conteo = {uid: len(v) for uid, v in self.votos_urna.items()}

        # Desglose visual
        desglose_lines: list[str] = []
        if conteo:
            for uid_str, votos in sorted(conteo.items(), key=lambda x: -x[1]):
                miembro = discord.utils.get(self.partida.jugadores_iniciales, id=int(uid_str))
                nombre  = miembro.display_name if miembro else f"ID:{uid_str}"
                barra   = "█" * votos
                desglose_lines.append(f"`{barra:<10}` " + t("results_vote_field", gid, votes=votos, name=nombre))

        await canal.send(embed=discord.Embed(
            title=t("results_tally_title", gid),
            description="\n".join(desglose_lines) or t("results_no_votes", gid),
            color=discord.Color.orange(),
        ))

        if not conteo:
            await canal.send(t("results_nobody_voted", gid))
            return await self._siguiente_ronda(canal)

        max_votos  = max(conteo.values())
        candidatos = [k for k, v in conteo.items() if v == max_votos]

        # ── Lógica de empate ────────────────────────────────────────────────────
        if len(candidatos) > 1:
            modo = self.partida.config.modo_juego
            # En CAOS y EXTENDIDO: empate con votos > 0 → todos los empatados salen
            if modo in (ModoJuego.CAOS, ModoJuego.EXTENDIDO):
                expulsados_empate: list[discord.Member] = []
                for uid_str in candidatos:
                    m = discord.utils.get(self.partida.jugadores, id=int(uid_str))
                    if m:
                        expulsados_empate.append(m)

                nombres_exp = ", ".join(f"**{m.display_name}**" for m in expulsados_empate)
                await canal.send(embed=discord.Embed(
                    title=t("results_tie_multi_title", gid),
                    description=t("results_tie_multi_desc", gid, names=nombres_exp),
                    color=discord.Color.dark_orange(),
                ))

                # procesar cada expulsado
                for exp in expulsados_empate:
                    if exp in self.partida.impostores:
                        self.partida.impostores.remove(exp)
                    if exp in self.partida.jugadores:
                        self.partida.jugadores.remove(exp)

                # comprobar victoria tras el empate masivo
                if len(self.partida.impostores) == 0:
                    return await self._pantalla_final(canal)
                tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
                if len(self.partida.impostores) >= tripulantes_vivos:
                    await canal.send(embed=discord.Embed(
                        title=t("results_impostors_win_title", gid),
                        description=t("results_impostors_win_desc", gid),
                        color=discord.Color.from_rgb(50, 0, 0),
                    ))
                    return await self._pantalla_final(canal)
                return await self._siguiente_ronda(canal)
            else:
                # CLASICO y CAOS_JUGADOR: empate = nadie sale
                await canal.send(embed=discord.Embed(
                    title=t("results_tie_title", gid),
                    description=t("results_tie_desc", gid),
                    color=discord.Color.greyple(),
                ))
                return await self._siguiente_ronda(canal)

        expulsado = discord.utils.get(self.partida.jugadores, id=int(candidatos[0]))
        if expulsado is None:
            await canal.send(t("results_left_server", gid))
            return await self._siguiente_ronda(canal)

        es_impostor = expulsado in self.partida.impostores
        embed_rev   = discord.Embed(color=discord.Color.dark_red())
        embed_rev.set_thumbnail(url=expulsado.display_avatar.url)

        if es_impostor:
            self.partida.impostores.remove(expulsado)
            self.partida.jugadores.remove(expulsado)

            if len(self.partida.impostores) == 0:
                embed_rev.title       = t("results_impostor_found_title", gid)
                embed_rev.description = t("results_impostor_found_desc",  gid, name=expulsado.display_name)
                embed_rev.color       = discord.Color.green()
                await canal.send(embed=embed_rev)
                return await self._pantalla_final(canal)
            else:
                embed_rev.title       = t("results_impostor_more_title", gid)
                embed_rev.description = t("results_impostor_more_desc",  gid,
                                          name=expulsado.display_name,
                                          remaining=len(self.partida.impostores))
        else:
            self.partida.jugadores.remove(expulsado)
            embed_rev.title       = t("results_innocent_title", gid)
            embed_rev.description = t("results_innocent_desc",  gid, name=expulsado.display_name)

        await canal.send(embed=embed_rev)

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        if len(self.partida.impostores) >= tripulantes_vivos:
            await canal.send(embed=discord.Embed(
                title=t("results_impostors_win_title", gid),
                description=t("results_impostors_win_desc", gid),
                color=discord.Color.from_rgb(50, 0, 0),
            ))
            return await self._pantalla_final(canal)

        if self.partida.config.modo_juego == ModoJuego.CAOS and es_impostor:
            await self._pregunta_caos(canal)
        else:
            await self._siguiente_ronda(canal)

    async def _siguiente_ronda(self, canal: discord.TextChannel):
        gid = _gid(self.partida)
        self.partida.ronda += 1
        await canal.send(
            embed=discord.Embed(
                title=t("round_next_title", gid, n=self.partida.ronda),
                description=t("round_next_desc", gid),
                color=discord.Color.gold(),
            ),
            view=PanelDebate(self.partida),
        )

    async def _pregunta_caos(self, canal: discord.TextChannel):
        gid    = _gid(self.partida)
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
                await _final(i.channel)

        view = VotoCaos(self.partida)
        view.b_si.label = t("btn_caos_yes", gid)
        view.b_no.label = t("btn_caos_no",  gid)
        await canal.send(embed=discord.Embed(
            title=t("caos_question_title", gid),
            description=t("caos_question_desc", gid),
            color=discord.Color.from_rgb(100, 0, 200),
        ), view=view)

    async def _pantalla_final(self, canal: discord.TextChannel):
        gid  = _gid(self.partida)
        modo = self.partida.config.modo_juego
        es_ebrios = (modo == ModoJuego.CAOS and self.partida.config.caos_ebrios)

        embed = discord.Embed(title=t("final_title", gid), color=discord.Color.from_rgb(255, 203, 5))

        if es_ebrios:
            lines = []
            for j in self.partida.jugadores_iniciales:
                dp = self.partida.pokemons_ebrios.get(j.id)
                if dp:
                    lines.append(f"• **{j.display_name}** → {dp['nombre']} ({' / '.join(dp['tipos'])})")
            embed.add_field(name=t("final_ebrios_field", gid), value="\n".join(lines) or "—", inline=False)

        elif modo == ModoJuego.CAOS_JUGADOR:
            objetivo = self.partida.objetivo_humano
            if objetivo:
                embed.add_field(name=t("final_caos_jugador_field", gid), value=f"👤 **{objetivo.display_name}**", inline=False)
                embed.set_image(url=objetivo.display_avatar.url)
        else:
            dp = self.partida.datos_pokemon
            if dp:
                embed.set_image(url=dp["sprite"])
                embed.add_field(
                    name=t("final_pokemon_field", gid),
                    value=f"**{dp['nombre']}**\n{' / '.join(dp['tipos'])} · {dp['gen']}",
                    inline=False,
                )

        lista_imp  = "\n".join(f"🔪 {j.display_name}" for j in self.partida.impostores_iniciales)
        lista_trip = "\n".join(
            f"✅ {j.display_name}"
            for j in self.partida.jugadores_iniciales
            if j not in self.partida.impostores_iniciales
        )
        embed.add_field(name=t("final_impostors_field", gid), value=lista_imp  or t("final_none_caos", gid), inline=True)
        embed.add_field(name=t("final_crew_field",      gid), value=lista_trip or "—",                       inline=True)
        embed.set_footer(text=t("final_footer", gid, n=self.partida.ronda))
        await canal.send(embed=embed, view=PanelPostRonda(self.partida))


# ═══════════════════════════════════════════════════════════════════════════════
#  PANEL POST-RONDA
# ═══════════════════════════════════════════════════════════════════════════════

class PanelPostRonda(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida
        gid = _gid(partida)

        b1 = discord.ui.Button(label=t("btn_rematch",       gid), style=discord.ButtonStyle.success, row=0)
        b2 = discord.ui.Button(label=t("btn_change_config", gid), style=discord.ButtonStyle.primary,  row=0)
        b3 = discord.ui.Button(label=t("btn_end_session",   gid), style=discord.ButtonStyle.danger,   row=0)
        b1.callback = self._revancha
        b2.callback = self._config
        b3.callback = self._cerrar
        self.add_item(b1); self.add_item(b2); self.add_item(b3)

    async def _revancha(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)
        await inter.response.edit_message(view=None)
        # restaurar todos los jugadores iniciales para la revancha
        self.partida.jugadores = self.partida.jugadores_iniciales.copy()
        self.partida.ronda    += 1
        exito = await self.partida.arrancar_ronda()
        if not exito:
            return
        if self.partida.caos_sin_impostores:
            await inter.channel.send(embed=discord.Embed(
                title=t("caos_zero_title", gid),
                description=t("caos_zero_desc", gid),
                color=discord.Color.from_rgb(100, 0, 200),
            ))
        await inter.channel.send(
            embed=discord.Embed(
                title=t("round_rematch_title", gid, n=self.partida.ronda),
                description=t("round_rematch_desc", gid),
                color=discord.Color.gold(),
            ),
            view=PanelDebate(self.partida),
        )

    async def _config(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)
        await inter.response.send_message(
            embed=_build_embed_config(self.partida),
            view=PanelConfiguracion(self.partida),
            ephemeral=True,
        )

    async def _cerrar(self, inter: discord.Interaction):
        gid = inter.guild_id
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(t("only_admin", gid), ephemeral=True)
        self.partida.jugadores = []
        self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(view=None)
        await inter.channel.send(embed=discord.Embed(
            title=t("session_closed_title", gid),
            description=t("session_closed_desc", gid),
            color=discord.Color.from_rgb(60, 60, 60),
        ))
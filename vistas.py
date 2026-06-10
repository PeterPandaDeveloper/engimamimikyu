import discord
from motor_juego import Partida, ModoJuego, Ventaja

# ── Timeouts centralizados ───────────────────────────────────────────────────
TIMEOUT_LOBBY    = 3600   # 60 min — lobby puede quedarse abierto un rato
TIMEOUT_VOTACION = 1800   # 30 min — una votación no debería tardar más


class PanelInscripcion(discord.ui.View):
    def __init__(self, partida: Partida):
        # Fix 6: timeout en lugar de None
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida

    async def on_timeout(self):
        """Limpia la partida si el lobby expira sin que nadie lo cierre."""
        if hasattr(self.partida, 'limpiar_memoria'):
            self.partida.limpiar_memoria()

    @discord.ui.button(label="Unirse al Lobby", style=discord.ButtonStyle.success)
    async def btn_unirse(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user not in self.partida.jugadores:
            self.partida.jugadores.append(inter.user)
            await self.actualizar_lobby(inter)
        else:
            await inter.response.send_message("Ya estás dentro.", ephemeral=True)

    @discord.ui.button(label="Salir", style=discord.ButtonStyle.danger)
    async def btn_salir(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user in self.partida.jugadores:
            self.partida.jugadores.remove(inter.user)
            await self.actualizar_lobby(inter)
        else:
            await inter.response.send_message("No estás en el lobby.", ephemeral=True)

    @discord.ui.button(label="⚙️ Configurar (Admin)", style=discord.ButtonStyle.secondary, row=1)
    async def btn_config(self, inter: discord.Interaction, btn: discord.ui.Button):
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message("Solo admins pueden configurar la partida.", ephemeral=True)
        await inter.response.send_message(view=PanelConfiguracion(self.partida), ephemeral=True)

    @discord.ui.button(label="❌ Cancelar Lobby", style=discord.ButtonStyle.danger, row=1)
    async def btn_cancelar(self, inter: discord.Interaction, btn: discord.ui.Button):
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message("Solo admins pueden cancelar el lobby.", ephemeral=True)
        if hasattr(self.partida, 'limpiar_memoria'):
            self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(content="🛑 **El lobby ha sido cancelado por un administrador.**", embed=None, view=None)

    async def actualizar_lobby(self, inter: discord.Interaction):
        embed = inter.message.embeds[0]
        embed.description = f"Un juego está a punto de empezar.\n**Jugadores en el lobby: {len(self.partida.jugadores)}**"
        await inter.response.edit_message(embed=embed)


class PanelConfiguracion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida

    # Fix 4: valores del select usan ModoJuego Enum
    @discord.ui.select(placeholder="Modo de Juego", options=[
        discord.SelectOption(label="Clásico",   value=ModoJuego.CLASICO),
        discord.SelectOption(label="Extendido", value=ModoJuego.EXTENDIDO),
        discord.SelectOption(label="Caos",      value=ModoJuego.CAOS),
    ], row=0)
    async def sel_modo(self, inter: discord.Interaction, sel: discord.ui.Select):
        self.partida.config['modo_juego'] = ModoJuego(sel.values[0])
        await inter.response.defer()

    @discord.ui.select(placeholder="Ventaja del Impostor", options=[
        discord.SelectOption(label="Aleatorio cada ronda", value=Ventaja.ALEATORIO),
        discord.SelectOption(label="Letra Inicial",        value=Ventaja.LETRA),
        discord.SelectOption(label="Estadística más alta", value=Ventaja.STAT_ALTA),
        discord.SelectOption(label="Grupo Huevo",          value=Ventaja.HUEVO),
        discord.SelectOption(label="Tipo",                 value=Ventaja.TIPO),
        discord.SelectOption(label="Rango de Región",      value=Ventaja.RANGO_REGION),
    ], row=1)
    async def sel_pista(self, inter: discord.Interaction, sel: discord.ui.Select):
        self.partida.config['ventaja'] = Ventaja(sel.values[0])
        await inter.response.defer()

    @discord.ui.select(placeholder="Regiones (Elige varias)", min_values=1, max_values=10, options=[
        discord.SelectOption(label="Todas (1-9)",    value="todas"),
        discord.SelectOption(label="Kanto (Gen 1)",  value="gen1"),
        discord.SelectOption(label="Johto (Gen 2)",  value="gen2"),
        discord.SelectOption(label="Hoenn (Gen 3)",  value="gen3"),
        discord.SelectOption(label="Sinnoh (Gen 4)", value="gen4"),
        discord.SelectOption(label="Teselia (Gen 5)",value="gen5"),
        discord.SelectOption(label="Kalos (Gen 6)",  value="gen6"),
        discord.SelectOption(label="Alola (Gen 7)",  value="gen7"),
        discord.SelectOption(label="Galar (Gen 8)",  value="gen8"),
        discord.SelectOption(label="Paldea (Gen 9)", value="gen9"),
    ], row=2)
    async def sel_region(self, inter: discord.Interaction, sel: discord.ui.Select):
        self.partida.config['regiones'] = sel.values
        await inter.response.defer()

    @discord.ui.button(label="🚀 INICIAR RONDA", style=discord.ButtonStyle.primary, row=3)
    async def btn_iniciar(self, inter: discord.Interaction, btn: discord.ui.Button):
        # Fix 5: verificar admin aquí también
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message("Solo admins pueden iniciar la ronda.", ephemeral=True)

        if len(self.partida.jugadores) < 3:
            return await inter.response.send_message("Mínimo 3 jugadores para iniciar.", ephemeral=True)

        await inter.response.edit_message(content="Iniciando ronda...", view=None)

        # Fix 3: arrancar_ronda ahora devuelve False si la API falla
        exito = await self.partida.arrancar_ronda()
        if not exito:
            return  # El error ya fue anunciado en el canal por motor_juego

        await inter.channel.send(
            embed=discord.Embed(
                title=f"🏆 RONDA {self.partida.ronda}",
                description=(
                    "La ronda ha iniciado. Tómense su tiempo, pueden usar un canal de texto o hablar por voz.\n"
                    "Cuando estén listos, abran la votación."
                ),
                color=discord.Color.gold()
            ),
            view=PanelAbreVotacion(self.partida)
        )


class PanelAbreVotacion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_VOTACION)
        self.partida = partida

    @discord.ui.button(label="🗳️ Iniciar Votación", style=discord.ButtonStyle.danger)
    async def btn_votar(self, inter: discord.Interaction, btn: discord.ui.Button):
        self.stop()
        await inter.response.edit_message(view=None)
        await inter.channel.send(
            content=f"🗳️ **VOTACIÓN ABIERTA** (0/{len(self.partida.jugadores)} votos registrados)",
            view=PanelVotacion(self.partida)
        )


class PanelVotacion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_VOTACION)
        self.partida       = partida
        self.votos_emitidos = set()   # quién ya votó
        # Fix 1: dict {acusado_id: set(votantes_ids)} — peso 1 por jugador, sin importar cuántos seleccione
        self.votos_urna: dict[str, set[int]] = {}

        opciones = [
            discord.SelectOption(label=j.display_name, value=str(j.id))
            for j in partida.jugadores
        ]
        self.sel_votos = discord.ui.Select(
            placeholder="Selecciona a tus sospechosos...",
            min_values=0,
            max_values=len(partida.jugadores),
            options=opciones
        )
        self.sel_votos.callback = self.registrar_voto
        self.add_item(self.sel_votos)

    async def registrar_voto(self, inter: discord.Interaction):
        if inter.user not in self.partida.jugadores:
            return await inter.response.send_message("👻 Los muertos y espectadores no votan.", ephemeral=True)

        if inter.user.id in self.votos_emitidos:
            return await inter.response.send_message("Ya votaste.", ephemeral=True)

        self.votos_emitidos.add(inter.user.id)

        # Fix 1: cada acusado recibe UNA entrada del votante (no múltiples pesos)
        for acusado_id in self.sel_votos.values:
            if acusado_id not in self.votos_urna:
                self.votos_urna[acusado_id] = set()
            self.votos_urna[acusado_id].add(inter.user.id)

        total  = len(self.partida.jugadores)
        actual = len(self.votos_emitidos)

        await inter.response.send_message("Voto anónimo registrado.", ephemeral=True)
        await inter.message.edit(content=f"🗳️ **VOTACIÓN ABIERTA** ({actual}/{total} votos registrados)")

        if actual == total:
            self.clear_items()
            btn_res = discord.ui.Button(label="Mostrar Resultados", style=discord.ButtonStyle.primary)
            btn_res.callback = self.mostrar_resultados
            self.add_item(btn_res)
            await inter.message.edit(view=self)

    async def mostrar_resultados(self, inter: discord.Interaction):
        # Fix 1: conteo correcto — cada set tiene los IDs únicos de votantes
        conteo = {uid: len(votantes) for uid, votantes in self.votos_urna.items()}

        if not conteo:
            await inter.response.send_message("Nadie votó a nadie. Saltando...")
            return await self.evaluar_continuacion(inter.channel)

        max_votos  = max(conteo.values())
        candidatos = [k for k, v in conteo.items() if v == max_votos]

        if len(candidatos) > 1:
            await inter.channel.send("⚖️ Empate. Nadie es expulsado.")
            return await self.evaluar_continuacion(inter.channel)

        expulsado   = discord.utils.get(self.partida.jugadores, id=int(candidatos[0]))
        es_impostor = expulsado in self.partida.impostores

        embed = discord.Embed(title="Resultados del Sufragio", color=discord.Color.red())
        embed.set_thumbnail(url=expulsado.display_avatar.url)

        if es_impostor:
            self.partida.impostores.remove(expulsado)
            self.partida.jugadores.remove(expulsado)

            if len(self.partida.impostores) == 0:
                embed.description = (
                    f"**{expulsado.display_name} SÍ ERA IMPOSTOR.**\n\n"
                    "🎉 ¡Felicidades! **El Zoroark salió de su madriguera y fue revelado.**"
                )
                await inter.response.edit_message(view=None)
                await self.pantalla_final(inter.channel, embed)
                return
            else:
                embed.description = f"**{expulsado.display_name} SÍ ERA IMPOSTOR.**\n\nQuedan más traidores..."
        else:
            self.partida.jugadores.remove(expulsado)
            embed.description = f"**{expulsado.display_name} NO ERA IMPOSTOR.**\n\n🐘 **El Donphan sigue en la sala.**"

        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        if len(self.partida.impostores) >= tripulantes_vivos:
            embed.description += "\n\n💀 **¡LOS IMPOSTORES HAN TOMADO EL CONTROL!** Ya son mayoría. Han ganado."
            await inter.response.edit_message(view=None)
            await self.pantalla_final(inter.channel, embed)
            return

        await inter.response.edit_message(view=None)
        await inter.channel.send(embed=embed)

        if self.partida.config.get('modo_juego') == ModoJuego.CAOS and es_impostor:
            await self.pregunta_caos(inter.channel)
        else:
            await self.evaluar_continuacion(inter.channel)

    async def evaluar_continuacion(self, canal: discord.TextChannel):
        self.partida.ronda += 1
        await canal.send(f"Iniciando Ronda {self.partida.ronda}...", view=PanelAbreVotacion(self.partida))

    async def pregunta_caos(self, canal: discord.TextChannel):
        metodo_final = self.pantalla_final

        class VotoCaos(discord.ui.View):
            def __init__(self, partida: Partida):
                super().__init__(timeout=TIMEOUT_VOTACION)
                self.p = partida

            @discord.ui.button(label="Sí, hay más", style=discord.ButtonStyle.danger)
            async def b_si(self, i: discord.Interaction, b: discord.ui.Button):
                await i.response.edit_message(content="El juego continúa...", view=None)
                self.p.ronda += 1
                await i.channel.send(view=PanelAbreVotacion(self.p))

            @discord.ui.button(label="No, era el último", style=discord.ButtonStyle.success)
            async def b_no(self, i: discord.Interaction, b: discord.ui.Button):
                await i.response.edit_message(content="Terminando juego...", view=None)
                await metodo_final(i.channel)

        await canal.send("🔥 **Modo Caos:** ¿Creen que hay MÁS impostores ocultos?", view=VotoCaos(self.partida))

    async def pantalla_final(self, canal: discord.TextChannel, embed_pre: discord.Embed = None):
        if embed_pre:
            await canal.send(embed=embed_pre)

        dp    = self.partida.datos_pokemon
        embed = discord.Embed(title="🚨 JUEGO TERMINADO 🚨", color=discord.Color.dark_theme())
        embed.set_thumbnail(url=dp['sprite'])
        embed.add_field(name="El Pokémon Secreto era:", value=f"**{dp['nombre']}**", inline=False)

        lista_imp  = "\n".join([f"🔪 {imp.display_name}" for imp in self.partida.impostores_iniciales])
        lista_trip = "\n".join([
            f"✅ {j.display_name}"
            for j in self.partida.jugadores_iniciales
            if j not in self.partida.impostores_iniciales
        ])
        embed.add_field(name="Los Impostores Eran:", value=lista_imp  or "Ninguno", inline=True)
        embed.add_field(name="Los Amigos Eran:",     value=lista_trip or "Ninguno", inline=True)

        await canal.send(embed=embed, view=PanelPostRonda(self.partida))


class PanelPostRonda(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=TIMEOUT_LOBBY)
        self.partida = partida

    @discord.ui.button(label="🔄 Revancha Rápida", style=discord.ButtonStyle.success, row=0)
    async def btn_revancha(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        self.partida.jugadores = self.partida.jugadores_iniciales.copy()
        self.partida.ronda    += 1

        exito = await self.partida.arrancar_ronda()
        if not exito:
            return

        embed = discord.Embed(
            title=f"🏆 RONDA {self.partida.ronda} (REVANCHA)",
            description="¡Nueva partida iniciada con los mismos jugadores!\nRevisen sus DMs.",
            color=discord.Color.gold()
        )
        await inter.channel.send(embed=embed, view=PanelAbreVotacion(self.partida))

    @discord.ui.button(label="⚙️ Cambiar Configuración", style=discord.ButtonStyle.primary, row=0)
    async def btn_config(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        await inter.channel.send(
            embed=discord.Embed(
                title="⚙️ Mesa del Game Master",
                description="Ajusten las reglas para la siguiente partida.",
                color=discord.Color.blue()
            ),
            view=PanelConfiguracion(self.partida)
        )

    @discord.ui.button(label="❌ Terminar de Jugar", style=discord.ButtonStyle.danger, row=0)
    async def btn_cerrar(self, inter: discord.Interaction, btn: discord.ui.Button):
        self.partida.jugadores = []
        if hasattr(self.partida, 'limpiar_memoria'):
            self.partida.limpiar_memoria()
        self.stop()
        await inter.response.edit_message(view=None)
        await inter.channel.send("🧹 **El lobby ha sido cerrado.** ¡Gracias por jugar! Usen `/impregister` para abrir uno nuevo.")
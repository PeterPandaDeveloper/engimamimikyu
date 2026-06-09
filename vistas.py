import discord
from motor_juego import Partida

class PanelInscripcion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__(timeout=None)
        self.partida = partida

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

    @discord.ui.button(label="⚙️ Configurar (Admin)", style=discord.ButtonStyle.secondary, row=1)
    async def btn_config(self, inter: discord.Interaction, btn: discord.ui.Button):
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message("Solo admins.", ephemeral=True)
        await inter.response.send_message(view=PanelConfiguracion(self.partida), ephemeral=True)

    async def actualizar_lobby(self, inter):
        embed = inter.message.embeds[0]
        embed.description = f"Un juego está a punto de empezar.\n**Jugadores en el lobby: {len(self.partida.jugadores)}**"
        await inter.response.edit_message(embed=embed)


class PanelConfiguracion(discord.ui.View):
    def __init__(self, partida: Partida):
        super().__init__()
        self.partida = partida

    @discord.ui.select(placeholder="Modo de Juego", options=[
        discord.SelectOption(label="Clásico", value="classico", description="Un solo impostor"),
        discord.SelectOption(label="Extendido", value="extendido", description="Escala con jugadores, nunca 0 o todos"),
        discord.SelectOption(label="Caos", value="caos", description="Aleatorio total (0 a Todos)")
    ], row=0)
    async def sel_modo(self, inter, sel): self.partida.config['modo_juego'] = sel.values[0]; await inter.response.defer()

    @discord.ui.select(placeholder="Ventaja del Impostor", options=[
        discord.SelectOption(label="Aleatorio cada ronda", value="aleatorio"),
        discord.SelectOption(label="Letra Inicial", value="letra"),
        discord.SelectOption(label="Estadística más alta", value="stat_alta"),
        discord.SelectOption(label="Grupo Huevo", value="huevo"),
        discord.SelectOption(label="Tipo", value="tipo"),
        discord.SelectOption(label="Rango de Región", value="rango_region")
    ], row=1)
    async def sel_pista(self, inter, sel): self.partida.config['ventaja'] = sel.values[0]; await inter.response.defer()

    @discord.ui.button(label="🚀 INICIAR RONDA", style=discord.ButtonStyle.primary, row=2)
    async def btn_iniciar(self, inter, btn):
        if len(self.partida.jugadores) < 3: return await inter.response.send_message("Mínimo 3 jugadores.")
        await self.partida.arrancar_ronda()
        await inter.channel.send(embed=discord.Embed(
            title=f"🏆 RONDA {self.partida.ronda}", 
            description="La ronda ha iniciado. Tómense su tiempo, pueden usar un canal de texto o hablar por voz.\nCuando estén listos, abran la votación.",
            color=discord.Color.gold()
        ), view=PanelAbreVotacion(self.partida))
        await inter.response.edit_message(content="Juego iniciado.", view=None)


class PanelAbreVotacion(discord.ui.View):
    def __init__(self, partida):
        super().__init__(timeout=None)
        self.partida = partida

    @discord.ui.button(label="🗳️ Iniciar Votación", style=discord.ButtonStyle.danger)
    async def btn_votar(self, inter, btn):
        await inter.response.edit_message(view=None)
        await inter.channel.send(
            content=f"🗳️ **VOTACIÓN ABIERTA** (0/{len(self.partida.jugadores)} votos registrados)",
            view=PanelVotacion(self.partida)
        )


class PanelVotacion(discord.ui.View):
    def __init__(self, partida):
        super().__init__(timeout=None)
        self.partida = partida
        self.votos_emitidos = set() # Rastrea QUIÉN ya votó
        self.votos_urna = []        # Urna secreta de votos (IDs de los acusados)
        
        # Permitir elegir desde 0 (Ninguno) hasta todos los jugadores
        opciones = [discord.SelectOption(label=j.display_name, value=str(j.id)) for j in partida.jugadores]
        self.sel_votos = discord.ui.Select(
            placeholder="Selecciona a tus sospechosos...", 
            min_values=0, max_values=len(partida.jugadores), options=opciones
        )
        self.sel_votos.callback = self.registrar_voto
        self.add_item(self.sel_votos)

    async def registrar_voto(self, inter):
        if inter.user.id in self.votos_emitidos:
            return await inter.response.send_message("Ya votaste.", ephemeral=True)
            
        self.votos_emitidos.add(inter.user.id)
        self.votos_urna.extend(self.sel_votos.values) # Guarda las selecciones
        
        total = len(self.partida.jugadores)
        actual = len(self.votos_emitidos)
        
        await inter.response.send_message("Voto anónimo registrado.", ephemeral=True)
        await inter.message.edit(content=f"🗳️ **VOTACIÓN ABIERTA** ({actual}/{total} votos registrados)")
        
        # Si todos votaron, mostrar botón de resultados
        if actual == total:
            self.clear_items()
            btn_res = discord.ui.Button(label="Mostrar Resultados", style=discord.ButtonStyle.primary)
            btn_res.callback = self.mostrar_resultados
            self.add_item(btn_res)
            await inter.message.edit(view=self)

    async def mostrar_resultados(self, inter):
        # Conteo de la urna
        conteo = {id_voto: self.votos_urna.count(id_voto) for id_voto in self.votos_urna}
        if not conteo:
            return await inter.response.send_message("Nadie votó a nadie. Saltando...", view=PanelAbreVotacion(self.partida))

        max_votos = max(conteo.values())
        candidatos = [k for k, v in conteo.items() if v == max_votos]
        
        if len(candidatos) > 1:
            await inter.channel.send("⚖️ Empate. Nadie es expulsado.")
            return await self.evaluar_continuacion(inter)

        expulsado = discord.utils.get(self.partida.jugadores, id=int(candidatos[0]))
        es_impostor = expulsado in self.partida.impostores
        
        embed = discord.Embed(title="Resultados del Sufragio", color=discord.Color.red())
        embed.set_thumbnail(url=expulsado.display_avatar.url)
        
        if es_impostor:
            self.partida.impostores.remove(expulsado)
            self.partida.jugadores.remove(expulsado)
            
            # Verificamos si era el único/último
            if len(self.partida.impostores) == 0:
                embed.description = f"**{expulsado.display_name} SÍ ERA IMPOSTOR.**\n\n🎉 ¡Felicidades! **El Zoroark salió de su madriguera y fue revelado.**"
                await inter.response.edit_message(view=None)
                await inter.channel.send(embed=embed)
                await self.pantalla_final(inter.channel)
                return
            else:
                embed.description = f"**{expulsado.display_name} SÍ ERA IMPOSTOR.**\n\nQuedan más traidores..."
        else:
            self.partida.jugadores.remove(expulsado)
            embed.description = f"**{expulsado.display_name} NO ERA IMPOSTOR.**\n\n🐘 **El Donphan sigue en la sala.**"

        await inter.response.edit_message(view=None)
        await inter.channel.send(embed=embed)
        
        # Evaluar lógica de Caos
        if self.partida.config.get('modo_juego') == 'caos' and es_impostor:
            await self.pregunta_caos(inter.channel)
        else:
            await self.evaluar_continuacion(inter.channel)

    async def evaluar_continuacion(self, canal):
        self.partida.ronda += 1
        await canal.send(f"Iniciando Ronda {self.partida.ronda}...", view=PanelAbreVotacion(self.partida))

    async def pregunta_caos(self, canal):
        class VotoCaos(discord.ui.View):
            def __init__(self, partida): super().__init__(); self.p = partida
            @discord.ui.button(label="Sí, hay más", style=discord.ButtonStyle.danger)
            async def b_si(self, i, b): 
                await i.response.edit_message(content="El juego continúa...", view=None)
                self.p.ronda += 1
                await i.channel.send(view=PanelAbreVotacion(self.p))
            @discord.ui.button(label="No, era el último", style=discord.ButtonStyle.success)
            async def b_no(self, i, b):
                await i.response.edit_message(content="Terminando juego...", view=None)
                await PantallaFinal(self.p, i.channel)
        await canal.send("🔥 **Modo Caos:** ¿Creen que hay MÁS impostores ocultos?", view=VotoCaos(self.partida))

    async def pantalla_final(self, canal):
        dp = self.partida.datos_pokemon
        embed = discord.Embed(title="🚨 JUEGO TERMINADO 🚨", color=discord.Color.dark_theme())
        embed.set_image(url=dp['sprite'])
        
        if getattr(self.partida, '_impostores_originales', None) is None:
            # Fallback simple
            embed.add_field(name="El Pokémon Secreto era:", value=f"**{dp['nombre']}**", inline=False)
        
        await canal.send(embed=embed)
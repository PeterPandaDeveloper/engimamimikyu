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
            return await inter.response.send_message("Solo admins pueden configurar la partida.", ephemeral=True)
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
        discord.SelectOption(label="Clásico", value="classico"),
        discord.SelectOption(label="Extendido", value="extendido"),
        discord.SelectOption(label="Caos", value="caos")
    ], row=0)
    async def sel_modo(self, inter, sel): 
        self.partida.config['modo_juego'] = sel.values[0]
        await inter.response.defer()

    @discord.ui.select(placeholder="Ventaja del Impostor", options=[
        discord.SelectOption(label="Aleatorio cada ronda", value="aleatorio"),
        discord.SelectOption(label="Letra Inicial", value="letra"),
        discord.SelectOption(label="Estadística más alta", value="stat_alta"),
        discord.SelectOption(label="Grupo Huevo", value="huevo"),
        discord.SelectOption(label="Tipo", value="tipo"),
        discord.SelectOption(label="Rango de Región", value="rango_region")
    ], row=1)
    async def sel_pista(self, inter, sel): 
        self.partida.config['ventaja'] = sel.values[0]
        await inter.response.defer()

    # SELECTOR DE REGIONES (Actualizado hasta la Gen 9)
    @discord.ui.select(placeholder="Regiones (Elige varias)", min_values=1, max_values=10, options=[
        discord.SelectOption(label="Todas (1-9)", value="todas"),
        discord.SelectOption(label="Kanto (Gen 1)", value="gen1"),
        discord.SelectOption(label="Johto (Gen 2)", value="gen2"),
        discord.SelectOption(label="Hoenn (Gen 3)", value="gen3"),
        discord.SelectOption(label="Sinnoh (Gen 4)", value="gen4"),
        discord.SelectOption(label="Teselia (Gen 5)", value="gen5"),
        discord.SelectOption(label="Kalos (Gen 6)", value="gen6"),
        discord.SelectOption(label="Alola (Gen 7)", value="gen7"),
        discord.SelectOption(label="Galar (Gen 8)", value="gen8"),
        discord.SelectOption(label="Paldea (Gen 9)", value="gen9")
    ], row=2)
    async def sel_region(self, inter, sel): 
        self.partida.config['regiones'] = sel.values
        await inter.response.defer()

    @discord.ui.button(label="🚀 INICIAR RONDA", style=discord.ButtonStyle.primary, row=3)
    async def btn_iniciar(self, inter, btn):
        if len(self.partida.jugadores) < 3: 
            return await inter.response.send_message("Mínimo 3 jugadores.")
        
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
        # Bloqueamos a los muertos para que no voten (Bug arreglado)
        if inter.user not in self.partida.jugadores:
            return await inter.response.send_message("👻 Los muertos y los espectadores no votan.", ephemeral=True)
        
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
            return await self.evaluar_continuacion(inter.channel)

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
                await self.pantalla_final(inter.channel, embed)
                return
            else:
                embed.description = f"**{expulsado.display_name} SÍ ERA IMPOSTOR.**\n\nQuedan más traidores..."
        else:
            self.partida.jugadores.remove(expulsado)
            embed.description = f"**{expulsado.display_name} NO ERA IMPOSTOR.**\n\n🐘 **El Donphan sigue en la sala.**"

        # LÓGICA DE VICTORIA PARA LOS IMPOSTORES (Bug arreglado)
        tripulantes_vivos = len(self.partida.jugadores) - len(self.partida.impostores)
        if len(self.partida.impostores) >= tripulantes_vivos:
            embed.description += "\n\n💀 **¡LOS IMPOSTORES HAN TOMADO EL CONTROL!** Ya son mayoría. Han ganado."
            await inter.response.edit_message(view=None)
            await self.pantalla_final(inter.channel, embed)
            return

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
        metodo_final = self.pantalla_final 
        
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
                await metodo_final(i.channel) 
                
        await canal.send("🔥 **Modo Caos:** ¿Creen que hay MÁS impostores ocultos?", view=VotoCaos(self.partida))

    async def pantalla_final(self, canal, embed_pre=None):
        if embed_pre:
            await canal.send(embed=embed_pre)
            
        dp = self.partida.datos_pokemon
        embed = discord.Embed(title="🚨 JUEGO TERMINADO 🚨", color=discord.Color.dark_theme())
        embed.set_thumbnail(url=dp['sprite'])
        
        embed.add_field(name="El Pokémon Secreto era:", value=f"**{dp['nombre']}**", inline=False)
        
        # Listar Impostores originales usando nuestra memoria
        lista_imp = "\n".join([f"🔪 {imp.display_name}" for imp in self.partida.impostores_iniciales])
        embed.add_field(name="Los Impostores Eran:", value=lista_imp or "Ninguno", inline=True)
        
        # Listar Tripulantes originales
        lista_trip = "\n".join([f"✅ {j.display_name}" for j in self.partida.jugadores_iniciales if j not in self.partida.impostores_iniciales])
        embed.add_field(name="Los Amigos Eran:", value=lista_trip or "Ninguno", inline=True)
        
        await canal.send(embed=embed, view=PanelPostRonda(self.partida))


# CLASE INDEPENDIENTE: El menú de después del juego
class PanelPostRonda(discord.ui.View):
    def __init__(self, partida):
        super().__init__(timeout=None)
        self.partida = partida

    @discord.ui.button(label="🔄 Revancha Rápida", style=discord.ButtonStyle.success, row=0)
    async def btn_revancha(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        
        # Revivir a todos los jugadores de la partida anterior (Bug arreglado)
        self.partida.jugadores = self.partida.jugadores_iniciales.copy()
        
        self.partida.ronda += 1
        await self.partida.arrancar_ronda()
        
        embed = discord.Embed(
            title=f"🏆 RONDA {self.partida.ronda} (REVANCHA)", 
            description="¡Nueva partida iniciada con los mismos jugadores!\nRevisen sus DMs. Tómense su tiempo para hablar.",
            color=discord.Color.gold()
        )
        await inter.channel.send(embed=embed, view=PanelAbreVotacion(self.partida))

    @discord.ui.button(label="⚙️ Cambiar Configuración", style=discord.ButtonStyle.primary, row=0)
    async def btn_config(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        await inter.channel.send(
            embed=discord.Embed(title="⚙️ Mesa del Game Master", description="Ajusten las reglas para la siguiente partida.", color=discord.Color.blue()), 
            view=PanelConfiguracion(self.partida)
        )

    @discord.ui.button(label="❌ Terminar de Jugar", style=discord.ButtonStyle.danger, row=0)
    async def btn_cerrar(self, inter: discord.Interaction, btn: discord.ui.Button):
        # Limpiamos la lista de jugadores para vaciar el lobby
        self.partida.jugadores = []
        await inter.response.edit_message(view=None)
        await inter.channel.send("🧹 **El lobby ha sido cerrado.** ¡Gracias por jugar! Usen `pkmi!register` para abrir uno nuevo más tarde.")
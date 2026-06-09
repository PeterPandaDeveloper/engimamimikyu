import discord
from discord.ext import commands
import random
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# --- MINIBASES DE DATOS PARA LAS VARIANTES ---
DB_PERSONAJES = {
    "Ash Ketchum": "Tiene un Pikachu chetado que le gana a legendarios pero pierde con un Snivy nivel 5.",
    "Red": "No dice ni una sola palabra, solo respira épicamente en la cima de una montaña.",
    "Azul (Gary)": "Es el clásico huelemepio que siempre va un paso adelante de ti.",
    "Misty": "Te va a cobrar una bicicleta por el resto de tu vida.",
    "Brock": "Abre los ojos una vez cada 3 temporadas y usa sus sartenes como paraguas.",
    "Cintia": "Cuando escuchas la música de su piano, sabes que vas a sufrir.",
    "Lance": "Usa pociones completas en la Liga y tiene Dragonites ilegales.",
    "N": "Habla excesivamente rápido y quiere liberar a todos los Pokémon.",
    "Profesor Oak": "No sabe si eres chico o chica, ni el nombre de su propio nieto."
}

DB_OBJETOS = {
    "Master Ball": "Nunca la usas, siempre la guardas 'por si acaso aparece un shiny'.",
    "Bicicleta": "Hay un momento y lugar para todo, pero no puedes usar esto aquí.",
    "Restos": "Se lo pones a tu tanque y haces que el rival se desespere curándote cada turno.",
    "Repartir Exp": "Antes era un objeto, ahora viene activado a la fuerza para todo el equipo.",
    "Poción Máxima": "Ese objeto molesto que usan los líderes de gimnasio cuando los dejas a 1 HP.",
    "Piedra Trueno": "El mayor trauma de Pikachu en la primera temporada."
}

# --- 1. BASE DE DATOS POKÉMON (API) ---
async def obtener_pokemon_datos(id_pokemon):
    url = f"https://pokeapi.co/api/v2/pokemon/{id_pokemon}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return (
                    data['name'].capitalize(),
                    [t['type']['name'].capitalize() for t in data['types']],
                    [h['ability']['name'].replace('-', ' ').capitalize() for h in data['abilities']]
                )
            return "Pikachu", ["Electric"], ["Static"]

# --- 2. EL MOTOR DEL JUEGO ---
async def motor_de_juego(canal, rol_juego, config):
    jugadores = rol_juego.members
    if len(jugadores) < 3:
        return await canal.send("⚠️ Faltan jugadores para armar el desmadre. Mínimo 3 inscritos en el lobby (!reclutar).")

    msg_carga = await canal.send("✨ *Mezclando las cartas y preparando las mentiras...*")
    
    # --- LÓGICA DE TEMÁTICA ---
    tema = config.get('tema', 'pokemon')
    if tema == 'personajes':
        secreto, pista_texto = random.choice(list(DB_PERSONAJES.items()))
    elif tema == 'objetos':
        secreto, pista_texto = random.choice(list(DB_OBJETOS.items()))
    else:
        # Lógica clásica de Pokémon API
        gen_ranges = {
            "gen1": range(1, 152), "gen2": range(152, 252), "gen3": range(252, 387),
            "gen4": range(387, 494), "gen5": range(494, 650), "gen6": range(650, 722),
            "gen7": range(722, 810), "gen8": range(810, 906), "gen9": range(906, 1026)
        }
        ids_validos = list(range(1, 1026)) if "todas" in config['gens'] else []
        if not ids_validos:
            for gen in config['gens']: ids_validos.extend(gen_ranges[gen])
                
        id_elegido = random.choice(ids_validos)
        secreto, tipos, habilidades = await obtener_pokemon_datos(id_elegido)
        
        tipo_final = random.choice(["tipo", "habilidad", "letra"]) if config['pista'] == "random" else config['pista']
        if tipo_final == "tipo": pista_texto = f"Es de tipo **{', '.join(tipos)}**."
        elif tipo_final == "habilidad": pista_texto = f"Posible habilidad: **{random.choice(habilidades)}**."
        else: pista_texto = f"Su nombre empieza con **'{secreto[0]}'**."

    # --- REPARTO DE ROLES ---
    total = len(jugadores)
    modo_imp = config['impostores']
    if modo_imp == "caos": cantidad = random.choice([0, 1, 2, 3, total])
    elif modo_imp == "todos": cantidad = total
    else: cantidad = min(int(modo_imp), total)
        
    impostores = random.sample(jugadores, min(cantidad, total))
    jugadores_vivos = jugadores.copy()
    impostores_vivos = impostores.copy()

    for jugador in jugadores:
        try:
            if jugador in impostores: 
                await jugador.send(f"🔪 **ERES EL IMPOSTOR**.\nNo tienes idea de qué están hablando.\n\n🔍 **Tu pista salvavidas:** {pista_texto}")
            else: 
                await jugador.send(f"✅ **ERES INOCENTE**.\n\nEl secreto de esta ronda es: **{secreto}**.\nNo dejes que los impostores te engañen.")
        except discord.Forbidden:
            await msg_carga.delete()
            return await canal.send(f"💀 **{jugador.display_name}** tiene los DMs cerrados. Abran sus privados o expúlsenlo para poder jugar.")

    await msg_carga.delete()
    
    # Interfaz bonita de Ronda
    embed = discord.Embed(title="🕵️‍♂️ ¡LA RONDA HA COMENZADO!", color=discord.Color.dark_red())
    embed.add_field(name="📜 Temática", value=f"**{tema.capitalize()}**", inline=True)
    embed.add_field(name="👥 Vivos", value=f"**{len(jugadores_vivos)}** jugadores", inline=True)
    embed.add_field(name="💬 Objetivo", value="Hablen, mientan y pregunten. Cuando sospechen de alguien, ¡llamen a votación!", inline=False)
    embed.set_footer(text="Nadie sabe cuántos impostores hay... o sí.")
    
    await canal.send(embed=embed, view=PanelRonda(jugadores_vivos, impostores_vivos, secreto, rol_juego, config, canal))

# --- 3. PANELES Y VOTACIÓN ---
class PanelRonda(discord.ui.View):
    def __init__(self, vivos, impostores, secreto, rol, config, canal):
        super().__init__(timeout=None)
        self.vivos, self.impostores, self.secreto = vivos, impostores, secreto
        self.rol, self.config, self.canal = rol, config, canal

    @discord.ui.button(label="📢 Llamar a Votación", style=discord.ButtonStyle.danger)
    async def btn_votar(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        embed = discord.Embed(title="🗳️ EL TRIBUNAL ESTÁ ABIERTO", description="Elijan a quién lanzar al vacío o voten por pasar.\n*Sus votos son secretos.*", color=discord.Color.blue())
        await self.canal.send(embed=embed, view=PanelVotacion(self.vivos, self.impostores, self.secreto, self.rol, self.config, self.canal))

class PanelVotacion(discord.ui.View):
    def __init__(self, vivos, impostores, secreto, rol, config, canal):
        super().__init__(timeout=None)
        self.vivos, self.impostores, self.secreto = vivos, impostores, secreto
        self.rol, self.config, self.canal = rol, config, canal
        self.votos = {}

        opciones = [discord.SelectOption(label=j.display_name, value=str(j.id)) for j in vivos]
        opciones.append(discord.SelectOption(label="⏭️ Pasar el voto", value="pasar"))

        self.select_voto = discord.ui.Select(placeholder="👇 Elige a tu sospechoso...", options=opciones)
        self.select_voto.callback = self.registrar_voto
        self.add_item(self.select_voto)

    async def registrar_voto(self, inter: discord.Interaction):
        if inter.user not in self.vivos:
            return await inter.response.send_message("👻 Los fantasmas no pueden votar.", ephemeral=True)
        self.votos[inter.user.id] = self.select_voto.values[0]
        await inter.response.send_message("✅ Voto guardado. Shhh...", ephemeral=True)

        if len(self.votos) == len(self.vivos):
            await self.procesar_resultados(inter.message)

    @discord.ui.button(label="⏳ Forzar Conteo", style=discord.ButtonStyle.secondary, row=1)
    async def btn_forzar(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer()
        await self.procesar_resultados(inter.message)

    async def procesar_resultados(self, mensaje_votacion):
        await mensaje_votacion.edit(view=None)
        conteo = {}
        for voto in self.votos.values(): conteo[voto] = conteo.get(voto, 0) + 1

        if not conteo:
            return await self.canal.send("Nadie votó. Seguimos igual.", view=PanelRonda(self.vivos, self.impostores, self.secreto, self.rol, self.config, self.canal))

        max_votos = max(conteo.values())
        candidatos = [k for k, v in conteo.items() if v == max_votos]

        if len(candidatos) > 1 or candidatos[0] == "pasar":
            mensaje_exp = "⚖️ **EMPATE o SKIP.** Nadie salió volando esta vez."
        else:
            expulsado = discord.utils.get(self.vivos, id=int(candidatos[0]))
            es_impostor = expulsado in self.impostores
            texto_rol = "🔪 **ERA** un impostor." if es_impostor else "🕊️ **NO** era un impostor."
            mensaje_exp = f"👢 Decidieron patear a **{expulsado.display_name}**.\n\n{texto_rol}"

            self.vivos.remove(expulsado)
            if es_impostor: self.impostores.remove(expulsado)

        # Condiciones de Victoria o Continuar
        if len(self.impostores) == 0:
            e = discord.Embed(title="🏆 ¡INOCENTES GANAN!", description=f"{mensaje_exp}\n\nLimpiaron la sala. El secreto era: **{self.secreto}**.", color=discord.Color.green())
            await self.canal.send(embed=e, view=PanelPostRonda(self.rol, self.config))
        elif len(self.impostores) >= len(self.vivos) - len(self.impostores):
            e = discord.Embed(title="💀 ¡IMPOSTORES GANAN!", description=f"{mensaje_exp}\n\nYa son mayoría. Se apoderaron del lobby. El secreto era: **{self.secreto}**.", color=discord.Color.red())
            await self.canal.send(embed=e, view=PanelPostRonda(self.rol, self.config))
        else:
            # EL DONPHAN EN LA SALA
            e = discord.Embed(title="🌑 La noche cae de nuevo...", description=f"{mensaje_exp}\n\n***🐘 El Donphan sigue en la sala...***", color=discord.Color.dark_gray())
            await self.canal.send(embed=e, view=PanelRonda(self.vivos, self.impostores, self.secreto, self.rol, self.config, self.canal))

# --- PANELES DE CONFIGURACIÓN Y LOBBY ---
class PanelPostRonda(discord.ui.View):
    def __init__(self, rol, config):
        super().__init__(timeout=None)
        self.rol, self.config = rol, config
    @discord.ui.button(label="🔄 Otra Partida Rápida", style=discord.ButtonStyle.success)
    async def btn_revancha(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        await motor_de_juego(inter.channel, self.rol, self.config)
    @discord.ui.button(label="⚙️ Ajustar Reglas", style=discord.ButtonStyle.primary)
    async def btn_editar(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(view=None)
        await inter.channel.send(embed=discord.Embed(title="⚙️ Setup de Partida", color=discord.Color.blue()), view=PanelConfiguracion(self.rol, self.config))

class PanelConfiguracion(discord.ui.View):
    def __init__(self, rol, config_previa=None):
        super().__init__(timeout=None)
        self.rol = rol
        self.config = config_previa or {"tema": "pokemon", "gens": ["todas"], "impostores": "1", "pista": "random"}

    @discord.ui.select(placeholder="🎭 Elegir Temática", row=0, options=[
        discord.SelectOption(label="Pokémon Clásico", value="pokemon", description="Usa la PokéAPI", emoji="🐾"),
        discord.SelectOption(label="Personajes del Anime/Juegos", value="personajes", description="Ash, Misty, Cintia...", emoji="🧢"),
        discord.SelectOption(label="Objetos", value="objetos", description="Pokéballs, Pociones...", emoji="🎒")])
    async def s_tema(self, inter: discord.Interaction, s: discord.ui.Select):
        self.config['tema'] = s.values[0]; await inter.response.defer()

    @discord.ui.select(placeholder="🌍 Generaciones (Solo si juegan Pokémon)", row=1, options=[
        discord.SelectOption(label="Todas las Gens", value="todas"), discord.SelectOption(label="Solo Gen 1", value="gen1"),
        discord.SelectOption(label="Solo Gen 2", value="gen2"), discord.SelectOption(label="Solo Gen 3", value="gen3")])
    async def s_gen(self, inter: discord.Interaction, s: discord.ui.Select):
        self.config['gens'] = s.values; await inter.response.defer()
        
    @discord.ui.select(placeholder="🔪 Número de Impostores", row=2, options=[
        discord.SelectOption(label="1 Solo Impostor", value="1"), discord.SelectOption(label="2 Impostores", value="2"), 
        discord.SelectOption(label="Modo CAOS", value="caos", description="Nunca sabrán cuántos hay")])
    async def s_imp(self, inter: discord.Interaction, s: discord.ui.Select):
        self.config['impostores'] = s.values[0]; await inter.response.defer()

    @discord.ui.button(label="🔥 ¡ARRANCAR PARTIDA!", style=discord.ButtonStyle.success, row=3)
    async def btn_iniciar(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.edit_message(content="*Iniciando protocolo de traición...*", view=None)
        await motor_de_juego(inter.channel, self.rol, self.config)

# --- COMANDOS BÁSICOS ---
@bot.event
async def on_ready(): print(f'⚡ {bot.user} ha despertado y está listo para arruinar amistades.')

@bot.command()
async def reclutar(ctx):
    rol = discord.utils.get(ctx.guild.roles, name="jugador-impostor")
    if not rol: rol = await ctx.guild.create_role(name="jugador-impostor", color=discord.Color.gold())
    
    e = discord.Embed(title="🎪 LOBBY: EL IMPUESTO POKÉMON", description="Pulsa el botón verde para entrar a jugar.\n*Dile a tus amigos que no sean cobardes.*", color=discord.Color.gold())
    
    class Inscripcion(discord.ui.View):
        @discord.ui.button(label="🎮 Entrar / Salir", style=discord.ButtonStyle.success)
        async def btn(self, i: discord.Interaction, b: discord.ui.Button):
            if rol in i.user.roles:
                await i.user.remove_roles(rol)
                await i.response.send_message("🚪 Te saliste.", ephemeral=True)
            else:
                await i.user.add_roles(rol)
                await i.response.send_message("🎟️ Estás dentro.", ephemeral=True)
                
    await ctx.send(embed=e, view=Inscripcion())

@bot.command()
async def organizar(ctx):
    rol = discord.utils.get(ctx.guild.roles, name="jugador-impostor")
    if not rol or len(rol.members) < 3: return await ctx.send("Bro, faltan jugadores. Usen `!reclutar` primero.")
    await ctx.send(embed=discord.Embed(title="⚙️ Mesa del Game Master", description="Configura la partida.", color=discord.Color.blurple()), view=PanelConfiguracion(rol))

if TOKEN: bot.run(TOKEN)
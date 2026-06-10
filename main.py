import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from vistas import PanelInscripcion
from motor_juego import Partida

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='pkmi!', intents=intents)

# Diccionario para rastrear partidas activas por ID de canal
partidas_activas = {}

@bot.event
async def on_ready():
    print(f'⚡ {bot.user} en línea. El Donphan está listo.')
    try:
        # Esto envía tus comandos a los servidores de Discord
        sincronizados = await bot.tree.sync()
        print(f"🌐 Slash commands sincronizados: {len(sincronizados)}")
    except Exception as e:
        print(f"Error sincronizando comandos: {e}")

# COMANDO 1: /impregister (Abre la sala de juego)
@bot.tree.command(name="impregister", description="Abre un nuevo lobby de PokeImpostor")
async def impregister(interaction: discord.Interaction):
    if interaction.channel.id in partidas_activas:
        return await interaction.response.send_message("⚠️ Ya hay una partida activa o un lobby abierto en este canal. Termínenla primero.", ephemeral=True)
    
    nueva_partida = Partida(interaction.channel)
    nueva_partida.limpiar_memoria = lambda: partidas_activas.pop(interaction.channel.id, None)
    
    partidas_activas[interaction.channel.id] = nueva_partida
    
    embed = discord.Embed(
        title="🎮 ¡NUEVO JUEGO DE POKEIMPOSTOR!",
        description="Un juego está a punto de empezar.\n**Jugadores en el lobby: 0**",
        color=discord.Color.green()
    )
    vista = PanelInscripcion(nueva_partida)
    
    await interaction.response.send_message(embed=embed, view=vista)


# COMANDO 2: /imphelp (Muestra las instrucciones)
@bot.tree.command(name="imphelp", description="Muestra las reglas y cómo jugar a PokeImpostor")
async def imphelp(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Cómo jugar PokeImpostor",
        description="¡El juego de deducción y engaño Pokémon!",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="1️⃣ Iniciar Lobby", 
        value="El administrador usa `/impregister` para abrir la sala. Todos deben darle a 'Unirse'.", 
        inline=False
    )
    embed.add_field(
        name="2️⃣ Revisen sus DMs", 
        value="Los tripulantes recibirán la imagen y el nombre de un Pokémon secreto.\nEl impostor no sabrá cuál es, pero recibirá una pista en su lugar (ej. *'Su estadística más alta es Ataque'*).", 
        inline=False
    )
    embed.add_field(
        name="3️⃣ El Debate", 
        value="Hablen e intenten descubrir quién no sabe de qué Pokémon están hablando. ¡Los tripulantes deben cuidarse de no ser muy obvios o el impostor adivinará la respuesta!", 
        inline=False
    )
    embed.add_field(
        name="4️⃣ Votación", 
        value="Abran la votación y elijan a sus sospechosos en secreto. Si expulsan a todos los impostores, los tripulantes ganan. Si se equivocan, ¡el caos continúa!", 
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)


if __name__ == '__main__':
    bot.run(TOKEN)
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
bot = commands.Bot(command_prefix='pkmi!', intents=intents)

# Diccionario para rastrear partidas activas por ID de canal
partidas_activas = {}

@bot.event
async def on_ready():
    print(f'⚡ {bot.user} en línea. El Donphan está listo.')

@bot.command()
async def register(ctx):
    if ctx.channel.id in partidas_activas:
        return await ctx.send("⚠️ Ya hay una partida activa o un lobby abierto en este canal. Termínenla primero.")
    
    nueva_partida = Partida(ctx.channel)
    # Le inyectamos la orden de autodestruirse de la memoria al terminar
    nueva_partida.limpiar_memoria = lambda: partidas_activas.pop(ctx.channel.id, None)
    
    partidas_activas[ctx.channel.id] = nueva_partida
    
    embed = discord.Embed(
        title="🎮 ¡NUEVO JUEGO DE POKEIMPOSTOR!",
        description="Un juego está a punto de empezar.\n**Jugadores en el lobby: 0**",
        color=discord.Color.green()
    )
    vista = PanelInscripcion(nueva_partida)
    await ctx.send(embed=embed, view=vista)
    
if __name__ == '__main__':
    bot.run(TOKEN)
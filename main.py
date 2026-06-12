"""
main.py — Entry point de PokeImpostor
Registra los slash commands y gestiona el ciclo de vida del bot.
"""
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from motor_juego import Partida
from vistas import PanelInscripcion, _build_embed_lobby
from api import cerrar_session

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="pkmi!", intents=intents)

# Registro central de partidas activas: { channel_id: Partida }
partidas_activas: dict[int, Partida] = {}


# ═══════════════════════════════════════════════════════════════════════════════
#  EVENTOS DEL BOT
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"⚡ {bot.user} conectado. Esperando entrenadores...")
    try:
        sync = await bot.tree.sync()
        print(f"🌐 {len(sync)} slash commands sincronizados.")
    except Exception as e:
        print(f"Error sincronizando comandos: {e}")

@bot.event
async def on_close():
    await cerrar_session()
    print("🔌 Sesión HTTP cerrada correctamente.")


# ═══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="impregister", description="Abre un nuevo lobby de PokeImpostor")
async def impregister(interaction: discord.Interaction):
    if interaction.channel.id in partidas_activas:
        return await interaction.response.send_message(
            "⚠️ Ya hay una partida activa en este canal. Termínenla antes de abrir otra.",
            ephemeral=True,
        )

    # fix-11: Partida recibe la referencia al dict — no más monkey-patch
    nueva = Partida(canal=interaction.channel, partidas_activas=partidas_activas)
    partidas_activas[interaction.channel.id] = nueva

    await interaction.response.send_message(
        embed=_build_embed_lobby(nueva),
        view=PanelInscripcion(nueva),
    )


@bot.tree.command(name="impver", description="Vuelve a enviarte tu rol por DM (solo durante la partida)")
async def impver(interaction: discord.Interaction):
    """fix-9: los tripulantes pueden volver a ver el Pokémon si cerraron el DM."""
    partida = partidas_activas.get(interaction.channel.id)

    if partida is None or partida.datos_pokemon is None:
        return await interaction.response.send_message(
            "No hay una partida activa en este canal.", ephemeral=True
        )
    if interaction.user not in partida.jugadores_iniciales:
        return await interaction.response.send_message(
            "No participaste en esta ronda.", ephemeral=True
        )

    dp = partida.datos_pokemon
    try:
        if interaction.user in partida.impostores_iniciales:
            await interaction.user.send(
                embed=discord.Embed(
                    title="🕵️ Tu rol — IMPOSTOR",
                    description=f"🔍 **Tu pista:** {partida.pista_generada}",
                    color=discord.Color.from_rgb(180, 30, 30),
                )
            )
        else:
            embed = discord.Embed(
                title="✅ Tu rol — TRIPULANTE",
                description=f"El Pokémon secreto es: **{dp['nombre']}**",
                color=discord.Color.from_rgb(30, 160, 80),
            )
            embed.set_image(url=dp["sprite"])
            await interaction.user.send(embed=embed)

        await interaction.response.send_message(
            "✅ Te reenvié tu rol por DM.", ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ No pude enviarte un DM. Revisa que tengas los DMs del servidor habilitados.",
            ephemeral=True,
        )


@bot.tree.command(name="imphelp", description="Cómo jugar a PokeImpostor")
async def imphelp(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 PokeImpostor — Guía Rápida",
        description="El juego de deducción donde el conocimiento Pokémon es tu arma.",
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.add_field(
        name="1️⃣  Unirse al Lobby",
        value="Usa `/impregister` para abrir la sala. Todos presionan **⚡ Unirse**.",
        inline=False,
    )
    embed.add_field(
        name="2️⃣  Revisar el DM",
        value=(
            "**Tripulantes** reciben la imagen y nombre del Pokémon secreto.\n"
            "**El Impostor** recibe solo una pista y debe fingir que lo conoce.\n"
            "Si cerraste el DM, usa `/impver` para volver a verlo."
        ),
        inline=False,
    )
    embed.add_field(
        name="3️⃣  El Debate",
        value=(
            "Hablen del Pokémon sin decir su nombre directamente.\n"
            "Observen quién titubea, da pistas demasiado vagas o demasiado generales."
        ),
        inline=False,
    )
    embed.add_field(
        name="4️⃣  Votación",
        value=(
            "El admin abre la votación. Elijan a sus sospechosos (anónimo).\n"
            "El más votado es expulsado. ¡Descubran a todos los impostores para ganar!"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️  Modos de Juego",
        value=(
            "**Clásico** — Siempre 1 impostor.\n"
            "**Extendido** — 1 impostor por cada 3 jugadores.\n"
            "**Caos** — Cantidad aleatoria. ¡Puede haber 0!"
        ),
        inline=False,
    )
    embed.set_footer(text="¡Buena suerte, entrenador!")
    await interaction.response.send_message(embed=embed)


# ═══════════════════════════════════════════════════════════════════════════════
#  ARRANQUE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN no encontrado. Crea un archivo .env con DISCORD_TOKEN=tu_token")
    else:
        bot.run(TOKEN)
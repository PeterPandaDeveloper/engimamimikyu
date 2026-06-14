"""
main.py — Entry point de PokeImpostor
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

from motor_juego import Partida
from vistas import PanelInscripcion, _build_embed_lobby
from api import cerrar_session
from i18n import t, set_lang, get_lang

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="pkmi!", intents=intents)

# Registro central: { channel_id: Partida }
partidas_activas: dict[int, Partida] = {}


# ═══════════════════════════════════════════════════════════════════════════════
#  EVENTOS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"⚡ {bot.user} online. Waiting for trainers...")
    try:
        sync = await bot.tree.sync()
        print(f"🌐 {len(sync)} slash commands synced.")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.event
async def on_close():
    await cerrar_session()
    print("🔌 HTTP session closed.")


# ═══════════════════════════════════════════════════════════════════════════════
#  /impregister
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="impregister", description="Open a new PokeImpostor lobby")
async def impregister(interaction: discord.Interaction):
    gid = interaction.guild_id
    if interaction.channel.id in partidas_activas:
        return await interaction.response.send_message(
            t("register_already_active", gid), ephemeral=True
        )
    nueva = Partida(canal=interaction.channel, partidas_activas=partidas_activas)
    partidas_activas[interaction.channel.id] = nueva
    await interaction.response.send_message(
        embed=_build_embed_lobby(nueva),
        view=PanelInscripcion(nueva),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  /impver — reenviar rol por DM
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="impver", description="Re-send your role by DM (only during an active game)")
async def impver(interaction: discord.Interaction):
    gid     = interaction.guild_id
    partida = partidas_activas.get(interaction.channel.id)

    if partida is None or (partida.datos_pokemon is None and not partida.pokemons_ebrios and partida.objetivo_humano is None):
        return await interaction.response.send_message(t("impver_no_game", gid), ephemeral=True)

    if interaction.user not in partida.jugadores_iniciales:
        return await interaction.response.send_message(t("impver_not_player", gid), ephemeral=True)

    try:
        es_impostor  = interaction.user in partida.impostores_iniciales
        es_ebrios    = bool(partida.pokemons_ebrios)
        es_cj        = partida.objetivo_humano is not None

        if es_cj:
            # Modo Caos Jugador
            if es_impostor:
                pista = partida.pistas_impostores.get(interaction.user.id, "—")
                await interaction.user.send(embed=discord.Embed(
                    title=t("impver_impostor_title", gid),
                    description=t("dm_caos_jugador_detective_desc", gid, hint=pista),
                    color=discord.Color.from_rgb(180, 30, 30),
                ))
            else:
                await interaction.user.send(embed=discord.Embed(
                    title=t("impver_crew_title", gid),
                    description=t("dm_caos_jugador_crew_desc", gid, target=f"**{partida.objetivo_humano.display_name}**"),
                    color=discord.Color.from_rgb(30, 160, 80),
                ).set_image(url=partida.objetivo_humano.display_avatar.url))

        elif es_ebrios:
            # Variante Danza Caos — usar el mismo título/color que tripulante normal
            # para no revelar el sub-modo activo.
            dp = partida.pokemons_ebrios.get(interaction.user.id)
            if dp:
                await interaction.user.send(embed=discord.Embed(
                    title=t("dm_crew_title", gid),
                    description=t("dm_ebrios_desc", gid, name=dp["nombre"], types=" / ".join(dp["tipos"])),
                    color=discord.Color.from_rgb(30, 160, 80),
                ).set_image(url=dp["sprite"]).set_footer(text=t("dm_ebrios_footer", gid)))

        elif es_impostor:
            # Impostor normal
            pista = partida.pistas_impostores.get(interaction.user.id, partida.pista_generada)
            await interaction.user.send(embed=discord.Embed(
                title=t("impver_impostor_title", gid),
                description=t("dm_impostor_desc", gid, hint=pista),
                color=discord.Color.from_rgb(180, 30, 30),
            ))
        else:
            # Tripulante normal
            dp = partida.datos_pokemon
            await interaction.user.send(embed=discord.Embed(
                title=t("impver_crew_title", gid),
                description=t("dm_crew_desc", gid, name=dp["nombre"], types=" / ".join(dp["tipos"])),
                color=discord.Color.from_rgb(30, 160, 80),
            ).set_image(url=dp["sprite"]))

        await interaction.response.send_message(t("impver_sent", gid), ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message(t("impver_dm_blocked", gid), ephemeral=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  /implanguage — cambiar idioma del servidor
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="implanguage", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def implanguage(interaction: discord.Interaction, language: str):
    gid = interaction.guild_id
    if not interaction.user.guild_permissions.administrator:
        # Mensaje de error bilingüe (no sabemos el idioma actual del usuario)
        return await interaction.response.send_message(
            t("lang_only_admin", gid), ephemeral=True
        )
    set_lang(gid, language)
    # Confirmación en el idioma recién elegido (ya está guardado)
    key = "lang_changed_en" if language == "en" else "lang_changed_es"
    await interaction.response.send_message(t(key, gid))


# ═══════════════════════════════════════════════════════════════════════════════
#  /imphelp
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="imphelp", description="How to play PokeImpostor / Cómo jugar")
async def imphelp(interaction: discord.Interaction):
    gid = interaction.guild_id
    embed = discord.Embed(
        title=t("help_title",  gid),
        description=t("help_desc", gid),
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.add_field(name=t("help_step1_name", gid), value=t("help_step1_value", gid), inline=False)
    embed.add_field(name=t("help_step2_name", gid), value=t("help_step2_value", gid), inline=False)
    embed.add_field(name=t("help_step3_name", gid), value=t("help_step3_value", gid), inline=False)
    embed.add_field(name=t("help_step4_name", gid), value=t("help_step4_value", gid), inline=False)
    embed.add_field(name=t("help_modes_name", gid), value=t("help_modes_value", gid), inline=False)
    embed.set_footer(text=t("help_footer", gid))
    await interaction.response.send_message(embed=embed)


# ═══════════════════════════════════════════════════════════════════════════════
#  ARRANQUE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not found. Create a .env file with DISCORD_TOKEN=your_token")
    else:
        bot.run(TOKEN)
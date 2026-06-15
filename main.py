"""
main.py — Entry point de PokeImpostor
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import json
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

# ── Persistencia ligera de sesiones activas ──────────────────────────────────
# No persistimos el ESTADO completo de cada Partida (contiene objetos
# discord.Member que no son serializables y que habría que re-resolver vía
# API tras un reinicio). En su lugar, guardamos solo QUÉ canales tenían una
# partida activa. Si el bot se reinicia a mitad de una partida, al arrancar
# avisamos en esos canales que la sesión se perdió y hay que abrir un lobby
# nuevo — mejor que dejar botones "muertos" sin explicación.
_DATA_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_SESSIONS_FILE = os.path.join(_DATA_DIR, "sesiones_activas.json")


def _guardar_sesiones_activas() -> None:
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(partidas_activas.keys()), f)
    except OSError as e:
        print(f"[main] No se pudo guardar sesiones_activas.json: {e}")


def _cargar_sesiones_previas() -> list[int]:
    try:
        with open(_SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return []


class _PartidasActivasDict(dict):
    """
    dict { channel_id: Partida } que persiste automáticamente en disco
    (solo las claves, ver _guardar_sesiones_activas) cada vez que se
    añade o elimina una partida — sin que el resto del código tenga que
    acordarse de llamar a una función extra.
    """
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        _guardar_sesiones_activas()

    def __delitem__(self, key):
        super().__delitem__(key)
        _guardar_sesiones_activas()

    def pop(self, *args, **kwargs):
        result = super().pop(*args, **kwargs)
        _guardar_sesiones_activas()
        return result

    def clear(self):
        super().clear()
        _guardar_sesiones_activas()


# Registro central: { channel_id: Partida }
partidas_activas: dict[int, Partida] = _PartidasActivasDict()


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

    # ── Recuperación tras reinicio ───────────────────────────────────────────
    # Si el bot se cayó/reinició a mitad de una partida, los botones de esos
    # mensajes quedan "muertos" (la View vivía solo en memoria del proceso
    # anterior). Avisamos en cada canal afectado para que el grupo sepa que
    # debe abrir un lobby nuevo, en lugar de quedarse pulsando botones sin
    # respuesta sin entender por qué.
    canales_previos = _cargar_sesiones_previas()
    for channel_id in canales_previos:
        try:
            canal = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            gid = canal.guild.id if getattr(canal, "guild", None) else None
            await canal.send(
                t("session_lost_after_restart", gid)
            )
        except Exception as e:
            print(f"[on_ready] No se pudo avisar en canal {channel_id}: {e}")

    # Limpiar el registro: estas sesiones ya no son válidas y no deben
    # volver a generar avisos en el siguiente reinicio.
    partidas_activas.clear()
    _guardar_sesiones_activas()

@bot.event
async def on_close():
    await cerrar_session()
    print("🔌 HTTP session closed.")


# ═══════════════════════════════════════════════════════════════════════════════
#  /impregister
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="impregister", description="Open a new PokeImpostor lobby")
async def impregister(interaction: discord.Interaction):
    # Este juego depende de roles de servidor (administrator), DMs a
    # miembros del servidor, e idioma por servidor. No tiene sentido fuera
    # de un guild (ej. DMs directos al bot).
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

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
            # Variante Objetivo Humano
            if es_impostor:
                # El detective
                pista = partida.pistas_impostores.get(interaction.user.id, "—")
                await interaction.user.send(embed=discord.Embed(
                    title=t("impver_impostor_title", gid),
                    description=t("dm_caos_jugador_detective_desc", gid, hint=pista),
                    color=discord.Color.from_rgb(180, 30, 30),
                ))
            elif interaction.user == partida.objetivo_humano:
                # El propio objetivo — NUNCA debe ver "describe a [su nombre]"
                await interaction.user.send(embed=discord.Embed(
                    title=t("impver_crew_title", gid),
                    description=t("dm_caos_jugador_target_desc", gid),
                    color=discord.Color.from_rgb(30, 160, 80),
                ))
            else:
                # Tripulante normal describiendo al objetivo
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
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

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
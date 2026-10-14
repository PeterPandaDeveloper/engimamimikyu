"""
main.py — Entry point de PokeImpostor
Inicialización del bot de Discord, sincronización de comandos Slash,
despachador de comandos de texto y ciclo de vida de la aplicación.
"""
from __future__ import annotations

import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from motor_juego import Partida
from vistas import (
    PanelInscripcion,
    _build_embed_lobby,
    es_anfitrion_o_admin,
    obtener_nombre_rol_host,
)
from api import cerrar_session
from i18n import t, set_lang
from db import (
    init_db,
    close_db,
    crear_licencia_async,
    registrar_servidor_partner_async,
)
from security import verificar_master_password, generar_codigo_licencia
from webhook_topgg import iniciar_webhook_topgg, detener_webhook_topgg
from comandos_comunes import (
    BUYMEACOFFEE_URL,
    INVITE_PERMS_INT,
    asegurar_rol_pokehost,
    reenviar_rol_secreto,
    construir_embed_perfil,
    construir_embed_ranking,
    construir_embed_stats,
    construir_payload_licencia,
    canjear_clave_licencia,
    construir_payload_voto,
    construir_payload_donar,
    construir_payload_invitar,
    construir_embed_ayuda,
    construir_embed_creditos,
    ejecutar_setrole_comun,
)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class PokeImpostorBot(commands.Bot):
    """
    Subclase especializada de commands.Bot para PokeImpostor.
    - Maneja el ciclo de vida y apagado limpio de recursos (DuckDB, aiohttp, runner de Top.gg).
    - Mantiene una bandera de inicialización para evitar borrado de partidas activas en reconexiones.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ya_iniciado: bool = False

    async def close(self):
        await detener_webhook_topgg()
        await cerrar_session()
        print("🔌 HTTP session closed.")
        try:
            await close_db()
            print("[DuckDB] Connection closed cleanly.")
        except Exception as e:
            print(f"[DuckDB] Error closing database: {e}")

        await super().close()


bot = PokeImpostorBot(command_prefix="pkmi!", intents=intents)

# Servidor central autorizado exclusivamente para generar keys y gestionar partners
SERVER_ADMIN_CENTRAL_ID = 402155389958881310

# ── Persistencia ligera de sesiones activas ──────────────────────────────────
_DATA_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_SESSIONS_FILE = os.path.join(_DATA_DIR, "sesiones_activas.json")


class _PartidasActivasDict(dict):
    """
    dict { channel_id: Partida } que persiste automáticamente en disco
    (solo las claves) cada vez que se añade o elimina una partida.
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


# Registro central: { channel_id: Partida }
partidas_activas: dict[int, Partida] = _PartidasActivasDict()


# ═══════════════════════════════════════════════════════════════════════════════
#  EVENTOS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"⚡ {bot.user} online. Waiting for trainers...")

    # Si es una reconexión automática de Gateway, NO reinicializamos ni borramos partidas activas
    if getattr(bot, "_ya_iniciado", False):
        print("🔄 [on_ready] Reconexión exitosa de Gateway. Partidas activas y webhook preservados.")
        return
    bot._ya_iniciado = True

    try:
        await init_db()
        print("[DuckDB] DuckDB initialized.")
    except Exception as e:
        print(f"[DuckDB] Error initializing DuckDB: {e}")

    try:
        sync = await bot.tree.sync()
        print(f"🌐 {len(sync)} slash commands synced.")
    except Exception as e:
        print(f"Sync error: {e}")

    # Asegurar que el rol PokeHost exista en todos los servidores actuales
    for g in bot.guilds:
        try:
            await asegurar_rol_pokehost(g)
        except Exception as e:
            print(f"[on_ready] Error asegurando rol en {g.name}: {e}")

    # Iniciar listener de webhook Top.gg
    bot.loop.create_task(iniciar_webhook_topgg(bot))

    # ── Recuperación tras reinicio ───────────────────────────────────────────
    canales_previos = _cargar_sesiones_previas()
    for channel_id in canales_previos:
        try:
            canal = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            gid = canal.guild.id if getattr(canal, "guild", None) else None
            await canal.send(t("session_lost_after_restart", gid))
        except Exception as e:
            print(f"[on_ready] No se pudo avisar en canal {channel_id}: {e}")

    partidas_activas.clear()
    _guardar_sesiones_activas()


@bot.event
async def on_guild_join(guild: discord.Guild):
    print(f"📥 Bot añadido al servidor: {guild.name} ({guild.id})")
    await asegurar_rol_pokehost(guild)

    target_channel = guild.system_channel
    if not (target_channel and target_channel.permissions_for(guild.me).send_messages):
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                target_channel = ch
                break

    if target_channel:
        try:
            gid = guild.id
            embed = discord.Embed(
                title=t("welcome_title", gid),
                description=t("welcome_desc", gid),
                color=discord.Color.from_rgb(255, 203, 5),
            )
            embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
            client_id = bot.user.id if bot.user else 1135381488775463075
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=f"https://top.gg/bot/{client_id}/vote?guild={gid}", style=discord.ButtonStyle.link))
            view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
            await target_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"[on_guild_join] Error enviando bienvenida en {guild.name}: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"[Slash Command Error] {interaction.command.name if interaction.command else 'Unknown'}: {error}")
    msg = "⚠️ An unexpected error occurred while executing this command. / Ocurrió un error inesperado al ejecutar el comando."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS (29 GLOBALES LIMPIOS)
# ═══════════════════════════════════════════════════════════════════════════════

# 1 & 2. /impregister & /play-kyu
@bot.tree.command(name="impregister", description="Open a new PokeImpostor lobby / Abrir sala de PokeImpostor")
async def impregister(interaction: discord.Interaction):
    if interaction.guild_id is None or interaction.guild is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id
    await asegurar_rol_pokehost(interaction.guild)

    if not es_anfitrion_o_admin(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            t("register_only_host", gid, role=obtener_nombre_rol_host(interaction.guild)),
            ephemeral=True,
        )

    if interaction.channel.id in partidas_activas:
        return await interaction.response.send_message(t("register_already_active", gid), ephemeral=True)

    nueva = Partida(canal=interaction.channel, partidas_activas=partidas_activas)
    partidas_activas[interaction.channel.id] = nueva
    view = PanelInscripcion(nueva)
    await interaction.response.send_message(embed=_build_embed_lobby(nueva), view=view)
    try:
        view.message = await interaction.original_response()
        nueva.mensaje_lobby = view.message
    except Exception:
        pass


@bot.tree.command(name="play-kyu", description="Start a new PokeImpostor lobby / Iniciar sala de PokeImpostor")
async def play_kyu(interaction: discord.Interaction):
    await impregister(interaction)


# 3 & 4. /impver & /role-kyu
@bot.tree.command(name="impver", description="Re-send your role by DM (only during an active game)")
async def impver(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    partida = partidas_activas.get(interaction.channel.id)
    ok, msg_key = await reenviar_rol_secreto(partida, interaction.user, gid)
    await interaction.response.send_message(t(msg_key, gid), ephemeral=True)


@bot.tree.command(name="role-kyu", description="Re-send your secret role by DM / Reenviar rol secreto por DM")
async def role_kyu(interaction: discord.Interaction):
    await impver(interaction)


# 5 & 6. /implang & /lang-kyu
async def _ejecutar_cambio_idioma(interaction: discord.Interaction, language: str):
    if interaction.guild_id is None or interaction.guild is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id
    if not es_anfitrion_o_admin(interaction.user, interaction.guild):
        return await interaction.response.send_message(t("lang_only_admin", gid), ephemeral=True)

    set_lang(gid, language)
    key = "lang_changed_en" if language == "en" else "lang_changed_es"
    await interaction.response.send_message(t(key, gid))


@bot.tree.command(name="implang", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def implang(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


@bot.tree.command(name="lang-kyu", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def lang_kyu(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


# 7 & 8. /imphelp & /help-kyu
@bot.tree.command(name="imphelp", description="How to play PokeImpostor / Cómo jugar")
async def imphelp(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    await interaction.response.send_message(embed=construir_embed_ayuda(gid))


@bot.tree.command(name="help-kyu", description="How to play PokeImpostor / Cómo jugar")
async def help_kyu(interaction: discord.Interaction):
    await imphelp(interaction)


# 9 & 10. /impcreditos & /credits-kyu
@bot.tree.command(name="impcreditos", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def impcreditos(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    await interaction.response.send_message(embed=construir_embed_creditos(gid))


@bot.tree.command(name="credits-kyu", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def credits_kyu(interaction: discord.Interaction):
    await impcreditos(interaction)


# 11 & 12. /impprofile & /profile-kyu
async def _ejecutar_perfil(interaction: discord.Interaction, usuario: discord.Member | None = None):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id
    target = usuario or interaction.user
    embed, err = await construir_embed_perfil(gid, target)
    if err:
        return await interaction.response.send_message(t(err, gid), ephemeral=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impprofile", description="View your or another trainer's profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def impprofile(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


@bot.tree.command(name="profile-kyu", description="View trainer profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def profile_kyu(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


# 13 & 14. /impleaderboard & /leaderboard-kyu
async def _ejecutar_ranking(interaction: discord.Interaction, categoria: str = "general"):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id
    embed, err = await construir_embed_ranking(gid, categoria)
    if err:
        return await interaction.response.send_message(t(err, gid), ephemeral=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impleaderboard", description="View the server leaderboard / Ver tabla de clasificación")
@app_commands.describe(categoria="Leaderboard category / Categoría de la clasificación")
@app_commands.choices(categoria=[
    app_commands.Choice(name="🏆 General (Most Wins / Victorias)", value="general"),
    app_commands.Choice(name="🔪 Impostors (Deadliest Impostors)", value="impostores"),
    app_commands.Choice(name="🔍 Crewmates (Best Detectives)", value="detectives"),
])
async def impleaderboard(interaction: discord.Interaction, categoria: str = "general"):
    await _ejecutar_ranking(interaction, categoria)


@bot.tree.command(name="leaderboard-kyu", description="View the server leaderboard / Ver tabla de clasificación")
@app_commands.describe(categoria="Leaderboard category / Categoría de la clasificación")
@app_commands.choices(categoria=[
    app_commands.Choice(name="🏆 General (Most Wins / Victorias)", value="general"),
    app_commands.Choice(name="🔪 Impostors (Deadliest Impostors)", value="impostores"),
    app_commands.Choice(name="🔍 Crewmates (Best Detectives)", value="detectives"),
])
async def leaderboard_kyu(interaction: discord.Interaction, categoria: str = "general"):
    await _ejecutar_ranking(interaction, categoria)


# 15 & 16. /impstats & /stats-kyu
async def _ejecutar_stats(interaction: discord.Interaction):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id
    embed, err = await construir_embed_stats(gid)
    if err:
        return await interaction.response.send_message(t(err, gid), ephemeral=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impstats", description="Global game statistics on this server / Estadísticas de partidas en este servidor")
async def impstats(interaction: discord.Interaction):
    await _ejecutar_stats(interaction)


@bot.tree.command(name="stats-kyu", description="Global game statistics on this server / Estadísticas de partidas en este servidor")
async def stats_kyu(interaction: discord.Interaction):
    await _ejecutar_stats(interaction)


# 17 & 18. /impgenkey & /genkey-kyu
class ModalGenerarKey(discord.ui.Modal):
    def __init__(self, gid: int):
        super().__init__(title="PokeImpostor — Generar Clave VIP")
        self.gid = gid
        self.password_input = discord.ui.TextInput(
            label="Master Password (MASTER_AUTH_KEY)",
            placeholder="••••••••••••",
            required=True,
            style=discord.TextStyle.short,
        )
        self.tipo_input = discord.ui.TextInput(
            label="Tipo de Licencia (vitalicio / cargas)",
            placeholder="vitalicio ($5 USD) o cargas (ej. 10)",
            default="vitalicio",
            required=True,
            style=discord.TextStyle.short,
        )
        self.valor_input = discord.ui.TextInput(
            label="Partidas (solo si eliges cargas)",
            placeholder="10 (por defecto 10 partidas)",
            default="10",
            required=False,
            style=discord.TextStyle.short,
        )
        self.add_item(self.password_input)
        self.add_item(self.tipo_input)
        self.add_item(self.valor_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not verificar_master_password(self.password_input.value.strip()):
            return await interaction.response.send_message(t("license_auth_failed", self.gid), ephemeral=True)

        tipo_raw = self.tipo_input.value.strip().lower()
        val_str = self.valor_input.value.strip().lower()

        if "carg" in tipo_raw or "partid" in tipo_raw or "voto" in tipo_raw:
            tipo = "cargas"
            import re
            nums = re.findall(r"\d+", val_str)
            cargas = int(nums[0]) if nums else 10
            duracion_dias = 0
            detalle = f"{cargas} Partidas VIP con todo desbloqueado (Top.gg / Cargas)"
        else:
            tipo = "permanente"
            duracion_dias = 0
            cargas = 0
            detalle = "Membresía VIP Vitalicia ($5 USD) Permanente de por vida"

        nueva_key = generar_codigo_licencia()
        exito = await crear_licencia_async(nueva_key, tipo, duracion_dias, cargas)

        if not exito:
            return await interaction.response.send_message("❌ Error al registrar la clave en la base de datos.", ephemeral=True)

        embed = discord.Embed(
            title=t("license_key_gen_title", self.gid),
            description=t("license_key_generated", self.gid, key=nueva_key, tipo=tipo.upper(), details=detalle),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def _ejecutar_generarkey(interaction: discord.Interaction):
    if interaction.guild_id != SERVER_ADMIN_CENTRAL_ID:
        return await interaction.response.send_message(
            f"⛔ Este comando solo puede ser ejecutado en el servidor central autorizado (ID: {SERVER_ADMIN_CENTRAL_ID}).",
            ephemeral=True
        )
    es_dueno = await bot.is_owner(interaction.user) or (
        os.getenv("OWNER_ID") and str(interaction.user.id) == os.getenv("OWNER_ID").strip()
    )
    if not es_dueno:
        return await interaction.response.send_message(
            "⛔ Access Denied: This command is restricted to the bot owner.",
            ephemeral=True
        )
    gid = interaction.guild_id or 0
    await interaction.response.send_modal(ModalGenerarKey(gid))


@bot.tree.command(name="impgenkey", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def impgenkey(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


@bot.tree.command(name="genkey-kyu", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def genkey_kyu(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


# 19 & 20. /impredeem & /redeem-kyu
async def _ejecutar_canjear(interaction: discord.Interaction, clave: str):
    if interaction.guild_id is None or interaction.guild is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id

    if not es_anfitrion_o_admin(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            t("redeem_only_host", gid, role=obtener_nombre_rol_host(interaction.guild)),
            ephemeral=True
        )

    embed, err = await canjear_clave_licencia(clave.strip(), gid, interaction.user.id)
    if err:
        return await interaction.response.send_message(t(err, gid), ephemeral=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impredeem", description="Redeem a VIP License Key for this server / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def impredeem(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


@bot.tree.command(name="redeem-kyu", description="Redeem a VIP License Key / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def redeem_kyu(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


# 21 & 22. /implicense & /license-kyu
async def _ejecutar_licencia(interaction: discord.Interaction):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id
    client_id = bot.user.id if bot.user else 1135381488775463075
    embed, view = await construir_payload_licencia(gid, client_id)
    if view:
        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="implicense", description="Check this server's license and VIP tier / Consultar estado de licencia")
async def implicense(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


@bot.tree.command(name="license-kyu", description="Check this server's license / Consultar estado de licencia")
async def license_kyu(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


# 23. /vote-kyu
@bot.tree.command(name="vote-kyu", description="Vote on Top.gg for 10 free premium matches / Votar en Top.gg")
async def vote_kyu(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    client_id = bot.user.id if bot.user else 1135381488775463075
    embed, view = construir_payload_voto(gid, client_id)
    await interaction.response.send_message(embed=embed, view=view)


# 24. /donate-kyu
@bot.tree.command(name="donate-kyu", description="Support the bot & get Lifetime VIP ($5 USD) / Donar")
async def donate_kyu(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    embed, view = construir_payload_donar(gid)
    await interaction.response.send_message(embed=embed, view=view)


# 25. /invite-kyu
@bot.tree.command(name="invite-kyu", description="Invite Mimikyu to another server / Invitar a Mimikyu")
async def invite_kyu(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    client_id = bot.user.id if bot.user else 1135381488775463075
    embed, view = construir_payload_invitar(gid, client_id)
    await interaction.response.send_message(embed=embed, view=view)


# 26 & 27. /impsetrole & /setrole-kyu
async def _ejecutar_setrole(
    interaction: discord.Interaction,
    role: discord.Role | None = None,
    assign_to: discord.Member | None = None,
):
    if interaction.guild_id is None or interaction.guild is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id
    es_admin = (
        getattr(interaction.user, "guild_permissions", None)
        and interaction.user.guild_permissions.administrator
    ) or (interaction.user == interaction.guild.owner)

    if not es_admin:
        return await interaction.response.send_message(t("setrole_admin_only", gid), ephemeral=True)

    embed, err = await ejecutar_setrole_comun(interaction.guild, interaction.user, role, assign_to)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impsetrole", description="Set or create the PokeImpostor host role / Configurar o crear rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def impsetrole(interaction: discord.Interaction, role: discord.Role | None = None, assign_to: discord.Member | None = None):
    await _ejecutar_setrole(interaction, role, assign_to)


@bot.tree.command(name="setrole-kyu", description="Set or create the PokeImpostor host role / Configurar rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def setrole_kyu(interaction: discord.Interaction, role: discord.Role | None = None, assign_to: discord.Member | None = None):
    await _ejecutar_setrole(interaction, role, assign_to)


# 28 & 29. /imppartner_add & /partner-kyu
async def _ejecutar_partner_add(interaction: discord.Interaction, servidor_id: str, motivo: str):
    if interaction.guild_id != SERVER_ADMIN_CENTRAL_ID:
        return await interaction.response.send_message(
            f"⛔ Este comando solo puede ser ejecutado en el servidor central autorizado (ID: {SERVER_ADMIN_CENTRAL_ID}).",
            ephemeral=True
        )
    es_dueno = await bot.is_owner(interaction.user) or (
        os.getenv("OWNER_ID") and str(interaction.user.id) == os.getenv("OWNER_ID").strip()
    )
    if not es_dueno:
        return await interaction.response.send_message("⛔ Access Denied: Bot owner only.", ephemeral=True)

    gid = interaction.guild_id or 0

    class ModalPartnerAuth(discord.ui.Modal):
        def __init__(self):
            super().__init__(title="PokeImpostor — Autorizar Beta Partner")
            self.pwd = discord.ui.TextInput(
                label="Master Password (MASTER_AUTH_KEY)",
                placeholder="••••••••••••",
                required=True,
                style=discord.TextStyle.short,
            )
            self.add_item(self.pwd)

        async def on_submit(self, modal_inter: discord.Interaction):
            if not verificar_master_password(self.pwd.value.strip()):
                return await modal_inter.response.send_message(t("license_auth_failed", gid), ephemeral=True)
            try:
                target_gid = int(servidor_id.strip())
            except ValueError:
                return await modal_inter.response.send_message("❌ ID de servidor inválido.", ephemeral=True)

            ok = await registrar_servidor_partner_async(target_gid, motivo)
            if ok:
                await modal_inter.response.send_message(t("partner_register_success", gid, guild_id=servidor_id), ephemeral=True)
            else:
                await modal_inter.response.send_message("❌ Error al registrar partner.", ephemeral=True)

    await interaction.response.send_modal(ModalPartnerAuth())


@bot.tree.command(name="imppartner_add", description="Owner only: Grant permanent Beta Partner status to a server")
@app_commands.describe(servidor_id="Guild ID / ID del servidor", motivo="Partner description / Motivo")
async def imppartner_add(interaction: discord.Interaction, servidor_id: str, motivo: str = "Beta Tester Fundador"):
    await _ejecutar_partner_add(interaction, servidor_id, motivo)


@bot.tree.command(name="partner-kyu", description="Owner only: Grant permanent Beta Partner status to a server")
@app_commands.describe(servidor_id="Guild ID / ID del servidor", motivo="Partner description / Motivo")
async def partner_kyu(interaction: discord.Interaction, servidor_id: str, motivo: str = "Beta Tester Fundador"):
    await _ejecutar_partner_add(interaction, servidor_id, motivo)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERCEPTOR DE MENSAJES DE TEXTO (-imp sufijo y prefijo)
# ═══════════════════════════════════════════════════════════════════════════════

def _extraer_comando_imp(texto: str) -> tuple[bool, str, list[str]]:
    """
    Detecta si un mensaje de texto es un comando para PokeImpostor.
    Soporta sufijos (-mimi, mimi, -imp) y prefijos (-mimi, !mimi, -imp, etc.).
    """
    s = texto.strip()
    if not s:
        return False, "", []

    cmd_str = None
    low = s.lower()

    # Sufijos (-mimi, -imp)
    if low.endswith(" -mimi"):
        cmd_str = s[:-6].strip()
    elif low.endswith("-mimi"):
        cmd_str = s[:-5].strip()
    elif low.endswith(" -imp"):
        cmd_str = s[:-5].strip()
    elif low.endswith("-imp"):
        cmd_str = s[:-4].strip()

    # Prefijos (mimi, -mimi, !mimi, /mimi, -imp, !imp, /imp)
    elif low.startswith("-mimi "):
        cmd_str = s[6:].strip()
    elif low.startswith("!mimi "):
        cmd_str = s[6:].strip()
    elif low.startswith("/mimi "):
        cmd_str = s[6:].strip()
    elif low.startswith("mimi "):
        cmd_str = s[5:].strip()
    elif low.startswith("-imp "):
        cmd_str = s[5:].strip()
    elif low.startswith("!imp "):
        cmd_str = s[5:].strip()
    elif low.startswith("/imp "):
        cmd_str = s[5:].strip()

    # Invocaciones directas
    elif low in ("mimi", "-mimi", "!mimi", "-imp", "!imp"):
        cmd_str = "help"
    elif low in ("/play-kyu", "/jugar-kyu", "/play", "/jugar", "/imp", "/mimi"):
        cmd_str = "play"

    if cmd_str is None:
        return False, "", []

    partes = cmd_str.split()
    if not partes:
        return True, "help", []

    raw_nombre = partes[0].lower().removeprefix("/").removeprefix("mimi").removeprefix("imp")
    nombre = raw_nombre.removesuffix("-kyu").removesuffix("kyu")
    if nombre == "":
        nombre = "help"
    args = partes[1:]
    return True, nombre, args


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    es_cmd, cmd, args = _extraer_comando_imp(message.content)
    if not es_cmd:
        await bot.process_commands(message)
        return

    gid = message.guild.id

    # 1. play / jugar / register / sala
    if cmd in ("play", "jugar", "register", "registrar", "sala", "lobby", "start", "iniciar"):
        await asegurar_rol_pokehost(message.guild)
        if not es_anfitrion_o_admin(message.author, message.guild):
            await message.reply(t("register_only_host", gid, role=obtener_nombre_rol_host(message.guild)), mention_author=False)
            return

        if message.channel.id in partidas_activas:
            await message.reply(t("register_already_active", gid), mention_author=False)
            return

        nueva = Partida(canal=message.channel, partidas_activas=partidas_activas)
        partidas_activas[message.channel.id] = nueva
        view = PanelInscripcion(nueva)
        msg_lobby = await message.channel.send(embed=_build_embed_lobby(nueva), view=view)
        view.message = msg_lobby
        nueva.mensaje_lobby = msg_lobby
        return

    # 2. ver / impver / rol
    elif cmd in ("ver", "rol", "role", "myrole"):
        partida = partidas_activas.get(message.channel.id)
        ok, msg_key = await reenviar_rol_secreto(partida, message.author, gid)
        if ok:
            try:
                await message.add_reaction("📬")
            except Exception:
                await message.reply(t(msg_key, gid), delete_after=10, mention_author=False)
        else:
            await message.reply(t(msg_key, gid), mention_author=False)
        return

    # 3. perfil / profile
    elif cmd in ("perfil", "profile"):
        target = message.mentions[0] if message.mentions else message.author
        embed, err = await construir_embed_perfil(gid, target)
        if err:
            await message.reply(t(err, gid), mention_author=False)
            return
        await message.reply(embed=embed, mention_author=False)
        return

    # 4. ranking / leaderboard / top
    elif cmd in ("ranking", "leaderboard", "top"):
        cat = "general"
        if args:
            arg_low = args[0].lower()
            if "imp" in arg_low:
                cat = "impostores"
            elif "trip" in arg_low or "det" in arg_low or "crew" in arg_low:
                cat = "detectives"

        embed, err = await construir_embed_ranking(gid, cat)
        if err:
            await message.reply(t(err, gid), mention_author=False)
            return
        await message.reply(embed=embed, mention_author=False)
        return

    # 5. stats / serverstats / partidas
    elif cmd in ("stats", "stats_partidas", "serverstats", "partidas"):
        embed, err = await construir_embed_stats(gid)
        if err:
            await message.reply(t(err, gid), mention_author=False)
            return
        await message.reply(embed=embed, mention_author=False)
        return

    # 6. licencia / license / vip / tier
    elif cmd in ("licencia", "license", "vip", "tier"):
        client_id = bot.user.id if bot.user else 1135381488775463075
        embed, view = await construir_payload_licencia(gid, client_id)
        if view:
            await message.reply(embed=embed, view=view, mention_author=False)
        else:
            await message.reply(embed=embed, mention_author=False)
        return

    # 7. canjear / redeem
    elif cmd in ("canjear", "redeem"):
        if not es_anfitrion_o_admin(message.author, message.guild):
            await message.reply(t("redeem_only_host", gid, role=obtener_nombre_rol_host(message.guild)), mention_author=False)
            return

        if not args:
            await message.reply("⚠️ Usage: `mimi redeem <KEY>` (or `redeem <KEY> -mimi`) / Uso: `mimi canjear <CLAVE>` (o `canjear <CLAVE> -mimi`)", mention_author=False)
            return

        embed, err = await canjear_clave_licencia(args[0].strip(), gid, message.author.id)
        if err:
            await message.reply(t(err, gid), mention_author=False)
            return
        await message.reply(embed=embed, mention_author=False)
        return

    # 8. lang / idioma
    elif cmd in ("lang", "language", "idioma", "idiomas", "lenguaje"):
        if not es_anfitrion_o_admin(message.author, message.guild):
            await message.reply(t("lang_only_admin", gid), mention_author=False)
            return

        if not args:
            await message.reply("⚠️ Usage: `mimi lang <en|es>` (or `lang en -mimi`) / Uso: `mimi idioma <es|en>` (o `idioma es -mimi`)", mention_author=False)
            return

        elegido = args[0].lower()
        if elegido in ("en", "english", "ingles", "inglés"):
            set_lang(gid, "en")
            await message.reply(t("lang_changed_en", gid), mention_author=False)
        elif elegido in ("es", "spanish", "espanol", "español"):
            set_lang(gid, "es")
            await message.reply(t("lang_changed_es", gid), mention_author=False)
        else:
            await message.reply("⚠️ Valid options: `en` or `es` / Opciones válidas: `en` o `es`", mention_author=False)
        return

    # 9. generarkey / genkey
    elif cmd in ("generarkey", "genkey", "impgenkey"):
        await message.reply("🔐 For Discord security and password entry, please use the slash command: `/impgenkey`", mention_author=False)
        return

    # 10. help / ayuda / guia
    elif cmd in ("help", "ayuda", "guia", "guide"):
        await message.reply(embed=construir_embed_ayuda(gid), mention_author=False)
        return

    # 11. creditos / credits / arte
    elif cmd in ("creditos", "credito", "credits", "credit", "arte", "art", "artista", "artist"):
        await message.reply(embed=construir_embed_creditos(gid), mention_author=False)
        return

    # 12. setrole / hostrole / rolesetup
    elif cmd in ("setrole", "hostrole", "impsetrole", "imphostrole", "rolesetup"):
        es_admin = (
            getattr(message.author, "guild_permissions", None)
            and message.author.guild_permissions.administrator
        ) or (message.author == message.guild.owner)

        if not es_admin:
            await message.reply(t("setrole_admin_only", gid), mention_author=False)
            return

        target_role = message.role_mentions[0] if message.role_mentions else None
        target_user = message.mentions[0] if message.mentions else None

        embed, err = await ejecutar_setrole_comun(message.guild, message.author, target_role, target_user, args=args)
        if err:
            await message.reply(err, mention_author=False)
            return
        await message.reply(embed=embed, mention_author=False)
        return

    # 13. vote / votar / voto
    elif cmd in ("vote", "votar", "voto"):
        client_id = bot.user.id if bot.user else 1135381488775463075
        embed, view = construir_payload_voto(gid, client_id)
        await message.reply(embed=embed, view=view, mention_author=False)
        return

    # 14. donar / donate / kofi
    elif cmd in ("donar", "donate", "dona", "donation", "kofi", "buymeacoffee", "coffee"):
        embed, view = construir_payload_donar(gid)
        await message.reply(embed=embed, view=view, mention_author=False)
        return

    # 15. invite / invitar
    elif cmd in ("invite", "invitar", "invitacion", "invitación"):
        client_id = bot.user.id if bot.user else 1135381488775463075
        embed, view = construir_payload_invitar(gid, client_id)
        await message.reply(embed=embed, view=view, mention_author=False)
        return

    # 16. debug / bots (Rellenar sala con bots fantasma para pruebas en solitario)
    elif cmd in ("debug", "bots", "fill", "test"):
        SERVIDORES_DEV_TEST = (402155389958881310, 774891658508107776)
        if gid not in SERVIDORES_DEV_TEST:
            return
        if not es_anfitrion_o_admin(message.author, message.guild):
            return
        partida = partidas_activas.get(message.channel.id)
        if partida is None:
            await message.reply("⚠️ Primero abre una sala con `/play-kyu` o `-mimi play`.", mention_author=False)
            return

        from motor_juego import DummyMember, CaosVariante, ModoJuego

        cantidad = 3
        var_arg = None
        for a in args:
            if a.isdigit():
                cantidad = int(a)
            else:
                var_arg = a

        cantidad = max(1, min(10, cantidad))

        agregados = 0
        async with partida.lock:
            if not any(j.id == message.author.id for j in partida.jugadores):
                partida.jugadores.append(message.author)

            nombres_bots = ["Ash", "Misty", "Brock", "Gary", "Cynthia", "Red", "Dawn", "Serena", "N", "Lance"]
            for idx, nom in enumerate(nombres_bots):
                if agregados >= cantidad or len(partida.jugadores) >= 24:
                    break
                fake_id = 900000 + idx
                if not any(j.id == fake_id for j in partida.jugadores):
                    partida.jugadores.append(DummyMember(fake_id, nom, message.author))
                    agregados += 1

        variante_nombre = None
        if var_arg:
            v_low = var_arg.lower()
            for v in CaosVariante:
                if v_low in (v.value.lower(), v.name.lower()):
                    partida.config.caos_variante = v
                    partida.config.modo_juego = ModoJuego.CAOS
                    variante_nombre = v.value
                    break

        if getattr(partida, "mensaje_lobby", None):
            try:
                from vistas.common import build_embed_lobby
                await partida.mensaje_lobby.edit(embed=build_embed_lobby(partida))
            except Exception:
                pass

        det_caos = f"\n🌀 **Variante Caos forzada:** `{variante_nombre}`" if variante_nombre else ""
        await message.reply(
            f"🧪 **Modo Debug Activado:** Se unieron **{agregados} bots fantasma** a la sala "
            f"(Total: **{len(partida.jugadores)}** jugadores). Todos sus DMs te llegarán a ti.{det_caos}",
            mention_author=False,
        )
        return

    await bot.process_commands(message)


# ═══════════════════════════════════════════════════════════════════════════════
#  ARRANQUE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not found. Create a .env file with DISCORD_TOKEN=your_token")
    else:
        bot.run(TOKEN)
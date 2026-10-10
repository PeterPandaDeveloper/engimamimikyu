"""
main.py — Entry point de PokeImpostor
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import urllib.parse
import aiohttp.web
from dotenv import load_dotenv

from motor_juego import Partida
from vistas import (
    PanelInscripcion,
    _build_embed_lobby,
    NOMBRE_ROL_HOST,
    es_anfitrion_o_admin,
    obtener_nombre_rol_host,
)
from api import cerrar_session
from i18n import t, set_lang, get_lang
from db import (
    init_db,
    close_db,
    obtener_perfil_jugador_async,
    obtener_ranking_async,
    obtener_stats_servidor_async,
    crear_licencia_async,
    canjear_licencia_async,
    verificar_estado_premium_async,
    registrar_servidor_partner_async,
    sumar_partidas_voto_async,
    get_guild_rol_host,
    set_guild_rol_host_async,
)
from security import verificar_master_password, generar_codigo_licencia

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="pkmi!", intents=intents)

BUYMEACOFFEE_URL = "https://buymeacoffee.com/peterpandadeveloperz"
INVITE_PERMS_INT = 268817624

# Servidor central autorizado exclusivamente para generar keys y gestionar partners
SERVER_ADMIN_CENTRAL_ID = 402155389958881310

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


async def asegurar_rol_pokehost(guild: discord.Guild) -> discord.Role | None:
    """
    Busca el rol configurado o PokeHost en el servidor, o lo crea automáticamente
    con color distintivo si no existe.
    """
    if guild is None:
        return None

    cfg_id = get_guild_rol_host(guild.id)
    if cfg_id:
        r_cfg = guild.get_role(cfg_id)
        if r_cfg is not None:
            return r_cfg

    rol = discord.utils.get(guild.roles, name=NOMBRE_ROL_HOST)
    if rol is None:
        try:
            rol = await guild.create_role(
                name=NOMBRE_ROL_HOST,
                color=discord.Color.from_rgb(255, 203, 5),  # Amarillo insignia Pokémon
                mentionable=True,
                reason="Rol para anfitriones de PokeImpostor (crear y gestionar salas)",
            )
            print(f"[Roles] ✅ Rol '{NOMBRE_ROL_HOST}' creado exitosamente en {guild.name} ({guild.id})")
        except discord.Forbidden:
            print(f"[Roles] ⚠️ Sin permisos suficientes para crear el rol '{NOMBRE_ROL_HOST}' en {guild.name}")
        except Exception as e:
            print(f"[Roles] ❌ Error al crear rol '{NOMBRE_ROL_HOST}' en {guild.name}: {e}")
    return rol


# ═══════════════════════════════════════════════════════════════════════════════
#  WEBHOOK TOP.GG (ACREDITACIÓN AUTOMÁTICA DE VOTOS)
# ═══════════════════════════════════════════════════════════════════════════════

_webhook_runner: aiohttp.web.AppRunner | None = None

async def handle_topgg_webhook(request: aiohttp.web.Request) -> aiohttp.web.Response:
    # 1. Validación de seguridad opcional (si se configura TOPGG_WEBHOOK_SECRET en .env)
    expected_auth = os.getenv("TOPGG_WEBHOOK_SECRET", "").strip()
    if expected_auth:
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header != expected_auth:
            print("[Top.gg Webhook] ⛔ Intento de acceso con Authorization inválido.")
            return aiohttp.web.Response(status=401, text="Unauthorized")

    try:
        data = await request.json()
    except Exception as e:
        print(f"[Top.gg Webhook] ❌ Error leyendo cuerpo JSON: {e}")
        return aiohttp.web.Response(status=400, text="Bad Request")

    user_raw = data.get("user")
    if not user_raw:
        return aiohttp.web.Response(status=400, text="Missing user field")

    try:
        user_id = int(user_raw)
    except ValueError:
        return aiohttp.web.Response(status=400, text="Invalid user ID")

    # 2. Detección del servidor objetivo:
    # Prioridad A: query string (?guild=12345)
    guild_id = None
    query_str = data.get("query", "")
    if query_str:
        params = urllib.parse.parse_qs(query_str.lstrip("?"))
        if "guild" in params and params["guild"][0].isdigit():
            guild_id = int(params["guild"][0])

    # Prioridad B: servidor con más partidas del usuario en DuckDB
    if guild_id is None:
        try:
            from db import _get_connection, _DB_LOCK
            with _DB_LOCK:
                con = _get_connection()
                row = con.execute(
                    "SELECT guild_id FROM perfiles_jugadores WHERE user_id = ? ORDER BY total_partidas DESC, victorias DESC LIMIT 1;",
                    [user_id]
                ).fetchone()
                if row:
                    guild_id = row[0]
        except Exception as e:
            print(f"[Top.gg Webhook] Error consultando perfil: {e}")

    # Prioridad C: primer servidor compartido entre el bot y el usuario
    if guild_id is None:
        for g in bot.guilds:
            if g.get_member(user_id):
                guild_id = g.id
                break

    if guild_id is None:
        print(f"[Top.gg Webhook] ⚠️ Voto recibido de usuario {user_id}, pero no se encontró servidor asociado.")
        return aiohttp.web.json_response({"status": "received_no_guild", "user_id": user_id})

    # 3. Sumar 10 partidas premium
    nuevas = await sumar_partidas_voto_async(guild_id, 10)
    print(f"🗳️ [Top.gg Webhook] ¡Voto exitoso! Usuario {user_id} -> Servidor {guild_id}. Partidas totales: {nuevas}")

    # 4. Enviar anuncio en el canal del servidor
    guild = bot.get_guild(guild_id)
    if guild:
        target_ch = guild.system_channel
        if not (target_ch and target_ch.permissions_for(guild.me).send_messages):
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    target_ch = ch
                    break
        if target_ch:
            try:
                embed = discord.Embed(
                    title=t("vote_announced_title", guild_id),
                    description=t("vote_announced_desc", guild_id, user=f"<@{user_id}>", count=nuevas),
                    color=discord.Color.from_rgb(255, 105, 180),
                )
                embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
                await target_ch.send(embed=embed)
            except Exception as e:
                print(f"[Top.gg Webhook] No se pudo enviar anuncio en {guild.name}: {e}")

    return aiohttp.web.json_response({
        "status": "success",
        "user_id": user_id,
        "guild_id": guild_id,
        "partidas_totales": nuevas,
    })


async def iniciar_webhook_topgg():
    global _webhook_runner
    port = int(os.getenv("TOPGG_WEBHOOK_PORT", "5000"))
    app = aiohttp.web.Application()
    app.router.add_post("/topgg-webhook", handle_topgg_webhook)
    app.router.add_post("/dblwebhook", handle_topgg_webhook)
    app.router.add_get("/", lambda req: aiohttp.web.Response(text="PokeImpostor Top.gg Webhook Active ⚡"))
    _webhook_runner = aiohttp.web.AppRunner(app)
    await _webhook_runner.setup()
    site = aiohttp.web.TCPSite(_webhook_runner, "0.0.0.0", port)
    try:
        await site.start()
        print(f"🗳️ [Top.gg Webhook] Servidor escuchando en http://0.0.0.0:{port}/topgg-webhook")
    except Exception as e:
        print(f"⚠️ [Top.gg Webhook] No se pudo iniciar en el puerto {port}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  EVENTOS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"⚡ {bot.user} online. Waiting for trainers...")
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
    bot.loop.create_task(iniciar_webhook_topgg())

    # ── Recuperación tras reinicio ───────────────────────────────────────────
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

    partidas_activas.clear()
    _guardar_sesiones_activas()


@bot.event
async def on_guild_join(guild: discord.Guild):
    print(f"📥 Bot añadido al servidor: {guild.name} ({guild.id})")
    await asegurar_rol_pokehost(guild)

    # Buscar canal adecuado para el mensaje de bienvenida
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
            client_id = bot.user.id if bot.user else 1195913386899296347
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=f"https://top.gg/bot/{client_id}/vote?guild={gid}", style=discord.ButtonStyle.link))
            view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
            await target_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"[on_guild_join] Error enviando bienvenida en {guild.name}: {e}")


@bot.event
async def on_close():
    global _webhook_runner
    if _webhook_runner:
        try:
            await _webhook_runner.cleanup()
            print("🔌 Top.gg Webhook runner stopped.")
        except Exception as e:
            print(f"Error deteniendo webhook runner: {e}")

    await cerrar_session()
    print("🔌 HTTP session closed.")
    try:
        await close_db()
        print("[DuckDB] Connection closed cleanly.")
    except Exception as e:
        print(f"[DuckDB] Error closing database: {e}")


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
#  /impregister
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="impregister", description="Open a new PokeImpostor lobby / Abrir sala de PokeImpostor")
async def impregister(interaction: discord.Interaction):
    # Este juego depende de roles de servidor, DMs a
    # miembros del servidor, e idioma por servidor. No tiene sentido fuera
    # de un guild (ej. DMs directos al bot).
    if interaction.guild_id is None or interaction.guild is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id

    # Asegurar que el rol PokeHost existe en el servidor
    await asegurar_rol_pokehost(interaction.guild)

    # Validar permisos: debe tener el rol PokeHost o ser Administrador
    if not es_anfitrion_o_admin(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            t("register_only_host", gid, role=obtener_nombre_rol_host(interaction.guild)),
            ephemeral=True,
        )

    if interaction.channel.id in partidas_activas:
        return await interaction.response.send_message(
            t("register_already_active", gid), ephemeral=True
        )
    nueva = Partida(canal=interaction.channel, partidas_activas=partidas_activas)
    partidas_activas[interaction.channel.id] = nueva
    view = PanelInscripcion(nueva)
    await interaction.response.send_message(
        embed=_build_embed_lobby(nueva),
        view=view,
    )
    try:
        view.message = await interaction.original_response()
    except Exception:
        pass


@bot.tree.command(name="play-kyu", description="Start a new PokeImpostor lobby / Iniciar sala de PokeImpostor")
async def play_kyu(interaction: discord.Interaction):
    await impregister(interaction)


@bot.tree.command(name="jugar-kyu", description="Start a new PokeImpostor lobby / Iniciar sala de PokeImpostor")
async def jugar_kyu(interaction: discord.Interaction):
    await impregister(interaction)


@bot.tree.command(name="play", description="Start a new PokeImpostor lobby / Iniciar sala de PokeImpostor")
async def play_cmd(interaction: discord.Interaction):
    await impregister(interaction)


@bot.tree.command(name="jugar", description="Start a new PokeImpostor lobby / Iniciar sala de PokeImpostor")
async def jugar_cmd(interaction: discord.Interaction):
    await impregister(interaction)


@bot.tree.command(name="register", description="Open a new PokeImpostor lobby / Abrir sala de PokeImpostor")
async def register(interaction: discord.Interaction):
    await impregister(interaction)


@bot.tree.command(name="imp", description="Open a new PokeImpostor lobby / Abrir sala de PokeImpostor")
async def imp_slash(interaction: discord.Interaction):
    await impregister(interaction)


@bot.tree.command(name="mimi", description="Open a new PokeImpostor lobby / Abrir sala de PokeImpostor")
async def mimi_slash(interaction: discord.Interaction):
    await impregister(interaction)





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
                pista = partida.pistas_impostores.get(interaction.user.id, "")
                await interaction.user.send(embed=partida._build_dm_caos_jugador_impostor(pista))
            else:
                await interaction.user.send(embed=partida._build_dm_caos_jugador_tripulante(partida.objetivo_humano))

        elif es_ebrios:
            # Variante Danza Caos — 100% idéntico a tripulante normal
            dp = partida.pokemons_ebrios.get(interaction.user.id)
            if dp:
                emb = discord.Embed(
                    title=t("impver_crew_title", gid),
                    description=t("dm_crew_desc", gid, name=dp.get("nombre", "?"), types=" / ".join(dp.get("tipos", ["?"]))),
                    color=discord.Color.from_rgb(30, 160, 80),
                )
                if dp.get("sprite"):
                    emb.set_image(url=dp["sprite"])
                await interaction.user.send(embed=emb)

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
            if dp:
                emb = discord.Embed(
                    title=t("impver_crew_title", gid),
                    description=t("dm_crew_desc", gid, name=dp.get("nombre", "?"), types=" / ".join(dp.get("tipos", ["?"]))),
                    color=discord.Color.from_rgb(30, 160, 80),
                )
                if dp.get("sprite"):
                    emb.set_image(url=dp["sprite"])
                await interaction.user.send(embed=emb)

        await interaction.response.send_message(t("impver_sent", gid), ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message(t("impver_dm_blocked", gid), ephemeral=True)


@bot.tree.command(name="improle", description="Re-send your secret role by DM (active game) / Reenviar tu rol secreto")
async def improle(interaction: discord.Interaction):
    await impver(interaction)


@bot.tree.command(name="role", description="Re-send your secret role by DM (active game) / Reenviar tu rol secreto")
async def role_cmd(interaction: discord.Interaction):
    await impver(interaction)


@bot.tree.command(name="ver", description="Re-send your secret role by DM (active game) / Reenviar tu rol secreto")
async def ver(interaction: discord.Interaction):
    await impver(interaction)


@bot.tree.command(name="role-kyu", description="Re-send your secret role by DM / Reenviar rol secreto por DM")
async def role_kyu(interaction: discord.Interaction):
    await impver(interaction)


@bot.tree.command(name="ver-kyu", description="Re-send your secret role by DM / Reenviar rol secreto por DM")
async def ver_kyu(interaction: discord.Interaction):
    await impver(interaction)



# ═══════════════════════════════════════════════════════════════════════════════
#  /implanguage — cambiar idioma del servidor
# ═══════════════════════════════════════════════════════════════════════════════

async def _ejecutar_cambio_idioma(interaction: discord.Interaction, language: str):
    if interaction.guild_id is None or interaction.guild is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id
    if not es_anfitrion_o_admin(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            t("lang_only_admin", gid), ephemeral=True
        )
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


@bot.tree.command(name="implanguage", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def implanguage(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


@bot.tree.command(name="lang", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def lang(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


@bot.tree.command(name="impidioma", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def impidioma(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


@bot.tree.command(name="idioma", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def idioma(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


@bot.tree.command(name="lang-kyu", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def lang_kyu(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)


@bot.tree.command(name="idioma-kyu", description="Change the bot language for this server / Cambiar idioma del bot")
@app_commands.describe(language="Choose language / Elige idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="🇬🇧 English", value="en"),
    app_commands.Choice(name="🇪🇸 Español", value="es"),
])
async def idioma_kyu(interaction: discord.Interaction, language: str):
    await _ejecutar_cambio_idioma(interaction, language)




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
    embed.add_field(name=t("help_commands_name", gid), value=t("help_commands_value", gid), inline=False)
    embed.add_field(name=t("help_art_credits_name", gid), value=t("help_art_credits_value", gid), inline=False)
    embed.set_footer(text=t("help_footer", gid))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="help", description="How to play PokeImpostor / Cómo jugar")
async def help_cmd(interaction: discord.Interaction):
    await imphelp(interaction)


@bot.tree.command(name="help-kyu", description="How to play PokeImpostor / Cómo jugar")
async def help_kyu(interaction: discord.Interaction):
    await imphelp(interaction)


@bot.tree.command(name="ayuda-kyu", description="How to play PokeImpostor / Cómo jugar")
async def ayuda_kyu(interaction: discord.Interaction):
    await imphelp(interaction)


# ═══════════════════════════════════════════════════════════════════════════════
#  /impcreditos — Créditos del artista
# ═══════════════════════════════════════════════════════════════════════════════

async def _ejecutar_creditos(interaction: discord.Interaction):
    gid = interaction.guild_id
    embed = discord.Embed(
        title=t("credits_title", gid),
        description=t("credits_desc", gid),
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.set_footer(text=t("credits_footer", gid))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impcreditos", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def impcreditos(interaction: discord.Interaction):
    await _ejecutar_creditos(interaction)


@bot.tree.command(name="impcredits", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def impcredits(interaction: discord.Interaction):
    await _ejecutar_creditos(interaction)


@bot.tree.command(name="creditos", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def creditos(interaction: discord.Interaction):
    await _ejecutar_creditos(interaction)


@bot.tree.command(name="credits", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def credits_cmd(interaction: discord.Interaction):
    await _ejecutar_creditos(interaction)


@bot.tree.command(name="credits-kyu", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def credits_kyu(interaction: discord.Interaction):
    await _ejecutar_creditos(interaction)


@bot.tree.command(name="creditos-kyu", description="Artist and illustration credits / Créditos del artista de PokeImpostor")
async def creditos_kyu(interaction: discord.Interaction):
    await _ejecutar_creditos(interaction)


# ═══════════════════════════════════════════════════════════════════════════════
#  /impperfil — Estadísticas y perfil del jugador
# ═══════════════════════════════════════════════════════════════════════════════

async def _ejecutar_perfil(interaction: discord.Interaction, usuario: discord.Member | None = None):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id
    target = usuario or interaction.user
    stats = await obtener_perfil_jugador_async(gid, target.id)

    if stats is None:
        return await interaction.response.send_message(
            t("profile_no_games", gid),
            ephemeral=True,
        )

    # Color personalizado según el rol del miembro si tiene uno configurado
    embed_color = target.color if getattr(target, "color", None) and target.color.value != 0 else discord.Color.from_rgb(255, 203, 5)
    embed = discord.Embed(
        title=t("profile_title", gid, name=target.display_name),
        color=embed_color,
    )
    if getattr(target, "display_avatar", None) and target.display_avatar.url:
        embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(
        name=t("profile_general_field", gid),
        value=t("profile_general_value", gid,
                total=stats["total_partidas"],
                wins=stats["victorias"],
                losses=stats["derrotas"],
                winrate=stats["winrate_gral"]),
        inline=False,
    )
    embed.add_field(
        name=t("profile_roles_field", gid),
        value=t("profile_roles_value", gid,
                imp_wins=stats["victorias_impostor"],
                imp_games=stats["partidas_impostor"],
                imp_wr=stats["winrate_impostor"],
                crew_wins=stats["victorias_tripulante"],
                crew_games=stats["partidas_tripulante"],
                crew_wr=stats["winrate_tripulante"]),
        inline=False,
    )

    if stats["expulsado_inocente"] > 0:
        embed.add_field(
            name=t("profile_innocent_field", gid),
            value=t("profile_innocent_value", gid, count=stats["expulsado_inocente"]),
            inline=True,
        )

    if stats["pokemon_frecuente"]:
        embed.add_field(
            name=t("profile_pokemon_field", gid),
            value=t("profile_pokemon_value", gid, name=stats["pokemon_frecuente"]),
            inline=True,
        )

    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impprofile", description="View your or another trainer's profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def impprofile(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


@bot.tree.command(name="profile", description="View your or another trainer's profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def profile(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


@bot.tree.command(name="impperfil", description="View your or another trainer's profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def impperfil(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


@bot.tree.command(name="perfil", description="View your or another trainer's profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def perfil(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


@bot.tree.command(name="profile-kyu", description="View trainer profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def profile_kyu(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)


@bot.tree.command(name="perfil-kyu", description="View trainer profile / Ver perfil de entrenador")
@app_commands.describe(usuario="Trainer to inspect (optional) / Entrenador a consultar (opcional)")
async def perfil_kyu(interaction: discord.Interaction, usuario: discord.Member | None = None):
    await _ejecutar_perfil(interaction, usuario)



# ═══════════════════════════════════════════════════════════════════════════════
#  /impranking — Tabla de clasificación del servidor
# ═══════════════════════════════════════════════════════════════════════════════

async def _ejecutar_ranking(interaction: discord.Interaction, categoria: str = "general"):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id
    top = await obtener_ranking_async(gid, categoria)

    if not top:
        return await interaction.response.send_message(
            t("ranking_empty", gid),
            ephemeral=True,
        )

    title_key = (
        "ranking_title_impostores" if categoria == "impostores"
        else ("ranking_title_detectives" if categoria == "detectives" else "ranking_title_general")
    )
    embed = discord.Embed(
        title=t(title_key, gid),
        color=discord.Color.from_rgb(255, 203, 5),
    )

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for idx, row in enumerate(top):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        lines.append(
            t("ranking_entry", gid,
              medal=medal,
              name=row["user_name"],
              wins=row["victorias"],
              winrate=row["winrate"],
              total=row["total"])
        )

    embed.description = "\n".join(lines)
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
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


@bot.tree.command(name="leaderboard", description="View the server leaderboard / Ver tabla de clasificación")
@app_commands.describe(categoria="Leaderboard category / Categoría de la clasificación")
@app_commands.choices(categoria=[
    app_commands.Choice(name="🏆 General (Most Wins / Victorias)", value="general"),
    app_commands.Choice(name="🔪 Impostors (Deadliest Impostors)", value="impostores"),
    app_commands.Choice(name="🔍 Crewmates (Best Detectives)", value="detectives"),
])
async def leaderboard(interaction: discord.Interaction, categoria: str = "general"):
    await _ejecutar_ranking(interaction, categoria)


@bot.tree.command(name="impranking", description="View the server leaderboard / Ver tabla de clasificación")
@app_commands.describe(categoria="Leaderboard category / Categoría de la clasificación")
@app_commands.choices(categoria=[
    app_commands.Choice(name="🏆 General (Most Wins / Victorias)", value="general"),
    app_commands.Choice(name="🔪 Impostors (Deadliest Impostors)", value="impostores"),
    app_commands.Choice(name="🔍 Crewmates (Best Detectives)", value="detectives"),
])
async def impranking(interaction: discord.Interaction, categoria: str = "general"):
    await _ejecutar_ranking(interaction, categoria)


@bot.tree.command(name="ranking", description="View the server leaderboard / Ver tabla de clasificación")
@app_commands.describe(categoria="Leaderboard category / Categoría de la clasificación")
@app_commands.choices(categoria=[
    app_commands.Choice(name="🏆 General (Most Wins / Victorias)", value="general"),
    app_commands.Choice(name="🔪 Impostors (Deadliest Impostors)", value="impostores"),
    app_commands.Choice(name="🔍 Crewmates (Best Detectives)", value="detectives"),
])
async def ranking(interaction: discord.Interaction, categoria: str = "general"):
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


@bot.tree.command(name="ranking-kyu", description="View the server leaderboard / Ver tabla de clasificación")
@app_commands.describe(categoria="Leaderboard category / Categoría de la clasificación")
@app_commands.choices(categoria=[
    app_commands.Choice(name="🏆 General (Most Wins / Victorias)", value="general"),
    app_commands.Choice(name="🔪 Impostors (Deadliest Impostors)", value="impostores"),
    app_commands.Choice(name="🔍 Crewmates (Best Detectives)", value="detectives"),
])
async def ranking_kyu(interaction: discord.Interaction, categoria: str = "general"):
    await _ejecutar_ranking(interaction, categoria)


# ═══════════════════════════════════════════════════════════════════════════════
#  /impstats — Analítica global del servidor
# ═══════════════════════════════════════════════════════════════════════════════

async def _ejecutar_stats(interaction: discord.Interaction):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )

    gid = interaction.guild_id
    stats = await obtener_stats_servidor_async(gid)

    if stats is None:
        return await interaction.response.send_message(
            t("server_stats_empty", gid),
            ephemeral=True,
        )

    embed = discord.Embed(
        title=t("server_stats_title", gid),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name=t("server_stats_balance_field", gid),
        value=t("server_stats_balance_value", gid,
                total=stats["total_partidas"],
                imp_wins=stats["vic_impostores"],
                imp_pct=stats["pct_impostores"],
                crew_wins=stats["vic_tripulantes"],
                crew_pct=stats["pct_tripulantes"],
                no_imp=stats["sin_impostor"]),
        inline=False,
    )
    embed.add_field(
        name=t("server_stats_fav_mode", gid),
        value=f"**{stats['modo_favorito'].capitalize()}**",
        inline=True,
    )
    embed.add_field(
        name=t("server_stats_deadliest_pk", gid),
        value=f"**{stats['pokemon_letal']}**",
        inline=True,
    )
    embed.add_field(
        name=t("server_stats_common_pk", gid),
        value=f"**{stats['pokemon_comun']}**",
        inline=True,
    )

    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impstats", description="Global game statistics on this server / Estadísticas de partidas en este servidor")
async def impstats(interaction: discord.Interaction):
    await _ejecutar_stats(interaction)


@bot.tree.command(name="stats_partidas", description="Global game statistics on this server / Estadísticas de partidas en este servidor")
async def stats_partidas(interaction: discord.Interaction):
    await _ejecutar_stats(interaction)


@bot.tree.command(name="stats", description="Global game statistics on this server / Estadísticas de partidas en este servidor")
async def stats(interaction: discord.Interaction):
    await _ejecutar_stats(interaction)


@bot.tree.command(name="stats-kyu", description="Global game statistics on this server / Estadísticas de partidas en este servidor")
async def stats_kyu(interaction: discord.Interaction):
    await _ejecutar_stats(interaction)



# ═══════════════════════════════════════════════════════════════════════════════
#  SISTEMA DE LICENCIAS, MONETIZACIÓN Y CLAVES VIP
# ═══════════════════════════════════════════════════════════════════════════════

class ModalGenerarKey(discord.ui.Modal):
    def __init__(self, gid: int):
        super().__init__(title=t("license_key_modal_title", gid))
        self.gid = gid

        self.password_input = discord.ui.TextInput(
            label=t("license_key_modal_pwd", gid),
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
        # Validación con digest criptográfico seguro (timing-attack resistant)
        if not verificar_master_password(self.password_input.value.strip()):
            return await interaction.response.send_message(
                t("license_auth_failed", self.gid),
                ephemeral=True
            )

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
            return await interaction.response.send_message(
                "❌ Error al registrar la clave en la base de datos.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=t("license_key_gen_title", self.gid),
            description=t("license_key_generated", self.gid, key=nueva_key, tipo=tipo.upper(), details=detalle),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def _ejecutar_generarkey(interaction: discord.Interaction):
    # Verificación exclusiva de servidor central autorizado
    if interaction.guild_id != SERVER_ADMIN_CENTRAL_ID:
        return await interaction.response.send_message(
            f"⛔ Este comando solo puede ser ejecutado en el servidor central autorizado (ID: {SERVER_ADMIN_CENTRAL_ID}).",
            ephemeral=True
        )
    # Verificación estricta de propietario del bot / app owner
    es_dueno = await bot.is_owner(interaction.user) or (
        os.getenv("OWNER_ID") and str(interaction.user.id) == os.getenv("OWNER_ID").strip()
    )
    if not es_dueno:
        return await interaction.response.send_message(
            "⛔ Access Denied: This command is restricted to the bot owner.",
            ephemeral=True
        )
    gid = interaction.guild_id or 0
    modal = ModalGenerarKey(gid)
    await interaction.response.send_modal(modal)


@bot.tree.command(name="impgenkey", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def impgenkey(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


@bot.tree.command(name="genkey", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def genkey(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


@bot.tree.command(name="impgenerarkey", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def impgenerarkey(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


@bot.tree.command(name="generarkey", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def generarkey(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


@bot.tree.command(name="genkey-kyu", description="Owner only: Generate VIP License Keys / Generar claves VIP")
async def genkey_kyu(interaction: discord.Interaction):
    await _ejecutar_generarkey(interaction)


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

    res = await canjear_licencia_async(clave, gid, interaction.user.id)
    if not res["exito"]:
        err = res.get("error")
        if err == "already_used":
            return await interaction.response.send_message(t("redeem_already_used", gid), ephemeral=True)
        return await interaction.response.send_message(t("redeem_not_found", gid), ephemeral=True)

    tipo = res["tipo"]
    if tipo == "permanente":
        det = "Pase Vitalicio ($5 USD) Permanente de por vida"
    elif tipo == "dias":
        exp = res["expira_en"].strftime("%d/%m/%Y") if res.get("expira_en") else "?"
        dias = res.get("duracion_dias", 30)
        det = f"{dias} días (hasta {exp})"
    else:
        det = f"{res['cargas_totales']} partidas VIP disponibles (Top.gg / Cargas)"

    embed = discord.Embed(
        title=t("redeem_success_title", gid),
        description=t("redeem_success_desc", gid, tipo=tipo.upper(), details=det),
        color=discord.Color.green(),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impredeem", description="Redeem a VIP License Key for this server / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def impredeem(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


@bot.tree.command(name="redeem", description="Redeem a VIP License Key for this server / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def redeem(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


@bot.tree.command(name="impcanjear", description="Redeem a VIP License Key for this server / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def impcanjear(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


@bot.tree.command(name="canjear", description="Redeem a VIP License Key for this server / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def canjear(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


@bot.tree.command(name="redeem-kyu", description="Redeem a VIP License Key / Canjear clave de licencia VIP")
@app_commands.describe(clave="VIP Key code (e.g. POKE-VIP-XXXX-YYYY)")
async def redeem_kyu(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


@bot.tree.command(name="canjear-kyu", description="Canjear clave de licencia VIP")
@app_commands.describe(clave="Código de clave VIP (ej. POKE-VIP-XXXX-YYYY)")
async def canjear_kyu(interaction: discord.Interaction, clave: str):
    await _ejecutar_canjear(interaction, clave)


async def _ejecutar_licencia(interaction: discord.Interaction):
    if interaction.guild_id is None:
        return await interaction.response.send_message(
            "❌ This command only works inside a server. / Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
    gid = interaction.guild_id
    estado = await verificar_estado_premium_async(gid)

    if estado["es_premium"]:
        embed = discord.Embed(
            title=t("license_status_title", gid),
            description=t("license_status_premium", gid, tipo=estado["tipo"].upper(), details=estado["detalle"]),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await interaction.response.send_message(embed=embed)
    else:
        client_id = bot.user.id if bot.user else 1195913386899296347
        vote_url = f"https://top.gg/bot/{client_id}/vote"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=vote_url, style=discord.ButtonStyle.link))
        view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
        embed = discord.Embed(
            title=t("license_status_title", gid),
            description=t("license_status_free", gid),
            color=discord.Color.light_grey(),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="implicense", description="Check this server's license and VIP tier / Consultar estado de licencia")
async def implicense(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


@bot.tree.command(name="license", description="Check this server's license and VIP tier / Consultar estado de licencia")
async def license(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


@bot.tree.command(name="implicencia", description="Check this server's license and VIP tier / Consultar estado de licencia")
async def implicencia(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


@bot.tree.command(name="licencia", description="Check this server's license and VIP tier / Consultar estado de licencia")
async def licencia(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


@bot.tree.command(name="license-kyu", description="Check this server's license / Consultar estado de licencia")
async def license_kyu(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


@bot.tree.command(name="licencia-kyu", description="Consultar estado de licencia del servidor")
async def licencia_kyu(interaction: discord.Interaction):
    await _ejecutar_licencia(interaction)


async def _ejecutar_voto(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    client_id = bot.user.id if bot.user else 1195913386899296347
    vote_url = f"https://top.gg/bot/{client_id}/vote?guild={gid}" if gid else f"https://top.gg/bot/{client_id}/vote"
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=vote_url, style=discord.ButtonStyle.link))
    view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
    embed = discord.Embed(
        title=t("vote_embed_title", gid),
        description=t("vote_embed_desc", gid),
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="vote-kyu", description="Vote on Top.gg for 10 free premium matches / Votar en Top.gg")
async def vote_kyu(interaction: discord.Interaction):
    await _ejecutar_voto(interaction)


@bot.tree.command(name="votar-kyu", description="Vota en Top.gg para recibir 10 partidas premium gratis")
async def votar_kyu(interaction: discord.Interaction):
    await _ejecutar_voto(interaction)


@bot.tree.command(name="vote", description="Vote on Top.gg for 10 free premium matches / Votar en Top.gg")
async def vote(interaction: discord.Interaction):
    await _ejecutar_voto(interaction)


@bot.tree.command(name="votar", description="Vota en Top.gg para recibir 10 partidas premium gratis")
async def votar(interaction: discord.Interaction):
    await _ejecutar_voto(interaction)


async def _ejecutar_donar(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
    embed = discord.Embed(
        title=t("donate_embed_title", gid),
        description=t("donate_embed_desc", gid),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="donate-kyu", description="Support the bot & get Lifetime VIP ($5 USD) / Donar")
async def donate_kyu(interaction: discord.Interaction):
    await _ejecutar_donar(interaction)


@bot.tree.command(name="donar-kyu", description="Apoya al bot y obtén el Pase Vitalicio ($5 USD)")
async def donar_kyu(interaction: discord.Interaction):
    await _ejecutar_donar(interaction)


@bot.tree.command(name="donate", description="Support the bot & get Lifetime VIP ($5 USD) / Donar")
async def donate(interaction: discord.Interaction):
    await _ejecutar_donar(interaction)


@bot.tree.command(name="donar", description="Apoya al bot y obtén el Pase Vitalicio ($5 USD)")
async def donar(interaction: discord.Interaction):
    await _ejecutar_donar(interaction)


async def _ejecutar_invitar(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    client_id = bot.user.id if bot.user else 1195913386899296347
    invite_url = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions={INVITE_PERMS_INT}&scope=bot%20applications.commands"
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=t("invite_btn_label", gid), url=invite_url, style=discord.ButtonStyle.link))
    embed = discord.Embed(
        title=t("invite_embed_title", gid),
        description=t("invite_embed_desc", gid),
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="invite-kyu", description="Invite Mimikyu to another server / Invitar a Mimikyu")
async def invite_kyu(interaction: discord.Interaction):
    await _ejecutar_invitar(interaction)


@bot.tree.command(name="invitar-kyu", description="Invita a Mimikyu a tu servidor")
async def invitar_kyu(interaction: discord.Interaction):
    await _ejecutar_invitar(interaction)


@bot.tree.command(name="invite", description="Invite Mimikyu to another server / Invitar a Mimikyu")
async def invite(interaction: discord.Interaction):
    await _ejecutar_invitar(interaction)


@bot.tree.command(name="invitar", description="Invita a Mimikyu a tu servidor")
async def invitar(interaction: discord.Interaction):
    await _ejecutar_invitar(interaction)



# ═══════════════════════════════════════════════════════════════════════════════
#  /impsetrole — Configurar o crear rol de anfitrión PokeImpostor
# ═══════════════════════════════════════════════════════════════════════════════

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

    # Solo administradores o el dueño del servidor pueden configurar el rol
    es_admin = (
        getattr(interaction.user, "guild_permissions", None)
        and interaction.user.guild_permissions.administrator
    ) or (interaction.user == interaction.guild.owner)

    if not es_admin:
        return await interaction.response.send_message(
            t("setrole_admin_only", gid),
            ephemeral=True,
        )

    target_role: discord.Role | None = role
    creado = False

    if target_role is None:
        # Buscar si ya existe el rol PokeHost
        target_role = discord.utils.get(interaction.guild.roles, name=NOMBRE_ROL_HOST)
        if target_role is None:
            # Crear el rol con color insignia de Pokémon
            try:
                target_role = await interaction.guild.create_role(
                    name=NOMBRE_ROL_HOST,
                    color=discord.Color.from_rgb(255, 203, 5),
                    mentionable=True,
                    reason="PokeImpostor official host role",
                )
                creado = True
            except discord.Forbidden:
                return await interaction.response.send_message(
                    t("setrole_missing_perms", gid),
                    ephemeral=True,
                )
            except Exception as e:
                return await interaction.response.send_message(
                    f"❌ Error creating role: {e}",
                    ephemeral=True,
                )

    # Persistir rol host en DuckDB
    await set_guild_rol_host_async(gid, target_role.id)

    # Mensaje base
    if creado:
        msg = t("setrole_success_created", gid, role=target_role.mention)
    else:
        msg = t("setrole_success_existing", gid, role=target_role.mention)

    # Asignar a usuario si se especificó, o por defecto al autor si no lo tiene
    usuario_asignar = assign_to
    if usuario_asignar is None:
        if isinstance(interaction.user, discord.Member) and target_role not in interaction.user.roles:
            usuario_asignar = interaction.user

    if usuario_asignar is not None:
        try:
            await usuario_asignar.add_roles(target_role, reason="PokeImpostor host role assignment")
            msg += "\n" + t("setrole_assigned_user", gid, role=target_role.name, user=usuario_asignar.mention)
        except discord.Forbidden:
            msg += "\n" + t("setrole_hierarchy_error", gid, role=target_role.name, user=usuario_asignar.mention)
        except Exception as e:
            msg += f"\n⚠️ Warning: could not assign role to {usuario_asignar.mention}: {e}"

    embed = discord.Embed(
        title=t("setrole_embed_title", gid),
        description=msg,
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="impsetrole", description="Set or create the PokeImpostor host role / Configurar o crear rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def impsetrole(
    interaction: discord.Interaction,
    role: discord.Role | None = None,
    assign_to: discord.Member | None = None,
):
    await _ejecutar_setrole(interaction, role, assign_to)


@bot.tree.command(name="setrole", description="Set or create the PokeImpostor host role / Configurar o crear rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def setrole(
    interaction: discord.Interaction,
    role: discord.Role | None = None,
    assign_to: discord.Member | None = None,
):
    await _ejecutar_setrole(interaction, role, assign_to)


@bot.tree.command(name="imphostrole", description="Set or create the PokeImpostor host role / Configurar o crear rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def imphostrole(
    interaction: discord.Interaction,
    role: discord.Role | None = None,
    assign_to: discord.Member | None = None,
):
    await _ejecutar_setrole(interaction, role, assign_to)


@bot.tree.command(name="hostrole", description="Set or create the PokeImpostor host role / Configurar o crear rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def hostrole(
    interaction: discord.Interaction,
    role: discord.Role | None = None,
    assign_to: discord.Member | None = None,
):
    await _ejecutar_setrole(interaction, role, assign_to)


@bot.tree.command(name="setrole-kyu", description="Set or create the PokeImpostor host role / Configurar rol de anfitrión")
@app_commands.describe(
    role="Role to designate as PokeHost (leave empty to auto-create @PokeHost)",
    assign_to="Trainer to grant the host role to (optional)",
)
async def setrole_kyu(
    interaction: discord.Interaction,
    role: discord.Role | None = None,
    assign_to: discord.Member | None = None,
):
    await _ejecutar_setrole(interaction, role, assign_to)



async def _ejecutar_partner_add(interaction: discord.Interaction, servidor_id: str, motivo: str = "Beta Tester Fundador"):
    # Verificación exclusiva de servidor central autorizado
    if interaction.guild_id != SERVER_ADMIN_CENTRAL_ID:
        return await interaction.response.send_message(
            f"⛔ Este comando solo puede ser ejecutado en el servidor central autorizado (ID: {SERVER_ADMIN_CENTRAL_ID}).",
            ephemeral=True
        )
    # Verificación estricta de propietario del bot / app owner
    es_dueno = await bot.is_owner(interaction.user) or (
        os.getenv("OWNER_ID") and str(interaction.user.id) == os.getenv("OWNER_ID").strip()
    )
    if not es_dueno:
        return await interaction.response.send_message(
            "⛔ Access Denied: This command is restricted to the bot owner.",
            ephemeral=True
        )
    gid = interaction.guild_id or 0

    class ModalPartnerAuth(discord.ui.Modal):
        def __init__(self):
            super().__init__(title="🔐 Confirmar Partner con Contraseña")
            self.pwd = discord.ui.TextInput(
                label="Contraseña Maestra",
                placeholder="••••••••••••",
                style=discord.TextStyle.short,
                required=True,
            )
            self.add_item(self.pwd)

        async def on_submit(self, modal_inter: discord.Interaction):
            if not verificar_master_password(self.pwd.value.strip()):
                return await modal_inter.response.send_message(
                    t("license_auth_failed", gid),
                    ephemeral=True
                )
            try:
                target_gid = int(servidor_id.strip())
            except ValueError:
                return await modal_inter.response.send_message("❌ ID de servidor inválido.", ephemeral=True)

            ok = await registrar_servidor_partner_async(target_gid, motivo)
            if ok:
                await modal_inter.response.send_message(
                    t("partner_register_success", gid, guild_id=servidor_id),
                    ephemeral=True
                )
            else:
                await modal_inter.response.send_message("❌ Error al registrar partner.", ephemeral=True)

    await interaction.response.send_modal(ModalPartnerAuth())


@bot.tree.command(name="imppartner_add", description="Owner only: Grant permanent Beta Partner status to a server")
@app_commands.describe(servidor_id="Guild ID / ID del servidor", motivo="Partner description / Motivo")
async def imppartner_add(interaction: discord.Interaction, servidor_id: str, motivo: str = "Beta Tester Fundador"):
    await _ejecutar_partner_add(interaction, servidor_id, motivo)


@bot.tree.command(name="partner_add", description="Owner only: Grant permanent Beta Partner status to a server")
@app_commands.describe(servidor_id="Guild ID / ID del servidor", motivo="Partner description / Motivo")
async def partner_add(interaction: discord.Interaction, servidor_id: str, motivo: str = "Beta Tester Fundador"):
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
    Soporta:
      - Sufijo: 'register -imp', 'perfil -imp', 'canjear ABCD -imp'
      - Prefijo: '-imp register', '!imp register'
    Retorna: (es_comando_valido, nombre_comando, argumentos)
    """
    s = texto.strip()
    if not s:
        return False, "", []

    cmd_str = None
    low = s.lower()

    # Sufijos (-mimi, mimi, -imp)
    if low.endswith(" -mimi"):
        cmd_str = s[:-6].strip()
    elif low.endswith("-mimi"):
        cmd_str = s[:-5].strip()
    elif low.endswith(" mimi"):
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

    # 1. play / jugar / register / impregister / sala
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
        msg_lobby = await message.channel.send(
            embed=_build_embed_lobby(nueva),
            view=view,
        )
        view.message = msg_lobby
        return

    # 2. ver / impver
    elif cmd in ("ver", "rol", "role", "myrole"):
        partida = partidas_activas.get(message.channel.id)
        if partida is None or (partida.datos_pokemon is None and not partida.pokemons_ebrios and partida.objetivo_humano is None):
            await message.reply(t("impver_no_game", gid), mention_author=False)
            return

        if message.author not in partida.jugadores_iniciales:
            await message.reply(t("impver_not_player", gid), mention_author=False)
            return

        try:
            es_impostor = message.author in partida.impostores_iniciales
            es_ebrios = bool(partida.pokemons_ebrios)
            es_cj = partida.objetivo_humano is not None

            if es_cj:
                if es_impostor:
                    pista = partida.pistas_impostores.get(message.author.id, "")
                    await message.author.send(embed=partida._build_dm_caos_jugador_impostor(pista))
                else:
                    await message.author.send(embed=partida._build_dm_caos_jugador_tripulante(partida.objetivo_humano))

            elif es_ebrios:
                # Variante Danza Caos — 100% idéntico a tripulante normal
                dp = partida.pokemons_ebrios.get(message.author.id)
                if dp:
                    emb = discord.Embed(
                        title=t("impver_crew_title", gid),
                        description=t("dm_crew_desc", gid, name=dp.get("nombre", "?"), types=" / ".join(dp.get("tipos", ["?"]))),
                        color=discord.Color.from_rgb(30, 160, 80),
                    )
                    if dp.get("sprite"):
                        emb.set_image(url=dp["sprite"])
                    await message.author.send(embed=emb)

            elif es_impostor:
                pista = partida.pistas_impostores.get(message.author.id, partida.pista_generada)
                await message.author.send(embed=discord.Embed(
                    title=t("impver_impostor_title", gid),
                    description=t("dm_impostor_desc", gid, hint=pista),
                    color=discord.Color.from_rgb(180, 30, 30),
                ))
            else:
                dp = partida.datos_pokemon
                if dp:
                    emb = discord.Embed(
                        title=t("impver_crew_title", gid),
                        description=t("dm_crew_desc", gid, name=dp.get("nombre", "?"), types=" / ".join(dp.get("tipos", ["?"]))),
                        color=discord.Color.from_rgb(30, 160, 80),
                    )
                    if dp.get("sprite"):
                        emb.set_image(url=dp["sprite"])
                    await message.author.send(embed=emb)

            try:
                await message.add_reaction("📬")
            except Exception:
                await message.reply(t("impver_sent", gid), delete_after=10, mention_author=False)

        except discord.Forbidden:
            await message.reply(t("impver_dm_blocked", gid), mention_author=False)
        return

    # 3. perfil / impperfil
    elif cmd in ("perfil", "profile"):
        target = message.mentions[0] if message.mentions else message.author
        stats = await obtener_perfil_jugador_async(gid, target.id)
        if stats is None:
            await message.reply(t("profile_no_games", gid), mention_author=False)
            return

        embed_color = target.color if getattr(target, "color", None) and target.color.value != 0 else discord.Color.from_rgb(255, 203, 5)
        embed = discord.Embed(
            title=t("profile_title", gid, name=target.display_name),
            color=embed_color,
        )
        if getattr(target, "display_avatar", None) and target.display_avatar.url:
            embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(
            name=t("profile_general_field", gid),
            value=t("profile_general_value", gid,
                    total=stats["total_partidas"],
                    wins=stats["victorias"],
                    losses=stats["derrotas"],
                    winrate=stats["winrate_gral"]),
            inline=False,
        )
        embed.add_field(
            name=t("profile_roles_field", gid),
            value=t("profile_roles_value", gid,
                    imp_wins=stats["victorias_impostor"],
                    imp_games=stats["partidas_impostor"],
                    imp_wr=stats["winrate_impostor"],
                    crew_wins=stats["victorias_tripulante"],
                    crew_games=stats["partidas_tripulante"],
                    crew_wr=stats["winrate_tripulante"]),
            inline=False,
        )
        if stats["expulsado_inocente"] > 0:
            embed.add_field(
                name=t("profile_innocent_field", gid),
                value=t("profile_innocent_value", gid, count=stats["expulsado_inocente"]),
                inline=True,
            )
        if stats["pokemon_frecuente"]:
            embed.add_field(
                name=t("profile_pokemon_field", gid),
                value=t("profile_pokemon_value", gid, name=stats["pokemon_frecuente"]),
                inline=True,
            )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, mention_author=False)
        return

    # 4. ranking / impranking
    elif cmd in ("ranking", "leaderboard", "top"):
        cat = "general"
        if args:
            arg_low = args[0].lower()
            if "imp" in arg_low:
                cat = "impostores"
            elif "trip" in arg_low or "det" in arg_low or "crew" in arg_low:
                cat = "detectives"

        top = await obtener_ranking_async(gid, cat)
        if not top:
            await message.reply(t("ranking_empty", gid), mention_author=False)
            return

        title_key = (
            "ranking_title_impostores" if cat == "impostores"
            else ("ranking_title_detectives" if cat == "detectives" else "ranking_title_general")
        )
        embed = discord.Embed(
            title=t(title_key, gid),
            color=discord.Color.from_rgb(255, 203, 5),
        )
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = []
        for idx, row in enumerate(top):
            medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
            lines.append(
                t("ranking_entry", gid,
                  medal=medal,
                  name=row["user_name"],
                  wins=row["victorias"],
                  winrate=row["winrate"],
                  total=row["total"])
            )
        embed.description = "\n".join(lines)
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, mention_author=False)
        return

    # 5. stats / impstats
    elif cmd in ("stats", "stats_partidas", "serverstats", "partidas"):
        stats = await obtener_stats_servidor_async(gid)
        if stats is None:
            await message.reply(t("server_stats_empty", gid), mention_author=False)
            return

        embed = discord.Embed(
            title=t("server_stats_title", gid),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=t("server_stats_balance_field", gid),
            value=t("server_stats_balance_value", gid,
                    total=stats["total_partidas"],
                    imp_wins=stats["vic_impostores"],
                    imp_pct=stats["pct_impostores"],
                    crew_wins=stats["vic_tripulantes"],
                    crew_pct=stats["pct_tripulantes"],
                    no_imp=stats["sin_impostor"]),
            inline=False,
        )
        embed.add_field(
            name=t("server_stats_fav_mode", gid),
            value=f"**{stats['modo_favorito'].capitalize()}**",
            inline=True,
        )
        embed.add_field(
            name=t("server_stats_deadliest_pk", gid),
            value=f"**{stats['pokemon_letal']}**",
            inline=True,
        )
        embed.add_field(
            name=t("server_stats_common_pk", gid),
            value=f"**{stats['pokemon_comun']}**",
            inline=True,
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, mention_author=False)
        return

    # 6. licencia / implicencia
    elif cmd in ("licencia", "license", "vip", "tier"):
        estado = await verificar_estado_premium_async(gid)
        if estado["es_premium"]:
            embed = discord.Embed(
                title=t("license_status_title", gid),
                description=t("license_status_premium", gid, tipo=estado["tipo"].upper(), details=estado["detalle"]),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
            await message.reply(embed=embed, mention_author=False)
        else:
            client_id = bot.user.id if bot.user else 1195913386899296347
            vote_url = f"https://top.gg/bot/{client_id}/vote"
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=vote_url, style=discord.ButtonStyle.link))
            view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
            embed = discord.Embed(
                title=t("license_status_title", gid),
                description=t("license_status_free", gid),
                color=discord.Color.light_grey(),
            )
            embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
            await message.reply(embed=embed, view=view, mention_author=False)
        return

    # 7. canjear / impcanjear
    elif cmd in ("canjear", "redeem"):
        if not es_anfitrion_o_admin(message.author, message.guild):
            await message.reply(t("redeem_only_host", gid, role=obtener_nombre_rol_host(message.guild)), mention_author=False)
            return

        if not args:
            await message.reply("⚠️ Usage: `mimi redeem <KEY>` (or `redeem <KEY> -mimi`) / Uso: `mimi canjear <CLAVE>` (o `canjear <CLAVE> -mimi`)", mention_author=False)
            return

        clave = args[0].strip()
        res = await canjear_licencia_async(clave, gid, message.author.id)
        if not res["exito"]:
            err = res.get("error")
            if err == "already_used":
                await message.reply(t("redeem_already_used", gid), mention_author=False)
            else:
                await message.reply(t("redeem_not_found", gid), mention_author=False)
            return

        tipo = res["tipo"]
        if tipo == "permanente":
            det = "Pase Vitalicio ($5 USD) Permanente de por vida"
        elif tipo == "dias":
            exp = res["expira_en"].strftime("%d/%m/%Y") if res.get("expira_en") else "?"
            dias = res.get("duracion_dias", 30)
            det = f"{dias} días (hasta {exp})"
        else:
            det = f"{res['cargas_totales']} partidas VIP disponibles (Top.gg / Cargas)"

        embed = discord.Embed(
            title=t("redeem_success_title", gid),
            description=t("redeem_success_desc", gid, tipo=tipo.upper(), details=det),
            color=discord.Color.green(),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, mention_author=False)
        return

    # 8. lang / implang / implanguage / idioma / impidioma
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

    # 9. generarkey / impgenerarkey / genkey
    elif cmd in ("generarkey", "genkey", "impgenkey"):
        await message.reply(
            "🔐 For Discord security and password entry, please use the slash command: `/impgenkey`",
            mention_author=False
        )
        return

    # 10. help / imphelp / ayuda
    elif cmd in ("help", "ayuda", "guia", "guide"):
        embed = discord.Embed(
            title=t("help_title", gid),
            description=t("help_desc", gid),
            color=discord.Color.from_rgb(255, 203, 5),
        )
        embed.add_field(name=t("help_step1_name", gid), value=t("help_step1_value", gid), inline=False)
        embed.add_field(name=t("help_step2_name", gid), value=t("help_step2_value", gid), inline=False)
        embed.add_field(name=t("help_step3_name", gid), value=t("help_step3_value", gid), inline=False)
        embed.add_field(name=t("help_step4_name", gid), value=t("help_step4_value", gid), inline=False)
        embed.add_field(name=t("help_modes_name", gid), value=t("help_modes_value", gid), inline=False)
        embed.add_field(name=t("help_commands_name", gid), value=t("help_commands_value", gid), inline=False)
        embed.add_field(name=t("help_art_credits_name", gid), value=t("help_art_credits_value", gid), inline=False)
        embed.set_footer(text=t("help_footer", gid))
        await message.reply(embed=embed, mention_author=False)
        return

    # 11. creditos / credits / arte / art
    elif cmd in ("creditos", "credito", "credits", "credit", "arte", "art", "artista", "artist"):
        embed = discord.Embed(
            title=t("credits_title", gid),
            description=t("credits_desc", gid),
            color=discord.Color.from_rgb(255, 105, 180),
        )
        embed.set_footer(text=t("credits_footer", gid))
        await message.reply(embed=embed, mention_author=False)
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
        creado = False

        if target_role is None and args:
            for a in args:
                if a.isdigit():
                    r = message.guild.get_role(int(a))
                    if r:
                        target_role = r
                        break
                r = discord.utils.get(message.guild.roles, name=a)
                if r:
                    target_role = r
                    break

        if target_role is None:
            target_role = discord.utils.get(message.guild.roles, name=NOMBRE_ROL_HOST)
            if target_role is None:
                try:
                    target_role = await message.guild.create_role(
                        name=NOMBRE_ROL_HOST,
                        color=discord.Color.from_rgb(255, 203, 5),
                        mentionable=True,
                        reason="PokeImpostor official host role",
                    )
                    creado = True
                except discord.Forbidden:
                    await message.reply(t("setrole_missing_perms", gid), mention_author=False)
                    return
                except Exception as e:
                    await message.reply(f"❌ Error creating role: {e}", mention_author=False)
                    return

        await set_guild_rol_host_async(gid, target_role.id)

        if creado:
            msg = t("setrole_success_created", gid, role=target_role.mention)
        else:
            msg = t("setrole_success_existing", gid, role=target_role.mention)

        usuario_asignar = target_user
        if usuario_asignar is None:
            if isinstance(message.author, discord.Member) and target_role not in message.author.roles:
                usuario_asignar = message.author

        if usuario_asignar is not None:
            try:
                await usuario_asignar.add_roles(target_role, reason="PokeImpostor host role assignment")
                msg += "\n" + t("setrole_assigned_user", gid, role=target_role.name, user=usuario_asignar.mention)
            except discord.Forbidden:
                msg += "\n" + t("setrole_hierarchy_error", gid, role=target_role.name, user=usuario_asignar.mention)
            except Exception as e:
                msg += f"\n⚠️ Warning: could not assign role to {usuario_asignar.mention}: {e}"

        embed = discord.Embed(
            title=t("setrole_embed_title", gid),
            description=msg,
            color=discord.Color.from_rgb(255, 203, 5),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, mention_author=False)
        return

    # 13. vote / votar / voto
    elif cmd in ("vote", "votar", "voto"):
        client_id = bot.user.id if bot.user else 1195913386899296347
        vote_url = f"https://top.gg/bot/{client_id}/vote?guild={gid}"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=vote_url, style=discord.ButtonStyle.link))
        view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
        embed = discord.Embed(
            title=t("vote_embed_title", gid),
            description=t("vote_embed_desc", gid),
            color=discord.Color.from_rgb(255, 105, 180),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, view=view, mention_author=False)
        return

    # 14. donar / donate / kofi / buymeacoffee / coffee
    elif cmd in ("donar", "donate", "dona", "donation", "kofi", "buymeacoffee", "coffee"):
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
        embed = discord.Embed(
            title=t("donate_embed_title", gid),
            description=t("donate_embed_desc", gid),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, view=view, mention_author=False)
        return

    # 15. invite / invitar
    elif cmd in ("invite", "invitar", "invitacion", "invitacion"):
        client_id = bot.user.id if bot.user else 1195913386899296347
        invite_url = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions={INVITE_PERMS_INT}&scope=bot%20applications.commands"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=t("invite_btn_label", gid), url=invite_url, style=discord.ButtonStyle.link))
        embed = discord.Embed(
            title=t("invite_embed_title", gid),
            description=t("invite_embed_desc", gid),
            color=discord.Color.from_rgb(255, 203, 5),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        await message.reply(embed=embed, view=view, mention_author=False)
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
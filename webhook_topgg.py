"""
webhook_topgg.py — Servidor HTTP aiohttp para recibir webhooks de votos de Top.gg
Acredita 10 partidas VIP automáticas y anuncia el voto en el servidor correspondiente.
"""
from __future__ import annotations

import os
import urllib.parse
import aiohttp
import aiohttp.web
import discord
from discord.ext import commands

from db import obtener_guild_mas_activa_usuario_async, sumar_partidas_voto_async
from i18n import t

_webhook_runner: aiohttp.web.AppRunner | None = None


async def handle_topgg_webhook(request: aiohttp.web.Request, bot: commands.Bot) -> aiohttp.web.Response:
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
            guild_id = await obtener_guild_mas_activa_usuario_async(user_id)
        except Exception as e:
            print(f"[Top.gg Webhook] Error consultando servidor más activo: {e}")

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


async def iniciar_webhook_topgg(bot: commands.Bot):
    global _webhook_runner
    port = int(os.getenv("TOPGG_WEBHOOK_PORT", "5000"))
    app = aiohttp.web.Application()

    async def _handler(request: aiohttp.web.Request):
        return await handle_topgg_webhook(request, bot)

    app.router.add_post("/topgg-webhook", _handler)
    app.router.add_post("/dblwebhook", _handler)
    app.router.add_get("/", lambda req: aiohttp.web.Response(text="PokeImpostor Top.gg Webhook Active ⚡"))
    _webhook_runner = aiohttp.web.AppRunner(app)
    await _webhook_runner.setup()
    site = aiohttp.web.TCPSite(_webhook_runner, "0.0.0.0", port)
    try:
        await site.start()
        print(f"🗳️ [Top.gg Webhook] Servidor escuchando en http://0.0.0.0:{port}/topgg-webhook")
    except Exception as e:
        print(f"⚠️ [Top.gg Webhook] No se pudo iniciar en el puerto {port}: {e}")


async def detener_webhook_topgg():
    global _webhook_runner
    if _webhook_runner:
        try:
            await _webhook_runner.cleanup()
            print("🔌 Top.gg Webhook runner stopped.")
        except Exception as e:
            print(f"Error deteniendo webhook runner: {e}")

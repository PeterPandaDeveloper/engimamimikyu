"""
vistas/common.py — Constantes y helpers compartidos por todos los paneles de UI.
"""
from __future__ import annotations

from typing import Any
import discord
from motor_juego import Partida, ModoJuego, CaosVariante, Ventaja
from i18n import t

# Timeouts de las vistas (en segundos). El debate y la votación no tienen
# límite de tiempo real para el juego — estos valores solo evitan que
# Discord acumule listeners de mensajes abandonados para siempre.
TIMEOUT_LOBBY    = 3600   # 1 hora
TIMEOUT_VOTACION = 3600   # 1 hora
TIMEOUT_DEBATE   = 21600  # 6 horas — el debate puede tardar lo que el grupo quiera

VOTO_NULO_ID = "voto_nulo"
NOMBRE_ROL_HOST = "PokeHost"


def es_anfitrion_o_admin(user: Any, guild: discord.Guild | None = None) -> bool:
    """
    Retorna True si el usuario tiene permisos de Administrador
    o posee el rol PokeHost.
    """
    perms = getattr(user, "guild_permissions", None)
    if perms and getattr(perms, "administrator", False):
        return True
    roles = getattr(user, "roles", [])
    return any(getattr(r, "name", "") == NOMBRE_ROL_HOST for r in roles)


def gid(partida: Partida) -> int:
    """ID del servidor (guild) para resolver el idioma."""
    return partida.canal.guild.id


def build_embed_lobby(partida: Partida) -> discord.Embed:
    g = gid(partida)
    lista = (
        "\n".join(f"• {j.display_name}" for j in partida.jugadores)
        if partida.jugadores else t("lobby_nobody", g)
    )
    embed = discord.Embed(
        title=t("lobby_title", g),
        description=t("lobby_desc", g),
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.add_field(
        name=t("lobby_players_field", g, count=len(partida.jugadores)),
        value=lista, inline=False,
    )
    embed.set_footer(text=t("lobby_footer", g))
    return embed


def build_embed_config(partida: Partida) -> discord.Embed:
    g   = gid(partida)
    cfg = partida.config
    modo_display = {
        ModoJuego.CLASICO:   t("mode_classic_display",  g),
        ModoJuego.EXTENDIDO: t("mode_extended_display", g),
        ModoJuego.CAOS:      t("mode_caos_display",     g),
    }
    ventaja_display = {
        Ventaja.ALEATORIO:    t("hint_random",   g),
        Ventaja.LETRA:        t("hint_letter",   g),
        Ventaja.TIPO:         t("hint_type",     g),
        Ventaja.RANGO_REGION: t("hint_region",   g),
        Ventaja.HABILIDAD:    t("hint_ability",  g),
        Ventaja.ESTADISTICAS: t("hint_stats",    g),
        Ventaja.PERFIL:       t("hint_profile",  g),
        Ventaja.DEBILIDADES:  t("hint_weakness", g),
        Ventaja.POKEDEX:      t("hint_pokedex",  g),
    }
    if cfg.regiones == ["todas"]:
        regiones_str = t("region_all", g)
    else:
        regiones_str = ", ".join(t(f"region_{r}", g) if f"region_{r}" in t.__globals__["STRINGS"] else r for r in cfg.regiones)

    embed = discord.Embed(title=t("config_title", g), color=discord.Color.blurple())
    embed.add_field(name=t("config_mode_label",    g), value=modo_display.get(cfg.modo_juego, cfg.modo_juego.value), inline=True)
    embed.add_field(name=t("config_hint_label",    g), value=ventaja_display.get(cfg.ventaja, cfg.ventaja.value),    inline=True)
    embed.add_field(name=t("config_regions_label", g), value=regiones_str,                                           inline=True)
    embed.add_field(name=t("config_rounds_label",  g), value=f"⏳ **{cfg.max_rondas}**",                             inline=True)
    return embed


def build_embed_ronda(partida: Partida) -> discord.Embed:
    g = gid(partida)
    modo_display = {
        ModoJuego.CLASICO:   t("mode_classic",  g),
        ModoJuego.EXTENDIDO: t("mode_extended", g),
        ModoJuego.CAOS:      t("mode_caos",     g),
    }
    modo_val = modo_display.get(partida.config.modo_juego, "?")
    restantes = partida.rondas_restantes

    embed = discord.Embed(
        title=t("round_title", g, n=partida.ronda),
        description=t("round_desc", g),
        color=discord.Color.gold(),
    )
    embed.add_field(name=t("round_mode_field",      g), value=modo_val,                    inline=True)
    embed.add_field(name=t("round_players_field",   g), value=str(len(partida.jugadores)), inline=True)
    embed.add_field(name=t("round_remaining_field", g), value=f"⏳ **{restantes}**",       inline=True)
    return embed
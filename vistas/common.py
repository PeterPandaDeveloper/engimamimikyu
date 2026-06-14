"""
vistas/common.py — Constantes y helpers compartidos por todos los paneles de UI.
"""
from __future__ import annotations

import discord
from motor_juego import Partida, ModoJuego, CaosVariante
from i18n import t

# Timeouts de las vistas (en segundos). El debate y la votación no tienen
# límite de tiempo real para el juego — estos valores solo evitan que
# Discord acumule listeners de mensajes abandonados para siempre.
TIMEOUT_LOBBY    = 3600   # 1 hora
TIMEOUT_VOTACION = 3600   # 1 hora
TIMEOUT_DEBATE   = 21600  # 6 horas — el debate puede tardar lo que el grupo quiera

VOTO_NULO_ID = "voto_nulo"


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
    regiones_str = ", ".join(cfg.regiones) if cfg.regiones != ["todas"] else t("region_all", g)

    embed = discord.Embed(title=t("config_title", g), color=discord.Color.blurple())
    embed.add_field(name=t("config_mode_label",    g), value=modo_display.get(cfg.modo_juego, cfg.modo_juego.value), inline=True)
    embed.add_field(name=t("config_hint_label",    g), value=cfg.ventaja.value,                                      inline=True)
    embed.add_field(name=t("config_regions_label", g), value=regiones_str,                                           inline=True)

    # Variante de CAOS — solo visible/aplicable al admin durante configuración
    if cfg.modo_juego == ModoJuego.CAOS:
        variante_display = {
            CaosVariante.NORMAL:          t("caos_variant_normal", g),
            CaosVariante.OBJETIVO_HUMANO: t("caos_variant_human",  g),
            CaosVariante.DANZA_CAOS:      t("caos_variant_dance",  g),
        }
        embed.add_field(
            name=t("caos_variant_label", g),
            value=variante_display.get(cfg.caos_variante, "—"),
            inline=True,
        )
    return embed


def build_embed_ronda(partida: Partida) -> discord.Embed:
    g = gid(partida)
    # IMPORTANTE: el embed público de la ronda NUNCA debe revelar la variante
    # de CAOS activa (Objetivo Humano / Danza Caos). Solo el admin la conoce
    # al configurar. Aquí siempre se muestra el modo de alto nivel tal cual.
    modo_display = {
        ModoJuego.CLASICO:   t("mode_classic",  g),
        ModoJuego.EXTENDIDO: t("mode_extended", g),
        ModoJuego.CAOS:      t("mode_caos",     g),
    }
    modo_val = modo_display.get(partida.config.modo_juego, "?")

    embed = discord.Embed(
        title=t("round_title", g, n=partida.ronda),
        description=t("round_desc", g),
        color=discord.Color.gold(),
    )
    embed.add_field(name=t("round_mode_field",    g), value=modo_val,                    inline=True)
    embed.add_field(name=t("round_players_field", g), value=str(len(partida.jugadores)), inline=True)
    return embed
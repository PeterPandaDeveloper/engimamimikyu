"""
comandos_comunes.py — Constructores de embeds y lógica de ejecución unificada
para Slash Commands y comandos de texto de PokeImpostor.
Elimina la duplicación de código y garantiza paridad absoluta entre ambas interfaces.
"""
from __future__ import annotations

import discord
from i18n import t
from db import (
    obtener_perfil_jugador_async,
    obtener_ranking_async,
    obtener_stats_servidor_async,
    canjear_licencia_async,
    verificar_estado_premium_async,
    get_guild_rol_host,
    set_guild_rol_host_async,
    NOMBRE_ROL_HOST,
)

BUYMEACOFFEE_URL = "https://buymeacoffee.com/peterpandadeveloperz"
INVITE_PERMS_INT = 268817624


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


async def reenviar_rol_secreto(partida, user: discord.Member | discord.User, gid: int) -> tuple[bool, str]:
    """
    Reenvía por mensaje directo el rol secreto asignado en la partida actual.
    Retorna (éxito, clave_i18n_o_mensaje).
    """
    if partida is None or (partida.datos_pokemon is None and not partida.pokemons_ebrios and partida.objetivo_humano is None):
        return False, "impver_no_game"

    if not any(j.id == user.id for j in partida.jugadores_iniciales):
        return False, "impver_not_player"

    try:
        es_impostor = any(imp.id == user.id for imp in partida.impostores_iniciales)
        es_ebrios = bool(partida.pokemons_ebrios)
        es_cj = partida.objetivo_humano is not None

        if es_cj:
            if es_impostor:
                pista = partida.pistas_impostores.get(user.id, "")
                await user.send(embed=partida._build_dm_caos_jugador_impostor(pista))
            else:
                await user.send(embed=partida._build_dm_caos_jugador_tripulante(partida.objetivo_humano))

        elif es_ebrios:
            dp = partida.pokemons_ebrios.get(user.id)
            if dp:
                emb = discord.Embed(
                    title=t("impver_crew_title", gid),
                    description=t("dm_crew_desc", gid, name=dp.get("nombre", "?"), types=" / ".join(dp.get("tipos", ["?"]))),
                    color=discord.Color.from_rgb(30, 160, 80),
                )
                if dp.get("sprite"):
                    emb.set_image(url=dp["sprite"])
                await user.send(embed=emb)

        elif es_impostor:
            await user.send(embed=partida._build_dm_impostor(user))
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
                await user.send(embed=emb)

        return True, "impver_sent"
    except discord.Forbidden:
        return False, "impver_dm_blocked"


async def construir_embed_perfil(gid: int, target: discord.Member | discord.User) -> tuple[discord.Embed | None, str | None]:
    """
    Construye el embed del perfil de entrenador.
    Retorna (embed, None) o (None, clave_i18n_error).
    """
    stats = await obtener_perfil_jugador_async(gid, target.id)
    if stats is None:
        return None, "profile_no_games"

    embed_color = target.color if getattr(target, "color", None) and target.color.value != 0 else discord.Color.from_rgb(255, 203, 5)
    embed = discord.Embed(
        title=t("profile_title", gid, name=getattr(target, "display_name", str(target))),
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
    return embed, None


async def construir_embed_ranking(gid: int, categoria: str = "general") -> tuple[discord.Embed | None, str | None]:
    """
    Construye el embed de la tabla de clasificación.
    Retorna (embed, None) o (None, clave_i18n_error).
    """
    top = await obtener_ranking_async(gid, categoria)
    if not top:
        return None, "ranking_empty"

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
    return embed, None


async def construir_embed_stats(gid: int) -> tuple[discord.Embed | None, str | None]:
    """
    Construye el embed de estadísticas del servidor.
    Retorna (embed, None) o (None, clave_i18n_error).
    """
    stats = await obtener_stats_servidor_async(gid)
    if stats is None:
        return None, "server_stats_empty"

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
    return embed, None


async def construir_payload_licencia(gid: int, bot_id: int) -> tuple[discord.Embed, discord.ui.View | None]:
    """
    Construye el embed y botones de estado de licencia VIP / Premium.
    """
    estado = await verificar_estado_premium_async(gid)
    if estado["es_premium"]:
        embed = discord.Embed(
            title=t("license_status_title", gid),
            description=t("license_status_premium", gid, tipo=estado["tipo"].upper(), details=estado["detalle"]),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        return embed, None
    else:
        vote_url = f"https://top.gg/bot/{bot_id}/vote"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=vote_url, style=discord.ButtonStyle.link))
        view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
        embed = discord.Embed(
            title=t("license_status_title", gid),
            description=t("license_status_free", gid),
            color=discord.Color.light_grey(),
        )
        embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
        return embed, view


async def canjear_clave_licencia(clave: str, gid: int, user_id: int) -> tuple[discord.Embed | None, str | None]:
    """
    Valida y canjea una clave de licencia VIP en DuckDB.
    Retorna (embed, None) o (None, clave_i18n_error).
    """
    res = await canjear_licencia_async(clave, gid, user_id)
    if not res["exito"]:
        err = res.get("error")
        if err == "already_used":
            return None, "redeem_already_used"
        return None, "redeem_not_found"

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
    return embed, None


def construir_payload_voto(gid: int, bot_id: int) -> tuple[discord.Embed, discord.ui.View]:
    """
    Construye el embed y botones para votar en Top.gg.
    """
    vote_url = f"https://top.gg/bot/{bot_id}/vote?guild={gid}" if gid else f"https://top.gg/bot/{bot_id}/vote"
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=t("vote_btn_label", gid), url=vote_url, style=discord.ButtonStyle.link))
    view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
    embed = discord.Embed(
        title=t("vote_embed_title", gid),
        description=t("vote_embed_desc", gid),
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    return embed, view


def construir_payload_donar(gid: int) -> tuple[discord.Embed, discord.ui.View]:
    """
    Construye el embed y botón de donaciones (BuyMeACoffee).
    """
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=t("donate_btn_label", gid), url=BUYMEACOFFEE_URL, style=discord.ButtonStyle.link))
    embed = discord.Embed(
        title=t("donate_embed_title", gid),
        description=t("donate_embed_desc", gid),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    return embed, view


def construir_payload_invitar(gid: int, bot_id: int) -> tuple[discord.Embed, discord.ui.View]:
    """
    Construye el embed y botón de invitación del bot.
    """
    invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions={INVITE_PERMS_INT}&scope=bot%20applications.commands"
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label=t("invite_btn_label", gid), url=invite_url, style=discord.ButtonStyle.link))
    embed = discord.Embed(
        title=t("invite_embed_title", gid),
        description=t("invite_embed_desc", gid),
        color=discord.Color.from_rgb(255, 203, 5),
    )
    embed.set_footer(text="🎨 Arte: @xeechithecat.bsky.social")
    return embed, view


def construir_embed_ayuda(gid: int) -> discord.Embed:
    """
    Construye la guía visual completa del juego.
    """
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
    return embed


def construir_embed_creditos(gid: int) -> discord.Embed:
    """
    Construye el panel de agradecimiento y créditos del artista.
    """
    embed = discord.Embed(
        title=t("credits_title", gid),
        description=t("credits_desc", gid),
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.set_footer(text=t("credits_footer", gid))
    return embed


async def ejecutar_setrole_comun(
    guild: discord.Guild,
    author: discord.Member,
    target_role: discord.Role | None,
    assign_to: discord.Member | None,
    args: list[str] | None = None,
) -> tuple[discord.Embed | None, str | None]:
    """
    Configura, busca o crea el rol oficial de PokeHost para el servidor y lo asigna si corresponde.
    Retorna (embed, None) o (None, mensaje_error_texto).
    """
    gid = guild.id
    creado = False

    if target_role is None and args:
        for a in args:
            if a.isdigit():
                r = guild.get_role(int(a))
                if r:
                    target_role = r
                    break
            r = discord.utils.get(guild.roles, name=a)
            if r:
                target_role = r
                break

    if target_role is None:
        target_role = discord.utils.get(guild.roles, name=NOMBRE_ROL_HOST)
        if target_role is None:
            try:
                target_role = await guild.create_role(
                    name=NOMBRE_ROL_HOST,
                    color=discord.Color.from_rgb(255, 203, 5),
                    mentionable=True,
                    reason="PokeImpostor official host role",
                )
                creado = True
            except discord.Forbidden:
                return None, t("setrole_missing_perms", gid)
            except Exception as e:
                return None, f"❌ Error creating role: {e}"

    # Persistir rol host en DuckDB
    await set_guild_rol_host_async(gid, target_role.id)

    if creado:
        msg = t("setrole_success_created", gid, role=target_role.mention)
    else:
        msg = t("setrole_success_existing", gid, role=target_role.mention)

    usuario_asignar = assign_to
    if usuario_asignar is None:
        if isinstance(author, discord.Member) and target_role not in author.roles:
            usuario_asignar = author

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
    return embed, None

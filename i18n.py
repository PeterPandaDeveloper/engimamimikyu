"""
i18n.py — Sistema de internacionalización para PokeImpostor
Idioma por defecto: inglés. Se puede cambiar por servidor con /implanguage.

El idioma de cada servidor se persiste en disco (data/idiomas.json) para
que sobreviva a reinicios del bot. Si el archivo no existe o está corrupto,
simplemente se empieza desde un registro vacío (todo en inglés).
"""
from __future__ import annotations

import json
import os

# ═══════════════════════════════════════════════════════════════════════════════
#  REGISTRO DE IDIOMA POR SERVIDOR  { guild_id: "en" | "es" }  — persistido con DuckDB
# ═══════════════════════════════════════════════════════════════════════════════

from db import cargar_todos_los_idiomas, get_guild_lang, set_guild_lang

_idiomas: dict[int, str] = cargar_todos_los_idiomas()


def get_lang(guild_id: int) -> str:
    if guild_id not in _idiomas:
        _idiomas[guild_id] = get_guild_lang(guild_id)
    return _idiomas.get(guild_id, "en")


def set_lang(guild_id: int, lang: str) -> None:
    _idiomas[guild_id] = lang
    set_guild_lang(guild_id, lang)


# ═══════════════════════════════════════════════════════════════════════════════
#  DICCIONARIO DE CADENAS
#  Estructura: STRINGS["clave"]["en" | "es"]
#  Para cadenas con variables usa {} y llama con .format(...)
# ═══════════════════════════════════════════════════════════════════════════════

STRINGS: dict[str, dict[str, str]] = {

    # ── Lobby ─────────────────────────────────────────────────────────────────
    "lobby_title": {
        "en": "🎮 PokeImpostor — Waiting Room",
        "es": "🎮 PokeImpostor — Sala de Espera",
    },
    "lobby_desc": {
        "en": (
            "Who knows Pokémon best?\n"
            "The impostor will try to blend in... can you catch them?\n\n"
            "Join below and wait for an admin to start."
        ),
        "es": (
            "¿Quién conoce mejor a los Pokémon?\n"
            "El impostor intentará pasar desapercibido... ¿puedes descubrirlo?\n\n"
            "Únete abajo y espera a que el admin inicie la partida."
        ),
    },
    "lobby_players_field": {
        "en": "👥 Players ({count})",
        "es": "👥 Jugadores ({count})",
    },
    "lobby_nobody": {
        "en": "*Nobody yet... be the first!*",
        "es": "*Nadie todavía... ¡sé el primero!*",
    },
    "lobby_footer": {
        "en": "At least 3 players are needed to start · 🎨 Art: @xeechithecat.bsky.social",
        "es": "Se necesitan al menos 3 jugadores para iniciar · 🎨 Arte: @xeechithecat.bsky.social",
    },
    "lobby_already_in": {
        "en": "You're already in the lobby.",
        "es": "Ya estás en el lobby.",
    },
    "lobby_already_in_other_game": {
        "en": "⚠️ You are already participating in a game in another channel.",
        "es": "⚠️ Ya estás participando en una partida en otro canal.",
    },
    "lobby_not_in": {
        "en": "You're not in the lobby.",
        "es": "No estás en el lobby.",
    },
    "lobby_cancelled": {
        "en": "🛑 **Lobby cancelled by an administrator.**",
        "es": "🛑 **Lobby cancelado por el administrador.**",
    },
    "lobby_full": {
        "en": "⚠️ The lobby is full (maximum 24 players).",
        "es": "⚠️ El lobby está lleno (máximo 24 jugadores).",
    },

    # ── Botones generales ─────────────────────────────────────────────────────
    "btn_join": {
        "en": "⚡ Join",
        "es": "⚡ Unirse",
    },
    "btn_leave": {
        "en": "🚪 Leave",
        "es": "🚪 Salir",
    },
    "btn_config": {
        "en": "⚙️ Settings",
        "es": "⚙️ Configurar",
    },
    "btn_cancel": {
        "en": "❌ Cancel",
        "es": "❌ Cancelar",
    },
    "btn_start_round": {
        "en": "🚀 START ROUND",
        "es": "🚀 INICIAR RONDA",
    },
    "btn_open_vote": {
        "en": "🗳️ Open Voting",
        "es": "🗳️ Abrir Votación",
    },
    "btn_force_close": {
        "en": "⚠️ Close Voting (Admin)",
        "es": "⚠️ Cerrar Votación (Admin)",
    },
    "btn_show_results": {
        "en": "Show Results",
        "es": "Mostrar Resultados",
    },
    "btn_rematch": {
        "en": "🔄 Quick Rematch",
        "es": "🔄 Revancha Rápida",
    },
    "btn_change_config": {
        "en": "⚙️ Change Settings",
        "es": "⚙️ Cambiar Configuración",
    },
    "btn_end_session": {
        "en": "❌ End Session",
        "es": "❌ Terminar Sesión",
    },
    "btn_caos_yes": {
        "en": "Yes, there are more",
        "es": "Sí, siguen habiendo más",
    },
    "btn_caos_no": {
        "en": "No, that was the last one",
        "es": "No, era el último impostor",
    },

    # ── Permisos ──────────────────────────────────────────────────────────────
    "only_admin": {
        "en": "Only administrators can do that.",
        "es": "Solo administradores pueden hacer eso.",
    },
    "only_host_or_admin": {
        "en": "⚠️ Only members with the **{role}** role or Administrators can do that.",
        "es": "⚠️ Solo los miembros con el rol **{role}** o Administradores pueden hacer eso.",
    },
    "min_players": {
        "en": "At least **3 players** are needed to start.",
        "es": "Se necesitan al menos **3 jugadores** para iniciar.",
    },

    # ── Configuración ─────────────────────────────────────────────────────────
    "config_title": {
        "en": "⚙️ Game Settings",
        "es": "⚙️ Configuración de la Partida",
    },
    "config_mode_label": {
        "en": "Mode",
        "es": "Modo",
    },
    "config_hint_label": {
        "en": "Hint",
        "es": "Pista",
    },
    "config_regions_label": {
        "en": "Regions",
        "es": "Regiones",
    },
    "config_saved": {
        "en": "✅ Settings saved. Starting round!",
        "es": "✅ Configuración guardada. ¡Arrancando ronda!",
    },
    "config_expired": {
        "en": "The settings panel has expired.",
        "es": "El panel de configuración expiró.",
    },
    "sel_gamemode": {
        "en": "🎲 Game Mode",
        "es": "🎲 Modo de juego",
    },
    "sel_hint": {
        "en": "🔍 Impostor Hint",
        "es": "🔍 Ventaja del impostor",
    },
    "sel_regions": {
        "en": "🗺️ Regions",
        "es": "🗺️ Regiones",
    },
    "sel_rounds": {
        "en": "⏳ Round limit (1 to 9)...",
        "es": "⏳ Límite de rondas (1 a 9)...",
    },
    "config_rounds_label": {
        "en": "⏳ Round Limit",
        "es": "⏳ Límite de Rondas",
    },
    "config_rounds_option": {
        "en": "{n} Rounds",
        "es": "{n} Rondas",
    },
    "config_rounds_desc": {
        "en": "Up to {n} debate rounds before timeout",
        "es": "Hasta {n} rondas de debate antes de derrota por tiempo",
    },

    # Opciones de modo
    "mode_classic": {
        "en": "Classic",
        "es": "Clásico",
    },
    "mode_classic_desc": {
        "en": "Always 1 impostor",
        "es": "Siempre 1 impostor",
    },
    "mode_extended": {
        "en": "Extended",
        "es": "Extendido",
    },
    "mode_extended_desc": {
        "en": "1 impostor per 3 players",
        "es": "1 impostor por cada 3 jugadores",
    },
    "mode_caos": {
        "en": "⚠️ Chaos",
        "es": "⚠️ Caos",
    },
    "mode_caos_desc": {
        "en": "Random impostors (even 0!)",
        "es": "Impostores totalmente aleatorios (¡incluso 0!)",
    },
    "mode_classic_display": {
        "en": "Classic (1 impostor)",
        "es": "Clásico (1 impostor)",
    },
    "mode_extended_display": {
        "en": "Extended (1 per 3 players)",
        "es": "Extendido (1 por cada 3 jugadores)",
    },
    "mode_caos_display": {
        "en": "⚠️ Chaos (random, even 0)",
        "es": "⚠️ Caos (aleatorio, incluso 0)",
    },

    # Opciones de pista
    "hint_random":       {"en": "Random",              "es": "Aleatorio"},
    "hint_random_desc":  {"en": "Changes each round",  "es": "Cambia cada ronda"},
    "hint_letter":       {"en": "First letter",        "es": "Letra inicial"},
    "hint_type":         {"en": "Type",                "es": "Tipo"},
    "hint_region":       {"en": "Origin Region",       "es": "Región de origen"},
    "hint_ability":      {"en": "Ability",             "es": "Habilidad"},
    "hint_word": {
        "en": "Ambiguous Word",
        "es": "Palabra Ambigua",
    },
    "hint_word_desc": {
        "en": "A single ambiguous and thematic word",
        "es": "Una sola palabra ambigua y temática",
    },
    "hint_profile": {
        "en": "Species Profile",
        "es": "Perfil de Especie",
    },
    "hint_profile_desc": {
        "en": "Species, habitat & egg group combined",
        "es": "Especie, hábitat y grupo huevo combinados",
    },
    "hint_weakness": {
        "en": "Weaknesses",
        "es": "Debilidades",
    },
    "hint_weakness_desc": {
        "en": "Its biggest type weakness(es)",
        "es": "Su(s) mayor(es) debilidad(es) de tipo",
    },
    "hint_pokedex": {
        "en": "Pokédex Entry",
        "es": "Entrada de Pokédex",
    },
    "hint_pokedex_desc": {
        "en": "First words of its Pokédex description",
        "es": "Primeras palabras de su descripción de Pokédex",
    },

    # Opciones de regiones
    "region_all":   {"en": "All",          "es": "Todas"},
    "region_gen1":  {"en": "Kanto  (Gen 1)","es": "Kanto  (Gen 1)"},
    "region_gen2":  {"en": "Johto  (Gen 2)","es": "Johto  (Gen 2)"},
    "region_gen3":  {"en": "Hoenn  (Gen 3)","es": "Hoenn  (Gen 3)"},
    "region_gen4":  {"en": "Sinnoh (Gen 4)","es": "Sinnoh (Gen 4)"},
    "region_gen5":  {"en": "Unova  (Gen 5)","es": "Teselia (Gen 5)"},
    "region_gen6":  {"en": "Kalos  (Gen 6)","es": "Kalos  (Gen 6)"},
    "region_gen7":  {"en": "Alola  (Gen 7)","es": "Alola  (Gen 7)"},
    "region_gen8":  {"en": "Galar  (Gen 8)","es": "Galar  (Gen 8)"},
    "region_gen9":  {"en": "Paldea (Gen 9)","es": "Paldea (Gen 9)"},

    # Opciones de timer — eliminadas (el debate ya no tiene límite de tiempo)

    # ── API / errores ─────────────────────────────────────────────────────────
    "api_error": {
        "en": (
            "❌ **Connection error:** Could not fetch a Pokémon from PokéAPI "
            "after several attempts. Try again in a few seconds."
        ),
        "es": (
            "❌ **Error de conexión:** No se pudo obtener un Pokémon de PokéAPI "
            "después de varios intentos. Vuelvan a intentarlo en unos segundos."
        ),
    },
    "dm_blocked_warning": {
        "en": (
            "⚠️ **Heads up!** I couldn't send the role via DM to: {mentions}\n"
            "They probably have server DMs disabled. "
            "Ask them to enable *'Allow direct messages from server members'* and use `/impver`."
        ),
        "es": (
            "⚠️ **¡Atención!** No pude enviarle el rol por DM a: {mentions}\n"
            "Probablemente tienen los DMs del servidor bloqueados. "
            "Que habiliten *'Permitir mensajes directos de miembros del servidor'* y usen `/impver`."
        ),
    },

    # ── DMs de rol ────────────────────────────────────────────────────────────
    "dm_impostor_title": {
        "en": "🕵️ YOU ARE THE IMPOSTOR",
        "es": "🕵️ ERES EL IMPOSTOR",
    },
    "dm_impostor_desc": {
        "en": "You don't know the secret Pokémon, but you have a clue.\n\n🔍 **Your hint:** {hint}",
        "es": "No sabes cuál es el Pokémon secreto, pero tienes una ventaja.\n\n🔍 **Tu pista:** {hint}",
    },
    "dm_impostor_accomplices_title": {
        "en": "🔪 {count} impostors total",
        "es": "🔪 Hay {count} impostores en total",
    },
    "dm_impostor_accomplices_title_hidden": {
        "en": "🔪 You're not alone",
        "es": "🔪 No estás solo",
    },
    "dm_impostor_accomplices_value": {
        "en": "Your accomplices: {names}",
        "es": "Tus cómplices: {names}",
    },
    "dm_impostor_footer": {
        "en": "Don't share this message · 🎨 Art: @xeechithecat.bsky.social",
        "es": "No reenvíes este mensaje · 🎨 Arte: @xeechithecat.bsky.social",
    },
    "dm_crew_title": {
        "en": "✅ YOU ARE A CREWMATE",
        "es": "✅ ERES TRIPULANTE",
    },
    "dm_crew_desc": {
        "en": (
            "The secret Pokémon is: **{name}**\n"
            "Type: {types}\n\n"
            "Talk about it without saying its name directly.\n"
            "Find out who doesn't seem to know what everyone's talking about!"
        ),
        "es": (
            "El Pokémon secreto es: **{name}**\n"
            "Tipo: {types}\n\n"
            "Habla de él sin decir su nombre directamente.\n"
            "¡Descubre quién no sabe de qué están hablando!"
        ),
    },
    "dm_crew_footer": {
        "en": "Use /impver to see again · 🎨 Art: @xeechithecat.bsky.social",
        "es": "Usa /impver si necesitas volver a verlo · 🎨 Arte: @xeechithecat.bsky.social",
    },

    # ── Pistas generadas ──────────────────────────────────────────────────────
    "hint_text_letter":      {"en": "Its name starts with the letter **{v}**.",  "es": "Su nombre empieza con la letra **{v}**."},
    "hint_text_ends_letter": {"en": "Its name ends with the letter **{v}**.",    "es": "Su nombre termina con la letra **{v}**."},
    "hint_text_type":        {"en": "Its type is **{v}**.",                      "es": "Es de tipo **{v}**."},
    "hint_text_region":  {"en": "It first appeared in the **{v}**.",         "es": "Apareció por primera vez en la **{v}**."},
    "hint_text_ability": {"en": "One of its abilities is **{v}**.",          "es": "Una de sus habilidades es **{v}**."},

    # Estadísticas: nombres legibles
    "stat_name_hp":      {"en": "HP",              "es": "PS"},
    "stat_name_attack":  {"en": "Attack",          "es": "Ataque"},
    "stat_name_defense": {"en": "Defense",         "es": "Defensa"},
    "stat_name_spatk":   {"en": "Sp. Attack",      "es": "Ataque Esp."},
    "stat_name_spdef":   {"en": "Sp. Defense",     "es": "Defensa Esp."},
    "stat_name_speed":   {"en": "Speed",           "es": "Velocidad"},

    "hint_text_word": {
        "en": "🔮 Concept Clue: **{word}**\n*(An ambiguous thematic word related to the secret Pokémon)*",
        "es": "🔮 Pista Conceptual: **{word}**\n*(Una palabra ambigua y temática relacionada con el Pokémon secreto)*",
    },

    # Arquetipos RPG de estadísticas
    "arch_glass_cannon_name": {"en": "Glass Cannon", "es": "Cañón de Cristal"},
    "arch_glass_cannon_desc": {"en": "High offensive power and speed, but fragile defenses", "es": "Gran potencia ofensiva y velocidad, pero defensas frágiles"},

    "arch_agile_scout_name": {"en": "Agile Scout", "es": "Explorador Veloz"},
    "arch_agile_scout_desc": {"en": "Blazing speed and reaction, outpaces almost any foe", "es": "Velocidad vertiginosa, supera en rapidez a casi cualquier rival"},

    "arch_heavy_hitter_name": {"en": "Heavy Hitter", "es": "Golpeador Pesado"},
    "arch_heavy_hitter_desc": {"en": "Devastating attack power, but slow movement", "es": "Fuerza de ataque demoledora, pero movimientos lentos"},

    "arch_defensive_tank_name": {"en": "Defensive Tank", "es": "Tanque Defensivo"},
    "arch_defensive_tank_desc": {"en": "High durability and resistance, withstands massive punishment", "es": "Gran aguante y resistencia, soporta muchos golpes"},

    "arch_bulky_powerhouse_name": {"en": "Bulky Powerhouse", "es": "Titán Todoterreno"},
    "arch_bulky_powerhouse_desc": {"en": "Deadly offensive power combined with sturdy defense", "es": "Poderoso en ataque y con gran aguante defensivo"},

    "arch_well_rounded_name": {"en": "Balanced Fighter", "es": "Combatiente Equilibrado"},
    "arch_well_rounded_desc": {"en": "Well-balanced attributes, versatile and adaptable", "es": "Atributos muy parejos en todas las áreas, versátil y adaptable"},

    "highlight_hp": {"en": "Colossal Stamina (HP)", "es": "Salud y Vitalidad Colosal"},
    "highlight_attack": {"en": "Brute Physical Strength", "es": "Fuerza Física Brutal"},
    "highlight_defense": {"en": "Ironclad Physical Defense", "es": "Defensa Física Impenetrable"},
    "highlight_special-attack": {"en": "Devastating Special Power", "es": "Poder Especial Devastador"},
    "highlight_special-defense": {"en": "Immense Special Resistance", "es": "Gran Resistencia Especial"},
    "highlight_speed": {"en": "Lightning Speed", "es": "Velocidad Relámpago"},

    # Perfil: especie + hábitat + grupo huevo
    "hint_unknown_value": {
        "en": "unknown",
        "es": "desconocido",
    },
    "hint_text_profile": {
        "en": "It's known as the **{species}**. Its habitat is **{habitat}**, and it belongs to the **{egg}** egg group.",
        "es": "Es conocido como el **{species}**. Su hábitat es **{habitat}**, y pertenece al grupo huevo **{egg}**.",
    },

    # Debilidades
    "hint_text_weakness_x4": {
        "en": "It's extremely weak (x4) to **{types}**.",
        "es": "Es extremadamente débil (x4) contra **{types}**.",
    },
    "hint_text_weakness_x2": {
        "en": "It's weak (x2) to **{types}**.",
        "es": "Es débil (x2) contra **{types}**.",
    },
    "hint_text_weakness_none": {
        "en": "It has no notable type weaknesses.",
        "es": "No tiene debilidades de tipo destacables.",
    },

    # Pokédex entry
    "hint_text_pokedex": {
        "en": "Pokédex log (classified): \"{excerpt}\"",
        "es": "Registro de Pokédex (clasificado): \"{excerpt}\"",
    },
    "hint_text_pokedex_unavailable": {
        "en": "No Pokédex entry is available for it.",
        "es": "No hay entrada de Pokédex disponible para él.",
    },

    # ── Ronda ─────────────────────────────────────────────────────────────────
    "round_title": {
        "en": "🏆 ROUND {n}",
        "es": "🏆 RONDA {n}",
    },
    "round_desc": {
        "en": (
            "Roles have been sent by DM. Check them!\n\n"
            "Debate and try to figure out who doesn't know which Pokémon you're talking about.\n"
            "When ready, open the voting."
        ),
        "es": (
            "Los roles fueron enviados por DM. ¡Revísenlos!\n\n"
            "Debatan e intenten descubrir quién no sabe de qué Pokémon están hablando.\n"
            "Cuando estén listos, inicien la votación."
        ),
    },
    "round_mode_field":    {"en": "Mode",    "es": "Modo"},
    "round_players_field": {"en": "Players", "es": "Jugadores"},
    "round_remaining_field": {"en": "⏳ Rounds Left", "es": "⏳ Rondas Restantes"},
    "round_rematch_title": {
        "en": "🏆 ROUND {n} (REMATCH)",
        "es": "🏆 RONDA {n} (REVANCHA)",
    },
    "round_rematch_desc": {
        "en": "New game with the same players! Check your DMs.",
        "es": "¡Nueva partida con los mismos jugadores! Revisen sus DMs.",
    },
    "round_next_title": {
        "en": "🔄 Round {n}",
        "es": "🔄 Ronda {n}",
    },
    "round_next_desc": {
        "en": "The debate continues! Discuss and open voting when ready.",
        "es": "¡El debate continúa! Debatan y abran la votación cuando estén listos.",
    },
    "game_over_timeout_title": {
        "en": "⌛ TIME'S UP — IMPOSTORS ESCAPED!",
        "es": "⌛ ¡TIEMPO AGOTADO — LOS IMPOSTORES ESCAPARON!",
    },
    "game_over_timeout_desc": {
        "en": "The crew ran out of debate rounds! The impostors survived the clock and win the match.",
        "es": "¡Los tripulantes se quedaron sin rondas de debate! Los impostores sobrevivieron al límite de tiempo y ganan la partida.",
    },

    # ── Modo Caos 0 impostores ────────────────────────────────────────────────
    "caos_zero_title": {
        "en": "🌀 CHAOS MODE — Mystery Round",
        "es": "🌀 MODO CAOS — Ronda Misteriosa",
    },
    "caos_zero_desc": {
        "en": (
            "Fate has spoken...\n\n"
            "**This round has no impostors.**\n"
            "Or so they say. Can you really trust each other?\n\n"
            "Debate normally. In the end, everyone is innocent! (maybe 😏)"
        ),
        "es": (
            "El azar ha hablado...\n\n"
            "**Esta ronda no hay impostores.**\n"
            "O eso es lo que dicen. ¿Pueden confiar el uno en el otro?\n\n"
            "Debatan con normalidad. Al final, ¡todos son inocentes! (o no 😏)"
        ),
    },

    # ── Timer ─────────────────────────────────────────────────────────────────
    "timer_expired_title": {
        "en": "⏰ Time's up!",
        "es": "⏰ ¡Tiempo agotado!",
    },
    "timer_expired_desc": {
        "en": "Debate time is over. **Voting starts now!**",
        "es": "El debate ha terminado. **¡La votación comienza ahora!**",
    },

    # ── Votación ──────────────────────────────────────────────────────────────
    "vote_title_open": {
        "en": "🗳️ VOTING OPEN",
        "es": "🗳️ VOTACIÓN ABIERTA",
    },
    "vote_desc": {
        "en": "**{current} / {total}** votes registered.\nSelect your suspects (anonymous).",
        "es": "**{current} / {total}** votos registrados.\nSelecciona a tus sospechosos (anónimo).",
    },
    "vote_placeholder": {
        "en": "🔍 Select your suspects...",
        "es": "🔍 Selecciona a tus sospechosos...",
    },
    "vote_only_players": {
        "en": "👻 Only active players can vote.",
        "es": "👻 Solo los jugadores activos pueden votar.",
    },
    "vote_already_voted": {
        "en": "You already voted.",
        "es": "Ya emitiste tu voto.",
    },
    "vote_registered": {
        "en": "✅ Your vote was registered anonymously.",
        "es": "✅ Voto registrado de forma anónima.",
    },
    "vote_force_closed": {
        "en": "🔒 Voting forcibly closed by admin. ({current}/{total} votes received)",
        "es": "🔒 Votación cerrada forzosamente por el admin. ({current}/{total} votos recibidos)",
    },
    "vote_only_admin_force": {
        "en": "Only admins can force-close the vote.",
        "es": "Solo admins pueden forzar el cierre de la votación.",
    },

    # ── Resultados ────────────────────────────────────────────────────────────
    "results_tally_title": {
        "en": "📊 Vote Tally",
        "es": "📊 Conteo de Votos",
    },
    "results_no_votes": {
        "en": "*Nobody received votes.*",
        "es": "*Nadie recibió votos.*",
    },
    "results_nobody_voted": {
        "en": "Nobody voted for anyone. The vote has no effect.",
        "es": "Nadie recibió votos. La votación no tiene efecto.",
    },
    "results_tie_title": {
        "en": "⚖️ TIE!",
        "es": "⚖️ ¡EMPATE!",
    },
    "results_tie_desc": {
        "en": "No consensus. Nobody is ejected this round.",
        "es": "No hay consenso. Nadie es expulsado esta ronda.",
    },
    "results_left_server": {
        "en": "⚠️ The most voted player has left the server. Nobody is ejected.",
        "es": "⚠️ El jugador más votado ya no está en el servidor. Nadie es expulsado.",
    },
    "results_impostor_found_title": {
        "en": "🎉 IMPOSTOR REVEALED!",
        "es": "🎉 ¡IMPOSTOR REVELADO!",
    },
    "results_impostor_found_desc": {
        "en": "**{name} WAS THE IMPOSTOR.**\n\n👻 **Mimikyu has dropped its disguise.**\nThe crewmates win!",
        "es": "**{name} SÍ ERA IMPOSTOR.**\n\n👻 **El Mimikyu ha abandonado su disfraz.**\n¡Los tripulantes han ganado!",
    },
    "results_impostor_more_title": {
        "en": "🔪 Impostor found",
        "es": "🔪 Impostor descubierto",
    },
    "results_impostor_more_desc": {
        "en": "**{name} WAS AN IMPOSTOR.**\n\nBut there are still **{remaining}** traitor(s) hiding...",
        "es": "**{name} SÍ ERA IMPOSTOR.**\n\nPero aún quedan **{remaining}** traidor(es) oculto(s)...",
    },
    "results_innocent_title": {
        "en": "😱 Innocent ejected!",
        "es": "😱 ¡Inocente expulsado!",
    },
    "results_innocent_desc": {
        "en": "**{name} WAS NOT THE IMPOSTOR.**\n\n🐘 **The Donphan is still walking the room.**",
        "es": "**{name} NO ERA IMPOSTOR.**\n\n🐘 **El Donphan sigue caminando por la sala.**",
    },
    "results_impostors_win_title": {
        "en": "💀 IMPOSTORS WIN",
        "es": "💀 LOS IMPOSTORES HAN GANADO",
    },
    "results_impostors_win_desc": {
        "en": "The traitors are the majority. They've taken control.\nThe secret Pokémon remains in darkness...",
        "es": "Los traidores son mayoría. Han tomado el control.\nEl Pokémon secreto permanece en la oscuridad...",
    },
    "results_vote_field": {
        "en": "{votes} vote(s) — **{name}**",
        "es": "{votes} voto(s) — **{name}**",
    },

    # ── Caos pregunta final ───────────────────────────────────────────────────
    "caos_question_title": {
        "en": "🌀 Chaos Mode — Final Question",
        "es": "🌀 Modo Caos — Pregunta Final",
    },
    "caos_question_desc": {
        "en": (
            "You found an impostor... but in **Chaos Mode** nothing is certain.\n\n"
            "Do you think there are **more impostors** still hiding among you?"
        ),
        "es": (
            "Encontraron a un impostor... pero en el **Modo Caos** nada es seguro.\n\n"
            "¿Creen que todavía hay **más impostores** ocultos entre ustedes?"
        ),
    },

    # ── Pantalla final ────────────────────────────────────────────────────────
    "final_title": {
        "en": "🎊 GAME OVER",
        "es": "🎊 PARTIDA TERMINADA",
    },
    "final_pokemon_field": {
        "en": "🔴 The Secret Pokémon was",
        "es": "🔴 El Pokémon Secreto era",
    },
    "final_impostors_field": {
        "en": "Impostors",
        "es": "Impostores",
    },
    "final_crew_field": {
        "en": "Crewmates",
        "es": "Tripulantes",
    },
    "final_none_caos": {
        "en": "None (Chaos Mode)",
        "es": "Ninguno (Modo Caos)",
    },
    "final_footer": {
        "en": "Round {n} completed · 🎨 Art: @xeechithecat.bsky.social",
        "es": "Ronda {n} completada · 🎨 Arte: @xeechithecat.bsky.social",
    },

    # ── Sesión cerrada ────────────────────────────────────────────────────────
    "session_closed_title": {
        "en": "👋 Session closed",
        "es": "👋 Sesión cerrada",
    },
    "session_closed_desc": {
        "en": "Thanks for playing **PokeImpostor**.\nUse `/play-kyu` (or `-mimi play`) to open a new lobby.",
        "es": "Gracias por jugar **PokeImpostor**.\nUsen `/play-kyu` (o `-mimi play`) para abrir un nuevo lobby.",
    },

    # ── /impver ───────────────────────────────────────────────────────────────
    "impver_no_game": {
        "en": "There is no active game in this channel.",
        "es": "No hay una partida activa en este canal.",
    },
    "impver_not_player": {
        "en": "You didn't participate in this round.",
        "es": "No participaste en esta ronda.",
    },
    "impver_sent": {
        "en": "✅ Your role has been re-sent by DM.",
        "es": "✅ Te reenvié tu rol por DM.",
    },
    "impver_dm_blocked": {
        "en": "❌ I couldn't DM you. Make sure you have server DMs enabled.",
        "es": "❌ No pude enviarte un DM. Revisa que tengas los DMs del servidor habilitados.",
    },
    "impver_impostor_title": {
        "en": "🕵️ Your role — IMPOSTOR",
        "es": "🕵️ Tu rol — IMPOSTOR",
    },
    "impver_crew_title": {
        "en": "✅ Your role — CREWMATE",
        "es": "✅ Tu rol — TRIPULANTE",
    },

    # ── /implanguage ──────────────────────────────────────────────────────────
    "lang_changed_en": {
        "en": "🇬🇧 Language set to **English** for this server.",
        "es": "🇬🇧 Idioma cambiado a **inglés** para este servidor.",
    },
    "lang_changed_es": {
        "en": "🇪🇸 Language set to **Spanish** for this server.",
        "es": "🇪🇸 Idioma cambiado a **español** para este servidor.",
    },
    "lang_only_admin": {
        "en": "Only administrators can change the language.",
        "es": "Solo administradores pueden cambiar el idioma.",
    },

    # ── /imphelp ──────────────────────────────────────────────────────────────
    "help_title": {
        "en": "📖 PokeImpostor — Quick Guide",
        "es": "📖 PokeImpostor — Guía Rápida",
    },
    "help_desc": {
        "en": "The deduction game where Pokémon knowledge is your weapon.",
        "es": "El juego de deducción donde el conocimiento Pokémon es tu arma.",
    },
    "help_step1_name":  {"en": "1️⃣  Join the Lobby",  "es": "1️⃣  Unirse al Lobby"},
    "help_step1_value": {
        "en": "Use `/play-kyu` (or `-mimi play`) to open the room. Everyone presses **⚡ Join**.",
        "es": "Usa `/play-kyu` (o `-mimi play`) para abrir la sala. Todos presionan **⚡ Unirse**.",
    },
    "help_step2_name":  {"en": "2️⃣  Check your DM",  "es": "2️⃣  Revisar el DM"},
    "help_step2_value": {
        "en": (
            "**Crewmates** get the image and name of the secret Pokémon.\n"
            "**The Impostor** only gets a clue and must pretend to know it.\n"
            "If you closed the DM, use `/role-kyu` (or `-mimi role`) to see it again."
        ),
        "es": (
            "**Tripulantes** reciben la imagen y nombre del Pokémon secreto.\n"
            "**El Impostor** recibe solo una pista y debe fingir que lo conoce.\n"
            "Si cerraste el DM, usa `/role-kyu` (o `-mimi ver`) para volver a verlo."
        ),
    },
    "help_step3_name":  {"en": "3️⃣  The Debate",  "es": "3️⃣  El Debate"},
    "help_step3_value": {
        "en": (
            "Talk about the Pokémon without saying its name directly.\n"
            "Watch for who hesitates or gives overly vague hints."
        ),
        "es": (
            "Hablen del Pokémon sin decir su nombre directamente.\n"
            "Observen quién titubea, da pistas demasiado vagas o demasiado generales."
        ),
    },
    "help_step4_name":  {"en": "4️⃣  Voting",  "es": "4️⃣  Votación"},
    "help_step4_value": {
        "en": (
            "The admin opens the vote. Choose your suspects (anonymous).\n"
            "The most voted player is ejected. Find all impostors to win!"
        ),
        "es": (
            "El admin abre la votación. Elijan a sus sospechosos (anónimo).\n"
            "El más votado es expulsado. ¡Descubran a todos los impostores para ganar!"
        ),
    },
    "help_modes_name":  {"en": "⚙️  Game Modes",  "es": "⚙️  Modos de Juego"},
    "help_modes_value": {
        "en": (
            "• **Classic:** 1 secret Impostor, 1 secret Pokémon.\n"
            "• **Extended:** Multiple Impostors who know each other.\n"
            "• **Chaos:** Unpredictable rules (0 to N Impostors, Human Target, or Chaos Dance)."
        ),
        "es": (
            "• **Clásico:** 1 Impostor secreto, 1 Pokémon secreto.\n"
            "• **Extendido:** Múltiples Impostores cómplices que se conocen.\n"
            "• **Caos:** Reglas impredecibles (0 a N Impostores, Objetivo Humano o Danza Caos)."
        ),
    },
    "help_commands_name": {
        "en": "📜  Available Commands",
        "es": "📜  Comandos Disponibles",
    },
    "help_commands_value": {
        "en": (
            "• `/play-kyu` (or `-mimi play` / `play -mimi`) — Start new waiting room / lobby\n"
            "• `/role-kyu` (or `-mimi role` / `role -mimi`) — Re-send your secret role via DM\n"
            "• `/profile-kyu [@user]` (or `-mimi profile` / `profile -mimi`) — View trainer profile\n"
            "• `/leaderboard-kyu` (or `-mimi leaderboard` / `leaderboard -mimi`) — Server leaderboard\n"
            "• `/stats-kyu` (or `-mimi stats` / `stats -mimi`) — Server match analytics\n"
            "• `/setrole-kyu [@role] [@user]` (or `-mimi setrole`) — Set or create host role (Admin)\n"
            "• `/license-kyu` (or `-mimi license` / `license -mimi`) — Check VIP status\n"
            "• `/redeem-kyu <key>` (or `-mimi redeem <key>`) — Redeem VIP Key\n"
            "• `/credits-kyu` (or `-mimi credits` / `credits -mimi`) — Artist & illustration credits\n"
            "• `/lang-kyu` (or `-mimi lang <en|es>`) — Change language (Admin only)\n"
            "• `/help-kyu` (or `-mimi help` / `help -mimi`) — Show this guide\n"
            "*(💡 Use slash commands `/...-kyu` or chat with prefix `-mimi <cmd>` or suffix `<cmd> -mimi`!)*"
        ),
        "es": (
            "• `/play-kyu` (o `-mimi play` / `-mimi jugar` / `play -mimi`) — Abrir nueva sala de espera\n"
            "• `/role-kyu` (o `-mimi ver` / `ver -mimi` / `rol -mimi`) — Reenviar tu rol secreto por DM\n"
            "• `/profile-kyu [@usuario]` (o `-mimi perfil` / `perfil -mimi`) — Ver perfil de entrenador\n"
            "• `/leaderboard-kyu` (o `-mimi ranking` / `ranking -mimi`) — Tablas de clasificación\n"
            "• `/stats-kyu` (o `-mimi stats` / `stats -mimi`) — Analítica de partidas del servidor\n"
            "• `/setrole-kyu [@rol] [@usuario]` (o `-mimi setrole`) — Configurar o crear rol de anfitrión (Admin)\n"
            "• `/license-kyu` (o `-mimi licencia` / `licencia -mimi`) — Consultar estado VIP\n"
            "• `/redeem-kyu <clave>` (o `-mimi canjear <clave>`) — Canjear clave VIP\n"
            "• `/credits-kyu` (o `-mimi creditos` / `creditos -mimi`) — Créditos del artista del bot\n"
            "• `/lang-kyu` (o `-mimi idioma <es|en>`) — Cambiar idioma (Solo Admin)\n"
            "• `/help-kyu` (o `-mimi help` / `help -mimi`) — Mostrar esta guía\n"
            "*(💡 ¡Usa comandos slash `/...-kyu` o escribe en el chat con prefijo `-mimi <comando>` o sufijo `<comando> -mimi`!)*"
        ),
    },
    "help_footer": {
        "en": "Good luck, trainer! · 🎨 Art: @xeechithecat.bsky.social",
        "es": "¡Buena suerte, entrenador! · 🎨 Arte: @xeechithecat.bsky.social",
    },
    "help_art_credits_name": {
        "en": "🎨  Art & Illustrations / Arte del Bot",
        "es": "🎨  Arte e Ilustraciones del Bot",
    },
    "help_art_credits_value": {
        "en": (
            "Illustrated with love by **@xeechithecat.bsky.social**!\n"
            "🔗 Follow on Bluesky: [bsky.app/profile/xeechithecat.bsky.social](https://bsky.app/profile/xeechithecat.bsky.social)"
        ),
        "es": (
            "¡Ilustrado con amor por **@xeechithecat.bsky.social**!\n"
            "🔗 Sigue su trabajo en Bluesky: [bsky.app/profile/xeechithecat.bsky.social](https://bsky.app/profile/xeechithecat.bsky.social)"
        ),
    },
    "credits_title": {
        "en": "🎨 Artist Credits — PokeImpostor",
        "es": "🎨 Créditos del Artista — PokeImpostor",
    },
    "credits_desc": {
        "en": (
            "The character art, sprites, and illustrations of PokeImpostor are made by the talented artist:\n\n"
            "🌟 **@xeechithecat.bsky.social**\n"
            "🌐 Bluesky: [https://bsky.app/profile/xeechithecat.bsky.social](https://bsky.app/profile/xeechithecat.bsky.social)\n\n"
            "Be sure to visit their profile and show some love to their work! 💖"
        ),
        "es": (
            "El arte de personajes, sprites e ilustraciones de PokeImpostor fueron creados por el talentoso artista:\n\n"
            "🌟 **@xeechithecat.bsky.social**\n"
            "🌐 Perfil de Bluesky: [https://bsky.app/profile/xeechithecat.bsky.social](https://bsky.app/profile/xeechithecat.bsky.social)\n\n"
            "¡Visita su perfil de Bluesky y dale mucho apoyo a su arte! 💖"
        ),
    },
    "credits_footer": {
        "en": "🎨 Art by @xeechithecat.bsky.social",
        "es": "🎨 Arte por @xeechithecat.bsky.social",
    },

    # ── /impregister ──────────────────────────────────────────────────────────
    "register_only_host": {
        "en": "⚠️ Only members with the **{role}** role or Administrators can open game lobbies.",
        "es": "⚠️ Solo los miembros con el rol **{role}** o Administradores pueden abrir salas de juego.",
    },
    "register_already_active": {
        "en": "⚠️ There is already an active game in this channel. Finish it before opening another.",
        "es": "⚠️ Ya hay una partida activa en este canal. Termínenla antes de abrir otra.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL DE TRADUCCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def t(key: str, guild_id: int, **kwargs) -> str:
    """
    Devuelve la cadena traducida para `key` en el idioma del servidor.
    Acepta kwargs para formatear variables ({name}, {count}, etc.)
    Si la clave no existe devuelve la clave misma como fallback.
    """
    lang  = get_lang(guild_id)
    entry = STRINGS.get(key, {})
    text  = entry.get(lang) or entry.get("en") or key
    return text.format(**kwargs) if kwargs else text

# ── Nuevos modos ──────────────────────────────────────────────────────────────
STRINGS["mode_caos_jugador"] = {
    "en": "🕵️ Chaos: Human Target",
    "es": "🕵️ Caos: Objetivo Humano",
}
STRINGS["mode_caos_jugador_display"] = {
    "en": "🕵️ Chaos: Human Target",
    "es": "🕵️ Caos: Objetivo Humano",
}
STRINGS["mode_caos_jugador_desc"] = {
    "en": "One player IS the target. The detective tries to guess who from clues.",
    "es": "Un jugador ES el objetivo. El detective intenta adivinarlo con pistas.",
}

STRINGS["dm_caos_jugador_detective_title"] = {
    "en": "🕵️ YOU ARE THE IMPOSTOR",
    "es": "🕵️ ERES EL IMPOSTOR",
}
STRINGS["dm_caos_jugador_impostor_title"] = {
    "en": "🕵️ YOU ARE THE IMPOSTOR",
    "es": "🕵️ ERES EL IMPOSTOR",
}
STRINGS["dm_caos_jugador_impostor_desc"] = {
    "en": (
        "The crewmates are describing a secret member of this server.\n\n"
        "You do NOT know who the secret target is!\n"
        "Listen carefully to what they say, blend in so they don't suspect you, "
        "and try to figure out who everyone is talking about!"
    ),
    "es": (
        "Los tripulantes están describiendo a un miembro secreto de este servidor.\n\n"
        "¡Tú NO sabes quién es el objetivo secreto!\n"
        "Escucha con atención lo que dicen, disimula para que no sospechen de ti "
        "e intenta adivinar de quién están hablando."
    ),
}
STRINGS["dm_caos_jugador_detective_desc"] = STRINGS["dm_caos_jugador_impostor_desc"]

STRINGS["dm_caos_jugador_crew_title"] = {
    "en": "✅ YOU ARE A CREWMATE",
    "es": "✅ ERES TRIPULANTE",
}
STRINGS["dm_caos_jugador_crew_desc"] = {
    "en": (
        "🎯 Secret target to describe: {target}\n\n"
        "Describe this person without saying their name directly!\n"
        "The impostor is among you and has no idea who everyone is describing.\n"
        "Find out who is pretending!"
    ),
    "es": (
        "🎯 Objetivo secreto a describir: {target}\n\n"
        "¡Describe a esta persona sin decir su nombre directamente!\n"
        "El impostor está entre ustedes y no tiene idea de a quién están describiendo.\n"
        "¡Descubran quién está fingiendo!"
    ),
}
STRINGS["caos_jugador_hint_avatar"] = {
    "en": "The target has a profile picture.",
    "es": "El objetivo tiene foto de perfil.",
}
STRINGS["caos_jugador_hint_name"] = {
    "en": "The target's name starts with '{target}'.",
    "es": "El nombre del objetivo empieza con '{target}'.",
}
STRINGS["caos_jugador_hint_join"] = {
    "en": "The target is a member of this server.",
    "es": "El objetivo es miembro de este servidor.",
}
STRINGS["dm_ebrios_title"] = {
    "en": "🍻 YOUR POKÉMON (Drunk Friends Mode)",
    "es": "🍻 TU POKÉMON (Modo Amigos Ebrios)",
}
STRINGS["dm_ebrios_desc"] = {
    "en": (
        "Type: **{types}**\n\n"
        "Describe your Pokémon without saying its name.\n"
        "Everyone has a DIFFERENT one — try to blend in!"
    ),
    "es": (
        "Tipo: **{types}**\n\n"
        "Describe tu Pokémon sin decir su nombre.\n"
        "¡Todos tienen uno DIFERENTE — intenta pasar desapercibido!"
    ),
}
STRINGS["dm_ebrios_footer"] = {
    "en": "The sprite is your clue · 🎨 Art: @xeechithecat.bsky.social",
    "es": "El sprite es tu pista · 🎨 Arte: @xeechithecat.bsky.social",
}

# ── Pantalla final nuevos modos ───────────────────────────────────────────────
STRINGS["final_ebrios_field"] = {
    "en": "🍻 Everyone's Pokémon",
    "es": "🍻 El Pokémon de cada uno",
}
STRINGS["final_caos_jugador_field"] = {
    "en": "👤 The Target Was",
    "es": "👤 El Objetivo Era",
}

# ── Votación: voto nulo ───────────────────────────────────────────────────────
STRINGS["vote_null_label"] = {
    "en": "⚪ Skip (Null Vote)",
    "es": "⚪ Pasar (Voto Nulo)",
}
STRINGS["vote_null_desc"] = {
    "en": "Don't accuse anyone this round",
    "es": "No acuses a nadie esta ronda",
}

# ── Toggle Ebrios (modificador del modo CAOS) ─────────────────────────────────
STRINGS["caos_ebrios_label"] = {
    "en": "🍻 Drunk Friends Mode",
    "es": "🍻 Modo Amigos Ebrios",
}
STRINGS["caos_ebrios_on"] = {
    "en": "✅ Active — everyone gets their own Pokémon",
    "es": "✅ Activo — cada uno tiene su propio Pokémon",
}
STRINGS["caos_ebrios_off"] = {
    "en": "⬜ Inactive (normal Chaos)",
    "es": "⬜ Inactivo (Caos normal)",
}
STRINGS["caos_ebrios_btn_on"] = {
    "en": "🍻 Drunk Friends: ON",
    "es": "🍻 Amigos Ebrios: ACTIVO",
}
STRINGS["caos_ebrios_btn_off"] = {
    "en": "🍻 Drunk Friends: OFF",
    "es": "🍻 Amigos Ebrios: INACTIVO",
}
STRINGS["caos_ebrios_only_caos"] = {
    "en": "This option is only available in Chaos mode.",
    "es": "Esta opción solo está disponible en el modo Caos.",
}

# ── Empate múltiple (CAOS y EXTENDIDO) ───────────────────────────────────────
STRINGS["results_tie_multi_title"] = {
    "en": "💥 TIE — MASS EJECTION!",
    "es": "💥 ¡EMPATE — EXPULSIÓN MASIVA!",
}
STRINGS["results_tie_multi_desc"] = {
    "en": "Everyone with the same votes is ejected: {names}",
    "es": "Todos los que empataron son expulsados: {names}",
}

# ── Votación CAOS_JUGADOR ─────────────────────────────────────────────────────
STRINGS["caos_jugador_vote_placeholder"] = {
    "en": "🕵️ Who do you think is the target?",
    "es": "🕵️ ¿Quién crees que es el objetivo?",
}
STRINGS["caos_jugador_only_detective"] = {
    "en": "Only the detective votes in this mode.",
    "es": "Solo el detective vota en este modo.",
}
STRINGS["caos_jugador_pass_desc"] = {
    "en": "Skip — don't accuse anyone",
    "es": "Pasar — no acuses a nadie",
}
STRINGS["caos_jugador_pass_title"] = {
    "en": "🏳️ Detective passed",
    "es": "🏳️ El detective pasó",
}
STRINGS["caos_jugador_pass_desc_result"] = {
    "en": "The detective chose not to guess. The target was {target}. **Crewmates win!**",
    "es": "El detective decidió no adivinar. El objetivo era {target}. **¡Los tripulantes ganan!**",
}
STRINGS["caos_jugador_correct_title"] = {
    "en": "🔍 DETECTIVE WINS!",
    "es": "🔍 ¡EL DETECTIVE GANÓ!",
}
STRINGS["caos_jugador_correct_desc"] = {
    "en": "{detective} correctly identified the target: {target}!\n\n**The detective wins!**",
    "es": "{detective} identificó correctamente al objetivo: {target}.\n\n**¡El detective gana!**",
}
STRINGS["caos_jugador_wrong_title"] = {
    "en": "❌ Wrong guess!",
    "es": "❌ ¡Adivinanza incorrecta!",
}
STRINGS["caos_jugador_wrong_desc"] = {
    "en": "The detective guessed {guessed}, but the target was actually {target}.\n\n**Crewmates win!**",
    "es": "El detective adivinó a {guessed}, pero el objetivo era {target}.\n\n**¡Los tripulantes ganan!**",
}
STRINGS["caos_jugador_admin_skip"] = {
    "en": "🔒 Round skipped by admin. No result.",
    "es": "🔒 Ronda saltada por el admin. Sin resultado.",
}

# ── /imphelp modos actualizados ───────────────────────────────────────────────
STRINGS["help_modes_value"] = {
    "en": (
        "**Classic** — Always 1 impostor.\n"
        "**Extended** — 1 impostor per 3 players.\n"
        "**Chaos** — Random amount, can be 0!\n"
        "**Chaos: Human Target** — A real player is the secret, not a Pokémon.\n"
        "*(Chaos + 💃 Teeter Dance — everyone gets a different Pokémon)*"
    ),
    "es": (
        "**Clásico** — Siempre 1 impostor.\n"
        "**Extendido** — 1 impostor por cada 3 jugadores.\n"
        "**Caos** — Cantidad aleatoria. ¡Puede haber 0!\n"
        "**Caos: Objetivo Humano** — Un jugador real es el secreto, no un Pokémon.\n"
        "*(Caos + 💃 Danza Caos — cada uno recibe un Pokémon diferente)*"
    ),
}

# ── Variante de CAOS (radio buttons, solo visible al admin en config) ────────
STRINGS["caos_variant_label"] = {
    "en": "🎲 Chaos Variant (random chance each round)",
    "es": "🎲 Variante de Caos (aleatoria cada ronda)",
}
STRINGS["caos_variant_normal"] = {
    "en": "Standard only (no special variants)",
    "es": "Solo estándar (sin variantes especiales)",
}
STRINGS["caos_variant_human"] = {
    "en": "🕵️ + Human Target (~40% chance)",
    "es": "🕵️ + Objetivo Humano (~40% chance)",
}
STRINGS["caos_variant_dance"] = {
    "en": "💃 + Teeter Dance (~40% chance)",
    "es": "💃 + Danza Caos (~40% chance)",
}
STRINGS["caos_variant_only_caos"] = {
    "en": "This option only applies when the mode is Chaos.",
    "es": "Esta opción solo aplica cuando el modo es Caos.",
}

# Botones (radio buttons) para elegir variante
STRINGS["caos_variant_normal_btn"] = {
    "en": "🎲 Standard only",
    "es": "🎲 Solo estándar",
}
STRINGS["caos_variant_human_btn"] = {
    "en": "🕵️ + Human Target",
    "es": "🕵️ + Objetivo Humano",
}
STRINGS["caos_variant_dance_btn"] = {
    "en": "💃 + Teeter Dance",
    "es": "💃 + Danza Caos",
}

# ── Cara a cara final (1 vs 1) ────────────────────────────────────────────────
STRINGS["results_faceoff_title"] = {
    "en": "🎭 FACE TO FACE — THE FINAL REVEAL",
    "es": "🎭 CARA A CARA — LA REVELACIÓN FINAL",
}
STRINGS["results_faceoff_desc"] = {
    "en": (
        "Only two remain... and the truth can no longer hide.\n\n"
        "{impostor} was the impostor all along.\n"
        "{crewmate} never suspected a thing... until now.\n\n"
        "**The impostor wins!**"
    ),
    "es": (
        "Solo quedan dos... y la verdad ya no puede esconderse más.\n\n"
        "{impostor} era el impostor desde el principio.\n"
        "{crewmate} nunca lo sospechó... hasta ahora.\n\n"
        "**¡El impostor gana!**"
    ),
}

# ── Pantalla final: victoria de impostores ────────────────────────────────────
STRINGS["final_title_impostors_win"] = {
    "en": "💀 GAME OVER — THE IMPOSTORS WON",
    "es": "💀 PARTIDA TERMINADA — LOS IMPOSTORES GANARON",
}
STRINGS["final_pokemon_hidden_field"] = {
    "en": "🔒 The Secret",
    "es": "🔒 El Secreto",
}
STRINGS["final_pokemon_hidden_value"] = {
    "en": "The impostors took the secret with them. It will never be revealed...",
    "es": "Los impostores se llevaron el secreto con ellos. Nunca será revelado...",
}
STRINGS["final_impostor_caught"] = {
    "en": "🔪 {name} *(caught)*",
    "es": "🔪 {name} *(descubierto)*",
}
STRINGS["final_impostor_escaped"] = {
    "en": "🏆 {name} *(escaped undetected)*",
    "es": "🏆 {name} *(escapó sin ser descubierto)*",
}

# ── Pista pública anti-estancamiento ──────────────────────────────────────────
STRINGS["public_hint_title"] = {
    "en": "📢 A clue echoes through the room...",
    "es": "📢 Una pista resuena por la sala...",
}
STRINGS["public_hint_desc"] = {
    "en": "Nobody has been voted out in a while. Everyone now knows: {hint}",
    "es": "Hace rato que nadie es expulsado. Ahora todos saben: {hint}",
}

# ── DM neutro para tripulantes de Objetivo Humano ────────────────────────────
# Tanto el objetivo como los tripulantes normales ven este mensaje.
# NO revela que hay un "detective" ni que alguien es el "objetivo".
# Solo ven la foto del jugador misterioso y una instrucción genérica.
STRINGS["dm_caos_jugador_crew_neutral"] = {
    "en": (
        "🎯 Secret target to describe: {target}\n\n"
        "Describe this person without saying their name directly.\n"
        "Someone among you has no idea who everyone is talking about!"
    ),
    "es": (
        "🎯 Objetivo secreto a describir: {target}\n\n"
        "Describe a esta persona sin decir su nombre directamente.\n"
        "¡Alguien entre ustedes no sabe de quién están hablando todos!"
    ),
}

# ── DM para el propio objetivo (Objetivo Humano) — no debe delatarlo ──────────
STRINGS["dm_caos_jugador_target_desc"] = {
    "en": (
        "The others are describing someone in the group, trying to confuse the detective.\n"
        "Just chat normally and try to figure out who the detective might be!"
    ),
    "es": (
        "Los demás están describiendo a alguien del grupo para confundir al detective.\n"
        "¡Solo participa normalmente e intenta descubrir quién podría ser el detective!"
    ),
}

# ── Concurrencia: votación ya cerrada por otra interacción ────────────────────
STRINGS["vote_already_closed"] = {
    "en": "This vote was already closed.",
    "es": "Esta votación ya fue cerrada.",
}

# ── Concurrencia: ronda ya iniciada por otro admin ────────────────────────────
STRINGS["round_already_started"] = {
    "en": "The round was already started by someone else.",
    "es": "La ronda ya fue iniciada por otra persona.",
}

# ── Recuperación tras reinicio del bot ────────────────────────────────────────
STRINGS["session_lost_after_restart"] = {
    "en": (
        "🔌 **I just restarted** and lost track of the game that was running in this channel.\n"
        "Sorry about that! Please use `/play-kyu` to start a new lobby."
    ),
    "es": (
        "🔌 **Me acabo de reiniciar** y perdí el rastro de la partida que estaba en este canal.\n"
        "¡Disculpen las molestias! Usen `/play-kyu` para abrir un nuevo lobby."
    ),
}

# ── Estadísticas y Perfil (/perfil) ──────────────────────────────────────────
STRINGS["profile_title"] = {
    "en": "👤 Trainer Profile — {name}",
    "es": "👤 Perfil de Entrenador — {name}",
}
STRINGS["profile_no_games"] = {
    "en": "This trainer hasn't played any PokeImpostor games yet!",
    "es": "¡Este entrenador todavía no ha jugado ninguna partida de PokeImpostor!",
}
STRINGS["profile_general_field"] = {
    "en": "📊 General Performance",
    "es": "📊 Rendimiento General",
}
STRINGS["profile_general_value"] = {
    "en": "• Games: **{total}**\n• Wins: **{wins}** ({winrate}%)\n• Losses: **{losses}**",
    "es": "• Partidas: **{total}**\n• Victorias: **{wins}** ({winrate}%)\n• Derrotas: **{losses}**",
}
STRINGS["profile_roles_field"] = {
    "en": "🎭 Performance by Role",
    "es": "🎭 Rendimiento por Rol",
}
STRINGS["profile_roles_value"] = {
    "en": "• 🔪 Impostor: **{imp_wins}/{imp_games}** ({imp_wr}% winrate)\n• 🔍 Crewmate: **{crew_wins}/{crew_games}** ({crew_wr}% winrate)",
    "es": "• 🔪 Impostor: **{imp_wins}/{imp_games}** ({imp_wr}% victorias)\n• 🔍 Tripulante: **{crew_wins}/{crew_games}** ({crew_wr}% victorias)",
}
STRINGS["profile_innocent_field"] = {
    "en": "😱 Wrongfully Expelled",
    "es": "😱 Inocente Expulsado",
}
STRINGS["profile_innocent_value"] = {
    "en": "{count} times voted out while innocent",
    "es": "{count} veces votado siendo inocente",
}
STRINGS["profile_pokemon_field"] = {
    "en": "🌟 Signature Pokémon",
    "es": "🌟 Pokémon Más Frecuente",
}
STRINGS["profile_pokemon_value"] = {
    "en": "**{name}**",
    "es": "**{name}**",
}

# ── Tabla de Clasificación (/ranking) ────────────────────────────────────────
STRINGS["ranking_title_general"] = {
    "en": "🏆 Server Leaderboard — Most Wins",
    "es": "🏆 Tabla de Clasificación — Más Victorias",
}
STRINGS["ranking_title_impostores"] = {
    "en": "🔪 Server Leaderboard — Deadliest Impostors",
    "es": "🔪 Tabla de Clasificación — Impostores Más Letales",
}
STRINGS["ranking_title_detectives"] = {
    "en": "🔍 Server Leaderboard — Best Crewmates",
    "es": "🔍 Tabla de Clasificación — Mejores Tripulantes",
}
STRINGS["ranking_empty"] = {
    "en": "No games recorded on this server yet! Start one with `/play-kyu`.",
    "es": "¡Aún no hay partidas registradas en este servidor! Inicien una con `/play-kyu`.",
}
STRINGS["ranking_entry"] = {
    "en": "{medal} **{name}** — **{wins}** wins ({winrate}% in {total} games)",
    "es": "{medal} **{name}** — **{wins}** victorias ({winrate}% en {total} partidas)",
}

# ── Estadísticas Globales del Servidor (/stats_partidas) ─────────────────────
STRINGS["server_stats_title"] = {
    "en": "📈 PokeImpostor — Server Analytics",
    "es": "📈 PokeImpostor — Analítica del Servidor",
}
STRINGS["server_stats_empty"] = {
    "en": "No game history available yet on this server. Play a game first!",
    "es": "Aún no hay historial de partidas en este servidor. ¡Jueguen una primera partida!",
}
STRINGS["server_stats_balance_field"] = {
    "en": "⚖️ Win Balance",
    "es": "⚖️ Balance de Victorias",
}
STRINGS["server_stats_balance_value"] = {
    "en": "• Total Games: **{total}**\n• 🔪 Impostor Wins: **{imp_wins}** ({imp_pct}%)\n• 🔍 Crewmate Wins: **{crew_wins}** ({crew_pct}%)\n• 🌀 No Impostor (Chaos): **{no_imp}**",
    "es": "• Total Partidas: **{total}**\n• 🔪 Victorias Impostor: **{imp_wins}** ({imp_pct}%)\n• 🔍 Victorias Tripulante: **{crew_wins}** ({crew_pct}%)\n• 🌀 Sin Impostores (Caos): **{no_imp}**",
}
STRINGS["server_stats_fav_mode"] = {
    "en": "🎲 Favorite Game Mode",
    "es": "🎲 Modo Favorito",
}
STRINGS["server_stats_deadliest_pk"] = {
    "en": "💀 Deadliest Pokémon",
    "es": "💀 Pokémon Más Letal",
}
STRINGS["server_stats_common_pk"] = {
    "en": "✨ Most Common Pokémon",
    "es": "✨ Pokémon Más Frecuente",
}

# ── Sistema de Licencias, Códigos y Monetización ─────────────────────────────
STRINGS["license_key_gen_title"] = {
    "en": "🔑 PokeImpostor — VIP License Generator",
    "es": "🔑 PokeImpostor — Generador de Licencias VIP",
}
STRINGS["license_key_modal_title"] = {
    "en": "🔐 Master Authorization",
    "es": "🔐 Autorización Maestra",
}
STRINGS["license_key_modal_pwd"] = {
    "en": "Master Password",
    "es": "Contraseña Maestra",
}
STRINGS["license_key_modal_type"] = {
    "en": "Type: mes / dias / permanente / cargas",
    "es": "Tipo: mes / dias / permanente / cargas",
}
STRINGS["license_key_modal_val"] = {
    "en": "Duration (e.g. 1 month, 30 days) or Charges",
    "es": "Duración (ej: 1 mes, 30 días) o Cargas",
}
STRINGS["license_auth_failed"] = {
    "en": "❌ Authorization failed: Incorrect master password.",
    "es": "❌ Autorización denegada: Contraseña maestra incorrecta.",
}
STRINGS["license_key_generated"] = {
    "en": "✨ **VIP License Key Generated:**\n`{key}`\n\n📌 **Type:** {tipo}\n⌛ **Details:** {details}\n\n*Deliver this key to the supporter to redeem via `/canjear {key}`.*",
    "es": "✨ **Clave de Licencia VIP Generada:**\n`{key}`\n\n📌 **Tipo:** {tipo}\n⌛ **Detalles:** {details}\n\n*Entrega esta clave al comprador/donador para canjear con `/canjear {key}`.*",
}
STRINGS["redeem_only_host"] = {
    "en": "❌ Only an Administrator or a member with the **{role}** role can redeem licenses for this server.",
    "es": "❌ Solo un Administrador o miembro con rol **{role}** puede canjear licencias para este servidor.",
}
STRINGS["redeem_not_found"] = {
    "en": "❌ The provided license key does not exist or is invalid.",
    "es": "❌ El código de licencia ingresado no existe o no es válido.",
}
STRINGS["redeem_already_used"] = {
    "en": "⚠️ This license key has already been redeemed previously.",
    "es": "⚠️ Este código de licencia ya ha sido canjeado anteriormente.",
}
STRINGS["redeem_success_title"] = {
    "en": "🎉 PokeImpostor Premium Activated!",
    "es": "🎉 ¡PokeImpostor Premium Activado!",
}
STRINGS["redeem_success_desc"] = {
    "en": "This server now has **PokeImpostor Premium** enabled!\n\n👑 **Tier:** {tipo}\n📅 **Status:** {details}",
    "es": "¡Este servidor ahora cuenta con **PokeImpostor Premium** activado!\n\n👑 **Membresía:** {tipo}\n📅 **Estado:** {details}",
}
STRINGS["license_status_title"] = {
    "en": "🛡️ Server License Status",
    "es": "🛡️ Estado de Licencia del Servidor",
}
STRINGS["license_status_premium"] = {
    "en": "🌟 **Status:** PREMIUM ACTIVE\n💎 **Tier:** {tipo}\n📝 **Details:** {details}",
    "es": "🌟 **Estado:** PREMIUM ACTIVO\n💎 **Membresía:** {tipo}\n📝 **Detalles:** {details}",
}
STRINGS["license_status_free"] = {
    "en": "🌱 **Status:** Free Base Edition\n\nTo unlock all game modes (Extended, Chaos, all generations, future Items/Trivia modes):\n1. 🗳️ Vote on Top.gg (1 vote = 5 unlocked matches!).\n2. ☕ Support on Ko-fi to get a permanent or monthly VIP key.\n3. 🤝 Official Beta Partner Server.",
    "es": "🌱 **Estado:** Edición Gratuita Base\n\nPara desbloquear todos los modos (Extendido, Caos, todas las generaciones, futuros modos Ítems/Trivia):\n1. 🗳️ Votar en Top.gg (¡1 voto = 5 partidas con todo desbloqueado!).\n2. ☕ Donar en Ko-fi para recibir una clave VIP mensual o permanente.\n3. 🤝 Servidor Beta Partner Oficial.",
}
STRINGS["partner_register_success"] = {
    "en": "👑 Server **{guild_id}** successfully registered as a permanent **Beta Partner**!",
    "es": "👑 ¡El servidor **{guild_id}** ha sido registrado con éxito como **Beta Partner** permanente!",
}

# ── Configuración de Rol Host (/impsetrole) ──────────────────────────────────
STRINGS["setrole_embed_title"] = {
    "en": "👑 PokeImpostor Host Role Setup",
    "es": "👑 Configuración del Rol Host de PokeImpostor",
}
STRINGS["setrole_admin_only"] = {
    "en": "⛔ Only server administrators can configure the PokeImpostor host role.",
    "es": "⛔ Solo los administradores del servidor pueden configurar el rol de PokeImpostor.",
}
STRINGS["setrole_success_existing"] = {
    "en": "✅ {role} is now configured as the official PokeImpostor host role for this server!",
    "es": "✅ ¡{role} ahora está configurado como el rol oficial de anfitrión de PokeImpostor en este servidor!",
}
STRINGS["setrole_success_created"] = {
    "en": "✨ Created and configured {role} as the official PokeImpostor host role!",
    "es": "✨ ¡Se creó y configuró {role} como el rol oficial de anfitrión de PokeImpostor!",
}
STRINGS["setrole_assigned_user"] = {
    "en": "👤 Successfully assigned {role} to {user}!",
    "es": "👤 ¡Se asignó exitosamente {role} a {user}!",
}
STRINGS["setrole_missing_perms"] = {
    "en": "❌ I don't have permission to manage roles. Please grant me the 'Manage Roles' permission and place my bot role above the target role.",
    "es": "❌ No tengo permisos para gestionar roles. Otórgame el permiso 'Gestionar Roles' y coloca el rol del bot por encima del rol objetivo.",
}
STRINGS["setrole_hierarchy_error"] = {
    "en": "⚠️ Cannot assign {role} to {user} because it is higher than my highest role in the server hierarchy.",
    "es": "⚠️ No puedo asignar {role} a {user} porque está más arriba que mi rol más alto en la jerarquía del servidor.",
}
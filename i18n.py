"""
i18n.py — Sistema de internacionalización para PokeImpostor
Idioma por defecto: inglés. Se puede cambiar por servidor con /implanguage.
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════════
#  REGISTRO DE IDIOMA POR SERVIDOR  { guild_id: "en" | "es" }
# ═══════════════════════════════════════════════════════════════════════════════

_idiomas: dict[int, str] = {}

def get_lang(guild_id: int) -> str:
    return _idiomas.get(guild_id, "en")

def set_lang(guild_id: int, lang: str) -> None:
    _idiomas[guild_id] = lang


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
        "en": "At least 3 players are needed to start.",
        "es": "Se necesitan al menos 3 jugadores para iniciar.",
    },
    "lobby_already_in": {
        "en": "You're already in the lobby.",
        "es": "Ya estás en el lobby.",
    },
    "lobby_not_in": {
        "en": "You're not in the lobby.",
        "es": "No estás en el lobby.",
    },
    "lobby_cancelled": {
        "en": "🛑 **Lobby cancelled by an administrator.**",
        "es": "🛑 **Lobby cancelado por el administrador.**",
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
    "hint_stat_high":    {"en": "Highest stat",        "es": "Estadística más alta"},
    "hint_stat_low":     {"en": "Lowest stat",         "es": "Estadística más baja"},
    "hint_egg":          {"en": "Egg Group",           "es": "Grupo Huevo"},
    "hint_type":         {"en": "Type",                "es": "Tipo"},
    "hint_habitat":      {"en": "Habitat",             "es": "Hábitat"},
    "hint_region":       {"en": "Origin Region",       "es": "Región de origen"},
    "hint_ability":      {"en": "Ability",             "es": "Habilidad"},

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
        "en": "Don't share this message. Good luck, traitor!",
        "es": "No reenvíes este mensaje. ¡Buena suerte, traidor!",
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
        "en": "Use /impver if you need to see it again during the game.",
        "es": "Usa /impver si necesitas volver a verlo durante la partida.",
    },

    # ── Pistas generadas ──────────────────────────────────────────────────────
    "hint_text_letter":   {"en": "Its name starts with the letter **{v}**.",         "es": "Su nombre empieza con la letra **{v}**."},
    "hint_text_stat_high":{"en": "Its highest stat is **{v}**.",                     "es": "Su estadística más alta es **{v}**."},
    "hint_text_stat_low": {"en": "Its lowest stat is **{v}**.",                      "es": "Su estadística más baja es **{v}**."},
    "hint_text_egg":      {"en": "It belongs to the **{v}** egg group(s).",          "es": "Pertenece al grupo huevo **{v}**."},
    "hint_text_type":     {"en": "Its type is **{v}**.",                             "es": "Es de tipo **{v}**."},
    "hint_text_habitat":  {"en": "Its primary habitat is **{v}**.",                  "es": "Su hábitat principal es **{v}**."},
    "hint_text_region":   {"en": "It first appeared in the **{v}**.",                "es": "Apareció por primera vez en la **{v}**."},
    "hint_text_ability":  {"en": "One of its abilities is **{v}**.",                 "es": "Una de sus habilidades es **{v}**."},

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
        "en": "The debate continues. Open voting when ready.",
        "es": "El debate continúa. Cuando estén listos, inicien la votación.",
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
        "en": "**{name} WAS THE IMPOSTOR.**\n\n🦊 **Zoroark has dropped its disguise.**\nThe crewmates win!",
        "es": "**{name} SÍ ERA IMPOSTOR.**\n\n🦊 **El Zoroark ha abandonado su disfraz.**\n¡Los tripulantes han ganado!",
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
        "en": "Round {n} completed.",
        "es": "Ronda {n} completada.",
    },

    # ── Sesión cerrada ────────────────────────────────────────────────────────
    "session_closed_title": {
        "en": "👋 Session closed",
        "es": "👋 Sesión cerrada",
    },
    "session_closed_desc": {
        "en": "Thanks for playing **PokeImpostor**.\nUse `/impregister` to open a new lobby.",
        "es": "Gracias por jugar **PokeImpostor**.\nUsen `/impregister` para abrir un nuevo lobby.",
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
        "en": "Use `/impregister` to open the room. Everyone presses **⚡ Join**.",
        "es": "Usa `/impregister` para abrir la sala. Todos presionan **⚡ Unirse**.",
    },
    "help_step2_name":  {"en": "2️⃣  Check your DM",  "es": "2️⃣  Revisar el DM"},
    "help_step2_value": {
        "en": (
            "**Crewmates** get the image and name of the secret Pokémon.\n"
            "**The Impostor** only gets a clue and must pretend to know it.\n"
            "If you closed the DM, use `/impver` to see it again."
        ),
        "es": (
            "**Tripulantes** reciben la imagen y nombre del Pokémon secreto.\n"
            "**El Impostor** recibe solo una pista y debe fingir que lo conoce.\n"
            "Si cerraste el DM, usa `/impver` para volver a verlo."
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
            "**Classic** — Always 1 impostor.\n"
            "**Extended** — 1 impostor per 3 players.\n"
            "**Chaos** — Random amount. Can be 0!"
        ),
        "es": (
            "**Clásico** — Siempre 1 impostor.\n"
            "**Extendido** — 1 impostor por cada 3 jugadores.\n"
            "**Caos** — Cantidad aleatoria. ¡Puede haber 0!"
        ),
    },
    "help_footer": {
        "en": "Good luck, trainer!",
        "es": "¡Buena suerte, entrenador!",
    },

    # ── /impregister ──────────────────────────────────────────────────────────
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
STRINGS["mode_amigos_ebrios"] = {
    "en": "🍻 Drunk Friends",
    "es": "🍻 Amigos Ebrios",
}
STRINGS["mode_amigos_ebrios_display"] = {
    "en": "🍻 Drunk Friends (no impostors)",
    "es": "🍻 Amigos Ebrios (sin impostores)",
}
STRINGS["mode_amigos_ebrios_desc"] = {
    "en": "No impostors — everyone has a DIFFERENT Pokémon. Can you tell them apart?",
    "es": "Sin impostores — todos tienen un Pokémon DIFERENTE. ¿Pueden distinguirlos?",
}

# ── DMs nuevos modos ──────────────────────────────────────────────────────────
STRINGS["dm_caos_jugador_detective_title"] = {
    "en": "🕵️ YOU ARE THE DETECTIVE",
    "es": "🕵️ ERES EL DETECTIVE",
}
STRINGS["dm_caos_jugador_detective_desc"] = {
    "en": "The other players are describing a real member of the group.\nYour clue: {hint}\n\nListen carefully and guess who they're talking about!",
    "es": "Los demás jugadores están describiendo a un miembro real del grupo.\nTu pista: {hint}\n\n¡Escucha con atención e intenta adivinar de quién hablan!",
}
STRINGS["dm_caos_jugador_crew_title"] = {
    "en": "✅ YOU ARE A CREWMATE",
    "es": "✅ ERES TRIPULANTE",
}
STRINGS["dm_caos_jugador_crew_desc"] = {
    "en": "Describe {target} without saying their name!\nThe detective is trying to figure out who you're talking about.",
    "es": "¡Describe a {target} sin decir su nombre!\nEl detective intenta adivinar de quién hablan.",
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
    "en": "Your Pokémon is: **{name}**\nType: {types}\n\nDescribe it without saying the name. Everyone has a DIFFERENT one!",
    "es": "Tu Pokémon es: **{name}**\nTipo: {types}\n\n¡Descríbelo sin decir el nombre. Todos tienen uno DIFERENTE!",
}
STRINGS["dm_ebrios_footer"] = {
    "en": "Try to confuse the others — they don't know yours!",
    "es": "¡Intenta confundir a los demás — ellos no saben cuál es el tuyo!",
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
        "*(Chaos + 🍻 Drunk Friends — everyone gets a different Pokémon)*"
    ),
    "es": (
        "**Clásico** — Siempre 1 impostor.\n"
        "**Extendido** — 1 impostor por cada 3 jugadores.\n"
        "**Caos** — Cantidad aleatoria. ¡Puede haber 0!\n"
        "**Caos: Objetivo Humano** — Un jugador real es el secreto, no un Pokémon.\n"
        "*(Caos + 🍻 Amigos Ebrios — cada uno recibe un Pokémon diferente)*"
    ),
}

# ── Variante de CAOS (radio buttons, solo visible al admin en config) ────────
STRINGS["caos_variant_label"] = {
    "en": "🎲 Chaos Variant",
    "es": "🎲 Variante de Caos",
}
STRINGS["caos_variant_normal"] = {
    "en": "Standard (random impostors 0-N)",
    "es": "Estándar (impostores aleatorios 0-N)",
}
STRINGS["caos_variant_human"] = {
    "en": "🕵️ Human Target",
    "es": "🕵️ Objetivo Humano",
}
STRINGS["caos_variant_dance"] = {
    "en": "💃 Chaos Dance",
    "es": "💃 Danza Caos",
}
STRINGS["caos_variant_only_caos"] = {
    "en": "This option only applies when the mode is Chaos.",
    "es": "Esta opción solo aplica cuando el modo es Caos.",
}

# Botones (radio buttons) para elegir variante
STRINGS["caos_variant_normal_btn"] = {
    "en": "🎲 Standard",
    "es": "🎲 Estándar",
}
STRINGS["caos_variant_human_btn"] = {
    "en": "🕵️ Human Target",
    "es": "🕵️ Objetivo Humano",
}
STRINGS["caos_variant_dance_btn"] = {
    "en": "💃 Chaos Dance",
    "es": "💃 Danza Caos",
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
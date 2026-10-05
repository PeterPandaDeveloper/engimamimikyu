"""
simulacion_realista.py — Simulación realista por consola de PokeImpostor con 8 jugadores.

Ejecuta 3 partidas completas utilizando el motor de juego real y PokéAPI:
  1. Modo CLÁSICO (1 Impostor)
  2. Modo EXTENDIDO (2 Impostores)
  3. Modo CAOS (Reglas impredecibles)

Al finalizar, consulta la base de datos DuckDB real y presenta:
  - Estadísticas globales del servidor
  - Tabla de clasificación (Leaderboard)
  - Perfiles individuales de los jugadores
"""
from __future__ import annotations

import asyncio
import random
import os
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_juego import Partida, ModoJuego, CaosVariante, Ventaja, ConfigPartida
from api import cerrar_session
from db import (
    init_db,
    close_db,
    guardar_partida_async,
    obtener_stats_servidor_async,
    obtener_ranking_async,
    obtener_perfil_jugador_async,
)


class MockAvatar:
    def __init__(self, url: str):
        self.url = url


class MockPermissions:
    def __init__(self, administrator: bool = False):
        self.administrator = administrator


class MockRole:
    def __init__(self, name: str):
        self.name = name


class MockMember:
    def __init__(self, user_id: int, name: str, display_name: str, is_admin: bool = False, roles: list = None):
        self.id = user_id
        self.name = name
        self.display_name = display_name
        self.mention = f"<@{user_id}>"
        self.display_avatar = MockAvatar(f"https://cdn.discordapp.com/avatars/{user_id}/avatar.png")
        self.guild_permissions = MockPermissions(administrator=is_admin)
        self.roles = roles or []
        self.dm_recibido: Any = None

    async def send(self, content: str = None, embed: Any = None):
        self.dm_recibido = embed or content
        return self.dm_recibido

    def __repr__(self):
        return f"{self.display_name} (ID:{self.id})"


class MockGuild:
    def __init__(self, guild_id: int, name: str):
        self.id = guild_id
        self.name = name


class MockChannel:
    def __init__(self, channel_id: int, guild: MockGuild):
        self.id = channel_id
        self.guild = guild
        self.mensajes: list[str] = []

    async def send(self, content: str = None, embed: Any = None, view: Any = None):
        msg = f"[Canal #{self.id}] {content or ''}"
        if embed:
            msg += f" [Embed: {getattr(embed, 'title', '')}]"
        self.mensajes.append(msg)
        return msg


SEP_LINE = "━" * 68
SUB_SEP  = "─" * 68


def print_banner(titulo: str):
    print(f"\n{SEP_LINE}")
    print(f"  {titulo.upper()}")
    print(f"{SEP_LINE}")


def print_subbanner(titulo: str):
    print(f"\n  ┌{SUB_SEP}┐")
    print(f"  │ {titulo.center(66)} │")
    print(f"  └{SUB_SEP}┘")


async def main():
    print_banner("Iniciando Simulador de PokeImpostor con 8 Jugadores")
    await init_db()

    guild = MockGuild(guild_id=777888999, name="Liga Pokémon Indigo")
    canal = MockChannel(channel_id=987654321, guild=guild)
    partidas_activas = {}

    # Limpiar datos previos de simulación para mantener estadísticas limpias
    from db import _DB_LOCK, _get_connection
    with _DB_LOCK:
        con = _get_connection()
        con.execute("DELETE FROM participaciones WHERE partida_id IN (SELECT id FROM partidas WHERE guild_id = ?)", [guild.id])
        con.execute("DELETE FROM partidas WHERE guild_id = ?", [guild.id])

    jugadores = [
        MockMember(1001, "ash_k",     "Ash Ketchum",      is_admin=True),
        MockMember(1002, "misty_w",   "Misty",            is_admin=False),
        MockMember(1003, "brock_h",   "Brock",            is_admin=False),
        MockMember(1004, "gary_o",    "Gary Oak",         is_admin=False),
        MockMember(1005, "serena_y",  "Serena",           is_admin=False),
        MockMember(1006, "red_c",     "Red",              is_admin=False),
        MockMember(1007, "dawn_b",    "Dawn",             is_admin=False),
        MockMember(1008, "cynthia_s", "Cynthia",          is_admin=False),
    ]

    print("Participantes registrados en el lobby (8 entrenadores):")
    for i, j in enumerate(jugadores, 1):
        rol_txt = "[ADMIN]" if j.guild_permissions.administrator else ""
        print(f"  {i}. {j.display_name:<18} (ID: {j.id}) {rol_txt}")

    # ─────────────────────────────────────────────────────────────────────────
    #  PARTIDA 1: MODO CLÁSICO
    # ─────────────────────────────────────────────────────────────────────────
    print_banner("Partida 1: MODO CLÁSICO (1 Impostor Secreto)")
    p1 = Partida(canal=canal, partidas_activas=partidas_activas)
    p1.config.modo_juego = ModoJuego.CLASICO
    p1.config.ventaja = Ventaja.ALEATORIO
    p1.jugadores = jugadores.copy()

    exito1 = await p1.arrancar_ronda()
    if not exito1 or not p1.datos_pokemon:
        print("❌ Error al arrancar partida 1 (PokéAPI).")
        return

    pk1 = p1.datos_pokemon
    impostor1 = p1.impostores[0]
    pista1 = p1.pistas_impostores[impostor1.id]

    print(f"📡 Pokémon secreto obtenido de PokéAPI: #{pk1['id']} {pk1['nombre'].upper()}")
    print(f"   • Tipos: {', '.join(pk1['tipos'])}")
    print(f"   • Hábitat: {pk1.get('habitat', 'Desconocido')}")
    print(f"   • Habilidades: {', '.join(pk1.get('habilidades', []))}")
    print(f"   • Stat Destacada: {pk1.get('stat_mayor', 'N/A')} ({pk1['stats'].get(pk1.get('stat_mayor',''), '')})")
    print(f"   • Pokédex: \"{pk1.get('pokedex_entry', '')[:90]}...\"")
    print(f"\n🎭 Distribución de Roles:")
    print(f"   🔪 Impostor: {impostor1.display_name}")
    print(f"      Pista privada entregada: \"{pista1}\"")
    print(f"   🔍 Tripulantes ({len(p1.jugadores) - 1}): {', '.join(j.display_name for j in p1.jugadores if j != impostor1)}")

    print_subbanner("Ronda 1 — Debate y Primera Votación")
    print("💬 Los entrenadores debaten con pistas sutiles...")
    tripulantes1 = [j for j in p1.jugadores if j != impostor1]
    hablante_t1 = tripulantes1[0]
    hablante_t2 = tripulantes1[1]

    print(f"  • {hablante_t1.display_name}: \"Su tipo principal coincide con mi estrategia favorita.\"")
    print(f"  • {hablante_t2.display_name}: \"Tiene estadísticas interesantes, su hábitat tiene sentido.\"")
    print(f"  • {impostor1.display_name} (Impostor): \"Totalmente de acuerdo, y además coincide con la pista que conozco.\"")
    
    # En ronda 1 se vota por error a un inocente
    expulsado_r1 = tripulantes1[2]
    print(f"  • {expulsado_r1.display_name}: \"¡Esa respuesta de {impostor1.display_name} sonó sospechosa!\"")

    print("\n🗳️ Votación Ronda 1:")
    urnas_r1 = {
        expulsado_r1.display_name: 4,
        impostor1.display_name: 3,
        hablante_t1.display_name: 1,
    }
    for sospechoso, cant in urnas_r1.items():
        print(f"  `{'█' * cant:<8}` {sospechoso}: {cant} votos")

    p1.jugadores.remove(expulsado_r1)
    print(f"\n⚠️ Resultado R1: ¡{expulsado_r1.display_name} fue expulsado con 4 votos!")
    print(f"   ❌ Revelación: ¡{expulsado_r1.display_name} ERA INOCENTE! El impostor sigue libre.")

    print_subbanner("Ronda 2 — Segunda Votación y Resolución")
    p1.ronda = 2
    print(f"👥 Jugadores restantes ({len(p1.jugadores)}): {', '.join(j.display_name for j in p1.jugadores)}")
    hablante_t2 = next(j for j in p1.jugadores if j != impostor1 and j != hablante_t1)
    print("💬 Debate Ronda 2:")
    print(f"  • {hablante_t1.display_name}: \"{expulsado_r1.display_name} no era el traidor. Las sospechas apuntan a {impostor1.display_name}.\"")
    print(f"  • {hablante_t2.display_name}: \"Las pistas no coinciden con lo que dijo {impostor1.display_name}. Mi voto es claro.\"")

    rival = "Gary Oak" if impostor1.display_name != "Gary Oak" else "Ash Ketchum"
    if rival not in [j.display_name for j in p1.jugadores]:
        rival = [j.display_name for j in p1.jugadores if j != impostor1][0]

    print("\n🗳️ Votación Ronda 2:")
    urnas_r2 = {
        impostor1.display_name: 5,
        rival: 2,
    }
    for sospechoso, cant in urnas_r2.items():
        print(f"  `{'█' * cant:<8}` {sospechoso}: {cant} votos")

    p1.jugadores.remove(impostor1)
    p1.impostores.remove(impostor1)
    print(f"\n🎉 Resultado R2: ¡{impostor1.display_name} ha sido expulsado con 5 votos!")
    print(f"   ✅ Revelación: ¡{impostor1.display_name} ERA EL IMPOSTOR!")
    print(f"   🏆 ¡VICTORIA DE LOS TRIPULANTES! (Pokémon secreto: {pk1['nombre']})")

    victoria_impostores_p1 = False
    jugadores_data_p1 = []
    for j in p1.jugadores_iniciales:
        es_imp = (j.id == impostor1.id)
        fue_expulsado = (j.id in (expulsado_r1.id, impostor1.id))
        jugadores_data_p1.append({
            "user_id": j.id,
            "user_name": j.display_name,
            "rol": "impostor" if es_imp else "tripulante",
            "gano": not victoria_impostores_p1 if not es_imp else victoria_impostores_p1,
            "expulsado": fue_expulsado,
        })

    pid_1 = await guardar_partida_async(
        guild_id=guild.id,
        canal_id=canal.id,
        modo=ModoJuego.CLASICO.value,
        variante=None,
        rondas=p1.ronda,
        pokemon_id=pk1["id"],
        pokemon_nombre=pk1["nombre"],
        pokemon_tipos=" / ".join(pk1["tipos"]),
        victoria_impostores=victoria_impostores_p1,
        caos_sin_impostores=False,
        jugadores_data=jugadores_data_p1,
    )
    print(f"💾 Partida 1 guardada en DuckDB con ID: {pid_1}")

    # ─────────────────────────────────────────────────────────────────────────
    #  PARTIDA 2: MODO EXTENDIDO (2 Impostores)
    # ─────────────────────────────────────────────────────────────────────────
    print_banner("Partida 2: MODO EXTENDIDO (2 Impostores Cómplices)")
    p2 = Partida(canal=canal, partidas_activas=partidas_activas)
    p2.config.modo_juego = ModoJuego.EXTENDIDO
    p2.config.ventaja = Ventaja.TIPO
    p2.jugadores = jugadores.copy()

    exito2 = await p2.arrancar_ronda()
    if not exito2 or not p2.datos_pokemon:
        print("❌ Error al arrancar partida 2.")
        return

    pk2 = p2.datos_pokemon
    impostores2 = p2.impostores.copy()
    print(f"📡 Pokémon secreto obtenido de PokéAPI: #{pk2['id']} {pk2['nombre'].upper()}")
    print(f"   • Tipos: {', '.join(pk2['tipos'])}")
    print(f"   • Hábitat: {pk2.get('habitat', 'Desconocido')}")
    print(f"\n🎭 Distribución de Roles (8 jugadores -> {len(impostores2)} impostores):")
    for imp in impostores2:
        complices = [x.display_name for x in impostores2 if x != imp]
        print(f"   🔪 Impostor: {imp.display_name} (Sabe que su cómplice es: {', '.join(complices)})")
    print(f"   🔍 Tripulantes ({len(p2.jugadores) - len(impostores2)}): {', '.join(j.display_name for j in p2.jugadores if j not in impostores2)}")

    print_subbanner("Ronda 1 — Emboscada de los Impostores")
    inocentes_p2 = [j for j in p2.jugadores if j not in impostores2]
    expulsado_p2_r1 = inocentes_p2[0]
    p2.jugadores.remove(expulsado_p2_r1)
    print(f"💬 Los 2 impostores coordinan votos en secreto para incriminar a {expulsado_p2_r1.display_name}...")
    print(f"⚠️ Votación R1: ¡{expulsado_p2_r1.display_name} fue expulsado/a!")
    print(f"   ❌ {expulsado_p2_r1.display_name} era INOCENTE. Quedan 2 impostores ocultos.")

    print_subbanner("Ronda 2 — Caída del Primer Impostor")
    p2.ronda = 2
    imp_caido = impostores2[0]
    imp_sobreviviente = impostores2[1]
    p2.jugadores.remove(imp_caido)
    p2.impostores.remove(imp_caido)
    print(f"⚠️ Votación R2: ¡El grupo descubre y expulsa a {imp_caido.display_name}!")
    print(f"   ✅ ¡{imp_caido.display_name} ERA UN IMPOSTOR! Queda 1 impostor activo: {imp_sobreviviente.display_name}.")

    print_subbanner("Ronda 3 — Enfrentamiento Decisivo")
    p2.ronda = 3
    expulsado_p2_r3 = inocentes_p2[1]
    p2.jugadores.remove(expulsado_p2_r3)
    print(f"⚠️ Votación R3: ¡Expulsan a {expulsado_p2_r3.display_name} (Inocente)!")

    p2.ronda = 4
    expulsado_p2_r4 = inocentes_p2[2]
    p2.jugadores.remove(expulsado_p2_r4)
    print(f"⚠️ Votación R4: ¡Expulsan a {expulsado_p2_r4.display_name} (Inocente)!")

    print_subbanner("Ronda 5 y 6 — El Impostor Oculto Remonta")
    p2.ronda = 5
    expulsado_p2_r5 = inocentes_p2[3]
    p2.jugadores.remove(expulsado_p2_r5)
    print(f"⚠️ Votación R5: ¡Expulsan a {expulsado_p2_r5.display_name} (Inocente)!")

    p2.ronda = 6
    expulsado_p2_r6 = inocentes_p2[4]
    p2.jugadores.remove(expulsado_p2_r6)
    print(f"⚠️ Votación R6: ¡Expulsan a {expulsado_p2_r6.display_name} (Inocente)!")

    tripulantes_vivos2 = len(p2.jugadores) - len(p2.impostores)
    print(f"\n⚔️ Estado del enfrentamiento: {len(p2.impostores)} Impostor vs {tripulantes_vivos2} Tripulante vivo ({inocentes_p2[5].display_name}).")
    if len(p2.impostores) >= tripulantes_vivos2:
        print(f"💀 ¡PARIDAD ALCANZADA! El impostor restante ({imp_sobreviviente.display_name}) domina la partida.")
        print(f"🏆 ¡VICTORIA DE LOS IMPOSTORES!")
        victoria_impostores_p2 = True
    else:
        victoria_impostores_p2 = False

    jugadores_data_p2 = []
    expulsados_p2_ids = {
        expulsado_p2_r1.id, imp_caido.id, expulsado_p2_r3.id,
        expulsado_p2_r4.id, expulsado_p2_r5.id, expulsado_p2_r6.id
    }
    impostores2_ids = {x.id for x in impostores2}
    for j in p2.jugadores_iniciales:
        es_imp = j.id in impostores2_ids
        fue_exp = j.id in expulsados_p2_ids
        jugadores_data_p2.append({
            "user_id": j.id,
            "user_name": j.display_name,
            "rol": "impostor" if es_imp else "tripulante",
            "gano": victoria_impostores_p2 if es_imp else not victoria_impostores_p2,
            "expulsado": fue_exp,
        })

    pid_2 = await guardar_partida_async(
        guild_id=guild.id,
        canal_id=canal.id,
        modo=ModoJuego.EXTENDIDO.value,
        variante=None,
        rondas=p2.ronda,
        pokemon_id=pk2["id"],
        pokemon_nombre=pk2["nombre"],
        pokemon_tipos=" / ".join(pk2["tipos"]),
        victoria_impostores=victoria_impostores_p2,
        caos_sin_impostores=False,
        jugadores_data=jugadores_data_p2,
    )
    print(f"💾 Partida 2 guardada en DuckDB con ID: {pid_2}")

    # ─────────────────────────────────────────────────────────────────────────
    #  PARTIDA 3: MODO CAOS
    # ─────────────────────────────────────────────────────────────────────────
    print_banner("Partida 3: MODO CAOS (Incertidumbre Total)")
    p3 = Partida(canal=canal, partidas_activas=partidas_activas)
    p3.config.modo_juego = ModoJuego.CAOS
    p3.config.caos_variante = CaosVariante.OBJETIVO_HUMANO
    p3.jugadores = jugadores.copy()

    exito3 = await p3.arrancar_ronda()
    if not exito3:
        print("❌ Error al arrancar partida 3.")
        return

    print(f"🌀 Variante de Caos sorteada: {p3._variante_ronda.value.upper()}")
    if p3.objetivo_humano:
        print(f"   🎯 Jugador Objetivo Secreto: {p3.objetivo_humano.display_name}")
        detective = p3.impostores[0]
        print(f"   🕵️ Detective Encubierto: {detective.display_name}")
        print(f"      Pista del Detective: \"{p3.pistas_impostores.get(detective.id, '')}\"")
        print(f"   👥 Tripulantes regulares: {', '.join(j.display_name for j in p3.jugadores if j not in (detective, p3.objetivo_humano))}")

        print_subbanner("Ronda 1 — El Detective Intenta Descubrir al Humano")
        print("💬 Los tripulantes describen la personalidad y avatar del objetivo sin decir su nombre...")
        hablantes = [j for j in p3.jugadores if j not in (detective, p3.objetivo_humano)]
        print(f"  • {hablantes[0].display_name}: \"Tiene un estilo muy competitivo y siempre analiza a sus rivales.\"")
        print(f"  • {hablantes[1].display_name}: \"Su avatar refleja su experiencia en los torneos oficiales.\"")
        print(f"  • {detective.display_name} (Detective): \"¡Con esas pistas ya lo tengo claro!\"")

        print(f"\n🗳️ Decisión del Detective ({detective.display_name}):")
        print(f"   El detective acusa formalmente a: **{p3.objetivo_humano.display_name}**")
        print(f"   🎉 ¡ACIERTO! El objetivo era exactamente {p3.objetivo_humano.display_name}.")
        print(f"   🏆 ¡VICTORIA DEL DETECTIVE ({detective.display_name})!")
        victoria_impostores_p3 = True
    elif p3.caos_sin_impostores:
        pk3 = p3.datos_pokemon
        print(f"   🌀 ¡EL DADO DEL CAOS CAYÓ EN 0! No hay impostores en esta ronda.")
        print(f"   Pokémon secreto: #{pk3['id']} {pk3['nombre'].upper()}")
        print_subbanner("Ronda 1 — La Paranoia del Caos")
        print("💬 Todos tienen el Pokémon real, pero desconfían unos de otros creyendo que alguien miente...")
        print(f"  • Ash: \"Dice que vive en montañas... ¿o estás inventando?\"")
        print(f"  • Gary Oak: \"¡Todos estamos diciendo la verdad, no hay impostor!\"")
        print("\n🗳️ Votación: Nadie es expulsado con mayoría.")
        print("🎉 ¡TODOS LOS ENTRENADORES SON INOCENTES! Victoria colectiva.")
        victoria_impostores_p3 = False
    else:
        pk3 = p3.datos_pokemon
        print(f"   Pokémon secreto: #{pk3['id']} {pk3['nombre'].upper()}")
        print(f"   Impostores sorteados ({len(p3.impostores)}): {', '.join(x.display_name for x in p3.impostores)}")
        print_subbanner("Ronda 1 — Caos Desatado")
        print("💬 Los múltiples impostores desatan confusión con pistas falsas...")
        print("🗳️ Votación: El grupo descubre y expulsa a uno de los impostores.")
        exp_imp = p3.impostores[0]
        p3.jugadores.remove(exp_imp)
        p3.impostores.remove(exp_imp)
        print(f"🎉 ¡{exp_imp.display_name} ERA IMPOSTOR!")
        victoria_impostores_p3 = (len(p3.impostores) > 0)
        print(f"🏆 Victoria: {'Impostores' if victoria_impostores_p3 else 'Tripulantes'}")

    jugadores_data_p3 = []
    for j in p3.jugadores_iniciales:
        es_imp = j in p3.impostores_iniciales
        es_obj = (j == p3.objetivo_humano)
        rol = "impostor" if es_imp else ("objetivo" if es_obj else "tripulante")
        gano = victoria_impostores_p3 if es_imp else not victoria_impostores_p3
        jugadores_data_p3.append({
            "user_id": j.id,
            "user_name": j.display_name,
            "rol": rol,
            "gano": gano,
            "expulsado": (j not in p3.jugadores),
        })

    pk_id3 = p3.datos_pokemon.get("id") if p3.datos_pokemon else None
    pk_nom3 = p3.datos_pokemon.get("nombre") if p3.datos_pokemon else "Objetivo Humano"
    pk_tip3 = " / ".join(p3.datos_pokemon.get("tipos", [])) if p3.datos_pokemon else "Humano"

    pid_3 = await guardar_partida_async(
        guild_id=guild.id,
        canal_id=canal.id,
        modo=ModoJuego.CAOS.value,
        variante=p3._variante_ronda.value,
        rondas=p3.ronda,
        pokemon_id=pk_id3,
        pokemon_nombre=pk_nom3,
        pokemon_tipos=pk_tip3,
        victoria_impostores=victoria_impostores_p3,
        caos_sin_impostores=p3.caos_sin_impostores,
        jugadores_data=jugadores_data_p3,
    )
    print(f"💾 Partida 3 guardada en DuckDB con ID: {pid_3}")

    # ─────────────────────────────────────────────────────────────────────────
    #  CONSULTAS ANALÍTICAS DIRECTAMENTE DESDE DUCKDB
    # ─────────────────────────────────────────────────────────────────────────
    print_banner("Consultas Analíticas desde DuckDB (Persistencia Real)")

    stats_servidor = await obtener_stats_servidor_async(guild.id)
    print("\n📊 1. MÉTRICAS GLOBALES DEL SERVIDOR (/stats_partidas):")
    if stats_servidor:
        print(f"   • Total de partidas jugadas:  {stats_servidor['total_partidas']}")
        print(f"   • Victorias Tripulantes:     {stats_servidor['vic_tripulantes']} ({stats_servidor['pct_tripulantes']}%)")
        print(f"   • Victorias Impostores:      {stats_servidor['vic_impostores']} ({stats_servidor['pct_impostores']}%)")
        print(f"   • Partidas sin Impostor:     {stats_servidor['sin_impostor']}")
        print(f"   • Modo de Juego Favorito:    {stats_servidor['modo_favorito']}")
        print(f"   • Pokémon más Letal:         {stats_servidor['pokemon_letal']}")
        print(f"   • Pokémon más Frecuente:     {stats_servidor['pokemon_comun']}")

    ranking_gen = await obtener_ranking_async(guild.id, "general")
    print("\n🏆 2. TABLA DE CLASIFICACIÓN GENERAL (/ranking general):")
    print(f"   {'Pos':<4} {'Entrenador':<18} {'Victorias':<10} {'Partidas':<10} {'Winrate':<10}")
    print(f"   {'-'*4} {'-'*18} {'-'*10} {'-'*10} {'-'*10}")
    for idx, r in enumerate(ranking_gen, 1):
        medalla = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"{idx}."))
        print(f"   {medalla:<4} {r['user_name']:<18} {r['victorias']:<10} {r['total']:<10} {r['winrate']}%")

    ranking_imp = await obtener_ranking_async(guild.id, "impostores")
    print("\n🔪 3. RANKING DE IMPOSTORES MÁS LETALES (/ranking impostores):")
    print(f"   {'Pos':<4} {'Entrenador':<18} {'Vic. Impostor':<15} {'Total Impostor':<15} {'Winrate Imp.':<10}")
    print(f"   {'-'*4} {'-'*18} {'-'*15} {'-'*15} {'-'*10}")
    for idx, r in enumerate(ranking_imp, 1):
        medalla = "💀" if idx == 1 else f"{idx}."
        print(f"   {medalla:<4} {r['user_name']:<18} {r['victorias']:<15} {r['total']:<15} {r['winrate']}%")

    top_player = ranking_gen[0] if ranking_gen else None
    if top_player:
        perfil = await obtener_perfil_jugador_async(guild.id, top_player["user_id"])
        print(f"\n👤 4. PERFIL DETALLADO DE {perfil['nombre'].upper()} (/perfil):")
        print(f"   • Total Partidas:           {perfil['total_partidas']}")
        print(f"   • Balance Global:           {perfil['victorias']}V - {perfil['derrotas']}D ({perfil['winrate_gral']}% Winrate)")
        print(f"   • Como Impostor:            {perfil['victorias_impostor']}/{perfil['partidas_impostor']} ({perfil['winrate_impostor']}% Winrate)")
        print(f"   • Como Tripulante:          {perfil['victorias_tripulante']}/{perfil['partidas_tripulante']} ({perfil['winrate_tripulante']}% Winrate)")
        print(f"   • Inocente Expulsado:       {perfil['expulsado_inocente']} veces")
        if perfil.get('pokemon_frecuente'):
            print(f"   • Pokémon Más Frecuente:    {perfil['pokemon_frecuente']}")

    await cerrar_session()
    await close_db()
    print_banner("Simulación Completada con Éxito — Datos 100% Reales y Persistidos")


if __name__ == "__main__":
    asyncio.run(main())

"""
db.py — Capa de persistencia analítica con DuckDB para PokeImpostor.

Almacena:
1. Configuración de servidores (idioma) reemplazando la dependencia frágil de JSON.
2. Historial completo de partidas (modo, variante, rondas, Pokémon, ganador).
3. Participaciones individuales (roles, expulsiones, victorias) para métricas y rankings.

Todas las consultas públicas son asíncronas y se despachan en hilos separados
(asyncio.to_thread) protegidas con un Lock para no bloquear el bucle de eventos
de discord.py y asegurar concurrencia sin condiciones de carrera.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any

import duckdb

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_DB_PATH = os.path.join(_DATA_DIR, "pokeimpostor.duckdb")
_LEGACY_LANG_FILE = os.path.join(_DATA_DIR, "idiomas.json")

# Lock de hilo para sincronizar escrituras y lecturas seguras en DuckDB
_DB_LOCK = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


def _init_schema_sync(con: duckdb.DuckDBPyConnection) -> None:
    # 1. Configuración de servidor (idiomas y rol host)
    con.execute("""
        CREATE TABLE IF NOT EXISTS servidores_config (
            guild_id BIGINT PRIMARY KEY,
            idioma VARCHAR NOT NULL DEFAULT 'en',
            rol_host_id BIGINT,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info('servidores_config')").fetchall()]
        if "rol_host_id" not in cols:
            con.execute("ALTER TABLE servidores_config ADD COLUMN rol_host_id BIGINT;")
    except Exception:
        pass

    # 2. Historial de partidas
    con.execute("""
        CREATE TABLE IF NOT EXISTS partidas (
            id VARCHAR PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            canal_id BIGINT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modo VARCHAR NOT NULL,
            variante VARCHAR,
            rondas INTEGER NOT NULL,
            pokemon_id INTEGER,
            pokemon_nombre VARCHAR,
            pokemon_tipos VARCHAR,
            victoria_impostores BOOLEAN NOT NULL,
            caos_sin_impostores BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)

    # 3. Participación de jugadores en cada partida
    con.execute("""
        CREATE TABLE IF NOT EXISTS participaciones (
            partida_id VARCHAR NOT NULL,
            user_id BIGINT NOT NULL,
            user_name VARCHAR NOT NULL,
            rol VARCHAR NOT NULL,
            gano BOOLEAN NOT NULL,
            expulsado BOOLEAN NOT NULL,
            PRIMARY KEY (partida_id, user_id)
        );
    """)

    # 4. Sistema de Licencias y Códigos VIP
    con.execute("""
        CREATE TABLE IF NOT EXISTS licencias (
            codigo VARCHAR PRIMARY KEY,
            tipo VARCHAR NOT NULL,
            duracion_dias INTEGER DEFAULT 0,
            cargas INTEGER DEFAULT 0,
            usada BOOLEAN DEFAULT FALSE,
            creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            canjeada_por_guild BIGINT,
            canjeada_por_user BIGINT,
            canjeada_en TIMESTAMP
        );
    """)

    # 5. Estado Premium y Licencias por Servidor
    con.execute("""
        CREATE TABLE IF NOT EXISTS servidores_licencia (
            guild_id BIGINT PRIMARY KEY,
            tipo VARCHAR NOT NULL,
            motivo VARCHAR,
            partidas_restantes INTEGER DEFAULT 0,
            expira_en TIMESTAMP,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        os.makedirs(_DATA_DIR, exist_ok=True)
        _con = duckdb.connect(_DB_PATH)
        _init_schema_sync(_con)
    return _con


def _init_db_sync() -> None:
    """Crea tablas e índices y realiza la migración desde idiomas.json si existe."""
    with _DB_LOCK:
        con = _get_connection()

        # Auto-migración desde idiomas.json a la tabla servidores_config
        if os.path.exists(_LEGACY_LANG_FILE):
            try:
                with open(_LEGACY_LANG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for gid_str, lang in data.items():
                    gid = int(gid_str)
                    con.execute("""
                        INSERT INTO servidores_config (guild_id, idioma)
                        VALUES (?, ?)
                        ON CONFLICT (guild_id) DO UPDATE SET idioma = excluded.idioma;
                    """, [gid, str(lang)])
                print(f"[DuckDB] Migracion completada: {len(data)} servidores desde idiomas.json.")
            except Exception as e:
                print(f"[DuckDB] Error al migrar idiomas.json: {e}")

        try:
            con.execute("CHECKPOINT;")
        except Exception:
            pass


async def init_db() -> None:
    """Inicialización asíncrona de la base de datos al arrancar el bot."""
    await asyncio.to_thread(_init_db_sync)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN / IDIOMAS (Servidores)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_lang_sync(guild_id: int) -> str:
    with _DB_LOCK:
        con = _get_connection()
        res = con.execute(
            "SELECT idioma FROM servidores_config WHERE guild_id = ?", [guild_id]
        ).fetchone()
        return res[0] if res else "en"


def _set_lang_sync(guild_id: int, lang: str) -> None:
    with _DB_LOCK:
        con = _get_connection()
        con.execute("""
            INSERT INTO servidores_config (guild_id, idioma, actualizado_en)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (guild_id) DO UPDATE SET
                idioma = excluded.idioma,
                actualizado_en = excluded.actualizado_en;
        """, [guild_id, lang])


def _cargar_todos_los_idiomas_sync() -> dict[int, str]:
    with _DB_LOCK:
        con = _get_connection()
        rows = con.execute("SELECT guild_id, idioma FROM servidores_config").fetchall()
        return {r[0]: r[1] for r in rows}


def get_guild_lang(guild_id: int) -> str:
    """Lectura síncrona en memoria/DB para llamadas rápidas de i18n."""
    try:
        return _get_lang_sync(guild_id)
    except Exception as e:
        print(f"[DuckDB get_lang] {e}")
        return "en"


def set_guild_lang(guild_id: int, lang: str) -> None:
    """Escritura síncrona/segura de idioma."""
    try:
        _set_lang_sync(guild_id, lang)
    except Exception as e:
        print(f"[DuckDB set_lang] {e}")


def cargar_todos_los_idiomas() -> dict[int, str]:
    """Carga masiva para caché en memoria."""
    try:
        return _cargar_todos_los_idiomas_sync()
    except Exception as e:
        print(f"[DuckDB cargar_idiomas] {e}")
        return {}


# ── Configuración de Rol Host por Servidor ───────────────────────────────────

def _get_rol_host_sync(guild_id: int) -> int | None:
    with _DB_LOCK:
        con = _get_connection()
        res = con.execute(
            "SELECT rol_host_id FROM servidores_config WHERE guild_id = ?", [guild_id]
        ).fetchone()
        return res[0] if (res and res[0] is not None) else None


def _set_rol_host_sync(guild_id: int, rol_id: int | None) -> None:
    with _DB_LOCK:
        con = _get_connection()
        con.execute("""
            INSERT INTO servidores_config (guild_id, rol_host_id, actualizado_en)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (guild_id) DO UPDATE SET
                rol_host_id = excluded.rol_host_id,
                actualizado_en = excluded.actualizado_en;
        """, [guild_id, rol_id])


_ROLES_HOST_CACHE: dict[int, int | None] = {}


def get_guild_rol_host(guild_id: int) -> int | None:
    """Lectura de rol host con caché en memoria."""
    if guild_id not in _ROLES_HOST_CACHE:
        try:
            _ROLES_HOST_CACHE[guild_id] = _get_rol_host_sync(guild_id)
        except Exception as e:
            print(f"[DuckDB get_rol_host] {e}")
            return None
    return _ROLES_HOST_CACHE.get(guild_id)


def set_guild_rol_host(guild_id: int, rol_id: int | None) -> None:
    """Actualiza el rol host configurado para el servidor."""
    _ROLES_HOST_CACHE[guild_id] = rol_id
    try:
        _set_rol_host_sync(guild_id, rol_id)
    except Exception as e:
        print(f"[DuckDB set_rol_host] {e}")


async def set_guild_rol_host_async(guild_id: int, rol_id: int | None) -> None:
    await asyncio.to_thread(set_guild_rol_host, guild_id, rol_id)


async def get_guild_rol_host_async(guild_id: int) -> int | None:
    return await asyncio.to_thread(get_guild_rol_host, guild_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  REGISTRO DE PARTIDAS
# ═══════════════════════════════════════════════════════════════════════════════

def _guardar_partida_sync(
    guild_id: int,
    canal_id: int,
    modo: str,
    variante: str | None,
    rondas: int,
    pokemon_id: int | None,
    pokemon_nombre: str | None,
    pokemon_tipos: str | None,
    victoria_impostores: bool,
    caos_sin_impostores: bool,
    jugadores_data: list[dict[str, Any]],
) -> str:
    partida_id = str(uuid.uuid4())
    with _DB_LOCK:
        con = _get_connection()
        con.execute("""
            INSERT INTO partidas (
                id, guild_id, canal_id, modo, variante, rondas,
                pokemon_id, pokemon_nombre, pokemon_tipos,
                victoria_impostores, caos_sin_impostores
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, [
            partida_id, guild_id, canal_id, modo, variante, rondas,
            pokemon_id, pokemon_nombre, pokemon_tipos,
            victoria_impostores, caos_sin_impostores
        ])

        for jd in jugadores_data:
            con.execute("""
                INSERT INTO participaciones (
                    partida_id, user_id, user_name, rol, gano, expulsado
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, [
                partida_id,
                jd["user_id"],
                jd["user_name"],
                jd["rol"],
                jd["gano"],
                jd["expulsado"],
            ])
    return partida_id


async def guardar_partida_async(
    guild_id: int,
    canal_id: int,
    modo: str,
    variante: str | None,
    rondas: int,
    pokemon_id: int | None,
    pokemon_nombre: str | None,
    pokemon_tipos: str | None,
    victoria_impostores: bool,
    caos_sin_impostores: bool,
    jugadores_data: list[dict[str, Any]],
) -> str:
    return await asyncio.to_thread(
        _guardar_partida_sync,
        guild_id, canal_id, modo, variante, rondas,
        pokemon_id, pokemon_nombre, pokemon_tipos,
        victoria_impostores, caos_sin_impostores,
        jugadores_data
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSULTAS ANALÍTICAS (Perfil, Ranking, Estadísticas)
# ═══════════════════════════════════════════════════════════════════════════════

def _obtener_perfil_sync(guild_id: int, user_id: int) -> dict[str, Any] | None:
    with _DB_LOCK:
        con = _get_connection()
        query = """
            SELECT 
                COUNT(*) AS total_partidas,
                SUM(CASE WHEN p.gano THEN 1 ELSE 0 END) AS victorias,
                SUM(CASE WHEN NOT p.gano THEN 1 ELSE 0 END) AS derrotas,
                SUM(CASE WHEN p.rol = 'impostor' THEN 1 ELSE 0 END) AS partidas_impostor,
                SUM(CASE WHEN p.rol = 'impostor' AND p.gano THEN 1 ELSE 0 END) AS victorias_impostor,
                SUM(CASE WHEN p.rol != 'impostor' THEN 1 ELSE 0 END) AS partidas_tripulante,
                SUM(CASE WHEN p.rol != 'impostor' AND p.gano THEN 1 ELSE 0 END) AS victorias_tripulante,
                SUM(CASE WHEN p.rol != 'impostor' AND p.expulsado THEN 1 ELSE 0 END) AS expulsado_inocente,
                ANY_VALUE(p.user_name) AS nombre
            FROM participaciones p
            JOIN partidas part ON p.partida_id = part.id
            WHERE part.guild_id = ? AND p.user_id = ?;
        """
        row = con.execute(query, [guild_id, user_id]).fetchone()
        if not row or row[0] == 0:
            return None

        (
            total, victorias, derrotas,
            p_imp, v_imp,
            p_trip, v_trip,
            exp_inocente, nombre
        ) = row

        winrate_gral = (victorias / total * 100.0) if total > 0 else 0.0
        winrate_imp  = (v_imp / p_imp * 100.0) if p_imp > 0 else 0.0
        winrate_trip = (v_trip / p_trip * 100.0) if p_trip > 0 else 0.0

        # Pokémon más frecuente con el que ha jugado este usuario
        fav_pk_query = """
            SELECT part.pokemon_nombre, COUNT(*) AS c
            FROM participaciones p
            JOIN partidas part ON p.partida_id = part.id
            WHERE part.guild_id = ? AND p.user_id = ? AND part.pokemon_nombre IS NOT NULL
            GROUP BY part.pokemon_nombre
            ORDER BY c DESC
            LIMIT 1;
        """
        fav_pk_row = con.execute(fav_pk_query, [guild_id, user_id]).fetchone()
        pokemon_frecuente = fav_pk_row[0] if fav_pk_row else None

        return {
            "nombre": nombre,
            "total_partidas": total,
            "victorias": victorias,
            "derrotas": derrotas,
            "winrate_gral": round(winrate_gral, 1),
            "partidas_impostor": p_imp,
            "victorias_impostor": v_imp,
            "winrate_impostor": round(winrate_imp, 1),
            "partidas_tripulante": p_trip,
            "victorias_tripulante": v_trip,
            "winrate_tripulante": round(winrate_trip, 1),
            "expulsado_inocente": exp_inocente,
            "pokemon_frecuente": pokemon_frecuente,
        }


async def obtener_perfil_jugador_async(guild_id: int, user_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(_obtener_perfil_sync, guild_id, user_id)


def _obtener_ranking_sync(guild_id: int, categoria: str = "general") -> list[dict[str, Any]]:
    """
    Devuelve el Top 10 según la categoría:
    - 'general': Mayor número de victorias totales (desempate por winrate).
    - 'impostores': Mayor número de victorias como impostor (desempate por winrate de impostor).
    - 'detectives': Mayor número de victorias como tripulante/detective.
    """
    with _DB_LOCK:
        con = _get_connection()

        if categoria == "impostores":
            query = """
                SELECT 
                    p.user_id,
                    ANY_VALUE(p.user_name) AS nombre,
                    SUM(CASE WHEN p.rol = 'impostor' THEN 1 ELSE 0 END) AS total,
                    SUM(CASE WHEN p.rol = 'impostor' AND p.gano THEN 1 ELSE 0 END) AS victorias,
                    ROUND(SUM(CASE WHEN p.rol = 'impostor' AND p.gano THEN 1.0 ELSE 0.0 END) / 
                          NULLIF(SUM(CASE WHEN p.rol = 'impostor' THEN 1.0 ELSE 0.0 END), 0) * 100.0, 1) AS winrate
                FROM participaciones p
                JOIN partidas part ON p.partida_id = part.id
                WHERE part.guild_id = ?
                GROUP BY p.user_id
                HAVING total >= 1
                ORDER BY victorias DESC, winrate DESC, total DESC
                LIMIT 10;
            """
        elif categoria == "detectives":
            query = """
                SELECT 
                    p.user_id,
                    ANY_VALUE(p.user_name) AS nombre,
                    SUM(CASE WHEN p.rol != 'impostor' THEN 1 ELSE 0 END) AS total,
                    SUM(CASE WHEN p.rol != 'impostor' AND p.gano THEN 1 ELSE 0 END) AS victorias,
                    ROUND(SUM(CASE WHEN p.rol != 'impostor' AND p.gano THEN 1.0 ELSE 0.0 END) / 
                          NULLIF(SUM(CASE WHEN p.rol != 'impostor' THEN 1.0 ELSE 0.0 END), 0) * 100.0, 1) AS winrate
                FROM participaciones p
                JOIN partidas part ON p.partida_id = part.id
                WHERE part.guild_id = ?
                GROUP BY p.user_id
                HAVING total >= 1
                ORDER BY victorias DESC, winrate DESC, total DESC
                LIMIT 10;
            """
        else:  # general
            query = """
                SELECT 
                    p.user_id,
                    ANY_VALUE(p.user_name) AS nombre,
                    COUNT(*) AS total,
                    SUM(CASE WHEN p.gano THEN 1 ELSE 0 END) AS victorias,
                    ROUND(SUM(CASE WHEN p.gano THEN 1.0 ELSE 0.0 END) / COUNT(*) * 100.0, 1) AS winrate
                FROM participaciones p
                JOIN partidas part ON p.partida_id = part.id
                WHERE part.guild_id = ?
                GROUP BY p.user_id
                HAVING total >= 1
                ORDER BY victorias DESC, winrate DESC, total DESC
                LIMIT 10;
            """

        rows = con.execute(query, [guild_id]).fetchall()
        resultados = []
        for r in rows:
            resultados.append({
                "user_id": r[0],
                "user_name": r[1],
                "total": r[2],
                "victorias": r[3],
                "winrate": r[4] if r[4] is not None else 0.0,
            })
        return resultados


async def obtener_ranking_async(guild_id: int, categoria: str = "general") -> list[dict[str, Any]]:
    return await asyncio.to_thread(_obtener_ranking_sync, guild_id, categoria)


def _obtener_stats_servidor_sync(guild_id: int) -> dict[str, Any] | None:
    with _DB_LOCK:
        con = _get_connection()
        query = """
            SELECT 
                COUNT(*) AS total_partidas,
                SUM(CASE WHEN victoria_impostores THEN 1 ELSE 0 END) AS vic_impostores,
                SUM(CASE WHEN NOT victoria_impostores AND NOT caos_sin_impostores THEN 1 ELSE 0 END) AS vic_tripulantes,
                SUM(CASE WHEN caos_sin_impostores THEN 1 ELSE 0 END) AS partidas_sin_impostor
            FROM partidas
            WHERE guild_id = ?;
        """
        row = con.execute(query, [guild_id]).fetchone()
        if not row or row[0] == 0:
            return None

        total, v_imp, v_trip, sin_imp = row
        pct_imp  = round((v_imp / total * 100.0), 1) if total > 0 else 0.0
        pct_trip = round((v_trip / total * 100.0), 1) if total > 0 else 0.0

        # Modo de juego favorito
        modo_query = """
            SELECT modo, COUNT(*) as c
            FROM partidas
            WHERE guild_id = ?
            GROUP BY modo
            ORDER BY c DESC
            LIMIT 1;
        """
        modo_row = con.execute(modo_query, [guild_id]).fetchone()
        modo_fav = modo_row[0] if modo_row else "—"

        # Pokémon más letal (con el que más veces ganaron los impostores)
        pk_letal_query = """
            SELECT pokemon_nombre, COUNT(*) as c
            FROM partidas
            WHERE guild_id = ? AND victoria_impostores = TRUE AND pokemon_nombre IS NOT NULL
            GROUP BY pokemon_nombre
            ORDER BY c DESC
            LIMIT 1;
        """
        pk_letal_row = con.execute(pk_letal_query, [guild_id]).fetchone()
        pk_letal = f"{pk_letal_row[0]} ({pk_letal_row[1]} victorias)" if pk_letal_row else "—"

        # Pokémon que más veces ha salido
        pk_comun_query = """
            SELECT pokemon_nombre, COUNT(*) as c
            FROM partidas
            WHERE guild_id = ? AND pokemon_nombre IS NOT NULL
            GROUP BY pokemon_nombre
            ORDER BY c DESC
            LIMIT 1;
        """
        pk_comun_row = con.execute(pk_comun_query, [guild_id]).fetchone()
        pk_comun = f"{pk_comun_row[0]} ({pk_comun_row[1]} veces)" if pk_comun_row else "—"

        return {
            "total_partidas": total,
            "vic_impostores": v_imp,
            "vic_tripulantes": v_trip,
            "sin_impostor": sin_imp,
            "pct_impostores": pct_imp,
            "pct_tripulantes": pct_trip,
            "modo_favorito": modo_fav,
            "pokemon_letal": pk_letal,
            "pokemon_comun": pk_comun,
        }


async def obtener_stats_servidor_async(guild_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(_obtener_stats_servidor_sync, guild_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  GESTIÓN DE LICENCIAS, CÓDIGOS Y SERVIDORES PREMIUM
# ═══════════════════════════════════════════════════════════════════════════════

def _crear_licencia_sync(codigo: str, tipo: str, duracion_dias: int = 0, cargas: int = 0) -> bool:
    with _DB_LOCK:
        con = _get_connection()
        try:
            con.execute("""
                INSERT INTO licencias (codigo, tipo, duracion_dias, cargas, usada)
                VALUES (?, ?, ?, ?, FALSE);
            """, [codigo.upper().strip(), tipo, duracion_dias, cargas])
            return True
        except Exception as e:
            print(f"[Licencias] Error al crear licencia {codigo}: {e}")
            return False


async def crear_licencia_async(codigo: str, tipo: str, duracion_dias: int = 0, cargas: int = 0) -> bool:
    return await asyncio.to_thread(_crear_licencia_sync, codigo, tipo, duracion_dias, cargas)


def _canjear_licencia_sync(codigo: str, guild_id: int, user_id: int) -> dict[str, Any]:
    with _DB_LOCK:
        con = _get_connection()
        codigo_clean = codigo.upper().strip()
        row = con.execute("""
            SELECT tipo, duracion_dias, cargas, usada
            FROM licencias
            WHERE UPPER(codigo) = ?;
        """, [codigo_clean]).fetchone()

        if not row:
            return {"exito": False, "error": "not_found"}

        tipo, duracion_dias, cargas, usada = row
        if usada:
            return {"exito": False, "error": "already_used"}

        # Marcar licencia como usada
        con.execute("""
            UPDATE licencias
            SET usada = TRUE,
                canjeada_por_guild = ?,
                canjeada_por_user = ?,
                canjeada_en = CURRENT_TIMESTAMP
            WHERE codigo = ?;
        """, [guild_id, user_id, codigo_clean])

        ahora = datetime.now()
        expira_en = None
        cargas_totales = 0

        prev = con.execute("""
            SELECT tipo, partidas_restantes, expira_en
            FROM servidores_licencia
            WHERE guild_id = ?;
        """, [guild_id]).fetchone()

        if tipo == "permanente":
            motivo = "Pase Vitalicio ($5 USD) Permanente"
            con.execute("""
                INSERT INTO servidores_licencia (guild_id, tipo, motivo, expira_en, partidas_restantes, actualizado_en)
                VALUES (?, 'vip_permanente', ?, NULL, 0, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id) DO UPDATE SET
                    tipo = 'vip_permanente',
                    motivo = EXCLUDED.motivo,
                    expira_en = NULL,
                    actualizado_en = EXCLUDED.actualizado_en;
            """, [guild_id, motivo])

        elif tipo == "dias":
            if duracion_dias in (28, 29, 30, 31):
                motivo = "Pase VIP 1 Mes"
            elif duracion_dias > 31 and duracion_dias % 30 == 0:
                motivo = f"Pase VIP {duracion_dias // 30} Meses"
            else:
                motivo = f"Pase VIP {duracion_dias} Días"
            base_fecha = ahora
            if prev and prev[0] == "vip_dias" and prev[2] and prev[2] > ahora:
                base_fecha = prev[2]
            expira_en = base_fecha + timedelta(days=duracion_dias)

            con.execute("""
                INSERT INTO servidores_licencia (guild_id, tipo, motivo, expira_en, partidas_restantes, actualizado_en)
                VALUES (?, 'vip_dias', ?, ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id) DO UPDATE SET
                    tipo = 'vip_dias',
                    motivo = EXCLUDED.motivo,
                    expira_en = EXCLUDED.expira_en,
                    actualizado_en = EXCLUDED.actualizado_en;
            """, [guild_id, motivo, expira_en])

        elif tipo == "cargas":
            motivo = f"Bono de {cargas} Partidas VIP"
            cargas_actuales = prev[1] if prev and prev[1] else 0
            cargas_totales = cargas_actuales + cargas

            con.execute("""
                INSERT INTO servidores_licencia (guild_id, tipo, motivo, expira_en, partidas_restantes, actualizado_en)
                VALUES (?, 'cargas', ?, NULL, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id) DO UPDATE SET
                    tipo = CASE WHEN servidores_licencia.tipo IN ('partner', 'vip_permanente') THEN servidores_licencia.tipo ELSE 'cargas' END,
                    motivo = EXCLUDED.motivo,
                    partidas_restantes = EXCLUDED.partidas_restantes,
                    actualizado_en = EXCLUDED.actualizado_en;
            """, [guild_id, motivo, cargas_totales])

        return {
            "exito": True,
            "tipo": tipo,
            "duracion_dias": duracion_dias,
            "cargas": cargas,
            "cargas_totales": cargas_totales,
            "expira_en": expira_en,
        }


async def canjear_licencia_async(codigo: str, guild_id: int, user_id: int) -> dict[str, Any]:
    return await asyncio.to_thread(_canjear_licencia_sync, codigo, guild_id, user_id)


def _verificar_estado_premium_sync(guild_id: int) -> dict[str, Any]:
    with _DB_LOCK:
        con = _get_connection()
        row = con.execute("""
            SELECT tipo, motivo, partidas_restantes, expira_en
            FROM servidores_licencia
            WHERE guild_id = ?;
        """, [guild_id]).fetchone()

        if not row:
            return {
                "es_premium": False,
                "tipo": "gratis",
                "motivo": "Edición Gratuita Base",
                "detalle": "Funciones estándar",
                "partidas_restantes": 0,
            }

        tipo, motivo, partidas_restantes, expira_en = row
        ahora = datetime.now()

        if tipo in ("partner", "vip_permanente"):
            return {
                "es_premium": True,
                "tipo": tipo,
                "motivo": motivo or "Membresía Permanente",
                "detalle": "Acceso ilimitado de por vida",
                "partidas_restantes": -1,
            }

        if tipo == "vip_dias":
            if expira_en and expira_en > ahora:
                dias_restantes = (expira_en - ahora).days
                if dias_restantes in (28, 29, 30, 31):
                    tiempo_str = f"1 mes ({dias_restantes} días)"
                elif dias_restantes > 31:
                    tiempo_str = f"{dias_restantes // 30} meses ({dias_restantes} días)"
                else:
                    tiempo_str = f"{dias_restantes} días"
                return {
                    "es_premium": True,
                    "tipo": "vip_dias",
                    "motivo": motivo or "Pase Temporal",
                    "detalle": f"Válido hasta {expira_en.strftime('%d/%m/%Y')} ({tiempo_str})",
                    "expira_en": expira_en,
                    "partidas_restantes": -1,
                }
            else:
                return {
                    "es_premium": False,
                    "tipo": "expirado",
                    "motivo": "Pase temporal expirado",
                    "detalle": "Licencia vencida",
                    "partidas_restantes": 0,
                }

        if tipo == "cargas":
            if (partidas_restantes or 0) > 0:
                return {
                    "es_premium": True,
                    "tipo": "cargas",
                    "motivo": motivo or "Partidas con Cargas",
                    "detalle": f"{partidas_restantes} partidas premium disponibles",
                    "partidas_restantes": partidas_restantes,
                }
            else:
                return {
                    "es_premium": False,
                    "tipo": "sin_cargas",
                    "motivo": "Sin partidas premium",
                    "detalle": "Cargas agotadas",
                    "partidas_restantes": 0,
                }

        return {
            "es_premium": False,
            "tipo": "gratis",
            "motivo": "Edición Gratuita Base",
            "detalle": "Funciones estándar",
            "partidas_restantes": 0,
        }


async def verificar_estado_premium_async(guild_id: int) -> dict[str, Any]:
    return await asyncio.to_thread(_verificar_estado_premium_sync, guild_id)


def _registrar_servidor_partner_sync(guild_id: int, motivo: str = "Beta Tester Fundador") -> bool:
    with _DB_LOCK:
        con = _get_connection()
        try:
            con.execute("""
                INSERT INTO servidores_licencia (guild_id, tipo, motivo, expira_en, partidas_restantes, actualizado_en)
                VALUES (?, 'partner', ?, NULL, 0, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id) DO UPDATE SET
                    tipo = 'partner',
                    motivo = EXCLUDED.motivo,
                    expira_en = NULL,
                    actualizado_en = EXCLUDED.actualizado_en;
            """, [guild_id, motivo])
            return True
        except Exception as e:
            print(f"[Partner] Error registrando servidor partner {guild_id}: {e}")
            return False


async def registrar_servidor_partner_async(guild_id: int, motivo: str = "Beta Tester Fundador") -> bool:
    return await asyncio.to_thread(_registrar_servidor_partner_sync, guild_id, motivo)


def _sumar_partidas_voto_sync(guild_id: int, cantidad: int = 10) -> int:
    with _DB_LOCK:
        con = _get_connection()
        prev = con.execute("""
            SELECT tipo, partidas_restantes
            FROM servidores_licencia
            WHERE guild_id = ?;
        """, [guild_id]).fetchone()

        if prev and prev[0] in ("partner", "vip_permanente"):
            return -1

        cargas_actuales = prev[1] if prev and prev[1] else 0
        nuevas = cargas_actuales + cantidad
        con.execute("""
            INSERT INTO servidores_licencia (guild_id, tipo, motivo, expira_en, partidas_restantes, actualizado_en)
            VALUES (?, 'cargas', 'Recompensa Voto Top.gg (10 Partidas)', NULL, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (guild_id) DO UPDATE SET
                partidas_restantes = EXCLUDED.partidas_restantes,
                actualizado_en = EXCLUDED.actualizado_en;
        """, [guild_id, nuevas])
        return nuevas


async def sumar_partidas_voto_async(guild_id: int, cantidad: int = 10) -> int:
    return await asyncio.to_thread(_sumar_partidas_voto_sync, guild_id, cantidad)


def _consumir_partida_premium_sync(guild_id: int) -> None:
    with _DB_LOCK:
        con = _get_connection()
        row = con.execute("""
            SELECT tipo, partidas_restantes
            FROM servidores_licencia
            WHERE guild_id = ?;
        """, [guild_id]).fetchone()
        if row and row[0] == "cargas" and (row[1] or 0) > 0:
            con.execute("""
                UPDATE servidores_licencia
                SET partidas_restantes = partidas_restantes - 1,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE guild_id = ?;
            """, [guild_id])


async def consumir_partida_premium_async(guild_id: int) -> None:
    await asyncio.to_thread(_consumir_partida_premium_sync, guild_id)


def _close_db_sync() -> None:
    global _con
    with _DB_LOCK:
        if _con is not None:
            try:
                _con.close()
            except Exception as e:
                print(f"[DuckDB] Error closing connection: {e}")
            finally:
                _con = None


async def close_db() -> None:
    """Cierra la conexión con DuckDB al apagar el bot para garantizar el vaciado limpio del WAL."""
    await asyncio.to_thread(_close_db_sync)

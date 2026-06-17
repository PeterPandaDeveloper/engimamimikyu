"""
motor_juego.py — Núcleo lógico de PokeImpostor
"""
from __future__ import annotations

import asyncio
import random
import discord
from dataclasses import dataclass, field
from enum import Enum

from api import obtener_datos_completos_pokemon
from tipos_pokemon import debilidades_x4, debilidades_x2
from i18n import t, get_lang


# ═══════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class ModoJuego(str, Enum):
    CLASICO   = "clasico"
    EXTENDIDO = "extendido"
    CAOS      = "caos"


class CaosVariante(str, Enum):
    """
    Sub-modificadores EXCLUSIVOS del modo CAOS (radio buttons: solo uno activo).
    Nunca se revelan en el embed público — solo el admin los ve al configurar.
    """
    NORMAL          = "normal"            # Caos estándar (impostores 0..N sobre un Pokémon)
    OBJETIVO_HUMANO = "objetivo_humano"   # un jugador real es el "secreto" en vez de un Pokémon
    DANZA_CAOS      = "danza_caos"        # cada jugador recibe un Pokémon distinto (sin impostores)


class Ventaja(str, Enum):
    ALEATORIO   = "aleatorio"
    LETRA       = "letra"
    TIPO        = "tipo"
    RANGO_REGION = "rango_region"
    HABILIDAD   = "habilidad"
    ESTADISTICAS = "estadisticas"  # listado de stats más altas/bajas juntas
    PERFIL      = "perfil"          # especie + hábitat + grupo huevo (3 datos)
    DEBILIDADES = "debilidades"     # x4 si existe, sino x2, sino "sin debilidades"
    POKEDEX     = "pokedex"         # primeras palabras de la entrada Pokédex


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConfigPartida:
    regiones:      list[str]    = field(default_factory=lambda: ["todas"])
    modo_juego:    ModoJuego    = ModoJuego.CLASICO
    ventaja:       Ventaja      = Ventaja.ALEATORIO
    # Sub-modificador exclusivo de CAOS (radio button). Se ignora en otros modos.
    caos_variante: CaosVariante = CaosVariante.NORMAL


# ═══════════════════════════════════════════════════════════════════════════════
#  RANGOS POR GENERACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

RANGOS_GEN: dict[str, range] = {
    "gen1": range(1,   152),
    "gen2": range(152, 252),
    "gen3": range(252, 387),
    "gen4": range(387, 494),
    "gen5": range(494, 650),
    "gen6": range(650, 722),
    "gen7": range(722, 810),
    "gen8": range(810, 906),
    "gen9": range(906, 1026),
}


# ═══════════════════════════════════════════════════════════════════════════════
#  CLASE PARTIDA
# ═══════════════════════════════════════════════════════════════════════════════

class Partida:
    def __init__(self, canal: discord.TextChannel, partidas_activas: dict):
        self.canal  = canal
        self.config = ConfigPartida()

        self.jugadores:  list[discord.Member] = []
        self.impostores: list[discord.Member] = []

        self.jugadores_iniciales:  list[discord.Member] = []
        self.impostores_iniciales: list[discord.Member] = []

        self.ronda:               int         = 1
        self.datos_pokemon:       dict | None = None
        self.caos_sin_impostores: bool        = False

        # Anti-estancamiento: si pasan demasiadas rondas sin ninguna
        # expulsión (ej. todos votando nulo), se revela una pista pública
        # para presionar al grupo a decidirse.
        self.rondas_sin_expulsion: int  = 0
        self.pista_publica_revelada: bool = False

        # fix: cada impostor tiene su propia pista
        # { jugador.id: texto_de_pista }
        self.pistas_impostores: dict[int, str] = {}
        # para /impver y compatibilidad — pista del primer impostor o única
        self.pista_generada: str = ""

        # variante Objetivo Humano: quién es el "objetivo" (jugador que los demás describen)
        self.objetivo_humano: discord.Member | None = None

        # variante Danza Caos: cada tripulante tiene su propio Pokémon
        # { jugador.id: dict_pokemon }
        self.pokemons_ebrios: dict[int, dict] = {}

        # Variante efectiva de esta ronda (puede diferir de config.caos_variante
        # porque se sortea aleatoriamente en cada arrancar_ronda)
        self._variante_ronda: CaosVariante = CaosVariante.NORMAL

        self._pokemon_usados:   set[int] = set()
        self._partidas_activas: dict     = partidas_activas

        # Lock de concurrencia: protege operaciones que mutan el estado de la
        # partida desde callbacks de UI (votar, forzar cierre, iniciar ronda,
        # revancha...). Sin esto, dos interacciones casi simultáneas podrían
        # ejecutar la misma transición dos veces (doble expulsión, doble
        # avance de ronda, etc.).
        self.lock: asyncio.Lock = asyncio.Lock()
        # Flag auxiliar: True mientras arrancar_ronda() está en ejecución,
        # para detectar intentos concurrentes de iniciar/revancha.
        self._ronda_arrancando: bool = False

    # ── helpers ───────────────────────────────────────────────────────────────
    def _t(self, key: str, **kwargs) -> str:
        return t(key, self.canal.guild.id, **kwargs)

    def limpiar_memoria(self) -> None:
        self._partidas_activas.pop(self.canal.id, None)

    # ── pista pública anti-estancamiento (visible para TODOS) ────────────────
    def generar_pista_publica(self) -> str | None:
        """
        Genera un dato público sobre el Pokémon secreto, distinto de las
        pistas ya entregadas a los impostores, para presionar al grupo
        cuando llevan demasiadas rondas sin expulsar a nadie.
        Devuelve None si no aplica (variantes sin Pokémon secreto tradicional).
        """
        if self.datos_pokemon is None:
            return None
        gid = self.canal.guild.id
        dp  = self.datos_pokemon
        # Reutilizamos el generador de pistas, excluyendo las ya repartidas
        # a los impostores para no dar información redundante.
        excluir = set(self.pistas_impostores.values())
        return self._generar_pista_para(dp, excluir=excluir)

    # ── selección de ID sin repetición ───────────────────────────────────────
    def _elegir_id_pokemon(self) -> int:
        ids_validos: list[int] = []
        if "todas" in self.config.regiones:
            ids_validos = list(range(1, 1026))
        else:
            for gen in self.config.regiones:
                if gen in RANGOS_GEN:
                    ids_validos.extend(RANGOS_GEN[gen])
        if not ids_validos:
            ids_validos = list(range(1, 152))

        disponibles = [i for i in ids_validos if i not in self._pokemon_usados]
        if not disponibles:
            self._pokemon_usados.clear()
            disponibles = ids_validos

        elegido = random.choice(disponibles)
        self._pokemon_usados.add(elegido)
        return elegido

    # ── generación de UNA pista para UN impostor (siempre distinta) ──────────
    def _generar_pista_para(self, dp: dict, excluir: set[str] | None = None) -> str:
        """
        Genera una pista aleatoria o según config.
        Si excluir está definido, no repite pistas ya asignadas a otros impostores.
        """
        gid = self.canal.guild.id
        opciones: dict[Ventaja, str] = {
            Ventaja.LETRA:        t("hint_text_letter", gid, v=dp["nombre"][0]),
            Ventaja.TIPO:         t("hint_text_type",   gid, v=", ".join(dp["tipos"])),
            Ventaja.RANGO_REGION: t("hint_text_region", gid, v=dp["gen"]),
            Ventaja.HABILIDAD:    t("hint_text_ability", gid, v=random.choice(dp["habilidades"])),
            Ventaja.ESTADISTICAS: self._pista_estadisticas(dp, gid),
            Ventaja.PERFIL:       self._pista_perfil(dp, gid),
            Ventaja.DEBILIDADES:  self._pista_debilidades(dp, gid),
            Ventaja.POKEDEX:      self._pista_pokedex(dp, gid),
        }

        if self.config.ventaja != Ventaja.ALEATORIO:
            return opciones.get(self.config.ventaja, opciones[Ventaja.TIPO])

        # aleatorio: evitar repetir si hay varias pistas disponibles
        if excluir:
            disponibles = [v for k, v in opciones.items() if v not in excluir]
            if disponibles:
                return random.choice(disponibles)
        return random.choice(list(opciones.values()))

    # ── Pista: estadísticas (las 2 más altas y las 2 más bajas juntas) ───────
    @staticmethod
    def _pista_estadisticas(dp: dict, gid: int) -> str:
        stats: dict[str, int] = dp.get("stats", {})
        if not stats:
            # Fallback por si 'stats' no vino (compatibilidad con datos viejos):
            # usamos la pista de tipo, que siempre está disponible.
            return t("hint_text_type", gid, v=", ".join(dp.get("tipos", ["?"])))

        nombres_stats = {
            "hp":              t("stat_name_hp",      gid),
            "attack":          t("stat_name_attack",  gid),
            "defense":         t("stat_name_defense", gid),
            "special-attack":  t("stat_name_spatk",   gid),
            "special-defense": t("stat_name_spdef",   gid),
            "speed":           t("stat_name_speed",   gid),
        }
        ordenadas = sorted(stats.items(), key=lambda kv: kv[1], reverse=True)
        altas = ordenadas[:2]
        bajas = ordenadas[-2:]

        altas_str = ", ".join(f"{nombres_stats.get(k, k)} ({v})" for k, v in altas)
        bajas_str = ", ".join(f"{nombres_stats.get(k, k)} ({v})" for k, v in bajas)

        return t("hint_text_stats", gid, high=altas_str, low=bajas_str)

    # ── Pista: perfil (especie + hábitat + grupo huevo) ───────────────────────
    @staticmethod
    def _pista_perfil(dp: dict, gid: int) -> str:
        especie = dp.get("especie") or t("hint_unknown_value", gid)
        habitat = dp.get("habitat") or t("hint_unknown_value", gid)
        huevo   = ", ".join(dp.get("grupos_huevo", [])) or t("hint_unknown_value", gid)
        return t("hint_text_profile", gid, species=especie, habitat=habitat, egg=huevo)

    # ── Pista: debilidades (x4 > x2 > ninguna) ────────────────────────────────
    @staticmethod
    def _pista_debilidades(dp: dict, gid: int) -> str:
        tipos = dp.get("tipos", [])
        x4 = debilidades_x4(tipos)
        if x4:
            return t("hint_text_weakness_x4", gid, types=", ".join(x4))

        x2 = debilidades_x2(tipos)
        if x2:
            # Mostrar como máximo 2 para no ser demasiado revelador
            return t("hint_text_weakness_x2", gid, types=", ".join(x2[:2]))

        return t("hint_text_weakness_none", gid)

    # ── Pista: entrada de Pokédex (primeras palabras) ─────────────────────────
    @staticmethod
    def _pista_pokedex(dp: dict, gid: int) -> str:
        entry = dp.get("pokedex_entry", "")
        if not entry:
            return t("hint_text_pokedex_unavailable", gid)
        # Tomamos las primeras ~8 palabras: suficiente para dar ambiente sin
        # ser tan específico que delate el nombre directamente.
        palabras = entry.split()
        fragmento = " ".join(palabras[:8])
        if len(palabras) > 8:
            fragmento += "..."
        return t("hint_text_pokedex", gid, excerpt=fragmento)


    # ── sorteo de variante Caos por ronda ─────────────────────────────────
    def _sortear_variante_caos(self) -> CaosVariante:
        """
        Elige aleatoriamente qué variante de Caos se jugará en esta ronda.

        La config.caos_variante actúa como PERMISO, no como fijación:
        - NORMAL   → solo Caos estándar (sin variantes especiales)
        - DANZA_CAOS  → puede salir Normal O Danza Caos (50/50)
        - OBJETIVO_HUMANO → puede salir Normal O Objetivo Humano (50/50)

        Diseño: Normal siempre tiene peso para que las variantes especiales
        sean sorpresas ocasionales, no algo que pasa cada ronda.
        """
        cfg = self.config.caos_variante

        if cfg == CaosVariante.NORMAL:
            return CaosVariante.NORMAL

        # Si el admin eligió Danza Caos u Objetivo Humano, hay 40% de que
        # salga la variante especial y 60% de que salga el Caos normal.
        # Así mantiene la sorpresa sin que domine la variante.
        if random.random() < 0.4:
            return cfg         # variante especial elegida por el admin
        return CaosVariante.NORMAL

    # ── cantidad de impostores ─────────────────────────────────────────────
    def _calcular_impostores(self, total: int) -> int:
        modo = self.config.modo_juego
        if modo == ModoJuego.CLASICO:   return 1
        if modo == ModoJuego.EXTENDIDO: return min(max(1, total // 3), total - 1)
        if modo == ModoJuego.CAOS:
            # Usar la variante efectiva de esta ronda (sorteada, no la config)
            if self._variante_ronda == CaosVariante.OBJETIVO_HUMANO:
                return 1
            return self._roll_caos_impostores(total)
        return 1

    @staticmethod
    def _roll_caos_impostores(total: int) -> int:
        """
        Tira el dado del Caos: cuántos impostores habrá.

        Reglas de diseño para que el Caos se sienta "dominado" y no un
        sorteo sin sentido:
        - Nunca TODOS son impostores (eso mata la partida en la ronda 1
          sin debate posible).
        - 0 impostores sigue siendo posible (es la sorpresa icónica del
          Caos: "esta ronda no hay traidores"), pero es poco frecuente.
        - El resto de la probabilidad se concentra en valores "jugables":
          de 1 hasta la mitad de los jugadores (redondeando hacia abajo,
          mínimo 1), que es donde el debate y la votación tienen sentido.
        """
        maximo_jugable = max(1, total // 2)  # ej. 6 jugadores → hasta 3 impostores
        # Pesos: 0 impostores tiene peso fijo bajo; el resto se reparte
        # uniformemente entre 1..maximo_jugable. Para grupos pequeños
        # (pocas opciones jugables), el peso de 0 se reduce más para que
        # no domine la distribución.
        opciones = [0] + list(range(1, maximo_jugable + 1))
        peso_cero = 1 if maximo_jugable >= 2 else 0.5
        pesos     = [peso_cero] + [3] * maximo_jugable
        elegido   = random.choices(opciones, weights=pesos, k=1)[0]
        # Salvaguarda final: jamás todos los jugadores (se necesita al
        # menos 1 tripulante para que haya partida).
        return min(elegido, total - 1)

    # ── DM impostor clásico/extendido/caos ───────────────────────────────────
    def _build_dm_impostor(self, jugador: discord.Member) -> discord.Embed:
        gid       = self.canal.guild.id
        pista     = self.pistas_impostores.get(jugador.id, self.pista_generada)
        total_imp = len(self.impostores)
        complices = [j for j in self.impostores if j != jugador]
        modo      = self.config.modo_juego

        embed = discord.Embed(
            title=t("dm_impostor_title", gid),
            description=t("dm_impostor_desc", gid, hint=pista),
            color=discord.Color.from_rgb(180, 30, 30),
        )
        if modo == ModoJuego.EXTENDIDO and total_imp > 1:
            nombres = ", ".join(f"**{c.display_name}**" for c in complices)
            embed.add_field(
                name=t("dm_impostor_accomplices_title_hidden", gid),
                value=t("dm_impostor_accomplices_value", gid, names=nombres),
                inline=False,
            )
        elif modo == ModoJuego.CAOS and total_imp > 1:
            nombres = ", ".join(f"**{c.display_name}**" for c in complices)
            embed.add_field(
                name=t("dm_impostor_accomplices_title_hidden", gid),
                value=t("dm_impostor_accomplices_value", gid, names=nombres),
                inline=False,
            )
        embed.set_footer(text=t("dm_impostor_footer", gid))
        return embed

    # ── DM tripulante ────────────────────────────────────────────────────────
    def _build_dm_tripulante(self, dp: dict) -> discord.Embed:
        gid = self.canal.guild.id
        embed = discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_crew_desc", gid, name=dp["nombre"], types=" / ".join(dp["tipos"])),
            color=discord.Color.from_rgb(30, 160, 80),
        )
        embed.set_image(url=dp["sprite"])
        embed.set_footer(text=t("dm_crew_footer", gid))
        return embed

    # ── DM variante Objetivo Humano ──────────────────────────────────────────
    def _build_dm_caos_jugador_detective(self, objetivo: discord.Member, pista: str) -> discord.Embed:
        gid = self.canal.guild.id
        # El detective recibe el MISMO título que un impostor normal para no
        # revelar que está en un sub-modo especial. Solo cambia la descripción:
        # su "pista" son datos sobre el jugador objetivo, pero el texto lo
        # presenta como si fuera una pista sobre un Pokémon.
        return discord.Embed(
            title=t("dm_impostor_title", gid),
            description=t("dm_impostor_desc", gid, hint=pista),
            color=discord.Color.from_rgb(180, 30, 30),
        ).set_footer(text=t("dm_impostor_footer", gid))

    def _build_dm_caos_jugador_tripulante(self, objetivo: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        # Tripulante normal de Objetivo Humano: ve el mismo DM que un tripulante
        # de Caos estándar. NO sabe que es un sub-modo especial ni que hay un
        # "objetivo" — solo sabe que describe a "ese jugador" como si fuera un
        # Pokémon. Si le dijéramos "describe a X sin decir su nombre" quedaría
        # obvio que hay un detective buscando a alguien.
        # Usamos un mensaje neutro que da la imagen del objetivo como referencia
        # sin revelar la mecánica.
        return discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_caos_jugador_crew_neutral", gid),
            color=discord.Color.from_rgb(30, 160, 80),
        ).set_image(url=objetivo.display_avatar.url)

    def _build_dm_caos_jugador_objetivo(self) -> discord.Embed:
        """
        DM para el propio objetivo.
        Recibe el mismo DM neutro que los demás tripulantes — no sabe que
        ES el objetivo. Así no puede delatar accidentalmente su rol.
        """
        gid = self.canal.guild.id
        return discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_caos_jugador_crew_neutral", gid),
            color=discord.Color.from_rgb(30, 160, 80),
        )

    # ── DM variante Danza Caos — NO revela sub-modo NI nombre del Pokémon ──
    def _build_dm_amigos_ebrios(self, jugador: discord.Member) -> discord.Embed:
        gid = self.canal.guild.id
        dp  = self.pokemons_ebrios.get(jugador.id)
        if not dp:
            return discord.Embed(title="Error", description="No se asignó Pokémon.")
        # Título y color IGUALES al tripulante normal → no delata el sub-modo.
        # NO se revela el nombre — solo el tipo y el sprite para que el jugador
        # sepa qué describir sin que sea trivialmente obvio para los demás.
        tipos_str = " / ".join(dp["tipos"])
        return discord.Embed(
            title=t("dm_crew_title", gid),
            description=t("dm_ebrios_desc", gid, types=tipos_str),
            color=discord.Color.from_rgb(30, 160, 80),
        ).set_image(url=dp["sprite"]).set_footer(text=t("dm_ebrios_footer", gid))

    # ─────────────────────────────────────────────────────────────────────────
    #  ARRANCAR RONDA — punto de entrada principal
    # ─────────────────────────────────────────────────────────────────────────
    async def arrancar_ronda(self) -> bool:
        self.impostores.clear()
        self.jugadores_iniciales.clear()
        self.impostores_iniciales.clear()
        self.pistas_impostores.clear()
        self.pista_generada   = ""
        self.caos_sin_impostores = False
        self.objetivo_humano  = None
        self.pokemons_ebrios.clear()
        self._variante_ronda = CaosVariante.NORMAL
        self.rondas_sin_expulsion   = 0
        self.pista_publica_revelada = False

        modo = self.config.modo_juego

        # Caos: elegir variante aleatoriamente entre las permitidas ─────────
        # Los radio buttons de configuración indican qué variantes PUEDEN salir
        # (NORMAL siempre disponible). En cada ronda se sortea cuál aparece.
        if modo == ModoJuego.CAOS:
            variante_elegida = self._sortear_variante_caos()
            self._variante_ronda = variante_elegida   # usada por _calcular_impostores
            if variante_elegida == CaosVariante.DANZA_CAOS:
                return await self._arrancar_amigos_ebrios()
            if variante_elegida == CaosVariante.OBJETIVO_HUMANO:
                return await self._arrancar_caos_jugador()
            # Si NORMAL, continúa con el flujo estándar de Caos

        # ── Modos normales (Clásico / Extendido / Caos) ───────────────────────
        id_elegido         = self._elegir_id_pokemon()
        lang               = get_lang(self.canal.guild.id)
        self.datos_pokemon = await obtener_datos_completos_pokemon(id_elegido, lang=lang)
        if self.datos_pokemon is None:
            await self.canal.send(self._t("api_error"))
            return False

        total    = len(self.jugadores)
        cant_imp = self._calcular_impostores(total)

        if cant_imp == 0:
            self.caos_sin_impostores = True
            self.impostores          = []
        else:
            self.impostores = random.sample(self.jugadores, cant_imp)

        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        # fix: pista DISTINTA para cada impostor
        pistas_usadas: set[str] = set()
        for imp in self.impostores:
            pista = self._generar_pista_para(self.datos_pokemon, excluir=pistas_usadas)
            self.pistas_impostores[imp.id] = pista
            pistas_usadas.add(pista)

        # pista_generada = primera pista (para compatibilidad con /impver en modo 1 impostor)
        if self.pistas_impostores:
            self.pista_generada = next(iter(self.pistas_impostores.values()))

        # enviar DMs
        dm_fallidos: list[discord.Member] = []
        for jugador in self.jugadores:
            try:
                if jugador in self.impostores:
                    await jugador.send(embed=self._build_dm_impostor(jugador))
                else:
                    await jugador.send(embed=self._build_dm_tripulante(self.datos_pokemon))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True

    # ── Subrutina: Amigos Ebrios ──────────────────────────────────────────────
    async def _arrancar_amigos_ebrios(self) -> bool:
        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = []

        # asignar un Pokémon distinto a cada jugador
        dm_fallidos: list[discord.Member] = []
        for jugador in self.jugadores:
            id_pk  = self._elegir_id_pokemon()
            dp     = await obtener_datos_completos_pokemon(id_pk, lang=get_lang(self.canal.guild.id))
            if dp is None:
                await self.canal.send(self._t("api_error"))
                return False
            self.pokemons_ebrios[jugador.id] = dp
            if jugador == self.jugadores[0]:
                self.datos_pokemon = dp  # para la pantalla final

            try:
                await jugador.send(embed=self._build_dm_amigos_ebrios(jugador))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True

    # ── Subrutina: Caos Jugador ────────────────────────────────────────────────
    async def _arrancar_caos_jugador(self) -> bool:
        # elegir un jugador al azar como "objetivo" (el que los demás describen)
        self.objetivo_humano = random.choice(self.jugadores)
        # el "detective" (impostor) es quien intenta adivinar
        resto = [j for j in self.jugadores if j != self.objetivo_humano]
        detective = random.choice(resto)
        self.impostores = [detective]

        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        # La pista del detective: 1 o 2 datos sobre el objetivo, según
        # cuántos tripulantes normales habrá describiéndolo. Con pocos
        # jugadores (3-4), solo 1-2 personas describen al objetivo, así
        # que el detective recibe 2 pistas para que siga siendo jugable.
        gid = self.canal.guild.id
        pistas_posibles = [
            t("caos_jugador_hint_avatar",  gid, target=self.objetivo_humano.display_name),
            t("caos_jugador_hint_name",    gid, target=self.objetivo_humano.display_name[0]),
            t("caos_jugador_hint_join",    gid, target=self.objetivo_humano.display_name),
        ]
        random.shuffle(pistas_posibles)

        tripulantes_normales = len(resto) - 1  # resto sin contar al detective
        n_pistas = 2 if tripulantes_normales <= 2 else 1
        pista_detective = "\n".join(f"• {p}" for p in pistas_posibles[:n_pistas])

        self.pistas_impostores[detective.id] = pista_detective
        self.pista_generada = pista_detective

        dm_fallidos: list[discord.Member] = []
        for jugador in self.jugadores:
            try:
                if jugador == detective:
                    await jugador.send(embed=self._build_dm_caos_jugador_detective(self.objetivo_humano, pista_detective))
                elif jugador == self.objetivo_humano:
                    # El objetivo NUNCA debe recibir "describe a [tu propio nombre]"
                    await jugador.send(embed=self._build_dm_caos_jugador_objetivo())
                else:
                    await jugador.send(embed=self._build_dm_caos_jugador_tripulante(self.objetivo_humano))
            except Exception as e:
                print(f"[DM] Falló con {jugador.display_name}: {e}")
                dm_fallidos.append(jugador)

        if dm_fallidos:
            menciones = ", ".join(j.mention for j in dm_fallidos)
            await self.canal.send(self._t("dm_blocked_warning", mentions=menciones))

        return True
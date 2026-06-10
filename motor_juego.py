import random
import discord
from enum import Enum
from api import obtener_datos_completos_pokemon

# ── Fix 4: Enum de modos → no más typos 'classico' sueltos ──────────────────
class ModoJuego(str, Enum):
    CLASICO   = "clasico"
    EXTENDIDO = "extendido"
    CAOS      = "caos"

class Ventaja(str, Enum):
    ALEATORIO    = "aleatorio"
    LETRA        = "letra"
    STAT_ALTA    = "stat_alta"
    STAT_BAJA    = "stat_baja"
    HUEVO        = "huevo"
    TIPO         = "tipo"
    HABITAT      = "habitat"
    RANGO_REGION = "rango_region"
    HABILIDAD    = "habilidad"


class Partida:
    def __init__(self, canal):
        self.canal    = canal
        self.jugadores  = []
        self.impostores = []

        self.jugadores_iniciales  = []
        self.impostores_iniciales = []

        self.ronda = 1
        self.config = {
            'regiones':    ['todas'],
            'modo_juego':  ModoJuego.CLASICO,
            'ventaja':     Ventaja.ALEATORIO,
        }
        self.datos_pokemon  = None
        self.pista_generada = ""

    async def arrancar_ronda(self) -> bool:
        """
        Prepara y arranca la ronda.
        Devuelve False si la API falló y no se pudo obtener un Pokémon.
        """
        self.impostores.clear()
        self.jugadores_iniciales.clear()
        self.impostores_iniciales.clear()

        # ── Filtro de regiones ───────────────────────────────────────────────
        rangos = {
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
        ids_validos = []
        regiones_config = self.config.get('regiones', ['todas'])

        if "todas" in regiones_config:
            ids_validos = list(range(1, 1026))
        else:
            for gen in regiones_config:
                if gen in rangos:
                    ids_validos.extend(rangos[gen])

        if not ids_validos:
            ids_validos = list(range(1, 152))

        id_elegido = random.choice(ids_validos)

        # ── Fix 3: manejo de fallo de API ────────────────────────────────────
        self.datos_pokemon = await obtener_datos_completos_pokemon(id_elegido)
        if self.datos_pokemon is None:
            await self.canal.send(
                "❌ **Error:** No se pudo contactar a PokéAPI después de varios intentos. "
                "Inténtalo de nuevo en unos segundos."
            )
            return False

        # ── Algoritmo de impostores ──────────────────────────────────────────
        total = len(self.jugadores)
        modo  = self.config.get('modo_juego', ModoJuego.CLASICO)

        if modo == ModoJuego.CLASICO:
            cant_imp = 1
        elif modo == ModoJuego.EXTENDIDO:
            cant_imp = max(1, total // 3)
            if cant_imp >= total:
                cant_imp = max(1, total - 1)
        elif modo == ModoJuego.CAOS:
            cant_imp = random.randint(0, total)
        else:
            cant_imp = 1

        self.impostores = random.sample(self.jugadores, cant_imp)

        self.jugadores_iniciales  = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        # ── Generación de pista ──────────────────────────────────────────────
        tipo_pista = self.config.get('ventaja', Ventaja.ALEATORIO)
        dp = self.datos_pokemon

        opciones_pista = {
            Ventaja.LETRA:        f"Su nombre empieza con '{dp['nombre'][0]}'.",
            Ventaja.STAT_ALTA:    f"Su estadística más alta es {dp['stat_mayor']}.",
            Ventaja.STAT_BAJA:    f"Su estadística más baja es {dp['stat_menor']}.",
            Ventaja.HUEVO:        f"Pertenece al grupo huevo {', '.join(dp['grupos_huevo'])}.",
            Ventaja.TIPO:         f"Es de tipo {', '.join(dp['tipos'])}.",
            Ventaja.HABITAT:      f"Su hábitat principal es: {dp['habitat']}.",
            Ventaja.RANGO_REGION: f"Apareció en la {dp['gen']}.",
            Ventaja.HABILIDAD:    f"Una habilidad suya es {random.choice(dp['habilidades'])}.",
        }

        if tipo_pista == Ventaja.ALEATORIO:
            self.pista_generada = random.choice(list(opciones_pista.values()))
        else:
            self.pista_generada = opciones_pista.get(tipo_pista, opciones_pista[Ventaja.TIPO])

        # ── Envío de DMs ─────────────────────────────────────────────────────
        for j in self.jugadores:
            try:
                if j in self.impostores:
                    await j.send(
                        f"🤫 **ERES EL IMPOSTOR**.\n🔍 **Tu ventaja:** {self.pista_generada}"
                    )
                else:
                    embed = discord.Embed(
                        title="✅ Eres tripulante",
                        description=f"El Pokémon secreto es: **{dp['nombre']}**",
                        color=discord.Color.green()
                    )
                    embed.set_image(url=dp['sprite'])
                    await j.send(embed=embed)
            except Exception as e:
                print(f"No se pudo enviar DM a {j.display_name}: {e}")
                await self.canal.send(
                    f"⚠️ **¡ALERTA!** No pude enviarle su rol a {j.mention}. "
                    "Probablemente tiene los DMs bloqueados en este servidor."
                )

        return True
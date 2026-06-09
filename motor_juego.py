import random
from api import obtener_datos_completos_pokemon

class Partida:
    def __init__(self, canal):
        self.canal = canal
        self.jugadores = []
        self.impostores = []
        self.ronda = 1
        self.config = {}
        self.datos_pokemon = None
        self.pista_generada = ""

    async def arrancar_ronda(self):
        # Seleccionar Pokémon
        id_elegido = random.randint(1, 1025)
        self.datos_pokemon = await obtener_datos_completos_pokemon(id_elegido)
        
        # Algoritmo de Impostores según el modo
        total = len(self.jugadores)
        modo = self.config.get('modo_juego', 'classico')
        
        if modo == 'classico':
            cant_imp = 1
        elif modo == 'extendido':
            # Escala con los jugadores pero nunca es 0 ni todos (ej. 1 cada 3 jugadores)
            cant_imp = max(1, total // 3)
            if cant_imp == total: cant_imp = total - 1
        elif modo == 'caos':
            # Puede ser 0, 1, varios, o TODOS
            cant_imp = random.randint(0, total)
            
        self.impostores = random.sample(self.jugadores, cant_imp)

        # Lógica de Pistas dinámicas
        tipo_pista = self.config.get('ventaja', 'aleatorio')
        dp = self.datos_pokemon
        opciones_pista = {
            'letra': f"Su nombre empieza con '{dp['nombre'][0]}'.",
            'stat_alta': f"Su estadística más alta es {dp['stat_mayor']}.",
            'stat_baja': f"Su estadística más baja es {dp['stat_menor']}.",
            'huevo': f"Pertenece al grupo huevo {', '.join(dp['grupos_huevo'])}.",
            'tipo': f"Es de tipo {', '.join(dp['tipos'])}.",
            'habitat': f"Su hábitat principal es: {dp['habitat']}.",
            'rango_region': f"Apareció en la {dp['gen']}.",
            'habilidad': f"Una habilidad suya es {random.choice(dp['habilidades'])}."
        }
        
        if tipo_pista == 'aleatorio':
            self.pista_generada = random.choice(list(opciones_pista.values()))
        else:
            self.pista_generada = opciones_pista.get(tipo_pista, opciones_pista['tipo'])

        # Enviar DMs
        for j in self.jugadores:
            if j in self.impostores:
                await j.send(f"🤫 **ERES EL IMPOSTOR**.\n🔍 **Tu ventaja:** {self.pista_generada}")
            else:
                await j.send(f"✅ Eres tripulante. El Pokémon es: **{dp['nombre']}**.")
import random
from api import obtener_datos_completos_pokemon

class Partida:
    def __init__(self, canal):
        self.canal = canal
        self.jugadores = []
        self.impostores = []
        
        # Memoria para el final del juego
        self.jugadores_iniciales = []
        self.impostores_iniciales = []
        
        self.ronda = 1
        self.config = {'regiones': ['todas']} # Valor por defecto
        self.datos_pokemon = None
        self.pista_generada = ""

    async def arrancar_ronda(self):
        # 1. Filtro de regiones
        rangos = {
            "gen1": range(1, 152), 
            "gen2": range(152, 252), 
            "gen3": range(252, 387), 
            "gen4": range(387, 494)
        }
        ids_validos = []
        
        # Leer la configuración de regiones (o usar 'todas' como seguridad)
        regiones_config = self.config.get('regiones', ['todas'])
        
        if "todas" in regiones_config:
            ids_validos = list(range(1, 1026))
        else:
            for gen in regiones_config:
                if gen in rangos:
                    ids_validos.extend(rangos[gen])
                    
        # Fallback de seguridad por si no se seleccionó ninguna región válida
        if not ids_validos:
            ids_validos = list(range(1, 152))
                
        id_elegido = random.choice(ids_validos)
        self.datos_pokemon = await obtener_datos_completos_pokemon(id_elegido)
        
        # 2. Algoritmo de Impostores según el modo
        total = len(self.jugadores)
        modo = self.config.get('modo_juego', 'classico')
        
        if modo == 'classico':
            cant_imp = 1
        elif modo == 'extendido':
            # Escala con los jugadores pero nunca es 0 ni todos (ej. 1 cada 3 jugadores)
            cant_imp = max(1, total // 3)
            # Evitar que todos sean impostores en extendido
            if cant_imp >= total: 
                cant_imp = max(1, total - 1)
        elif modo == 'caos':
            # Puede ser 0, 1, varios, o TODOS
            cant_imp = random.randint(0, total)
        else:
            cant_imp = 1 # Seguridad
            
        self.impostores = random.sample(self.jugadores, cant_imp)
        
        # GUARDAMOS MEMORIA PARA LA PANTALLA FINAL
        self.jugadores_iniciales = self.jugadores.copy()
        self.impostores_iniciales = self.impostores.copy()

        # 3. Lógica de Pistas / Ventajas dinámicas
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
            # Si el tipo específico falla, damos el tipo como pista de seguridad
            self.pista_generada = opciones_pista.get(tipo_pista, opciones_pista['tipo'])

        # 4. Enviar DMs
        for j in self.jugadores:
            try:
                if j in self.impostores:
                    await j.send(f"🤫 **ERES EL IMPOSTOR**.\n🔍 **Tu ventaja:** {self.pista_generada}")
                else:
                    await j.send(f"✅ Eres tripulante. El Pokémon es: **{dp['nombre']}**.")
            except Exception as e:
                print(f"No se pudo enviar un DM a {j.display_name}. Dile que abra sus mensajes. Error: {e}")
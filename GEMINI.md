# REGLAS CENTRALES DE ARQUITECTURA — POKEIMPOSTOR (MIMIKYU)

Este archivo es leído automáticamente por Antigravity en cada conversación iniciada en este proyecto.

---

## ⏳ 1. LEY FUNDAMENTAL: "Ronda de Palabras" vs "Límite de Rondas del Juego"

Existe una distinción crítica que NUNCA debe confundirse:

1. **Ronda de Palabras (Turno de Discusión):**
   * Es una vuelta completa donde cada jugador en la mesa da su palabra o pista para demostrar que no es el impostor:
     * *Ejemplo:* Pedro habla → Juan habla → André habla → Paul habla.
   * Al terminar la ronda de palabras, se abre el debate y la votación para expulsar a un sospechoso.

2. **Límite de Rondas del Juego (Contador Decremental de Presión):**
   * En **TODOS LOS MODOS**, el anfitrión configura el límite de rondas máximas (entre **1 y 9 rondas** mediante un **Combo Box / Select Menu**).
   * El juego maneja un **contador decremental**:
     * Empieza en $N$ (ej: 3 rondas restantes).
     * Si tras la votación aún quedan impostores con vida, el contador baja: $3 \rightarrow 2 \rightarrow 1$.
   * **Condición de Derrota por Tiempo:**
     * Si el contador decremental llega a `0` sin que los tripulantes hayan expulsado a todos los impostores, **¡los Impostores ganan automáticamente!** (los tripulantes se quedaron sin turnos).

---

## 🌀 2. MODO CAOS = CAOS TOTAL (Ruleta Rusa de Incertidumbre)

* El Modo Caos NO tiene botones ni sub-selectores manuales para los usuarios en partidas públicas.
* Es una ruleta rusa de incertidumbre total:
  * Al arrancar cada ronda en Modo Caos, el motor sortea equitativamente entre las 7 variantes oficiales:
    1. `CERO_IMPOSTORES`: 0% impostores, todos comparten el mismo Pokémon (paranoia pura).
    2. `UN_IMPOSTOR`: 1 solo impostor clásico.
    3. `CINCUENTA_PORCIENTO`: 50% de la sala impostor.
    4. `SETENTA_Y_CINCO`: 75% de la sala impostor.
    5. `TODOS_IMPOSTORES`: 100% de la sala impostor (ganan los supervivientes que no sean expulsados).
    6. `AMIGOS_BORRACHOS`: 0 impostores, cada jugador recibe un Pokémon diferente (Danza Caos).
    7. `OBJETIVO_HUMANO`: Un jugador de la sala es el secreto (foto y nombre), el impostor recibe una pista y todos votan para desenmascarar.
* **Reseteo tras consumo:** `partida.config.caos_variante` se reinicia a `NORMAL` tras aplicarse para garantizar que las rondas subsiguientes sigan sorteando en la ruleta.
* **Cero Spoilers:** La interfaz nunca revela cuántos impostores quedan vivos ni la variante exacta en juego hasta la pantalla final.

---

## 🎛️ 3. INTERFAZ DE CONFIGURACIÓN Y CONTROLES DEL ANFITRIÓN

* **Roles y Permisos:**
  * Cualquier usuario con el rol oficial (`PokeHost` o el rol personalizado asignado con `/setrole-kyu`) o Administrador puede crear salas (`/play-kyu` o `-mimi play`).
  * Los botones de configuración y cierre de votación solo pueden ser accionados por el anfitrión o administradores.
* **Selectores Limpios y Accesibles:**
  * Límite de Rondas: Combo Box (`discord.ui.Select`) de `1` a `9` rondas.
  * Modo de Juego: Clásico, Extendido (con toggle para complicidad entre impostores) y Caos.
  * Ventajas: Tipo, Letra, Región, Habilidad, Palabra Ambigua, Perfil, Debilidades, Pokédex (Cloze test), o Aleatorio.
* **Créditos Oficiales:**
  * Todos los embeds del bot llevan en su pie de página: `🎨 Arte: @xeechithecat.bsky.social`.

---

## 🏛️ 4. ESTRUCTURA Y MODULARIZACIÓN DEL CÓDIGO

El proyecto cuenta con una arquitectura completamente desacoplada y modular:

* **`main.py` (Punto de Entrada):**
  * Subclase `PokeImpostorBot(commands.Bot)` con apagado limpio de recursos en `close()` (DuckDB, aiohttp y webhook runner).
  * 29 Slash Commands globales limpios (muy por debajo del límite duro de 50 de Discord).
  * Interceptor dual de texto `_extraer_comando_imp` que soporta prefijos (`-mimi`, `mimi`, `!mimi`, `/mimi`, `-imp`) y sufijos (`-mimi`, `mimi`, `-imp`).
* **`pistas.py` (Generación de Pistas y Vocabulario):**
  * Extraído de `motor_juego.py` para aislar la lógica temática.
  * Diccionarios curados: `VOCABULARIO_TEMATICO`, `HABITATS_AMBIGUOS`, `TIPOS_AMBIGUOS`.
  * Cloze Test Pokédex con censura de términos delatores, cálculo de debilidades elementales (x4 / x2) y perfiles taxonómicos.
  * Respeto estricto del catálogo existente (sin agregar pistas arbitrarias no solicitadas).
* **`webhook_topgg.py` (Recepción de Votos y Monetización):**
  * Servidor web `aiohttp` independiente en el puerto configurado (default: 5000).
  * Acreditación automática de 10 partidas VIP por voto en Top.gg.
  * Detección por query string (`?guild=...`), servidor más activo en DuckDB o servidor compartido.
  * Anuncio público automático con embed en el canal del servidor beneficiado.
* **`comandos_comunes.py` (Lógica Compartida Slash / Texto):**
  * Constructores reutilizables para `/perfil`, `/ranking`, `/stats`, `/licencia`, `/canjear`, `/voto`, `/donar`, `/invitar`, `/ayuda`, `/creditos`, `/setrole` y reenvío de roles por DM (`reenviar_rol_secreto`).
  * Elimina la duplicación de código entre Slash y mensajes de texto, asegurando paridad visual y de comportamiento.
* **`motor_juego.py` (Lógica Central de la Partida):**
  * Gestión de estados de sala, sorteo de Pokémon sin repetición, asignación de roles y turnos.
  * Integración con `DummyMember` para pruebas en solitario.
* **`db.py` (Persistencia DuckDB):**
  * Esquema relacional con tablas: `partidas`, `participaciones`, `perfiles_jugadores`, `licencias_vip`, `servidores_partner` y `config_servidores`.
  * Acceso atómico mediante `threading.Lock` y llamadas asíncronas con `asyncio.to_thread`.
* **`vistas/` (Componentes UI):**
  * `config.py`: Panel de configuración pre-partida con validación VIP en vivo.
  * `debate.py`: Temporizadores de discusión y botón de inicio de votación.
  * `votacion.py`: Votación cero-spoilers con auto-voto de bots fantasma, votación unificada de 1 voto por jugador y expulsión masiva al superar 3 empates consecutivos (empates > 3 en Caos/Extendido).
  * `final.py`: Resumen final, persistencia de métricas, descuento de cargas VIP y sistema de revancha.

---

## 🧪 5. MODO DEBUGGER EN SOLITARIO (`-mimi debug`)

* **Restricción de Seguridad:** Limitado exclusivamente a servidores de desarrollo `(402155389958881310, 774891658508107776)` y anfitriones/administradores.
* **Comando:** `-mimi debug [cantidad] [variante_caos]` (ej: `-mimi debug 3 objetivo_humano`).
* **Bots Fantasma (`DummyMember`):** Emulan miembros reales (`Ash`, `Misty`, `Brock`...), redirigen sus DMs de rol al anfitrión humano con el prefijo `🧪 [DEBUG — Rol enviado a X]:` y emiten auto-votos inmediatos para cerrar rondas de prueba.
* **Aislamiento en DB:** Si hay `DummyMember` en la sala, `vistas/final.py` omite el guardado en DuckDB y el consumo de cargas VIP para no ensuciar las estadísticas reales ni los rankings del servidor.

---

## 🚀 6. ENTORNO DE PRODUCCIÓN Y DESPLIEGUE

* **Servidor Remoto:** Oracle Cloud Infrastructure (Ubuntu VM, IP: `150.136.238.32`, alias SSH `oracle`).
* **Ruta en Servidor:** `/home/ubuntu/pokeimpostor`.
* **Servicio del Sistema:** `pokeimpostor.service` gestionado vía systemd.
* **Repositorio Git:** `https://github.com/PeterPandaDeveloper/engimamimikyu.git` (rama `main`).

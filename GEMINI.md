# REGLAS CENTRALES DE ARQUITECTURA — POKEIMPOSTOR

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

## 🌀 2. MODO CAOS = CAOS TOTAL (Sin Sub-Selectores)

* El Modo Caos NO debe tener botones ni selectores manuales de variantes.
* Es una ruleta rusa de incertidumbre total:
  * Al iniciar una partida en Modo Caos, el motor sortea aleatoriamente entre todo el abanico:
    * Partida con $N$ impostores normales.
    * Partida con **0 impostores** (paranoia colectiva).
    * Variante **Objetivo Humano** (un detective debe descubrir a un jugador real).
    * Variante **Danza Caos** (cada jugador recibe un Pokémon diferente).
* Los jugadores jamás conocen la variante activa hasta que la deducen por sí mismos.

---

## 🎛️ 3. INTERFAZ DE CONFIGURACIÓN (Combo Box de 1 a 9)

* **Selector de Límite de Rondas:**
  * Debe ser siempre un **Combo Box (`discord.ui.Select`)** con opciones del `1` al `9` (ej: `1 Ronda`, `2 Rondas`, ..., `9 Rondas`).
  * Sin botones dispersos: limpio, accesible y ergonómico para móvil.

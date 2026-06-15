"""
tipos_pokemon.py — Tabla estática de relaciones de tipo (multiplicadores de daño).

Esta tabla es información de juego fija (no cambia entre generaciones
modernas relevantes para este bot), así que se mantiene local en lugar
de hacer llamadas extra a /type/{id} por cada Pokémon — evita N llamadas
adicionales a PokéAPI por ronda.

Estructura: DEBILIDADES[tipo_atacante] = {tipo_defensor: multiplicador}
Solo se listan multiplicadores != 1 (x2 fuerte, x0.5 resiste, x0 inmune).
Aquí invertimos la lógica: para un Pokémon de tipo X, ¿qué tipos le hacen
x4, x2, x0.5, x0? Se calcula combinando ambos tipos si el Pokémon es dual.
"""
from __future__ import annotations

# Multiplicador de daño que el tipo ATACANTE (clave externa) hace al tipo
# DEFENSOR (clave interna). Solo valores != 1.0.
EFECTIVIDAD: dict[str, dict[str, float]] = {
    "Normal":   {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire":     {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water":    {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Grass":    {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice":      {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison":   {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground":   {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying":   {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic":  {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug":      {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock":     {"Normal": 0.5, "Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost":    {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon":   {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Dark":     {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Steel":    {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Fairy":    {"Fighting": 2.0, "Poison": 0.5, "Bug": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
}

TODOS_LOS_TIPOS = list(EFECTIVIDAD.keys())


def calcular_debilidades(tipos_defensor: list[str]) -> dict[str, float]:
    """
    Dado uno o dos tipos defensores (los del Pokémon), calcula el
    multiplicador combinado que recibiría de cada tipo atacante.
    Devuelve {tipo_atacante: multiplicador_combinado}.
    """
    resultado: dict[str, float] = {}
    for atacante in TODOS_LOS_TIPOS:
        mult = 1.0
        for defensor in tipos_defensor:
            mult *= EFECTIVIDAD.get(atacante, {}).get(defensor, 1.0)
        if mult != 1.0:
            resultado[atacante] = mult
    return resultado


def debilidades_x4(tipos_defensor: list[str]) -> list[str]:
    deb = calcular_debilidades(tipos_defensor)
    return sorted([t for t, m in deb.items() if m >= 4.0])


def debilidades_x2(tipos_defensor: list[str]) -> list[str]:
    deb = calcular_debilidades(tipos_defensor)
    return sorted([t for t, m in deb.items() if m == 2.0])
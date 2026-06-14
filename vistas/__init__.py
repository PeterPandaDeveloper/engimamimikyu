"""
vistas/__init__.py — Punto de entrada del paquete de UI.

Re-exporta los símbolos que `main.py` necesita, para no romper
las importaciones existentes (`from vistas import PanelInscripcion, ...`).
"""
from .common import build_embed_lobby as _build_embed_lobby
from .lobby import PanelInscripcion
from .config import PanelConfiguracion
from .debate import PanelDebate
from .votacion import PanelVotacion
from .final import PanelPostRonda, mostrar_pantalla_final

__all__ = [
    "PanelInscripcion",
    "PanelConfiguracion",
    "PanelDebate",
    "PanelVotacion",
    "PanelPostRonda",
    "mostrar_pantalla_final",
    "_build_embed_lobby",
]
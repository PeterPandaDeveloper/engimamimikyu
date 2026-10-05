"""
security.py — Sistema de autenticación criptográfica y generación de licencias seguras.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# Hash SHA-256 de la contraseña maestra (nunca en texto plano en el repositorio)
# Valor por defecto correspondiente al hash seguro de autorización
_DEFAULT_HASH = "6f27fad91d72d87c37223c13f431e09e0aa5a13eb3f4c115be54a95e98b9c9ae"
ADMIN_MASTER_HASH = os.getenv("ADMIN_MASTER_HASH", _DEFAULT_HASH)


def verificar_master_password(password_candidata: str) -> bool:
    """
    Verifica la contraseña ingresada calculando su digest SHA-256
    y comparándolo en tiempo constante (timing-attack resistant).
    """
    if not password_candidata:
        return False
    hash_candidato = hashlib.sha256(password_candidata.encode("utf-8")).hexdigest()
    return hmac.compare_digest(hash_candidato.lower(), ADMIN_MASTER_HASH.lower())


def generar_codigo_licencia(prefijo: str = "POKE-VIP") -> str:
    """
    Genera un código criptográficamente seguro con formato:
    POKE-VIP-XXXX-YYYY (usando CSPRNG del sistema operativo vía secrets).
    """
    parte1 = secrets.token_hex(2).upper()
    parte2 = secrets.token_hex(2).upper()
    return f"{prefijo}-{parte1}-{parte2}"

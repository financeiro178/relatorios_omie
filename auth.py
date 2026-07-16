# -*- coding: utf-8 -*-
"""Autenticação: hash de senha (PBKDF2) e tokens de sessão (biblioteca padrão)."""
from __future__ import annotations

import hashlib
import hmac
import secrets

ITERACOES = 240000


def hash_senha(senha, salt=None, iteracoes=ITERACOES):
    """Retorna (hash_hex, salt_hex, iteracoes)."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), iteracoes)
    return dk.hex(), salt, iteracoes


def verificar_senha(senha, hash_hex, salt, iteracoes):
    try:
        calc = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), int(iteracoes))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc.hex(), hash_hex or "")


def novo_token():
    """Token de sessão opaco (vai no cookie)."""
    return secrets.token_urlsafe(32)


def hash_token(token):
    """Guardamos no banco apenas o hash do token (não o token em si)."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def senha_forte(senha):
    """Validação mínima de senha."""
    return isinstance(senha, str) and len(senha) >= 6

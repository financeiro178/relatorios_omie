# -*- coding: utf-8 -*-
"""Funcoes utilitarias compartilhadas."""
from __future__ import annotations


def para_iso(data_br):
    """Converte 'dd/mm/aaaa' (formato OMIE) para 'aaaa-mm-dd'. Retorna None se vazio/invalido."""
    if not data_br or not isinstance(data_br, str):
        return None
    data_br = data_br.strip()
    if not data_br:
        return None
    partes = data_br.split("/")
    if len(partes) != 3:
        return None
    d, m, a = partes
    if not (d.isdigit() and m.isdigit() and a.isdigit()):
        return None
    try:
        return "%04d-%02d-%02d" % (int(a), int(m), int(d))
    except (ValueError, TypeError):
        return None


def num(valor):
    """Converte para float de forma segura. Aceita numero, string '1.234,56' ou '1234.56'."""
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    # remove separador de milhar e troca virgula decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def slug(texto):
    """Gera um identificador simples a partir de um texto."""
    import re
    texto = (texto or "").strip().lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    return texto.strip("-") or "empresa"

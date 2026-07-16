# -*- coding: utf-8 -*-
"""Atribuição de empresa real em OMIE consolidado (holding).

A ROI é a empresa-mãe: o OMIE dela contém contas bancárias de várias empresas,
identificadas pelo prefixo [Empresa] no nome da conta corrente. Aqui mapeamos cada
conta para a empresa real, para que os títulos sejam atribuídos corretamente.
"""
from __future__ import annotations

import re
import unicodedata

# Credenciais que são "holding" (um OMIE com várias empresas dentro)
CREDENCIAIS_HOLDING = {"roi"}

# empresas encontradas dentro da ROI que ainda não estavam no diretório
NOVAS_EMPRESAS = [
    # (id, nome, grupo, responsavel)
    ("camefe", "Camefe", "bpo", ""),
    ("ceuta", "Ceuta", "bpo", ""),
    ("costa-dos-corais", "Costa dos Corais", "bpo", ""),
    ("tecstar", "Tecstar", "bpo", ""),
]


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", s.lower())


# prefixo normalizado -> empresa_id real
PREFIXO_EMPRESA = {
    "ativus": "ativus", "audax": "audax", "autor": "autor", "acao": "acao",
    "bird": "roi",                       # Bird tem OMIE próprio; o [Bird] interno fica na holding
    "camefe": "camefe", "ceuta": "ceuta", "costadoscorais": "costa-dos-corais",
    "gibraltar": "gibraltar", "golf": "golf", "malaga": "malaga", "quintas": "quintas",
    "roi": "roi", "rr": "rr-participacoes", "rrparticipacoes": "rr-participacoes",
    "school": "school", "tarifa": "tarifa", "tecstar": "tecstar",
}


def empresa_real(credencial_id, conta_descricao):
    """Dada a credencial e a descrição da conta corrente, retorna a empresa real."""
    if credencial_id not in CREDENCIAIS_HOLDING:
        return credencial_id
    m = re.match(r"\s*\[([^\]]+)\]", conta_descricao or "")
    if not m:
        return credencial_id  # sem prefixo -> fica na própria holding
    return PREFIXO_EMPRESA.get(_norm(m.group(1)), credencial_id)

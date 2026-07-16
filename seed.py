# -*- coding: utf-8 -*-
"""Catalogo de nomes das empresas do grupo (para exibicao nos relatorios).

As empresas com credencial OMIE recebem razao social real na sincronizacao.
As empresas que vivem DENTRO do OMIE da ROI (holding) nao tem sync proprio,
entao garantimos aqui um nome amigavel para elas.
"""
from __future__ import annotations

# (id, nome)
EMPRESAS = [
    ("roi",               "ROI Participações e Inv. S.A."),
    ("acao",              "Ação Consultoria e Empr. Imob. Ltda"),
    ("ativus",            "Ativus Participações S/A"),
    ("autor",             "Autor Participações S.A."),
    ("audax",             "Audax Participações LTDA"),
    ("bird",              "Bird Partners LTDA"),
    ("camefe",            "Camefe"),
    ("ceuta",             "Ceuta"),
    ("costa-dos-corais",  "Costa dos Corais"),
    ("esfera",            "Esfera Arena e Negócios Spe Ltda"),
    ("eleven",            "Eleven & One Partners LTDA"),
    ("gibraltar",         "Gibraltar Inv. Imob. Part. S/A"),
    ("golf",              "Golf Participações e Inv. Imob. LTDA"),
    ("k-finserv",         "K Finserv Serviços Financeiros LTDA"),
    ("malaga",            "Malaga Participação LTDA"),
    ("mar-azul",          "Mar Azul Empreendimentos Imob. LTDA"),
    ("quintas",           "Quintas Empreendimentos e Part. S/A"),
    ("rr-participacoes",  "RR Participações LTDA"),
    ("school",            "School Participações Inv. Imob. LTDA"),
    ("tarifa",            "Tarifa Participações LTDA"),
    ("tecstar",           "Tecstar"),
]


def seed_nomes(db):
    """Garante nome amigavel para as empresas conhecidas (idempotente, nao sobrescreve sync)."""
    for eid, nome in EMPRESAS:
        db.upsert_empresa_basica(eid, {"nome": nome})

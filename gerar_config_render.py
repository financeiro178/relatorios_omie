# -*- coding: utf-8 -*-
"""Gera o valor da variavel CONFIG_JSON para deploy na nuvem (Render Free).

Le as credenciais OMIE do banco local (analise_omie.db) e grava tudo em UMA linha
no arquivo config.render.json (gitignored — NUNCA versionar). Copie o conteudo desse
arquivo e cole no Render em Environment > CONFIG_JSON.

Uso: dois cliques (ou: py gerar_config_render.py)
"""
from __future__ import annotations

import json
import os
import sqlite3

RAIZ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(RAIZ, "analise_omie.db")
SAIDA = os.path.join(RAIZ, "config.render.json")

if not os.path.isfile(DB):
    print("Banco analise_omie.db nao encontrado — rode o app (iniciar.bat) ao menos uma vez.")
else:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT empresa_id, nome, app_key, app_secret FROM empresa_credencial ORDER BY empresa_id").fetchall()
    cfg = {"empresas": [
        {"id": r["empresa_id"], "nome": r["nome"], "app_key": r["app_key"], "app_secret": r["app_secret"]}
        for r in rows]}
    with open(SAIDA, "w", encoding="utf-8") as fp:
        fp.write(json.dumps(cfg, ensure_ascii=False))
    print("OK: %d credenciais gravadas em config.render.json" % len(cfg["empresas"]))
    print("Abra o arquivo no Bloco de Notas, copie TUDO (e uma linha so) e cole no Render")
    print("em Environment > CONFIG_JSON. Depois apague o arquivo se quiser.")

input("\nEnter para fechar...")

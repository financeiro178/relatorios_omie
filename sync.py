# -*- coding: utf-8 -*-
"""Sincroniza os dados do OMIE para o banco local (SQLite).

Para cada empresa do config.json: busca empresa, contas correntes, categorias,
clientes/fornecedores, contas a pagar e contas a receber.
"""
from __future__ import annotations

from datetime import datetime

import holding
from omie_client import OmieClient, OmieError, SemRegistros
from util import num, para_iso


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sincronizar_empresa(db, empresa_cfg, status=None):
    """Sincroniza uma empresa. 'status' e um dict opcional para reportar progresso."""
    empresa_id = empresa_cfg["id"]
    cli = OmieClient(empresa_cfg["app_key"], empresa_cfg["app_secret"])

    def passo(msg, **extra):
        if status is not None:
            status["mensagem"] = msg
            status["empresa_atual"] = empresa_cfg.get("nome") or empresa_id
            status.update(extra)

    resumo = {}

    # 1) Dados da empresa
    passo("Buscando dados da empresa...")
    try:
        r = cli.chamar("geral/empresas/", "ListarEmpresas",
                       {"pagina": 1, "registros_por_pagina": 50, "apenas_importado_api": "N"})
        emp = (r.get("empresas_cadastro") or [{}])[0]
    except OmieError:
        emp = {}
    db.upsert_empresa(empresa_id, {
        "nome": empresa_cfg.get("nome") or emp.get("nome_fantasia") or empresa_id,
        "razao_social": emp.get("razao_social") or empresa_cfg.get("nome") or empresa_id,
        "nome_fantasia": emp.get("nome_fantasia") or "",
        "cnpj": emp.get("cnpj") or "",
        "cidade": emp.get("cidade") or "",
        "estado": emp.get("estado") or "",
        "atualizado_em": _agora(),
    })

    # 2) Contas correntes (contas bancarias)
    passo("Buscando contas bancarias...")
    contas = cli.listar_tudo("geral/contacorrente/", "ListarContasCorrentes", {},
                             "ListarContasCorrentes", registros_por_pagina=50)
    linhas = [{
        "empresa_id": empresa_id,
        "ncodcc": c.get("nCodCC"),
        "descricao": c.get("descricao") or "",
        "tipo": c.get("tipo") or c.get("tipo_conta_corrente") or "",
        "codigo_banco": str(c.get("codigo_banco") or ""),
        "agencia": str(c.get("codigo_agencia") or ""),
        "numero": str(c.get("numero_conta_corrente") or c.get("numero") or ""),
        "inativo": c.get("inativo") or "N",
        "saldo_inicial": num(c.get("saldo_inicial")),
    } for c in contas]
    db.substituir("conta_corrente", empresa_id, linhas,
                  ["empresa_id", "ncodcc", "descricao", "tipo", "codigo_banco",
                   "agencia", "numero", "inativo", "saldo_inicial"])
    # mapa conta -> empresa real (divide holding ROI por prefixo [Empresa])
    mapa_cc = {c.get("nCodCC"): (c.get("descricao") or "") for c in contas}
    resumo["contas_correntes"] = len(linhas)
    passo("%d contas bancarias." % len(linhas))

    # 3) Categorias
    passo("Buscando plano de categorias...")
    try:
        cats = cli.listar_tudo("geral/categorias/", "ListarCategorias", {},
                               "categoria_cadastro", registros_por_pagina=500)
    except OmieError:
        cats = []
    def _natureza(c):
        """'R' (receita) | 'D' (despesa) | '' — a partir dos flags do OMIE."""
        if (c.get("conta_receita") or "").upper() == "S":
            return "R"
        if (c.get("conta_despesa") or "").upper() == "S":
            return "D"
        n = (c.get("natureza") or "").strip().upper()
        return n if n in ("R", "D") else ""

    linhas = [{
        "empresa_id": empresa_id,
        "codigo": c.get("codigo"),
        "descricao": c.get("descricao") or c.get("descricao_padrao") or "",
        "natureza": _natureza(c),
    } for c in cats if c.get("codigo")]
    db.substituir("categoria", empresa_id, linhas,
                  ["empresa_id", "codigo", "descricao", "natureza"])
    resumo["categorias"] = len(linhas)
    passo("%d categorias." % len(linhas))

    # 4) Clientes / fornecedores
    passo("Buscando clientes e fornecedores...")
    try:
        clientes = cli.listar_tudo(
            "geral/clientes/", "ListarClientesResumido",
            {"apenas_importado_api": "N"}, "clientes_cadastro_resumido",
            registros_por_pagina=500,
            ao_progredir=lambda p, tp, acc, tot: passo(
                "Clientes/fornecedores: %d (pagina %d/%d)" % (acc, p, tp)),
        )
    except OmieError:
        clientes = []
    linhas = [{
        "empresa_id": empresa_id,
        "codigo": c.get("codigo_cliente"),
        "razao_social": c.get("razao_social") or c.get("nome_fantasia") or "",
        "nome_fantasia": c.get("nome_fantasia") or "",
        "documento": c.get("cnpj_cpf") or "",
    } for c in clientes if c.get("codigo_cliente")]
    db.substituir("cliente", empresa_id, linhas,
                  ["empresa_id", "codigo", "razao_social", "nome_fantasia", "documento"])
    resumo["clientes"] = len(linhas)
    passo("%d clientes/fornecedores." % len(linhas))

    # 5) Contas a pagar
    passo("Buscando contas a pagar...")
    pagar = cli.listar_tudo(
        "financas/contapagar/", "ListarContasPagar", {"apenas_importado_api": "N"},
        "conta_pagar_cadastro", registros_por_pagina=500,
        ao_progredir=lambda p, tp, acc, tot: passo(
            "Contas a pagar: %d/%s (pagina %d/%d)" % (acc, tot, p, tp)),
    )
    linhas = [_mapear_titulo(empresa_id, "pagar", t, mapa_cc) for t in pagar]
    db.substituir_titulos(empresa_id, "pagar", linhas, _COLUNAS_TITULO)
    resumo["contas_a_pagar"] = len(linhas)
    passo("%d contas a pagar." % len(linhas))

    # 6) Contas a receber
    passo("Buscando contas a receber...")
    receber = cli.listar_tudo(
        "financas/contareceber/", "ListarContasReceber", {"apenas_importado_api": "N"},
        "conta_receber_cadastro", registros_por_pagina=500,
        ao_progredir=lambda p, tp, acc, tot: passo(
            "Contas a receber: %d/%s (pagina %d/%d)" % (acc, tot, p, tp)),
    )
    linhas = [_mapear_titulo(empresa_id, "receber", t, mapa_cc) for t in receber]
    db.substituir_titulos(empresa_id, "receber", linhas, _COLUNAS_TITULO)
    resumo["contas_a_receber"] = len(linhas)
    passo("%d contas a receber." % len(linhas))

    # 7) Orcamento de caixa (previsto x realizado do OMIE) — ano anterior e atual
    passo("Buscando orcamento de caixa...")
    ano_atual = datetime.now().year
    total_orc = 0
    for ano in (ano_atual - 1, ano_atual):
        linhas_orc = []
        falhou = False
        for mes in range(1, 13):
            try:
                r = cli.chamar("financas/caixa/", "ListarOrcamentos", {"nAno": ano, "nMes": mes})
            except SemRegistros:
                continue   # mes sem orcamento cadastrado — segue
            except OmieError:
                falhou = True   # falha real da API: NAO apagar o orcamento ja sincronizado
                break
            for o in (r.get("ListaOrcamentos") or []):
                if not o.get("cCodCateg"):
                    continue
                realizado = o.get("nValorRealilzado")   # typo oficial da API
                if realizado is None:
                    realizado = o.get("nValorRealizado")
                desc = o.get("cDesCateg") or ""
                linhas_orc.append({
                    "empresa_id": empresa_id,
                    "empresa_real": holding.empresa_real(empresa_id, desc),
                    "ano": ano, "mes": mes,
                    "cod_categoria": o.get("cCodCateg"),
                    "descricao": desc,
                    "valor_previsto": num(o.get("nValorPrevisto")),
                    "valor_realizado_omie": num(realizado),
                })
        if not falhou:
            db.substituir_orcamento(empresa_id, ano, linhas_orc)
            total_orc += len(linhas_orc)
    resumo["orcamentos"] = total_orc
    passo("%d linhas de orcamento." % total_orc)

    db.registrar_sync(empresa_id, _agora(), resumo)
    return resumo


_COLUNAS_TITULO = [
    "empresa_id", "empresa_real", "tipo", "codigo", "cod_cliente", "ncodcc", "cod_categoria",
    "numero_documento", "numero_parcela", "tipo_documento",
    "data_emissao", "data_vencimento", "data_previsao", "data_registro",
    "valor", "status", "observacao",
]


def _mapear_titulo(empresa_id, tipo, t, mapa_cc=None):
    # categoria principal: campo direto ou a primeira do rateio
    cod_cat = t.get("codigo_categoria")
    if not cod_cat:
        cats = t.get("categorias") or []
        if cats:
            cod_cat = cats[0].get("codigo_categoria")
    # data "registro": entrada (pagar) ou registro (receber)
    data_reg = t.get("data_entrada") or t.get("data_registro")
    return {
        "empresa_id": empresa_id,
        "empresa_real": holding.empresa_real(empresa_id, (mapa_cc or {}).get(t.get("id_conta_corrente"), "")),
        "tipo": tipo,
        "codigo": t.get("codigo_lancamento_omie"),
        "cod_cliente": t.get("codigo_cliente_fornecedor"),
        "ncodcc": t.get("id_conta_corrente"),
        "cod_categoria": cod_cat,
        "numero_documento": t.get("numero_documento") or "",
        "numero_parcela": t.get("numero_parcela") or "",
        "tipo_documento": t.get("codigo_tipo_documento") or "",
        "data_emissao": para_iso(t.get("data_emissao")),
        "data_vencimento": para_iso(t.get("data_vencimento")),
        "data_previsao": para_iso(t.get("data_previsao")),
        "data_registro": para_iso(data_reg),
        "valor": num(t.get("valor_documento")),
        "status": (t.get("status_titulo") or "").strip().upper(),
        "observacao": t.get("observacao") or "",
    }

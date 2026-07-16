# -*- coding: utf-8 -*-
"""Cliente da API REST do OMIE (somente biblioteca padrao do Python).

A API do OMIE recebe POST JSON em https://app.omie.com.br/api/v1/<modulo>/
com o corpo {call, app_key, app_secret, param:[...]} e responde JSON.
Erros vem no campo 'faultstring'. Possui limite de requisicoes, entao
fazemos uma pequena pausa entre chamadas e re-tentamos erros transitorios.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

BASE_URL = "https://app.omie.com.br/api/v1/"

# Trechos de faultstring que indicam erro transitorio (vale a pena re-tentar)
_TRANSITORIOS = (
    "redundante", "Consumo indevido", "tente novamente", "timeout", "Timeout",
    "522", "523", "525", "500 Internal", "indisponivel", "indisponível",
)
# Trechos que indicam "fim da paginacao" (nao e erro de verdade)
_SEM_REGISTROS = ("nao existem registros", "não existem registros", "registros para a pagina",
                   "registros para a página")


class OmieError(Exception):
    def __init__(self, mensagem, codigo=None, payload=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.payload = payload


class SemRegistros(OmieError):
    """Levantado quando a pagina solicitada nao tem registros (fim dos dados)."""


class OmieClient:
    def __init__(self, app_key, app_secret, pausa=0.4, max_tentativas=5, timeout=120):
        self.app_key = app_key
        self.app_secret = app_secret
        self.pausa = pausa
        self.max_tentativas = max_tentativas
        self.timeout = timeout

    def chamar(self, caminho, metodo, param):
        """Faz uma chamada a API. 'caminho' ex.: 'financas/contapagar/'."""
        url = BASE_URL + caminho
        corpo = json.dumps({
            "call": metodo,
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [param],
        }).encode("utf-8")

        ultimo_erro = None
        for tentativa in range(1, self.max_tentativas + 1):
            time.sleep(self.pausa)
            req = urllib.request.Request(url, data=corpo, headers={
                "Content-Type": "application/json",
                "User-Agent": "RelatorioOmie/1.0",
            })
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    dados = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                texto = e.read().decode("utf-8", "replace")
                ultimo_erro = OmieError("HTTP %s: %s" % (e.code, texto[:300]), e.code)
                if e.code in (425, 429, 500, 502, 503, 504):
                    time.sleep(self.pausa * tentativa * 3)
                    continue
                raise ultimo_erro
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                ultimo_erro = OmieError("Falha de conexao: %r" % e)
                time.sleep(self.pausa * tentativa * 2)
                continue

            # API respondeu 200 mas pode conter erro logico
            if isinstance(dados, dict) and dados.get("faultstring"):
                fault = str(dados.get("faultstring", ""))
                fault_baixo = fault.lower()
                if any(s.lower() in fault_baixo for s in _SEM_REGISTROS):
                    raise SemRegistros(fault, dados.get("faultcode"))
                if any(s.lower() in fault_baixo for s in _TRANSITORIOS):
                    ultimo_erro = OmieError(fault, dados.get("faultcode"))
                    time.sleep(self.pausa * tentativa * 3)
                    continue
                raise OmieError(fault, dados.get("faultcode"), dados)

            return dados

        raise ultimo_erro or OmieError("Falha desconhecida na API OMIE")

    def listar_tudo(self, caminho, metodo, param_base, chave_lista,
                    registros_por_pagina=500, ao_progredir=None, limite_paginas=None):
        """Percorre todas as paginas e retorna a lista completa de itens.

        chave_lista: nome da chave no JSON que contem a lista (ex.: 'conta_pagar_cadastro').
        ao_progredir(pagina, total_paginas, acumulado, total_registros): callback opcional.
        """
        pagina = 1
        itens = []
        total_paginas = 1
        while True:
            param = dict(param_base)
            param["pagina"] = pagina
            param["registros_por_pagina"] = registros_por_pagina
            try:
                dados = self.chamar(caminho, metodo, param)
            except SemRegistros:
                break
            lote = dados.get(chave_lista) or []
            itens.extend(lote)
            try:
                total_paginas = int(dados.get("total_de_paginas", 1) or 1)
            except (ValueError, TypeError):
                total_paginas = 1
            if ao_progredir:
                ao_progredir(pagina, total_paginas, len(itens), dados.get("total_de_registros"))
            if not lote or pagina >= total_paginas:
                break
            if limite_paginas and pagina >= limite_paginas:
                break
            pagina += 1
        return itens

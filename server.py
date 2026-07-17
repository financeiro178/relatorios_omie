# -*- coding: utf-8 -*-
"""Servidor do app Analise Financeira OMIE (standalone, multiusuario).

Relatorios financeiros emitidos a partir da API do OMIE, separados do app de
tesouraria (K Finserv). Backend em Python puro (biblioteca padrao).

- Login com senha (PBKDF2) + sessoes no servidor (cookie HttpOnly).
- Admin gerencia usuarios e contas OMIE; usuario comum ve as empresas atribuidas
  (nenhuma atribuida = ve todas).
- Credenciais OMIE (app_secret) ficam SO no servidor.
- Na primeira execucao, importa dados/usuarios ja sincronizados do app
  'relatorio omie' (se encontrado ao lado), para nao esperar um sync completo.
"""
from __future__ import annotations

import http.cookies
import json
import os
import secrets
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import auth
from database import DB
from omie_client import OmieError
from seed import seed_nomes
from sync import sincronizar_empresa
from util import slug

RAIZ = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(RAIZ, "static")
DATA_DIR = os.environ.get("DATA_DIR", RAIZ)                 # em nuvem: disco persistente
DB_PATH = os.path.join(DATA_DIR, "analise_omie.db")
CONFIG_PATH = os.path.join(RAIZ, "config.json")
# banco do app de tesouraria (K Finserv), usado so na importacao inicial
DB_ANTIGO = os.environ.get(
    "IMPORTAR_DB",
    os.path.join(os.path.dirname(RAIZ), "relatorio omie", "relatorio_omie.db"))
PORT = int(os.environ.get("PORT", os.environ.get("PORTA", "8766")))
HOST = os.environ.get("HOST", "0.0.0.0")
SESSAO_HORAS = int(os.environ.get("SESSAO_HORAS", "12"))
# DATABASE_URL definida => backend Postgres (persistencia definitiva na nuvem);
# ausente => SQLite local em DB_PATH, como sempre.
DATABASE_URL = os.environ.get("DATABASE_URL") or None
EM_NUVEM = bool(os.environ.get("RENDER") or os.environ.get("DATA_DIR") or DATABASE_URL)

TIPOS_CONTEUDO = {
    ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".ico": "image/x-icon",
}

# ------------------------------------------------------------------ estado global
os.makedirs(DATA_DIR, exist_ok=True)
db = DB(DB_PATH, DATABASE_URL)

_sync_lock = threading.Lock()
sync_status = {
    "rodando": False, "iniciado_em": None, "terminado_em": None, "empresa_atual": None,
    "mensagem": "Nunca sincronizado nesta sessao.", "erro": None,
    "concluidas": [], "total_empresas": 0, "resultado": {},
}

# protecao simples contra forca-bruta no login (em memoria)
_falhas = {}
_falhas_lock = threading.Lock()


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ bootstrap
def bootstrap():
    # 1) primeira execucao: importa dados ja sincronizados do app de tesouraria
    #    (somente no backend SQLite local; no Postgres nao ha arquivo antigo)
    if not db.pg and not db.tem_titulos():
        try:
            resumo = db.importar_de(DB_ANTIGO)
            if resumo:
                print(" Dados importados do app 'relatorio omie':",
                      json.dumps(resumo, ensure_ascii=False))
        except Exception as ex:  # noqa: BLE001
            print(" Aviso: falha ao importar banco antigo:", ex)

    # 2) importa credenciais para o banco (apenas se ainda nao tem nenhuma):
    #    - arquivo config.json (uso local)
    #    - variavel de ambiente CONFIG_JSON, mesmo formato do arquivo (nuvem SEM disco
    #      persistente, ex. Render Free: as credenciais voltam sozinhas a cada restart)
    if not db.listar_credenciais():
        cfg, origem = None, None
        if os.path.exists(CONFIG_PATH):
            try:
                cfg, origem = json.load(open(CONFIG_PATH, encoding="utf-8")), "config.json"
            except Exception as ex:  # noqa: BLE001
                print(" Aviso: falha ao ler config.json:", ex)
        elif os.environ.get("CONFIG_JSON"):
            try:
                cfg, origem = json.loads(os.environ["CONFIG_JSON"]), "variavel CONFIG_JSON"
            except Exception as ex:  # noqa: BLE001
                print(" Aviso: CONFIG_JSON invalida:", ex)
        if cfg:
            try:
                for e in cfg.get("empresas", []):
                    if e.get("app_key") and e.get("app_secret"):
                        eid = e.get("id") or slug(e.get("nome") or e["app_key"])
                        db.salvar_credencial(eid, e.get("nome") or eid, e["app_key"], e["app_secret"], agora())
                print(" Credenciais importadas de %s." % origem)
            except Exception as ex:  # noqa: BLE001
                print(" Aviso: falha ao importar credenciais:", ex)

    # 3) garante um usuario admin
    if db.contar_usuarios() == 0:
        login = (os.environ.get("ADMIN_LOGIN") or "admin").strip().lower()
        senha = os.environ.get("ADMIN_SENHA") or secrets.token_urlsafe(9)
        h, salt, it = auth.hash_senha(senha)
        db.criar_usuario("Administrador", login, h, salt, it, "admin", agora())
        print("=" * 60)
        print(" USUARIO ADMINISTRADOR CRIADO")
        print("   login:", login)
        if os.environ.get("ADMIN_SENHA"):
            print("   senha: (definida pela variavel ADMIN_SENHA)")
        else:
            print("   senha:", senha)
            print("   ^^^ ANOTE esta senha! (defina ADMIN_SENHA para fixar uma)")
        print("=" * 60)
    elif os.environ.get("ADMIN_SENHA"):
        # ADMIN_SENHA definida: garante que o login 'admin' exista com essa senha
        login = (os.environ.get("ADMIN_LOGIN") or "admin").strip().lower()
        u = db.obter_usuario_por_login(login)
        if u:
            db.definir_senha(u["id"], *auth.hash_senha(os.environ["ADMIN_SENHA"]))
        else:
            h, salt, it = auth.hash_senha(os.environ["ADMIN_SENHA"])
            db.criar_usuario("Administrador", login, h, salt, it, "admin", agora())

    # 4) nomes amigaveis + divisao da holding ROI por empresa real
    try:
        seed_nomes(db)
        db.reatribuir_holding()
    except Exception as ex:  # noqa: BLE001
        print(" Aviso: falha no seed/holding:", ex)

    db.limpar_sessoes_expiradas(agora())


def empresas_config():
    return [{"id": c["empresa_id"], "nome": c["nome"], "app_key": c["app_key"], "app_secret": c["app_secret"]}
            for c in db.listar_credenciais()]


def empresas_relatorio(user):
    """Empresas com dados (credencial propria OU titulos atribuidos) visiveis ao usuario."""
    if not user:
        return []
    cred = {c["empresa_id"] for c in db.listar_credenciais()}
    com_dados = set(db.empresas_com_titulos())
    fontes = sorted(cred | com_dados)
    if user["papel"] == "admin":
        return fontes
    atribuidas = set(db.empresas_do_usuario(user["id"]))
    if not atribuidas:          # nenhuma atribuida = acesso a todas
        return fontes
    return [e for e in fontes if e in atribuidas]


# ------------------------------------------------------------------ sincronizacao
def _rodar_sync(ids):
    cfgs = [e for e in empresas_config() if not ids or e["id"] in ids]
    sync_status.update({
        "rodando": True, "iniciado_em": agora(), "terminado_em": None, "erro": None,
        "concluidas": [], "total_empresas": len(cfgs), "resultado": {}, "mensagem": "Iniciando...",
    })
    try:
        for cfg in cfgs:
            sync_status["empresa_atual"] = cfg.get("nome") or cfg["id"]
            try:
                resumo = sincronizar_empresa(db, cfg, status=sync_status)
                sync_status["resultado"][cfg["id"]] = resumo
                sync_status["concluidas"].append(cfg["id"])
            except OmieError as e:
                sync_status["erro"] = "Erro em %s: %s" % (cfg.get("nome") or cfg["id"], e.mensagem)
                sync_status["resultado"][cfg["id"]] = {"erro": e.mensagem}
        db.reatribuir_holding()
        sync_status["mensagem"] = "Sincronizacao concluida."
    except Exception as e:  # noqa: BLE001
        sync_status["erro"] = repr(e)
        sync_status["mensagem"] = "Falha na sincronizacao."
    finally:
        sync_status["rodando"] = False
        sync_status["terminado_em"] = agora()
        sync_status["empresa_atual"] = None


def iniciar_sync(ids):
    with _sync_lock:
        if sync_status["rodando"]:
            return False
        threading.Thread(target=_rodar_sync, args=(ids,), daemon=True).start()
        return True


# ------------------------------------------------------------------ login throttle
def pode_tentar(chave):
    with _falhas_lock:
        reg = _falhas.get(chave)
        if not reg:
            return True
        return datetime.now().timestamp() >= reg[1]


def registrar_falha(chave):
    with _falhas_lock:
        cnt = (_falhas.get(chave, [0, 0])[0]) + 1
        bloqueio = datetime.now().timestamp() + min(300, (cnt - 4) * 30) if cnt >= 5 else 0
        _falhas[chave] = [cnt, bloqueio]


def limpar_falhas(chave):
    with _falhas_lock:
        _falhas.pop(chave, None)


# ------------------------------------------------------------------ filtros
def _lista(qs, chave):
    v = qs.get(chave, [""])[0]
    return [p for p in v.split(",") if p] if v else []


def _lista_int(qs, chave):
    out = []
    for p in _lista(qs, chave):
        try:
            out.append(int(p))
        except ValueError:
            pass
    return out


def montar_filtros(qs):
    return {
        "empresas": _lista(qs, "empresas"),
        "tipo": (qs.get("tipo", ["ambos"])[0] or "ambos"),
        "contas": _lista_int(qs, "contas"),
        "status": _lista(qs, "status"),
        "categorias": _lista(qs, "categorias"),
        "cliente": (int(qs["cliente"][0]) if qs.get("cliente", [""])[0].isdigit() else None),
        "campo_data": qs.get("campo_data", ["vencimento"])[0],
        "de": qs.get("de", [""])[0] or None, "ate": qs.get("ate", [""])[0] or None,
        "busca": qs.get("busca", [""])[0],
        "ordenar": qs.get("ordenar", ["vencimento"])[0], "dir": qs.get("dir", ["desc"])[0],
        "pagina": int(qs.get("pagina", ["1"])[0] or 1),
        "por_pagina": int(qs.get("por_pagina", ["100"])[0] or 100),
    }


# ------------------------------------------------------------------ handler
class Handler(BaseHTTPRequestHandler):
    server_version = "AnaliseOmie/1.0"
    user = None

    def log_message(self, *a):
        pass

    # ---- sessao / identidade
    def _cookies(self):
        bruto = self.headers.get("Cookie")
        if not bruto:
            return {}
        c = http.cookies.SimpleCookie()
        try:
            c.load(bruto)
        except http.cookies.CookieError:
            return {}
        return {k: m.value for k, m in c.items()}

    def resolver_usuario(self):
        sid = self._cookies().get("sid")
        if not sid:
            return None
        s = db.obter_sessao(auth.hash_token(sid))
        if not s:
            return None
        if s["expira_em"] < agora():
            db.excluir_sessao(s["token_hash"])
            return None
        u = db.obter_usuario(s["usuario_id"])
        return u if u and u["ativo"] else None

    def _ip(self):
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "?"

    def _https(self):
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _cookie_sessao(self, token, max_age):
        partes = ["sid=" + token, "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=" + str(max_age)]
        if self._https():
            partes.append("Secure")
        return "; ".join(partes)

    # ---- respostas
    def _enviar_json(self, obj, status=200, extra=None):
        corpo = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _enviar_bytes(self, corpo, tipo, status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, msg, status=400):
        self._enviar_json({"erro": msg}, status)

    def _redirect(self, destino):
        self.send_response(302)
        self.send_header("Location", destino)
        self.end_headers()

    def _corpo_json(self):
        tam = int(self.headers.get("Content-Length", 0) or 0)
        if not tam:
            return {}
        try:
            return json.loads(self.rfile.read(tam) or b"{}")
        except json.JSONDecodeError:
            return {}

    # filtros ja restritos as empresas permitidas
    def _filtros(self, qs):
        f = montar_filtros(qs)
        perm = set(empresas_relatorio(self.user))
        req = [e for e in f["empresas"] if e in perm] if f["empresas"] else list(perm)
        if not req:
            req = ["\x00sem-acesso"]   # garante que nao vaze nada
        f["empresas"] = req
        return f

    def _me(self):
        return {
            "usuario": {"id": self.user["id"], "nome": self.user["nome"],
                         "login": self.user["login"], "papel": self.user["papel"]},
            "empresas_permitidas": empresas_relatorio(self.user),
        }

    # ===================================================== GET
    def do_GET(self):
        self.user = self.resolver_usuario()
        u = urlparse(self.path)
        try:
            if u.path.startswith("/api/"):
                return self._api_get(u.path, parse_qs(u.query))
            return self._estatico(u.path)
        except OmieError as e:
            return self._erro("OMIE: " + e.mensagem, 502)
        except BrokenPipeError:
            return
        except Exception as e:  # noqa: BLE001
            return self._erro("Erro interno: %r" % e, 500)

    def _api_get(self, caminho, qs):
        if caminho == "/api/me":
            if not self.user:
                return self._erro("Nao autenticado", 401)
            return self._enviar_json(self._me())
        if not self.user:
            return self._erro("Nao autenticado", 401)

        if caminho == "/api/empresas":
            return self._enviar_json(self._empresas())
        if caminho == "/api/sync/status":
            return self._enviar_json(sync_status)
        if caminho == "/api/filtros":
            return self._enviar_json(db.filtros_disponiveis(self._filtros(qs)["empresas"]))
        if caminho == "/api/titulos":
            return self._enviar_json(db.consultar_titulos(self._filtros(qs)))
        if caminho == "/api/agrupado":
            por = qs.get("por", ["categoria"])[0]
            return self._enviar_json({"por": por, "grupos": db.agrupar(self._filtros(qs), por)})
        if caminho == "/api/dashboard":
            return self._enviar_json(self._dashboard(self._filtros(qs)))
        if caminho == "/api/dre":
            return self._enviar_json(db.dre(self._filtros(qs)))
        if caminho == "/api/orcado":
            try:
                ano = int(qs.get("ano", [""])[0] or datetime.now().year)
            except ValueError:
                ano = datetime.now().year
            # respeita o filtro de empresas selecionado (ja restrito as permitidas)
            base = qs.get("base", [None])[0]
            return self._enviar_json(db.previsto_realizado(self._filtros(qs)["empresas"], ano, base))
        if caminho == "/api/export.csv":
            return self._exportar_csv(self._filtros(qs))
        if caminho == "/api/admin/dados":
            if self.user["papel"] != "admin":
                return self._erro("Acesso restrito ao administrador.", 403)
            return self._enviar_json(self._admin_dados())
        return self._erro("Rota nao encontrada: " + caminho, 404)

    def _empresas(self):
        perm = set(empresas_relatorio(self.user))
        creds = {c["empresa_id"]: c for c in db.listar_credenciais()}
        sync = {e["empresa_id"]: e for e in db.empresas()}
        lista = []
        for eid in perm:
            base = {"empresa_id": eid, "nome": creds.get(eid, {}).get("nome") or eid,
                    "razao_social": creds.get(eid, {}).get("nome") or eid}
            lista.append({**base, **sync.get(eid, {})})
        lista.sort(key=lambda e: (e.get("razao_social") or "").lower())
        return {"empresas": lista, "config": [{"id": e["empresa_id"], "nome": e.get("nome")} for e in lista]}

    def _dashboard(self, f):
        base = db.consultar_titulos({**f, "por_pagina": 1, "pagina": 1})
        return {
            "resumo": base["resumo"],
            "por_conta": db.agrupar(f, "conta"),
            "por_categoria": db.agrupar(f, "categoria"),
            "por_empresa": db.agrupar(f, "empresa"),
            "por_mes": sorted(db.agrupar(f, "mes"), key=lambda g: g["chave"] or ""),
        }

    def _admin_dados(self):
        creds = db.listar_credenciais()
        sync = {e["empresa_id"]: e for e in db.empresas()}
        emp = []
        for c in creds:
            s = sync.get(c["empresa_id"], {})
            emp.append({"empresa_id": c["empresa_id"], "nome": c["nome"], "app_key": c["app_key"],
                        "tem_secret": bool(c["app_secret"]), "razao_social": s.get("razao_social"),
                        "ultimo_sync": s.get("ultimo_sync"), "qtd_titulos": s.get("qtd_titulos", 0)})
        return {"usuarios": db.listar_usuarios(), "empresas": emp,
                "empresas_relatorio": empresas_relatorio(self.user)}

    def _exportar_csv(self, f):
        linhas = db.exportar_linhas(f)
        cab = ["Empresa", "Conta", "Tipo", "Status", "Cliente/Fornecedor", "Categoria",
               "Documento", "Parcela", "Emissao", "Vencimento", "Previsao", "Valor"]

        def br_data(iso):
            if not iso:
                return ""
            a, m, d = iso.split("-")
            return "%s/%s/%s" % (d, m, a)

        def esc(s):
            s = "" if s is None else str(s)
            return '"' + s.replace('"', '""') + '"' if (";" in s or '"' in s or "\n" in s) else s

        out = [";".join(cab)]
        for r in linhas:
            out.append(";".join([
                esc(r["empresa"]), esc(r["conta"]), "Pagar" if r["tipo"] == "pagar" else "Receber",
                esc(r["status"]), esc(r["cliente"]), esc(r["categoria"]),
                esc(r["numero_documento"]), esc(r["numero_parcela"]),
                br_data(r["data_emissao"]), br_data(r["data_vencimento"]), br_data(r["data_previsao"]),
                ("%.2f" % (r["valor"] or 0)).replace(".", ","),
            ]))
        corpo = ("﻿" + "\r\n".join(out)).encode("utf-8")
        nome = "analise_omie_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S")
        self._enviar_bytes(corpo, "text/csv; charset=utf-8",
                           extra={"Content-Disposition": 'attachment; filename="%s"' % nome})

    def _estatico(self, caminho):
        # app exige login; login.html e assets sao publicos
        if caminho in ("/", "", "/index.html"):
            if not self.user:
                return self._redirect("/login")
            rel = "index.html"
        elif caminho in ("/login", "/login.html"):
            rel = "login.html"
        else:
            rel = caminho.lstrip("/")
        destino = os.path.normpath(os.path.join(STATIC, rel))
        if not destino.startswith(STATIC) or not os.path.isfile(destino):
            return self._erro("Arquivo nao encontrado: " + caminho, 404)
        with open(destino, "rb") as fp:
            corpo = fp.read()
        self._enviar_bytes(corpo, TIPOS_CONTEUDO.get(os.path.splitext(destino)[1].lower(), "application/octet-stream"))

    # ===================================================== POST
    def do_POST(self):
        self.user = self.resolver_usuario()
        u = urlparse(self.path)
        try:
            if u.path == "/api/login":
                return self._login(self._corpo_json())
            if u.path == "/api/logout":
                return self._logout()
            if not self.user:
                return self._erro("Nao autenticado", 401)
            if u.path == "/api/sync":
                return self._sync(self._corpo_json())
            if u.path.startswith("/api/admin/"):
                if self.user["papel"] != "admin":
                    return self._erro("Acesso restrito ao administrador.", 403)
                d = self._corpo_json()
                if u.path == "/api/admin/usuario/salvar":
                    return self._admin_usuario_salvar(d)
                if u.path == "/api/admin/usuario/excluir":
                    return self._admin_usuario_excluir(d)
                if u.path == "/api/admin/empresa/salvar":
                    return self._admin_empresa_salvar(d)
                if u.path == "/api/admin/empresa/excluir":
                    return self._admin_empresa_excluir(d)
            return self._erro("Rota nao encontrada: " + u.path, 404)
        except Exception as e:  # noqa: BLE001
            return self._erro("Erro interno: %r" % e, 500)

    def _login(self, d):
        login = (d.get("login") or "").strip().lower()
        senha = d.get("senha") or ""
        chave = (self._ip() + "|" + login)
        if not pode_tentar(chave):
            return self._erro("Muitas tentativas. Aguarde alguns minutos.", 429)
        u = db.obter_usuario_por_login(login)
        if not u or not u["ativo"] or not auth.verificar_senha(senha, u["senha_hash"], u["salt"], u["iteracoes"]):
            registrar_falha(chave)
            return self._erro("Login ou senha invalidos.", 401)
        limpar_falhas(chave)
        token = auth.novo_token()
        expira = (datetime.now() + timedelta(hours=SESSAO_HORAS)).strftime("%Y-%m-%d %H:%M:%S")
        db.criar_sessao(auth.hash_token(token), u["id"], agora(), expira, self._ip())
        db.marcar_acesso(u["id"], agora())
        self._enviar_json({"ok": True, "usuario": {"nome": u["nome"], "papel": u["papel"]}},
                          extra={"Set-Cookie": self._cookie_sessao(token, SESSAO_HORAS * 3600)})

    def _logout(self):
        sid = self._cookies().get("sid")
        if sid:
            db.excluir_sessao(auth.hash_token(sid))
        self._enviar_json({"ok": True}, extra={"Set-Cookie": "sid=; Path=/; HttpOnly; Max-Age=0"})

    def _sync(self, d):
        # qualquer usuario autenticado pode atualizar os dados (sync roda por credencial)
        ids = [e["id"] for e in empresas_config()]
        pedidos = [e for e in (d.get("empresas") or []) if e in ids]
        if iniciar_sync(pedidos or ids):
            return self._enviar_json({"ok": True, "mensagem": "Sincronizacao iniciada."})
        return self._enviar_json({"ok": False, "mensagem": "Ja existe uma sincronizacao em andamento."}, 409)

    # ---- admin: usuarios
    def _admin_usuario_salvar(self, d):
        nome = (d.get("nome") or "").strip()
        papel = d.get("papel") if d.get("papel") in ("admin", "user") else "user"
        empresas = [e for e in (d.get("empresas") or []) if isinstance(e, str)]
        senha = d.get("senha") or ""
        uid = d.get("id")
        if uid:
            alvo = db.obter_usuario(int(uid))
            if not alvo:
                return self._erro("Usuario nao encontrado.", 404)
            if alvo["papel"] == "admin" and (papel != "admin" or not d.get("ativo", 1)):
                if len([x for x in db.listar_usuarios() if x["papel"] == "admin" and x["ativo"]]) <= 1:
                    return self._erro("Nao e possivel rebaixar/desativar o ultimo administrador.", 400)
            db.atualizar_usuario(int(uid), nome or alvo["nome"], papel, d.get("ativo", 1))
            if senha:
                if not auth.senha_forte(senha):
                    return self._erro("Senha muito curta (minimo 6 caracteres).", 400)
                db.definir_senha(int(uid), *auth.hash_senha(senha))
            db.definir_empresas_usuario(int(uid), empresas)
            return self._enviar_json({"ok": True})
        # novo usuario
        login = (d.get("login") or "").strip().lower()
        if not login:
            return self._erro("Informe o login.", 400)
        if db.obter_usuario_por_login(login):
            return self._erro("Ja existe um usuario com esse login.", 400)
        if not auth.senha_forte(senha):
            return self._erro("Senha muito curta (minimo 6 caracteres).", 400)
        nid = db.criar_usuario(nome or login, login, *auth.hash_senha(senha), papel, agora())
        db.definir_empresas_usuario(nid, empresas)
        return self._enviar_json({"ok": True, "id": nid})

    def _admin_usuario_excluir(self, d):
        uid = int(d.get("id") or 0)
        if uid == self.user["id"]:
            return self._erro("Voce nao pode excluir o proprio usuario.", 400)
        alvo = db.obter_usuario(uid)
        if not alvo:
            return self._erro("Usuario nao encontrado.", 404)
        if alvo["papel"] == "admin" and len([x for x in db.listar_usuarios() if x["papel"] == "admin" and x["ativo"]]) <= 1:
            return self._erro("Nao e possivel excluir o ultimo administrador.", 400)
        db.excluir_usuario(uid)
        return self._enviar_json({"ok": True})

    # ---- admin: empresas (contas OMIE)
    def _admin_empresa_salvar(self, d):
        eid = slug(d.get("id") or d.get("nome") or "")
        nome = (d.get("nome") or "").strip()
        app_key = (d.get("app_key") or "").strip()
        secret_novo = (d.get("app_secret") or "").strip()
        if not eid or not app_key:
            return self._erro("Informe identificador e app_key.", 400)
        existente = db.obter_credencial(eid)
        secret = secret_novo or (existente["app_secret"] if existente else "")
        if not secret:
            return self._erro("Informe o app_secret.", 400)
        db.salvar_credencial(eid, nome or eid, app_key, secret, agora())
        return self._enviar_json({"ok": True, "id": eid})

    def _admin_empresa_excluir(self, d):
        eid = d.get("id")
        if not eid:
            return self._erro("Informe o identificador.", 400)
        db.excluir_credencial(eid)
        return self._enviar_json({"ok": True})


def main():
    bootstrap()
    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 60)
    print(" Analise Financeira OMIE  (app standalone)")
    print(" Ouvindo em %s:%d" % (HOST, PORT))
    print(" Banco:", "Postgres (DATABASE_URL)" if db.pg else "SQLite em " + DB_PATH)
    print(" Empresas (contas OMIE):", len(empresas_config()))
    print(" Usuarios cadastrados:", db.contar_usuarios())
    print("=" * 60)
    if not EM_NUVEM and os.environ.get("NAO_ABRIR") != "1":
        threading.Timer(1.0, lambda: webbrowser.open("http://localhost:%d/" % PORT)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
        servidor.shutdown()
    finally:
        db.fechar()


if __name__ == "__main__":
    main()

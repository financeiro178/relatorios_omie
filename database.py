# -*- coding: utf-8 -*-
"""Camada de banco de dados do app Analise Financeira OMIE (SQLite, biblioteca padrao).

Guarda o que foi sincronizado do OMIE e responde as consultas dos relatorios.
Todas as tabelas tem 'empresa_id' para suportar varias empresas ao mesmo tempo.
Este app e independente do K Finserv Tesouraria: possui banco, usuarios e sessoes proprios.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

import holding

SCHEMA = """
CREATE TABLE IF NOT EXISTS empresa (
    empresa_id    TEXT PRIMARY KEY,
    nome          TEXT,            -- rotulo definido no config.json / seed
    razao_social  TEXT,
    nome_fantasia TEXT,
    cnpj          TEXT,
    cidade        TEXT,
    estado        TEXT,
    atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS conta_corrente (
    empresa_id    TEXT,
    ncodcc        INTEGER,
    descricao     TEXT,
    tipo          TEXT,
    codigo_banco  TEXT,
    agencia       TEXT,
    numero        TEXT,
    inativo       TEXT,
    saldo_inicial REAL,
    PRIMARY KEY (empresa_id, ncodcc)
);

CREATE TABLE IF NOT EXISTS cliente (
    empresa_id    TEXT,
    codigo        INTEGER,
    razao_social  TEXT,
    nome_fantasia TEXT,
    documento     TEXT,
    PRIMARY KEY (empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS categoria (
    empresa_id TEXT,
    codigo     TEXT,
    descricao  TEXT,
    natureza   TEXT,
    PRIMARY KEY (empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS titulo (
    empresa_id       TEXT,      -- credencial OMIE de origem
    empresa_real     TEXT,      -- empresa real (holding ROI dividida por conta)
    tipo             TEXT,      -- 'pagar' ou 'receber'
    codigo           INTEGER,   -- codigo_lancamento_omie
    cod_cliente      INTEGER,
    ncodcc           INTEGER,
    cod_categoria    TEXT,
    numero_documento TEXT,
    numero_parcela   TEXT,
    tipo_documento   TEXT,
    data_emissao     TEXT,      -- ISO aaaa-mm-dd
    data_vencimento  TEXT,
    data_previsao    TEXT,
    data_registro    TEXT,
    valor            REAL,
    status           TEXT,
    observacao       TEXT,
    PRIMARY KEY (empresa_id, tipo, codigo)
);
CREATE INDEX IF NOT EXISTS idx_titulo_emp        ON titulo(empresa_id);
CREATE INDEX IF NOT EXISTS idx_titulo_real       ON titulo(empresa_real);
CREATE INDEX IF NOT EXISTS idx_titulo_venc       ON titulo(data_vencimento);
CREATE INDEX IF NOT EXISTS idx_titulo_status     ON titulo(status);
CREATE INDEX IF NOT EXISTS idx_titulo_conta      ON titulo(ncodcc);
CREATE INDEX IF NOT EXISTS idx_titulo_categoria  ON titulo(cod_categoria);

CREATE TABLE IF NOT EXISTS sync_info (
    empresa_id  TEXT PRIMARY KEY,
    ultimo_sync TEXT,
    resumo      TEXT
);

CREATE TABLE IF NOT EXISTS usuario (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT,
    login         TEXT UNIQUE NOT NULL,
    senha_hash    TEXT NOT NULL,
    salt          TEXT NOT NULL,
    iteracoes     INTEGER NOT NULL,
    papel         TEXT NOT NULL DEFAULT 'user',   -- 'admin' | 'user'
    ativo         INTEGER NOT NULL DEFAULT 1,
    criado_em     TEXT,
    ultimo_acesso TEXT
);

CREATE TABLE IF NOT EXISTS usuario_empresa (
    usuario_id INTEGER NOT NULL,
    empresa_id TEXT NOT NULL,
    PRIMARY KEY (usuario_id, empresa_id)
);

CREATE TABLE IF NOT EXISTS sessao (
    token_hash TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    criado_em  TEXT,
    expira_em  TEXT,
    ip         TEXT
);

CREATE TABLE IF NOT EXISTS empresa_credencial (
    empresa_id TEXT PRIMARY KEY,
    nome       TEXT,
    app_key    TEXT,
    app_secret TEXT,
    criado_em  TEXT
);

CREATE TABLE IF NOT EXISTS app_config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""

# Coluna SQL por campo de data escolhido no filtro (whitelist anti-injecao)
CAMPO_DATA = {
    "vencimento": "t.data_vencimento",
    "emissao": "t.data_emissao",
    "previsao": "t.data_previsao",
    "registro": "t.data_registro",
}

# Colunas permitidas para ordenacao (whitelist anti-injecao)
ORDENAR = {
    "vencimento": "t.data_vencimento",
    "emissao": "t.data_emissao",
    "valor": "t.valor",
    "status": "t.status",
    "empresa": "e.razao_social",
    "conta": "cc.descricao",
    "cliente": "cl.razao_social",
    "categoria": "cat.descricao",
    "tipo": "t.tipo",
}

# JOINs usados em todas as consultas de titulo
# empresa e atribuida por empresa_real (holding ROI dividida); cliente/categoria/conta
# ficam no namespace da credencial (t.empresa_id)
_JOINS = """
FROM titulo t
LEFT JOIN empresa e        ON e.empresa_id  = t.empresa_real
LEFT JOIN conta_corrente cc ON cc.empresa_id = t.empresa_id AND cc.ncodcc  = t.ncodcc
LEFT JOIN cliente cl       ON cl.empresa_id = t.empresa_id AND cl.codigo  = t.cod_cliente
LEFT JOIN categoria cat    ON cat.empresa_id = t.empresa_id AND cat.codigo = t.cod_categoria
"""


class DB:
    def __init__(self, caminho):
        self.caminho = caminho
        self._lock = threading.Lock()
        self.con = sqlite3.connect(caminho, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=NORMAL")
        self.con.executescript(SCHEMA)
        self.con.commit()

    # ---------- escrita (sincronizacao) ----------
    def upsert_empresa(self, empresa_id, dados):
        with self._lock:
            self.con.execute(
                """INSERT INTO empresa (empresa_id, nome, razao_social, nome_fantasia, cnpj, cidade, estado, atualizado_em)
                   VALUES (:empresa_id, :nome, :razao_social, :nome_fantasia, :cnpj, :cidade, :estado, :atualizado_em)
                   ON CONFLICT(empresa_id) DO UPDATE SET
                     nome=excluded.nome, razao_social=excluded.razao_social,
                     nome_fantasia=excluded.nome_fantasia, cnpj=excluded.cnpj,
                     cidade=excluded.cidade, estado=excluded.estado,
                     atualizado_em=excluded.atualizado_em""",
                {"empresa_id": empresa_id, **dados},
            )
            self.con.commit()

    def upsert_empresa_basica(self, empresa_id, dados):
        """Garante a empresa com nome amigavel (sem depender de sync do OMIE)."""
        with self._lock:
            existe = self.con.execute("SELECT 1 FROM empresa WHERE empresa_id=?", (empresa_id,)).fetchone()
            if not existe:
                self.con.execute(
                    "INSERT INTO empresa (empresa_id, nome, razao_social, cnpj) VALUES (?,?,?,?)",
                    (empresa_id, dados.get("nome"), dados.get("razao_social") or dados.get("nome"), dados.get("cnpj") or ""))
            else:
                self.con.execute(
                    """UPDATE empresa SET nome=COALESCE(NULLIF(nome,''),?),
                                          razao_social=COALESCE(NULLIF(razao_social,''),?)
                       WHERE empresa_id=?""",
                    (dados.get("nome"), dados.get("razao_social") or dados.get("nome"), empresa_id))
            self.con.commit()

    def substituir(self, tabela, empresa_id, linhas, colunas):
        """Apaga os dados da empresa numa tabela e insere o lote novo (full refresh)."""
        with self._lock:
            cur = self.con.cursor()
            cur.execute("DELETE FROM %s WHERE empresa_id = ?" % tabela, (empresa_id,))
            if linhas:
                placeholders = ",".join([":" + c for c in colunas])
                sql = "INSERT INTO %s (%s) VALUES (%s)" % (tabela, ",".join(colunas), placeholders)
                cur.executemany(sql, linhas)
            self.con.commit()

    def substituir_titulos(self, empresa_id, tipo, linhas, colunas):
        with self._lock:
            cur = self.con.cursor()
            cur.execute("DELETE FROM titulo WHERE empresa_id = ? AND tipo = ?", (empresa_id, tipo))
            if linhas:
                placeholders = ",".join([":" + c for c in colunas])
                sql = "INSERT INTO titulo (%s) VALUES (%s)" % (",".join(colunas), placeholders)
                cur.executemany(sql, linhas)
            self.con.commit()

    def registrar_sync(self, empresa_id, quando, resumo):
        with self._lock:
            self.con.execute(
                """INSERT INTO sync_info (empresa_id, ultimo_sync, resumo)
                   VALUES (?, ?, ?)
                   ON CONFLICT(empresa_id) DO UPDATE SET ultimo_sync=excluded.ultimo_sync, resumo=excluded.resumo""",
                (empresa_id, quando, json.dumps(resumo, ensure_ascii=False)),
            )
            self.con.commit()

    def reatribuir_holding(self):
        """Atribui empresa_real aos titulos das credenciais holding (ROI) pelo prefixo da conta."""
        with self._lock:
            for cred in holding.CREDENCIAIS_HOLDING:
                contas = self.con.execute("SELECT ncodcc, descricao FROM conta_corrente WHERE empresa_id=?", (cred,)).fetchall()
                for c in contas:
                    self.con.execute("UPDATE titulo SET empresa_real=? WHERE empresa_id=? AND ncodcc=?",
                                     (holding.empresa_real(cred, c["descricao"]), cred, c["ncodcc"]))
                self.con.execute("UPDATE titulo SET empresa_real=? WHERE empresa_id=? AND (empresa_real IS NULL OR empresa_real='')",
                                 (cred, cred))
            self.con.execute("UPDATE titulo SET empresa_real=empresa_id WHERE empresa_real IS NULL OR empresa_real=''")
            self.con.commit()

    # ---------- leitura ----------
    def empresas(self):
        rows = self.con.execute(
            """SELECT e.*, s.ultimo_sync, s.resumo,
                      (SELECT COUNT(*) FROM titulo t WHERE t.empresa_real = e.empresa_id) AS qtd_titulos
               FROM empresa e LEFT JOIN sync_info s ON s.empresa_id = e.empresa_id
               ORDER BY e.razao_social"""
        ).fetchall()
        return [dict(r) for r in rows]

    def filtros_disponiveis(self, empresas):
        """Contas, status e categorias existentes para as empresas selecionadas."""
        ph, params = _in("t.empresa_real", empresas)
        cond = ("WHERE " + ph) if ph else ""
        contas = self.con.execute(
            """SELECT DISTINCT cc.ncodcc AS ncodcc, cc.descricao AS descricao, cc.empresa_id AS empresa_id
               FROM titulo t JOIN conta_corrente cc ON cc.empresa_id=t.empresa_id AND cc.ncodcc=t.ncodcc
               %s ORDER BY cc.descricao""" % cond, params).fetchall()
        status = self.con.execute(
            "SELECT DISTINCT status FROM titulo t %s ORDER BY status" % cond, params).fetchall()
        categorias = self.con.execute(
            """SELECT DISTINCT t.cod_categoria AS codigo, cat.descricao AS descricao
               FROM titulo t LEFT JOIN categoria cat ON cat.empresa_id=t.empresa_id AND cat.codigo=t.cod_categoria
               %s ORDER BY cat.descricao""" % cond, params).fetchall()
        return {
            "contas": [dict(r) for r in contas],
            "status": [r["status"] for r in status if r["status"]],
            "categorias": [dict(r) for r in categorias if r["codigo"]],
        }

    def consultar_titulos(self, f):
        where, params = _where(f)
        resumo = self._resumo(where, params)
        col = ORDENAR.get(f.get("ordenar"), "t.data_vencimento")
        direcao = "DESC" if str(f.get("dir", "desc")).lower() == "desc" else "ASC"
        por_pagina = max(1, min(int(f.get("por_pagina", 100)), 1000))
        pagina = max(1, int(f.get("pagina", 1)))
        offset = (pagina - 1) * por_pagina
        sql = """
            SELECT t.empresa_real AS empresa_id, t.tipo, t.codigo, t.numero_documento, t.numero_parcela,
                   t.data_emissao, t.data_vencimento, t.data_previsao, t.data_registro,
                   t.valor, t.status, t.tipo_documento, t.cod_categoria,
                   e.razao_social AS empresa_razao, e.nome_fantasia AS empresa_fantasia,
                   cc.descricao AS conta_nome, cc.codigo_banco AS conta_banco,
                   cl.razao_social AS cliente_razao, cl.nome_fantasia AS cliente_fantasia,
                   cat.descricao AS categoria_nome
            %s %s
            ORDER BY %s %s, t.codigo %s
            LIMIT ? OFFSET ?
        """ % (_JOINS, where, col, direcao, direcao)
        linhas = self.con.execute(sql, params + [por_pagina, offset]).fetchall()
        return {
            "linhas": [dict(r) for r in linhas],
            "resumo": resumo,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_registros": resumo["total_registros"],
            "total_paginas": max(1, -(-resumo["total_registros"] // por_pagina)),
        }

    def _resumo(self, where, params):
        sql = """SELECT t.tipo AS tipo, t.status AS status, COUNT(*) AS n, COALESCE(SUM(t.valor),0) AS soma
                 %s %s GROUP BY t.tipo, t.status""" % (_JOINS, where)
        linhas = self.con.execute(sql, params).fetchall()
        total = 0
        soma_pagar = soma_receber = 0.0
        por_status = {}
        for r in linhas:
            total += r["n"]
            if r["tipo"] == "pagar":
                soma_pagar += r["soma"] or 0
            else:
                soma_receber += r["soma"] or 0
            chave = "%s|%s" % (r["tipo"], r["status"] or "")
            por_status[chave] = {"tipo": r["tipo"], "status": r["status"] or "(sem status)",
                                 "n": r["n"], "soma": r["soma"] or 0}
        return {
            "total_registros": total,
            "soma_pagar": soma_pagar,
            "soma_receber": soma_receber,
            "saldo": soma_receber - soma_pagar,
            "por_status": list(por_status.values()),
        }

    def agrupar(self, f, por):
        """Agrupa os titulos filtrados por: categoria | conta | cliente | mes | empresa | status."""
        where, params = _where(f)
        campo_mes = CAMPO_DATA.get(f.get("campo_data"), "t.data_vencimento")
        mapa = {
            "categoria": ("t.cod_categoria", "COALESCE(cat.descricao, t.cod_categoria, '(sem categoria)')"),
            "conta": ("t.ncodcc", "COALESCE(cc.descricao, '(sem conta)')"),
            "cliente": ("t.cod_cliente", "COALESCE(cl.razao_social, cl.nome_fantasia, '(sem cadastro)')"),
            "empresa": ("t.empresa_real", "COALESCE(e.razao_social, e.nome, t.empresa_real)"),
            "status": ("t.status", "COALESCE(t.status, '(sem status)')"),
            "mes": ("substr(%s,1,7)" % campo_mes, "substr(%s,1,7)" % campo_mes),
        }
        chave_sql, label_sql = mapa.get(por, mapa["categoria"])
        sql = """
            SELECT {chave} AS chave, {label} AS label,
                   COUNT(*) AS n,
                   COALESCE(SUM(CASE WHEN t.tipo='pagar'   THEN t.valor END),0) AS soma_pagar,
                   COALESCE(SUM(CASE WHEN t.tipo='receber' THEN t.valor END),0) AS soma_receber
            {joins} {where}
            GROUP BY {chave}
            ORDER BY (COALESCE(SUM(t.valor),0)) DESC
        """.format(chave=chave_sql, label=label_sql, joins=_JOINS, where=where)
        linhas = self.con.execute(sql, params).fetchall()
        res = []
        for r in linhas:
            d = dict(r)
            d["saldo"] = (d["soma_receber"] or 0) - (d["soma_pagar"] or 0)
            res.append(d)
        return res

    def dre(self, f):
        """DRE gerencial: receitas (a receber) e despesas (a pagar) por categoria, mes a mes."""
        where, params = _where(f)
        campo = CAMPO_DATA.get(f.get("campo_data"), "t.data_vencimento")
        cond = (where + " AND " if where else "WHERE ") + "%s IS NOT NULL AND %s <> ''" % (campo, campo)
        sql = ("SELECT substr(%s,1,7) AS mes, t.tipo AS tipo, "
               "COALESCE(cat.descricao, t.cod_categoria, '(sem categoria)') AS categoria, "
               "COALESCE(SUM(t.valor),0) AS soma %s %s GROUP BY mes, t.tipo, categoria ORDER BY mes"
               % (campo, _JOINS, cond))
        rows = self.con.execute(sql, params).fetchall()
        meses = sorted({r["mes"] for r in rows if r["mes"]})
        rec, desp = {}, {}
        for r in rows:
            (rec if r["tipo"] == "receber" else desp).setdefault(r["categoria"], {})[r["mes"]] = r["soma"]

        def montar(d):
            linhas = [{"categoria": c, "valores": v, "total": sum(v.values())} for c, v in d.items()]
            linhas.sort(key=lambda x: -x["total"])
            if len(linhas) > 25:
                resto = linhas[25:]
                outras = {}
                for l in resto:
                    for m, v in l["valores"].items():
                        outras[m] = outras.get(m, 0) + v
                linhas = linhas[:25] + [{"categoria": "Outras (%d categorias)" % len(resto),
                                          "valores": outras, "total": sum(outras.values())}]
            return linhas
        receitas, despesas = montar(rec), montar(desp)
        tot_rec = {m: round(sum(l["valores"].get(m, 0) for l in receitas), 2) for m in meses}
        tot_desp = {m: round(sum(l["valores"].get(m, 0) for l in despesas), 2) for m in meses}
        resultado = {m: round(tot_rec.get(m, 0) - tot_desp.get(m, 0), 2) for m in meses}
        return {
            "meses": meses, "receitas": receitas, "despesas": despesas,
            "total_receitas": tot_rec, "total_despesas": tot_desp, "resultado": resultado,
            "soma_receitas": round(sum(tot_rec.values()), 2), "soma_despesas": round(sum(tot_desp.values()), 2),
        }

    def exportar_linhas(self, f):
        """Retorna TODAS as linhas filtradas (sem paginacao) para exportacao CSV."""
        where, params = _where(f)
        col = ORDENAR.get(f.get("ordenar"), "t.data_vencimento")
        direcao = "DESC" if str(f.get("dir", "desc")).lower() == "desc" else "ASC"
        sql = """
            SELECT e.razao_social AS empresa, cc.descricao AS conta, t.tipo, t.status,
                   cl.razao_social AS cliente, cat.descricao AS categoria,
                   t.numero_documento, t.numero_parcela,
                   t.data_emissao, t.data_vencimento, t.data_previsao, t.valor
            %s %s ORDER BY %s %s
        """ % (_JOINS, where, col, direcao)
        return [dict(r) for r in self.con.execute(sql, params).fetchall()]

    # ================= usuarios =================
    def contar_usuarios(self):
        return self.con.execute("SELECT COUNT(*) AS n FROM usuario").fetchone()["n"]

    def criar_usuario(self, nome, login, senha_hash, salt, iteracoes, papel, criado_em):
        with self._lock:
            cur = self.con.execute(
                """INSERT INTO usuario (nome, login, senha_hash, salt, iteracoes, papel, ativo, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (nome, login, senha_hash, salt, iteracoes, papel, criado_em),
            )
            self.con.commit()
            return cur.lastrowid

    def obter_usuario_por_login(self, login):
        r = self.con.execute("SELECT * FROM usuario WHERE login = ?", (login,)).fetchone()
        return dict(r) if r else None

    def obter_usuario(self, uid):
        r = self.con.execute("SELECT * FROM usuario WHERE id = ?", (uid,)).fetchone()
        return dict(r) if r else None

    def listar_usuarios(self):
        rows = self.con.execute("SELECT * FROM usuario ORDER BY nome, login").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d.pop("senha_hash", None); d.pop("salt", None); d.pop("iteracoes", None)
            d["empresas"] = self.empresas_do_usuario(d["id"])
            out.append(d)
        return out

    def atualizar_usuario(self, uid, nome, papel, ativo):
        with self._lock:
            self.con.execute("UPDATE usuario SET nome=?, papel=?, ativo=? WHERE id=?",
                             (nome, papel, 1 if ativo else 0, uid))
            self.con.commit()

    def definir_senha(self, uid, senha_hash, salt, iteracoes):
        with self._lock:
            self.con.execute("UPDATE usuario SET senha_hash=?, salt=?, iteracoes=? WHERE id=?",
                             (senha_hash, salt, iteracoes, uid))
            self.con.commit()

    def excluir_usuario(self, uid):
        with self._lock:
            self.con.execute("DELETE FROM usuario WHERE id=?", (uid,))
            self.con.execute("DELETE FROM usuario_empresa WHERE usuario_id=?", (uid,))
            self.con.execute("DELETE FROM sessao WHERE usuario_id=?", (uid,))
            self.con.commit()

    def marcar_acesso(self, uid, quando):
        with self._lock:
            self.con.execute("UPDATE usuario SET ultimo_acesso=? WHERE id=?", (quando, uid))
            self.con.commit()

    def definir_empresas_usuario(self, uid, empresa_ids):
        with self._lock:
            self.con.execute("DELETE FROM usuario_empresa WHERE usuario_id=?", (uid,))
            self.con.executemany("INSERT OR IGNORE INTO usuario_empresa (usuario_id, empresa_id) VALUES (?, ?)",
                                 [(uid, e) for e in (empresa_ids or [])])
            self.con.commit()

    def empresas_do_usuario(self, uid):
        return [r["empresa_id"] for r in
                self.con.execute("SELECT empresa_id FROM usuario_empresa WHERE usuario_id=?", (uid,)).fetchall()]

    # ================= sessoes =================
    def criar_sessao(self, token_hash, usuario_id, criado_em, expira_em, ip):
        with self._lock:
            self.con.execute("INSERT OR REPLACE INTO sessao (token_hash, usuario_id, criado_em, expira_em, ip) VALUES (?,?,?,?,?)",
                             (token_hash, usuario_id, criado_em, expira_em, ip))
            self.con.commit()

    def obter_sessao(self, token_hash):
        r = self.con.execute("SELECT * FROM sessao WHERE token_hash=?", (token_hash,)).fetchone()
        return dict(r) if r else None

    def excluir_sessao(self, token_hash):
        with self._lock:
            self.con.execute("DELETE FROM sessao WHERE token_hash=?", (token_hash,))
            self.con.commit()

    def limpar_sessoes_expiradas(self, agora):
        with self._lock:
            self.con.execute("DELETE FROM sessao WHERE expira_em < ?", (agora,))
            self.con.commit()

    # ================= credenciais OMIE =================
    def listar_credenciais(self):
        return [dict(r) for r in self.con.execute(
            "SELECT empresa_id, nome, app_key, app_secret FROM empresa_credencial ORDER BY nome").fetchall()]

    def obter_credencial(self, empresa_id):
        r = self.con.execute("SELECT * FROM empresa_credencial WHERE empresa_id=?", (empresa_id,)).fetchone()
        return dict(r) if r else None

    def salvar_credencial(self, empresa_id, nome, app_key, app_secret, criado_em):
        with self._lock:
            self.con.execute(
                """INSERT INTO empresa_credencial (empresa_id, nome, app_key, app_secret, criado_em)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(empresa_id) DO UPDATE SET nome=excluded.nome, app_key=excluded.app_key, app_secret=excluded.app_secret""",
                (empresa_id, nome, app_key, app_secret, criado_em))
            ex = self.con.execute("SELECT 1 FROM empresa WHERE empresa_id=?", (empresa_id,)).fetchone()
            if ex:
                self.con.execute("UPDATE empresa SET nome=COALESCE(NULLIF(nome,''),?) WHERE empresa_id=?", (nome, empresa_id))
            else:
                self.con.execute("INSERT INTO empresa (empresa_id, nome, razao_social) VALUES (?,?,?)",
                                 (empresa_id, nome, nome))
            self.con.commit()

    def excluir_credencial(self, empresa_id):
        with self._lock:
            self.con.execute("DELETE FROM empresa_credencial WHERE empresa_id=?", (empresa_id,))
            self.con.execute("DELETE FROM usuario_empresa WHERE empresa_id=?", (empresa_id,))
            self.con.commit()

    # ================= config =================
    def config_get(self, chave, padrao=None):
        r = self.con.execute("SELECT valor FROM app_config WHERE chave=?", (chave,)).fetchone()
        return r["valor"] if r else padrao

    def config_set(self, chave, valor):
        with self._lock:
            self.con.execute("INSERT INTO app_config (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                             (chave, valor))
            self.con.commit()

    # ================= importacao (1a execucao) =================
    def importar_de(self, caminho_db_antigo):
        """Copia dados de relatorio (e usuarios/credenciais, se vazios) de um banco do
        app 'relatorio omie' (K Finserv). Roda so quando este banco ainda nao tem titulos.
        Retorna um resumo do que importou, ou None se o arquivo nao existe/nao e compativel.
        """
        if not caminho_db_antigo or not os.path.isfile(caminho_db_antigo):
            return None
        resumo = {}
        try:
            velho = sqlite3.connect("file:%s?mode=ro" % caminho_db_antigo.replace("\\", "/"), uri=True)
            velho.row_factory = sqlite3.Row
        except sqlite3.Error:
            return None
        try:
            tabelas = {r["name"] for r in velho.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "titulo" not in tabelas:
                return None

            def copiar(tabela, colunas, transform=None, where=""):
                cols_velho = {r["name"] for r in velho.execute("PRAGMA table_info(%s)" % tabela)}
                cols = [c for c in colunas if c in cols_velho]
                if not cols:
                    return 0
                rows = velho.execute("SELECT %s FROM %s %s" % (",".join(cols), tabela, where)).fetchall()
                linhas = []
                for r in rows:
                    d = {c: r[c] for c in cols}
                    if transform:
                        d = transform(d)
                        if d is None:
                            continue
                    linhas.append(d)
                if not linhas:
                    return 0
                todas = list(linhas[0].keys())
                ph = ",".join(":" + c for c in todas)
                self.con.executemany(
                    "INSERT OR REPLACE INTO %s (%s) VALUES (%s)" % (tabela, ",".join(todas), ph), linhas)
                return len(linhas)

            with self._lock:
                resumo["empresas"] = copiar("empresa", ["empresa_id", "nome", "razao_social", "nome_fantasia",
                                                          "cnpj", "cidade", "estado", "atualizado_em"])
                resumo["contas_correntes"] = copiar("conta_corrente", ["empresa_id", "ncodcc", "descricao", "tipo",
                                                                        "codigo_banco", "agencia", "numero", "inativo", "saldo_inicial"])
                resumo["clientes"] = copiar("cliente", ["empresa_id", "codigo", "razao_social", "nome_fantasia", "documento"])
                resumo["categorias"] = copiar("categoria", ["empresa_id", "codigo", "descricao", "natureza"])
                resumo["titulos"] = copiar("titulo", ["empresa_id", "empresa_real", "tipo", "codigo", "cod_cliente",
                                                       "ncodcc", "cod_categoria", "numero_documento", "numero_parcela",
                                                       "tipo_documento", "data_emissao", "data_vencimento", "data_previsao",
                                                       "data_registro", "valor", "status", "observacao"])
                resumo["sync_info"] = copiar("sync_info", ["empresa_id", "ultimo_sync", "resumo"])
                if not self.con.execute("SELECT 1 FROM empresa_credencial LIMIT 1").fetchone() and "empresa_credencial" in tabelas:
                    resumo["credenciais"] = copiar("empresa_credencial",
                                                    ["empresa_id", "nome", "app_key", "app_secret", "criado_em"])
                if not self.con.execute("SELECT 1 FROM usuario LIMIT 1").fetchone() and "usuario" in tabelas:
                    def _mapear_usuario(d):
                        d["papel"] = "admin" if d.get("papel") == "admin" else "user"
                        return d
                    resumo["usuarios"] = copiar("usuario", ["id", "nome", "login", "senha_hash", "salt", "iteracoes",
                                                             "papel", "ativo", "criado_em"], _mapear_usuario)
                self.con.commit()
        finally:
            velho.close()
        return resumo


# ---------- helpers de WHERE ----------
def _in(coluna, valores):
    """Monta 'coluna IN (?,?,..)' com seus parametros. Retorna ('', []) se vazio."""
    valores = [v for v in (valores or []) if v not in (None, "")]
    if not valores:
        return "", []
    return "%s IN (%s)" % (coluna, ",".join("?" * len(valores))), list(valores)


def _where(f):
    cond, params = [], []
    for clausula, vals in (
        _in("t.empresa_real", f.get("empresas")),
        _in("t.ncodcc", f.get("contas")),
        _in("t.status", f.get("status")),
        _in("t.cod_categoria", f.get("categorias")),
    ):
        if clausula:
            cond.append(clausula)
            params += vals

    tipo = f.get("tipo")
    if tipo in ("pagar", "receber"):
        cond.append("t.tipo = ?")
        params.append(tipo)

    cliente = f.get("cliente")
    if cliente:
        cond.append("t.cod_cliente = ?")
        params.append(cliente)

    campo = CAMPO_DATA.get(f.get("campo_data"), "t.data_vencimento")
    if f.get("de"):
        cond.append("%s >= ?" % campo)
        params.append(f["de"])
    if f.get("ate"):
        cond.append("%s <= ?" % campo)
        params.append(f["ate"])

    busca = (f.get("busca") or "").strip()
    if busca:
        like = "%" + busca + "%"
        cond.append("(IFNULL(t.numero_documento,'') LIKE ? OR IFNULL(t.numero_parcela,'') LIKE ? "
                    "OR IFNULL(cl.razao_social,'') LIKE ? OR IFNULL(cl.nome_fantasia,'') LIKE ? "
                    "OR IFNULL(cat.descricao,'') LIKE ? OR IFNULL(t.observacao,'') LIKE ?)")
        params += [like] * 6

    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return where, params

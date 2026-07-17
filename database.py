# -*- coding: utf-8 -*-
"""Camada de banco de dados do app Analise Financeira OMIE.

Dois backends, escolhidos automaticamente:
- **PostgreSQL** quando a variavel de ambiente DATABASE_URL existe (producao no
  Render: o Postgres gerenciado persiste independente do web service). Usa
  psycopg 3 com pool de conexoes e linhas-dicionario.
- **SQLite** caso contrario (desenvolvimento local) — biblioteca padrao, arquivo
  local, exatamente como antes.

O restante do codigo fala com os helpers `_query`/`_query_one`/`_tx` da classe DB;
os SQLs sao escritos no dialeto comum (placeholders `?`/`:nome`, traduzidos para
`%s`/`%(nome)s` no Postgres). Linhas sao acessiveis por nome de coluna nos dois
backends (sqlite3.Row / psycopg dict_row).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager

import holding

try:  # so e necessario quando DATABASE_URL esta definida
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - ambiente local sem o pacote
    psycopg = None

# ---------------------------------------------------------------- schema
# Template unico; tipos trocados por backend:
#   {INT}    -> INTEGER (sqlite) | BIGINT (pg — codigos do OMIE passam de 2^31)
#   {REAL}   -> REAL (sqlite) | DOUBLE PRECISION (pg)
#   {AUTOPK} -> INTEGER PRIMARY KEY AUTOINCREMENT | BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
_SCHEMA_TEMPLATE = """
CREATE TABLE IF NOT EXISTS empresa (
    empresa_id    TEXT PRIMARY KEY,
    nome          TEXT,
    razao_social  TEXT,
    nome_fantasia TEXT,
    cnpj          TEXT,
    cidade        TEXT,
    estado        TEXT,
    atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS conta_corrente (
    empresa_id    TEXT,
    ncodcc        {INT},
    descricao     TEXT,
    tipo          TEXT,
    codigo_banco  TEXT,
    agencia       TEXT,
    numero        TEXT,
    inativo       TEXT,
    saldo_inicial {REAL},
    PRIMARY KEY (empresa_id, ncodcc)
);

CREATE TABLE IF NOT EXISTS cliente (
    empresa_id    TEXT,
    codigo        {INT},
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

CREATE TABLE IF NOT EXISTS departamento (
    empresa_id TEXT,
    codigo     TEXT,
    descricao  TEXT,
    estrutura  TEXT,
    inativo    TEXT,
    PRIMARY KEY (empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS titulo_departamento (
    empresa_id TEXT,      -- credencial OMIE (namespace do titulo)
    tipo       TEXT,      -- 'pagar' | 'receber'
    codigo     {INT},     -- codigo_lancamento_omie do titulo
    cod_dep    TEXT,
    valor      {REAL},    -- valor rateado para o departamento
    percentual {REAL},
    PRIMARY KEY (empresa_id, tipo, codigo, cod_dep)
);
CREATE INDEX IF NOT EXISTS idx_rateio_dep ON titulo_departamento(empresa_id, cod_dep);

CREATE TABLE IF NOT EXISTS titulo (
    empresa_id       TEXT,
    empresa_real     TEXT,
    tipo             TEXT,
    codigo           {INT},
    cod_cliente      {INT},
    ncodcc           {INT},
    cod_categoria    TEXT,
    numero_documento TEXT,
    numero_parcela   TEXT,
    tipo_documento   TEXT,
    data_emissao     TEXT,
    data_vencimento  TEXT,
    data_previsao    TEXT,
    data_registro    TEXT,
    valor            {REAL},
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

CREATE TABLE IF NOT EXISTS orcamento (
    empresa_id           TEXT,
    empresa_real         TEXT,    -- holding dividida pelo prefixo [Empresa] da categoria
    ano                  {INT},
    mes                  {INT},
    cod_categoria        TEXT,
    descricao            TEXT,
    valor_previsto       {REAL},
    valor_realizado_omie {REAL},
    PRIMARY KEY (empresa_id, ano, mes, cod_categoria)
);

CREATE TABLE IF NOT EXISTS usuario (
    id            {AUTOPK},
    nome          TEXT,
    login         TEXT UNIQUE NOT NULL,
    senha_hash    TEXT NOT NULL,
    salt          TEXT NOT NULL,
    iteracoes     {INT} NOT NULL,
    papel         TEXT NOT NULL DEFAULT 'user',
    ativo         {INT} NOT NULL DEFAULT 1,
    criado_em     TEXT,
    ultimo_acesso TEXT
);

CREATE TABLE IF NOT EXISTS usuario_empresa (
    usuario_id {INT} NOT NULL,
    empresa_id TEXT NOT NULL,
    PRIMARY KEY (usuario_id, empresa_id)
);

CREATE TABLE IF NOT EXISTS sessao (
    token_hash TEXT PRIMARY KEY,
    usuario_id {INT} NOT NULL,
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


def _schema_sql(pg):
    if pg:
        return _SCHEMA_TEMPLATE.format(
            INT="BIGINT", REAL="DOUBLE PRECISION",
            AUTOPK="BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY")
    return _SCHEMA_TEMPLATE.format(
        INT="INTEGER", REAL="REAL",
        AUTOPK="INTEGER PRIMARY KEY AUTOINCREMENT")


# ---------------------------------------------------------------- traducao de SQL
_RE_NOMEADO = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


def _pg_sql(sql):
    """Traduz placeholders do dialeto comum para o psycopg: ? -> %s, :nome -> %(nome)s.
    (Nenhum SQL do app tem '?' ou ':' dentro de literais de string.)"""
    sql = sql.replace("?", "%s")
    return _RE_NOMEADO.sub(r"%(\1)s", sql)


class _Exec:
    """Executor dentro de uma transacao (ver DB._tx)."""

    def __init__(self, con, pg):
        self._con = con
        self._pg = pg

    def exec(self, sql, params=()):
        if self._pg:
            return self._con.execute(_pg_sql(sql), params)
        return self._con.execute(sql, params)

    def exec_many(self, sql, seq):
        seq = list(seq)
        if not seq:
            return
        if self._pg:
            with self._con.cursor() as cur:
                cur.executemany(_pg_sql(sql), seq)
        else:
            self._con.executemany(sql, seq)

    def query_one(self, sql, params=()):
        return self.exec(sql, params).fetchone()

    def insert_id(self, sql, params=()):
        """INSERT que devolve o id gerado (lastrowid no SQLite, RETURNING no Postgres)."""
        if self._pg:
            return self._con.execute(_pg_sql(sql) + " RETURNING id", params).fetchone()["id"]
        return self._con.execute(sql, params).lastrowid


# ---------------------------------------------------------------- filtros (WHERE)
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
    def __init__(self, caminho, database_url=None):
        self.caminho = caminho
        self.database_url = database_url or None
        self.pg = bool(self.database_url)
        self._lock = threading.Lock()   # serializa escritas no caminho SQLite
        if self.pg:
            if psycopg is None:
                raise RuntimeError(
                    "DATABASE_URL definida mas o psycopg nao esta instalado. "
                    "Rode: pip install 'psycopg[binary,pool]'")
            self._pool = ConnectionPool(
                self.database_url, open=True, min_size=1,
                max_size=int(os.environ.get("PG_POOL_MAX", "10")),
                kwargs={"row_factory": dict_row})
            self.con = None
        else:
            self.con = sqlite3.connect(caminho, check_same_thread=False)
            self.con.row_factory = sqlite3.Row
            self.con.execute("PRAGMA journal_mode=WAL")       # PRAGMAs so existem no SQLite
            self.con.execute("PRAGMA synchronous=NORMAL")
        self._criar_schema()

    def fechar(self):
        """Encerra o backend (fecha o pool no Postgres / a conexao no SQLite)."""
        try:
            if self.pg:
                self._pool.close()
            elif self.con is not None:
                self.con.close()
        except Exception:  # noqa: BLE001 - shutdown nunca deve falhar
            pass

    def _criar_schema(self):
        if self.pg:
            with self._pool.connection() as con:
                con.execute(_schema_sql(True))
        else:
            self.con.executescript(_schema_sql(False))
            self.con.commit()
        self._migrar()

    def _migrar(self):
        """Migracao leve: adiciona colunas novas a bancos ja criados (idempotente)."""
        for alter in ("ALTER TABLE orcamento ADD COLUMN empresa_real TEXT",):
            try:
                with self._tx() as t:
                    t.exec(alter)
            except Exception:  # noqa: BLE001 - coluna ja existe
                pass
        with self._tx() as t:
            t.exec("UPDATE orcamento SET empresa_real=empresa_id WHERE empresa_real IS NULL OR empresa_real=''")

    # ---------------- helpers de acesso (unico ponto que fala com o banco) ----------------
    @contextmanager
    def _tx(self):
        """Transacao de escrita: tudo dentro do bloco e atomico e commitado ao sair."""
        if self.pg:
            with self._pool.connection() as con:   # commit/rollback automaticos
                yield _Exec(con, True)
        else:
            with self._lock:
                try:
                    yield _Exec(self.con, False)
                    self.con.commit()
                except Exception:
                    self.con.rollback()
                    raise

    def _query(self, sql, params=()):
        """SELECT -> lista de linhas acessiveis por nome de coluna."""
        if self.pg:
            with self._pool.connection() as con:
                return con.execute(_pg_sql(sql), params).fetchall()
        return self.con.execute(sql, params).fetchall()

    def _query_one(self, sql, params=()):
        if self.pg:
            with self._pool.connection() as con:
                return con.execute(_pg_sql(sql), params).fetchone()
        return self.con.execute(sql, params).fetchone()

    # ---------------- escrita (sincronizacao) ----------------
    def upsert_empresa(self, empresa_id, dados):
        with self._tx() as t:
            t.exec(
                """INSERT INTO empresa (empresa_id, nome, razao_social, nome_fantasia, cnpj, cidade, estado, atualizado_em)
                   VALUES (:empresa_id, :nome, :razao_social, :nome_fantasia, :cnpj, :cidade, :estado, :atualizado_em)
                   ON CONFLICT(empresa_id) DO UPDATE SET
                     nome=excluded.nome, razao_social=excluded.razao_social,
                     nome_fantasia=excluded.nome_fantasia, cnpj=excluded.cnpj,
                     cidade=excluded.cidade, estado=excluded.estado,
                     atualizado_em=excluded.atualizado_em""",
                {"empresa_id": empresa_id, **dados})

    def upsert_empresa_basica(self, empresa_id, dados):
        """Garante a empresa com nome amigavel (sem depender de sync do OMIE)."""
        with self._tx() as t:
            existe = t.query_one("SELECT 1 AS um FROM empresa WHERE empresa_id=?", (empresa_id,))
            if not existe:
                t.exec("INSERT INTO empresa (empresa_id, nome, razao_social, cnpj) VALUES (?,?,?,?)",
                       (empresa_id, dados.get("nome"), dados.get("razao_social") or dados.get("nome"),
                        dados.get("cnpj") or ""))
            else:
                t.exec(
                    """UPDATE empresa SET nome=COALESCE(NULLIF(nome,''),?),
                                          razao_social=COALESCE(NULLIF(razao_social,''),?)
                       WHERE empresa_id=?""",
                    (dados.get("nome"), dados.get("razao_social") or dados.get("nome"), empresa_id))

    def substituir(self, tabela, empresa_id, linhas, colunas):
        """Apaga os dados da empresa numa tabela e insere o lote novo (full refresh)."""
        with self._tx() as t:
            t.exec("DELETE FROM %s WHERE empresa_id = ?" % tabela, (empresa_id,))
            if linhas:
                placeholders = ",".join([":" + c for c in colunas])
                t.exec_many("INSERT INTO %s (%s) VALUES (%s)" % (tabela, ",".join(colunas), placeholders), linhas)

    def substituir_titulos(self, empresa_id, tipo, linhas, colunas):
        with self._tx() as t:
            t.exec("DELETE FROM titulo WHERE empresa_id = ? AND tipo = ?", (empresa_id, tipo))
            if linhas:
                placeholders = ",".join([":" + c for c in colunas])
                t.exec_many("INSERT INTO titulo (%s) VALUES (%s)" % (",".join(colunas), placeholders), linhas)

    def registrar_sync(self, empresa_id, quando, resumo):
        with self._tx() as t:
            t.exec(
                """INSERT INTO sync_info (empresa_id, ultimo_sync, resumo)
                   VALUES (?, ?, ?)
                   ON CONFLICT(empresa_id) DO UPDATE SET ultimo_sync=excluded.ultimo_sync, resumo=excluded.resumo""",
                (empresa_id, quando, json.dumps(resumo, ensure_ascii=False)))

    def reatribuir_holding(self):
        """Atribui empresa_real aos titulos das credenciais holding (ROI) pelo prefixo da conta."""
        with self._tx() as t:
            for cred in holding.CREDENCIAIS_HOLDING:
                contas = t.exec("SELECT ncodcc, descricao FROM conta_corrente WHERE empresa_id=?", (cred,)).fetchall()
                for c in contas:
                    t.exec("UPDATE titulo SET empresa_real=? WHERE empresa_id=? AND ncodcc=?",
                           (holding.empresa_real(cred, c["descricao"]), cred, c["ncodcc"]))
                t.exec("UPDATE titulo SET empresa_real=? WHERE empresa_id=? AND (empresa_real IS NULL OR empresa_real='')",
                       (cred, cred))
                # orcamento da holding: prefixo [Empresa] vem da descricao da categoria
                orcs = t.exec("""SELECT DISTINCT o.cod_categoria AS cod,
                                        COALESCE(NULLIF(o.descricao,''), cat.descricao, '') AS descricao
                                 FROM orcamento o
                                 LEFT JOIN categoria cat ON cat.empresa_id = o.empresa_id AND cat.codigo = o.cod_categoria
                                 WHERE o.empresa_id=?""", (cred,)).fetchall()
                for o in orcs:
                    t.exec("UPDATE orcamento SET empresa_real=? WHERE empresa_id=? AND cod_categoria=?",
                           (holding.empresa_real(cred, o["descricao"]), cred, o["cod"]))
            t.exec("UPDATE titulo SET empresa_real=empresa_id WHERE empresa_real IS NULL OR empresa_real=''")
            t.exec("UPDATE orcamento SET empresa_real=empresa_id WHERE empresa_real IS NULL OR empresa_real=''")

    def substituir_rateio(self, empresa_id, tipo, linhas):
        """Full refresh do rateio por departamento dos titulos de uma empresa/tipo."""
        with self._tx() as t:
            t.exec("DELETE FROM titulo_departamento WHERE empresa_id = ? AND tipo = ?", (empresa_id, tipo))
            if linhas:
                t.exec_many(
                    """INSERT INTO titulo_departamento (empresa_id, tipo, codigo, cod_dep, valor, percentual)
                       VALUES (:empresa_id, :tipo, :codigo, :cod_dep, :valor, :percentual)""", linhas)

    def substituir_orcamento(self, empresa_id, ano, linhas):
        """Full refresh do orcamento de caixa de uma empresa num ano."""
        with self._tx() as t:
            t.exec("DELETE FROM orcamento WHERE empresa_id = ? AND ano = ?", (empresa_id, ano))
            if linhas:
                t.exec_many(
                    """INSERT INTO orcamento (empresa_id, empresa_real, ano, mes, cod_categoria, descricao,
                                              valor_previsto, valor_realizado_omie)
                       VALUES (:empresa_id, :empresa_real, :ano, :mes, :cod_categoria, :descricao,
                               :valor_previsto, :valor_realizado_omie)""", linhas)

    def previsto_realizado(self, empresas, ano):
        """Previsto x Realizado no criterio do Fluxo de Caixa do OMIE, direto dos titulos:

        - **Previsto**  = TODOS os titulos com vencimento no mes (o esperado no periodo);
        - **Realizado** = os que ja foram liquidados (PAGO/RECEBIDO/LIQUIDADO/BAIXADO/CONCILIADO).

        Cancelados sao ignorados. Filtra por empresa_real (holding ROI dividida) e agrupa
        pelo rotulo da categoria; classifica receita/despesa pelo tipo do titulo.
        """
        ph, params = _in("t.empresa_real", empresas)
        cond = ("AND " + ph) if ph else ""
        rows = self._query(
            """SELECT COALESCE(NULLIF(cat.descricao,''), t.cod_categoria, '(sem categoria)') AS categoria,
                      t.tipo AS tipo, substr(t.data_vencimento,6,2) AS mes,
                      CASE WHEN UPPER(COALESCE(t.status,'')) IN
                                ('PAGO','RECEBIDO','LIQUIDADO','BAIXADO','CONCILIADO')
                           THEN 1 ELSE 0 END AS liquidado,
                      SUM(t.valor) AS soma
               FROM titulo t
               LEFT JOIN categoria cat ON cat.empresa_id = t.empresa_id AND cat.codigo = t.cod_categoria
               WHERE substr(t.data_vencimento,1,4) = ?
                 AND UPPER(COALESCE(t.status,'')) NOT LIKE ?
                 %s
               GROUP BY categoria, tipo, mes, liquidado""" % cond,
            [str(ano), "%CANCEL%"] + params)

        linhas = {}

        def linha(cat):
            if cat not in linhas:
                linhas[cat] = {"categoria": cat, "previsto": [0.0] * 12, "realizado": [0.0] * 12,
                                "receber": 0.0, "pagar": 0.0}
            return linhas[cat]

        for r in rows:
            try:
                m = int(r["mes"])
            except (TypeError, ValueError):
                continue
            if not (1 <= m <= 12):
                continue
            l = linha(r["categoria"])
            soma = r["soma"] or 0
            l["previsto"][m - 1] += soma                 # previsto = tudo que vence no mes
            if r["liquidado"]:
                l["realizado"][m - 1] += soma            # realizado = o subconjunto liquidado
            l[r["tipo"] if r["tipo"] in ("receber", "pagar") else "pagar"] += soma

        receitas, despesas = [], []
        for l in linhas.values():
            if not any(l["previsto"]) and not any(l["realizado"]):
                continue
            eh_receita = l["receber"] >= l["pagar"]      # todo titulo tem tipo definido
            item = {"categoria": l["categoria"], "previsto": [round(v, 2) for v in l["previsto"]],
                    "realizado": [round(v, 2) for v in l["realizado"]]}
            (receitas if eh_receita else despesas).append(item)
        chave = lambda i: -max(sum(i["previsto"]), sum(i["realizado"]))  # noqa: E731
        receitas.sort(key=chave)
        despesas.sort(key=chave)
        anos = [int(r["ano"]) for r in self._query(
            """SELECT DISTINCT substr(t.data_vencimento,1,4) AS ano FROM titulo t
               WHERE t.data_vencimento IS NOT NULL AND t.data_vencimento <> '' %s
               ORDER BY ano""" % cond, params) if r["ano"]]
        return {"ano": ano, "anos": anos, "receitas": receitas, "despesas": despesas}

    # ---------------- leitura ----------------
    def tem_titulos(self):
        return self._query_one("SELECT 1 AS um FROM titulo LIMIT 1") is not None

    def empresas_com_titulos(self):
        rows = self._query(
            "SELECT DISTINCT empresa_real FROM titulo WHERE empresa_real IS NOT NULL AND empresa_real <> ''")
        return [r["empresa_real"] for r in rows]

    def empresas(self):
        rows = self._query(
            """SELECT e.*, s.ultimo_sync, s.resumo,
                      (SELECT COUNT(*) FROM titulo t WHERE t.empresa_real = e.empresa_id) AS qtd_titulos
               FROM empresa e LEFT JOIN sync_info s ON s.empresa_id = e.empresa_id
               ORDER BY e.razao_social""")
        return [dict(r) for r in rows]

    def filtros_disponiveis(self, empresas):
        """Contas, status e categorias existentes para as empresas selecionadas."""
        ph, params = _in("t.empresa_real", empresas)
        cond = ("WHERE " + ph) if ph else ""
        contas = self._query(
            """SELECT DISTINCT cc.ncodcc AS ncodcc, cc.descricao AS descricao, cc.empresa_id AS empresa_id
               FROM titulo t JOIN conta_corrente cc ON cc.empresa_id=t.empresa_id AND cc.ncodcc=t.ncodcc
               %s ORDER BY cc.descricao""" % cond, params)
        status = self._query(
            "SELECT DISTINCT status FROM titulo t %s ORDER BY status" % cond, params)
        categorias = self._query(
            """SELECT DISTINCT t.cod_categoria AS codigo, cat.descricao AS descricao
               FROM titulo t LEFT JOIN categoria cat ON cat.empresa_id=t.empresa_id AND cat.codigo=t.cod_categoria
               %s ORDER BY cat.descricao""" % cond, params)
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
        linhas = self._query(sql, list(params) + [por_pagina, offset])
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
        linhas = self._query(sql, params)
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
        """Agrupa os titulos filtrados por: categoria | conta | cliente | mes | empresa |
        status | departamento.

        O rotulo usa MIN(...) para o SELECT ser valido no GROUP BY estrito do
        Postgres (o SQLite aceitava coluna nao agregada e escolhia uma qualquer).
        """
        if por == "departamento":
            return self._agrupar_departamento(f)
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
            SELECT {chave} AS chave, MIN({label}) AS label,
                   COUNT(*) AS n,
                   COALESCE(SUM(CASE WHEN t.tipo='pagar'   THEN t.valor END),0) AS soma_pagar,
                   COALESCE(SUM(CASE WHEN t.tipo='receber' THEN t.valor END),0) AS soma_receber
            {joins} {where}
            GROUP BY {chave}
            ORDER BY (COALESCE(SUM(t.valor),0)) DESC
        """.format(chave=chave_sql, label=label_sql, joins=_JOINS, where=where)
        linhas = self._query(sql, params)
        res = []
        for r in linhas:
            d = dict(r)
            d["saldo"] = (d["soma_receber"] or 0) - (d["soma_pagar"] or 0)
            res.append(d)
        return res

    def _agrupar_departamento(self, f):
        """Agrupa pelo rateio de departamentos: cada titulo pode dividir-se em N fatias
        (titulo_departamento); titulo sem rateio entra inteiro em '(sem departamento)'."""
        where, params = _where(f)
        sql = """
            SELECT COALESCE(td.cod_dep, '(sem departamento)') AS chave,
                   MIN(COALESCE(NULLIF(dep.descricao,''), td.cod_dep, '(sem departamento)')) AS label,
                   COUNT(DISTINCT t.codigo) AS n,
                   COALESCE(SUM(CASE WHEN t.tipo='pagar'   THEN COALESCE(td.valor, t.valor) END),0) AS soma_pagar,
                   COALESCE(SUM(CASE WHEN t.tipo='receber' THEN COALESCE(td.valor, t.valor) END),0) AS soma_receber
            {joins}
            LEFT JOIN titulo_departamento td ON td.empresa_id = t.empresa_id AND td.tipo = t.tipo AND td.codigo = t.codigo
            LEFT JOIN departamento dep       ON dep.empresa_id = t.empresa_id AND dep.codigo = td.cod_dep
            {where}
            GROUP BY chave
            ORDER BY (COALESCE(SUM(COALESCE(td.valor, t.valor)),0)) DESC
        """.format(joins=_JOINS, where=where)
        linhas = self._query(sql, params)
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
        rows = self._query(sql, params)
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
        return [dict(r) for r in self._query(sql, params)]

    # ================= usuarios =================
    def contar_usuarios(self):
        return self._query_one("SELECT COUNT(*) AS n FROM usuario")["n"]

    def criar_usuario(self, nome, login, senha_hash, salt, iteracoes, papel, criado_em):
        with self._tx() as t:
            return t.insert_id(
                """INSERT INTO usuario (nome, login, senha_hash, salt, iteracoes, papel, ativo, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (nome, login, senha_hash, salt, iteracoes, papel, criado_em))

    def obter_usuario_por_login(self, login):
        r = self._query_one("SELECT * FROM usuario WHERE login = ?", (login,))
        return dict(r) if r else None

    def obter_usuario(self, uid):
        r = self._query_one("SELECT * FROM usuario WHERE id = ?", (uid,))
        return dict(r) if r else None

    def listar_usuarios(self):
        rows = self._query("SELECT * FROM usuario ORDER BY nome, login")
        out = []
        for r in rows:
            d = dict(r)
            d.pop("senha_hash", None); d.pop("salt", None); d.pop("iteracoes", None)
            d["empresas"] = self.empresas_do_usuario(d["id"])
            out.append(d)
        return out

    def atualizar_usuario(self, uid, nome, papel, ativo):
        with self._tx() as t:
            t.exec("UPDATE usuario SET nome=?, papel=?, ativo=? WHERE id=?",
                   (nome, papel, 1 if ativo else 0, uid))

    def definir_senha(self, uid, senha_hash, salt, iteracoes):
        with self._tx() as t:
            t.exec("UPDATE usuario SET senha_hash=?, salt=?, iteracoes=? WHERE id=?",
                   (senha_hash, salt, iteracoes, uid))

    def excluir_usuario(self, uid):
        with self._tx() as t:
            t.exec("DELETE FROM usuario WHERE id=?", (uid,))
            t.exec("DELETE FROM usuario_empresa WHERE usuario_id=?", (uid,))
            t.exec("DELETE FROM sessao WHERE usuario_id=?", (uid,))

    def marcar_acesso(self, uid, quando):
        with self._tx() as t:
            t.exec("UPDATE usuario SET ultimo_acesso=? WHERE id=?", (quando, uid))

    def definir_empresas_usuario(self, uid, empresa_ids):
        with self._tx() as t:
            t.exec("DELETE FROM usuario_empresa WHERE usuario_id=?", (uid,))
            t.exec_many(
                """INSERT INTO usuario_empresa (usuario_id, empresa_id) VALUES (?, ?)
                   ON CONFLICT(usuario_id, empresa_id) DO NOTHING""",
                [(uid, e) for e in (empresa_ids or [])])

    def empresas_do_usuario(self, uid):
        return [r["empresa_id"] for r in
                self._query("SELECT empresa_id FROM usuario_empresa WHERE usuario_id=?", (uid,))]

    # ================= sessoes =================
    def criar_sessao(self, token_hash, usuario_id, criado_em, expira_em, ip):
        with self._tx() as t:
            t.exec(
                """INSERT INTO sessao (token_hash, usuario_id, criado_em, expira_em, ip)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(token_hash) DO UPDATE SET
                     usuario_id=excluded.usuario_id, criado_em=excluded.criado_em,
                     expira_em=excluded.expira_em, ip=excluded.ip""",
                (token_hash, usuario_id, criado_em, expira_em, ip))

    def obter_sessao(self, token_hash):
        r = self._query_one("SELECT * FROM sessao WHERE token_hash=?", (token_hash,))
        return dict(r) if r else None

    def excluir_sessao(self, token_hash):
        with self._tx() as t:
            t.exec("DELETE FROM sessao WHERE token_hash=?", (token_hash,))

    def limpar_sessoes_expiradas(self, agora):
        with self._tx() as t:
            t.exec("DELETE FROM sessao WHERE expira_em < ?", (agora,))

    # ================= credenciais OMIE =================
    def listar_credenciais(self):
        return [dict(r) for r in self._query(
            "SELECT empresa_id, nome, app_key, app_secret FROM empresa_credencial ORDER BY nome")]

    def obter_credencial(self, empresa_id):
        r = self._query_one("SELECT * FROM empresa_credencial WHERE empresa_id=?", (empresa_id,))
        return dict(r) if r else None

    def salvar_credencial(self, empresa_id, nome, app_key, app_secret, criado_em):
        with self._tx() as t:
            t.exec(
                """INSERT INTO empresa_credencial (empresa_id, nome, app_key, app_secret, criado_em)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(empresa_id) DO UPDATE SET nome=excluded.nome, app_key=excluded.app_key, app_secret=excluded.app_secret""",
                (empresa_id, nome, app_key, app_secret, criado_em))
            ex = t.query_one("SELECT 1 AS um FROM empresa WHERE empresa_id=?", (empresa_id,))
            if ex:
                t.exec("UPDATE empresa SET nome=COALESCE(NULLIF(nome,''),?) WHERE empresa_id=?", (nome, empresa_id))
            else:
                t.exec("INSERT INTO empresa (empresa_id, nome, razao_social) VALUES (?,?,?)",
                       (empresa_id, nome, nome))

    def excluir_credencial(self, empresa_id):
        with self._tx() as t:
            t.exec("DELETE FROM empresa_credencial WHERE empresa_id=?", (empresa_id,))
            t.exec("DELETE FROM usuario_empresa WHERE empresa_id=?", (empresa_id,))

    # ================= config =================
    def config_get(self, chave, padrao=None):
        r = self._query_one("SELECT valor FROM app_config WHERE chave=?", (chave,))
        return r["valor"] if r else padrao

    def config_set(self, chave, valor):
        with self._tx() as t:
            t.exec("INSERT INTO app_config (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                   (chave, valor))

    # ================= importacao (1a execucao, SOMENTE SQLite local) =================
    def importar_de(self, caminho_db_antigo):
        """Copia dados de relatorio (e usuarios/credenciais, se vazios) de um banco do
        app 'relatorio omie' (K Finserv). Caminho legado, exclusivo do backend SQLite
        local (usa PRAGMA table_info e INSERT OR REPLACE); no Postgres e simplesmente
        pulado — na nuvem nao existe arquivo antigo para importar.
        Retorna um resumo do que importou, ou None se nao aplicavel.
        """
        if self.pg:
            return None
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
        # LOWER(...) dos dois lados: o LIKE do SQLite ja era case-insensitive (ASCII),
        # o do Postgres nao — assim o comportamento fica igual nos dois backends.
        like = ("%" + busca + "%").lower()
        cond.append("(LOWER(COALESCE(t.numero_documento,'')) LIKE ? OR LOWER(COALESCE(t.numero_parcela,'')) LIKE ? "
                    "OR LOWER(COALESCE(cl.razao_social,'')) LIKE ? OR LOWER(COALESCE(cl.nome_fantasia,'')) LIKE ? "
                    "OR LOWER(COALESCE(cat.descricao,'')) LIKE ? OR LOWER(COALESCE(t.observacao,'')) LIKE ?)")
        params += [like] * 6

    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return where, params

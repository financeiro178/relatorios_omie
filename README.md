# Análise Financeira OMIE

Aplicativo **standalone** de relatórios financeiros emitidos a partir da API do OMIE —
a antiga tela "Análise" do app K Finserv, agora separada em um produto próprio.

## Telas

- **Visão Geral** — KPIs (a receber, a pagar, saldo, em aberto), fluxo de caixa mensal, situação dos títulos, top contas e categorias
- **DRE** — receitas × despesas por categoria, mês a mês (top 25 + "Outras")
- **Fluxo de Caixa** — entradas × saídas por mês com acumulado
- **Categorias / Contas / Clientes** — rankings e totais agrupados
- **Títulos** — tabela completa com ordenação, paginação e busca
- Filtros globais: empresa, tipo, campo de data, período, conta bancária, status, categoria e busca
- Exportação CSV (Excel), impressão/PDF e sincronização com o OMIE
- **Administração** (admin) — usuários e contas OMIE (app_key/app_secret)

## Como rodar

Dê dois cliques em `iniciar.bat` (ou `python server.py`). O app abre em `http://localhost:8766/`.

- Porta padrão: **8766** (variável `PORT`/`PORTA` muda). Pode rodar junto do app K Finserv (8765).
- Backend em **Python puro** (biblioteca padrão) + SQLite (`analise_omie.db`). Sem `pip install`.

## Primeira execução

1. Se o app **relatorio omie** (K Finserv) existir na pasta ao lado, os dados já sincronizados
   (títulos, contas, categorias, clientes), as credenciais OMIE e os **usuários** (mesmos logins
   e senhas) são importados automaticamente — não precisa esperar um sync completo.
   (Caminho alternativo: variável `IMPORTAR_DB` apontando para o `relatorio_omie.db`.)
2. Sem importação: as credenciais vêm do `config.json` (veja `config.example.json`) e um usuário
   `admin` é criado com senha exibida no console (`ADMIN_SENHA` fixa uma senha).
3. Clique em **Sincronizar** para buscar os dados direto do OMIE.

## Usuários e permissões

- **admin** — gerencia usuários/contas OMIE e vê todas as empresas.
- **user** — vê as empresas atribuídas a ele; **nenhuma atribuída = vê todas**.

## Holding ROI

O OMIE da ROI é consolidado: as contas correntes têm prefixo `[Empresa]` no nome
(ex.: `[Gibraltar] Bradesco`). O app divide os títulos por **empresa real** automaticamente
(`holding.py`), então cada empresa aparece separada nos relatórios e filtros.

## Banco de dados: SQLite local, Postgres na nuvem

A camada de dados escolhe o backend sozinha:

- **Sem `DATABASE_URL`** (rodando local): SQLite em `analise_omie.db`, como sempre — zero dependências.
- **Com `DATABASE_URL`** (produção): PostgreSQL via psycopg 3 (pool de conexões). O Render
  Postgres é um serviço gerenciado que **persiste independente do web service** — usuários,
  empresas e dados sincronizados **não se perdem mais** em deploy/restart/hibernação.

### Ativar a persistência definitiva no Render

1. No Render: **New → Postgres** (mesmo workspace/região do web service). O plano Free serve
   para começar (atenção: Postgres Free do Render expira em ~30 dias; o plano pago não).
2. No web service `relatorios_omie`: **Environment → Add** `DATABASE_URL` = a **Internal
   Database URL** do Postgres criado.
3. Mantenha `ADMIN_SENHA` (recria o admin se o banco estiver vazio) e o `CONFIG_JSON`
   (importa as credenciais OMIE se o banco estiver vazio) — a lógica de boot é idempotente:
   com o Postgres já populado, nada é sobrescrito.
4. **Manual Deploy** → o app sobe usando Postgres (o log de boot mostra
   `Banco: Postgres (DATABASE_URL)`). Faça login e **Sincronizar** uma vez; a partir daí
   tudo persiste, inclusive usuários e empresas criados na Administração.

## Deploy no Render (web service, plano Free)

No Render: **New → Web Service** → conecte este repositório e preencha:

| Campo | Valor |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Instance Type | Free |

Variáveis de ambiente (*Environment*):

- `ADMIN_LOGIN` = `admin` e `ADMIN_SENHA` = uma senha forte à sua escolha (recria o admin a cada restart);
- `CONFIG_JSON` = o JSON das credenciais OMIE, no formato do `config.example.json`, em uma
  linha só (**recomendado no Free**: faz as credenciais voltarem sozinhas a cada restart);
- `PYTHON_VERSION` = `3.12.6` e `SESSAO_HORAS` = `12` (opcionais).

**Atenção (Free):** sem disco persistente, o banco SQLite zera a cada deploy/restart e o
serviço hiberna após ~15 min sem uso (primeiro acesso demora ~1 min). Com `ADMIN_SENHA` +
`CONFIG_JSON` definidos, basta entrar e clicar em **Sincronizar** para repopular tudo direto
do OMIE. Usuários extras criados na Administração também se perdem no restart — no Free,
prefira usar só o admin. Se migrar para plano pago, o `render.yaml` (Blueprint) cria o
serviço com disco persistente e nada se perde.

## Segurança

- Login com senha (PBKDF2) e sessão em cookie HttpOnly; throttle de força-bruta.
- `app_secret` do OMIE nunca vai ao navegador.
- `config.json` e `*.db` são gitignored.

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

## Deploy no Render (web service)

O repositório inclui um `render.yaml` (Blueprint): no Render, **New → Blueprint** e aponte
para este repositório. Ele cria o web service (`python server.py`) com disco persistente
de 1 GB montado em `/var/data` (variável `DATA_DIR`), onde fica o SQLite.

- `ADMIN_SENHA` é gerada pelo Render — veja em *Environment* para o primeiro login (`admin`).
- Na nuvem não há `config.json` nem banco para importar: após o primeiro login, cadastre as
  credenciais OMIE em **Administração → + Nova conta OMIE** e clique em **Sincronizar**.
- Plano Free não tem disco persistente (dados se perdem a cada restart); use Starter ou superior.

## Segurança

- Login com senha (PBKDF2) e sessão em cookie HttpOnly; throttle de força-bruta.
- `app_secret` do OMIE nunca vai ao navegador.
- `config.json` e `*.db` são gitignored.

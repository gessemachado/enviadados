# SyncAgent — Firebird → Supabase

Agente de sincronização que lê dados do Firebird local e envia para o Supabase na nuvem a cada 15 minutos, permitindo acesso ao dashboard de qualquer lugar.

---

## Visão geral

```
Firebird (local) ──► SyncAgent.exe ──► Supabase (nuvem) ──► Dashboard (browser)
```

- Roda em background como serviço Windows
- Envia apenas registros novos ou alterados (delta)
- Retry automático em caso de falha de rede
- Log diário com rotação automática
- Configuração via `config.ini` sem recompilar

---

## Estrutura do projeto

```
syncagent/
├── src/
│   ├── main.py             # Ponto de entrada e loop principal
│   ├── config.py           # Leitura do config.ini
│   ├── log.py              # Log em arquivo com rotação diária
│   ├── firebird.py         # Leitura das tabelas via FireDAC/fdb
│   ├── supabase_client.py  # Envio HTTPS para o Supabase
│   ├── sync.py             # Orquestra o ciclo completo
│   └── ultimo_sync.py      # Controle do último sync por tabela
├── config.ini              # Configurações (não versionar com senhas)
├── build.bat               # Gera o SyncAgent.exe
└── servico.bat             # Instala/remove como serviço Windows
```

---

## Pré-requisitos

### No PC de desenvolvimento (para gerar o .exe)
- Windows 10 ou superior
- [Python 3.10+](https://www.python.org/downloads/) — marque "Add to PATH" na instalação
- Acesso à rede onde o Firebird está

### No servidor/PC onde o .exe vai rodar
- Windows 7 ou superior
- Acesso à rede do Firebird
- Acesso à internet (para enviar ao Supabase)
- **Nenhuma instalação adicional** — o .exe é autossuficiente

---

## Instalação passo a passo

### 1. Configurar o Supabase

1. Acesse [supabase.com](https://supabase.com) e crie uma conta gratuita
2. Crie um novo projeto (anote a senha do banco)
3. No painel, vá em **Settings → API** e copie:
   - `URL` do projeto (ex: `https://xxxxxxxxxxx.supabase.co`)
   - `anon public` key (a chave longa que começa com `eyJ...`)
4. Crie as tabelas no Supabase (veja seção [Tabelas no Supabase](#tabelas-no-supabase))

### 2. Configurar o config.ini

Edite o arquivo `config.ini` com os dados do seu ambiente:

```ini
[firebird]
host     = 192.168.1.10       # IP do servidor com o Firebird
port     = 3050               # Porta padrão do Firebird
database = C:\Sistema\dados.fdb
user     = SYSDBA
password = sua_senha_aqui
charset  = WIN1252            # Ou UTF8, dependendo do banco

[supabase]
url      = https://xxxxxxxxxxx.supabase.co
api_key  = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

[sync]
intervalo_minutos   = 15
log_arquivo         = sync_log.txt
ultimo_sync_arquivo = ultimo_sync.json
```

> **Atenção:** nunca compartilhe o `config.ini` com as senhas. Adicione-o ao `.gitignore` se usar Git.

### 3. Adaptar os nomes das tabelas

Abra o arquivo `src/firebird.py` e ajuste os nomes das tabelas e campos conforme o seu banco:

```python
# Exemplo — ajuste para o nome real das suas tabelas
cur.execute("""
    SELECT ID_VENDA, DATA_VENDA, VALOR_TOTAL, ...
    FROM VENDAS                        ← nome da sua tabela
    WHERE DATA_ALTERACAO >= ?          ← seu campo de data de alteração
""", (ultimo,))
```

### 4. Gerar o .exe

No PC de desenvolvimento, execute:

```
build.bat
```

O script instala as dependências e gera o executável em `dist\`:

```
dist/
├── SyncAgent.exe   ← copie este para o servidor
└── config.ini      ← copie e configure no servidor
```

### 5. Testar antes de instalar como serviço

```cmd
cd dist
SyncAgent.exe --agora
```

Isso executa um ciclo completo e mostra o resultado no terminal. Verifique:
- Conexão com o Firebird funcionando
- Dados aparecendo no Supabase
- Arquivo `sync_log.txt` gerado

### 6. Instalar como serviço Windows

Copie `SyncAgent.exe`, `config.ini` e `servico.bat` para a pasta definitiva no servidor, depois execute como **Administrador**:

```cmd
servico.bat instalar
```

O serviço inicia automaticamente com o Windows, mesmo sem usuário logado.

---

## Tabelas no Supabase

Execute estes SQLs no **SQL Editor** do Supabase para criar as tabelas:

```sql
-- Vendas
CREATE TABLE vendas (
  id_venda        TEXT PRIMARY KEY,
  data_venda      TIMESTAMP,
  valor_total     NUMERIC(15,2),
  valor_desconto  NUMERIC(15,2),
  id_cliente      TEXT,
  id_funcionario  TEXT,
  status          TEXT,
  data_alteracao  TIMESTAMP
);

-- Itens de venda
CREATE TABLE itens_venda (
  id_item           TEXT PRIMARY KEY,
  id_venda          TEXT,
  id_produto        TEXT,
  descricao_produto TEXT,
  quantidade        NUMERIC(15,3),
  valor_unitario    NUMERIC(15,2),
  valor_total       NUMERIC(15,2),
  data_alteracao    TIMESTAMP
);

-- Estoque
CREATE TABLE estoque (
  id_produto      TEXT PRIMARY KEY,
  descricao       TEXT,
  unidade         TEXT,
  saldo_atual     NUMERIC(15,3),
  estoque_minimo  NUMERIC(15,3),
  custo_medio     NUMERIC(15,2),
  data_alteracao  TIMESTAMP
);

-- Clientes
CREATE TABLE clientes (
  id_cliente     TEXT PRIMARY KEY,
  nome           TEXT,
  cpf_cnpj       TEXT,
  telefone       TEXT,
  email          TEXT,
  cidade         TEXT,
  uf             TEXT,
  data_cadastro  TIMESTAMP,
  data_alteracao TIMESTAMP
);

-- Financeiro / Caixa
CREATE TABLE financeiro (
  id_lancamento    TEXT PRIMARY KEY,
  data_lancamento  TIMESTAMP,
  tipo             TEXT,
  descricao        TEXT,
  valor            NUMERIC(15,2),
  forma_pagamento  TEXT,
  id_venda         TEXT,
  data_alteracao   TIMESTAMP
);

-- Funcionários
CREATE TABLE funcionarios (
  id_funcionario TEXT PRIMARY KEY,
  nome           TEXT,
  cargo          TEXT,
  ativo          TEXT,
  data_admissao  TIMESTAMP,
  data_alteracao TIMESTAMP
);
```

---

## Comandos do serviço Windows

```cmd
servico.bat instalar   # Instala e inicia o serviço
servico.bat remover    # Para e remove o serviço
servico.bat iniciar    # Inicia o serviço (já instalado)
servico.bat parar      # Para o serviço sem remover
servico.bat status     # Verifica se está rodando
```

---

## Monitoramento via log

O arquivo `sync_log.txt` registra cada ciclo:

```
2025-04-18 08:00:01 [INFO] === Iniciando ciclo de sincronização ===
2025-04-18 08:00:02 [INFO] Conectado ao Firebird com sucesso
2025-04-18 08:00:02 [INFO] VENDAS: 12 registros novos/alterados
2025-04-18 08:00:03 [INFO] VENDAS | lote 1/1 | 12 registros enviados
2025-04-18 08:00:03 [INFO] ITENS_VENDA: 34 registros novos/alterados
2025-04-18 08:00:04 [INFO] ESTOQUE: 0 registros novos/alterados
2025-04-18 08:00:05 [INFO] === Ciclo finalizado [OK] em 4.2s ===
2025-04-18 08:00:05 [INFO] Próximo sync em 15 minutos...
```

Logs são rotacionados diariamente e os últimos 30 dias são mantidos.

---

## Solução de problemas

| Problema | Causa provável | Solução |
|---|---|---|
| `config.ini não encontrado` | .exe não está na mesma pasta | Coloque `config.ini` na mesma pasta do `SyncAgent.exe` |
| `Falha ao conectar no Firebird` | IP/porta errados ou firewall | Verifique `host` e `port` no config.ini; libere a porta 3050 |
| `HTTP 401` no Supabase | API key incorreta | Copie a chave `anon public` novamente do painel do Supabase |
| `HTTP 404` no Supabase | Tabela não existe | Execute os SQLs de criação de tabelas no Supabase |
| Campo não encontrado | Nome de coluna diferente | Ajuste os nomes em `src/firebird.py` |
| Dados duplicados | Campo PRIMARY KEY errado | Verifique se o campo `id_*` é realmente único no Firebird |

---

## Dashboard

Com os dados no Supabase, você pode conectar qualquer ferramenta de BI:

| Ferramenta | Tipo | Como conectar |
|---|---|---|
| **Metabase** | Gratuito, self-hosted | Adiciona PostgreSQL com as credenciais do Supabase |
| **Grafana** | Gratuito, self-hosted | Plugin PostgreSQL |
| **Looker Studio** | Gratuito, Google | Conector PostgreSQL → Supabase |
| **Power BI** | Pago | Conector PostgreSQL |
| **Retool** | Gratuito (limitado) | Conecta direto ao Supabase |

As credenciais de conexão ao PostgreSQL do Supabase ficam em **Settings → Database**.

---

## Dependências Python

| Pacote | Versão mínima | Uso |
|---|---|---|
| `fdb` | 2.0+ | Driver Firebird para Python |
| `requests` | 2.28+ | Envio HTTPS para o Supabase |
| `pyinstaller` | 5.0+ | Geração do .exe (só no desenvolvimento) |

---

## Próximos passos sugeridos

- [ ] Adaptar nomes das tabelas e campos no `firebird.py`
- [ ] Criar as tabelas no Supabase
- [ ] Preencher o `config.ini` com os dados reais
- [ ] Executar `build.bat` para gerar o `.exe`
- [ ] Testar com `SyncAgent.exe --agora`
- [ ] Instalar como serviço Windows
- [ ] Conectar o dashboard (Metabase ou Looker Studio)

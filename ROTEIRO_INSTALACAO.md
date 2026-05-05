# Roteiro de Instalação — Obsidian Analytics

**Sistema:** Obsidian Analytics (Painel de Vendas + SyncAgent)
**Público:** Técnicos responsáveis pela instalação no cliente

---

## Visão Geral

O sistema tem duas partes:

```
[Computador do Cliente]           [Servidor em Nuvem]
  ERP Firebird (MegaFlex)   →   SyncAgent   →   Banco de Dados   →   Painel Web
```

- **SyncAgent** roda no computador do cliente, lê o Firebird e envia os dados a cada 15 min
- **Painel Web** é acessado pelo navegador em qualquer dispositivo (PC, celular, tablet)
- O servidor já está configurado — você só precisa cadastrar a loja e instalar o agente

---

## O que você vai precisar (antes de ir ao cliente)

- [ ] Acesso ao painel Admin: `https://obsidian-envia.duckdns.org/admin.html`
- [ ] Arquivo `SyncAgent.exe` (compilado mais recente)
- [ ] Arquivo `config.ini` (template em branco)
- [ ] Arquivo `INICIAR.BAT`
- [ ] Saber o caminho do banco Firebird do cliente (ex: `C:\Dados\BANCO.FDB`)
- [ ] Saber o IP do servidor Firebird (se for em rede, ex: `192.168.0.10`)
- [ ] Senha do Firebird (padrão: `masterkey`)

---

## PASSO 1 — Cadastrar a loja no painel Admin

> Pode ser feito remotamente antes de ir ao cliente.

1. Acesse: `https://obsidian-envia.duckdns.org/admin.html`
2. Faça login com a conta de administrador
3. Clique na aba **Lojas** → botão **+ Nova loja**
4. Preencha:
   - **Nome:** nome do cliente (ex: `Ferrenorte Comércio`)
   - **CNPJ:** CNPJ da empresa (opcional)
   - **ID Tenant:** número único para este cliente — **anote este número**, ele vai no config.ini
     > Use o próximo número disponível. Ex: se já tem lojas 1 e 2, use 3.
5. Clique em **Salvar**

### Criar o usuário do cliente

1. Clique na aba **Usuários** → botão **+ Novo usuário**
2. Preencha:
   - **Nome:** nome do responsável
   - **E-mail:** e-mail que o cliente vai usar para login
   - **Senha:** crie uma senha inicial (mín. 6 caracteres)
   - **Loja:** selecione a loja recém-cadastrada
   - **Administrador:** deixar **desmarcado** (usuário comum)
3. Clique em **Salvar**
4. **Anote o e-mail e senha** para entregar ao cliente

---

## PASSO 2 — Preparar a pasta de instalação

### Antes de ir ao cliente — gerar o SyncAgent.exe

No **seu computador** (onde está o código fonte), abra a pasta do projeto e execute:

```
build.bat
```

Isso gera o arquivo `dist\SyncAgent.exe`. Esse é o executável que vai para o cliente.

---

### No computador do cliente, crie a pasta:

```
C:\Obsidian\
```

Copie para dentro dela **3 arquivos**:

| # | Arquivo | De onde vem |
|---|---|---|
| 1 | `SyncAgent.exe` | Gerado pelo `build.bat` → pasta `dist\` |
| 2 | `config.ini` | Cópia do `config.ini.example` — você vai editar no Passo 3 |
| 3 | `INICIAR_CLIENTE.BAT` | Arquivo da pasta do projeto |

> **Dica:** Crie um atalho do `INICIAR_CLIENTE.BAT` na Área de Trabalho e renomeie para `Obsidian — Iniciar`.

---

## PASSO 3 — Configurar o config.ini

Abra o arquivo `C:\Obsidian\config.ini` com o **Bloco de Notas** e preencha:

```ini
[postgres]
host     = 108.174.148.133
port     = 5432
database = enviadados
user     = enviadados
password = Gab@311284

[firebird]
host     = 192.168.0.1          ← IP do servidor do ERP (ou deixe em branco se local)
port     = 3050
database = C:\Dados\BANCO.FDB   ← ALTERAR: caminho exato do banco Firebird
user     = SYSDBA
password = masterkey             ← senha do Firebird (padrão: masterkey)
charset  = WIN1252

[enviadados]
id_tenant = 3                    ← ALTERAR: número anotado no Passo 1

[sync]
intervalo_minutos   = 15
retry_tentativas    = 3
retry_espera_s      = 5
log_arquivo         = sync_log.txt
ultimo_sync_arquivo = ultimo_sync.json
```

**Campos obrigatórios a alterar:**
| Campo | O que colocar |
|---|---|
| `host` (firebird) | IP do servidor onde o ERP está instalado. Se for o mesmo PC, deixar em branco |
| `database` | Caminho completo do arquivo `.FDB`. Perguntar ao cliente ou verificar dentro do ERP |
| `password` (firebird) | Senha do banco. Padrão é `masterkey`. Se o cliente alterou, descobrir com o suporte do ERP |
| `id_tenant` | Número único anotado no Passo 1 |

Salve o arquivo.

---

## PASSO 4 — Testar o SyncAgent

1. Na pasta `C:\Obsidian\`, dê **duplo clique em `INICIAR.BAT`**
2. Uma janela preta vai abrir. Aguarde cerca de 30 segundos
3. Resultado esperado:

```
==========================================
  SyncAgent — Iniciando sincronização
==========================================

[OK] Conectado ao Firebird
[OK] Conectado ao PostgreSQL
[SYNC] Sincronizando saidas... 1.243 registros
[SYNC] Sincronizando produtos... 312 registros
[SYNC] Sincronizando estoque... 312 registros
...
[OK] Ciclo concluído em 18.4s — próximo em 15 min
```

4. **Se aparecer erro**, veja a seção de Problemas Comuns abaixo

> A janela deve ficar **aberta e rodando**. Não feche enquanto o computador estiver ligado.

---

## PASSO 5 — Verificar no painel web

1. Acesse no navegador: `https://obsidian-envia.duckdns.org/login.html`
2. Faça login com o e-mail e senha criados no Passo 1
3. Verifique se os dados aparecem no **Diário de Operações**

> Na primeira sincronização, o sistema processa o histórico completo. Pode demorar alguns minutos para os dados aparecerem no painel.

---

## PASSO 6 — Configurar inicialização automática (Windows)

Para o SyncAgent iniciar automaticamente com o Windows:

1. Pressione `Win + R`, digite `shell:startup` e pressione Enter
2. A pasta de Inicialização do Windows vai abrir
3. Copie o atalho do `INICIAR.BAT` para dentro dessa pasta

Pronto — na próxima vez que o computador ligar, o SyncAgent vai iniciar automaticamente.

---

## O que dizer ao cliente

Explique ao responsável:

> "Este programa roda em segundo plano e envia os dados de vendas para o painel automaticamente. Você vai ver uma janela preta — não feche ela enquanto o computador estiver ligado. Para acessar o painel, use o endereço e a senha que vou te passar."

**Entregar ao cliente:**
- URL do painel: `https://obsidian-envia.duckdns.org/login.html`
- E-mail e senha de acesso
- Instrução: não fechar a janela preta do SyncAgent

---

## Problemas Comuns

### ❌ "Erro ao conectar no Firebird"
- Verifique se o ERP (MegaFlex) está aberto e rodando
- Verifique se o caminho do banco no `config.ini` está correto
- Se for em rede, verifique se o IP do servidor Firebird está correto
- Tente abrir o banco pelo caminho `\\IP_SERVIDOR\Dados\BANCO.FDB`

### ❌ "Unable to complete network request to host"
- O Firebird Server não está rodando no servidor do ERP
- Verifique nos Serviços do Windows: `services.msc` → procure por "Firebird"

### ❌ "Senha inválida" no Firebird
- A senha padrão é `masterkey`. Pergunte ao fornecedor do ERP se foi alterada.

### ❌ "Erro de conexão com o PostgreSQL"
- Verifique a conexão com a internet
- Verifique se as credenciais do `[postgres]` no config.ini estão corretas

### ❌ O painel não mostra dados do cliente certo
- Verifique se o `id_tenant` no `config.ini` bate com o cadastrado na loja no painel Admin

### ❌ SyncAgent abre e fecha rapidamente
- Abra o arquivo `sync_log.txt` na pasta `C:\Obsidian\` para ver o erro detalhado

---

## Checklist final de instalação

- [ ] Loja cadastrada no Admin com id_tenant definido
- [ ] Usuário criado e senha anotada
- [ ] Pasta `C:\Obsidian\` criada com os 3 arquivos
- [ ] `config.ini` preenchido com caminho do banco e id_tenant
- [ ] SyncAgent testado e sincronizando sem erros
- [ ] Painel web verificado com dados aparecendo
- [ ] Atalho na Área de Trabalho criado
- [ ] Inicialização automática configurada
- [ ] Cliente instruído sobre não fechar a janela

---

*Obsidian Analytics — Suporte: gesseinvest@gmail.com*

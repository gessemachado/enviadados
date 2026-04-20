# Roadmap — SyncAgent

**Current Milestone:** M1 — Agente funcional
**Status:** Planning

---

## M1 — Agente funcional

**Goal:** SyncAgent.exe rodando no servidor, sincronizando dados do Firebird para o Supabase com logs e retry.
**Target:** Primeira sincronização bem-sucedida no ambiente real.

### Features

**Setup Supabase** - PLANNED

- Criar projeto no Supabase
- Criar as 6 tabelas (vendas, itens_venda, estoque, clientes, financeiro, funcionários)
- Obter URL e API key

**Core do agente** - PLANNED

- Estrutura do projeto Python (`src/`)
- Leitura delta do Firebird por tabela
- Envio em lotes para Supabase via REST
- Controle de último sync (`ultimo_sync.json`)
- Log diário com rotação

**Configuração e build** - PLANNED

- `config.ini` com todas as opções
- `build.bat` gerando `.exe` autossuficiente
- `servico.bat` para instalar/remover serviço Windows

**Validação em ambiente real** - PLANNED

- Testar com `SyncAgent.exe --agora`
- Verificar dados chegando no Supabase
- Instalar como serviço e confirmar início automático

---

## M2 — Dashboard

**Goal:** Visualização dos dados do Supabase via browser sem infraestrutura adicional.

### Features

**Escolha e configuração da ferramenta** - PLANNED

- Avaliar Metabase vs Looker Studio vs alternativa
- Conectar ao Supabase PostgreSQL

**Painéis principais** - PLANNED

- Vendas: faturamento diário/mensal, ticket médio
- Estoque: saldo atual, itens abaixo do mínimo
- Financeiro: entradas/saídas, saldo do caixa
- Clientes: ranking, novos cadastros
- Funcionários: vendas por vendedor

---

## Future Considerations

- Alertas automáticos (estoque mínimo, metas de venda)
- Suporte a múltiplos bancos Firebird
- Sincronização de tabelas customizadas via config.ini

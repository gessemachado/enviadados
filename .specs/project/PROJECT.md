# SyncAgent — enviadados

**Vision:** Agente Windows que sincroniza automaticamente dados do Firebird local para o Supabase na nuvem, permitindo acesso ao dashboard de qualquer lugar sem VPN.
**For:** Empresas com sistema ERP local em Firebird que precisam de visibilidade dos dados em tempo quase real via browser.
**Solves:** Dados presos no servidor local, inacessíveis remotamente sem infraestrutura complexa.

## Goals

- Sincronização confiável: enviar apenas registros novos/alterados, sem duplicatas, com retry automático
- Zero dependência no servidor: .exe autossuficiente, roda como serviço Windows sem Python instalado
- Dashboard acessível: dados visíveis via browser em qualquer dispositivo após sincronização

## Tech Stack

**Core:**

- Agent: Python 3.10+ → compilado com PyInstaller (`.exe`)
- Banco origem: Firebird (via `fdb`)
- Banco destino: Supabase (PostgreSQL via REST API / `supabase-py`)
- Dashboard: a definir (Metabase ou Looker Studio conectado ao Supabase)

**Key dependencies:**
- `fdb` — driver Firebird para Python
- `requests` ou `supabase-py` — envio para Supabase
- `pyinstaller` — geração do .exe
- `schedule` — controle do intervalo de sincronização

## Scope

**v1 inclui:**

- Leitura das 6 tabelas do Firebird: vendas, itens_venda, estoque, clientes, financeiro, funcionários
- Sincronização delta (somente novos/alterados por data de alteração)
- Envio em lotes para o Supabase via REST
- Controle de último sync por tabela (`ultimo_sync.json`)
- Log diário com rotação (30 dias)
- Retry automático em falha de rede
- Configuração via `config.ini` sem recompilar
- Build para `.exe` autossuficiente
- Instalação como serviço Windows (`servico.bat`)

**Explicitamente fora do v1:**

- Interface gráfica (GUI)
- Sincronização bidirecional (Supabase → Firebird)
- Multi-empresa / multi-banco

**v2 — Dashboard:**

- Dashboard web conectado ao Supabase (Metabase ou Looker Studio)
- Indicadores: vendas, estoque, financeiro, ranking de clientes

## Constraints

- Timeline: sem prazo definido
- Técnico: servidor de destino pode não ter Python — exige .exe autossuficiente
- Técnico: Supabase ainda não criado — criar na fase de setup

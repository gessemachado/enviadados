# Spec: Core do Agente SyncAgent

## Requisitos

**REQ-01** — Ler configuração de `config.ini` (host, porta, banco, user, senha, charset, URL Supabase, API key, intervalo)
**REQ-02** — Conectar ao Firebird via `fdb` com charset WIN1252
**REQ-03** — Para cada tabela, ler apenas registros novos/alterados desde o último sync (delta)
**REQ-04** — Enviar registros em lotes para o Supabase via REST (upsert)
**REQ-05** — Persistir o timestamp do último sync por tabela em `ultimo_sync.json`
**REQ-06** — Retry automático (3 tentativas, backoff exponencial) em falha de rede
**REQ-07** — Log diário em arquivo com rotação (manter 30 dias)
**REQ-08** — Suporte a `--agora` para execução imediata fora do ciclo agendado
**REQ-09** — Loop contínuo com intervalo configurável (padrão 15 minutos)

## Tabelas sincronizadas

| Tabela FB | Tabela Supabase | Chave | Campo Delta |
|---|---|---|---|
| SAIDAS | saidas | ID_SAIDA | DATA_MANUTENCAO |
| PRODUTOS | produtos | ID_PRODUTO | DATA_ATUALIZACAO |
| ESTOQUE | estoque | ID_ESTOQUE | join PRODUTOS.DATA_ATUALIZACAO |
| CLIENTE | clientes | ID_CLIENTE | DATA_ATUALIZACAO |
| VENDEDOR | vendedores | ID_VENDEDOR | DATA_ATUALIZACAO |
| FORNECEDOR | fornecedores | ID_FORNECEDOR | sync completo |
| CAIXA | caixa | ID_CAIXA | DATA |
| CONTA_RECEBER | contas_receber | ID_FATURA | DATA_ATUALIZACAO |
| CONTA_PAGAR | contas_pagar | ID_FATURA | DATA_ATUALIZACAO |

## Estrutura de arquivos

```
src/
├── main.py           # Ponto de entrada, loop, --agora
├── config.py         # Leitura do config.ini
├── log.py            # Logger com rotação diária
├── firebird.py       # Queries delta por tabela
├── supabase_client.py # Upsert em lotes via REST
├── sync.py           # Orquestra o ciclo completo
└── ultimo_sync.py    # Leitura/escrita de ultimo_sync.json
config.ini            # Configuração (não versionar com senhas)
build.bat             # Gera SyncAgent.exe
servico.bat           # Instala/remove serviço Windows
```

## Critérios de verificação

- [ ] `python src/main.py --agora` executa sem erro com banco real
- [ ] Dados aparecem no Supabase após execução
- [ ] `ultimo_sync.json` é atualizado com o timestamp correto
- [ ] Segunda execução envia 0 registros (nenhuma alteração)
- [ ] `sync_log.txt` gerado com entradas legíveis
- [ ] `build.bat` gera `.exe` que funciona sem Python instalado

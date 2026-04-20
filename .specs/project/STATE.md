# State — SyncAgent

## Status

**Fase atual:** Inicialização do projeto
**Último trabalho:** Criação dos docs de projeto (PROJECT.md, ROADMAP.md)
**Próximo passo:** Criar Supabase e especificar o core do agente

---

## Decisions

- **Driver Firebird:** usar `fdb` (madura, suporte WIN1252/UTF8)
- **Envio ao Supabase:** REST API com `requests` — evita overhead do SDK para operações simples de upsert
- **Controle de delta:** campo `DATA_ALTERACAO` em cada tabela (adaptar ao nome real do banco do usuário)
- **Build:** PyInstaller `--onefile` para .exe autossuficiente

---

## Blockers

- Supabase ainda não criado — necessário antes de qualquer teste de envio
- Nomes reais das tabelas e campos do Firebird do usuário ainda não mapeados

---

## Todos

- [ ] Criar projeto no Supabase
- [ ] Mapear nomes reais das tabelas/campos do Firebird
- [ ] Criar estrutura `src/` com os módulos do agente
- [ ] Criar `config.ini`, `build.bat`, `servico.bat`
- [ ] Testar build e sync em ambiente real

---

## Preferences

- Sem prazo definido
- .exe deve rodar em Windows sem Python instalado

---

## Lessons Learned

_(vazio — projeto iniciando)_

---

## Deferred Ideas

- Interface gráfica para monitorar o agente
- Sincronização bidirecional
- Multi-empresa

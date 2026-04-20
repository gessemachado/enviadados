from datetime import datetime
from src import firebird, supabase_client, ultimo_sync, log

def _serializar(val):
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val

def _serializar_rows(rows):
    return [{k: _serializar(v) for k, v in r.items()} for r in rows]

def executar_ciclo(cfg):
    logger = log.get()
    fb_cfg = cfg['firebird']
    sb_cfg = cfg['supabase']
    sync_cfg = cfg['sync']

    url = sb_cfg['url']
    api_key = sb_cfg['api_key']
    arquivo_sync = sync_cfg.get('ultimo_sync_arquivo', 'ultimo_sync.json')
    lote = int(sync_cfg.get('lote_tamanho', 500))
    tentativas = int(sync_cfg.get('retry_tentativas', 3))
    espera = int(sync_cfg.get('retry_espera_s', 5))

    logger.info('=== Iniciando ciclo de sincronização ===')
    inicio = datetime.now()

    try:
        conn = firebird.conectar(cfg)
    except Exception as e:
        logger.error(f'Falha ao conectar no Firebird: {e}')
        return

    try:
        for tabela in firebird.tabelas():
            ultimo = ultimo_sync.get(tabela, arquivo_sync)
            total_enviado = 0
            novo_ultimo = ultimo
            lote_num = 0

            try:
                for batch in firebird.ler(conn, tabela, ultimo):
                    if not batch:
                        continue

                    lote_num += 1
                    serializado = _serializar_rows(batch)
                    ok = supabase_client.upsert(
                        url, api_key, tabela, serializado, tentativas, espera
                    )

                    if ok:
                        total_enviado += len(batch)
                        # rastreia o maior valor de delta no lote
                        meta_campo = _delta_campo(tabela)
                        if meta_campo:
                            valores = [r.get(meta_campo) for r in batch if r.get(meta_campo)]
                            if valores:
                                novo_ultimo = max(str(v) for v in valores)

                        logger.info(f'{tabela.upper()} | lote {lote_num} | {len(batch)} registros enviados')
                    else:
                        logger.error(f'{tabela.upper()} | lote {lote_num} | falha no envio — abortando tabela')
                        break

            except Exception as e:
                logger.error(f'{tabela.upper()} | erro na leitura do Firebird: {e}')
                continue

            if total_enviado == 0:
                logger.info(f'{tabela.upper()}: 0 registros novos/alterados')
            else:
                ultimo_sync.set(tabela, novo_ultimo, arquivo_sync)

    finally:
        conn.close()

    duracao = (datetime.now() - inicio).total_seconds()
    logger.info(f'=== Ciclo finalizado [OK] em {duracao:.1f}s ===')

def _delta_campo(tabela):
    mapa = {
        'saidas': 'data_manutencao',
        'produtos': 'data_atualizacao',
        'estoque': 'data_atualizacao',
        'clientes': 'data_atualizacao',
        'vendedores': 'data_atualizacao',
        'fornecedores': None,
        'caixa': 'data',
        'contas_receber': 'data_atualizacao',
        'contas_pagar': 'data_atualizacao',
    }
    return mapa.get(tabela)

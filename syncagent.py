import sys
import os
import time
import json
import logging
import configparser
import decimal
import requests
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta

try:
    import fdb
except ImportError:
    print("ERRO: execute 'pip install fdb requests' antes de rodar.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def carregar_config():
    cfg = configparser.ConfigParser()
    path = os.path.join(_base_dir(), 'config.ini')
    if not cfg.read(path, encoding='utf-8'):
        raise FileNotFoundError(f'config.ini nao encontrado em: {path}')
    return cfg

# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------
def inicializar_log(nome_arquivo='sync_log.txt'):
    path = os.path.join(_base_dir(), nome_arquivo)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')
    handler_arquivo = TimedRotatingFileHandler(path, when='midnight', backupCount=30, encoding='utf-8')
    handler_arquivo.setFormatter(fmt)
    handler_console = logging.StreamHandler(sys.stdout)
    handler_console.setFormatter(fmt)
    logger = logging.getLogger('syncagent')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler_arquivo)
    logger.addHandler(handler_console)
    return logger

# ---------------------------------------------------------------------------
# Ultimo sync
# ---------------------------------------------------------------------------
def _sync_path(nome):
    return os.path.join(_base_dir(), nome)

def get_ultimo(tabela, nome):
    p = _sync_path(nome)
    if not os.path.exists(p):
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f).get(tabela)

def set_ultimo(tabela, valor, nome):
    p = _sync_path(nome)
    dados = {}
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    dados[tabela] = str(valor) if valor else None
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, default=str)

# ---------------------------------------------------------------------------
# Firebird
# ---------------------------------------------------------------------------
TABELAS = {
    'saidas': {
        'query': """SELECT ID_SAIDA, ID_PRODUTO, CODIGO, DESCRICAO,
                    NUMERO_CUPOM, NOTA_FISCAL, DATA_VENDA,
                    QUANTIDADE_VENDIDA, PRECO_VENDA, SUB_TOTAL, DESCONTO,
                    ID_CLIENTE, ID_VENDEDOR, ID_LOJA, OPERACAO, DATA_MANUTENCAO
                    FROM SAIDAS WHERE DATA_MANUTENCAO >= ? ORDER BY DATA_MANUTENCAO""",
        'delta': 'DATA_MANUTENCAO', 'padrao': '2000-01-01', 'limite_1_ano': True,
    },
    'produtos': {
        'query': """SELECT ID_PRODUTO, CODIGO, DESCRICAO, UNIDADE, PRECO, CUSTO_MEDIO,
                    EST_MINIMO, ID_GRUPO, GRUPO, ID_FORNECEDOR, ATIVO, SECAO, QTD_M3
                    FROM PRODUTOS ORDER BY ID_PRODUTO""",
        'delta': None, 'padrao': None,
    },
    'estoque': {
        'query': """SELECT ID_ESTOQUE, ID_PRODUTO, COD_PRODUTO, ID_LOJA, ESTOQUE
                    FROM ESTOQUE ORDER BY ID_ESTOQUE""",
        'delta': None, 'padrao': None,
    },
    'clientes': {
        'query': """SELECT ID_CLIENTE, CLIENTE, CGC_CPF, TELEFONE, CELULAR, WHATSAPP,
                    EMAIL, CIDADE, UF, ATIVO, ULTIMA_COMPRA, CADASTRO
                    FROM CLIENTE ORDER BY ID_CLIENTE""",
        'delta': None, 'padrao': None,
    },
    'vendedores': {
        'query': """SELECT ID_VENDEDOR, NOME, APELIDO, FUNCAO, ATIVO, META,
                    EMAIL, CELULAR, ID_LOJA
                    FROM VENDEDOR ORDER BY ID_VENDEDOR""",
        'delta': None, 'padrao': None,
    },
    'fornecedores': {
        'query': """SELECT ID_FORNECEDOR, RAZAO_SOC, NOME_FANTA, CNPJ,
                    CIDADE, UF, TELEFONE, EMAIL, WHATSAPP
                    FROM FORNECEDOR ORDER BY ID_FORNECEDOR""",
        'delta': None, 'padrao': None,
    },
    'grupo': {
        'query': """SELECT ID_GRUPO, GRUPO, DEPTO, COMISSAO, DATA_ATUALIZACAO
                    FROM GRUPO ORDER BY ID_GRUPO""",
        'delta': None, 'padrao': None,
    },
    'caixa': {
        'query': """SELECT ID_CAIXA, DATA, VALOR, HISTORICO, NAT, NATUREZA,
                    ID_CONTA, CONTA, ID_CLIENTE, ID_VENDEDOR, ID_LOJA,
                    BAIXADO, BX, DATA_BAIXA
                    FROM CAIXA WHERE DATA >= ? ORDER BY DATA""",
        'delta': 'DATA', 'padrao': '2000-01-01', 'limite_1_ano': True,
    },
    'contas_receber': {
        'query': """SELECT ID_FATURA, NUMERO, PARCELA, EMISSAO, VENCIMENTO,
                    VALOR_PARCELA, VALOR_TOTAL, RECEBIDO, JUROS, DESCONTO,
                    ID_CLIENTE, ID_VENDEDOR, LOJA, BX, SITUACAO, DATA_RECEB
                    FROM CONTA_RECEBER WHERE EMISSAO >= ? ORDER BY EMISSAO""",
        'delta': 'EMISSAO', 'padrao': '2000-01-01', 'limite_1_ano': True,
    },
    'contas_pagar': {
        'query': """SELECT ID_FATURA, NUMERO, ID_FORNECEDOR, DATA_EMISSAO, ID_TIPO,
                    JUROS, PARCELA, DATA_VENCIMENTO, DIAS_ATRASO,
                    VALOR_TOTAL, VALOR_PARCELA, BX, SITUACAO, ID_LOJA,
                    VALOR_PAGO, DATA_PAGO, REGISTRO
                    FROM FATURAS_PAGAR WHERE DATA_EMISSAO >= ? ORDER BY DATA_EMISSAO""",
        'delta': 'DATA_EMISSAO', 'padrao': '2000-01-01', 'limite_1_ano': True,
    },
}

def conectar_firebird(cfg):
    fb = cfg['firebird']
    kwargs = dict(
        database=fb['database'],
        user=fb['user'],
        password=fb['password'],
        charset=fb.get('charset', 'WIN1252'),
    )
    if fb.get('host'):
        kwargs['host'] = fb['host']
        kwargs['port'] = int(fb.get('port', 3050))
    if fb.get('fbclient'):
        kwargs['fb_library_name'] = fb['fbclient']
    return fdb.connect(**kwargs)

def _1_ano(fmt_timestamp=False):
    d = datetime.now() - timedelta(days=365)
    return d.strftime('%Y-%m-%d %H:%M:%S') if fmt_timestamp else d.strftime('%Y-%m-%d')

def ler_tabela(conn, tabela, ultimo):
    meta = TABELAS[tabela]
    cur = conn.cursor()
    if meta['delta'] is None:
        cur.execute(meta['query'])
    else:
        if not ultimo:
            if meta.get('limite_1_ano'):
                fmt_ts = '00:00:00' in (meta['padrao'] or '')
                ultimo = _1_ano(fmt_timestamp=fmt_ts)
            else:
                ultimo = meta['padrao']
        cur.execute(meta['query'], (ultimo,))
    while True:
        rows = cur.fetchmany(500)
        if not rows:
            break
        yield [{desc[0].lower(): val for desc, val in zip(cur.description, row)} for row in rows]

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
def upsert_supabase(url, api_key, tabela, registros, tentativas=3, espera=5):
    endpoint = f'{url}/rest/v1/{tabela}'
    headers = {
        'apikey': api_key,
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates',
    }
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(endpoint, json=registros, headers=headers, timeout=30)
            if resp.status_code in (200, 201):
                return True
            logging.getLogger('syncagent').warning(
                f'{tabela} | tentativa {tentativa} | HTTP {resp.status_code}: {resp.text[:200]}'
            )
        except requests.RequestException as e:
            logging.getLogger('syncagent').warning(f'{tabela} | tentativa {tentativa} | erro: {e}')
        if tentativa < tentativas:
            time.sleep(espera * tentativa)
    return False

# ---------------------------------------------------------------------------
# Serialização
# ---------------------------------------------------------------------------
def serializar(val):
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    if isinstance(val, decimal.Decimal):
        return int(val) if val == val.to_integral_value() else float(val)
    return val

def serializar_batch(rows):
    return [{k: serializar(v) for k, v in r.items()} for r in rows]

# ---------------------------------------------------------------------------
# Ciclo
# ---------------------------------------------------------------------------
def executar_ciclo(cfg, logger):
    sb = cfg['supabase']
    sync_cfg = cfg['sync']
    url = sb['url']
    api_key = sb['api_key']
    arquivo = sync_cfg.get('ultimo_sync_arquivo', 'ultimo_sync.json')
    tentativas = int(sync_cfg.get('retry_tentativas', 3))
    espera = int(sync_cfg.get('retry_espera_s', 5))

    logger.info('=== Iniciando ciclo de sincronizacao ===')
    inicio = datetime.now()

    try:
        conn = conectar_firebird(cfg)
        logger.info('Conectado ao Firebird com sucesso')
    except Exception as e:
        logger.error(f'Falha ao conectar no Firebird: {e}')
        return

    try:
        for tabela in TABELAS:
            ultimo = get_ultimo(tabela, arquivo)
            total = 0
            novo_ultimo = ultimo
            lote_num = 0

            try:
                for batch in ler_tabela(conn, tabela, ultimo):
                    if not batch:
                        continue
                    lote_num += 1
                    ok = upsert_supabase(url, api_key, tabela, serializar_batch(batch), tentativas, espera)
                    if ok:
                        total += len(batch)
                        campo = TABELAS[tabela]['delta']
                        if campo:
                            c = campo.lower()
                            vals = [r.get(c) for r in batch if r.get(c)]
                            if vals:
                                novo_ultimo = max(str(v) for v in vals)
                        logger.info(f'{tabela.upper()} | lote {lote_num} | {len(batch)} registros enviados')
                    else:
                        logger.error(f'{tabela.upper()} | lote {lote_num} | falha — abortando tabela')
                        break
            except Exception as e:
                logger.error(f'{tabela.upper()} | erro: {e}')
                continue

            if total == 0:
                logger.info(f'{tabela.upper()}: 0 registros novos/alterados')
            else:
                set_ultimo(tabela, novo_ultimo, arquivo)
    finally:
        conn.close()

    duracao = (datetime.now() - inicio).total_seconds()
    logger.info(f'=== Ciclo finalizado em {duracao:.1f}s ===')

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    cfg = carregar_config()
    logger = inicializar_log(cfg['sync'].get('log_arquivo', 'sync_log.txt'))
    agora = '--agora' in sys.argv

    if agora:
        logger.info('Modo --agora: executando ciclo unico')
        executar_ciclo(cfg, logger)
        logger.info('Concluido.')
        return

    intervalo = int(cfg['sync'].get('intervalo_minutos', 15)) * 60
    logger.info(f'SyncAgent iniciado — ciclo a cada {intervalo // 60} minutos')
    while True:
        executar_ciclo(cfg, logger)
        logger.info(f'Proximo sync em {intervalo // 60} minutos...')
        time.sleep(intervalo)

if __name__ == '__main__':
    main()

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
    print("ERRO: execute 'pip install fdb psycopg2-binary' antes de rodar.")
    sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERRO: execute 'pip install psycopg2-binary' antes de rodar.")
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
                    ID_CLIENTE, ID_VENDEDOR, ID_LOJA, OPERACAO, ID_PLANO, DATA_MANUTENCAO
                    FROM SAIDAS WHERE DATA_MANUTENCAO >= ? ORDER BY DATA_MANUTENCAO""",
        'delta': 'DATA_MANUTENCAO', 'padrao': '2025-01-01',
    },
    'plano_venda': {
        'query': """SELECT ID_PLANO, DESCRICAO, ID_TIPO, PARCELA, TXA,
                    ENTRADA, COMISSAO, DESCONTO, TAXA_CARTAO, ATIVO
                    FROM PLANO_VENDA ORDER BY ID_PLANO""",
        'delta': None, 'padrao': None,
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
        'delta': 'DATA', 'padrao': '2025-01-01',
    },
    'contas_receber': {
        'query': """SELECT ID_FATURA, NUMERO, PARCELA, EMISSAO, VENCIMENTO,
                    VALOR_PARCELA, VALOR_TOTAL, RECEBIDO, JUROS, DESCONTO,
                    ID_CLIENTE, ID_VENDEDOR, LOJA, BX, SITUACAO, DATA_RECEB
                    FROM CONTA_RECEBER WHERE EMISSAO >= ? ORDER BY EMISSAO""",
        'delta': 'EMISSAO', 'padrao': '2025-01-01',
    },
    'contas_pagar': {
        'query': """SELECT ID_FATURA, NUMERO, ID_FORNECEDOR, DATA_EMISSAO, ID_TIPO,
                    JUROS, PARCELA, DATA_VENCIMENTO, DIAS_ATRASO,
                    VALOR_TOTAL, VALOR_PARCELA, BX, SITUACAO, ID_LOJA,
                    VALOR_PAGO, DATA_PAGO, REGISTRO
                    FROM FATURAS_PAGAR WHERE DATA_EMISSAO >= ? ORDER BY DATA_EMISSAO""",
        'delta': 'DATA_EMISSAO', 'padrao': '2025-01-01',
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
# PostgreSQL
# ---------------------------------------------------------------------------
_PK = {
    'saidas':         ('id_saida',),
    'plano_venda':    ('id_plano',),
    'produtos':       ('id_produto',),
    'estoque':        ('id_estoque',),
    'clientes':       ('id_cliente',),
    'vendedores':     ('id_vendedor',),
    'fornecedores':   ('id_fornecedor',),
    'grupo':          ('id_grupo',),
    'caixa':          ('id_caixa',),
    'contas_receber': ('id_fatura', 'parcela'),
    'contas_pagar':   ('id_fatura', 'parcela'),
}

def _conectar_pg(pg_cfg):
    return psycopg2.connect(
        host=pg_cfg.get('host', '127.0.0.1'),
        port=int(pg_cfg.get('port', 5432)),
        dbname=pg_cfg['database'],
        user=pg_cfg['user'],
        password=pg_cfg['password'],
    )

def upsert_postgres(pg_cfg, tabela, registros, tentativas=3, espera=5):
    logger = logging.getLogger('syncagent')
    if not registros:
        return True

    pks    = _PK.get(tabela, ('id',))
    campos = list(registros[0].keys())
    colunas      = ', '.join(f'"{c}"' for c in campos)
    placeholders = ', '.join(['%s'] * len(campos))
    conflict     = ', '.join(f'"{c}"' for c in pks)
    updates      = ', '.join(f'"{c}" = EXCLUDED."{c}"' for c in campos if c not in pks)
    sql = (f'INSERT INTO {tabela} ({colunas}) VALUES ({placeholders}) '
           f'ON CONFLICT ({conflict}) DO UPDATE SET {updates}')
    valores = [tuple(r[c] for c in campos) for r in registros]

    for tentativa in range(1, tentativas + 1):
        try:
            conn = _conectar_pg(pg_cfg)
            try:
                with conn:
                    with conn.cursor() as cur:
                        psycopg2.extras.execute_batch(cur, sql, valores, page_size=500)
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f'{tabela} | tentativa {tentativa} | {e}')
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
    pg_cfg   = cfg['postgres']
    sync_cfg = cfg['sync']
    arquivo  = sync_cfg.get('ultimo_sync_arquivo', 'ultimo_sync.json')
    tentativas = int(sync_cfg.get('retry_tentativas', 3))
    espera     = int(sync_cfg.get('retry_espera_s', 5))
    id_tenant  = int(cfg.get('enviadados', 'id_tenant', fallback=0))

    logger.info(f'=== Iniciando ciclo de sincronizacao | id_tenant={id_tenant} ===')
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
                    for r in batch:
                        r['id_tenant'] = id_tenant
                    ok = upsert_postgres(pg_cfg, tabela, serializar_batch(batch), tentativas, espera)
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

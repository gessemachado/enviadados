import time
import psycopg2
import psycopg2.extras
from src import log

_PK = {
    'saidas':          ('id_saida',),
    'produtos':        ('id_produto',),
    'estoque':         ('id_estoque',),
    'clientes':        ('id_cliente',),
    'vendedores':      ('id_vendedor',),
    'fornecedores':    ('id_fornecedor',),
    'caixa':           ('id_caixa',),
    'contas_receber':  ('id_fatura', 'parcela'),
    'contas_pagar':    ('id_fatura', 'parcela'),
    'plano_venda':     ('id_plano',),
}

def _conectar(pg_cfg):
    return psycopg2.connect(
        host=pg_cfg.get('host', '127.0.0.1'),
        port=int(pg_cfg.get('port', 5432)),
        dbname=pg_cfg['database'],
        user=pg_cfg['user'],
        password=pg_cfg['password'],
    )

def upsert(pg_cfg, tabela, registros, tentativas=3, espera=5):
    logger = log.get()
    if not registros:
        return True

    pks = _PK.get(tabela, ('id',))
    campos = list(registros[0].keys())
    colunas = ', '.join(f'"{c}"' for c in campos)
    placeholders = ', '.join(['%s'] * len(campos))
    conflict_cols = ', '.join(f'"{c}"' for c in pks)
    updates = ', '.join(
        f'"{c}" = EXCLUDED."{c}"'
        for c in campos if c not in pks
    )
    sql = (
        f'INSERT INTO {tabela} ({colunas}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_cols}) DO UPDATE SET {updates}'
    )
    valores = [tuple(r[c] for c in campos) for r in registros]

    for tentativa in range(1, tentativas + 1):
        try:
            conn = _conectar(pg_cfg)
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

    logger.error(f'{tabela} | falhou após {tentativas} tentativas')
    return False

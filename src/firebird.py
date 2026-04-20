import fdb

_TABELAS = {
    'saidas': {
        'query': """
            SELECT
                ID_SAIDA, ID_PRODUTO, CODIGO, DESCRICAO,
                NUMERO_CUPOM, NOTA_FISCAL, DATA_VENDA,
                QUANTIDADE_VENDIDA, PRECO_VENDA, SUB_TOTAL, DESCONTO,
                ID_CLIENTE, ID_VENDEDOR, ID_LOJA,
                OPERACAO, DATA_MANUTENCAO
            FROM SAIDAS
            WHERE DATA_MANUTENCAO >= ?
            ORDER BY DATA_MANUTENCAO
        """,
        'delta_campo': 'DATA_MANUTENCAO',
        'delta_padrao': '2000-01-01',
    },
    'produtos': {
        'query': """
            SELECT
                ID_PRODUTO, CODIGO, DESCRICAO, UNIDADE,
                PRECO, CUSTO_MEDIO, EST_MINIMO,
                ID_GRUPO, GRUPO, ID_FORNECEDOR,
                ATIVO, ULTIMA_VENDA, DATA_ATUALIZACAO
            FROM PRODUTOS
            WHERE DATA_ATUALIZACAO >= ?
            ORDER BY DATA_ATUALIZACAO
        """,
        'delta_campo': 'DATA_ATUALIZACAO',
        'delta_padrao': '2000-01-01 00:00:00',
    },
    'estoque': {
        'query': """
            SELECT
                E.ID_ESTOQUE, E.ID_PRODUTO, E.COD_PRODUTO,
                E.ID_LOJA, E.ESTOQUE,
                P.DATA_ATUALIZACAO
            FROM ESTOQUE E
            JOIN PRODUTOS P ON P.ID_PRODUTO = E.ID_PRODUTO
            WHERE P.DATA_ATUALIZACAO >= ?
            ORDER BY P.DATA_ATUALIZACAO
        """,
        'delta_campo': 'DATA_ATUALIZACAO',
        'delta_padrao': '2000-01-01 00:00:00',
    },
    'clientes': {
        'query': """
            SELECT
                ID_CLIENTE, CLIENTE, CGC_CPF,
                TELEFONE, CELULAR, WHATSAPP, EMAIL,
                CIDADE, UF, ATIVO,
                ULTIMA_COMPRA, CADASTRO, DATA_ATUALIZACAO
            FROM CLIENTE
            WHERE DATA_ATUALIZACAO >= ?
            ORDER BY DATA_ATUALIZACAO
        """,
        'delta_campo': 'DATA_ATUALIZACAO',
        'delta_padrao': '2000-01-01 00:00:00',
    },
    'vendedores': {
        'query': """
            SELECT
                ID_VENDEDOR, NOME, APELIDO, FUNCAO,
                ATIVO, META, EMAIL, CELULAR, ID_LOJA,
                DATA_ATUALIZACAO
            FROM VENDEDOR
            WHERE DATA_ATUALIZACAO >= ?
            ORDER BY DATA_ATUALIZACAO
        """,
        'delta_campo': 'DATA_ATUALIZACAO',
        'delta_padrao': '2000-01-01 00:00:00',
    },
    'fornecedores': {
        'query': """
            SELECT
                ID_FORNECEDOR, RAZAO_SOC, NOME_FANTA, CNPJ,
                CIDADE, UF, TELEFONE, EMAIL, WHATSAPP
            FROM FORNECEDOR
            ORDER BY ID_FORNECEDOR
        """,
        'delta_campo': None,
        'delta_padrao': None,
    },
    'caixa': {
        'query': """
            SELECT
                ID_CAIXA, DATA, VALOR, HISTORICO,
                NAT, NATUREZA, ID_CONTA, CONTA,
                ID_CLIENTE, ID_VENDEDOR, ID_LOJA,
                BAIXADO, BX, DATA_BAIXA
            FROM CAIXA
            WHERE DATA >= ?
            ORDER BY DATA
        """,
        'delta_campo': 'DATA',
        'delta_padrao': '2000-01-01',
    },
    'contas_receber': {
        'query': """
            SELECT
                ID_FATURA, NUMERO, PARCELA, EMISSAO, VENCIMENTO,
                VALOR_PARCELA, VALOR_TOTAL, RECEBIDO, JUROS, DESCONTO,
                ID_CLIENTE, ID_VENDEDOR, LOJA, BX, SITUACAO,
                DATA_RECEB, DATA_ATUALIZACAO
            FROM CONTA_RECEBER
            WHERE DATA_ATUALIZACAO >= ?
            ORDER BY DATA_ATUALIZACAO
        """,
        'delta_campo': 'DATA_ATUALIZACAO',
        'delta_padrao': '2000-01-01 00:00:00',
    },
    'contas_pagar': {
        'query': """
            SELECT
                ID_FATURA, NUMERO, PARCELA, EMISSAO, VENCIMENTO,
                VALOR_PARCELA, VALOR_TOTAL, RECEBIDO, JUROS, DESCONTO,
                ID_CLIENTE, ID_VENDEDOR, LOJA, BX, SITUACAO,
                DATA_RECEB, DATA_ATUALIZACAO
            FROM CONTA_PAGAR
            WHERE DATA_ATUALIZACAO >= ?
            ORDER BY DATA_ATUALIZACAO
        """,
        'delta_campo': 'DATA_ATUALIZACAO',
        'delta_padrao': '2000-01-01 00:00:00',
    },
}

def conectar(cfg):
    fb = cfg['firebird']
    kwargs = dict(
        host=fb['host'],
        port=int(fb.get('port', 3050)),
        database=fb['database'],
        user=fb['user'],
        password=fb['password'],
        charset=fb.get('charset', 'WIN1252'),
    )
    if fb.get('fbclient'):
        kwargs['fb_library_name'] = fb['fbclient']
    return fdb.connect(**kwargs)

def _row_to_dict(cursor, row):
    return {desc[0].lower(): val for desc, val in zip(cursor.description, row)}

def ler(conn, tabela, ultimo):
    meta = _TABELAS[tabela]
    cur = conn.cursor()

    if meta['delta_campo'] is None:
        cur.execute(meta['query'])
    else:
        valor = ultimo if ultimo else meta['delta_padrao']
        cur.execute(meta['query'], (valor,))

    while True:
        rows = cur.fetchmany(500)
        if not rows:
            break
        yield [_row_to_dict(cur, r) for r in rows]

def tabelas():
    return list(_TABELAS.keys())

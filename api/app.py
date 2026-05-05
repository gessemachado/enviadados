from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import configparser
import os
from datetime import date, datetime
from decimal import Decimal

app = Flask(__name__)

_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
PG = _cfg['postgres']


def _conn():
    return psycopg2.connect(
        host=PG.get('host', '127.0.0.1'),
        port=int(PG.get('port', 5432)),
        dbname=PG['database'],
        user=PG['user'],
        password=PG['password'],
    )


def _serialize(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _query(sql, params=None):
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [{k: _serialize(v) for k, v in row.items()} for row in cur.fetchall()]
    finally:
        conn.close()


def _ok(rows):
    resp = jsonify(rows)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


def _err(msg, code=400):
    return jsonify({'error': msg}), code


# ── Saídas ────────────────────────────────────────────────────────────────────

@app.route('/api/saidas')
def saidas():
    inicio = request.args.get('inicio')
    fim    = request.args.get('fim')
    if not inicio or not fim:
        return _err('inicio e fim são obrigatórios')
    rows = _query("""
        SELECT id_saida, id_produto, codigo, descricao,
               data_venda, quantidade_vendida, preco_venda,
               sub_total, desconto, id_cliente, id_vendedor,
               id_plano, id_loja, operacao
        FROM saidas
        WHERE data_venda::date BETWEEN %s AND %s
          AND operacao = 'V'
          AND quantidade_vendida > 0
    """, (inicio, fim))
    return _ok(rows)


# ── Cadastros ─────────────────────────────────────────────────────────────────

@app.route('/api/produtos')
def produtos():
    return _ok(_query("""
        SELECT id_produto, codigo, descricao, unidade,
               preco, custo_medio, est_minimo,
               id_grupo, grupo, id_fornecedor, ativo
        FROM produtos
    """))


@app.route('/api/estoque')
def estoque():
    return _ok(_query("SELECT id_produto, id_loja, estoque FROM estoque"))


@app.route('/api/vendedores')
def vendedores():
    return _ok(_query(
        "SELECT id_vendedor, nome, apelido, funcao, ativo, meta, id_loja FROM vendedores"
    ))


@app.route('/api/plano_venda')
def plano_venda():
    return _ok(_query("SELECT id_plano, descricao FROM plano_venda ORDER BY id_plano"))


@app.route('/api/grupos')
def grupos():
    return _ok(_query("""
        SELECT DISTINCT id_grupo, grupo
        FROM produtos
        WHERE id_grupo IS NOT NULL
        ORDER BY id_grupo
    """))


# ── Relatório de estoque / projeção de compras ────────────────────────────────

@app.route('/api/relatorio_estoque', methods=['POST', 'OPTIONS'])
def relatorio_estoque():
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        resp.headers['Access-Control-Allow-Origin']  = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    body         = request.json or {}
    data_inicio  = body.get('data_inicio')
    data_fim     = body.get('data_fim')
    grupos_ids   = body.get('grupos', [])
    id_loja      = int(body.get('id_loja', 1))
    dif_max      = float(body.get('diferenca_max', 5))

    if not data_inicio or not data_fim or not grupos_ids:
        return _err('data_inicio, data_fim e grupos são obrigatórios')

    dt0  = datetime.strptime(data_inicio, '%Y-%m-%d')
    dt1  = datetime.strptime(data_fim,    '%Y-%m-%d')
    dias  = max(1, (dt1 - dt0).days + 1)
    meses = max(1, round(dias / 30.0))

    rows = _query("""
        WITH vendas AS (
            SELECT s.id_produto,
                   SUM(s.quantidade_vendida) AS quant_vend
            FROM saidas s
            WHERE s.data_venda::date BETWEEN %s AND %s
              AND s.operacao = 'V'
              AND s.quantidade_vendida > 0
              AND s.id_loja = %s
            GROUP BY s.id_produto
        ),
        estoques AS (
            SELECT id_produto, SUM(estoque) AS total
            FROM estoque
            WHERE id_loja = %s
            GROUP BY id_produto
        )
        SELECT
            p.id_grupo,
            p.grupo,
            p.codigo,
            p.descricao,
            p.unidade                                                    AS un,
            p.grupo                                                      AS secao,
            v.quant_vend,
            ROUND((v.quant_vend / %s)::numeric, 2)                       AS med_mensal,
            ROUND((v.quant_vend / %s)::numeric, 4)                       AS med_dia,
            ROUND(((v.quant_vend / %s) * 15)::numeric, 2)               AS est_de_segur,
            ROUND(((v.quant_vend / %s) * 30)::numeric, 2)               AS est_maxi,
            COALESCE(e.total, 0)                                         AS estoque_atual,
            ROUND((COALESCE(e.total, 0)
                   - (v.quant_vend / %s) * 30)::numeric, 2)             AS diferenca
        FROM vendas v
        JOIN produtos p ON p.id_produto = v.id_produto
        LEFT JOIN estoques e ON e.id_produto = v.id_produto
        WHERE p.id_grupo = ANY(%s)
          AND (COALESCE(e.total, 0) - (v.quant_vend / %s) * 30) <= %s
        ORDER BY p.id_grupo, p.descricao
    """, (
        data_inicio, data_fim, id_loja,   # vendas
        id_loja,                           # estoques
        meses, dias, dias, dias, dias,     # med_mensal, med_dia, est_segur, est_maxi, diferenca
        grupos_ids,                        # ANY(grupos)
        dias, dif_max,                     # filtro diferenca
    ))
    return _ok(rows)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)

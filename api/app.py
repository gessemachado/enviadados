from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import configparser
import os
import hashlib
import jwt
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps

app = Flask(__name__)

_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
PG = _cfg['postgres']
SECRET = _cfg.get('app', 'secret_key', fallback='obs-secret-2026')


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


def _write(sql, params=None):
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            try:
                return [{k: _serialize(v) for k, v in row.items()} for row in cur.fetchall()]
            except Exception:
                return []
    finally:
        conn.close()


def _ok(data):
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


def _err(msg, code=400):
    resp = jsonify({'error': msg})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp, code


def _cors_preflight():
    resp = app.make_default_options_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return resp


def _hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def _decode_token():
    auth = request.headers.get('Authorization', '')
    token = auth.replace('Bearer ', '').strip()
    if not token:
        return None, 'Token ausente'
    try:
        return jwt.decode(token, SECRET, algorithms=['HS256']), None
    except jwt.ExpiredSignatureError:
        return None, 'Token expirado'
    except jwt.InvalidTokenError:
        return None, 'Token inválido'


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return _cors_preflight()
        payload, err = _decode_token()
        if err:
            return _err(err, 401)
        request.user = payload
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return _cors_preflight()
        payload, err = _decode_token()
        if err:
            return _err(err, 401)
        if not payload.get('admin'):
            return _err('Acesso restrito a administradores', 403)
        request.user = payload
        return f(*args, **kwargs)
    return decorated


def _loja_user():
    user = getattr(request, 'user', {})
    return user.get('id_loja'), bool(user.get('admin'))


def _tenant_user():
    user = getattr(request, 'user', {})
    return user.get('id_tenant'), bool(user.get('admin'))


def _tenant_filter():
    """Retorna o id_tenant efetivo para filtro (None = mostrar tudo)."""
    user = getattr(request, 'user', {})
    is_admin = bool(user.get('admin'))
    if is_admin:
        tf = request.args.get('tenant_filter')
        if tf:
            try:
                return int(tf)
            except (ValueError, TypeError):
                pass
        return None  # admin sem filtro = vê tudo
    return user.get('id_tenant')


# ── Login ─────────────────────────────────────────────────────────────────────

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return _cors_preflight()

    body  = request.json or {}
    email = (body.get('email') or '').strip().lower()
    senha = body.get('senha') or ''

    if not email or not senha:
        return _err('Email e senha são obrigatórios')

    rows = _query("""
        SELECT u.id_usuario, u.nome, u.email, u.senha_hash, u.id_loja,
               l.id_tenant, u.admin, u.ativo
        FROM usuarios u
        LEFT JOIN lojas l ON l.id_loja = u.id_loja
        WHERE u.email = %s
    """, (email,))
    if not rows or not rows[0]['ativo'] or rows[0]['senha_hash'] != _hash(senha):
        return _err('Credenciais inválidas', 401)

    u = rows[0]
    payload = {
        'id_usuario': u['id_usuario'],
        'nome':       u['nome'],
        'email':      u['email'],
        'id_loja':    u['id_loja'],
        'id_tenant':  u['id_tenant'],
        'admin':      u['admin'],
        'exp':        datetime.utcnow() + timedelta(hours=8),
    }
    token = jwt.encode(payload, SECRET, algorithm='HS256')
    return _ok({'token': token, 'nome': u['nome'], 'id_loja': u['id_loja'],
                'id_tenant': u['id_tenant'], 'admin': u['admin']})


# ── Admin — Lojas ─────────────────────────────────────────────────────────────

@app.route('/api/lojas', methods=['GET', 'POST', 'OPTIONS'])
@admin_required
def lojas():
    if request.method == 'GET':
        return _ok(_query("SELECT id_loja, nome, cnpj, id_tenant, ativo FROM lojas ORDER BY nome"))

    body = request.json or {}
    nome = (body.get('nome') or '').strip()
    if not nome:
        return _err('Nome é obrigatório')

    rows = _write(
        "INSERT INTO lojas (nome, cnpj, id_tenant) VALUES (%s, %s, %s) RETURNING id_loja, nome, cnpj, id_tenant, ativo",
        (nome, body.get('cnpj') or None, body.get('id_tenant') or None)
    )
    return _ok(rows[0] if rows else {}), 201


@app.route('/api/lojas/<int:id_loja>', methods=['PATCH', 'OPTIONS'])
@admin_required
def loja_update(id_loja):
    body = request.json or {}
    nome   = (body.get('nome') or '').strip()
    cnpj   = body.get('cnpj') or None
    tenant = body.get('id_tenant') or None
    if not nome:
        return _err('Nome é obrigatório')
    rows = _write(
        "UPDATE lojas SET nome=%s, cnpj=%s, id_tenant=%s WHERE id_loja=%s RETURNING id_loja, nome, cnpj, id_tenant, ativo",
        (nome, cnpj, tenant, id_loja)
    )
    return _ok(rows[0] if rows else {})


# ── Admin — Usuários ──────────────────────────────────────────────────────────

@app.route('/api/usuarios', methods=['GET', 'POST', 'OPTIONS'])
@admin_required
def usuarios():
    if request.method == 'GET':
        return _ok(_query("""
            SELECT u.id_usuario, u.nome, u.email, u.id_loja,
                   l.nome AS loja, u.admin, u.ativo
            FROM usuarios u
            LEFT JOIN lojas l ON l.id_loja = u.id_loja
            ORDER BY u.nome
        """))

    body  = request.json or {}
    nome  = (body.get('nome') or '').strip()
    email = (body.get('email') or '').strip().lower()
    senha = body.get('senha') or ''
    if not nome or not email or not senha:
        return _err('Nome, email e senha são obrigatórios')

    rows = _write(
        """INSERT INTO usuarios (nome, email, senha_hash, id_loja, admin)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id_usuario, nome, email, id_loja, admin, ativo""",
        (nome, email, _hash(senha), body.get('id_loja') or None, bool(body.get('admin', False)))
    )
    return _ok(rows[0] if rows else {}), 201


# ── Saídas ────────────────────────────────────────────────────────────────────

@app.route('/api/saidas')
@token_required
def saidas():
    inicio = request.args.get('inicio')
    fim    = request.args.get('fim')
    if not inicio or not fim:
        return _err('inicio e fim são obrigatórios')

    tenant = _tenant_filter()
    base_sql = """
        SELECT id_saida, id_produto, codigo, descricao,
               data_venda, quantidade_vendida, preco_venda,
               sub_total, desconto, id_cliente, id_vendedor,
               id_plano, id_loja, operacao
        FROM saidas
        WHERE data_venda::date BETWEEN %s AND %s
          AND operacao = 'V' AND quantidade_vendida > 0
    """
    if tenant is None:
        return _ok(_query(base_sql, (inicio, fim)))
    return _ok(_query(base_sql + " AND id_tenant = %s", (inicio, fim, tenant)))


# ── Cadastros ─────────────────────────────────────────────────────────────────

@app.route('/api/produtos')
@token_required
def produtos():
    tenant = _tenant_filter()
    sql = """
        SELECT id_produto, codigo, descricao, unidade,
               preco, custo_medio, est_minimo,
               id_grupo, grupo, id_fornecedor, ativo
        FROM produtos
    """
    if tenant is None:
        return _ok(_query(sql))
    return _ok(_query(sql + " WHERE id_tenant = %s", (tenant,)))


@app.route('/api/estoque')
@token_required
def estoque():
    tenant = _tenant_filter()
    if tenant is None:
        return _ok(_query("SELECT id_produto, id_loja, estoque FROM estoque"))
    return _ok(_query("SELECT id_produto, id_loja, estoque FROM estoque WHERE id_tenant = %s", (tenant,)))


@app.route('/api/vendedores')
@token_required
def vendedores():
    tenant = _tenant_filter()
    sql = "SELECT id_vendedor, nome, apelido, funcao, ativo, meta, id_loja FROM vendedores"
    if tenant is None:
        return _ok(_query(sql))
    return _ok(_query(sql + " WHERE id_tenant = %s", (tenant,)))


@app.route('/api/plano_venda')
@token_required
def plano_venda():
    tenant = _tenant_filter()
    sql = "SELECT id_plano, descricao FROM plano_venda"
    if tenant is None:
        return _ok(_query(sql + " ORDER BY id_plano"))
    return _ok(_query(sql + " WHERE id_tenant = %s ORDER BY id_plano", (tenant,)))


@app.route('/api/grupos')
@token_required
def grupos():
    tenant = _tenant_filter()
    sql = "SELECT DISTINCT id_grupo, grupo FROM produtos WHERE id_grupo IS NOT NULL"
    if tenant is None:
        return _ok(_query(sql + " ORDER BY id_grupo"))
    return _ok(_query(sql + " AND id_tenant = %s ORDER BY id_grupo", (tenant,)))


# ── Relatório de estoque ──────────────────────────────────────────────────────

@app.route('/api/relatorio_estoque', methods=['POST', 'OPTIONS'])
@token_required
def relatorio_estoque():
    body        = request.json or {}
    data_inicio = body.get('data_inicio')
    data_fim    = body.get('data_fim')
    grupos_ids  = body.get('grupos', [])
    dif_max     = float(body.get('diferenca_max', 5))

    tenant = _tenant_filter()
    if tenant is None:
        tenant = int(body.get('id_tenant', 1))

    if not data_inicio or not data_fim or not grupos_ids:
        return _err('data_inicio, data_fim e grupos são obrigatórios')

    dt0   = datetime.strptime(data_inicio, '%Y-%m-%d')
    dt1   = datetime.strptime(data_fim,    '%Y-%m-%d')
    dias  = max(1, (dt1 - dt0).days + 1)
    meses = max(1, round(dias / 30.0))

    rows = _query("""
        WITH vendas AS (
            SELECT s.id_produto, SUM(s.quantidade_vendida) AS quant_vend
            FROM saidas s
            WHERE s.data_venda::date BETWEEN %s AND %s
              AND s.operacao = 'V' AND s.quantidade_vendida > 0 AND s.id_tenant = %s
            GROUP BY s.id_produto
        ),
        estoques AS (
            SELECT id_produto, SUM(estoque) AS total
            FROM estoque WHERE id_tenant = %s GROUP BY id_produto
        )
        SELECT p.id_grupo, p.grupo, p.codigo, p.descricao,
               p.unidade AS un, p.grupo AS secao, v.quant_vend,
               ROUND((v.quant_vend / %s)::numeric, 2)            AS med_mensal,
               ROUND((v.quant_vend / %s)::numeric, 4)            AS med_dia,
               ROUND(((v.quant_vend / %s) * 15)::numeric, 2)    AS est_de_segur,
               ROUND(((v.quant_vend / %s) * 30)::numeric, 2)    AS est_maxi,
               COALESCE(e.total, 0)                              AS estoque_atual,
               ROUND((COALESCE(e.total,0)-(v.quant_vend/%s)*30)::numeric, 2) AS diferenca
        FROM vendas v
        JOIN produtos p ON p.id_produto = v.id_produto
        LEFT JOIN estoques e ON e.id_produto = v.id_produto
        WHERE p.id_grupo = ANY(%s)
          AND (COALESCE(e.total,0) - (v.quant_vend/%s)*30) <= %s
        ORDER BY p.id_grupo, p.descricao
    """, (data_inicio, data_fim, tenant, tenant,
          meses, dias, dias, dias, dias, grupos_ids, dias, dif_max))
    return _ok(rows)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)

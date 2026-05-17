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
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, DELETE, OPTIONS'
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


# ── Perfil — Troca de senha ───────────────────────────────────────────────────

@app.route('/api/perfil/senha', methods=['PATCH', 'OPTIONS'])
@token_required
def perfil_senha():
    if request.method == 'OPTIONS':
        return _cors_preflight()

    body = request.json or {}
    senha_atual  = body.get('senha_atual') or ''
    nova_senha   = body.get('nova_senha') or ''
    confirmar    = body.get('confirmar') or ''

    if not senha_atual or not nova_senha or not confirmar:
        return _err('Todos os campos são obrigatórios')
    if nova_senha != confirmar:
        return _err('Nova senha e confirmação não coincidem')
    if len(nova_senha) < 6:
        return _err('Nova senha deve ter pelo menos 6 caracteres')

    id_usuario = request.user.get('id_usuario')
    rows = _query("SELECT senha_hash FROM usuarios WHERE id_usuario = %s", (id_usuario,))
    if not rows or rows[0]['senha_hash'] != _hash(senha_atual):
        return _err('Senha atual incorreta', 401)

    _write("UPDATE usuarios SET senha_hash = %s WHERE id_usuario = %s",
           (_hash(nova_senha), id_usuario))
    return _ok({'ok': True})


# ── Admin — Editar / Excluir Usuário ─────────────────────────────────────────

@app.route('/api/usuarios/<int:id_usuario>', methods=['PATCH', 'DELETE', 'OPTIONS'])
@admin_required
def usuario_update(id_usuario):
    if request.method == 'OPTIONS':
        return _cors_preflight()

    if request.method == 'DELETE':
        _write("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        return _ok({'ok': True})

    body  = request.json or {}
    nome  = (body.get('nome') or '').strip()
    email = (body.get('email') or '').strip().lower()
    loja  = body.get('id_loja') or None
    admin = bool(body.get('admin', False))
    nova_senha = body.get('nova_senha') or ''

    if not nome or not email:
        return _err('Nome e e-mail são obrigatórios')

    if nova_senha:
        if len(nova_senha) < 6:
            return _err('Senha deve ter pelo menos 6 caracteres')
        _write(
            "UPDATE usuarios SET nome=%s, email=%s, senha_hash=%s, id_loja=%s, admin=%s WHERE id_usuario=%s",
            (nome, email, _hash(nova_senha), loja, admin, id_usuario)
        )
    else:
        _write(
            "UPDATE usuarios SET nome=%s, email=%s, id_loja=%s, admin=%s WHERE id_usuario=%s",
            (nome, email, loja, admin, id_usuario)
        )
    rows = _query(
        "SELECT u.id_usuario, u.nome, u.email, u.id_loja, l.nome AS loja, u.admin, u.ativo FROM usuarios u LEFT JOIN lojas l ON l.id_loja=u.id_loja WHERE u.id_usuario=%s",
        (id_usuario,)
    )
    return _ok(rows[0] if rows else {})


# ── Admin — Zerar dados de um tenant ─────────────────────────────────────────

@app.route('/api/lojas/<int:id_loja>/dados', methods=['DELETE', 'OPTIONS'])
@admin_required
def zerar_dados(id_loja):
    if request.method == 'OPTIONS':
        return _cors_preflight()

    rows = _query("SELECT id_tenant FROM lojas WHERE id_loja = %s", (id_loja,))
    if not rows or not rows[0]['id_tenant']:
        return _err('Loja não encontrada ou sem id_tenant configurado')

    tenant = rows[0]['id_tenant']
    tabelas = [
        'saidas', 'estoque', 'produtos', 'clientes',
        'vendedores', 'fornecedores', 'caixa',
        'contas_receber', 'contas_pagar', 'plano_venda',
    ]
    conn = _conn()
    totais = {}
    try:
        with conn.cursor() as cur:
            for t in tabelas:
                cur.execute(f"DELETE FROM {t} WHERE id_tenant = %s", (tenant,))
                totais[t] = cur.rowcount
            conn.commit()
    finally:
        conn.close()

    return _ok({'ok': True, 'id_tenant': tenant, 'deletados': totais})


# ── Clientes ─────────────────────────────────────────────────────────────────

@app.route('/api/clientes/resumo')
@token_required
def clientes_resumo():
    inicio = request.args.get('inicio')
    fim    = request.args.get('fim')
    if not inicio or not fim:
        return _err('inicio e fim são obrigatórios')

    tenant = _tenant_filter()
    t_clause = "" if tenant is None else "AND s.id_tenant = %(tenant)s"
    params = {'inicio': inicio, 'fim': fim + ' 23:59:59', 'tenant': tenant}

    kpi = _query(f"""
        SELECT
            COUNT(DISTINCT s.nota_fiscal)                                          AS total_pedidos,
            COUNT(DISTINCT s.id_cliente) FILTER (
                WHERE s.id_cliente IS NOT NULL AND s.id_cliente <> '')              AS clientes_unicos,
            COALESCE(SUM(s.sub_total) /
                NULLIF(COUNT(*), 0), 0)                                             AS ticket_medio,
            COALESCE(SUM(s.sub_total), 0)                                           AS total_periodo
        FROM saidas s
        WHERE s.data_venda BETWEEN %(inicio)s AND %(fim)s
          AND s.operacao = 'V' AND s.quantidade_vendida > 0
          {t_clause}
    """, params)

    top10 = _query(f"""
        SELECT
            s.id_cliente,
            COALESCE(c.cliente, s.id_cliente, 'Sem identificação') AS nome,
            COUNT(DISTINCT s.nota_fiscal)                         AS pedidos,
            SUM(s.sub_total)                                       AS total,
            SUM(s.sub_total) /
                NULLIF(COUNT(*), 0)                                AS ticket_medio,
            MAX(s.data_venda)::date                                AS ultima_compra
        FROM saidas s
        LEFT JOIN clientes c
               ON c.id_cliente = s.id_cliente
              AND c.id_tenant  = s.id_tenant
        WHERE s.data_venda BETWEEN %(inicio)s AND %(fim)s
          AND s.operacao = 'V' AND s.quantidade_vendida > 0
          AND s.id_cliente IS NOT NULL AND s.id_cliente <> ''
          {t_clause}
        GROUP BY s.id_cliente, c.cliente
        ORDER BY total DESC
        LIMIT 30
    """, params)

    return _ok({'kpi': kpi[0] if kpi else {}, 'top10': top10})


@app.route('/api/clientes/inativos')
@token_required
def clientes_inativos():
    dias = int(request.args.get('dias', 60))
    tenant = _tenant_filter()
    t_clause = "" if tenant is None else "AND c.id_tenant = %(tenant)s"
    t_clause_s = "" if tenant is None else "AND s.id_tenant = %(tenant)s"
    params = {'dias': dias, 'tenant': tenant}

    rows = _query(f"""
        SELECT
            c.id_cliente,
            c.cliente                                              AS nome,
            c.cgc_cpf,
            COALESCE(c.celular, c.telefone, '')                   AS contato,
            MAX(s.data_venda)::date                               AS ultima_compra,
            CURRENT_DATE - MAX(s.data_venda)::date                AS dias_inativo,
            COUNT(DISTINCT s.nota_fiscal)                        AS total_pedidos,
            COALESCE(SUM(s.sub_total), 0)                         AS total_gasto
        FROM clientes c
        LEFT JOIN saidas s
               ON s.id_cliente = c.id_cliente
              AND s.operacao = 'V' AND s.quantidade_vendida > 0
              {t_clause_s}
        WHERE c.ativo IN ('S','1','true','t')
          {t_clause}
        GROUP BY c.id_cliente, c.cliente, c.cgc_cpf, c.celular, c.telefone
        HAVING MAX(s.data_venda) < CURRENT_DATE - %(dias)s
            OR MAX(s.data_venda) IS NULL
        ORDER BY dias_inativo DESC NULLS LAST
        LIMIT 100
    """, params)

    return _ok(rows)


@app.route('/api/clientes/produtos')
@token_required
def clientes_produtos():
    inicio = request.args.get('inicio')
    fim    = request.args.get('fim')
    if not inicio or not fim:
        return _err('inicio e fim são obrigatórios')

    tenant = _tenant_filter()
    t_clause = "" if tenant is None else "AND s.id_tenant = %(tenant)s"
    params = {'inicio': inicio, 'fim': fim + ' 23:59:59', 'tenant': tenant}

    base = f"""
        SELECT
            COALESCE(s.descricao, s.codigo, s.id_produto) AS nome,
            s.codigo,
            COUNT(DISTINCT s.nota_fiscal)                AS pedidos,
            SUM(s.quantidade_vendida)                     AS quantidade,
            SUM(s.sub_total)                              AS total
        FROM saidas s
        WHERE s.data_venda BETWEEN %(inicio)s AND %(fim)s
          AND s.operacao = 'V' AND s.quantidade_vendida > 0
          AND s.id_cliente IS NOT NULL AND s.id_cliente <> ''
          {t_clause}
        GROUP BY s.id_produto, s.descricao, s.codigo
    """
    por_pedidos = _query(base + " ORDER BY pedidos DESC LIMIT 50", params)
    por_volume  = _query(base + " ORDER BY total   DESC LIMIT 50", params)
    return _ok({'por_pedidos': por_pedidos, 'por_volume': por_volume})


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
    sql = "SELECT id_grupo, MAX(grupo) AS grupo FROM produtos WHERE id_grupo IS NOT NULL"
    if tenant is None:
        return _ok(_query(sql + " GROUP BY id_grupo ORDER BY id_grupo"))
    return _ok(_query(sql + " AND id_tenant = %s GROUP BY id_grupo ORDER BY id_grupo", (tenant,)))


# ── Relatório de estoque ──────────────────────────────────────────────────────

@app.route('/api/relatorio_estoque', methods=['POST', 'OPTIONS'])
@token_required
def relatorio_estoque():
    body        = request.json or {}
    data_inicio = body.get('data_inicio')
    data_fim    = body.get('data_fim')
    grupos_nomes = body.get('grupos', [])
    dif_max      = float(body.get('diferenca_max', 5))

    tenant = _tenant_filter()
    if tenant is None:
        tenant = int(body.get('id_tenant', 1))

    if not data_inicio or not data_fim or not grupos_nomes:
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
               p.unidade AS un, v.quant_vend,
               ROUND((v.quant_vend / %s)::numeric, 2)            AS med_mensal,
               ROUND((v.quant_vend / %s)::numeric, 4)            AS med_dia,
               ROUND(((v.quant_vend / %s) * 15)::numeric, 2)    AS est_de_segur,
               ROUND(((v.quant_vend / %s) * 30)::numeric, 2)    AS est_maxi,
               COALESCE(e.total, 0)                              AS estoque_atual,
               ROUND((COALESCE(e.total,0)-(v.quant_vend/%s)*30)::numeric, 2) AS diferenca,
               COALESCE(p.pb, 0)                                 AS pb,
               ROUND((GREATEST(0, -1*(COALESCE(e.total,0)-(v.quant_vend/%s)*30)) * COALESCE(p.pb, 0))::numeric, 2) AS peso_total
        FROM vendas v
        JOIN produtos p ON p.id_produto = v.id_produto
        LEFT JOIN estoques e ON e.id_produto = v.id_produto
        WHERE p.grupo = ANY(%s)
          AND (COALESCE(e.total,0) - (v.quant_vend/%s)*30) <= %s
        ORDER BY p.id_grupo, p.descricao
    """, (data_inicio, data_fim, tenant, tenant,
          meses, dias, dias, dias, dias, dias, grupos_nomes, dias, dif_max))
    return _ok(rows)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)

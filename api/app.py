from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras
import configparser
import os
import hashlib
import jwt
import json
import re
import time
import uuid
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps

app = Flask(__name__)

_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
PG = _cfg['postgres']
SECRET = _cfg.get('app', 'secret_key', fallback='obs-secret-2026')
MEDIA_DIR = _cfg.get('media', 'dir', fallback='/var/www/enviadados/media')
MEDIA_PUBLIC_BASE = _cfg.get('media', 'public_base', fallback='').rstrip('/')
GUPSHUP_WEBHOOK_TOKEN = _cfg.get('gupshup', 'webhook_token', fallback='')


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
               sub_total, desconto, val_desp_adm,
               val_enc_fed, val_icms_recolher, custo_total, id_cliente, id_vendedor,
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


# ── Marketing WhatsApp (Gupshup) ─────────────────────────────────────────────

GUPSHUP_HOST = 'api.gupshup.io'
GUPSHUP_URL = 'https://api.gupshup.io/wa/api/v1/template/msg'


def _gupshup_call(method, path, apikey, body=None, content_type=None, extra_headers=None, timeout=25):
    """Proxy HTTP genérico pra api.gupshup.io. Retorna (status, body_str)."""
    headers = {'apikey': apikey}
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        if content_type:
            headers['Content-Type'] = content_type
        if isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        elif isinstance(body, str):
            data = body.encode()
        else:
            data = urllib.parse.urlencode(body).encode()
            headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')
    req = urllib.request.Request(
        f'https://{GUPSHUP_HOST}{path}', data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        b = e.read().decode('utf-8', errors='replace') if e.fp else str(e)
        return e.code, b
    except urllib.error.URLError as e:
        return 0, f'network: {e.reason}'


def _passthrough(status, body):
    """Retorna a resposta do upstream como JSON (parseando se possível)."""
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = {'raw': body}
    resp = jsonify(parsed)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp, (status or 502)


def _normaliza_fone(v):
    if not v:
        return ''
    d = re.sub(r'\D', '', str(v))
    if not d:
        return ''
    if not d.startswith('55') and len(d) in (10, 11):
        d = '55' + d
    return d


def _gupshup_send(apikey, appname, source, destination, template_id, params,
                  media_url=None, media_type=None):
    fields = {
        'channel':     'whatsapp',
        'source':      source,
        'destination': destination,
        'src.name':    appname,
        'template':    json.dumps({'id': template_id, 'params': params or []}),
    }
    if media_url:
        t = (media_type or 'image').lower()
        fields['message'] = json.dumps({'type': t, t: {'link': media_url}})
    payload = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        GUPSHUP_URL, data=payload, method='POST',
        headers={'apikey': apikey, 'Content-Type': 'application/x-www-form-urlencoded'},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode('utf-8', errors='replace')
            return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else str(e)
        return e.code, body
    except urllib.error.URLError as e:
        return 0, f'network error: {e.reason}'


def _log_envio(tenant, id_usuario, id_cliente, destino, appname, source,
               template_id, template_nome, params, status, http_status,
               message_id, response_body, lote_id):
    _write("""
        INSERT INTO gupshup_envios
            (id_tenant, id_usuario, id_cliente, destino, appname, source,
             template_id, template_nome, params, status, http_status,
             message_id, response_body, lote_id)
        VALUES (%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s)
    """, (tenant, id_usuario, id_cliente, destino, appname, source,
          template_id, template_nome,
          psycopg2.extras.Json(params or []), status, http_status,
          message_id, response_body, lote_id))


def _parse_gupshup_resp(http_status, body):
    msg_id, st = None, 'error'
    try:
        j = json.loads(body)
        msg_id = j.get('messageId')
        if 200 <= http_status < 300 and (j.get('status') in ('submitted', 'success')):
            st = 'submitted'
    except Exception:
        pass
    return st, msg_id


@app.route('/api/gupshup/send', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_send():
    body = request.json or {}
    apikey      = (body.get('apikey') or '').strip()
    appname     = (body.get('appname') or '').strip()
    source      = re.sub(r'\D', '', str(body.get('source') or ''))
    destination = _normaliza_fone(body.get('destination'))
    template_id = (body.get('template_id') or '').strip()
    template_nome = (body.get('template_nome') or '').strip() or None
    params      = body.get('params') or []
    id_cliente  = body.get('id_cliente') or None
    media_url   = body.get('media_url') or None
    media_type  = body.get('media_type') or None

    if not apikey or not appname or not source or not destination or not template_id:
        return _err('apikey, appname, source, destination e template_id são obrigatórios')

    tenant, _ = _tenant_user()
    id_usuario = request.user.get('id_usuario')

    http_status, resp_body = _gupshup_send(
        apikey, appname, source, destination, template_id, params, media_url, media_type
    )
    st, msg_id = _parse_gupshup_resp(http_status, resp_body)

    _log_envio(tenant, id_usuario, id_cliente, destination, appname, source,
               template_id, template_nome, params, st, http_status,
               msg_id, resp_body, None)

    return _ok({
        'ok':          st == 'submitted',
        'status':      st,
        'http_status': http_status,
        'message_id':  msg_id,
        'response':    resp_body,
    })


@app.route('/api/gupshup/enviar-lote', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_enviar_lote():
    body = request.json or {}
    apikey      = (body.get('apikey') or '').strip()
    appname     = (body.get('appname') or '').strip()
    source      = re.sub(r'\D', '', str(body.get('source') or ''))
    template_id = (body.get('template_id') or '').strip()
    template_nome = (body.get('template_nome') or '').strip() or None
    destinos    = body.get('destinos') or []  # [{destination, params:[], id_cliente?}]
    media_url   = body.get('media_url') or None
    media_type  = body.get('media_type') or None

    if not apikey or not appname or not source or not template_id:
        return _err('apikey, appname, source e template_id são obrigatórios')
    if not isinstance(destinos, list) or not destinos:
        return _err('destinos deve ser lista não vazia')
    if len(destinos) > 250:
        return _err('máximo de 250 destinos por lote (limite MM Lite)')

    tenant, _ = _tenant_user()
    id_usuario = request.user.get('id_usuario')
    lote_id = uuid.uuid4().hex

    resultados = []
    for i, d in enumerate(destinos):
        destino = _normaliza_fone(d.get('destination'))
        params  = d.get('params') or []
        id_cliente = d.get('id_cliente') or None

        if not destino:
            resultados.append({'destination': d.get('destination'), 'ok': False,
                               'erro': 'telefone inválido'})
            continue

        http_status, resp_body = _gupshup_send(
            apikey, appname, source, destino, template_id, params, media_url, media_type
        )
        st, msg_id = _parse_gupshup_resp(http_status, resp_body)

        _log_envio(tenant, id_usuario, id_cliente, destino, appname, source,
                   template_id, template_nome, params, st, http_status,
                   msg_id, resp_body, lote_id)

        resultados.append({
            'destination': destino, 'id_cliente': id_cliente,
            'ok': st == 'submitted', 'status': st,
            'http_status': http_status, 'message_id': msg_id,
        })

        if i < len(destinos) - 1:
            time.sleep(0.25)

    total = len(resultados)
    ok = sum(1 for r in resultados if r.get('ok'))
    return _ok({'lote_id': lote_id, 'total': total, 'enviados': ok,
                'falhas': total - ok, 'resultados': resultados})


_MEDIA_EXT_TO_TYPE = {
    '.png':  ('image', 'image/png'),
    '.jpg':  ('image', 'image/jpeg'),
    '.jpeg': ('image', 'image/jpeg'),
    '.webp': ('image', 'image/webp'),
    '.gif':  ('image', 'image/gif'),
    '.mp4':  ('video', 'video/mp4'),
    '.pdf':  ('document', 'application/pdf'),
}
_MEDIA_MAX_BYTES = 20 * 1024 * 1024


@app.route('/api/gupshup/upload-media', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_upload_media():
    f = request.files.get('file')
    if not f or not f.filename:
        return _err('campo "file" obrigatório (multipart/form-data)')

    orig = secure_filename(f.filename) or 'upload.bin'
    ext = os.path.splitext(orig)[1].lower()
    if ext not in _MEDIA_EXT_TO_TYPE:
        return _err(f'extensão {ext or "(vazia)"} não suportada. Aceitas: {sorted(_MEDIA_EXT_TO_TYPE)}')
    media_type, _mime = _MEDIA_EXT_TO_TYPE[ext]

    data = f.read(_MEDIA_MAX_BYTES + 1)
    if not data:
        return _err('arquivo vazio')
    if len(data) > _MEDIA_MAX_BYTES:
        return _err(f'arquivo excede {_MEDIA_MAX_BYTES // (1024 * 1024)} MB')

    tenant, _u = _tenant_user()
    digest = hashlib.sha256(data).hexdigest()[:16]
    safe_name = f'{tenant or 0}_{int(time.time())}_{digest}{ext}'

    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        with open(os.path.join(MEDIA_DIR, safe_name), 'wb') as out:
            out.write(data)
    except OSError as e:
        return _err(f'erro salvando mídia: {e}', 500)

    if MEDIA_PUBLIC_BASE:
        media_url = f'{MEDIA_PUBLIC_BASE}/{safe_name}'
    else:
        scheme = request.headers.get('X-Forwarded-Proto') or ('https' if request.is_secure else 'http')
        host = request.headers.get('X-Forwarded-Host') or request.headers.get('Host') or request.host
        media_url = f'{scheme}://{host}/media/{safe_name}'

    return _ok({
        'mediaUrl': media_url,
        'provider': 'vps',
        'filename': safe_name,
        'size': len(data),
        'mediaType': media_type,
    })


@app.route('/api/gupshup/templates', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_templates():
    b = request.json or {}
    apikey = (b.get('apikey') or '').strip()
    app_id = (b.get('app_id') or '').strip()
    if not apikey or not app_id:
        return _err('apikey e app_id obrigatórios')
    status, body = _gupshup_call('GET', f'/wa/app/{urllib.parse.quote(app_id)}/template', apikey)
    return _passthrough(status, body)


@app.route('/api/gupshup/wallet', methods=['GET', 'OPTIONS'])
@token_required
def gupshup_wallet():
    apikey = (request.args.get('apikey') or '').strip()
    if not apikey:
        return _err('apikey obrigatório')
    status, body = _gupshup_call('GET', '/wa/api/v1/wallet/balance', apikey)
    try:
        data = json.loads(body)
    except Exception:
        data = body
    return _ok({'http_status': status, 'data': data})


@app.route('/api/gupshup/msg-status', methods=['GET', 'OPTIONS'])
@token_required
def gupshup_msg_status():
    apikey  = (request.args.get('apikey') or '').strip()
    app_id  = (request.args.get('app_id') or '').strip()
    msg_id  = (request.args.get('msg_id') or '').strip()
    app_name = (request.args.get('app_name') or '').strip()
    if not apikey or not app_id or not msg_id:
        return _err('apikey, app_id e msg_id obrigatórios')

    tries = [
        f'/wa/app/{urllib.parse.quote(app_id)}/msg/{urllib.parse.quote(msg_id)}',
        f'/wa/app/{urllib.parse.quote(app_id)}/msg-event/{urllib.parse.quote(msg_id)}',
    ]
    if app_name:
        tries.append(f'/wa/app/{urllib.parse.quote(app_name)}/msg-event/{urllib.parse.quote(msg_id)}')

    results = []
    for p in tries:
        st, body = _gupshup_call('GET', p, apikey)
        results.append({'path': p, 'status': st, 'body': body[:250]})
        if st == 200 and body and body not in ('[]', '{}'):
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            return _ok({'endpoint': p, 'http_status': st, 'data': parsed, 'tried': results})

    return _ok({
        'warning': 'Nenhum endpoint retornou dados. Gupshup só entrega estado por callback webhook — se o webhook não estiver configurado, esses endpoints devolvem vazio.',
        'tried': results,
    })


@app.route('/api/gupshup/send-text', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_send_text():
    b = request.json or {}
    apikey  = (b.get('apikey') or '').strip()
    appname = (b.get('appname') or '').strip()
    source  = re.sub(r'\D', '', str(b.get('source') or ''))
    dest    = _normaliza_fone(b.get('destination'))
    texto   = b.get('texto') or ''
    if not apikey or not appname or not source or not dest or not texto:
        return _err('apikey/appname/source/destination/texto obrigatórios')

    fields = {
        'channel':     'whatsapp',
        'source':      source,
        'destination': dest,
        'src.name':    appname,
        'message':     json.dumps({'type': 'text', 'text': texto}),
    }
    status, body = _gupshup_call('POST', '/wa/api/v1/msg', apikey, body=fields,
                                 content_type='application/x-www-form-urlencoded')
    st, msg_id = _parse_gupshup_resp(status, body)

    tenant, _u = _tenant_user()
    id_usuario = request.user.get('id_usuario')
    _log_envio(tenant, id_usuario, None, dest, appname, source,
               None, '[TEXTO-SESSAO]', [f'{len(texto)} chars'],
               st, status, msg_id, body, None)

    aviso = None
    if st != 'submitted' and re.search(r'1002|no active session', body, re.I):
        aviso = f'⚠ SEM SESSÃO ATIVA: {dest} precisa te mandar mensagem primeiro (janela 24h).'
    return _ok({
        'ok': st == 'submitted', 'status': st, 'http_status': status,
        'message_id': msg_id, 'response': body, 'aviso_sessao': aviso,
    })


@app.route('/api/gupshup/create-template', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_create_template():
    b = request.json or {}
    apikey  = (b.get('apikey') or '').strip()
    app_id  = (b.get('app_id') or '').strip()
    element = (b.get('element_name') or '').strip()
    content = b.get('content') or ''
    if not apikey or not app_id or not element or not content:
        return _err('apikey, app_id, element_name e content obrigatórios')

    fields = {
        'elementName':                 element,
        'languageCode':                b.get('language_code') or 'pt_BR',
        'category':                    b.get('category') or 'MARKETING',
        'templateType':                b.get('template_type') or 'TEXT',
        'vertical':                    b.get('vertical') or 'MARKETING',
        'content':                     content,
        'example':                     b.get('example') or content,
        'enableSample':                'true',
        'allowTemplateCategoryChange': 'true',
    }
    if b.get('footer'):
        fields['footer'] = b['footer']
    if b.get('example_media_id'):
        fields['exampleMedia'] = b['example_media_id']
    elif b.get('example_media'):
        fields['exampleMedia'] = b['example_media']

    status, body = _gupshup_call('POST', f'/wa/app/{urllib.parse.quote(app_id)}/template',
                                 apikey, body=fields,
                                 content_type='application/x-www-form-urlencoded')
    return _passthrough(status, body)


@app.route('/api/gupshup/upload-sample-media', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_upload_sample_media():
    apikey = (request.args.get('apikey') or '').strip()
    app_id = (request.args.get('app_id') or '').strip()
    if not apikey or not app_id:
        return _err('apikey e app_id na query obrigatórios')

    f = request.files.get('file')
    if not f or not f.filename:
        return _err('campo "file" obrigatório (multipart/form-data)')

    file_bytes = f.read()
    mime = f.mimetype or 'image/png'
    safe = secure_filename(f.filename) or f'sample_{int(time.time())}.png'

    boundary = f'----g{uuid.uuid4().hex[:16]}'
    parts = []
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file_type"\r\n\r\n{mime}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file_length"\r\n\r\n{len(file_bytes)}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe}"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    parts.append(file_bytes)
    parts.append(f'\r\n--{boundary}--\r\n'.encode())
    body_bytes = b''.join(parts)

    status, body = _gupshup_call(
        'POST',
        f'/wa/app/{urllib.parse.quote(app_id)}/template/upload/media',
        apikey,
        body=body_bytes,
        content_type=f'multipart/form-data; boundary={boundary}',
    )
    try:
        j = json.loads(body)
    except Exception:
        j = None
    handle = None
    if isinstance(j, dict):
        h = j.get('handleId')
        if isinstance(h, dict):
            handle = h.get('message')
        elif isinstance(h, str):
            handle = h
    if status != 200 or not handle:
        return _err(f'Gupshup: {body[:300]}', status or 502)
    return _ok({'handleId': handle, 'mediaType': mime.split('/')[0]})


@app.route('/api/gupshup/optin', methods=['POST', 'OPTIONS'])
@token_required
def gupshup_optin_platform():
    """Marca o usuário como opted-in NA GUPSHUP (WhatsApp platform).
    Distinto de /api/optin (que é registro local de auditoria LGPD)."""
    b = request.json or {}
    apikey  = (b.get('apikey') or '').strip()
    app_id  = (b.get('app_id') or '').strip()
    app_name = (b.get('app_name') or 'sertaocomunic').strip()
    phone   = _normaliza_fone(b.get('phone'))
    if not apikey or not app_id or not phone:
        return _err('apikey, app_id e phone obrigatórios')

    tries = [
        (f'/sm/api/v1/app/opt/in/{urllib.parse.quote(app_name)}',
         f'user={urllib.parse.quote(phone)}', 'application/x-www-form-urlencoded'),
        (f'/sm/api/v1/app/opt/in/{urllib.parse.quote(app_name)}',
         json.dumps({'user': phone}), 'application/json'),
        (f'/wa/api/v1/app/opt/in/{urllib.parse.quote(phone)}',
         'channel=whatsapp', 'application/x-www-form-urlencoded'),
        (f'/wa/app/{urllib.parse.quote(app_id)}/optin',
         f'user={urllib.parse.quote(phone)}', 'application/x-www-form-urlencoded'),
        (f'/wa/app/{urllib.parse.quote(app_id)}/wallet/optin/{urllib.parse.quote(phone)}',
         '', 'application/x-www-form-urlencoded'),
    ]

    results = []
    for path, body_str, ct in tries:
        st, rb = _gupshup_call('POST', path, apikey, body=body_str, content_type=ct)
        results.append({'path': path, 'ct': ct, 'status': st, 'body': rb[:250]})
        if 200 <= st < 300:
            try:
                parsed = json.loads(rb)
            except Exception:
                parsed = rb
            if isinstance(parsed, dict) and parsed.get('status') == 'error':
                continue
            return _ok({'ok': True, 'endpoint': path, 'http_status': st,
                        'data': parsed, 'tried': results})

    return _ok({'ok': False, 'tried': results,
                'dica': 'Se falhou em todos, faça manualmente em https://www.gupshup.io/whatsappassistant/#/account/opt-in'})


@app.route('/api/gupshup/list-optin', methods=['GET', 'OPTIONS'])
@token_required
def gupshup_list_optin_platform():
    apikey   = (request.args.get('apikey') or '').strip()
    app_name = (request.args.get('app_name') or '').strip()
    if not apikey or not app_name:
        return _err('apikey e app_name obrigatórios')
    path = f'/sm/api/v1/users/{urllib.parse.quote(app_name)}'
    status, body = _gupshup_call('GET', path, apikey)
    try:
        data = json.loads(body)
    except Exception:
        data = body
    return _ok({'http_status': status, 'endpoint': path, 'data': data})


_GUPSHUP_EVENT_TO_COL = {
    'enqueued':  'sent_at',
    'sent':      'sent_at',
    'delivered': 'delivered_at',
    'read':      'read_at',
    'failed':    'failed_at',
}


@app.route('/api/gupshup/webhook', methods=['POST', 'GET', 'OPTIONS'])
def gupshup_webhook():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    if request.method == 'GET':
        return _ok({'ok': True, 'service': 'gupshup-webhook'})

    if GUPSHUP_WEBHOOK_TOKEN:
        supplied = request.args.get('token') or request.headers.get('X-Webhook-Token', '')
        if supplied != GUPSHUP_WEBHOOK_TOKEN:
            return _err('token inválido', 401)

    body = request.get_json(silent=True) or {}
    ev_type = body.get('type') or ''
    payload = body.get('payload') or {}

    if ev_type != 'message-event':
        return _ok({'ignored': ev_type or 'unknown'})

    msg_id = payload.get('id') or payload.get('gsId')
    st = (payload.get('type') or '').lower()
    if not msg_id or not st:
        return _ok({'ignored': 'missing id or type'})

    col = _GUPSHUP_EVENT_TO_COL.get(st)
    if not col:
        return _ok({'ignored': f'status {st} não mapeado'})

    err_code = err_reason = None
    if st == 'failed':
        p2 = payload.get('payload') or {}
        err_code = (str(p2.get('code') or '')[:50]) or None
        err_reason = (str(p2.get('reason') or '')[:500]) or None

    _write(f"""
        UPDATE gupshup_envios
           SET status = %s,
               {col} = COALESCE({col}, NOW()),
               error_code = COALESCE(%s, error_code),
               error_reason = COALESCE(%s, error_reason)
         WHERE message_id = %s
    """, (st, err_code, err_reason, msg_id))

    return _ok({'updated': st, 'message_id': msg_id})


@app.route('/api/gupshup/envios')
@token_required
def gupshup_envios():
    tenant = _tenant_filter()
    limite = min(int(request.args.get('limite', 200)), 1000)
    lote   = request.args.get('lote_id')

    sql = """
        SELECT e.id, e.id_cliente,
               COALESCE(c.cliente, '') AS cliente_nome,
               e.destino, e.appname, e.template_id, e.template_nome,
               e.params, e.status, e.http_status, e.message_id,
               e.lote_id, e.enviado_em,
               e.sent_at, e.delivered_at, e.read_at, e.failed_at,
               e.error_code, e.error_reason,
               u.nome AS usuario_nome
        FROM gupshup_envios e
        LEFT JOIN clientes c
               ON c.id_cliente = e.id_cliente AND c.id_tenant = e.id_tenant
        LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
        WHERE 1=1
    """
    params = []
    if tenant is not None:
        sql += " AND e.id_tenant = %s"
        params.append(tenant)
    if lote:
        sql += " AND e.lote_id = %s"
        params.append(lote)
    sql += " ORDER BY e.enviado_em DESC LIMIT %s"
    params.append(limite)

    return _ok(_query(sql, tuple(params)))


@app.route('/api/optin', methods=['POST', 'OPTIONS'])
@token_required
def optin_registrar():
    body = request.json or {}
    telefone = _normaliza_fone(body.get('telefone'))
    if not telefone:
        return _err('telefone obrigatório')

    id_cliente = body.get('id_cliente') or None
    canal      = (body.get('canal') or 'whatsapp').strip()
    texto      = (body.get('texto') or '').strip() or None
    origem     = (body.get('origem') or 'manual').strip()
    observacao = (body.get('observacao') or '').strip() or None

    tenant, _u = _tenant_user()
    if tenant is None:
        return _err('tenant obrigatório', 400)
    id_usuario = request.user.get('id_usuario')

    # Reativa se já existe inativo, ou cria novo
    _write("""
        UPDATE cliente_optin
           SET ativo = FALSE, data_optout = NOW()
         WHERE id_tenant = %s AND telefone = %s AND ativo = TRUE
    """, (tenant, telefone))

    _write("""
        INSERT INTO cliente_optin
            (id_tenant, id_cliente, telefone, canal, texto, origem,
             ativo, data_optin, id_usuario, observacao)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), %s, %s)
    """, (tenant, id_cliente, telefone, canal, texto, origem, id_usuario, observacao))

    return _ok({'ok': True, 'telefone': telefone, 'ativo': True})


@app.route('/api/optout', methods=['POST', 'OPTIONS'])
@token_required
def optin_remover():
    body = request.json or {}
    telefone = _normaliza_fone(body.get('telefone'))
    if not telefone:
        return _err('telefone obrigatório')

    tenant, _u = _tenant_user()
    if tenant is None:
        return _err('tenant obrigatório', 400)

    _write("""
        UPDATE cliente_optin
           SET ativo = FALSE, data_optout = NOW()
         WHERE id_tenant = %s AND telefone = %s AND ativo = TRUE
    """, (tenant, telefone))

    return _ok({'ok': True, 'telefone': telefone, 'ativo': False})


@app.route('/api/optin/status')
@token_required
def optin_status():
    telefones_raw = request.args.get('telefones') or request.args.get('telefone') or ''
    telefones = [_normaliza_fone(t) for t in telefones_raw.split(',') if t.strip()]
    if not telefones:
        return _ok({})

    tenant = _tenant_filter()
    where = ["telefone = ANY(%s)", "ativo = TRUE"]
    params = [telefones]
    if tenant is not None:
        where.append("id_tenant = %s"); params.append(tenant)

    rows = _query(f"""
        SELECT telefone, id_cliente, canal, texto, origem, data_optin, id_usuario
          FROM cliente_optin
         WHERE {' AND '.join(where)}
    """, tuple(params))

    return _ok({r['telefone']: r for r in rows})


@app.route('/api/optin/list')
@token_required
def optin_list():
    tenant = _tenant_filter()
    limite = min(int(request.args.get('limite', 500)), 2000)
    where = ["1=1"]
    params = []
    if tenant is not None:
        where.append("o.id_tenant = %s"); params.append(tenant)

    rows = _query(f"""
        SELECT o.id, o.id_tenant, o.id_cliente, o.telefone, o.canal, o.texto,
               o.origem, o.ativo, o.data_optin, o.data_optout, o.observacao,
               COALESCE(c.cliente, '') AS cliente_nome,
               u.nome AS usuario_nome
          FROM cliente_optin o
          LEFT JOIN clientes c
                 ON c.id_cliente = o.id_cliente AND c.id_tenant = o.id_tenant
          LEFT JOIN usuarios u ON u.id_usuario = o.id_usuario
         WHERE {' AND '.join(where)}
         ORDER BY o.data_optin DESC
         LIMIT %s
    """, tuple(params) + (limite,))
    return _ok(rows)


@app.route('/api/gupshup/clientes-marketing')
@token_required
def gupshup_clientes_marketing():
    tenant = _tenant_filter()
    cidade = request.args.get('cidade')
    uf     = request.args.get('uf')
    busca  = request.args.get('busca')
    inativo_dias = request.args.get('inativo_dias')

    where = ["COALESCE(c.whatsapp, c.celular, c.telefone, '') <> ''",
             "c.ativo IN ('S','1','true','t')"]
    params = {}
    if tenant is not None:
        where.append("c.id_tenant = %(tenant)s"); params['tenant'] = tenant
    if cidade:
        where.append("UPPER(c.cidade) = UPPER(%(cidade)s)"); params['cidade'] = cidade
    if uf:
        where.append("UPPER(c.uf) = UPPER(%(uf)s)"); params['uf'] = uf
    if busca:
        where.append("UPPER(c.cliente) LIKE UPPER(%(busca)s)")
        params['busca'] = f'%{busca}%'
    if inativo_dias:
        try:
            params['dias'] = int(inativo_dias)
            where.append("(c.ultima_compra IS NULL OR c.ultima_compra < CURRENT_DATE - %(dias)s)")
        except (ValueError, TypeError):
            pass

    sql = f"""
        SELECT c.id_cliente, c.cliente AS nome, c.cgc_cpf,
               COALESCE(c.whatsapp, c.celular, c.telefone) AS telefone,
               c.cidade, c.uf, c.ultima_compra
        FROM clientes c
        WHERE {' AND '.join(where)}
        ORDER BY c.cliente
        LIMIT 1000
    """
    return _ok(_query(sql, params))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)

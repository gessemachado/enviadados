#!/usr/bin/env python3
"""
seed_demo.py — Massa de dados fictícios para a loja "teste" (id_tenant=2)
Execute no servidor: python seed_demo.py
"""
import configparser, os, random, sys
from datetime import date, datetime, timedelta
import psycopg2, psycopg2.extras

# ── Config ─────────────────────────────────────────────────────────────────────
_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
PG = _cfg['postgres']

ID_TENANT = 2
ID_LOJA   = 2

random.seed(42)  # reproduzível

def _conn():
    return psycopg2.connect(
        host=PG.get('host','127.0.0.1'), port=int(PG.get('port',5432)),
        dbname=PG['database'], user=PG['user'], password=PG['password']
    )

# ── Dados mestres ──────────────────────────────────────────────────────────────

PLANOS = [
    ('TST_PL001','PIX'),
    ('TST_PL002','Cartão de Crédito'),
    ('TST_PL003','Cartão de Débito'),
    ('TST_PL004','Dinheiro'),
    ('TST_PL005','Boleto Bancário'),
    ('TST_PL006','Crediário Próprio'),
]
PLANO_PESOS = ['TST_PL001']*40 + ['TST_PL002']*25 + ['TST_PL003']*15 + \
              ['TST_PL004']*15 + ['TST_PL005']*3  + ['TST_PL006']*2

VENDEDORES = [
    ('TST_VD001','João Silva','João','Vendedor','S',18000,'joao@demo.com','77991110001'),
    ('TST_VD002','Maria Souza','Maria','Vendedora','S',15000,'maria@demo.com','77991110002'),
    ('TST_VD003','Carlos Oliveira','Carlos','Vendedor','S',12000,'carlos@demo.com','77991110003'),
    ('TST_VD004','Ana Lima','Ana','Vendedora','S',14000,'ana@demo.com','77991110004'),
    ('TST_VD005','Pedro Santos','Pedro','Gerente','S',22000,'pedro@demo.com','77991110005'),
]

CLIENTES = [
    ('TST_CL001','Construtora Horizonte Ltda','12.345.678/0001-90','(77) 3211-1001','(77) 99111-0001','Juazeiro','BA'),
    ('TST_CL002','José Ferreira da Silva','234.567.890-12','','(77) 99111-0002','Juazeiro','BA'),
    ('TST_CL003','Ana Paula Rocha','345.678.901-23','','(77) 99111-0003','Petrolina','PE'),
    ('TST_CL004','Imobiliária Central Ltda','23.456.789/0001-01','(77) 3211-2001','(77) 99111-0004','Juazeiro','BA'),
    ('TST_CL005','Marcos Antônio Lima','456.789.012-34','','(77) 99111-0005','Sobradinho','BA'),
    ('TST_CL006','Empreiteira Nordeste SA','34.567.890/0001-12','(77) 3211-3001','(77) 99111-0006','Petrolina','PE'),
    ('TST_CL007','Raimundo Torres','567.890.123-45','','(77) 99111-0007','Casa Nova','BA'),
    ('TST_CL008','Construtora Dunas Ltda','45.678.901/0001-23','(77) 3211-4001','(77) 99111-0008','Juazeiro','BA'),
    ('TST_CL009','Fernanda Costa','678.901.234-56','','(77) 99111-0009','Juazeiro','BA'),
    ('TST_CL010','Supermercado Bom Preço','56.789.012/0001-34','(77) 3211-5001','(77) 99111-0010','Juazeiro','BA'),
    ('TST_CL011','Gilberto Santana','789.012.345-67','','(77) 99111-0011','Petrolina','PE'),
    ('TST_CL012','Padaria Sabor do Norte','67.890.123/0001-45','(77) 3211-6001','(77) 99111-0012','Juazeiro','BA'),
    ('TST_CL013','Luciana Mendes','890.123.456-78','','(77) 99111-0013','Juazeiro','BA'),
    ('TST_CL014','Posto Horizonte SA','78.901.234/0001-56','(77) 3211-7001','(77) 99111-0014','Sobradinho','BA'),
    ('TST_CL015','Roberto Campos','901.234.567-89','','(77) 99111-0015','Casa Nova','BA'),
    ('TST_CL016','Escola Municipal São Francisco','89.012.345/0001-67','(77) 3211-8001','','Juazeiro','BA'),
    ('TST_CL017','Carla Vieira','012.345.678-90','','(77) 99111-0017','Juazeiro','BA'),
    ('TST_CL018','Hospital Regional de Juazeiro','90.123.456/0001-78','(77) 3211-9001','','Juazeiro','BA'),
    ('TST_CL019','Sérgio Alves','123.456.789-01','','(77) 99111-0019','Petrolina','PE'),
    ('TST_CL020','Distribuidora Central Ltda','01.234.567/0001-89','(77) 3211-0001','','Juazeiro','BA'),
]
CLIENTES_IDS = [c[0] for c in CLIENTES] + [''] * 30  # 30% balcão

FORNECEDORES = [
    ('TST_FOR001','Ferrosteel Distribuidora Ltda','Ferrosteel','12.111.000/0001-01','São Paulo','SP','(11) 3111-1001','contato@ferrosteel.com.br','(11) 94111-1001'),
    ('TST_FOR002','Elétrica Nordeste Comércio','Elétrica NE','23.222.000/0001-02','Recife','PE','(81) 3222-2002','vendas@eletricanordeste.com.br','(81) 94222-2002'),
    ('TST_FOR003','Hidrafast Distribuidora SA','Hidrafast','34.333.000/0001-03','Salvador','BA','(71) 3333-3003','comercial@hidrafast.com.br','(71) 94333-3003'),
    ('TST_FOR004','Tintas e Cores Ltda','T&C Tintas','45.444.000/0001-04','Fortaleza','CE','(85) 3444-4004','vendas@tintascores.com.br','(85) 94444-4004'),
    ('TST_FOR005','Construtiva Materiais SA','Construtiva','56.555.000/0001-05','Salvador','BA','(71) 3555-5005','pedidos@construtiva.com.br','(71) 94555-5005'),
    ('TST_FOR006','Ferramentas Brasil Ltda','Ferramentas BR','67.666.000/0001-06','São Paulo','SP','(11) 3666-6006','contato@ferramentasbr.com.br','(11) 94666-6006'),
]

# (id, codigo, descricao, unidade, preco, custo_medio, est_minimo, id_grupo, grupo, id_fornecedor)
PRODUTOS = [
    # Ferragens
    ('TST_PR001','0001','Parafuso Sext. Zincado 5/16" cx 100un','CX', 18.90, 11.00,  5,1,'Ferragens','TST_FOR001'),
    ('TST_PR002','0002','Parafuso Chipboard 4x40 cx 200un',     'CX', 12.50,  7.00, 10,1,'Ferragens','TST_FOR001'),
    ('TST_PR003','0003','Prego Liso 17x27 kg',                  'KG',  9.80,  5.50, 20,1,'Ferragens','TST_FOR001'),
    ('TST_PR004','0004','Prego Liso 19x36 kg',                  'KG', 10.20,  5.80, 15,1,'Ferragens','TST_FOR001'),
    ('TST_PR005','0005','Abraçadeira Nylon P-19 pct 100un',     'PCT',  8.40,  4.50, 10,1,'Ferragens','TST_FOR001'),
    ('TST_PR006','0006','Dobradiça 3x2" Cromada par',           'PAR',  7.60,  4.00, 20,1,'Ferragens','TST_FOR001'),
    ('TST_PR007','0007','Fechadura Banheiro Redonda',            'UN', 28.90, 17.00,  5,1,'Ferragens','TST_FOR001'),
    ('TST_PR008','0008','Cadeado Zincado 40mm',                 'UN', 22.50, 13.00,  8,1,'Ferragens','TST_FOR001'),
    ('TST_PR009','0009','Corrente Zincada 4mm',                 'M',   4.90,  2.80, 50,1,'Ferragens','TST_FOR001'),
    ('TST_PR010','0010','Trinco Embutir Inox',                  'UN', 14.20,  8.00, 10,1,'Ferragens','TST_FOR001'),
    # Ferramentas
    ('TST_PR011','0011','Chave de Fenda Phillips 1/4"',         'UN', 12.90,  7.00,  5,2,'Ferramentas','TST_FOR006'),
    ('TST_PR012','0012','Chave de Fenda Simples 3/16"',         'UN', 11.90,  6.50,  5,2,'Ferramentas','TST_FOR006'),
    ('TST_PR013','0013','Alicate Universal 8"',                 'UN', 32.50, 19.00,  5,2,'Ferramentas','TST_FOR006'),
    ('TST_PR014','0014','Alicate de Pressão 10"',               'UN', 48.90, 28.00,  3,2,'Ferramentas','TST_FOR006'),
    ('TST_PR015','0015','Martelo Cabo Madeira 27mm',            'UN', 29.90, 17.00,  5,2,'Ferramentas','TST_FOR006'),
    ('TST_PR016','0016','Fita Métrica 5m',                      'UN', 15.50,  9.00, 10,2,'Ferramentas','TST_FOR006'),
    ('TST_PR017','0017','Trena 30m Nylon',                      'UN', 42.00, 24.00,  3,2,'Ferramentas','TST_FOR006'),
    ('TST_PR018','0018','Serra Manual 22"',                     'UN', 38.50, 22.00,  3,2,'Ferramentas','TST_FOR006'),
    ('TST_PR019','0019','Nível de Bolha 60cm',                  'UN', 24.90, 14.00,  4,2,'Ferramentas','TST_FOR006'),
    ('TST_PR020','0020','Espátula Cabo Madeira 3"',             'UN',  9.90,  5.50, 10,2,'Ferramentas','TST_FOR006'),
    # Material Elétrico
    ('TST_PR021','0021','Fio Elétrico 1,5mm rolo 100m',        'RL', 98.00, 58.00,  2,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR022','0022','Fio Elétrico 2,5mm rolo 100m',        'RL',148.00, 88.00,  2,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR023','0023','Tomada Elétrica 2P+T Branca',         'UN', 14.90,  8.50, 10,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR024','0024','Interruptor Simples Branco',           'UN', 12.50,  7.00, 10,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR025','0025','Disjuntor Monopolar 10A',              'UN', 18.90, 11.00,  5,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR026','0026','Disjuntor Monopolar 20A',              'UN', 19.90, 11.50,  5,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR027','0027','Lâmpada LED 9W E27 6500K',            'UN', 14.90,  8.50, 10,3,'Material Elétrico','TST_FOR002'),
    ('TST_PR028','0028','Fita LED 5m 6000K c/ fonte',          'UN', 45.90, 27.00,  3,3,'Material Elétrico','TST_FOR002'),
    # Material Hidráulico
    ('TST_PR029','0029','Cano PVC 25mm 6m',                    'UN', 24.50, 14.00,  5,4,'Material Hidráulico','TST_FOR003'),
    ('TST_PR030','0030','Cano PVC 32mm 6m',                    'UN', 32.90, 19.00,  5,4,'Material Hidráulico','TST_FOR003'),
    ('TST_PR031','0031','Joelho PVC 25mm',                      'UN',  2.80,  1.50, 20,4,'Material Hidráulico','TST_FOR003'),
    ('TST_PR032','0032','Tê PVC 25mm',                         'UN',  3.40,  1.80, 15,4,'Material Hidráulico','TST_FOR003'),
    ('TST_PR033','0033','Registro de Gaveta Bronze 1/2"',      'UN', 38.90, 22.00,  5,4,'Material Hidráulico','TST_FOR003'),
    ('TST_PR034','0034','Torneira Cozinha Bica Alta',           'UN', 68.90, 40.00,  3,4,'Material Hidráulico','TST_FOR003'),
    ('TST_PR035','0035','Sifão Plástico Cozinha',              'UN', 22.50, 13.00,  5,4,'Material Hidráulico','TST_FOR003'),
    # Tintas e Acabamentos
    ('TST_PR036','0036','Tinta Latex Branca 18L',              'GL',148.00, 88.00,  2,5,'Tintas e Acabamentos','TST_FOR004'),
    ('TST_PR037','0037','Tinta Acrílica Premium 3,6L',         'GL', 78.00, 46.00,  3,5,'Tintas e Acabamentos','TST_FOR004'),
    ('TST_PR038','0038','Massa Corrida PVA 25kg',              'BL', 68.50, 40.00,  3,5,'Tintas e Acabamentos','TST_FOR004'),
    ('TST_PR039','0039','Selador Acrílico 18L',                'GL', 98.00, 58.00,  2,5,'Tintas e Acabamentos','TST_FOR004'),
    ('TST_PR040','0040','Esmalte Sintético Preto 3,6L',        'GL', 82.00, 48.00,  3,5,'Tintas e Acabamentos','TST_FOR004'),
    # Material de Construção
    ('TST_PR041','0041','Argamassa ACII 20kg',                 'SC', 22.90, 13.00, 10,6,'Material de Construção','TST_FOR005'),
    ('TST_PR042','0042','Cimento CP II 50kg',                  'SC', 38.50, 22.00, 20,6,'Material de Construção','TST_FOR005'),
    ('TST_PR043','0043','Rejunte Cinza 1kg',                   'KG',  9.90,  5.50, 10,6,'Material de Construção','TST_FOR005'),
    ('TST_PR044','0044','Impermeabilizante 18L',               'GL',128.00, 75.00,  2,6,'Material de Construção','TST_FOR005'),
    ('TST_PR045','0045','Tela Soldada Q-138 2,45x6m',         'UN',178.00,105.00,  2,6,'Material de Construção','TST_FOR005'),
]
# Estoque gerado dinamicamente (ver abaixo)

# ── Geração de vendas ──────────────────────────────────────────────────────────

def gerar_saidas():
    hoje  = date(2026, 5, 5)
    inicio = date(2025, 5, 1)
    saidas = []
    cupom_seq = 10001

    # Multiplicador mensal para simular sazonalidade
    sazon = {1:0.80, 2:0.75, 3:0.90, 4:1.05, 5:1.10,
             6:1.00, 7:0.95, 8:1.00, 9:1.05,10:1.10,11:1.20,12:1.30}

    d = inicio
    while d <= hoje:
        if d.weekday() == 6:  # domingo fechado
            d += timedelta(days=1)
            continue

        mult = sazon[d.month] * (1.15 if d.weekday() == 5 else 1.0)  # sábado+15%
        n_trans = max(3, int(random.gauss(10, 3) * mult))

        for t in range(n_trans):
            cupom = f'TST{cupom_seq:07d}'
            cupom_seq += 1
            hora = random.randint(8, 18)
            minuto = random.randint(0, 59)
            dt_venda = datetime(d.year, d.month, d.day, hora, minuto)
            n_itens = random.choices([1,2,3,4],[50,30,15,5])[0]
            produtos_dia = random.sample(PRODUTOS, min(n_itens, len(PRODUTOS)))
            id_vend = random.choice([v[0] for v in VENDEDORES])
            id_cli  = random.choice(CLIENTES_IDS)
            id_plan = random.choice(PLANO_PESOS)

            for i, prod in enumerate(produtos_dia):
                pid, cod, desc = prod[0], prod[1], prod[2]
                preco_base = prod[4]
                # Variação de ±5% no preço
                preco = round(preco_base * random.uniform(0.95, 1.05), 2)
                # Quantidade: maioria unitária, alguns em maior qtd
                qtd = random.choices([1,2,3,5,10],[50,25,12,8,5])[0]
                if prod[3] in ('KG','M'):  # vendidos por kg/metro
                    qtd = round(random.uniform(1.0, 20.0), 3)
                desc_val = round(preco * qtd * random.uniform(0, 0.03), 2)  # até 3% desconto
                subtotal = round(preco * qtd - desc_val, 2)

                id_saida = f'TST-{d.year}{d.month:02d}{d.day:02d}-{cupom_seq:06d}-{i}'
                saidas.append({
                    'id_saida': id_saida,
                    'id_produto': pid,
                    'codigo': cod,
                    'descricao': desc,
                    'numero_cupom': cupom,
                    'nota_fiscal': None,
                    'data_venda': dt_venda,
                    'quantidade_vendida': float(qtd),
                    'preco_venda': preco,
                    'sub_total': subtotal,
                    'desconto': desc_val,
                    'id_cliente': id_cli or None,
                    'id_vendedor': id_vend,
                    'id_plano': id_plan,
                    'id_loja': ID_LOJA,
                    'operacao': 'V',
                    'id_tenant': ID_TENANT,
                })
        d += timedelta(days=1)
    return saidas

def gerar_caixa(saidas):
    entradas = []
    seq = 1
    # Agrupa por cupom e plano
    cupons = {}
    for s in saidas:
        k = (s['numero_cupom'], s['id_plano'])
        cupons.setdefault(k, []).append(s)

    for (cupom, id_plan), itens in cupons.items():
        total = round(sum(i['sub_total'] for i in itens), 2)
        dt = itens[0]['data_venda'].date()
        plano_desc = next((p[1] for p in PLANOS if p[0]==id_plan), 'Pagamento')
        entradas.append({
            'id_caixa': f'CX-V-{seq:07d}',
            'data': dt,
            'valor': total,
            'historico': f'Venda Cupom {cupom}',
            'nat': 'E',
            'natureza': 'Entrada',
            'id_conta': id_plan,
            'conta': plano_desc,
            'id_cliente': itens[0]['id_cliente'],
            'id_vendedor': itens[0]['id_vendedor'],
            'id_loja': ID_LOJA,
            'baixado': 'S',
            'bx': 'S',
            'data_baixa': dt,
            'id_tenant': ID_TENANT,
        })
        seq += 1

    # Compras a fornecedores (saídas de caixa mensais)
    inicio = date(2025, 5, 1)
    hoje   = date(2026, 5, 5)
    d = inicio
    while d <= hoje:
        if d.day in (5, 15, 25):
            for for_ in random.sample(FORNECEDORES, random.randint(1,3)):
                val = round(random.uniform(2000, 12000), 2)
                entradas.append({
                    'id_caixa': f'CX-C-{seq:07d}',
                    'data': d,
                    'valor': -val,
                    'historico': f'Pagto {for_[2]} NF {random.randint(1000,9999)}',
                    'nat': 'S',
                    'natureza': 'Saída',
                    'id_conta': 'COMPRAS',
                    'conta': 'Compras de Mercadoria',
                    'id_cliente': None,
                    'id_vendedor': None,
                    'id_loja': ID_LOJA,
                    'baixado': 'S',
                    'bx': 'S',
                    'data_baixa': d,
                    'id_tenant': ID_TENANT,
                })
                seq += 1
        d += timedelta(days=1)

    return entradas

def gerar_contas_receber():
    contas = []
    hoje = date(2026, 5, 5)
    # Crediário: clientes com parcelas em aberto
    for i, cli in enumerate(CLIENTES[:8]):
        for parcela in range(1, random.randint(2,5)):
            emissao  = hoje - timedelta(days=random.randint(30,90))
            venc     = emissao + timedelta(days=30*parcela)
            val      = round(random.uniform(500, 4000), 2)
            recebido = val if venc < hoje else 0.0
            contas.append({
                'id_fatura': f'TST-FAT-{i+1:04d}',
                'numero': f'{i+1:04d}',
                'parcela': parcela,
                'emissao': emissao,
                'vencimento': venc,
                'valor_parcela': val,
                'valor_total': val,
                'recebido': recebido,
                'juros': 0.0,
                'desconto': 0.0,
                'id_cliente': cli[0],
                'id_vendedor': random.choice([v[0] for v in VENDEDORES]),
                'loja': ID_LOJA,
                'bx': 'S' if recebido else 'N',
                'situacao': 'BAIXADO' if recebido else 'ABERTO',
                'data_receb': venc if recebido else None,
                'id_tenant': ID_TENANT,
            })
    return contas

def gerar_contas_pagar():
    contas = []
    hoje = date(2026, 5, 5)
    for i, for_ in enumerate(FORNECEDORES):
        for parcela in range(1, random.randint(2,4)):
            emissao  = hoje - timedelta(days=random.randint(20,60))
            venc     = emissao + timedelta(days=30*parcela)
            val      = round(random.uniform(3000, 15000), 2)
            recebido = val if venc < hoje else 0.0
            contas.append({
                'id_fatura': f'TST-PAG-{i+1:04d}',
                'numero': f'{i+1:04d}',
                'parcela': parcela,
                'emissao': emissao,
                'vencimento': venc,
                'valor_parcela': val,
                'valor_total': val,
                'recebido': recebido,
                'juros': 0.0,
                'desconto': 0.0,
                'id_cliente': None,
                'id_vendedor': None,
                'loja': ID_LOJA,
                'bx': 'S' if recebido else 'N',
                'situacao': 'BAIXADO' if recebido else 'ABERTO',
                'data_receb': venc if recebido else None,
                'id_tenant': ID_TENANT,
            })
    return contas

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print('Conectando ao banco...')
    db = _conn()
    cur = db.cursor()

    print('Limpando dados anteriores do tenant 2...')
    for t in ['saidas','estoque','produtos','clientes','vendedores','fornecedores',
              'caixa','contas_receber','contas_pagar','plano_venda']:
        cur.execute(f'DELETE FROM {t} WHERE id_tenant = %s', (ID_TENANT,))
    db.commit()

    print('Inserindo planos de venda...')
    for r in PLANOS:
        cur.execute('INSERT INTO plano_venda (id_plano,descricao,id_tenant) VALUES (%s,%s,%s)',
                    (r[0], r[1], ID_TENANT))
    db.commit()

    print('Inserindo fornecedores...')
    for r in FORNECEDORES:
        cur.execute('''INSERT INTO fornecedores
            (id_fornecedor,razao_soc,nome_fanta,cnpj,cidade,uf,telefone,email,whatsapp,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],ID_TENANT))
    db.commit()

    print('Inserindo clientes...')
    hoje = date(2026,5,5)
    for r in CLIENTES:
        ultima = hoje - timedelta(days=random.randint(1,60))
        cadastro = hoje - timedelta(days=random.randint(200,800))
        cur.execute('''INSERT INTO clientes
            (id_cliente,cliente,cgc_cpf,telefone,celular,cidade,uf,ativo,ultima_compra,cadastro,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (r[0],r[1],r[2],r[3],r[4],r[5],r[6],'S',ultima,cadastro,ID_TENANT))
    db.commit()

    print('Inserindo vendedores...')
    for r in VENDEDORES:
        cur.execute('''INSERT INTO vendedores
            (id_vendedor,nome,apelido,funcao,ativo,meta,email,celular,id_loja,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],ID_LOJA,ID_TENANT))
    db.commit()

    print('Inserindo produtos...')
    for r in PRODUTOS:
        cur.execute('''INSERT INTO produtos
            (id_produto,codigo,descricao,unidade,preco,custo_medio,est_minimo,
             id_grupo,grupo,id_fornecedor,ativo,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'S',%s)''',
            (r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],ID_TENANT))
    db.commit()

    print('Inserindo estoque...')
    for r in PRODUTOS:
        id_est = f'EST-{r[0]}-{ID_LOJA}'
        qtd = round(random.uniform(r[6]*1.5, r[6]*8), 3)  # acima do mínimo
        cur.execute('''INSERT INTO estoque
            (id_estoque,id_produto,cod_produto,id_loja,estoque,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s)''',
            (id_est, r[0], r[1], ID_LOJA, qtd, ID_TENANT))
    db.commit()

    print('Gerando vendas (aguarde ~30s)...')
    saidas = gerar_saidas()
    print(f'  {len(saidas)} itens de venda gerados. Inserindo...')
    psycopg2.extras.execute_batch(cur, '''
        INSERT INTO saidas
            (id_saida,id_produto,codigo,descricao,numero_cupom,nota_fiscal,
             data_venda,quantidade_vendida,preco_venda,sub_total,desconto,
             id_cliente,id_vendedor,id_plano,id_loja,operacao,id_tenant)
        VALUES
            (%(id_saida)s,%(id_produto)s,%(codigo)s,%(descricao)s,%(numero_cupom)s,%(nota_fiscal)s,
             %(data_venda)s,%(quantidade_vendida)s,%(preco_venda)s,%(sub_total)s,%(desconto)s,
             %(id_cliente)s,%(id_vendedor)s,%(id_plano)s,%(id_loja)s,%(operacao)s,%(id_tenant)s)
    ''', saidas, page_size=500)
    db.commit()

    print('Inserindo caixa...')
    caixa = gerar_caixa(saidas)
    psycopg2.extras.execute_batch(cur, '''
        INSERT INTO caixa
            (id_caixa,data,valor,historico,nat,natureza,id_conta,conta,
             id_cliente,id_vendedor,id_loja,baixado,bx,data_baixa,id_tenant)
        VALUES
            (%(id_caixa)s,%(data)s,%(valor)s,%(historico)s,%(nat)s,%(natureza)s,%(id_conta)s,%(conta)s,
             %(id_cliente)s,%(id_vendedor)s,%(id_loja)s,%(baixado)s,%(bx)s,%(data_baixa)s,%(id_tenant)s)
    ''', caixa, page_size=500)
    db.commit()
    print(f'  {len(caixa)} registros de caixa.')

    print('Inserindo contas a receber...')
    cr = gerar_contas_receber()
    for r in cr:
        cur.execute('''INSERT INTO contas_receber
            (id_fatura,numero,parcela,emissao,vencimento,valor_parcela,valor_total,
             recebido,juros,desconto,id_cliente,id_vendedor,loja,bx,situacao,data_receb,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING''',
            (r['id_fatura'],r['numero'],r['parcela'],r['emissao'],r['vencimento'],
             r['valor_parcela'],r['valor_total'],r['recebido'],r['juros'],r['desconto'],
             r['id_cliente'],r['id_vendedor'],r['loja'],r['bx'],r['situacao'],r['data_receb'],r['id_tenant']))
    db.commit()

    print('Inserindo contas a pagar...')
    cp = gerar_contas_pagar()
    for r in cp:
        cur.execute('''INSERT INTO contas_pagar
            (id_fatura,numero,parcela,emissao,vencimento,valor_parcela,valor_total,
             recebido,juros,desconto,id_cliente,id_vendedor,loja,bx,situacao,data_receb,id_tenant)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING''',
            (r['id_fatura'],r['numero'],r['parcela'],r['emissao'],r['vencimento'],
             r['valor_parcela'],r['valor_total'],r['recebido'],r['juros'],r['desconto'],
             r['id_cliente'],r['id_vendedor'],r['loja'],r['bx'],r['situacao'],r['data_receb'],r['id_tenant']))
    db.commit()

    cur.close()
    db.close()

    total_venda = sum(s['sub_total'] for s in saidas)
    print(f'\n✓ Concluído!')
    print(f'  Vendas: {len(saidas)} itens | R$ {total_venda:,.2f} em 13 meses')
    print(f'  Caixa:  {len(caixa)} registros')
    print(f'  CR:     {len(cr)} parcelas | CP: {len(cp)} parcelas')

if __name__ == '__main__':
    main()
